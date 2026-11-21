# Adapted from EveryInc compound-engineering-plugin, ce-sessions scripts.
# Upstream repository: https://github.com/EveryInc/compound-engineering-plugin
# Upstream commit reviewed: 6f9ab03a031c054a8046659926251fb6c149269f
# License: MIT, Copyright (c) 2025 Every.
# Full notice: EveryInc-LICENSE. Exact upstream paths: sources.yaml.
#
"""Read local agent transcripts and identify shell command segments."""

from __future__ import annotations

import json
import os
import re
import shlex
import stat
import sys
import time
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Dict, Literal, NamedTuple, cast  # noqa: UP035 - Python 3.8 runtime alias

JsonObject = Dict[str, object]  # noqa: UP006 - evaluated at runtime on Python 3.8
DiscoveryPlatform = Literal["claude", "codex"]
Platform = Literal[DiscoveryPlatform, "cursor"]


class TranscriptShapeError(ValueError):
    """A decoded transcript value does not match a supported checked shape."""


class TranscriptDiagnostics:
    """Count failed parse and read attempts across extraction passes."""

    def __init__(self) -> None:
        self.lines = 0
        self.parse_errors = 0
        self.read_errors = 0

    def add(self, other: TranscriptDiagnostics) -> None:
        self.lines += other.lines
        self.parse_errors += other.parse_errors
        self.read_errors += other.read_errors

    def record_parse_error(self) -> None:
        self.parse_errors += 1

    def record_read_error(self) -> None:
        self.read_errors += 1

    @property
    def partial_errors(self) -> int:
        """All failures that make extraction coverage incomplete."""
        return self.parse_errors + self.read_errors


def decode_json_object(line: str) -> JsonObject:
    """Decode one JSONL line and require a top-level object."""
    try:
        value: object = json.loads(line)
    except ValueError as error:
        raise TranscriptShapeError("invalid JSON") from error
    if not isinstance(value, dict):
        raise TranscriptShapeError("top-level JSON value is not an object")
    return cast(JsonObject, value)


def iter_json_objects(
    lines: Iterable[str],
    diagnostics: TranscriptDiagnostics,
) -> Iterator[JsonObject]:
    """Yield checked JSON objects while counting malformed non-empty lines."""
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        diagnostics.lines += 1
        try:
            yield decode_json_object(line)
        except TranscriptShapeError:
            diagnostics.record_parse_error()


def detect_platform(obj: JsonObject) -> Platform | None:
    """Detect a supported transcript platform from one checked event object."""
    event_type = obj.get("type")
    if event_type in ("user", "assistant"):
        return "claude"
    if event_type in ("session_meta", "turn_context", "response_item", "event_msg"):
        return "codex"
    if obj.get("role") in ("user", "assistant") and "type" not in obj:
        return "cursor"
    return None


def iter_events(
    lines: Iterable[str],
    diagnostics: TranscriptDiagnostics,
    platform: Platform | None = None,
) -> Iterator[tuple[Platform, JsonObject]]:
    """Yield JSONL events for a known platform or detect it from the first recognizable event."""
    for event in iter_json_objects(lines, diagnostics):
        if platform is None:
            platform = detect_platform(event)
            if platform is None:
                continue
        yield platform, event


def object_value(value: object, field: str) -> JsonObject:
    """Require a mapping value."""
    if not isinstance(value, dict):
        raise TranscriptShapeError(f"{field} is not an object")
    return cast(JsonObject, value)


def object_field(obj: JsonObject, key: str) -> JsonObject:
    """Read an optional object field, rejecting a present wrong-shaped value."""
    if key not in obj:
        return {}
    return object_value(obj[key], key)


def object_list_value(value: object, field: str) -> list[JsonObject]:
    """Require a list whose elements are all mappings."""
    if not isinstance(value, list):
        raise TranscriptShapeError(f"{field} is not a list")
    return [object_value(item, f"{field}[]") for item in value]


def object_list_field(obj: JsonObject, key: str) -> list[JsonObject]:
    """Read an optional list-of-objects field."""
    if key not in obj:
        return []
    return object_list_value(obj[key], key)


def string_value(value: object, field: str) -> str:
    """Require a string value."""
    if not isinstance(value, str):
        raise TranscriptShapeError(f"{field} is not a string")
    return value


def string_field(obj: JsonObject, key: str, default: str = "") -> str:
    """Read an optional checked string field."""
    if key not in obj:
        return default
    return string_value(obj[key], key)


