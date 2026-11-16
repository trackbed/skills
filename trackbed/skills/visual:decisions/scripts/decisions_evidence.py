"""Read one evidence entry of a decision document: a capture, a table, an excerpt, or a chart.

A chart is drawn by the builder from numbers the content gives, so it can be checked here:
bars start at zero, share one scale, and there are enough of them to be worth a chart.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Optional, Protocol

from decisions_images import ImageProblem, embed_image
from decisions_model import Evidence

EVIDENCE_TYPES = ("image", "table", "excerpt", "chart")
ORIGINS = ("source", "added")
MIN_BARS = 2
MAX_BARS = 12
FOCUS_RE = re.compile(r"^(?:100|\d{1,2})% (?:100|\d{1,2})%$")


class Collector(Protocol):
    """What the content reader offers while an entry is read."""

    base_dir: Path
    image_count: int

    def problem(self, where: str, message: str) -> None: ...

    def text(self, raw: dict[str, Any], key: str, where: str, *, required: bool = False, limit: int = 4000) -> str: ...

    def lines(self, raw: dict[str, Any], key: str, where: str, *, required: bool = False) -> list[str]: ...

    def unknown_keys(self, raw: dict[str, Any], allowed: tuple[str, ...], where: str) -> None: ...


def read_evidence(reader: Collector, raw: Any, where: str) -> Optional[Evidence]:
    if not isinstance(raw, dict):
        reader.problem(where, "must be an object")
        return None
    kind = raw.get("type")
    if kind not in EVIDENCE_TYPES:
        reader.problem(f"{where}.type", f"must be one of {', '.join(EVIDENCE_TYPES)}")
        return None
    common = ("type", "label", "caption", "source", "origin")
    evidence = Evidence(
        kind=kind,
        label=reader.text(raw, "label", where, limit=60),
        caption=reader.text(raw, "caption", where, required=True, limit=600),
        source=reader.text(raw, "source", where, limit=400),
        # A chart is always a drawing made for the document, whoever supplied its numbers.
        origin=raw.get("origin", "added" if kind == "chart" else "source"),
    )
    if evidence.origin not in ORIGINS:
        reader.problem(f"{where}.origin", f"must be one of {', '.join(ORIGINS)}")
        evidence.origin = "source"
    if kind == "chart" and evidence.origin != "added":
        reader.problem(f"{where}.origin", 'must be "added" or left out: a chart is always made for the document')
        evidence.origin = "added"
    if kind == "image":
        reader.unknown_keys(raw, (*common, "file", "alt", "focus"), where)
        evidence.alt = reader.text(raw, "alt", where, limit=400) or evidence.caption
        evidence.focus = reader.text(raw, "focus", where, limit=9)
        if evidence.focus and not FOCUS_RE.match(evidence.focus):
            reader.problem(f"{where}.focus", 'must be two percentages such as "50% 20%"')
            evidence.focus = ""
        read_image(reader, reader.text(raw, "file", where, required=True, limit=1000), evidence, where)
    elif kind == "table":
        reader.unknown_keys(raw, (*common, "columns", "rows"), where)
        evidence.columns = reader.lines(raw, "columns", where)
        rows = raw.get("rows")
        if not (isinstance(rows, list) and rows):
            reader.problem(f"{where}.rows", "must be a non-empty list of rows")
            rows = []
        for index, row in enumerate(rows):
            if not (isinstance(row, list) and row and all(isinstance(cell, (str, int, float)) for cell in row)):
                reader.problem(f"{where}.rows[{index}]", "must be a list of text or number cells")
                continue
            evidence.rows.append([str(cell) for cell in row])
        widths = {len(row) for row in evidence.rows} | ({len(evidence.columns)} if evidence.columns else set())
        if len(widths) > 1:
            reader.problem(f"{where}.rows", "every row, and columns when given, must have the same number of cells")
    elif kind == "chart":
        reader.unknown_keys(raw, (*common, "unit", "rows", "emphasize", "limit"), where)
        read_chart(reader, raw, evidence, where)
    else:
        reader.unknown_keys(raw, (*common, "text"), where)
        value = raw.get("text")
        if not isinstance(value, str) or not value.strip():
            reader.problem(f"{where}.text", "is required: the quoted code, output, or passage")
        else:
            evidence.text = value.strip("\n")
            if len(evidence.text) > 12000:
                reader.problem(f"{where}.text", "is longer than 12000 characters; quote the part that proves the point")
    if evidence.origin == "added" and not evidence.source:
        reader.problem(
            f"{where}.source",
            "is required for something made for this document: say what it was drawn or captured from",
        )
    return evidence


def read_image(reader: Collector, name: str, evidence: Evidence, where: str) -> None:
    if not name:
        return
    path = Path(name).expanduser()
    if not path.is_absolute():
        path = reader.base_dir / path
    try:
        evidence.data_url, evidence.width, evidence.height = embed_image(path)
    except ImageProblem as problem:
        hint = f"; paths are relative to {reader.base_dir}" if problem.missing else ""
        reader.problem(f"{where}.file", f"{problem}{hint}")
        return
    evidence.file_name = path.name
    evidence.source = evidence.source or name
    reader.image_count += 1


def is_amount(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def amount_text(value: float, unit: str) -> str:
    """A value the way the reader sees it: `51,000`, `4.5 s`, `62%`."""
    number = f"{value:,.0f}" if float(value).is_integer() else f"{value:,.3f}".rstrip("0").rstrip(".")
    if not unit:
        return number
    return f"{number}{unit}" if unit == "%" else f"{number} {unit}"


def read_chart(reader: Collector, raw: dict[str, Any], evidence: Evidence, where: str) -> None:
    unit = reader.text(raw, "unit", where, limit=12)
    rows = raw.get("rows")
    if not isinstance(rows, list):
        reader.problem(f"{where}.rows", "is required: a list of [label, number] pairs")
        rows = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        spot = f"{where}.rows[{index}]"
        if not (isinstance(row, list) and len(row) == 2 and isinstance(row[0], str) and row[0].strip()):
            reader.problem(spot, 'must be a label and a number, such as ["12 months", 48]')
            continue
        label = row[0].strip()
        if not is_amount(row[1]):
            reader.problem(spot, "needs a number of zero or more as its value; bars start at zero")
            continue
        if label in seen:
            reader.problem(spot, f'"{label}" appears more than once')
        seen.add(label)
        evidence.bars.append((label, float(row[1]), amount_text(float(row[1]), unit)))
    if isinstance(raw.get("rows"), list) and not MIN_BARS <= len(rows) <= MAX_BARS:
        reader.problem(
            f"{where}.rows",
            f"needs {MIN_BARS} to {MAX_BARS} bars; state a single number in a sentence, and put a longer list in a table",
        )
    if evidence.bars and not any(value > 0 for _, value, _ in evidence.bars):
        reader.problem(f"{where}.rows", "has no value above zero, so there is nothing to draw")
    for label in reader.lines(raw, "emphasize", where):
        if label not in seen:
            reader.problem(f"{where}.emphasize", f'"{label}" is not the label of a bar')
        evidence.emphasis.append(label)
    limit = raw.get("limit")
    if limit is not None:
        spot = f"{where}.limit"
        if not (isinstance(limit, dict) and is_amount(limit.get("value")) and limit["value"] > 0):
            reader.problem(spot, "must be an object with a label and a value above zero")
            return
        reader.unknown_keys(limit, ("label", "value"), spot)
        evidence.limit_label = reader.text(limit, "label", spot, required=True, limit=80)
        evidence.limit_value = float(limit["value"])
        evidence.limit_text = amount_text(evidence.limit_value, unit)
