#!/usr/bin/env python3
# Adapted from EveryInc compound-engineering-plugin, ce-sessions/scripts/extract-metadata.py.
# Upstream repository: https://github.com/EveryInc/compound-engineering-plugin
# Upstream commit reviewed: 6f9ab03a031c054a8046659926251fb6c149269f
# License: MIT, Copyright (c) 2025 Every.
# Full notice: ../references/EveryInc-LICENSE
# Local changes: a Claude cwd, a longer header window that stops once the
# metadata is complete, path-aware --cwd-filter matching, and a separate count
# for files without recognizable metadata.
#
"""Extract session metadata from Claude Code, Codex, and Cursor JSONL files.

Batch mode (preferred — one invocation for all files):
  python3 extract-metadata.py /path/to/dir/*.jsonl
  python3 extract-metadata.py file1.jsonl file2.jsonl file3.jsonl

Single-file mode (stdin):
  head -20 <session.jsonl> | python3 extract-metadata.py

Auto-detects platform from the JSONL structure.
Outputs one JSON object per file, one per line.
Includes a final _meta line with processing stats.

--cwd-filter VALUE (repeatable) keeps Claude Code and Codex sessions whose
recorded working directory matches any value. An absolute path matches that
directory or one below it, never an ancestor; a bare name must equal one whole
path segment. Sessions without a recorded working directory are dropped while a
filter is set. Cursor records no working directory, so its sessions pass;
discovery already scopes them to the repository's project folders.
"""

from __future__ import annotations

import itertools
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Iterable, Iterator, Optional, Sequence

from session_common import (
    JsonObject,
    TranscriptDiagnostics,
    TranscriptShapeError,
    decode_json_object,
    iter_json_objects,
    object_field,
    object_list_field,
    string_field,
)

Metadata = Dict[str, object]

MAX_LINES = 200  # Resumed Claude sessions can open with long metadata preambles
TAIL_BYTES = 16384  # Read last 16KB to find final timestamp past trailing metadata


def try_claude(
    obj: JsonObject,
    diagnostics: TranscriptDiagnostics,
) -> Optional[Metadata]:
    if obj.get("type") != "user" or "gitBranch" not in obj:
        return None
    try:
        result: Metadata = {
            "platform": "claude",
            "branch": string_field(obj, "gitBranch"),
            "ts": string_field(obj, "timestamp"),
            "session": string_field(obj, "sessionId"),
        }
    except TranscriptShapeError:
        diagnostics.record_parse_error()
        return None
    cwd = obj.get("cwd")
    if isinstance(cwd, str) and cwd:
        result["cwd"] = cwd
    return result


def update_codex(
    obj: JsonObject,
    meta: Metadata,
    diagnostics: TranscriptDiagnostics,
) -> tuple[bool, bool]:
    event_type = obj.get("type")
    if event_type == "session_meta":
        try:
            payload = object_field(obj, "payload")
            session_id = string_field(payload, "id")
            if not session_id:
                raise TranscriptShapeError("session_meta payload has no session id")
            timestamp = string_field(payload, "timestamp") if "timestamp" in payload else string_field(obj, "timestamp")
            candidate: Metadata = {
                "platform": "codex",
                "cwd": string_field(payload, "cwd"),
                "session": session_id,
                "ts": timestamp,
                "cli_version": string_field(payload, "cli_version"),
            }
            source = payload.get("source", "")
            if isinstance(source, str):
                candidate["source"] = source
        except TranscriptShapeError:
            diagnostics.record_parse_error()
            return False, False
        meta.update(candidate)
        return True, False

    if event_type == "turn_context":
        try:
            payload = object_field(obj, "payload")
            model = string_field(payload, "model")
            context_cwd = string_field(payload, "cwd")
            existing_cwd = string_field(meta, "cwd")
        except TranscriptShapeError:
            diagnostics.record_parse_error()
            return False, False
        meta.update(
            {
                "model": model,
                "cwd": existing_cwd or context_cwd,
            }
        )
        return False, True

    return False, False


def try_cursor(
    obj: JsonObject,
) -> Optional[Metadata]:
    if obj.get("role") in ("user", "assistant") and "type" not in obj:
        return {"platform": "cursor"}
    return None


