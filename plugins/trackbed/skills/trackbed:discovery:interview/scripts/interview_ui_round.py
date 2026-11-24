"""Read an interview round the model wrote.

A round is one page of questions (`references/ui-round-format.md`). Reading it checks every field and
returns a plain dictionary that the page builder renders and the answer check reads, so nothing after
this module has to distrust a round. `check_value` is the one definition of a complete answer to a
question: a round's recommendations pass through it here, and a person's answers in
`interview_ui_answers`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from interview_ui_fields import Problems, _flag, _ident, _integer, _keys, _labelled, _objects, _texts, text_of
from interview_ui_figures import FIGURE_KINDS as FIGURE_KINDS, RoundImages, read_figures

ROUND_FORMAT = "trackbed-interview-round"
ANSWERS_FORMAT = "trackbed-interview-answers"
SCHEMA_VERSION = 1

KINDS = ("choice", "rank", "scale", "allocate", "matrix", "confirm", "text")
# Kinds whose question carries the interviewer's own recommendation.
RECOMMENDED_KINDS = ("choice", "rank", "scale", "allocate", "matrix")
# The field of such a question's answer that a recommendation picks a value for.
CORE = {"choice": "selected", "rank": "order", "scale": "value", "allocate": "amounts", "matrix": "cells"}
STATES = ("resolved", "active", "open")
STATUSES = ("answered", "unsure", "open")
NEXT = ("continue", "wrap-up")

MAX_QUESTIONS = 8
MAX_NOTE_CHARS = 2_000
MAX_TEXT_CHARS = 5_000


def _recommendation(raw: Any, question: dict[str, Any], where: str, problems: Problems) -> Optional[dict[str, Any]]:
    kind = question["kind"]
    if kind not in RECOMMENDED_KINDS:
        if raw is not None:
            problems.add(where, f"a `{kind}` question takes no recommendation; say what you inferred in the question")
        return None
    if not isinstance(raw, dict):
        problems.add(
            where,
            "is required: give `pick` and `reason`, or `pick: null` with a reason when you have no preference",
        )
        return None
    _keys(raw, ("pick", "reason"), where, problems)
    reason = text_of(raw.get("reason"), f"{where}.reason", problems, limit=600)
    pick = raw.get("pick")
    if pick is None:
        return {"pick": None, "reason": reason}
    value: dict[str, Any] = {CORE[kind]: pick}
    if kind == "choice":
        value = {"selected": pick if isinstance(pick, list) else [pick], "other": ""}
    checked = Problems()
    normal = check_value(question, value, f"{where}.pick", checked)
    if checked.items or normal is None:
        problems.items.extend(checked.items or [f"{where}.pick: is not a complete answer to this question"])
        return {"pick": None, "reason": reason}
    return {"pick": normal[CORE[kind]], "reason": reason}


def _question(raw: dict[str, Any], where: str, problems: Problems, media: RoundImages) -> dict[str, Any]:
    kind = raw.get("kind")
    if kind not in KINDS:
        problems.add(f"{where}.kind", f"must be one of {', '.join(KINDS)}")
        kind = "text"
    question: dict[str, Any] = {
        "id": _ident(raw.get("id"), f"{where}.id", problems),
        "kind": kind,
        "title": text_of(raw.get("title"), f"{where}.title", problems, limit=300),
        "why": text_of(raw.get("why"), f"{where}.why", problems, limit=700),
        "dimension": text_of(raw.get("dimension"), f"{where}.dimension", problems, limit=40, required=False),
        **read_figures(raw, where, problems, media),
    }
    common = ("id", "kind", "title", "why", "dimension", "figure", "figures", "recommendation")
    if kind == "choice":
        _keys(raw, (*common, "options", "multiple", "other"), where, problems)
        question["multiple"] = _flag(raw.get("multiple"), f"{where}.multiple", problems, default=False)
        question["other"] = _flag(raw.get("other"), f"{where}.other", problems, default=True)
        # `_labelled` returns one option per entry, in order, or none when the list is not a list of objects.
        entries: Any = raw.get("options")
        options = _labelled(
            entries, f"{where}.options", problems, low=2, high=6, extra=("gives", "costs", "figure", "figures")
        )
        for index, option in enumerate(options):
            entry = entries[index]
            here = f"{where}.options[{index}]"
            option["gives"] = _texts(entry.get("gives"), f"{here}.gives", problems, limit=200, most=4)
            option["costs"] = _texts(entry.get("costs"), f"{here}.costs", problems, limit=200, most=4)
            option.update(read_figures(entry, here, problems, media))
        question["options"] = options
    elif kind == "rank":
        _keys(raw, (*common, "items"), where, problems)
        question["items"] = _labelled(raw.get("items"), f"{where}.items", problems, low=2, high=8)
    elif kind == "scale":
        _keys(raw, (*common, "low", "high", "steps"), where, problems)
        question["low"] = text_of(raw.get("low"), f"{where}.low", problems, limit=80)
        question["high"] = text_of(raw.get("high"), f"{where}.high", problems, limit=80)
        question["steps"] = _integer(raw.get("steps"), f"{where}.steps", problems, low=3, high=7, default=5)
    elif kind == "allocate":
        _keys(raw, (*common, "items", "total", "unit", "step"), where, problems)
        question["items"] = _labelled(raw.get("items"), f"{where}.items", problems, low=2, high=8)
        total = _integer(raw.get("total"), f"{where}.total", problems, low=2, high=1000, default=100)
        question["total"] = total
        question["unit"] = text_of(raw.get("unit"), f"{where}.unit", problems, limit=24, required=False) or "points"
        default_step = 5 if total % 5 == 0 and total >= 50 else 1
        step = _integer(raw.get("step"), f"{where}.step", problems, low=1, high=total, default=default_step)
        if total % step:
            problems.add(f"{where}.step", f"must divide the total of {total} evenly")
            step = 1
        question["step"] = step
    elif kind == "matrix":
        _keys(raw, (*common, "rows", "columns"), where, problems)
        question["rows"] = _labelled(raw.get("rows"), f"{where}.rows", problems, low=1, high=10)
        question["columns"] = _labelled(raw.get("columns"), f"{where}.columns", problems, low=2, high=5)
    elif kind == "confirm":
        _keys(raw, (*common, "statement", "source"), where, problems)
        question["statement"] = text_of(raw.get("statement"), f"{where}.statement", problems, limit=700)
        question["source"] = text_of(raw.get("source"), f"{where}.source", problems, limit=240, required=False)
    else:
        _keys(raw, (*common, "placeholder", "long"), where, problems)
        question["placeholder"] = text_of(
            raw.get("placeholder"), f"{where}.placeholder", problems, limit=160, required=False
        )
        question["long"] = _flag(raw.get("long"), f"{where}.long", problems, default=False)
    question["recommendation"] = _recommendation(
        raw.get("recommendation"), question, f"{where}.recommendation", problems
    )
    return question


def _progress(raw: Any, where: str, problems: Problems) -> Optional[dict[str, Any]]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        problems.add(where, "must be an object")
        return None
    _keys(raw, ("label", "target", "entries"), where, problems)
    progress: dict[str, Any] = {
        "label": text_of(raw.get("label"), f"{where}.label", problems, limit=60, required=False) or "Progress",
        "target": None,
        "entries": [],
    }
    if raw.get("target") is not None:
        progress["target"] = _integer(raw.get("target"), f"{where}.target", problems, low=1, high=100)
    for index, entry in enumerate(_objects(raw.get("entries"), f"{where}.entries", problems, low=1, high=16)):
        here = f"{where}.entries[{index}]"
        _keys(entry, ("label", "value", "state", "depth", "note"), here, problems)
        item: dict[str, Any] = {
            "label": text_of(entry.get("label"), f"{here}.label", problems, limit=80),
            "note": text_of(entry.get("note"), f"{here}.note", problems, limit=200, required=False),
            "depth": _integer(entry.get("depth"), f"{here}.depth", problems, low=0, high=4, default=0),
            "value": None,
            "state": None,
        }
        if (entry.get("value") is None) == (entry.get("state") is None):
            problems.add(here, "takes either `value` (0 to 100) or `state` (resolved, active, open), not both")
        elif entry.get("value") is not None:
            item["value"] = _integer(entry.get("value"), f"{here}.value", problems, low=0, high=100)
        elif entry.get("state") in STATES:
            item["state"] = entry["state"]
        else:
            problems.add(f"{here}.state", f"must be one of {', '.join(STATES)}")
        progress["entries"].append(item)
    return progress


def read_round(raw: Any, media_dir: Optional[Path] = None) -> tuple[Optional[dict[str, Any]], list[str]]:
    """The round as a checked dictionary, or the problems that stop it from being asked."""
    problems = Problems()
    if not isinstance(raw, dict):
        return None, ["round: must be a JSON object"]
    if raw.get("format") != ROUND_FORMAT or raw.get("schemaVersion") != SCHEMA_VERSION:
        problems.add("round", f'must have "format": "{ROUND_FORMAT}" and "schemaVersion": {SCHEMA_VERSION}')
    _keys(
        raw,
        ("format", "schemaVersion", "session", "number", "title", "synthesis", "progress", "questions"),
        "round",
        problems,
    )
    session_raw = raw.get("session")
    if not isinstance(session_raw, dict):
        problems.add("session", "must be an object with `id` and `title`")
        session_raw = {}
    _keys(session_raw, ("id", "title", "topic"), "session", problems)
    round_: dict[str, Any] = {
        "session": {
            "id": _ident(session_raw.get("id"), "session.id", problems),
            "title": text_of(session_raw.get("title"), "session.title", problems, limit=160),
            "topic": text_of(session_raw.get("topic"), "session.topic", problems, limit=60, required=False),
        },
        "number": _integer(raw.get("number"), "number", problems, low=1, high=99),
        "title": text_of(raw.get("title"), "title", problems, limit=160),
        "synthesis": _texts(raw.get("synthesis"), "synthesis", problems, limit=900, most=4),
        "progress": _progress(raw.get("progress"), "progress", problems),
        "questions": [],
    }
    if not round_["synthesis"]:
        problems.add("synthesis", "provide at least one paragraph")
    seen: set[str] = set()
    media = RoundImages(media_dir)
    for index, entry in enumerate(_objects(raw.get("questions"), "questions", problems, low=1, high=MAX_QUESTIONS)):
        question = _question(entry, f"questions[{index}]", problems, media)
        if question["id"] in seen:
            problems.add(f"questions[{index}].id", f"`{question['id']}` is used twice")
        seen.add(question["id"])
        round_["questions"].append(question)
    if problems.items:
        return None, problems.items
    canonical = json.dumps(round_, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    round_["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return round_, []


def ids_of(entries: list[dict[str, Any]]) -> list[str]:
    return [str(entry["id"]) for entry in entries]


def check_value(question: dict[str, Any], raw: Any, where: str, problems: Problems) -> Optional[dict[str, Any]]:
    """A complete answer to one question, checked against what the question offers."""
    kind = question["kind"]
    if not isinstance(raw, dict):
        problems.add(where, "must be an object")
        return None
    if kind == "choice":
        selected = raw.get("selected")
        known = ids_of(question["options"])
        if not isinstance(selected, list) or any(entry not in known for entry in selected):
            problems.add(f"{where}.selected", "must list option ids from this question")
            return None
        if len(set(selected)) != len(selected) or (len(selected) > 1 and not question["multiple"]):
            problems.add(f"{where}.selected", "holds more options than this question takes")
            return None
        other = text_of(raw.get("other"), f"{where}.other", problems, limit=MAX_NOTE_CHARS, required=False)
        if selected and other and not question["multiple"]:
            problems.add(where, "a single choice takes either a selected option or a write-in")
            return None
        if other and not question["other"]:
            problems.add(f"{where}.other", "this question takes no answer of your own")
            return None
        if not selected and not other:
            problems.add(where, "selects nothing")
            return None
        return {"selected": [entry for entry in known if entry in selected], "other": other}
    if kind == "rank":
        order = raw.get("order")
        if (
            not isinstance(order, list)
            or not all(isinstance(entry, str) for entry in order)
            or sorted(order) != sorted(ids_of(question["items"]))
        ):
            problems.add(f"{where}.order", "must list every item of this question once")
            return None
        return {"order": list(order)}
    if kind == "scale":
        value = raw.get("value")
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= question["steps"]:
            problems.add(f"{where}.value", f"must be a whole number from 1 to {question['steps']}")
            return None
        return {"value": value}
    if kind == "allocate":
        amounts = raw.get("amounts")
        known = ids_of(question["items"])
        if not isinstance(amounts, dict) or any(key not in known for key in amounts):
            problems.add(f"{where}.amounts", "must give an amount per item of this question")
            return None
        result = {key: amounts.get(key, 0) for key in known}
        if any(isinstance(amount, bool) or not isinstance(amount, int) or amount < 0 for amount in result.values()):
            problems.add(f"{where}.amounts", "must be whole numbers that are not negative")
            return None
        if sum(result.values()) != question["total"]:
            problems.add(f"{where}.amounts", f"must add up to {question['total']}")
            return None
        if any(amount % question["step"] for amount in result.values()):
            problems.add(f"{where}.amounts", f"must be multiples of {question['step']}")
            return None
        return {"amounts": result}
    if kind == "matrix":
        cells = raw.get("cells")
        rows, columns = ids_of(question["rows"]), ids_of(question["columns"])
        if (
            not isinstance(cells, dict)
            or sorted(cells) != sorted(rows)
            or any(cell not in columns for cell in cells.values())
        ):
            problems.add(f"{where}.cells", "must give one column of this question for every row")
            return None
        return {"cells": {row: cells[row] for row in rows}}
    if kind == "confirm":
        verdict = raw.get("verdict")
        if verdict not in ("confirm", "correct"):
            problems.add(f"{where}.verdict", "must be confirm or correct")
            return None
        correction = text_of(
            raw.get("correction"), f"{where}.correction", problems, limit=MAX_NOTE_CHARS, required=False
        )
        if verdict == "correct" and not correction:
            problems.add(f"{where}.correction", "must say what is right when the verdict is correct")
            return None
        return {"verdict": verdict, "correction": correction if verdict == "correct" else ""}
    text = text_of(raw.get("text"), f"{where}.text", problems, limit=MAX_TEXT_CHARS)
    return {"text": text} if text else None
