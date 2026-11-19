"""What a decision document holds, and how its items and options are identified.

Shared by the modules beside it: `decisions_content` reads a content file into this model,
`decisions_choices` matches recorded choices to it, and `decisions_page` renders it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

FORMAT = "trackbed-decisions"
SCHEMA_VERSION = 1
STATUSES = {"open": "Not decided", "decided": "Decided", "discuss": "Needs discussion", "deferred": "Deferred"}
CUSTOM = "custom"
NO_CHANGE = "no-change"
MAX_NOTES_CHARS = 10000


class BuildError(Exception):
    """A file or usage problem: exit code 2."""


@dataclass
class Option:
    id: str
    letter: str
    name: str
    summary: list[str]
    benefits: list[str]
    tradeoffs: list[str]


@dataclass
class Evidence:
    kind: str
    label: str
    caption: str
    source: str
    # image
    data_url: str = ""
    alt: str = ""
    width: int = 0
    height: int = 0
    focus: str = ""
    file_name: str = ""
    # table
    columns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    # excerpt
    text: str = ""
    # chart: each bar is its label, its value, and the value as the reader sees it
    bars: list[tuple[str, float, str]] = field(default_factory=list)
    emphasis: list[str] = field(default_factory=list)
    limit_label: str = ""
    limit_value: float = 0.0
    limit_text: str = ""
    # "source" when the source itself holds this, "added" when it was made for the document
    origin: str = "source"


@dataclass
class Label:
    text: str
    tone: str


@dataclass
class Item:
    id: str
    title: str
    labels: list[Label]
    status: str
    summary: list[str]
    impact: list[str]
    steps: list[str]
    evidence: list[Evidence]
    options: list[Option]
    no_change: str
    no_change_description: str
    recommended: str
    recommendation: str
    reasoning: list[str]
    uncertainty: list[str]
    evidence_limits: list[str]
    success_criteria: list[str]
    details: list[tuple[str, str]]
    source_title: str
    source_location: str
    fingerprint: str = ""


@dataclass
class Group:
    label: str
    title: str
    summary: list[str]
    why: str
    items: list[str]


@dataclass
class Section:
    title: str
    paragraphs: list[str]
    bullets: list[str]


@dataclass
class Document:
    id: str
    title: str
    kicker: str
    summary: list[str]
    generated: str
    producer: str
    noun_one: str
    noun_many: str
    metrics: list[tuple[str, str]]
    start_with: list[tuple[str, str]]
    order: list[Group]
    sources: list[tuple[str, str]]
    sections: list[Section]
    fingerprint: str = ""


@dataclass
class Model:
    document: Document
    items: list[Item]

    def item(self, item_id: str) -> Optional[Item]:
        for item in self.items:
            if item.id == item_id:
                return item
        return None


def squash(value: str) -> str:
    return " ".join(value.split())


def digest(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def fingerprint_item(item: Item) -> str:
    """What a recorded choice was made about: the item's statement and every way to answer it.

    Evidence, the recommendation, and the supporting notes are left out on purpose. A choice
    stays attached while they are refined, and comes back for review when this changes.
    """
    return digest(
        {
            "id": item.id,
            "title": squash(item.title),
            "summary": [squash(line) for line in item.summary],
            "options": [
                {
                    "id": option.id,
                    "name": squash(option.name),
                    "summary": [squash(line) for line in option.summary],
                    "benefits": [squash(line) for line in option.benefits],
                    "tradeoffs": [squash(line) for line in option.tradeoffs],
                }
                for option in item.options
            ],
            "noChange": squash(item.no_change),
        }
    )


def fingerprint_model(model: Model) -> None:
    for item in model.items:
        item.fingerprint = fingerprint_item(item)
    model.document.fingerprint = digest(
        {"document": model.document.id, "items": [[item.id, item.fingerprint] for item in model.items]}
    )


def allowed_choices(item: Item) -> set[str]:
    choices = {option.id for option in item.options} | {CUSTOM}
    if item.no_change:
        choices.add(NO_CHANGE)
    return choices
