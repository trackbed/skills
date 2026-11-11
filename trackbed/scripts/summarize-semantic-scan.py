#!/usr/bin/env python3
"""Summarize a SkillSpector LLM scan against the static scan of the same directories.

An LLM report keeps only the findings the model confirmed or added. Pairing it
with the static report shows what the model added and which static findings it
dropped. The summary is Markdown on stdout; the exit code is 1 when a report
cannot be trusted because the model was not used or one of its calls failed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

Issue = dict[str, Any]
IssueKey = tuple[str, str, Any]

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
MAX_LISTED = 100
MAX_TEXT = 240

# SkillSpector logs a warning and carries on when a model call fails, so these
# loggers are the only sign that a clean-looking report skipped the model.
MODEL_LOG_LINE = re.compile(
    r"^(?:WARNING|ERROR|CRITICAL) \[skillspector\."
    r"(?:model_info|llm_\w+|nodes\.meta_analyzer|nodes\.analyzers\.(?:semantic_\w+|mcp_tool_poisoning))\]"
)

# Provider errors can quote a masked key or an organization ID, and the job
# summary of a public repository is public.
ACCOUNT_TOKEN = re.compile(r"\b(?:sk|org|proj|user)-[A-Za-z0-9_*-]{6,}")


def load_report(path: Path) -> dict[str, Any] | None:
    """Return the parsed report, or None when it is missing or unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def report_issues(report: dict[str, Any] | None) -> list[Issue]:
    issues = (report or {}).get("issues")
    if not isinstance(issues, list):
        return []
    return [issue for issue in issues if isinstance(issue, dict)]


def scanned_files(report: dict[str, Any] | None) -> set[str]:
    components = (report or {}).get("components")
    if not isinstance(components, list):
        return set()
    return {str(component.get("path")) for component in components if isinstance(component, dict)}


def issue_location(issue: Issue) -> tuple[str, Any]:
    location = issue.get("location")
    if not isinstance(location, dict):
        return "", None
    return str(location.get("file") or ""), location.get("start_line")


def issue_key(issue: Issue) -> IssueKey:
    file, line = issue_location(issue)
    return str(issue.get("id") or ""), file, line


def compare(static: list[Issue], semantic: list[Issue]) -> tuple[list[Issue], list[Issue], list[Issue]]:
    """Split findings into kept static, added by the model, and dropped static."""
    static_keys = {issue_key(issue) for issue in static}
    semantic_keys = {issue_key(issue) for issue in semantic}
    kept = [issue for issue in semantic if issue_key(issue) in static_keys]
    added = [issue for issue in semantic if issue_key(issue) not in static_keys]
    dropped = [issue for issue in static if issue_key(issue) not in semantic_keys]
    return kept, added, dropped


def model_log_problems(log_path: Path) -> list[str]:
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [ACCOUNT_TOKEN.sub("[redacted]", line.strip()) for line in lines if MODEL_LOG_LINE.match(line)]


def clean(text: object) -> str:
    """Collapse model-written text to one short line that cannot open an HTML tag."""
    flat = " ".join(str(text or "").split()).replace("<", "&lt;")
    return flat if len(flat) <= MAX_TEXT else flat[: MAX_TEXT - 1] + "…"


def issue_line(stem: str, issue: Issue) -> str:
    file, line = issue_location(issue)
    place = f"{file}:{line}" if line is not None else file
    severity = str(issue.get("severity") or "UNKNOWN").upper()
    text = clean(issue.get("explanation") or issue.get("pattern") or issue.get("finding"))
    return f"- **{severity}** `{issue.get('id') or '?'}` in `{stem}` at `{place}`: {text}"


def sort_key(item: tuple[str, Issue]) -> tuple[int, str, str, int]:
    stem, issue = item
    file, line = issue_location(issue)
    severity = str(issue.get("severity") or "").upper()
    return SEVERITY_ORDER.get(severity, len(SEVERITY_ORDER)), stem, file, line if isinstance(line, int) else 0


def capped(title: str, entries: list[str]) -> list[str]:
    if not entries:
        return []
    lines = ["", f"### {title}", "", *entries[:MAX_LISTED]]
    if len(entries) > MAX_LISTED:
        lines.append(f"- …and {len(entries) - MAX_LISTED} more in the report files.")
    return lines


def added_section(items: list[tuple[str, Issue]]) -> list[str]:
    """One line per finding: the model wrote each explanation, so each one differs."""
    return capped("Added by the model", [issue_line(stem, issue) for stem, issue in sorted(items, key=sort_key)])


