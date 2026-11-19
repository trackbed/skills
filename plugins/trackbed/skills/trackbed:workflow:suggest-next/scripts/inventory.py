#!/usr/bin/env python3
"""Read-only inventory for trackbed:workflow:suggest-next.

  inventory.py --plugin-root ROOT [--workdir DIR]

Prints one JSON document with:

- the installed plugin's name, host, and command prefix, from its `.codex-plugin` or `.claude-plugin` manifest;
- every installed skill the user can start, from the frontmatter of `ROOT/skills/*/SKILL.md`;
- the known workflow artifacts present under DIR, matched by path only, with the stage table entry that
  names the skill that wrote each one and the skills that continue from it.

The helper reads only plugin manifests, `SKILL.md` frontmatter, its own stage table, and file names under
DIR. It never reads workspace file contents and never writes. Exit codes: 0 `ok`; 2 `error`.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCHEMA_VERSION = 1
SELF_NAME = "workflow:suggest-next"
STAGE_TABLE = Path(__file__).resolve().parent.parent / "references" / "artifact-stages.json"
MAX_PATHS_PER_ARTIFACT = 10
BLOCK_SCALAR_INDICATORS = {">", ">-", ">+", "|", "|-", "|+"}

JsonDict = Dict[str, Any]


class InventoryError(Exception):
    pass


def emit(payload: JsonDict, code: int) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    return code


def parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        try:
            return json.loads(value)
        except ValueError:
            return value[1:-1]
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        return value[1:-1].replace("''", "'")
    if value in ("true", "false"):
        return value == "true"
    return value


def parse_frontmatter(text: str) -> Optional[JsonDict]:
    """Parse the top-level scalar keys of a SKILL.md frontmatter block; return None without one."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration:
        return None

    data: JsonDict = {}
    index = 1
    while index < end:
        line = lines[index]
        index += 1
        if not line.strip() or line.startswith((" ", "\t", "#", "-")) or ":" not in line:
            continue
        key, _, rest = line.partition(":")
        rest = rest.strip()
        if rest in BLOCK_SCALAR_INDICATORS:
            block: List[str] = []
            while index < end and (not lines[index].strip() or lines[index].startswith((" ", "\t"))):
                block.append(lines[index].strip())
                index += 1
            joiner = "\n" if rest.startswith("|") else " "
            data[key.strip()] = joiner.join(part for part in block if part)
            continue
        data[key.strip()] = parse_scalar(rest) if rest else None
    return data


def read_manifest(root: Path) -> Tuple[str, str, str]:
    """Return (plugin name, host, command prefix); the converter writes `.codex-plugin` only for Codex."""
    for directory, host, prefix in ((".codex-plugin", "codex", "$"), (".claude-plugin", "claude-code", "/")):
        manifest = root / directory / "plugin.json"
        if manifest.is_file():
            try:
                name = json.loads(manifest.read_text(encoding="utf-8")).get("name")
            except (OSError, ValueError) as error:
                raise InventoryError(f"cannot read {manifest}: {error}") from error
            if not isinstance(name, str) or not name:
                raise InventoryError(f"{manifest} has no plugin name")
            return name, host, prefix
    raise InventoryError(f"no .codex-plugin/plugin.json or .claude-plugin/plugin.json under {root}")


def qualified(name: str, plugin: str) -> str:
    """Add the plugin prefix unless the name already carries it, as converted Codex skill names do."""
    return name if name.startswith(f"{plugin}:") else f"{plugin}:{name}"


def load_skills(root: Path, plugin: str, prefix: str) -> Tuple[List[JsonDict], List[JsonDict]]:
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        raise InventoryError(f"no skills directory at {skills_dir}")

    skills: List[JsonDict] = []
    skipped: List[JsonDict] = []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        folder = path.parent.name
        try:
            frontmatter = parse_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            skipped.append({"folder": folder, "reason": f"unreadable: {error}"})
            continue
        if not frontmatter or not isinstance(frontmatter.get("name"), str):
            skipped.append({"folder": folder, "reason": "no frontmatter name"})
            continue
        name = qualified(frontmatter["name"], plugin)
        user_invocable = frontmatter.get("user-invocable")
        if name == qualified(SELF_NAME, plugin):
            skipped.append({"name": name, "reason": "this skill"})
            continue
        # Shipped skills declare user-invocable explicitly; Codex agent skills carry only name and description.
        if user_invocable is None:
            skipped.append({"name": name, "reason": "no user-invocable key (agent, not a skill)"})
            continue
        if user_invocable is not True:
            skipped.append({"name": name, "reason": "background skill the user cannot start"})
            continue
        skills.append(
            {
                "name": name,
                "command": f"{prefix}{name}",
                "invocation": "user" if frontmatter.get("disable-model-invocation") is True else "user, auto",
                "argument_hint": frontmatter.get("argument-hint") or None,
                "description": frontmatter.get("description") or "",
            }
        )
    return skills, skipped