def string_list_field(obj: JsonObject, key: str) -> list[str]:
    """Read an optional list whose elements are all strings."""
    if key not in obj:
        return []
    value = obj[key]
    if not isinstance(value, list):
        raise TranscriptShapeError(f"{key} is not a list")
    return [string_value(item, f"{key}[]") for item in value]


def as_object(value: object) -> JsonObject:
    return value if isinstance(value, dict) else {}


def as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def as_str(value: object) -> str:
    return value if isinstance(value, str) else ""


def shell_command(value: object) -> str:
    """Keep shell strings and preserve argument boundaries in command arrays."""
    if isinstance(value, list):
        return shlex.join([part for part in value if isinstance(part, str)])
    return as_str(value)


def codex_command(payload: JsonObject) -> str:
    try:
        arguments = decode_json_object(as_str(payload.get("arguments")) or "{}")
    except TranscriptShapeError:
        arguments = {}
    command = arguments.get("command", arguments.get("cmd", as_object(payload.get("action")).get("command")))
    parts = [as_str(part) for part in as_list(command)[:3]]
    if len(parts) >= 3 and os.path.basename(parts[0]) in ("bash", "sh", "zsh") and parts[1] in ("-c", "-lc"):
        return parts[2]
    return shell_command(command)


def text_blocks(content: object, *, strict: bool = True) -> list[str]:
    """Read text blocks while excluding tool results and other non-text blocks."""
    if isinstance(content, str):
        return [content]
    blocks = object_list_value(content, "content") if strict else list(map(as_object, as_list(content)))
    return [
        string_field(block, "text") if strict else as_str(block.get("text"))
        for block in blocks
        if block.get("type") in ("text", "input_text") or (not strict and "type" not in block and "text" in block)
    ]


def message_payload(event: JsonObject, platform: Platform, *, strict: bool = True) -> JsonObject:
    key = "payload" if platform == "codex" else "message"
    return object_field(event, key) if strict else as_object(event.get(key))


def user_text(event: JsonObject, platform: Platform, *, strict: bool = True) -> list[str]:
    """Read the user text in a Claude Code, Codex, or Cursor event."""
    if platform == "codex":
        kind = event.get("type")
        if kind not in ("event_msg", "response_item"):
            return []
        payload = message_payload(event, platform, strict=strict)
        if kind == "event_msg":
            if payload.get("type") == "user_message":
                return [string_field(payload, "message") if strict else as_str(payload.get("message"))]
            return []
        if payload.get("type") == "message" and payload.get("role") == "user":
            return text_blocks(payload.get("content", []), strict=strict)
        return []

    role = event.get("type" if platform == "claude" else "role")
    if role != "user":
        return []
    return text_blocks(message_payload(event, platform, strict=strict).get("content", ""), strict=strict)


class ToolCall(NamedTuple):
    name: str
    input: object
    call_id: str


def tool_calls(event: JsonObject, platform: Platform, *, strict: bool = True) -> list[ToolCall]:
    """Identify calls and keep raw inputs for consumer-specific interpretation."""
    if platform == "codex":
        if event.get("type") != "response_item":
            return []
        payload = message_payload(event, platform, strict=strict)
        kind = payload.get("type")
        if kind not in ("function_call", "custom_tool_call", "local_shell_call"):
            return []
        name = string_field(payload, "name", str(kind)) if strict else as_str(payload.get("name")) or "local_shell"
        return [ToolCall(name, payload.get("arguments", payload.get("input", {})), as_str(payload.get("call_id")))]

    if event.get("type" if platform == "claude" else "role") != "assistant":
        return []
    message = message_payload(event, platform, strict=strict)
    blocks: Iterable[JsonObject] = (
        object_list_field(message, "content") if strict else map(as_object, as_list(message.get("content")))
    )
    return [
        ToolCall(
            string_field(block, "name", "unknown") if strict else as_str(block.get("name")),
            block.get("input", {}),
            as_str(block.get("id")),
        )
        for block in blocks
        if block.get("type") == "tool_use"
    ]


_REDIRECTION = re.compile(r"<<<|<<-|<<|>>|<>|<&|>&|>\||&>>|&>|<|>")


def _after_heredoc(command: str, start: int, delimiter: str, strip_tabs: bool) -> int:
    """Advance past a here-document body without interpreting its contents."""
    while start < len(command):
        end = command.find("\n", start)
        if end < 0:
            return len(command)
        line = command[start:end]
        start = end + 1
        if (line.lstrip("\t") if strip_tabs else line) == delimiter:
            break
    return start