def dropped_section(items: list[tuple[str, Issue]]) -> list[str]:
    """One line per rule and file: a static rule repeats the same explanation on every line it flags."""
    groups: dict[tuple[int, str, str, str], list[Issue]] = {}
    for stem, issue in items:
        severity_rank, _, file, _ = sort_key((stem, issue))
        groups.setdefault((severity_rank, stem, str(issue.get("id") or "?"), file), []).append(issue)
    entries = []
    for (_, stem, rule, file), issues in sorted(groups.items()):
        numbers = sorted({line for line in (issue_location(issue)[1] for issue in issues) if isinstance(line, int)})
        place = (
            f"`{file}` {'line' if len(numbers) == 1 else 'lines'} {', '.join(map(str, numbers))}"
            if numbers
            else f"`{file}`"
        )
        severity = str(issues[0].get("severity") or "UNKNOWN").upper()
        text = clean(issues[0].get("explanation") or issues[0].get("pattern") or issues[0].get("finding"))
        entries.append(f"- **{severity}** `{rule}` in `{stem}`, {place}: {text}")
    return capped("Static findings the model dropped", entries)


def summarize(static_dir: Path, semantic_dir: Path, model: str) -> tuple[str, bool]:
    """Return the Markdown summary and whether every report can be trusted."""
    reports = sorted(semantic_dir.glob("*.json")) if semantic_dir.is_dir() else []
    logs = sorted(semantic_dir.glob("*.log")) if semantic_dir.is_dir() else []
    lines = ["## SkillSpector LLM scan", ""]
    problems: list[str] = []
    added_all: list[tuple[str, Issue]] = []
    dropped_all: list[tuple[str, Issue]] = []
    rows: list[str] = []
    unseen_findings = 0

    for report_path in reports:
        stem = report_path.stem
        semantic = load_report(report_path)
        if semantic is None:
            problems.append(f"`{stem}`: the LLM report is not readable JSON.")
            continue
        metadata = semantic.get("metadata")
        if not isinstance(metadata, dict) or not (metadata.get("llm_requested") and metadata.get("llm_available")):
            problems.append(f"`{stem}`: the report says no model was used.")
        static = load_report(static_dir / report_path.name)
        if static is None:
            problems.append(f"`{stem}`: no static report to compare with, so every finding counts as added.")
        # A file excluded from the LLM scan was never shown to the model, so the
        # model did not drop its static findings.
        unseen = scanned_files(static) - scanned_files(semantic)
        static_issues = [issue for issue in report_issues(static) if issue_location(issue)[0] not in unseen]
        unseen_findings += len(report_issues(static)) - len(static_issues)
        kept, added, dropped = compare(static_issues, report_issues(semantic))
        rows.append(f"| `{stem}` | {len(kept)} | {len(added)} | {len(dropped)} |")
        added_all += [(stem, issue) for issue in added]
        dropped_all += [(stem, issue) for issue in dropped]

    for log_path in logs:
        stem = log_path.stem
        if not (semantic_dir / f"{stem}.json").is_file():
            problems.append(f"`{stem}`: the scan wrote no report.")
        problems += [f"`{stem}`: {clean(line)}" for line in model_log_problems(log_path)]

    if not reports and not problems:
        lines.append("No skill directories were scanned.")
        return "\n".join(lines) + "\n", True

    label = f"Model `{model}`" if model else "The model"
    lines.append(f"{label} scanned {len(reports)} {'directory' if len(reports) == 1 else 'directories'}.")
    if rows:
        lines += [
            "",
            "| Directory | Static findings kept | Added by the model | Static findings dropped |",
            "| --- | ---: | ---: | ---: |",
            *rows,
        ]
    if unseen_findings:
        lines += ["", f"Not counted: {unseen_findings} static findings in files left out of the LLM scan."]
    lines += added_section(added_all)
    lines += dropped_section(dropped_all)
    if problems:
        lines += ["", "### Problems", "", "These reports cannot be trusted until the problem is fixed.", ""]
        lines += [f"- {problem}" for problem in problems]
    return "\n".join(lines) + "\n", not problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-dir", type=Path, required=True, help="directory holding the static JSON reports")
    parser.add_argument(
        "--semantic-dir", type=Path, required=True, help="directory holding the LLM JSON reports and logs"
    )
    parser.add_argument("--model", default="", help="model name to show in the summary")
    args = parser.parse_args(argv)

    summary, trusted = summarize(args.static_dir, args.semantic_dir, args.model)
    sys.stdout.write(summary)
    return 0 if trusted else 1


if __name__ == "__main__":
    raise SystemExit(main())