def extract_from_lines(
    lines: Iterable[str],
) -> tuple[Optional[Metadata], TranscriptDiagnostics]:
    diagnostics = TranscriptDiagnostics()
    claude_result: Optional[Metadata] = None
    first_cwd: Optional[str] = None
    codex_meta: Metadata = {}
    found_session_metadata = False
    saw_turn_context = False
    cursor_result: Optional[Metadata] = None

    for obj in iter_json_objects(lines, diagnostics):
        if claude_result is None:
            claude_result = try_claude(obj, diagnostics)
        if first_cwd is None:
            record_cwd = obj.get("cwd")
            if isinstance(record_cwd, str) and record_cwd:
                first_cwd = record_cwd
        found_session, saw_context = update_codex(obj, codex_meta, diagnostics)
        found_session_metadata = found_session_metadata or found_session
        saw_turn_context = saw_turn_context or saw_context
        if cursor_result is None:
            cursor_result = try_cursor(obj)
        # Stop once the metadata is complete, so large records later in the
        # header window cost nothing.
        if claude_result is not None and ("cwd" in claude_result or first_cwd):
            break
        if found_session_metadata and saw_turn_context:
            break
        if cursor_result is not None:
            break

    result: Optional[Metadata]
    if claude_result is not None:
        result = claude_result
        if "cwd" not in result and first_cwd:
            result["cwd"] = first_cwd
    elif found_session_metadata:
        result = codex_meta
    else:
        result = cursor_result

    # A file with no parse errors and no recognizable metadata is reported
    # separately by the caller, apart from parse errors.
    if result is None and saw_turn_context:
        diagnostics.record_parse_error()
    return result, diagnostics


def get_last_timestamp(
    filepath: str,
    size: int,
) -> tuple[Optional[str], TranscriptDiagnostics]:
    """Read the tail of a file to find the last checked timestamp."""
    diagnostics = TranscriptDiagnostics()
    try:
        with open(filepath, "rb") as session_file:
            start = max(0, size - TAIL_BYTES)
            starts_mid_record = False
            if start > 0:
                session_file.seek(start - 1)
                starts_mid_record = session_file.read(1) != b"\n"
            session_file.seek(start)
            tail = session_file.read().decode("utf-8", errors="ignore")
    except (OSError, IOError):
        diagnostics.record_read_error()
        return None, diagnostics

    lines = tail.splitlines()
    if starts_mid_record and lines:
        lines = lines[1:]
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue
        diagnostics.lines += 1
        try:
            obj = decode_json_object(stripped)
            if "timestamp" in obj:
                return string_field(obj, "timestamp"), diagnostics
        except TranscriptShapeError:
            diagnostics.record_parse_error()
    return None, diagnostics


