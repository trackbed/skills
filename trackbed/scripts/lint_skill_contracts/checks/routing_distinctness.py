"""Compare skill descriptions so auto-invocation routing stays distinguishable.

The comparison is lexical: descriptions are reduced to token sets and scored with
Jaccard overlap. Two descriptions that express the same triggers in different
vocabulary score low and pass, so this check narrows the routing-collision gap
rather than closing it. Pairs above the failure threshold must either be
differentiated or carry a recorded positive routing boundary in the registry,
unless `fail_population` exempts them because not both skills are auto-invocable.
A recorded boundary whose pair has since dropped below the warn threshold is
reported as removable.
"""

from __future__ import annotations

import re
from itertools import combinations
from typing import Any

from ..frontmatter import frontmatter_boolean_value, frontmatter_string_value, parse_frontmatter
from ..io import read_text, rel, skill_paths
from ..naming import qualified_name
from .types import CheckResult, LintContext

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
FAIL_POPULATIONS = ("auto_invocable", "all")


def description_tokens(description: str, name: str, stopwords: set[str]) -> set[str]:
    name_tokens = set(TOKEN_PATTERN.findall(name.lower()))
    return {
        token
        for token in TOKEN_PATTERN.findall(description.lower())
        if token not in stopwords and token not in name_tokens
    }


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def similarity_threshold(config: dict[str, Any], key: str, default: float, result: CheckResult) -> float:
    value = config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
        result.failures.append(f"routing distinctness: {key} must be a number between 0 and 1")
        return default
    return float(value)


def recorded_boundary_pairs(
    config: dict[str, Any],
    discovered: set[str],
    result: CheckResult,
) -> set[frozenset[str]]:
    entries = config.get("recorded_boundaries", [])
    pairs: set[frozenset[str]] = set()
    if not isinstance(entries, list):
        result.failures.append("routing distinctness: recorded_boundaries must be an array")
        return pairs

    for index, entry in enumerate(entries, start=1):
        label = f"routing distinctness: recorded_boundaries entry {index}"
        if not isinstance(entry, dict):
            result.failures.append(f"{label} must be an object")
            continue
        skills = entry.get("skills")
        boundary = entry.get("boundary")
        if (
            not isinstance(skills, list)
            or len(skills) < 2
            or not all(isinstance(path, str) and path for path in skills)
        ):
            result.failures.append(f"{label} requires at least two skill paths")
            continue
        if not isinstance(boundary, str) or not boundary.strip():
            result.failures.append(
                f"{label} requires a non-empty boundary stating a positive routing rule for {', '.join(sorted(skills))}"
            )
            continue
        for skill in sorted(set(skills) - discovered):
            result.failures.append(f"{label} skill does not exist: {skill}; remove or fix the entry")
        pairs.update(frozenset(pair) for pair in combinations(sorted(set(skills)), 2))
    return pairs


def check_routing_distinctness(context: LintContext) -> CheckResult:
    result = CheckResult()
    config = context.registry.get("routing_distinctness")
    if config is None:
        return result
    if not isinstance(config, dict):
        result.failures.append("routing distinctness: registry entry must be an object")
        return result
    report_limit = config.get("pair_report_limit", 20)
    if type(report_limit) is not int or report_limit < 0:
        result.failures.append("routing distinctness: pair_report_limit must be a non-negative integer")
    stopwords_raw = config.get("stopwords", [])
    if not isinstance(stopwords_raw, list) or not all(isinstance(word, str) for word in stopwords_raw):
        result.failures.append("routing distinctness: stopwords must be an array of strings")
    if not isinstance(config.get("skill_glob", "*"), str):
        result.failures.append("routing distinctness: skill_glob must be a string")
    if result.failures:
        return result

    pattern = config.get("skill_glob", "trackbed/skills/*/SKILL.md")
    warn_similarity = similarity_threshold(config, "warn_similarity", 1.0, result)
    fail_similarity = similarity_threshold(config, "fail_similarity", 1.0, result)
    if fail_similarity < warn_similarity:
        result.failures.append("routing distinctness: fail_similarity must be at or above warn_similarity")
        fail_similarity = warn_similarity
    stopwords = {word.lower() for word in stopwords_raw}
    fail_population = config.get("fail_population", "auto_invocable")
    if fail_population not in FAIL_POPULATIONS:
        result.failures.append(f"routing distinctness: fail_population must be one of {', '.join(FAIL_POPULATIONS)}")
        fail_population = "auto_invocable"

    skills: list[tuple[str, set[str], bool]] = []
    for path in skill_paths(context.root, pattern):
        relative = rel(path, context.root)
        text = read_text(path)
        frontmatter = parse_frontmatter(text)
        if frontmatter is None:
            continue
        description = frontmatter_string_value(text, "description")
        if not description:
            continue
        name = qualified_name(frontmatter_string_value(text, "name") or path.parent.name)
        auto_invocable = not frontmatter_boolean_value(text, "disable-model-invocation")
        skills.append((relative, description_tokens(description, name, stopwords), auto_invocable))

    recorded = recorded_boundary_pairs(config, {relative for relative, _tokens, _auto in skills}, result)

    failures: list[tuple[float, str, str]] = []
    burndown: list[tuple[float, str, str, bool]] = []
    removable: list[tuple[float, str, str]] = []
    for (left, left_tokens, left_auto), (right, right_tokens, right_auto) in combinations(skills, 2):
        score = jaccard(left_tokens, right_tokens)
        if frozenset((left, right)) in recorded:
            if score < warn_similarity:
                removable.append((score, left, right))
            continue
        if score < warn_similarity:
            continue
        in_fail_population = fail_population == "all" or (left_auto and right_auto)
        if score >= fail_similarity and in_fail_population:
            failures.append((score, left, right))
        else:
            burndown.append((score, left, right, score >= fail_similarity))

    for score, left, right in sorted(failures, key=lambda entry: (-entry[0], entry[1], entry[2])):
        result.failures.append(
            f"routing distinctness: {left} and {right} descriptions score {score:.2f} "
            f"(fail at {fail_similarity:.2f}); differentiate the descriptions or add a "
            "routing_distinctness.recorded_boundaries entry with a positive one-clause routing rule"
        )
    for score, left, right, exempt in sorted(burndown, key=lambda entry: (-entry[0], entry[1], entry[2]))[
        :report_limit
    ]:
        context_note = (
            f"at or above the {fail_similarity:.2f} failure threshold but exempt: only pairs with both "
            "skills auto-invocable fail, and at least one of these is user-invoked"
            if exempt
            else f"warn at {warn_similarity:.2f}, fail at {fail_similarity:.2f}"
        )
        result.warnings.append(
            f"routing distinctness: nearest-pair burndown: {left} and {right} score {score:.2f} ({context_note})"
        )
    for score, left, right in sorted(removable, key=lambda entry: (-entry[0], entry[1], entry[2])):
        result.warnings.append(
            f"routing distinctness: recorded boundary can be removed: {left} and {right} "
            f"score {score:.2f} (warn at {warn_similarity:.2f})"
        )
    return result
