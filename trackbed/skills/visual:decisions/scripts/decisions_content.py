"""Read a decision document's content file into the model, collecting every problem in one pass.

The format is described for authors in `references/content-format.md`.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any, Optional

from decisions_evidence import read_evidence
from decisions_model import (
    CUSTOM,
    NO_CHANGE,
    SCHEMA_VERSION,
    Document,
    Group,
    Item,
    Label,
    Model,
    Option,
    Section,
)

TONES = ("critical", "high", "medium", "low", "good", "neutral")
MAX_ITEMS = 200
MAX_OPTIONS = 6

# The builder rejects a field it does not know, so a typo is reported instead of dropped.
DOCUMENT_FIELDS = tuple(
    "id title kicker summary generated producer itemNoun metrics startWith order sources sections".split()
)
ITEM_FIELDS = tuple(
    "id title labels status summary impact steps evidence options noChange recommendation "
    "uncertainty evidenceLimits successCriteria details source".split()
)

DOCUMENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
ITEM_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
OPTION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Reader:
    """Reads the content file into the model and collects every problem in one pass."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.problems: list[str] = []
        self.image_count = 0

    def problem(self, where: str, message: str) -> None:
        self.problems.append(f"{where}: {message}")

    def text(self, raw: dict[str, Any], key: str, where: str, *, required: bool = False, limit: int = 4000) -> str:
        value = raw.get(key)
        if value is None:
            if required:
                self.problem(f"{where}.{key}", "is required")
            return ""
        if not isinstance(value, str) or (required and not value.strip()):
            self.problem(f"{where}.{key}", "must be a non-empty string" if required else "must be a string")
            return ""
        if len(value) > limit:
            self.problem(f"{where}.{key}", f"is longer than {limit} characters")
        return value.strip()

    def lines(self, raw: dict[str, Any], key: str, where: str, *, required: bool = False) -> list[str]:
        """A string, or a list of strings: paragraphs or list entries."""
        value = raw.get(key)
        if value is None:
            if required:
                self.problem(f"{where}.{key}", "is required")
            return []
        values = [value] if isinstance(value, str) else value
        if not isinstance(values, list) or not all(isinstance(entry, str) for entry in values):
            self.problem(f"{where}.{key}", "must be a string or a list of strings")
            return []
        cleaned = [entry.strip() for entry in values if entry.strip()]
        if required and not cleaned:
            self.problem(f"{where}.{key}", "must not be empty")
        return cleaned

    def entries(self, raw: dict[str, Any], key: str, where: str) -> list[Any]:
        value = raw.get(key)
        if value is None:
            return []
        if not isinstance(value, list):
            self.problem(f"{where}.{key}", "must be a list")
            return []
        return value

    def unknown_keys(self, raw: dict[str, Any], allowed: tuple[str, ...], where: str) -> None:
        for key in raw:
            if key not in allowed:
                self.problem(f"{where}.{key}", f"is not a field this format has; the fields are {', '.join(allowed)}")

    # ----- document -----

    def read(self, raw: Any) -> Optional[Model]:
        if not isinstance(raw, dict):
            self.problem("content", "must be a JSON object with schemaVersion, document, and items")
            return None
        self.unknown_keys(raw, ("schemaVersion", "document", "items"), "content")
        if raw.get("schemaVersion") != SCHEMA_VERSION:
            self.problem("schemaVersion", f"must be {SCHEMA_VERSION}")
        raw_items = raw.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            self.problem("items", "must be a non-empty list")
            raw_items = []
        if len(raw_items) > MAX_ITEMS:
            self.problem("items", f"holds more than {MAX_ITEMS} entries")
        items: list[Item] = []
        seen: set[str] = set()
        for index, raw_item in enumerate(raw_items):
            item = self.read_item(raw_item, f"items[{index}]")
            if item is None:
                continue
            if item.id in seen:
                self.problem(f"items[{index}].id", f'"{item.id}" is used more than once')
            seen.add(item.id)
            items.append(item)
        document = self.read_document(raw.get("document"), seen)
        if document is None:
            return None
        return Model(document, items)

    def read_document(self, raw: Any, item_ids: set[str]) -> Optional[Document]:
        where = "document"
        if not isinstance(raw, dict):
            self.problem(where, "is required and must be an object")
            return None
        self.unknown_keys(raw, DOCUMENT_FIELDS, where)
        document_id = self.text(raw, "id", where, required=True, limit=64)
        if document_id and not DOCUMENT_ID_RE.match(document_id):
            self.problem(
                f"{where}.id",
                "must be 3 to 64 lowercase letters, digits, and hyphens; it identifies this document across rebuilds",
            )
        generated = self.text(raw, "generated", where, limit=10) or dt.date.today().isoformat()
        if not DATE_RE.match(generated):
            self.problem(f"{where}.generated", "must be a date written as YYYY-MM-DD")
        noun = raw.get("itemNoun", ["decision", "decisions"])
        if not (isinstance(noun, list) and len(noun) == 2 and all(isinstance(n, str) and n.strip() for n in noun)):
            self.problem(
                f"{where}.itemNoun",
                'must be the singular and plural of what an item is, such as ["finding", "findings"]',
            )
            noun = ["decision", "decisions"]

        metrics: list[tuple[str, str]] = []
        for index, entry in enumerate(self.entries(raw, "metrics", where)):
            spot = f"{where}.metrics[{index}]"
            if not isinstance(entry, dict):
                self.problem(spot, "must be an object with value and label")
                continue
            self.unknown_keys(entry, ("value", "label"), spot)
            metrics.append(
                (
                    self.text(entry, "value", spot, required=True, limit=12),
                    self.text(entry, "label", spot, required=True, limit=60),
                )
            )
        if len(metrics) > 4:
            self.problem(f"{where}.metrics", "holds more than four entries")

        start_with: list[tuple[str, str]] = []
        for index, entry in enumerate(self.entries(raw, "startWith", where)):
            spot = f"{where}.startWith[{index}]"
            if isinstance(entry, str):
                entry = {"item": entry}
            if not isinstance(entry, dict):
                self.problem(spot, "must be an item id, or an object with item and reason")
                continue
            self.unknown_keys(entry, ("item", "reason"), spot)
            item_id = self.text(entry, "item", spot, required=True, limit=64)
            if item_id and item_id not in item_ids:
                self.problem(f"{spot}.item", f'"{item_id}" is not the id of an item')
            start_with.append((item_id, self.text(entry, "reason", spot, limit=400)))
        if len(start_with) > 3:
            self.problem(f"{where}.startWith", "holds more than three entries")

        order: list[Group] = []
        placed: set[str] = set()
        for index, entry in enumerate(self.entries(raw, "order", where)):
            spot = f"{where}.order[{index}]"
            if not isinstance(entry, dict):
                self.problem(spot, "must be an object with title and items")
                continue
            self.unknown_keys(entry, ("label", "title", "summary", "why", "items"), spot)
            members = entry.get("items")
            if not (isinstance(members, list) and members and all(isinstance(member, str) for member in members)):
                self.problem(f"{spot}.items", "must be a non-empty list of item ids")
                members = []
            for member in members:
                if member not in item_ids:
                    self.problem(f"{spot}.items", f'"{member}" is not the id of an item')
                elif member in placed:
                    self.problem(f"{spot}.items", f'"{member}" is placed in more than one group')
                placed.add(member)
            order.append(
                Group(
                    self.text(entry, "label", spot, limit=40),
                    self.text(entry, "title", spot, required=True, limit=160),
                    self.lines(entry, "summary", spot),
                    self.text(entry, "why", spot, limit=600),
                    list(members),
                )
            )

        sources: list[tuple[str, str]] = []
        for index, entry in enumerate(self.entries(raw, "sources", where)):
            spot = f"{where}.sources[{index}]"
            if not isinstance(entry, dict):
                self.problem(spot, "must be an object with label and detail")
                continue
            self.unknown_keys(entry, ("label", "detail"), spot)
            sources.append(
                (self.text(entry, "label", spot, required=True, limit=300), self.text(entry, "detail", spot, limit=600))
            )

        sections: list[Section] = []
        for index, entry in enumerate(self.entries(raw, "sections", where)):
            spot = f"{where}.sections[{index}]"
            if not isinstance(entry, dict):
                self.problem(spot, "must be an object with title and paragraphs or bullets")
                continue
            self.unknown_keys(entry, ("title", "paragraphs", "bullets"), spot)
            section = Section(
                self.text(entry, "title", spot, required=True, limit=160),
                self.lines(entry, "paragraphs", spot),
                self.lines(entry, "bullets", spot),
            )
            if not section.paragraphs and not section.bullets:
                self.problem(spot, "needs paragraphs or bullets")
            sections.append(section)

        return Document(
            id=document_id,
            title=self.text(raw, "title", where, required=True, limit=200),
            kicker=self.text(raw, "kicker", where, limit=120),
            summary=self.lines(raw, "summary", where, required=True),
            generated=generated,
            producer=self.text(raw, "producer", where, limit=200),
            noun_one=str(noun[0]).strip(),
            noun_many=str(noun[1]).strip(),
            metrics=metrics,
            start_with=start_with,
            order=order,
            sources=sources,
            sections=sections,
        )

    # ----- items -----

    def read_item(self, raw: Any, where: str) -> Optional[Item]:
        if not isinstance(raw, dict):
            self.problem(where, "must be an object")
            return None
        self.unknown_keys(raw, ITEM_FIELDS, where)
        item_id = self.text(raw, "id", where, required=True, limit=64)
        if item_id and not ITEM_ID_RE.match(item_id):
            self.problem(
                f"{where}.id", "must be letters, digits, dots, hyphens, or underscores; keep the source's own id"
            )
        if item_id:
            where = f"{where} ({item_id})"

        labels: list[Label] = []
        for index, entry in enumerate(self.entries(raw, "labels", where)):
            spot = f"{where}.labels[{index}]"
            if isinstance(entry, str):
                entry = {"text": entry}
            if not isinstance(entry, dict):
                self.problem(spot, "must be a string, or an object with text and tone")
                continue
            self.unknown_keys(entry, ("text", "tone"), spot)
            tone = entry.get("tone", "neutral")
            if tone not in TONES:
                self.problem(f"{spot}.tone", f"must be one of {', '.join(TONES)}")
                tone = "neutral"
            labels.append(Label(self.text(entry, "text", spot, required=True, limit=40), tone))
        if len(labels) > 4:
            self.problem(f"{where}.labels", "holds more than four entries")

        options: list[Option] = []
        option_ids: set[str] = set()
        raw_options = self.entries(raw, "options", where)
        if len(raw_options) > MAX_OPTIONS:
            self.problem(f"{where}.options", f"holds more than {MAX_OPTIONS} entries")
        for index, entry in enumerate(raw_options):
            spot = f"{where}.options[{index}]"
            if not isinstance(entry, dict):
                self.problem(spot, "must be an object")
                continue
            self.unknown_keys(entry, ("id", "name", "summary", "benefits", "tradeoffs"), spot)
            option_id = self.text(entry, "id", spot, required=True, limit=64)
            if option_id and (not OPTION_ID_RE.match(option_id) or option_id in (CUSTOM, NO_CHANGE)):
                self.problem(
                    f"{spot}.id",
                    f'must be lowercase letters, digits, and hyphens, and not "{CUSTOM}" or "{NO_CHANGE}"; '
                    "name the approach, not its position",
                )
            if option_id in option_ids:
                self.problem(f"{spot}.id", f'"{option_id}" is used more than once in this item')
            option_ids.add(option_id)
            option = Option(
                id=option_id,
                letter=chr(ord("A") + index),
                name=self.text(entry, "name", spot, required=True, limit=200),
                summary=self.lines(entry, "summary", spot),
                benefits=self.lines(entry, "benefits", spot),
                tradeoffs=self.lines(entry, "tradeoffs", spot),
            )
            if not option.summary and not option.benefits:
                self.problem(spot, "needs a summary or benefits, so the reader knows what choosing it gives them")
            options.append(option)

        no_change, no_change_description = "No change", "Leave things as they are."
        raw_no_change = raw.get("noChange", True)
        if raw_no_change is False:
            no_change, no_change_description = "", ""
        elif isinstance(raw_no_change, dict):
            spot = f"{where}.noChange"
            self.unknown_keys(raw_no_change, ("label", "description"), spot)
            no_change = self.text(raw_no_change, "label", spot, limit=80) or no_change
            no_change_description = self.text(raw_no_change, "description", spot, limit=300) or no_change_description
        elif raw_no_change is not True:
            self.problem(f"{where}.noChange", "must be true, false, or an object with label and description")

        recommended, recommendation, reasoning = "", "", []
        raw_recommendation = raw.get("recommendation")
        if not isinstance(raw_recommendation, dict):
            self.problem(
                f"{where}.recommendation",
                "is required: an object with option, summary, and reasoning. Set option to null when no option "
                "can be recommended, and say why in reasoning",
            )
        else:
            spot = f"{where}.recommendation"
            self.unknown_keys(raw_recommendation, ("option", "summary", "reasoning"), spot)
            choice = raw_recommendation.get("option")
            if choice is None:
                recommended = ""
            elif isinstance(choice, str) and (choice in option_ids or (choice == NO_CHANGE and no_change)):
                recommended = choice
            else:
                self.problem(
                    f"{spot}.option",
                    f'must be the id of one of this item\'s options, "{NO_CHANGE}" when that choice is offered, or null',
                )
            recommendation = self.text(raw_recommendation, "summary", spot, required=True, limit=600)
            reasoning = self.lines(raw_recommendation, "reasoning", spot, required=True)

        details: list[tuple[str, str]] = []
        for index, entry in enumerate(self.entries(raw, "details", where)):
            spot = f"{where}.details[{index}]"
            if not isinstance(entry, dict):
                self.problem(spot, "must be an object with label and value")
                continue
            self.unknown_keys(entry, ("label", "value"), spot)
            details.append(
                (
                    self.text(entry, "label", spot, required=True, limit=60),
                    self.text(entry, "value", spot, required=True, limit=300),
                )
            )

        source_title, source_location = "", ""
        raw_source = raw.get("source")
        if raw_source is not None:
            spot = f"{where}.source"
            if not isinstance(raw_source, dict):
                self.problem(spot, "must be an object with title and location")
            else:
                self.unknown_keys(raw_source, ("title", "location"), spot)
                source_title = self.text(raw_source, "title", spot, limit=300)
                source_location = self.text(raw_source, "location", spot, limit=400)

        evidence = [
            found
            for index, entry in enumerate(self.entries(raw, "evidence", where))
            if (found := read_evidence(self, entry, f"{where}.evidence[{index}]")) is not None
        ]

        return Item(
            id=item_id,
            title=self.text(raw, "title", where, required=True, limit=240),
            labels=labels,
            status=self.text(raw, "status", where, limit=200),
            summary=self.lines(raw, "summary", where, required=True),
            impact=self.lines(raw, "impact", where),
            steps=self.lines(raw, "steps", where),
            evidence=evidence,
            options=options,
            no_change=no_change,
            no_change_description=no_change_description,
            recommended=recommended,
            recommendation=recommendation,
            reasoning=reasoning,
            uncertainty=self.lines(raw, "uncertainty", where),
            evidence_limits=self.lines(raw, "evidenceLimits", where),
            success_criteria=self.lines(raw, "successCriteria", where),
            details=details,
            source_title=source_title,
            source_location=source_location,
        )
