from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..io import rel
from ..strings import is_empty_value
from .marker_manifest import parse_sources_manifest
from .types import CheckResult, LintContext

ALLOWED_SOURCE_USAGES = {"copied", "inspiration"}
COPIED_SOURCE_REVISION_FIELDS = (
    "upstream_commit",
    "baseline_commit",
    "upstream_revision",
    "upstream_release",
    "version",
)
COMMIT_FIELDS = {"baseline_commit", "upstream_commit"}
MOVING_REVISION_VALUES = {"head", "latest", "main", "master", "trunk"}


def _resolved_notice_path(notice_root: Path, raw_notice: str, root_label: str) -> tuple[Path | None, str | None]:
    notice_value = raw_notice.split("#", 1)[0].strip()
    if not notice_value:
        return None, f"must name a license or notice file in the {root_label}"

    notice_path = Path(notice_value)
    if notice_path.is_absolute():
        return None, f"must be relative to the {root_label}"

    resolved_root = notice_root.resolve()
    resolved = (notice_root / notice_path).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        return None, f"must stay within the {root_label}"
    return resolved, None


def _check_copied_source(
    result: CheckResult,
    root: Path,
    manifest_path: Path,
    entry: dict[str, Any],
    entry_id: str,
    notice_root: Path,
    root_label: str,
) -> None:
    manifest_relative = rel(manifest_path, root)
    for field in ("license", "notice", "upstream_path"):
        if is_empty_value(entry.get(field)):
            result.failures.append(
                f"source provenance: {manifest_relative} copied entry {entry_id!r} is missing non-empty {field!r}"
            )

    revisions = [
        (field, str(entry.get(field)).strip())
        for field in COPIED_SOURCE_REVISION_FIELDS
        if not is_empty_value(entry.get(field))
    ]
    if not revisions:
        fields = ", ".join(repr(field) for field in COPIED_SOURCE_REVISION_FIELDS)
        result.failures.append(
            f"source provenance: {manifest_relative} copied entry {entry_id!r} "
            f"is missing an immutable upstream revision; set one of {fields}"
        )
    for field, value in revisions:
        if value.lower() in MOVING_REVISION_VALUES:
            result.failures.append(
                f"source provenance: {manifest_relative} copied entry {entry_id!r} "
                f"{field!r} must be immutable, not {value!r}"
            )
        if field in COMMIT_FIELDS and re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", value) is None:
            result.failures.append(
                f"source provenance: {manifest_relative} copied entry {entry_id!r} "
                f"{field!r} must be a full 40- or 64-character commit hash"
            )

    notice = entry.get("notice")
    if is_empty_value(notice):
        return

    notice_path, error = _resolved_notice_path(notice_root, str(notice), root_label)
    if error:
        result.failures.append(f"source provenance: {manifest_relative} copied entry {entry_id!r} notice {error}")
        return
    if notice_path is None or not notice_path.is_file():
        result.failures.append(
            f"source provenance: {manifest_relative} copied entry {entry_id!r} notice file does not exist: {notice}"
        )


def check_source_provenance(context: LintContext) -> CheckResult:
    result = CheckResult()
    config = context.registry.get("source_provenance")
    if not config:
        return result

    manifest_glob = config.get("manifest_glob", "trackbed/skills/*/references/sources.yaml")
    snapshot_globs = config.get(
        "forbidden_snapshot_globs",
        [
            "trackbed/skills/*/references/sources-snapshot",
            ".agents/skills/*/references/sources-snapshot",
        ],
    )

    for pattern in snapshot_globs:
        for path in sorted(context.root.glob(pattern)):
            result.failures.append(
                "source provenance: committed upstream source bodies are forbidden; "
                f"remove {rel(path, context.root)} and keep only provenance/license "
                "metadata, review date, hash, and original notes"
            )

    # A skill manifest lives at <skill>/references/sources.yaml and names
    # notices relative to the skill directory. A shared manifest sits beside
    # plugin-level files that no single skill owns, such as
    # scripts/dev-server/, and names notices relative to its own directory.
    manifests = [(path, path.parent.parent, "skill directory") for path in sorted(context.root.glob(manifest_glob))]
    for pattern in config.get("shared_manifest_globs", []):
        manifests.extend((path, path.parent, "manifest directory") for path in sorted(context.root.glob(pattern)))

    for manifest_path, notice_root, root_label in manifests:
        manifest_relative = rel(manifest_path, context.root)
        for index, entry in enumerate(parse_sources_manifest(manifest_path), start=1):
            entry_id = str(entry.get("id", f"entry-{index}"))
            usage = entry.get("usage")
            if is_empty_value(usage):
                result.failures.append(
                    f"source provenance: {manifest_relative} entry {entry_id!r} is missing non-empty 'usage'"
                )
                continue
            if usage not in ALLOWED_SOURCE_USAGES:
                result.failures.append(
                    f"source provenance: {manifest_relative} entry "
                    f"{entry_id!r} has invalid usage {usage!r}; expected "
                    "'inspiration' or 'copied'"
                )
                continue
            if usage == "copied":
                _check_copied_source(result, context.root, manifest_path, entry, entry_id, notice_root, root_label)

    return result
