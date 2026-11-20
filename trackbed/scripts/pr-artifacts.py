#!/usr/bin/env python3
"""Stage, validate, and upload text documents as artifacts on a Pull Request.

GitHub shows an artifact beside the Pull Request: a Markdown or plain-text
document, or an HTML page a reader can preview. Documents are staged in one run
directory below ``<repo>/.trackbed/pr-artifacts/``, which Git's local exclude
file hides so no workflow commits it, and uploaded once the Pull Request exists.

Subcommands:

- ``init`` creates a run directory and an empty manifest.
- ``inspect`` returns one workflow document and the digest of those exact bytes.
- ``add`` validates one document, copies it into the run directory, and records
  it. ``--spec 'path#name'`` names the artifact; the file name is the default.
  ``--file`` with ``--name`` takes a path that contains ``#``.
- ``remove`` drops one staged document that was not sent yet.
- ``show`` prints the revalidated manifest.
- ``upload`` creates one artifact per staged document on a Pull Request through
  ``gh api`` and records each result. A second call sends only the documents
  GitHub refused or that were not attempted, never one whose outcome is unconfirmed.

Every subcommand prints one JSON document on success. A failure exits 1 with
a one-line diagnostic, or 3 when Git can include an untracked workflow source.
``upload`` reports a document GitHub refused in that JSON and still exits 0.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS_DIR), str(SCRIPTS_DIR / "lib")]
from pr_staging import (  # noqa: E402
    StagingError,
    UnignoredSourceError,
    fail_if_symlink_chain,
    load_manifest,
    manifest_location,
    open_run,
    reject_uncommitted_repo_file,
    relative_to_directory,
    resolve_repo_root,
    write_manifest,
)
from review_process import noninteractive_environment, run_bounded  # noqa: E402
from risk_patterns import SECRET_PATTERNS  # noqa: E402

SCHEMA_VERSION = 1
ARTIFACT_DIR = Path(".trackbed") / "pr-artifacts"
MAX_ARTIFACTS = 10
MAX_BYTES = 1024 * 1024
MAX_NAME_LENGTH = 100
HTML_EXTENSIONS = {".htm", ".html"}
TEXT_EXTENSIONS = {".markdown", ".md", ".txt"}
SOURCES = ("user", "workflow")
FILE_NAME_PATTERN = re.compile(r"[0-9]{2,}-[a-z0-9-]{1,40}\.(?:htm|html|markdown|md|txt)")
PR_URL_PATTERN = re.compile(
    r"^https://(?P<host>[A-Za-z0-9][A-Za-z0-9.-]*)/(?P<owner>[A-Za-z0-9][A-Za-z0-9_.-]*)"
    r"/(?P<repo>[A-Za-z0-9_.-]+)/pull/(?P<number>[1-9][0-9]*)$"
)
API_VERSION = "2026-03-10"
UPLOAD_TIMEOUT = 60
# A missing API, missing permission, or rate limit answers every document the same way.
STOP_STATUSES = {401, 403, 404, 410, 429}
STATUS_LINE_PATTERN = re.compile(r"^HTTP/\S+ (\d{3})\b")
# Stricter than the shared patterns, because no person previews an automatic upload and a
# false positive only keeps one document off the Pull Request.
EXTRA_SECRET_PATTERNS = (
    ("private-key-block", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY BLOCK-----")),
    ("url-credentials", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@")),
    (
        "authorization-header",
        re.compile(r"(?i)\bauthorization[\"']?\s*[:=]\s*[\"']?(?:bearer|basic|token)\s+[A-Za-z0-9._~+/=-]{8,}"),
    ),
    ("json-web-token", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("token-prefix", re.compile(r"\b(?:glpat-|npm_|lin_api_|xapp-|dop_v1_|hf_)[A-Za-z0-9_-]{16,}")),
    (
        "assigned-secret",
        re.compile(
            r"(?i)(?:password|passwd|secret|token|api[_-]?key|access[_-]?key)[a-z0-9_-]*[\"']?\s*[:=]\s*[\"']?"
            r"(?=[^\s\"']*[0-9])(?=[^\s\"']*[a-z])[^\s\"'<>{}$]{6,}"
        ),
    ),
)


def clean_name(value: str) -> str:
    """Fit GitHub's rule for artifact names.

    A name may contain letters, numbers, accent marks, spaces, ``.``, ``-`` and
    ``_``, and starts and ends with a letter or number.
    """
    kept = "".join(
        character
        for character in " ".join(value.split())
        if character.isalnum() or unicodedata.category(character).startswith("M") or character in " .-_"
    )
    start, end = 0, len(kept)
    while start < end and not kept[start].isalnum():
        start += 1
    while end > start and not kept[end - 1].isalnum():
        end -= 1
    name = " ".join(kept[start:end].split())
    if not name:
        raise StagingError("artifact name needs at least one letter or number")
    if len(name) > MAX_NAME_LENGTH:
        raise StagingError(f"artifact name must be at most {MAX_NAME_LENGTH} characters")
    return name


def read_document(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise StagingError(f"{path} must be a regular file, not a symlink")
    if path.suffix.lower() not in HTML_EXTENSIONS | TEXT_EXTENSIONS:
        supported = ", ".join(sorted(HTML_EXTENSIONS | TEXT_EXTENSIONS))
        raise StagingError(f"{path.name} has an unsupported file type; use one of {supported}")
    with path.open("rb") as document:
        data = document.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise StagingError(f"{path.name} exceeds the {MAX_BYTES // 1024} KB artifact limit")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StagingError(f"{path.name} is not UTF-8 text") from exc
    if "\x00" in text:
        raise StagingError(f"{path.name} is not a text document")
    if not text.strip():
        raise StagingError(f"{path.name} is empty")
    return text


def reject_secrets(text: str, file_name: str) -> None:
    for label, pattern in (*SECRET_PATTERNS, *EXTRA_SECRET_PATTERNS):
        match = pattern.search(text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            raise StagingError(f"{file_name} line {line} looks like a secret ({label}); remove it before uploading")


def document_types(path: Path) -> tuple[str, ...]:
    """Return the artifact types a document may have, default first."""
    return ("embedded_html",) if path.suffix.lower() in HTML_EXTENSIONS else ("generic", "plan")


def artifact_type(path: Path, requested: str) -> str:
    types = document_types(path)
    if requested == "plan" and "plan" not in types:
        raise StagingError("--type plan applies to Markdown and text documents, not HTML pages")
    return "plan" if requested == "plan" else types[0]


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:40].strip("-")) or "artifact"


def source_path(path_text: str) -> Path:
    if not path_text or "\n" in path_text or "\x00" in path_text:
        raise StagingError("artifact path must be one non-empty line")
    return Path(path_text).expanduser().absolute()


def check_source(repo_root: Path, source: Path, *, workflow: bool) -> None:
    reject_uncommitted_repo_file(repo_root, source, tracked_policy="reject" if workflow else "clean")
    if not workflow or source.is_symlink():
        return
    # Every workflow archives its review rounds under .context/<workflow>/reviews/.
    for path in (source, source.resolve()):
        parts = (relative_to_directory(path, repo_root / ".context") or Path()).parts
        if len(parts) > 2 and parts[1].casefold() == "reviews":
            raise StagingError("archived review reports stay local")


def command_inspect(args: argparse.Namespace, repo_root: Path) -> dict[str, str]:
    source = source_path(args.file)
    check_source(repo_root, source, workflow=True)
    text = read_document(source)
    reject_secrets(text, source.name)
    return {"text": text, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def command_add(args: argparse.Namespace, repo_root: Path, manifest: Path) -> dict[str, Any]:
    payload = load_manifest(manifest, SCHEMA_VERSION)
    entries: list[dict[str, Any]] = payload["entries"]
    if len(entries) >= MAX_ARTIFACTS:
        raise StagingError(f"a Pull Request gets at most {MAX_ARTIFACTS} artifacts from one run")

    if args.spec is not None:
        if args.file is not None or args.name is not None:
            raise StagingError("pass either --spec, or --file with an optional --name")
        path_text, _separator, name_text = args.spec.partition("#")
    else:
        if args.file is None:
            raise StagingError("pass --spec or --file")
        path_text, name_text = args.file, args.name or ""
    source = source_path(path_text)
    workflow = args.source == "workflow"
    check_source(repo_root, source, workflow=workflow)
    text = read_document(source)
    kind = artifact_type(source, args.type)
    reject_secrets(text, source.name)
    name = clean_name(name_text or source.name)
    reject_secrets(name, "artifact name")
    if any(entry.get("name") == name for entry in entries):
        raise StagingError(f"an artifact named {name!r} is already staged")
    # Stage the bytes that were just checked, not a second read of a file a workflow may still be writing.
    data = text.encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    if workflow and args.reviewed_sha256 != digest:
        raise StagingError("workflow artifact must match the SHA-256 of the inspected document")
    if any(entry.get("sha256") == digest for entry in entries):
        raise StagingError(f"{source.name} is already staged")
    index = max((int(entry["file"].split("-", 1)[0]) for entry in entries), default=0) + 1
    file_name = f"{index:02d}-{slugify(name)}{source.suffix.lower()}"
    destination = manifest.parent / file_name
    if destination.exists():
        raise StagingError(f"{file_name} already exists in the run directory")
    destination.write_bytes(data)

    entry = {"file": file_name, "name": name, "sha256": digest, "source": args.source, "type": kind}
    if args.public_ok:
        entry["public_ok"] = True
    entries.append(entry)
    try:
        write_manifest(manifest, payload)
    except OSError:
        destination.unlink()
        raise
    return entry


def staged_file(repo_root: Path, manifest: Path, entry: Any, index: int) -> Path:
    if not isinstance(entry, dict):
        raise StagingError(f"entries[{index}] must be an object")
    file_name = entry.get("file")
    if not isinstance(file_name, str) or not FILE_NAME_PATTERN.fullmatch(file_name):
        raise StagingError(f"entries[{index}].file is not a staged artifact name")
    path = manifest.parent / file_name
    fail_if_symlink_chain(path, repo_root)
    return path


def validated_documents(repo_root: Path, manifest: Path) -> tuple[dict[str, Any], list[str]]:
    """Return the manifest and each staged document's text, read once and checked again.

    The caller uploads this text, so nothing reaches GitHub that the credential
    scan did not see, whatever happened to the run directory after staging.
    """
    payload = load_manifest(manifest, SCHEMA_VERSION)
    if len(payload["entries"]) > MAX_ARTIFACTS:
        raise StagingError(f"a Pull Request gets at most {MAX_ARTIFACTS} artifacts from one run")
    texts: list[str] = []
    for index, entry in enumerate(payload["entries"]):
        path = staged_file(repo_root, manifest, entry, index)
        text = read_document(path)
        name = entry.get("name")
        if not isinstance(name, str) or clean_name(name) != name:
            raise StagingError(f"entries[{index}].name is not a valid artifact name")
        reject_secrets(name, "artifact name")
        if entry.get("type") not in document_types(path) or entry.get("source") not in SOURCES:
            raise StagingError(f"entries[{index}] has an invalid type or source")
        if entry.get("sha256") != hashlib.sha256(text.encode("utf-8")).hexdigest():
            raise StagingError(f"{path.name} changed after it was staged")
        reject_secrets(text, path.name)
        texts.append(text)
    return payload, texts


def command_remove(args: argparse.Namespace, repo_root: Path, manifest: Path) -> dict[str, Any]:
    payload = load_manifest(manifest, SCHEMA_VERSION)
    entries: list[Any] = payload["entries"]
    matches = [
        index for index, entry in enumerate(entries) if isinstance(entry, dict) and entry.get("name") == args.name
    ]
    if not matches:
        raise StagingError(f"no staged artifact is named {args.name!r}")
    index = matches[0]
    if entries[index].get("uploaded") or entries[index].get("unconfirmed"):
        raise StagingError(f"{args.name!r} was already sent to the Pull Request")
    path = staged_file(repo_root, manifest, entries[index], index)
    del entries[index]
    write_manifest(manifest, payload)
    result = {"remaining": len(entries), "removed": args.name}
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        result["cleanup_warning"] = f"could not remove staged copy {path.name}: {exc.strerror}"
    return result


def command_show(args: argparse.Namespace, repo_root: Path, manifest: Path) -> dict[str, Any]:
    for spec in args.check_source:
        source = source_path(spec.partition("#")[0])
        try:
            source.lstat()
        except (FileNotFoundError, NotADirectoryError):
            # A removed original cannot be committed, and its staged copy is independent.
            continue
        check_source(repo_root, source, workflow=False)
    entries = validated_documents(repo_root, manifest)[0]["entries"]
    return {"dir": str(manifest.parent), "entries": entries, "manifest": str(manifest)}


def create_artifact(target: dict[str, str], entry: dict[str, Any], body: str) -> tuple[int | None, dict[str, Any], str]:
    """POST one artifact and return the HTTP status, the decoded response, and a diagnostic.

    A timeout raises ``subprocess.TimeoutExpired``: the request may still have arrived.
    """
    request = json.dumps({"type": entry["type"], "name": entry["name"], "body": body})
    result = run_bounded(
        [
            "gh",
            "api",
            "--hostname",
            target["host"],
            "--include",
            "--method",
            "POST",
            "-H",
            "Accept: application/vnd.github+json",
            "-H",
            f"X-GitHub-Api-Version: {API_VERSION}",
            f"repos/{target['owner']}/{target['repo']}/issues/{target['number']}/artifacts",
            "--input",
            "-",
        ],
        timeout=UPLOAD_TIMEOUT,
        input=request,
        text=True,
        env={**noninteractive_environment(), "NO_COLOR": "1", "CLICOLOR_FORCE": "0"},
    )
    head, _separator, raw_body = result.stdout.replace("\r\n", "\n").partition("\n\n")
    match = STATUS_LINE_PATTERN.match(head)
    status = int(match.group(1)) if match else None
    try:
        response = json.loads(raw_body) if raw_body.strip() else {}
    except json.JSONDecodeError:
        response = {}
    if not isinstance(response, dict):
        response = {}
    detail = response.get("message") or (result.stderr.strip().splitlines() or ["gh api failed"])[0]
    return status, response, f"HTTP {status}: {detail}"[:300] if status else str(detail)[:300]


def allows_private_artifacts(target: dict[str, str]) -> bool:
    repository = f"{target['host']}/{target['owner']}/{target['repo']}"
    try:
        result = run_bounded(
            ["gh", "repo", "view", repository, "--json", "visibility", "--jq", ".visibility"],
            timeout=UPLOAD_TIMEOUT,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() in ("PRIVATE", "INTERNAL")


def command_upload(args: argparse.Namespace, repo_root: Path, manifest: Path) -> dict[str, Any]:
    match = PR_URL_PATTERN.fullmatch(args.pr_url)
    if match is None or match["repo"] in (".", ".."):
        raise StagingError("--pr-url must be https://<host>/<owner>/<repo>/pull/<number>")
    target = match.groupdict()
    payload, texts = validated_documents(repo_root, manifest)
    if payload.get("pull_request") not in (None, args.pr_url):
        raise StagingError(f"this run already belongs to {payload['pull_request']}")
    # Bind the run to its Pull Request before the first request, so no later call can send it elsewhere.
    payload["pull_request"] = args.pr_url
    write_manifest(manifest, payload)

    uploaded: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    not_attempted: list[str] = []
    skipped_visibility: list[str] = []
    unconfirmed: list[str] = []
    already_uploaded = 0
    stopped: str | None = None
    private_allowed: bool | None = None
    for entry, body in zip(payload["entries"], texts, strict=True):
        if entry.get("uploaded"):
            already_uploaded += 1
            continue
        if entry.get("unconfirmed"):
            unconfirmed.append(entry["name"])
            continue
        if entry["source"] == "workflow" and entry.get("public_ok") is not True:
            if private_allowed is None:
                private_allowed = allows_private_artifacts(target)
            if not private_allowed:
                skipped_visibility.append(entry["name"])
                continue
        if stopped is not None:
            not_attempted.append(entry["name"])
            continue
        # Preserve the attempt even if the helper dies before it can record the response.
        entry["unconfirmed"] = True
        write_manifest(manifest, payload)
        try:
            status, response, diagnostic = create_artifact(target, entry, body)
        except FileNotFoundError as exc:
            del entry["unconfirmed"]
            write_manifest(manifest, payload)
            stopped = f"could not start gh: {exc.strerror or exc}"
            failed.append({"name": entry["name"], "error": stopped})
            continue
        except subprocess.TimeoutExpired:
            status, response, diagnostic = None, {}, "gh api timed out"
        if status is None or status < 200 or status >= 500:
            unconfirmed.append(entry["name"])
            stopped = diagnostic
            continue
        del entry["unconfirmed"]
        if status < 300:
            number = response.get("number")
            entry["uploaded"] = {
                "number": number if isinstance(number, int) else None,
                "url": str(response.get("html_url") or ""),
            }
            write_manifest(manifest, payload)
            uploaded.append({"name": entry["name"], **entry["uploaded"]})
            continue
        write_manifest(manifest, payload)
        failed.append({"name": entry["name"], "error": diagnostic})
        if status in STOP_STATUSES:
            stopped = diagnostic
    return {
        "already_uploaded": already_uploaded,
        "dir": str(manifest.parent),
        "failed": failed,
        "not_attempted": not_attempted,
        "pull_request": args.pr_url,
        "skipped_visibility": skipped_visibility,
        "stopped": stopped,
        "unconfirmed": unconfirmed,
        "uploaded": uploaded,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="create a run directory and manifest")
    init.add_argument("--repo-root", required=True)

    inspect = subparsers.add_parser("inspect", help="read one eligible workflow document and its SHA-256")
    inspect.add_argument("--repo-root", required=True)
    inspect.add_argument("--file", required=True)

    add = subparsers.add_parser("add", help="validate, copy, and record one document")
    add.add_argument("--repo-root", required=True)
    add.add_argument("--manifest", required=True)
    add.add_argument("--spec", help="'path#artifact name'; the file name is the default name")
    add.add_argument("--file", help="path to the document, for a path that contains #")
    add.add_argument("--name", help="artifact name when using --file")
    add.add_argument("--source", choices=SOURCES, required=True)
    add.add_argument("--reviewed-sha256", help="the digest returned by inspect for the workflow document reviewed")
    add.add_argument("--type", choices=("auto", "plan"), default="auto")
    add.add_argument("--public-ok", action="store_true", help="this workflow document passed the public PR checks")

    remove = subparsers.add_parser("remove", help="drop one staged document that was not sent yet")
    remove.add_argument("--repo-root", required=True)
    remove.add_argument("--manifest", required=True)
    remove.add_argument("--name", required=True)

    show = subparsers.add_parser("show", help="print the revalidated manifest")
    show.add_argument("--repo-root", required=True)
    show.add_argument("--manifest", required=True)
    show.add_argument(
        "--check-source",
        action="append",
        default=[],
        metavar="SPEC",
        help="recheck an explicit artifact's original path before committing",
    )

    upload = subparsers.add_parser("upload", help="create one artifact per staged document on a Pull Request")
    upload.add_argument("--repo-root", required=True)
    upload.add_argument("--manifest", required=True)
    upload.add_argument("--pr-url", required=True)
    return parser


COMMANDS = {
    "add": command_add,
    "remove": command_remove,
    "show": command_show,
    "upload": command_upload,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo_root = resolve_repo_root(args.repo_root)
        if args.command == "init":
            result = open_run(repo_root, ARTIFACT_DIR, SCHEMA_VERSION)
        elif args.command == "inspect":
            result = command_inspect(args, repo_root)
        else:
            manifest = manifest_location(repo_root, ARTIFACT_DIR, args.manifest)
            run_fd = os.open(manifest.parent, os.O_RDONLY)
            try:
                try:
                    fcntl.flock(run_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise StagingError("another command is using this artifact run") from exc
                result = COMMANDS[args.command](args, repo_root, manifest)
            finally:
                os.close(run_fd)
    except (StagingError, OSError, subprocess.SubprocessError) as exc:
        print(f"pr-artifacts {args.command} failed: {exc}", file=sys.stderr)
        if isinstance(exc, UnignoredSourceError) and (
            args.command == "inspect" or (args.command == "add" and args.source == "workflow")
        ):
            return 3
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