def _iter_user_assistant_text(
    filepath: str,
    diagnostics: TranscriptDiagnostics,
) -> Iterator[str]:
    """Yield only user/assistant text while counting malformed content shapes."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as session_file:
            for line in session_file:
                stripped = line.strip()
                if not stripped:
                    continue
                diagnostics.lines += 1
                try:
                    obj = decode_json_object(stripped)

                    # Claude Code: type-tagged top-level
                    event_type = obj.get("type")
                    if event_type == "user":
                        message = object_field(obj, "message")
                        content = message.get("content")
                        if isinstance(content, str):
                            yield content
                        elif content is not None:
                            for block in object_list_field(message, "content"):
                                if block.get("type") == "text":
                                    yield string_field(block, "text")
                                # Tool results are intentionally excluded.
                        continue
                    if event_type == "assistant":
                        message = object_field(obj, "message")
                        for block in object_list_field(message, "content"):
                            if block.get("type") == "text":
                                yield string_field(block, "text")
                            # Tool use and thinking blocks are intentionally excluded.
                        continue

                    # Codex: payload-typed events
                    if event_type == "event_msg":
                        payload = object_field(obj, "payload")
                        if payload.get("type") == "user_message":
                            codex_message = string_field(payload, "message")
                            parts = codex_message.split("</system_instruction>")
                            yield parts[-1] if parts else codex_message
                        continue
                    if event_type == "response_item":
                        payload = object_field(obj, "payload")
                        if payload.get("type") == "message" and payload.get("role") == "assistant":
                            for block in object_list_field(payload, "content"):
                                if block.get("type") == "output_text":
                                    yield string_field(block, "text")
                        continue

                    # Cursor: role-tagged with no top-level type
                    if obj.get("role") in ("user", "assistant") and "type" not in obj:
                        message = object_field(obj, "message")
                        for block in object_list_field(message, "content"):
                            if block.get("type") == "text":
                                yield string_field(block, "text")
                except TranscriptShapeError:
                    diagnostics.record_parse_error()
    except (OSError, IOError):
        diagnostics.record_read_error()


class KeywordCounter:
    """Count non-overlapping matches without retaining the complete transcript."""

    _MARKERS = ("\0", "\x01", "\x02", "\x03", "\ufffe", "\uffff")

    def __init__(self, keyword: str) -> None:
        self.keyword = keyword
        self.remainder = ""
        self.count = 0

    def feed(self, text: str) -> None:
        combined = self.remainder + text
        marker = next(
            (candidate for candidate in self._MARKERS if candidate not in combined),
            None,
        )
        if marker is None:
            self._feed_without_marker(combined)
            return

        collapsed = combined.replace(self.keyword, marker)
        self.count += collapsed.count(marker)
        unmatched_tail = collapsed[collapsed.rfind(marker) + 1 :]
        self.remainder = unmatched_tail[-len(self.keyword) + 1 :] if len(self.keyword) > 1 else ""

    def _feed_without_marker(self, combined: str) -> None:
        """Fall back when unusually broad text contains every reserved marker."""
        search_from = 0
        while True:
            match_at = combined.find(self.keyword, search_from)
            if match_at < 0:
                break
            self.count += 1
            search_from = match_at + len(self.keyword)

        suffix_start = max(search_from, len(combined) - len(self.keyword) + 1)
        self.remainder = combined[suffix_start:]


def count_keyword_matches(
    filepath: str,
    keywords: Sequence[str],
) -> tuple[dict[str, int], TranscriptDiagnostics]:
    """Count keywords in checked user/assistant text and return diagnostics."""
    counters = {keyword: KeywordCounter(keyword.lower()) for keyword in keywords}
    diagnostics = TranscriptDiagnostics()
    first_chunk = True
    for chunk in _iter_user_assistant_text(filepath, diagnostics):
        if not first_chunk:
            for counter in counters.values():
                counter.feed("\n")
        lowered_chunk = chunk.lower()
        for counter in counters.values():
            counter.feed(lowered_chunk)
        first_chunk = False
    return (
        {keyword: counter.count for keyword, counter in counters.items()},
        diagnostics,
    )


def normalize_cwd(value: str) -> str:
    """Use forward slashes and drop trailing separators."""
    path = value.replace("\\", "/")
    while len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path


def is_absolute_cwd(value: str) -> bool:
    return value.startswith("/") or (len(value) > 2 and value[1] == ":" and value[2] == "/")


def expand_cwd_filters(raw_filters: Sequence[str]) -> list[str]:
    """Normalize filters, adding the symlink-resolved form of absolute paths."""
    expanded: list[str] = []
    for raw in raw_filters:
        forms = [raw]
        if os.path.isabs(raw):
            forms.append(os.path.realpath(raw))
        for form in forms:
            normalized = normalize_cwd(form)
            if normalized and normalized not in expanded:
                expanded.append(normalized)
    return expanded


def cwd_matches_filter(cwd: str, cwd_filters: Sequence[str]) -> bool:
    """Match a recorded working directory against normalized --cwd-filter values."""
    paths = {normalize_cwd(cwd)}
    if os.path.isabs(cwd):
        paths.add(normalize_cwd(os.path.realpath(cwd)))
    for path in paths:
        segments = [segment for segment in path.split("/") if segment]
        for wanted in cwd_filters:
            if is_absolute_cwd(wanted):
                if path == wanted or path.startswith(wanted.rstrip("/") + "/"):
                    return True
            elif wanted in segments:
                return True
    return False


def session_in_scope(result: Metadata, cwd_filters: Sequence[str]) -> bool:
    if result.get("platform") == "cursor":
        return True
    cwd = result.get("cwd")
    return isinstance(cwd, str) and bool(cwd) and cwd_matches_filter(cwd, cwd_filters)


def process_file(
    filepath: str,
    cwd_filters: Sequence[str] = (),
) -> tuple[Optional[Metadata], TranscriptDiagnostics, str]:
    """Extract checked metadata and diagnostics for one file.

    The status is "kept", "filtered" (outside the cwd filters), "missing" (no
    recognizable metadata and no parse errors), or "error". The tail is read
    only for kept sessions.
    """
    diagnostics = TranscriptDiagnostics()
    try:
        size = os.path.getsize(filepath)
        with open(filepath, "r", encoding="utf-8", errors="replace") as session_file:
            result, header_diagnostics = extract_from_lines(itertools.islice(session_file, MAX_LINES))
    except (OSError, IOError):
        diagnostics.record_read_error()
        return None, diagnostics, "error"

    diagnostics.add(header_diagnostics)
    if result is None:
        return None, diagnostics, ("missing" if header_diagnostics.partial_errors == 0 else "error")
    if cwd_filters and not session_in_scope(result, cwd_filters):
        return result, diagnostics, "filtered"

    result["file"] = filepath
    result["size"] = size
    if result["platform"] == "cursor":
        try:
            mtime = os.path.getmtime(filepath)
        except (OSError, IOError):
            diagnostics.record_read_error()
            return None, diagnostics, "error"
        result["ts"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        result["session"] = os.path.basename(os.path.dirname(filepath))
    else:
        last_ts, tail_diagnostics = get_last_timestamp(filepath, size)
        diagnostics.add(tail_diagnostics)
        if last_ts:
            result["last_ts"] = last_ts
    return result, diagnostics, "kept"


# Parse arguments: files and optional --cwd-filter / --keyword
files: list[str] = []
raw_cwd_filters: list[str] = []
keywords: Optional[list[str]] = None
args = sys.argv[1:]
i = 0
while i < len(args):
    if args[i] == "--cwd-filter" and i + 1 < len(args):
        if args[i + 1]:
            raw_cwd_filters.append(args[i + 1])
        i += 2
    elif args[i] == "--keyword" and i + 1 < len(args):
        keywords = [keyword for keyword in args[i + 1].split(",") if keyword]
        i += 2
    elif not args[i].startswith("-"):
        files.append(args[i])
        i += 1
    else:
        i += 1

cwd_filters = expand_cwd_filters(raw_cwd_filters)

if files:
    # Batch mode: isolate every file so later valid sessions always survive.
    processed = 0
    parse_errors = 0
    read_errors = 0
    filtered = 0
    matched = 0
    without_metadata = 0
    for filepath in files:
        if not filepath.endswith(".jsonl"):
            continue
        result, diagnostics, status = process_file(filepath, cwd_filters)
        processed += 1
        if status == "filtered":
            filtered += 1
        elif status == "missing":
            without_metadata += 1
        should_print = status == "kept" and result is not None
        if should_print and result is not None:
            if keywords:
                matches, keyword_diagnostics = count_keyword_matches(
                    filepath,
                    keywords,
                )
                diagnostics.add(keyword_diagnostics)
                result["keyword_matches"] = matches
                match_count = sum(matches.values())
                result["match_count"] = match_count
                if match_count == 0:
                    should_print = False
                else:
                    matched += 1
            if should_print:
                print(json.dumps(result))

        parse_errors += diagnostics.partial_errors
        read_errors += diagnostics.read_errors

    meta: dict[str, object] = {
        "_meta": True,
        "files_processed": processed,
        "parse_errors": parse_errors,
    }
    if read_errors:
        meta["read_errors"] = read_errors
    if without_metadata:
        meta["files_without_metadata"] = without_metadata
    if filtered:
        meta["filtered_by_cwd"] = filtered
    if keywords:
        meta["files_matched"] = matched
    print(json.dumps(meta))
else:
    # No file arguments: either single-file stdin mode or empty xargs invocation.
    if sys.stdin.isatty():
        first_line = None
        lines: Iterator[str] = iter(())
    else:
        lines = itertools.islice(sys.stdin, MAX_LINES)
        first_line = next(lines, None)

    if first_line is None:
        meta = {"_meta": True, "files_processed": 0, "parse_errors": 0}
        if keywords:
            meta["files_matched"] = 0
        print(json.dumps(meta))
    else:
        result, diagnostics = extract_from_lines(itertools.chain((first_line,), lines))
        if result:
            print(json.dumps(result))
        meta = {
            "_meta": True,
            "files_processed": 1,
            "parse_errors": diagnostics.partial_errors,
        }
        if result is None and diagnostics.partial_errors == 0:
            meta["files_without_metadata"] = 1
        if diagnostics.read_errors:
            meta["read_errors"] = diagnostics.read_errors
        print(json.dumps(meta))