def shell_segments(command: str, *, include_redirections: bool = True) -> Iterator[list[str]]:
    """Read shell words for inspection while preserving quoted arguments."""
    segments: list[list[str]] = []
    argv: list[str] = []
    word: list[str] = []
    heredocs: list[tuple[str, bool]] = []
    quote = ""
    redirect = ""
    index = 0

    def finish_word() -> None:
        nonlocal redirect
        if not word:
            return
        value = "".join(word)
        if any(char in value for char in "\"'\\"):
            value = shlex.split(value, comments=False)[0]
        if redirect in ("<<", "<<-"):
            heredocs.append((value, redirect == "<<-"))
        if include_redirections or not redirect:
            argv.append(value)
        word.clear()
        redirect = ""

    try:
        while index < len(command):
            char = command[index]
            index += 1
            if char == "\\" and quote != "'" and index < len(command):
                escaped = command[index]
                index += 1
                if escaped != "\n":
                    word.extend((char, escaped))
            elif quote:
                word.append(char)
                if char == quote:
                    quote = ""
            elif char in "\"'":
                quote = char
                word.append(char)
            elif char == "#" and not word:
                newline = command.find("\n", index)
                index = len(command) if newline < 0 else newline
            elif char in "<>&" and (operator := _REDIRECTION.match(command, index - 1)):
                if (
                    not include_redirections
                    and not redirect
                    and char != "&"
                    and word
                    and all(d in "0123456789" for d in word)
                ):
                    word.clear()
                finish_word()
                redirect = operator.group()
                index = operator.end()
                if include_redirections:
                    argv.append(redirect)
            elif char in ";|&()`\n":
                finish_word()
                if argv:
                    segments.append(argv)
                    argv = []
                redirect = ""
                if char == "\n":
                    for delimiter, strip_tabs in heredocs:
                        index = _after_heredoc(command, index, delimiter, strip_tabs)
                    heredocs.clear()
            elif char in " \t\r":
                finish_word()
            else:
                word.append(char)

        finish_word()
    except ValueError:
        return
    if argv:
        segments.append(argv)
    yield from segments


def discover(
    prefixes: Sequence[str],
    cutoff: float,
    *,
    platform: DiscoveryPlatform | None = None,
    claude_root: Path | None = None,
    codex_root: Path | None = None,
) -> list[tuple[float, DiscoveryPlatform, Path]]:
    """List recent Claude Code and Codex transcripts, newest first."""
    home = Path.home()
    if claude_root is None:
        claude_root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or home / ".claude") / "projects"
    codex_roots = (
        (codex_root,)
        if codex_root is not None
        else (Path(os.environ.get("CODEX_HOME") or home / ".codex") / "sessions", home / ".agents" / "sessions")
    )

    candidates: list[tuple[float, DiscoveryPlatform, Path]] = []
    if platform in (None, "claude") and claude_root.is_dir():
        encoded = tuple(re.sub(r"[^A-Za-z0-9]", "-", prefix) for prefix in prefixes)
        for project in claude_root.glob("*"):
            if project.is_dir() and (not encoded or project.name.startswith(encoded)):
                candidates.extend(_recent(project.glob("*.jsonl"), "claude", cutoff))
    if platform in (None, "codex"):
        seen = set()
        for root in codex_roots:
            if not root.is_dir():
                continue
            resolved = root.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            candidates.extend(_recent(root.rglob("*.jsonl"), "codex", cutoff))
    return sorted(candidates, key=lambda candidate: candidate[0], reverse=True)


def _recent(
    paths: Iterable[Path], platform: DiscoveryPlatform, cutoff: float
) -> Iterator[tuple[float, DiscoveryPlatform, Path]]:
    for path in paths:
        try:
            info = path.stat()
            if stat.S_ISREG(info.st_mode) and info.st_mtime >= cutoff:
                yield info.st_mtime, platform, path
        except OSError:
            continue


def main() -> None:
    """Provide the Claude Code and Codex discovery backend for discover-sessions.sh."""
    platform, days, *raw_prefixes = sys.argv[1:]
    if platform not in ("claude", "codex"):
        raise SystemExit(f"Unknown platform: {platform}")
    prefixes = []
    for raw in raw_prefixes:
        prefix = raw.rstrip("/") or "/"
        prefixes.append(prefix)
        if Path(prefix).is_dir():
            prefixes.append(str(Path(prefix).resolve()))
    for _, _, path in discover(prefixes, time.time() - int(days) * 86400, platform=cast(DiscoveryPlatform, platform)):
        print(path)


if __name__ == "__main__":
    main()
