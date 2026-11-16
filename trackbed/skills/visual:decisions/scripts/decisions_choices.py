"""Carry a reader's recorded choices into a rebuilt decision document.

The page's runtime (`assets/decisions.js`) applies the same rules when it reads an export, and
`tests/fixtures/visual-decisions-choices-cases.json` holds both to the same answers.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from decisions_model import FORMAT, MAX_NOTES_CHARS, SCHEMA_VERSION, STATUSES, BuildError, Model, allowed_choices

MAX_LABEL_CHARS = 300
MAX_DECISIONS = 5000
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
STATE_BLOCK_RE = re.compile(r'<script type="application/json" id="trackbed-decisions-state">(.*?)</script>', re.S)


def load_choices(path: Path) -> Any:
    """Read a choices export, or the choices embedded in a saved copy of a decision document."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise BuildError(f"{path}: cannot read the choices file: {error}") from error
    if path.suffix.lower() in (".html", ".htm"):
        match = STATE_BLOCK_RE.search(text)
        if not match:
            raise BuildError(f"{path}: is not a decision document, so it holds no choices to carry over")
        text = match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise BuildError(f"{path}: is not valid JSON: {error}") from error


def is_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not TIMESTAMP_RE.match(value):
        return False
    try:
        dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return False
    return True


def has_content(record: dict[str, Any]) -> bool:
    """An earlier choice waiting for review counts, even when its option is gone and it has no notes."""
    return bool(record.get("option") or record.get("status") != "open" or record.get("notes") or record.get("earlier"))


def check_record(raw: Any) -> Optional[str]:
    """Why one decision record is unusable, or None. The page's runtime applies the same rules."""
    if not isinstance(raw, dict) or not isinstance(raw.get("itemId"), str) or not raw["itemId"]:
        return "a decision record has no itemId"
    item_id = raw["itemId"]
    option = raw.get("option")
    if option is not None and not (isinstance(option, str) and len(option) <= 64):
        return f"{item_id}: option must be text or null"
    if raw.get("status") not in STATUSES:
        return f"{item_id}: status must be one of {', '.join(STATUSES)}"
    notes = raw.get("notes")
    if not isinstance(notes, str) or len(notes) > MAX_NOTES_CHARS:
        return f"{item_id}: notes must be text of at most {MAX_NOTES_CHARS} characters"
    if raw["status"] == "decided" and not option:
        return f"{item_id}: a decided record needs an option"
    if not has_content(raw):
        # An item the reader never touched: nothing to carry, so nothing more to check.
        return None
    if not is_timestamp(raw.get("updatedAt")):
        return f"{item_id}: updatedAt must be a UTC time such as 2026-01-15T09:30:00.000Z"
    fingerprint = raw.get("itemFingerprint")
    if not (isinstance(fingerprint, str) and 0 < len(fingerprint) <= 64):
        return f"{item_id}: itemFingerprint is missing"
    label = raw.get("choiceLabel")
    if label is not None and not (isinstance(label, str) and len(label) <= MAX_LABEL_CHARS):
        return f"{item_id}: choiceLabel must be text of at most {MAX_LABEL_CHARS} characters"
    earlier = raw.get("earlier")
    if earlier is not None and not (
        isinstance(earlier, dict)
        and earlier.get("status") in STATUSES
        and isinstance(earlier.get("choiceLabel"), str)
        and len(earlier["choiceLabel"]) <= MAX_LABEL_CHARS
    ):
        return f"{item_id}: earlier must hold a status and a choiceLabel"
    return None


@dataclass
class Carried:
    decisions: list[dict[str, Any]] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    needs_review: list[str] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)


def carry_choices(model: Model, payload: Any) -> tuple[Carried, list[str]]:
    """Match recorded choices to the rebuilt items. Nothing is attached to a changed item silently."""
    problems: list[str] = []
    carried = Carried()
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        return carried, ["the choices file is not a decision document export"]
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        return carried, [
            f"the choices file uses format version {payload.get('schemaVersion')!r}; this builder reads {SCHEMA_VERSION}"
        ]
    source = payload.get("document")
    source_id = source.get("id") if isinstance(source, dict) else None
    if source_id != model.document.id:
        return carried, [
            f'the choices file belongs to document "{source_id}", not "{model.document.id}". '
            "Keep document.id stable across rebuilds, or leave these choices out"
        ]
    decisions = payload.get("decisions")
    if not isinstance(decisions, list) or len(decisions) > MAX_DECISIONS:
        return carried, ["the choices file has no usable decisions list"]
    seen: set[str] = set()
    for raw in decisions:
        problem = check_record(raw)
        if problem is None and raw["itemId"] in seen:
            problem = f"{raw['itemId']}: appears more than once"
        if problem:
            problems.append(problem)
            continue
        seen.add(raw["itemId"])
        if not has_content(raw):
            continue
        item = model.item(raw["itemId"])
        title = str(raw.get("itemTitle") or "")
        if item is None:
            carried.dropped.append(
                {"itemId": raw["itemId"], "itemTitle": title, "reason": "no item with this id in the rebuilt document"}
            )
            continue
        if raw["itemFingerprint"] == item.fingerprint:
            if raw.get("option") and raw["option"] not in allowed_choices(item):
                problems.append(f'{item.id}: option "{raw["option"]}" is not one this item offers')
                continue
            carried.unchanged.append(item.id)
        else:
            carried.needs_review.append(item.id)
        carried.decisions.append(raw)
    if problems:
        return Carried(), problems
    return carried, []
