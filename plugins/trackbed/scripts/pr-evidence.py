#!/usr/bin/env python3
"""Stage, validate, and prepare screenshot and video evidence for a Pull Request.

Evidence lives in one run directory below ``<repo>/.trackbed/pr-evidence/``, which
Git's local exclude file hides so no workflow commits it. ``gh pr create --attach``
uploads the files; this helper never uploads anything.

Subcommands:

- ``init`` creates a run directory and an empty manifest.
- ``add`` validates one image or video, copies it into the run directory, and
  records it. ``--spec 'path#alt'`` mirrors the ``gh --attach`` syntax.
- ``show`` prints the revalidated manifest.
- ``prepare`` revalidates every entry against a final PR body and writes the body
  to publish, an evidence-free fallback body, and NUL-delimited ``--attach``
  values.
- ``strip`` removes every evidence reference from a body, for publishing
  without attachments when the manifest cannot be used.

Every subcommand prints one JSON document on success and exits 1 with a
one-line diagnostic on failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
EVIDENCE_DIR = Path(".trackbed") / "pr-evidence"
EXCLUDE_ENTRY = ".trackbed/"
MAX_ATTACHMENTS = 50
IMAGE_LIMIT = 10 * 1024 * 1024
VIDEO_LIMIT = 100 * 1024 * 1024
IMAGE_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mov", ".mp4", ".webm"}
ROLES = ("before", "after", "other")
MAX_ALT_LENGTH = 200
# A path to a run directory or file inside the evidence directory. A mention of the
# directory itself, such as `.trackbed/pr-evidence/` or `.trackbed/pr-evidence/<run-id>/`,
# names no local file and stays in the body.
LEFTOVER_PATH_PATTERN = re.compile(r"\.trackbed/pr-evidence/[\w.-]*\w")
RUN_ID_PATTERN = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")
FILE_NAME_PATTERN = re.compile(r"^[0-9]{2}-(before|after|other)-[a-z0-9-]{1,40}\.[a-z0-9]{3,4}$")
# Markdown image or link targets and HTML src attributes that point into the evidence directory.
REFERENCE_PATTERN = re.compile(
    r"(?P<image>!?)\[(?P<alt>[^\]\n]*)\]\((?P<md>\./\.trackbed/pr-evidence/[^)\s]+)\)"
    r"|<img\b[^>]*?\bsrc=\"(?P<html>\./\.trackbed/pr-evidence/[^\"]+)\"[^>]*>"
)


class EvidenceError(ValueError):
    """Raised when evidence cannot safely become a Pull Request attachment."""


def fail_if_symlink_chain(path: Path, stop: Path) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise EvidenceError(f"{current} must not be a symlink")
        if current == stop or current.parent == current:
            return
        current = current.parent


def resolve_repo_root(value: str) -> Path:
    root = Path(value).expanduser()
    if not root.is_absolute():
        raise EvidenceError("--repo-root must be an absolute path")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise EvidenceError("--repo-root must be a directory")
    return root


def evidence_root(repo_root: Path) -> Path:
    root = repo_root / EVIDENCE_DIR
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
        raise EvidenceError("could not locate Git's local exclude file")
    exclude = Path(result.stdout.strip())
    if not exclude.is_absolute():
        exclude = repo_root / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if EXCLUDE_ENTRY not in existing.splitlines():
        with exclude.open("a", encoding="utf-8") as handle:
            handle.write(("" if existing.endswith("\n") or not existing else "\n") + EXCLUDE_ENTRY + "\n")


def manifest_location(repo_root: Path, manifest_arg: str) -> Path:
    manifest = Path(manifest_arg).expanduser()
    if not manifest.is_absolute():
        raise EvidenceError("--manifest must be an absolute path")
    manifest = Path(os.path.abspath(manifest))
    root = evidence_root(repo_root)
    try:
        relative = manifest.relative_to(root)
    except ValueError as exc:
        raise EvidenceError(f"manifest must be below {root}") from exc
    if len(relative.parts) != 2 or relative.parts[1] != "manifest.json" or not RUN_ID_PATTERN.match(relative.parts[0]):
        raise EvidenceError("manifest must be <run-id>/manifest.json in the evidence directory")
    fail_if_symlink_chain(manifest, repo_root)
    if not manifest.is_file():
        raise EvidenceError("manifest must be a regular file")
    return manifest


def load_manifest(manifest: Path) -> dict[str, Any]:
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"manifest is not readable JSON: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise EvidenceError(f"manifest schema_version must be {SCHEMA_VERSION}")
    if not isinstance(payload.get("entries"), list):
        raise EvidenceError("manifest entries must be an array")
    return payload


def write_manifest(manifest: Path, payload: dict[str, Any]) -> None:
    temporary = manifest.with_name("manifest.json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, manifest)


def clean_alt(value: str) -> str:
    text = " ".join(value.split())
    if not text:
        raise EvidenceError("alt text must not be empty")
    if len(text) > MAX_ALT_LENGTH:
        raise EvidenceError(f"alt text must be at most {MAX_ALT_LENGTH} characters")
    if any(character in text for character in "[]()<>#`|"):
        raise EvidenceError("alt text must not contain [ ] ( ) < > # ` or |")
    return text


def media_kind(path: Path) -> tuple[str, int]:
    extension = path.suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        return "image", IMAGE_LIMIT
    if extension in VIDEO_EXTENSIONS:
        return "video", VIDEO_LIMIT
    supported = ", ".join(sorted(IMAGE_EXTENSIONS | VIDEO_EXTENSIONS))
    raise EvidenceError(f"{path.name} has an unsupported file type; use one of {supported}")


def matches_signature(path: Path) -> bool:
    with path.open("rb") as handle:
        head = handle.read(16)
    extension = path.suffix.lower()
    if extension == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return head.startswith(b"\xff\xd8\xff")
    if extension == ".gif":
        return head[:6] in {b"GIF87a", b"GIF89a"}
    if extension == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if extension in {".mp4", ".mov"}:
        return head[4:8] in {b"ftyp", b"moov", b"wide", b"mdat", b"free"}
    if extension == ".webm":
        return head.startswith(b"\x1a\x45\xdf\xa3")
    return False


def check_media_file(path: Path) -> tuple[str, int]:
    if path.is_symlink() or not path.is_file():
        raise EvidenceError(f"{path} must be a regular file, not a symlink")
    kind, limit = media_kind(path)
    size = path.stat().st_size
    if size == 0:
        raise EvidenceError(f"{path.name} is empty")
    if size > limit:
        raise EvidenceError(f"{path.name} exceeds the {limit // (1024 * 1024)} MB {kind} limit")
    if not matches_signature(path):
        raise EvidenceError(f"{path.name} content does not match its {path.suffix.lower()} extension")
    return kind, size


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_uncommitted_repo_file(repo_root: Path, source: Path) -> None:
    try:
        relative = source.resolve(strict=True).relative_to(repo_root)
    except ValueError:
        return
    if relative.parts[: len(EVIDENCE_DIR.parts)] == EVIDENCE_DIR.parts:
        return
    if run_git(repo_root, "ls-files", "--error-unmatch", "--", str(relative)).returncode == 0:
        return
    if run_git(repo_root, "check-ignore", "-q", "--", str(relative)).returncode == 0:
        return
    raise EvidenceError(
        f"{relative} is an untracked file inside the repository, so the PR workflow would commit it; "
        "move it outside the repository and pass that path instead"
    )


def infer_role(name: str, alt: str) -> str:
    for text in (alt.lower(), name.lower()):
        for role in ("before", "after"):
            if re.match(rf"^{role}\b|^{role}[-_]", text):
                return role
    return "other"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:40].strip("-")) or "evidence"


def reference_for(run_id: str, file_name: str) -> str:
    return f"./{EVIDENCE_DIR.as_posix()}/{run_id}/{file_name}"


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = resolve_repo_root(args.repo_root)
    ensure_excluded(repo_root)
    root = evidence_root(repo_root)
    root.mkdir(parents=True, exist_ok=True)
    fail_if_symlink_chain(root, repo_root)
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + secrets.token_hex(4)
    run_dir = root / run_id
    run_dir.mkdir()
    manifest = run_dir / "manifest.json"
    write_manifest(manifest, {"schema_version": SCHEMA_VERSION, "run_id": run_id, "entries": []})
    return {"dir": str(run_dir), "manifest": str(manifest), "run_id": run_id}


def command_add(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = resolve_repo_root(args.repo_root)
    manifest = manifest_location(repo_root, args.manifest)
    payload = load_manifest(manifest)
    entries: list[dict[str, Any]] = payload["entries"]
    if len(entries) >= MAX_ATTACHMENTS:
        raise EvidenceError(f"gh attaches at most {MAX_ATTACHMENTS} files per Pull Request")

    if args.spec is not None:
        if args.file is not None:
            raise EvidenceError("pass either --spec or --file, not both")
        path_text, separator, alt_text = args.spec.partition("#")
        if not separator:
            alt_text = ""
    else:
        if args.file is None:
            raise EvidenceError("pass --spec or --file")
        path_text, alt_text = args.file, args.alt or ""
    if not path_text or "\n" in path_text or "\x00" in path_text:
        raise EvidenceError("attachment path must be one non-empty line")
    source = Path(path_text).expanduser()
    if not source.is_absolute():
        source = Path.cwd() / source
    source = Path(os.path.abspath(source))
    kind, _size = check_media_file(source)
    if args.source == "user":
        reject_uncommitted_repo_file(repo_root, source)

    alt = clean_alt(alt_text or source.stem.replace("-", " ").replace("_", " "))
    role = args.role if args.role != "auto" else infer_role(source.name, alt)
    run_id = manifest.parent.name
    file_name = f"{len(entries) + 1:02d}-{role}-{slugify(alt)}{source.suffix.lower()}"
    destination = manifest.parent / file_name
    if destination.exists():
        raise EvidenceError(f"{file_name} already exists in the run directory")
    digest = sha256(source)
    if any(entry.get("sha256") == digest for entry in entries):
        raise EvidenceError(f"{source.name} is already staged")
    shutil.copyfile(source, destination)
    if sha256(destination) != digest:
        destination.unlink()
        raise EvidenceError(f"{source.name} changed while it was copied")

    entry = {
        "alt": alt,
        "file": file_name,
        "kind": kind,
        "ref": reference_for(run_id, file_name),
        "role": role,
        "sha256": digest,
        "source": args.source,
    }
    entries.append(entry)
    write_manifest(manifest, payload)
    return entry


def validated_entries(repo_root: Path, manifest: Path) -> list[dict[str, Any]]:
    payload = load_manifest(manifest)
    run_id = manifest.parent.name
    entries: list[dict[str, Any]] = []
    for index, raw in enumerate(payload["entries"]):
        if not isinstance(raw, dict):
            raise EvidenceError(f"entries[{index}] must be an object")
        file_name = raw.get("file")
        if not isinstance(file_name, str) or not FILE_NAME_PATTERN.match(file_name):
            raise EvidenceError(f"entries[{index}].file is not a staged evidence name")
        path = manifest.parent / file_name
        fail_if_symlink_chain(path, repo_root)
        kind, _size = check_media_file(path)
        if raw.get("kind") != kind or raw.get("role") not in ROLES or raw.get("source") not in {"user", "capture"}:
            raise EvidenceError(f"entries[{index}] has an invalid kind, role, or source")
        if raw.get("sha256") != sha256(path):
            raise EvidenceError(f"{file_name} changed after it was staged")
        if raw.get("ref") != reference_for(run_id, file_name):
            raise EvidenceError(f"entries[{index}].ref does not match its file")
        entries.append({**raw, "alt": clean_alt(str(raw.get("alt", "")))})
    if len(entries) > MAX_ATTACHMENTS:
        raise EvidenceError(f"gh attaches at most {MAX_ATTACHMENTS} files per Pull Request")
    return entries


def command_show(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = resolve_repo_root(args.repo_root)
    manifest = manifest_location(repo_root, args.manifest)
    entries = validated_entries(repo_root, manifest)
    return {"dir": str(manifest.parent), "entries": entries, "manifest": str(manifest)}


def drop_leftover_lines(body: str, keep: set[str]) -> tuple[str, int]:
    """Drop any line that still names a path inside the evidence directory outside a kept reference."""
    kept_lines = []
    dropped = 0
    for line in body.splitlines(keepends=True):
        masked = line
        for reference in keep:
            masked = masked.replace(reference, "")
        if LEFTOVER_PATH_PATTERN.search(masked):
            dropped += 1
            continue
        kept_lines.append(line)
    return "".join(kept_lines), dropped


def strip_reference(match: re.Match[str]) -> str:
    alt = match.group("alt")
    if alt is None:
        return ""
    return f"_{alt}_" if alt.strip() else ""


def command_prepare(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = resolve_repo_root(args.repo_root)
    manifest = manifest_location(repo_root, args.manifest)
    entries = validated_entries(repo_root, manifest)
    body_path = Path(args.body_file)
    out_dir = Path(args.out_dir)
    if not out_dir.is_dir() or out_dir.is_symlink():
        raise EvidenceError("--out-dir must be an existing directory")
    body = body_path.read_text(encoding="utf-8")

    attachable = {entry["ref"]: entry for entry in entries}
    referenced: set[str] = set()
    kept_references: set[str] = set()
    unknown: list[str] = []

    def keep_or_strip(match: re.Match[str]) -> str:
        # Keep only the canonical ![alt](ref) form for a staged image; gh rewrites that form.
        target = match.group("md")
        entry = attachable.get(target) if target else None
        if match.group("image") and entry is not None and entry["kind"] == "image":
            referenced.add(target)
            kept_references.add(match.group(0))
            return match.group(0)
        unknown.append(target or match.group("html"))
        return strip_reference(match)

    publish_body, dropped = drop_leftover_lines(REFERENCE_PATTERN.sub(keep_or_strip, body), kept_references)
    fallback_body, _ = drop_leftover_lines(REFERENCE_PATTERN.sub(strip_reference, body), set())

    attach_values = []
    for entry in entries:
        value = entry["ref"]
        if entry["kind"] == "image":
            value = f"{value}#{entry['alt']}"
        attach_values.append(value)

    (out_dir / "body.md").write_text(publish_body, encoding="utf-8")
    (out_dir / "fallback-body.md").write_text(fallback_body, encoding="utf-8")
    (out_dir / "attach.nul").write_bytes(b"".join(value.encode("utf-8") + b"\0" for value in attach_values))
    return {
        "attachments": len(attach_values),
        "body_file": str(out_dir / "body.md"),
        "fallback_body_file": str(out_dir / "fallback-body.md"),
        "attach_file": str(out_dir / "attach.nul"),
        "referenced_in_body": sorted(referenced),
        "appended_by_gh": [entry["ref"] for entry in entries if entry["ref"] not in referenced],
        "stripped_references": unknown,
        "dropped_lines": dropped,
        "roles": {role: sum(1 for entry in entries if entry["role"] == role) for role in ROLES},
    }


def command_strip(args: argparse.Namespace) -> dict[str, Any]:
    body = Path(args.body_file).read_text(encoding="utf-8")
    stripped = REFERENCE_PATTERN.findall(body)
    out_file = Path(args.out_file)
    if out_file.is_symlink():
        raise EvidenceError("--out-file must not be a symlink")
    result, dropped = drop_leftover_lines(REFERENCE_PATTERN.sub(strip_reference, body), set())
    out_file.write_text(result, encoding="utf-8")
    return {"body_file": str(out_file), "dropped_lines": dropped, "stripped_references": len(stripped)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="create a run directory and manifest")
    init.add_argument("--repo-root", required=True)

    add = subparsers.add_parser("add", help="validate, copy, and record one image or video")
    add.add_argument("--repo-root", required=True)
    add.add_argument("--manifest", required=True)
    add.add_argument("--spec", help="'path#alt text', the gh --attach syntax")
    add.add_argument("--file", help="path to the image or video")
    add.add_argument("--alt", help="alt text when using --file")
    add.add_argument("--role", choices=(*ROLES, "auto"), default="auto")
    add.add_argument("--source", choices=("user", "capture"), required=True)

    show = subparsers.add_parser("show", help="print the revalidated manifest")
    show.add_argument("--repo-root", required=True)
    show.add_argument("--manifest", required=True)

    prepare = subparsers.add_parser("prepare", help="write the publish body, fallback body, and attach values")
    prepare.add_argument("--repo-root", required=True)
    prepare.add_argument("--manifest", required=True)
    prepare.add_argument("--body-file", required=True)
    prepare.add_argument("--out-dir", required=True)

    strip = subparsers.add_parser("strip", help="remove every evidence reference from a body")
    strip.add_argument("--body-file", required=True)
    strip.add_argument("--out-file", required=True)
    return parser


COMMANDS = {
    "init": command_init,
    "add": command_add,
    "show": command_show,
    "prepare": command_prepare,
    "strip": command_strip,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = COMMANDS[args.command](args)
    except (EvidenceError, OSError, subprocess.SubprocessError) as exc:
        print(f"pr-evidence {args.command} failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
