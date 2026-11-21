#!/usr/bin/env python3
# Decision: trackbed/docs/decisions/2026-09-28-pr-risk-triage.md
"""Deterministic risk signals for trackbed:pr:triage-risk.

Classify the paths changed between a merge base and a head commit, scan added
lines for high-signal patterns, apply the optional risk policy read from a
trusted revision, and print one JSON report. The report names paths, line
numbers, and counts only; it never reproduces file content.

Usage: risk-signals.py --merge-base REV [--head REV] [--policy-rev REV]
Exit codes: 0 success, 1 git or input failure, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any

import risk_patterns as patterns
from risk_classification import (
    POLICY_LIST_KEYS as POLICY_LIST_KEYS,
)
from risk_classification import (
    POLICY_PATH,
    Policy,
    TriageError,
    classify_kind,
    code_path_signals,
    git,
    is_manifest,
    is_source_path,
    load_policy,
    matches_any,
)

SCHEMA = "trackbed-pr-triage-risk-signals/v1"
MAX_EVIDENCE = 20
LEVELS = ("low", "medium", "high")

# id -> (level, discountable). references/signals.md documents every id.
SIGNALS: dict[str, tuple[str, bool]] = {
    "content:secret": ("high", False),
    "policy:changed": ("high", False),
    "policy:invalid": ("high", False),
    "policy:high-path": ("high", False),
    "policy:medium-path": ("medium", False),
    "path:auth": ("high", True),
    "path:secrets-config": ("high", True),
    "path:database": ("high", True),
    "path:ci": ("high", True),
    "path:infra": ("high", True),
    "shape:very-large": ("high", True),
    "path:dependencies": ("medium", True),
    "path:api-contract": ("medium", True),
    "path:public-interface": ("medium", True),
    "shape:large": ("medium", True),
    "shape:non-trivial": ("medium", True),
    "shape:deleted-source": ("medium", True),
    "shape:deleted-test": ("medium", True),
    "shape:untested-source": ("medium", True),
    "content:disabled-test": ("medium", True),
    "content:dangerous-sink": ("medium", True),
}

# Size thresholds over code-kind files and their added + deleted lines; binary non-source files are excluded.
VERY_LARGE_LINES = 1000
LARGE_LINES = 400
LARGE_FILES = 25
NON_TRIVIAL_LINES = 100
NON_TRIVIAL_FILES = 10
# Changed lines in non-deleted source files before a branch without test changes is flagged.
UNTESTED_SOURCE_LINES = 20

# --text and --ignore-submodules=none stop branch .gitattributes, .gitmodules, or NUL bytes from hiding changes.
DIFF_OPTIONS = tuple(
    "--no-color --no-ext-diff --no-textconv --no-relative --find-renames --submodule=short --ignore-submodules=none "
    "--text".split()
)

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
SECTION_START_RE = re.compile(r"^(?=diff --git )", re.MULTILINE)


@dataclass
class FileChange:
    path: str
    old_path: str | None
    status: str
    submodule: bool
    kind: str = "code"
    added: int = 0
    deleted: int = 0
    binary: bool = False

    @property
    def paths(self) -> tuple[str, ...]:
        return (self.path,) if self.old_path is None else (self.old_path, self.path)

    @property
    def is_source(self) -> bool:
        return self.kind == "code" and is_source_path(self.path)


class Signals:
    def __init__(self) -> None:
        self._evidence: dict[str, dict[str, None]] = {signal_id: {} for signal_id in SIGNALS}

    def add(self, signal_id: str, evidence: str) -> None:
        self._evidence[signal_id][evidence] = None

    def to_json(self) -> list[dict[str, Any]]:
        return [
            {
                "id": signal_id,
                "level": level,
                "discountable": discountable,
                "count": len(found),
                "evidence": list(found)[:MAX_EVIDENCE],
            }
            for signal_id, (level, discountable) in SIGNALS.items()
            if (found := self._evidence[signal_id])
        ]


def resolve_commit(root: str, rev: str) -> str:
    try:
        return git(root, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{rev}^{{commit}}").decode().strip()
    except TriageError as error:
        raise TriageError(f"cannot resolve {rev!r} to a commit") from error


def parse_raw(data: bytes) -> list[FileChange]:
    fields = data.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    changes: list[FileChange] = []
    index = 0
    try:
        while index < len(fields):
            meta = fields[index].decode("utf-8", "replace")
            parts = meta[1:].split(" ")
            if not meta.startswith(":") or len(parts) != 5:
                raise TriageError(f"unexpected raw diff entry {meta!r}")
            old_mode, new_mode, _, _, status = parts
            letter = status[:1]
            if letter in ("R", "C"):
                old_path: str | None = fields[index + 1].decode("utf-8", "replace")
                path = fields[index + 2].decode("utf-8", "replace")
                index += 3
            else:
                old_path = None
                path = fields[index + 1].decode("utf-8", "replace")
                index += 2
            submodule = "160000" in (old_mode, new_mode)
            changes.append(FileChange(path=path, old_path=old_path, status=letter, submodule=submodule))
    except IndexError as error:
        raise TriageError("raw diff output ended mid-entry") from error
    return changes


def scan_line(change: FileChange, line_no: int, text: str, signals: Signals, scan_sinks: bool) -> None:
    location = f"{change.path}:{line_no}"
    for name, pattern in patterns.SECRET_PATTERNS:
        if pattern.search(text):
            signals.add("content:secret", f"{location} ({name})")
    if scan_sinks:
        for name, pattern in patterns.SINK_PATTERNS:
            if pattern.search(text):
                signals.add("content:dangerous-sink", f"{location} ({name})")
    if change.kind == "test":
        for name, pattern in patterns.DISABLED_TEST_PATTERNS:
            if pattern.search(text):
                signals.add("content:disabled-test", f"{location} ({name})")


def apply_patch(changes: list[FileChange], patch: str, signals: Signals) -> None:
    preamble, *sections = SECTION_START_RE.split(patch)
    if preamble:
        raise TriageError("patch output did not start with a file header")
    # A type change (for example file to symlink) prints as a deletion section plus an addition section.
    owners = [change for change in changes for _ in range(2 if change.status == "T" else 1)]
    if len(owners) != len(sections):
        raise TriageError(f"patch has {len(sections)} file sections but the raw diff has {len(owners)}")
    for change, section in zip(owners, sections):  # noqa: B905 - lengths checked above; strict= needs Python 3.10
        scan_sinks = change.kind == "code"
        new_line: int | None = None  # None until the first hunk header
        for line in section.split("\n"):
            if line.startswith("@@"):
                match = HUNK_RE.match(line)
                if not match:
                    raise TriageError(f"unexpected hunk header {line!r}")
                new_line = int(match.group(1))
            elif new_line is None:
                continue
            elif line.startswith(("+", "-")):
                change.binary = change.binary or "\0" in line
                if line.startswith("-"):
                    change.deleted += 1
                    continue
                change.added += 1
                if not change.submodule:
                    scan_line(change, new_line, line[1:], signals, scan_sinks)
                new_line += 1
            elif line.startswith(" "):
                new_line += 1
    # --text renders binaries as pseudo-lines, so zero binary non-source files; a source file keeps its counts, so a
    # planted NUL byte cannot shrink the size signals.
    for change in changes:
        if change.binary and not change.is_source:
            change.added = change.deleted = 0


def apply_path_signals(changes: list[FileChange], policy: Policy, signals: Signals) -> None:
    if policy.status == "invalid":
        signals.add("policy:invalid", POLICY_PATH)
    for change in changes:
        for path in change.paths:
            if path == POLICY_PATH:
                signals.add("policy:changed", path)
            if matches_any(path, policy.high):
                signals.add("policy:high-path", path)
            if matches_any(path, policy.medium):
                signals.add("policy:medium-path", path)
            name = PurePosixPath(path).name
            if change.submodule or name in patterns.LOCKFILES or is_manifest(name) or path == ".gitmodules":
                signals.add("path:dependencies", path)
            # Classify each side of a rename, so moving code into a test or docs path keeps the old path's categories.
            if classify_kind(path, policy) == "code":
                for signal_id in code_path_signals(path):
                    signals.add(signal_id, path)


def apply_shape_signals(changes: list[FileChange], signals: Signals) -> dict[str, Any]:
    code = [change for change in changes if change.kind == "code" and (change.is_source or not change.binary)]
    code_lines = sum(change.added + change.deleted for change in code)
    size_evidence = f"{code_lines} code lines in {len(code)} code files"
    if code_lines > VERY_LARGE_LINES:
        signals.add("shape:very-large", size_evidence)
    elif code_lines > LARGE_LINES or len(code) > LARGE_FILES:
        signals.add("shape:large", size_evidence)
    elif code_lines > NON_TRIVIAL_LINES or len(code) > NON_TRIVIAL_FILES:
        signals.add("shape:non-trivial", size_evidence)

    for change in changes:
        if change.status != "D":
            continue
        if change.is_source:
            signals.add("shape:deleted-source", change.path)
        elif change.kind == "test":
            signals.add("shape:deleted-test", change.path)
    sources = [change for change in changes if change.is_source and change.status != "D"]
    source_lines = sum(change.added + change.deleted for change in sources)
    touches_tests = any(change.kind == "test" and change.status != "D" for change in changes)
    if source_lines > UNTESTED_SOURCE_LINES and not touches_tests:
        for change in sources:
            signals.add("shape:untested-source", change.path)

    kinds = Counter(change.kind for change in changes)
    return {
        "files": len(changes),
        "added": sum(change.added for change in changes),
        "deleted": sum(change.deleted for change in changes),
        "code_files": len(code),
        "code_lines": code_lines,
        "kinds": dict(sorted(kinds.items())),
    }


def file_record(change: FileChange) -> dict[str, Any]:
    # Unset markers are omitted so a report for a wide branch stays under host tool-output caps.
    record = asdict(change)
    for key in ("old_path", "binary", "submodule"):
        if not record[key]:
            del record[key]
    return record


def highest(levels: list[str]) -> str:
    return max(levels, key=LEVELS.index, default="low")


def build_report(root: str, merge_base: str, head: str, policy_rev: str) -> dict[str, Any]:
    policy = load_policy(root, policy_rev)
    changes = parse_raw(git(root, "diff", "--raw", "-z", "--no-abbrev", *DIFF_OPTIONS, merge_base, head))
    for change in changes:
        change.kind = classify_kind(change.path, policy)
    signals = Signals()
    patch = git(root, "diff", "--patch", "--unified=0", *DIFF_OPTIONS, merge_base, head)
    apply_patch(changes, patch.decode("utf-8", "replace"), signals)
    apply_path_signals(changes, policy, signals)
    totals = apply_shape_signals(changes, signals)
    report_signals = signals.to_json()
    return {
        "schema": SCHEMA,
        "range": {"merge_base": merge_base, "head": head},
        "policy": {"path": POLICY_PATH, "rev": policy.rev, "status": policy.status, "error": policy.error},
        "floor": highest([signal["level"] for signal in report_signals]),
        "hard_floor": highest([signal["level"] for signal in report_signals if not signal["discountable"]]),
        "totals": totals,
        "signals": report_signals,
        "files": [file_record(change) for change in changes],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="risk-signals.py", description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--merge-base", required=True, help="commit the branch diverged from")
    parser.add_argument("--head", default="HEAD", help="commit to triage (default: HEAD)")
    parser.add_argument("--policy-rev", help="trusted revision to read the risk policy from (default: merge base)")
    args = parser.parse_args(argv)
    try:
        root = git(None, "rev-parse", "--show-toplevel").decode().strip()
        merge_base = resolve_commit(root, args.merge_base)
        head = resolve_commit(root, args.head)
        policy_rev = resolve_commit(root, args.policy_rev) if args.policy_rev else merge_base
        report = build_report(root, merge_base, head, policy_rev)
    except TriageError as error:
        print(f"risk-signals: {error}", file=sys.stderr)
        return 1
    json.dump(report, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
