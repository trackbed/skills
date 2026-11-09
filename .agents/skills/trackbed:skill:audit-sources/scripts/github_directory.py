#!/usr/bin/env python3
"""Fetch the text files of a GitHub directory at one commit as transient source-audit comparison input.

The audit runs this on the `head_url` that `github_changes.py` reports for a `tree` URL. It lists the directory from
the commit's recursive git tree, applies the skip rules the comparison prompt uses for a skill directory plus a symlink
rule, reads each remaining file as a git blob through `gh api`, drops binary blobs, and writes the files in path
order, each under a `==> <path> <==` header, to `--output`. It prints a JSON summary of the included and skipped
paths. The written body is transient; never keep it in the repository or a durable cache.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import re
import sys
from collections.abc import Sequence
from typing import Any

from github_changes import SHA_RE, SourceError, UnsupportedUrl, _list, _object, _string, gh_json, parse_github_url

MAX_FILE_BYTES = 100 * 1024
SOURCE_MANIFEST = "references/sources.yaml"
SYMLINK_MODE = "120000"
LICENSE_NAMES = frozenset({"copying", "licence", "license", "notice", "notices"})
# A bare stem such as `LICENSE` or `notice.txt` matches LICENSE_NAMES in any case. Inside a longer name, only an
# upper-case part such as `EveryInc-LICENSE` or `THIRD_PARTY_NOTICES.md` marks a notice, so guidance such as
# `license-review.md` stays in the comparison.
LICENSE_PART_RE = re.compile(r"(?:^|[-_.])(?:COPYING|LICEN[CS]E|NOTICES?)(?:$|[-_.])")
VENDORED_SEGMENTS = frozenset({"node_modules", "third_party", "vendor", "vendored"})


def skip_reason(relative_path: str, mode: str, size: int) -> str | None:
    """Return why a directory file is left out of the comparison, or None to include it."""
    segments = relative_path.split("/")
    name = segments[-1]
    if relative_path == SOURCE_MANIFEST:
        return "source manifest"
    if name.split(".")[0].lower() in LICENSE_NAMES or LICENSE_PART_RE.search(name):
        return "license or notice"
    if ".min." in name or VENDORED_SEGMENTS.intersection(segments[:-1]):
        return "minified or vendored"
    if mode == SYMLINK_MODE:
        return "symlink"
    if size > MAX_FILE_BYTES:
        return "larger than 100 KB"
    return None


def _blob_text(repository: str, blob_sha: str) -> str | None:
    """Return a blob's UTF-8 text, or None when it is binary."""
    blob = _object(gh_json(f"repos/{repository}/git/blobs/{blob_sha}"), "blob")
    if blob.get("encoding") != "base64":
        raise SourceError("malformed blob response: expected base64 encoding")
    try:
        data = base64.b64decode(_string(blob, "content", "blob"))
    except binascii.Error as error:
        raise SourceError("malformed blob response: invalid base64 content") from error
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def fetch_directory(url: str) -> tuple[str, dict[str, Any]]:
    """Return the directory body and its summary for a tree URL pinned to a full commit SHA."""
    source = parse_github_url(url)
    if source.kind != "tree" or not source.path or source.ref is None or not SHA_RE.fullmatch(source.ref):
        raise UnsupportedUrl("needs a github.com tree URL that names a directory at a full commit SHA")

    prefix = f"{source.path}/"
    tree = _object(gh_json(f"repos/{source.repository}/git/trees/{source.ref}", {"recursive": "1"}), "tree")
    if tree.get("truncated") is True:
        raise SourceError("the git tree is truncated, so the directory listing would be incomplete")

    entries: list[tuple[str, str, str, int]] = []
    for value in _list(tree.get("tree"), "tree"):
        entry = _object(value, "tree entry")
        path = entry.get("path")
        if entry.get("type") != "blob" or not isinstance(path, str) or not path.startswith(prefix):
            continue
        blob_sha, mode, size = entry.get("sha"), entry.get("mode"), entry.get("size")
        if not isinstance(blob_sha, str) or not SHA_RE.fullmatch(blob_sha):
            raise SourceError("malformed tree entry: invalid blob SHA")
        if not isinstance(mode, str) or not isinstance(size, int):
            raise SourceError("malformed tree entry: missing mode or size")
        entries.append((path[len(prefix) :], blob_sha, mode, size))
    if not entries:
        raise SourceError(f"no files under {source.path} at {source.ref}")

    parts: list[str] = []
    files: list[str] = []
    skipped: list[dict[str, str]] = []
    for relative_path, blob_sha, mode, size in sorted(entries):
        reason = skip_reason(relative_path, mode, size)
        text = None
        if reason is None:
            try:
                text = _blob_text(source.repository, blob_sha)
            except SourceError as error:
                raise SourceError(f"{relative_path}: {error}") from error
        if text is None:
            skipped.append({"path": relative_path, "reason": reason or "binary"})
            continue
        if not text.endswith("\n"):
            text += "\n"
        parts.append(f"==> {relative_path} <==\n{text}")
        files.append(relative_path)
    if not files:
        raise SourceError(f"no comparable text files under {source.path} at {source.ref}")

    summary = {
        "file_count": len(files),
        "files": files,
        "skipped": skipped,
    }
    return "\n".join(parts), summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch a GitHub directory's text files at one commit.")
    parser.add_argument("--url", required=True, help="github.com tree URL naming a directory at a full commit SHA.")
    parser.add_argument("--output", required=True, help="File that receives the concatenated directory text.")
    args = parser.parse_args(argv)

    try:
        body, summary = fetch_directory(args.url)
    except UnsupportedUrl as error:
        print(f"github_directory.py: {error}", file=sys.stderr)
        return 2
    except SourceError as error:
        print(f"github_directory.py: {error}", file=sys.stderr)
        return 1

    try:
        with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
    except OSError as error:
        print(f"github_directory.py: could not write {args.output}: {error.strerror}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
