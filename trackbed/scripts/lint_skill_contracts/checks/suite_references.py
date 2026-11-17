from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..io import read_text, rel
from .types import CheckResult

# Accept both shell paths and Python's root / "skills" / "domain:name" spelling.
PATH_JOIN = re.compile(r"""["']\s*/\s*["']""")
SKILL_REFERENCE = re.compile(r"""\bskills/([a-z][a-z0-9-]*(?::[a-z0-9-]+)*)(?=[/"'\s])""")


def referenced_skills(text: str, discovered: set[str]) -> set[str]:
    names = set(SKILL_REFERENCE.findall(PATH_JOIN.sub("/", text)))
    return {skill for skill in discovered if Path(skill).parent.name in names}


def check_suite_references(root: Path, inventory: dict[str, Any], discovered: set[str]) -> CheckResult:
    result = CheckResult()
    suites = sorted(set(root.glob("trackbed/tests/**/*.bats")) | set(root.glob("trackbed/tests/python/test_*.py")))
    references = {rel(path, root): referenced_skills(read_text(path), discovered) for path in suites}
    exceptions: dict[tuple[str, str], str] = {}
    entries = inventory.get("skill_contract_exceptions", [])
    if not isinstance(entries, list):
        result.failures.append("mechanical: skill_contract_exceptions must be an array")
        entries = []
    for entry in entries:
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(field), str) and entry[field].strip() for field in ("suite", "skill", "reason")
        ):
            result.failures.append("mechanical: skill contract exception requires suite, skill, and a non-empty reason")
            continue
        kind = entry.get("kind")
        if kind not in ("incidental", "indirect"):
            result.failures.append("mechanical: skill contract exception kind must be incidental or indirect")
            continue
        pair = (entry["suite"], entry["skill"])
        if pair in exceptions:
            result.failures.append(f"mechanical: duplicate skill contract exception: {pair[0]} -> {pair[1]}")
        exceptions[pair] = kind
        if pair[0] not in references or pair[1] not in discovered:
            result.failures.append(f"mechanical: unknown suite or skill in contract exception: {pair[0]} -> {pair[1]}")

    for entry in inventory["skill_contracts"]:
        if not isinstance(entry, dict) or entry.get("kind") not in ("guidance", "executable"):
            continue
        suite = entry.get("suite")
        skills = entry.get("skills")
        if not isinstance(suite, str) or not isinstance(skills, list):
            continue
        for skill in skills:
            if not isinstance(skill, str):
                continue
            pair = (suite, skill)
            if suite in references and skill not in references[suite] and pair not in exceptions:
                result.failures.append(f"mechanical: stale skill contract mapping: {suite} -> {skill}")

    # Registry and evaluation mappings do not claim direct suite coverage, but may
    # already account for a candidate (for example an executable evaluation harness).
    registered = {
        (entry["suite"], skill)
        for entry in inventory["skill_contracts"]
        if isinstance(entry, dict) and isinstance(entry.get("suite"), str) and isinstance(entry.get("skills"), list)
        for skill in entry["skills"]
        if isinstance(skill, str)
    }
    for (suite, skill), kind in exceptions.items():
        if kind == "indirect" and suite in references:
            references[suite].add(skill)

    for suite, skills in references.items():
        for skill in sorted(skills):
            if (suite, skill) not in registered and exceptions.get((suite, skill)) != "incidental":
                result.failures.append(f"mechanical: missing skill contract mapping: {suite} -> {skill}")
    return result
