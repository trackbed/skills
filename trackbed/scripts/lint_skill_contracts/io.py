from __future__ import annotations

import json
from pathlib import Path

JsonObject = dict[str, object]


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(root: Path, path: str) -> Path:
    return (root / path).resolve()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def skill_paths(root: Path, pattern: str) -> list[Path]:
    return sorted(path for path in root.glob(pattern) if path.is_file())


def load_json_object(path: Path, label: str) -> JsonObject:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"{path}: cannot read {label}: {exc}") from exc

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: {label} must be JSON-compatible YAML for stdlib parsing: {exc}") from exc

    if not isinstance(value, dict):
        raise SystemExit(f"{path}: {label} must be a JSON object; received {json_value_kind(value)}.")
    return value


def json_value_kind(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, list):
        return "array"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return type(value).__name__
