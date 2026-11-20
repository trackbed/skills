"""Field validation shared by interview questions and evidence figures."""

from __future__ import annotations

import re
from typing import Any, Optional

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")


class Problems:
    """What is wrong with a file, one line per problem, each naming where it is."""

    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, where: str, message: str) -> None:
        self.items.append(f"{where}: {message}")


def _keys(raw: dict[str, Any], allowed: tuple[str, ...], where: str, problems: Problems) -> None:
    for key in raw:
        if key not in allowed:
            problems.add(where, f"has an unknown field `{key}`; the fields here are {', '.join(allowed)}")


def text_of(raw: Any, where: str, problems: Problems, *, limit: int, required: bool = True) -> str:
    if raw is None and not required:
        return ""
    if not isinstance(raw, str):
        problems.add(where, "must be text" if required else "must be text when given")
        return ""
    value = raw.strip()
    if not value and required:
        problems.add(where, "must not be empty")
    if len(value) > limit:
        problems.add(where, f"is {len(value)} characters; keep it within {limit}")
    return value


def _texts(raw: Any, where: str, problems: Problems, *, limit: int, most: int) -> list[str]:
    """One paragraph or a list of them, as a list."""
    if raw is None:
        return []
    values = raw if isinstance(raw, list) else [raw]
    if len(values) > most:
        problems.add(where, f"has {len(values)} entries; keep it within {most}")
    return [
        text
        for index, value in enumerate(values)
        if (text := text_of(value, f"{where}[{index}]", problems, limit=limit))
    ]


def _ident(raw: Any, where: str, problems: Problems) -> str:
    if not isinstance(raw, str) or not ID_RE.match(raw):
        problems.add(where, "must be a short id of lowercase letters, digits, and hyphens")
        return ""
    return raw


def _integer(raw: Any, where: str, problems: Problems, *, low: int, high: int, default: Optional[int] = None) -> int:
    if raw is None and default is not None:
        return default
    if not isinstance(raw, int) or isinstance(raw, bool) or not low <= raw <= high:
        problems.add(where, f"must be a whole number from {low} to {high}")
        return low
    return raw


def _flag(raw: Any, where: str, problems: Problems, *, default: bool) -> bool:
    if raw is None:
        return default
    if not isinstance(raw, bool):
        problems.add(where, "must be true or false")
        return default
    return raw


def _objects(raw: Any, where: str, problems: Problems, *, low: int, high: int) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not all(isinstance(entry, dict) for entry in raw):
        problems.add(where, "must be a list of objects")
        return []
    if not low <= len(raw) <= high:
        problems.add(where, f"has {len(raw)} entries; it takes {low} to {high}")
    return list(raw)


def _labelled(
    raw: Any, where: str, problems: Problems, *, low: int, high: int, extra: tuple[str, ...] = ()
) -> list[dict[str, Any]]:
    """A list of things a person picks between: each has an id, a label, and maybe a description."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, entry in enumerate(_objects(raw, where, problems, low=low, high=high)):
        here = f"{where}[{index}]"
        _keys(entry, ("id", "label", "description", *extra), here, problems)
        ident = _ident(entry.get("id"), f"{here}.id", problems)
        if ident in seen:
            problems.add(f"{here}.id", f"`{ident}` is used twice")
        seen.add(ident)
        result.append(
            {
                "id": ident,
                "label": text_of(entry.get("label"), f"{here}.label", problems, limit=160),
                "description": text_of(
                    entry.get("description"), f"{here}.description", problems, limit=600, required=False
                ),
            }
        )
    return result