def load_stage_table() -> List[JsonDict]:
    try:
        table = json.loads(STAGE_TABLE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise InventoryError(f"cannot read stage table {STAGE_TABLE}: {error}") from error
    entries = table.get("artifacts")
    if not isinstance(entries, list):
        raise InventoryError(f"stage table {STAGE_TABLE} has no artifacts list")
    return entries


def modified(path: Path) -> str:
    stamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return stamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def match_pattern(workdir: Path, pattern: str) -> List[Path]:
    want_dir = pattern.endswith("/")
    clean = pattern.rstrip("/")
    candidates = sorted(workdir.glob(clean)) if any(char in clean for char in "*?[") else [workdir / clean]
    return [candidate for candidate in candidates if (candidate.is_dir() if want_dir else candidate.is_file())]


def rank_after_anchors(found: List[JsonDict], rank_after: Dict[str, List[str]]) -> List[JsonDict]:
    """Move each artifact whose `rank_after` entry also matched to just after the last of those entries."""
    present = {artifact["id"] for artifact in found}
    deferred = [artifact for artifact in found if present.intersection(rank_after.get(artifact["id"], []))]
    ordered = [artifact for artifact in found if artifact not in deferred]
    for artifact in deferred:
        anchors = rank_after[artifact["id"]]
        position = max(index for index, other in enumerate(ordered) if other["id"] in anchors)
        ordered.insert(position + 1, artifact)
    return ordered


def find_artifacts(workdir: Path, plugin: str, prefix: str, installed: Set[str]) -> List[JsonDict]:
    found: List[JsonDict] = []
    rank_after: Dict[str, List[str]] = {}
    for entry in load_stage_table():
        rank_after[entry["id"]] = entry.get("rank_after", [])
        matches: List[Path] = []
        for pattern in entry["paths"]:
            for match in match_pattern(workdir, pattern):
                if match not in matches:
                    matches.append(match)
        if not matches:
            continue
        matches.sort(key=lambda match: match.stat().st_mtime, reverse=True)
        next_steps = []
        for step in entry["next"]:
            name = qualified(step["skill"], plugin)
            next_steps.append(
                {
                    "skill": name,
                    "command": f"{prefix}{name}" + (f" {step['args']}" if step.get("args") else ""),
                    "when": step["when"],
                    "installed": name in installed,
                }
            )
        found.append(
            {
                "id": entry["id"],
                "stage": entry["stage"],
                "produced_by": qualified(entry["produced_by"], plugin),
                "paths": [
                    {"path": match.relative_to(workdir).as_posix(), "modified": modified(match)}
                    for match in matches[:MAX_PATHS_PER_ARTIFACT]
                ],
                "more_paths": max(0, len(matches) - MAX_PATHS_PER_ARTIFACT),
                "next": next_steps,
            }
        )
    found.sort(key=lambda artifact: artifact["paths"][0]["modified"], reverse=True)
    return rank_after_anchors(found, rank_after)


def build(plugin_root: Path, workdir: Path) -> JsonDict:
    if not workdir.is_dir():
        raise InventoryError(f"working directory {workdir} does not exist")
    plugin, host, prefix = read_manifest(plugin_root)
    skills, skipped = load_skills(plugin_root, plugin, prefix)
    installed = {skill["name"] for skill in skills}
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "plugin": plugin,
        "host": host,
        "command_prefix": prefix,
        "workdir": str(workdir),
        "skills": skills,
        "skipped": skipped,
        "artifacts": find_artifacts(workdir, plugin, prefix, installed),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only skill and artifact inventory for suggest-next.")
    parser.add_argument("--plugin-root", required=True, help="installed plugin root that holds skills/")
    parser.add_argument("--workdir", default=".", help="directory to check for workflow artifacts")
    args = parser.parse_args(argv)
    try:
        payload = build(Path(args.plugin_root).resolve(), Path(args.workdir).resolve())
    except (InventoryError, OSError) as error:
        return emit({"schema_version": SCHEMA_VERSION, "status": "error", "message": str(error)}, 2)
    except Exception as error:  # Fail closed with one JSON document instead of a traceback.
        message = f"unexpected helper failure: {error!r}"
        return emit({"schema_version": SCHEMA_VERSION, "status": "error", "message": message}, 2)
    return emit(payload, 0)


if __name__ == "__main__":
    sys.exit(main())
