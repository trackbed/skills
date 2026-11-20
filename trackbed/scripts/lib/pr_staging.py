"""Run directories below ``<repo>/.trackbed/`` that stage files for a Pull Request.

Git's local exclude file hides ``.trackbed/``, so no workflow commits a staged file.
Callers own what a staged file may be and what happens to it afterwards.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import time
from pathlib import Path
from typing import Any, Literal

EXCLUDE_ENTRY = "/.trackbed/"
RUN_ID_PATTERN = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")


class StagingError(ValueError):
    """Raised when a file cannot safely be staged for a Pull Request."""


class UnignoredSourceError(StagingError):
    """Raised when the publication workflow would commit the source document."""


def fail_if_symlink_chain(path: Path, stop: Path) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise StagingError(f"{current} must not be a symlink")
        if current == stop or current.parent == current:
            return
        current = current.parent


def resolve_repo_root(value: str) -> Path:
    root = Path(value).expanduser()
    if not root.is_absolute():
        raise StagingError("--repo-root must be an absolute path")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise StagingError("--repo-root must be a directory")
    return root


def staging_root(repo_root: Path, directory: Path) -> Path:
    root = repo_root / directory
    fail_if_symlink_chain(root, repo_root)
    return root


def run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def ensure_excluded(repo_root: Path) -> None:
    result = run_git(repo_root, "rev-parse", "--git-path", "info/exclude")
    if result.returncode != 0 or not result.stdout.strip():
        raise StagingError("could not locate Git's local exclude file")
    exclude = Path(result.stdout.strip())
    if not exclude.is_absolute():
        exclude = repo_root / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if EXCLUDE_ENTRY not in existing.splitlines():
        with exclude.open("a", encoding="utf-8") as handle:
            handle.write(("" if existing.endswith("\n") or not existing else "\n") + EXCLUDE_ENTRY + "\n")


def require_ignored_run(repo_root: Path, run_dir: Path) -> None:
    relative = run_dir.relative_to(repo_root)
    # The trailing slash lets Git evaluate directory rules before the run exists.
    if run_git(repo_root, "check-ignore", "-q", "--", f"{relative}/").returncode != 0:
        raise StagingError(f"{relative} must be ignored by Git before it can hold staged Pull Request files")


def open_run(repo_root: Path, directory: Path, schema_version: int) -> dict[str, str]:
    """Create a run directory with an empty manifest below ``directory``."""
    ensure_excluded(repo_root)
    root = staging_root(repo_root, directory)
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + secrets.token_hex(4)
    run_dir = root / run_id
    require_ignored_run(repo_root, run_dir)
    root.mkdir(parents=True, exist_ok=True)
    fail_if_symlink_chain(root, repo_root)
    run_dir.mkdir(mode=0o700)
    manifest = run_dir / "manifest.json"
    write_manifest(manifest, {"schema_version": schema_version, "run_id": run_id, "entries": []})
    return {"dir": str(run_dir), "manifest": str(manifest), "run_id": run_id}


def manifest_location(repo_root: Path, directory: Path, manifest_arg: str) -> Path:
    manifest = Path(manifest_arg).expanduser()
    if not manifest.is_absolute():
        raise StagingError("--manifest must be an absolute path")
    manifest = Path(os.path.abspath(manifest))
    root = staging_root(repo_root, directory)
    try:
        relative = manifest.relative_to(root)
    except ValueError as exc:
        raise StagingError(f"manifest must be below {root}") from exc
    if len(relative.parts) != 2 or relative.parts[1] != "manifest.json" or not RUN_ID_PATTERN.match(relative.parts[0]):
        raise StagingError(f"manifest must be <run-id>/manifest.json below {root}")
    fail_if_symlink_chain(manifest, repo_root)
    if not manifest.is_file():
        raise StagingError("manifest must be a regular file")
    require_ignored_run(repo_root, manifest.parent)
    return manifest


def load_manifest(manifest: Path, schema_version: int) -> dict[str, Any]:
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StagingError(f"manifest is not readable JSON: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != schema_version:
        raise StagingError(f"manifest schema_version must be {schema_version}")
    if not isinstance(payload.get("entries"), list):
        raise StagingError("manifest entries must be an array")
    return payload


def write_manifest(manifest: Path, payload: dict[str, Any]) -> None:
    temporary = manifest.with_name("manifest.json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, manifest)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_to_directory(path: Path, directory: Path) -> Path | None:
    """Find the relative path, including when an ancestor has a different spelling."""
    if path.is_relative_to(directory):
        return path.relative_to(directory)
    if directory.is_dir():
        for parent in path.parents:
            if parent.samefile(directory):
                return path.relative_to(parent)
    return None


def tracked_path(repo_root: Path, relative: Path) -> Path | None:
    # Git spells index entries literally, even when the filesystem accepts a case alias.
    result = run_git(repo_root, "ls-files", "-z", "--", f":(icase,literal){relative}")
    if result.returncode != 0:
        raise UnignoredSourceError(f"could not verify that {relative} is outside Git's include set")
    candidates = [Path(name) for name in result.stdout.split("\0") if name]
    if relative in candidates:
        return relative
    source = repo_root / relative
    for candidate in candidates:
        path = repo_root / candidate
        try:
            same_entry = os.path.samestat(path.lstat(), source.lstat()) and path.parent.samefile(source.parent)
        except FileNotFoundError:
            continue
        if not same_entry:
            continue
        # A case-sensitive directory can contain distinct entries that are hard links.
        if path.name == source.name or not any(entry.name == source.name for entry in source.parent.iterdir()):
            return candidate
    return None


def reject_uncommitted_repo_file(
    repo_root: Path, source: Path, *, tracked_policy: Literal["allow", "clean", "reject"] = "allow"
) -> None:
    """Check Git's view of a source before validating the file for staging."""
    try:
        # Git stages a symlink itself. Resolve its parent so the final component still names that entry.
        git_source = source.parent.resolve(strict=True) / source.name
        git_source.lstat()
    except FileNotFoundError as exc:
        raise StagingError(f"{source} must be a regular file, not a symlink") from exc
    relative = relative_to_directory(git_source, repo_root)
    if relative is None:
        return
    tracked = tracked_path(repo_root, relative)
    if tracked is not None:
        if tracked_policy == "allow":
            return
        status = run_git(
            repo_root,
            "--no-optional-locks",
            "--literal-pathspecs",
            "status",
            "--porcelain=v1",
            "-uno",
            "--",
            str(tracked),
        )
        if status.returncode != 0:
            raise UnignoredSourceError(f"could not verify that {tracked} is outside Git's include set")
        if status.stdout:
            raise UnignoredSourceError(f"{tracked} has local changes that the PR workflow could commit")
        if tracked_policy == "reject":
            raise StagingError(f"{tracked} is tracked by Git, so reviewers already have it in the repository")
        return
    # A leading colon in a filename would otherwise start a Git pathspec.
    ignored = run_git(repo_root, "check-ignore", "-q", "--", f"./{relative}")
    if ignored.returncode == 0:
        return
    if ignored.returncode != 1:
        raise UnignoredSourceError(f"could not verify that {relative} is outside Git's include set")
    raise UnignoredSourceError(
        f"{relative} is an untracked file inside the repository, so the PR workflow would commit it; "
        "move it outside the repository and pass that path instead"
    )
