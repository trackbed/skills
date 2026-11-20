"""Read the answers a person gave to an interview round, and spell them out for the interviewer.

The answers a page sends back are checked against the round they answer (`interview_ui_round`): an
answer can only name a question, an option, an item, or a row that round asked about, and only a
complete answer carries a value.
"""

from __future__ import annotations

from typing import Any, Optional

from interview_ui_fields import Problems, text_of
from interview_ui_round import (
    ANSWERS_FORMAT,
    CORE,
    MAX_NOTE_CHARS,
    MAX_TEXT_CHARS,
    NEXT,
    SCHEMA_VERSION,
    STATUSES,
    check_value,
    ids_of,
)


def read_answers(round_: dict[str, Any], raw: Any) -> tuple[Optional[dict[str, Any]], list[str]]:
    """The answers to `round_` as a checked dictionary, or the problems that make them unusable."""
    problems = Problems()
    if not isinstance(raw, dict):
        return None, ["answers: must be a JSON object"]
    if raw.get("format") != ANSWERS_FORMAT or raw.get("schemaVersion") != SCHEMA_VERSION:
        return None, [f'answers: must have "format": "{ANSWERS_FORMAT}" and "schemaVersion": {SCHEMA_VERSION}']
    if raw.get("session") != round_["session"]["id"] or raw.get("round") != round_["number"]:
        return None, [
            f"answers: are for round {raw.get('round')!r} of {raw.get('session')!r}, "
            f"not round {round_['number']} of {round_['session']['id']!r}"
        ]
    if raw.get("fingerprint") != round_["fingerprint"]:
        return None, ["answers: were given to an earlier version of this round; reload the page and answer again"]
    next_step = raw.get("next", "continue")
    if next_step not in NEXT:
        problems.add("next", f"must be one of {', '.join(NEXT)}")
    entries = raw.get("answers")
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        return None, ["answers.answers: must be a list of objects"]
    if not all(isinstance(entry.get("id"), str) for entry in entries):
        return None, ["answers.answers: each entry must have a string id"]
    by_id = {entry["id"]: entry for entry in entries}
    known = ids_of(round_["questions"])
    if len(by_id) != len(entries) or set(by_id) != set(known):
        return None, ["answers.answers: must hold exactly one entry for every question of the round"]
    answers: list[dict[str, Any]] = []
    for question in round_["questions"]:
        entry = by_id[question["id"]]
        where = f"answers[{question['id']}]"
        status = entry.get("status")
        if status not in STATUSES:
            problems.add(f"{where}.status", f"must be one of {', '.join(STATUSES)}")
            continue
        value = check_value(question, entry.get("value"), f"{where}.value", problems) if status == "answered" else None
        answers.append(
            {
                "id": question["id"],
                "status": status,
                "value": value,
                "note": text_of(entry.get("note"), f"{where}.note", problems, limit=MAX_NOTE_CHARS, required=False),
            }
        )
    note = text_of(raw.get("note"), "note", problems, limit=MAX_TEXT_CHARS, required=False)
    if problems.items:
        return None, problems.items
    submitted = raw.get("submittedAt")
    return {
        "format": ANSWERS_FORMAT,
        "schemaVersion": SCHEMA_VERSION,
        "session": round_["session"]["id"],
        "round": round_["number"],
        "fingerprint": round_["fingerprint"],
        "submittedAt": submitted if isinstance(submitted, str) else None,
        "next": next_step,
        "note": note,
        "answers": answers,
    }, []


def _labels(entries: list[dict[str, Any]]) -> dict[str, str]:
    return {str(entry["id"]): str(entry["label"]) for entry in entries}


def _in_words(question: dict[str, Any], value: dict[str, Any]) -> str:
    """One answer in the words the person saw on the page."""
    kind = question["kind"]
    if kind == "choice":
        labels = _labels(question["options"])
        parts = [labels[entry] for entry in value["selected"]]
        if value["other"]:
            parts.append(f"their own answer: {value['other']}")
        return "; ".join(parts)
    if kind == "rank":
        labels = _labels(question["items"])
        return " > ".join(f"{place}. {labels[entry]}" for place, entry in enumerate(value["order"], 1))
    if kind == "scale":
        return (
            f"{value['value']} of {question['steps']} (1 = {question['low']}, {question['steps']} = {question['high']})"
        )
    if kind == "allocate":
        labels = _labels(question["items"])
        ordered = sorted(value["amounts"].items(), key=lambda pair: -pair[1])
        return "; ".join(f"{labels[entry]}: {amount} {question['unit']}" for entry, amount in ordered)
    if kind == "matrix":
        rows, columns = _labels(question["rows"]), _labels(question["columns"])
        return "; ".join(f"{rows[row]}: {columns[column]}" for row, column in value["cells"].items())
    if kind == "confirm":
        return "confirmed" if value["verdict"] == "confirm" else f"corrected: {value['correction']}"
    return str(value["text"])


def describe_answers(round_: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    """Checked answers with each one spelled out, for the interviewer to read."""
    by_id = {entry["id"]: entry for entry in answers["answers"]}
    described: list[dict[str, Any]] = []
    for question in round_["questions"]:
        entry = by_id[question["id"]]
        value = entry["value"]
        row: dict[str, Any] = {
            "id": question["id"],
            "question": question["title"],
            "kind": question["kind"],
            "status": entry["status"],
            "answer": _in_words(question, value) if value is not None else None,
            "value": value,
            "note": entry["note"],
        }
        recommendation = question["recommendation"]
        if value is not None and recommendation is not None and recommendation["pick"] is not None:
            own_words = question["kind"] == "choice" and bool(value["other"])
            row["matchesRecommendation"] = value[CORE[question["kind"]]] == recommendation["pick"] and not own_words
        described.append(row)
    return {
        "session": answers["session"],
        "round": answers["round"],
        "next": answers["next"],
        "note": answers["note"],
        "counts": {status: sum(1 for entry in described if entry["status"] == status) for status in STATUSES},
        "answers": described,
    }
