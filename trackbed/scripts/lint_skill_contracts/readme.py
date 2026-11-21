from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .frontmatter import (
    expected_arguments,
    expected_invocation,
    frontmatter_boolean_value,
    frontmatter_string_value,
    parse_frontmatter,
    parse_frontmatter_bool,
)
from .io import read_text, rel, resolve
from .markdown import (
    escape_markdown_table_cell,
    normalize_markdown_cell,
    split_markdown_table_row,
)
from .naming import PLUGIN_NAMESPACE, qualified_name
from .readme_summaries import apply_readme_summaries, readme_summaries_configured
from .registry_types import Registry
from .schema import load_contract_schema, skill_frontmatter_field_by_loader_property
from .strings import is_empty_value, shorten


@dataclass(frozen=True)
class SkillReference:
    name: str
    display_name: str
    invocation: str
    arguments: str
    description: str
    source_name: str = ""


@dataclass(frozen=True)
class AgentReference:
    name: str
    description: str
    source_name: str = ""


@dataclass(frozen=True)
class HookReference:
    name: str
    event: str
    description: str
    path: str = ""


def skill_reference_from_frontmatter(
    name: str,
    frontmatter: dict[str, str],
    schema: dict[str, Any] | None = None,
) -> SkillReference:
    user_invocable_field = skill_frontmatter_field_by_loader_property(
        "userInvocable",
        "user-invocable",
        schema,
    )
    invocable_name = qualified_name(name)
    display_name = f"/{invocable_name}" if parse_frontmatter_bool(frontmatter, user_invocable_field) else invocable_name
    return SkillReference(
        name=invocable_name,
        display_name=display_name,
        invocation=expected_invocation(frontmatter, schema),
        arguments=expected_arguments(frontmatter, schema),
        description=frontmatter.get("description", ""),
        source_name=name,
    )


def render_skill_reference_row(reference: SkillReference) -> str:
    arguments = "—" if reference.arguments == "—" else f"`{escape_markdown_table_cell(reference.arguments)}`"
    return (
        f"| `{escape_markdown_table_cell(reference.display_name)}` | "
        f"{reference.invocation} | "
        f"{arguments} | "
        f"{escape_markdown_table_cell(reference.description)} |"
    )


def generated_readme_block_bounds(
    readme: str,
    config: dict[str, Any],
    failures: list[str],
    label: str = "readme skill sync",
) -> tuple[int, int] | None:
    lines = readme.splitlines()
    start_marker = config.get("start_marker")
    end_marker = config.get("end_marker")
    if start_marker or end_marker:
        if not isinstance(start_marker, str) or not isinstance(end_marker, str):
            failures.append(f"{label}: start_marker and end_marker must both be strings")
            return None
        try:
            start = next(index for index, line in enumerate(lines) if line.strip() == start_marker)
        except StopIteration:
            failures.append(f"{label}: missing start marker {start_marker!r}")
            return None
        try:
            end = next(
                index for index, line in enumerate(lines[start + 1 :], start=start + 1) if line.strip() == end_marker
            )
        except StopIteration:
            failures.append(f"{label}: missing end marker {end_marker!r}")
            return None
        if end <= start:
            failures.append(f"{label}: generated block end marker precedes start marker")
            return None
        return start + 1, end

    start_heading = config.get("section_start_heading", "## Skills")
    end_heading = config.get("section_end_heading", "## Agents")
    in_section = False
    start = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == start_heading:
            in_section = True
            start = index + 1
            continue
        if in_section and stripped == end_heading:
            return start, index

    failures.append(f"{label}: could not find section from {start_heading!r} to {end_heading!r}")
    return None


def name_from_readme_cell(cell: str, pattern: str) -> str | None:
    match = re.search(pattern, cell)
    if match:
        return match.group("name")
    return None


def skill_name_from_readme_cell(cell: str) -> str | None:
    return name_from_readme_cell(cell, rf"`/?(?P<name>{re.escape(PLUGIN_NAMESPACE)}:[A-Za-z0-9:_-]+)`")


def agent_name_from_readme_cell(cell: str) -> str | None:
    return name_from_readme_cell(cell, rf"`(?P<name>{re.escape(PLUGIN_NAMESPACE)}:[A-Za-z0-9:_-]+)`")


def hook_name_from_readme_cell(cell: str) -> str | None:
    return name_from_readme_cell(cell, r"`(?P<name>[A-Za-z0-9_-]+)`")


def readme_component_rows(
    readme: str,
    config: dict[str, Any],
    failures: list[str],
    label: str,
    name_from_cell,
) -> dict[str, tuple[int, list[str]]]:
    bounds = generated_readme_block_bounds(readme, config, failures, label)
    if bounds is None:
        return {}

    start, end = bounds
    rows: dict[str, tuple[int, list[str]]] = {}
    for index, line in enumerate(readme.splitlines()[start:end], start=start + 1):
        cells = split_markdown_table_row(line)
        if not cells:
            continue
        name = name_from_cell(cells[0])
        if name is None:
            continue
        if name in rows:
            previous_line = rows[name][0]
            failures.append(
                f"{label}: README entry {name!r} is documented more than once (lines {previous_line} and {index})"
            )
            continue
        rows[name] = (index, cells)
    return rows


def load_skill_references(
    root: Path,
    skills_relative: str,
    failures: list[str],
    schema: dict[str, Any] | None = None,
) -> dict[str, SkillReference]:
    skills_dir = resolve(root, skills_relative)
    if not skills_dir.exists():
        failures.append(f"readme skill sync: registered path is missing: {skills_relative}")
        return {}

    references: dict[str, SkillReference] = {}
    for path in sorted(skills_dir.iterdir()):
        skill_path = path / "SKILL.md"
        if not path.is_dir() or not skill_path.is_file():
            continue
        text = read_text(skill_path)
        frontmatter = parse_frontmatter(text)
        relative = rel(skill_path, root)
        if frontmatter is None:
            failures.append(f"readme skill sync: {relative} is missing YAML frontmatter")
            continue
        name = path.name
        frontmatter_name = frontmatter_string_value(text, "name")
        if frontmatter_name and frontmatter_name != name:
            failures.append(
                f"readme skill sync: {relative} frontmatter name {frontmatter_name!r} "
                f"does not match skill directory {name!r}"
            )
            continue
        for loader_property, fallback in (
            ("userInvocable", "user-invocable"),
            ("disableModelInvocation", "disable-model-invocation"),
        ):
            field = skill_frontmatter_field_by_loader_property(loader_property, fallback, schema)
            value = frontmatter_boolean_value(text, field)
            if value is not None:
                frontmatter[field] = "true" if value else "false"
        for field in (
            "description",
            skill_frontmatter_field_by_loader_property("argumentHint", "argument-hint", schema),
        ):
            scalar_value = frontmatter_string_value(text, field)
            if scalar_value is not None:
                frontmatter[field] = scalar_value
        reference = skill_reference_from_frontmatter(name, frontmatter, schema)
        hint = frontmatter_string_value(
            text, skill_frontmatter_field_by_loader_property("argumentHint", "argument-hint", schema)
        )
        user_field = skill_frontmatter_field_by_loader_property("userInvocable", "user-invocable", schema)
        if frontmatter_boolean_value(text, user_field) and hint is not None and hint.strip():
            reference = replace(reference, arguments=hint)
        references[reference.name] = reference
    return references


def load_agent_references(
    root: Path,
    agents_relative: str,
    failures: list[str],
) -> dict[str, AgentReference]:
    agents_dir = resolve(root, agents_relative)
    if not agents_dir.exists():
        failures.append(f"readme agent sync: registered path is missing: {agents_relative}")
        return {}

    references: dict[str, AgentReference] = {}
    for path in sorted(agents_dir.glob("*.md")):
        text = read_text(path)
        frontmatter = parse_frontmatter(text)
        relative = rel(path, root)
        if frontmatter is None:
            failures.append(f"readme agent sync: {relative} is missing YAML frontmatter")
            continue
        name = path.stem
        frontmatter_name = frontmatter_string_value(text, "name")
        if frontmatter_name and frontmatter_name != name:
            failures.append(
                f"readme agent sync: {relative} frontmatter name {frontmatter_name!r} "
                f"does not match agent file {name!r}"
            )
            continue
        description = frontmatter_string_value(text, "description") or ""
        if is_empty_value(description):
            failures.append(f"readme agent sync: {relative} is missing frontmatter description")
            continue
        references[qualified_name(name)] = AgentReference(
            name=qualified_name(name), description=description, source_name=name
        )
    return references


def hook_command_relative_path(command: str, command_path_regex: str) -> str | None:
    matches = re.findall(command_path_regex, command)
    if not matches:
        return None
    return str(matches[0])


def hook_name_from_command(command: str, command_path_regex: str) -> str | None:
    plugin_relative = hook_command_relative_path(command, command_path_regex)
    if plugin_relative is None:
        return None
    return Path(plugin_relative).name.removesuffix(".sh")


def hook_event_label(event: str, matcher: Any) -> str:
    if isinstance(matcher, str) and not is_empty_value(matcher):
        return f"{event} ({matcher})"
    return event


def load_hook_references(
    root: Path,
    config: dict[str, Any],
    failures: list[str],
) -> dict[str, HookReference]:
    hooks_relative = config.get("hooks_json", "trackbed/hooks/hooks.json")
    hooks_path = resolve(root, hooks_relative)
    if not hooks_path.exists():
        failures.append(f"readme hook sync: registered path is missing: {hooks_relative}")
        return {}

    try:
        data = json.loads(read_text(hooks_path))
    except json.JSONDecodeError as exc:
        failures.append(
            f"readme hook sync: {hooks_relative} is invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        )
        return {}

    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        failures.append(f"readme hook sync: {hooks_relative} must contain an object field 'hooks'")
        return {}

    command_path_regex = config.get(
        "command_path_regex",
        r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"'\s]+)",
    )
    plugin_root = config.get("plugin_root", "trackbed")
    descriptions = config.get("descriptions", {})
    if not isinstance(descriptions, dict):
        failures.append("readme hook sync: descriptions must be an object keyed by hook name")
        descriptions = {}

    order: list[str] = []
    events_by_name: dict[str, list[str]] = {}
    paths_by_name: dict[str, str] = {}

    for event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        for entry_index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                continue
            event_label = hook_event_label(event, entry.get("matcher"))
            hook_entries = entry.get("hooks")
            if not isinstance(hook_entries, list):
                continue
            for hook_index, hook_entry in enumerate(hook_entries, start=1):
                if not isinstance(hook_entry, dict):
                    continue
                command = hook_entry.get("command")
                if not isinstance(command, str):
                    continue
                name = hook_name_from_command(command, command_path_regex)
                if name is None:
                    failures.append(
                        f"readme hook sync: {hooks_relative} {event}[{entry_index}]."
                        f"hooks[{hook_index}] command does not reference a plugin hook script"
                    )
                    continue
                if name not in events_by_name:
                    events_by_name[name] = []
                    plugin_relative = hook_command_relative_path(command, command_path_regex)
                    paths_by_name[name] = f"{plugin_root}/{plugin_relative}"
                    order.append(name)
                if event_label not in events_by_name[name]:
                    events_by_name[name].append(event_label)

    references: dict[str, HookReference] = {}
    for name in order:
        description = descriptions.get(name)
        if not isinstance(description, str) or is_empty_value(description):
            failures.append(f"readme hook sync: descriptions is missing hook {name!r}")
            continue
        references[name] = HookReference(
            name=name,
            event=", ".join(events_by_name[name]),
            description=description,
            path=paths_by_name[name],
        )
    return references


@dataclass(frozen=True)
class ComponentSync:
    """The README rows for one component kind, resolved from its registry config, and the source they mirror.

    `columns` maps each README column to the reference attribute it shows and its
    column index. Agent and hook tables are regenerated whole under `table_header`;
    skill rows are rewritten in place because the README splits them across tables.
    """

    label: str
    config: dict[str, Any]
    root: Path
    readme: str
    source: str
    kind: str
    loader: Callable[[list[str]], dict[str, Any]]
    name_from_cell: Callable[[str], str | None]
    columns: dict[str, tuple[str, int]]
    row_renderer: Callable[[Any], str]
    table_header: tuple[str, ...] = ()
    source_label: str = "source metadata"
    source_file: str | None = None
    allow_readme_only: frozenset[str] = frozenset()

    def check(self, failures: list[str]) -> None:
        readme_path = resolve(self.root, self.readme)
        if not readme_path.exists():
            failures.append(f"{self.label}: registered path is missing: {self.readme}")
            return

        readme = read_text(readme_path)
        references = self.loader(failures)
        documented = self._documented_rows(readme, failures)
        self._check_missing_rows(documented, references, failures)
        self._check_extra_rows(documented, references, failures)
        self._check_row_values(documented, references, failures)

    def render(self, readme: str, failures: list[str]) -> str | None:
        references = self.loader(failures)
        if self.table_header:
            if failures:
                return None
            rows = [self.row_renderer(reference) for reference in references.values()]
            block = [*self.table_header, *rows]
            return replace_generated_readme_block(readme, self.config, failures, self.label, block)

        documented = self._documented_rows(readme, failures)
        self._check_missing_rows(documented, references, failures)
        self._check_extra_rows(documented, references, failures)
        if failures:
            return None

        lines = readme.splitlines()
        for name, (line_no, _cells) in documented.items():
            reference = references.get(name)
            if reference is not None:
                lines[line_no - 1] = self.row_renderer(reference)
        rendered = "\n".join(lines)
        if readme.endswith("\n"):
            rendered += "\n"
        return rendered

    def _documented_rows(self, readme: str, failures: list[str]) -> dict[str, tuple[int, list[str]]]:
        return readme_component_rows(readme, self.config, failures, self.label, self.name_from_cell)

    def _check_missing_rows(
        self,
        documented: dict[str, tuple[int, list[str]]],
        references: dict[str, Any],
        failures: list[str],
    ) -> None:
        for name in sorted(references):
            if name not in documented:
                failures.append(f"{self.label}: {self.readme} is missing {self.kind} {name!r} from {self.source}")

    def _check_extra_rows(
        self,
        documented: dict[str, tuple[int, list[str]]],
        references: dict[str, Any],
        failures: list[str],
    ) -> None:
        for name, (line_no, _cells) in documented.items():
            if name in references or name in self.allow_readme_only:
                continue
            if self.source_file is None:
                missing = f"{self.kind} source is missing from {self.source}"
            else:
                missing = f"{self.source}/{name}/{self.source_file} does not exist"
            failures.append(f"{self.label}: {self.readme}:{line_no} documents {name!r}, but {missing}")

    def _check_row_values(
        self,
        documented: dict[str, tuple[int, list[str]]],
        references: dict[str, Any],
        failures: list[str],
    ) -> None:
        source_label = "source metadata" if readme_summaries_configured(self.config) else self.source_label
        max_column = max(column for _attribute, column in self.columns.values())
        for name, (line_no, cells) in documented.items():
            reference = references.get(name)
            if reference is None:
                continue
            if len(cells) <= max_column:
                columns = ", ".join(field.title() for field in self.columns)
                failures.append(
                    f"{self.label}: {self.readme}:{line_no} row for {name!r} must include {columns} columns"
                )
                continue

            for field, (attribute, column) in self.columns.items():
                actual = normalize_markdown_cell(cells[column])
                expected = normalize_markdown_cell(getattr(reference, attribute))
                if actual != expected:
                    failures.append(
                        f"{self.label}: {self.readme}:{line_no} {name!r} "
                        f"{field} differs from {source_label}; expected "
                        f"{shorten(expected)!r}, got {shorten(actual)!r}"
                    )


def resolved_columns(config: dict[str, Any], columns: dict[str, tuple[str, int]]) -> dict[str, tuple[str, int]]:
    return {
        field: (attribute, int(config.get(f"{field}_column", default)))
        for field, (attribute, default) in columns.items()
    }


def skill_component_sync(root: Path, config: dict[str, Any], schema: dict[str, Any] | None) -> ComponentSync:
    label = "readme skill sync"
    skills_relative = config.get("skills_dir", "trackbed/skills")

    def load(failures: list[str]) -> dict[str, Any]:
        references = load_skill_references(root, skills_relative, failures, schema)
        return apply_readme_summaries(label, "skill", references, config, failures)

    return ComponentSync(
        label=label,
        config=config,
        root=root,
        readme=config.get("readme", "README.md"),
        source=skills_relative,
        kind="skill",
        loader=load,
        name_from_cell=skill_name_from_readme_cell,
        columns=resolved_columns(
            config,
            {
                "skill": ("display_name", 0),
                "invocation": ("invocation", 1),
                "arguments": ("arguments", 2),
                "description": ("description", 3),
            },
        ),
        row_renderer=render_skill_reference_row,
        source_label="SKILL.md frontmatter",
        source_file="SKILL.md",
        allow_readme_only=frozenset(config.get("allow_readme_only_skills", [])),
    )


def agent_component_sync(root: Path, config: dict[str, Any]) -> ComponentSync:
    label = "readme agent sync"
    agents_relative = config.get("agents_dir", "trackbed/agents")

    def load(failures: list[str]) -> dict[str, Any]:
        references = load_agent_references(root, agents_relative, failures)
        return apply_readme_summaries(label, "agent", references, config, failures)

    return ComponentSync(
        label=label,
        config=config,
        root=root,
        readme=config.get("readme", "README.md"),
        source=agents_relative,
        kind="agent",
        loader=load,
        name_from_cell=agent_name_from_readme_cell,
        columns=resolved_columns(config, {"agent": ("name", 0), "description": ("description", 1)}),
        row_renderer=render_agent_reference_row,
        table_header=("| Agent | Description |", "| --- | --- |"),
    )


def hook_component_sync(root: Path, config: dict[str, Any]) -> ComponentSync:
    return ComponentSync(
        label="readme hook sync",
        config=config,
        root=root,
        readme=config.get("readme", "README.md"),
        source=config.get("hooks_json", "trackbed/hooks/hooks.json"),
        kind="hook",
        loader=lambda failures: load_hook_references(root, config, failures),
        name_from_cell=hook_name_from_readme_cell,
        columns=resolved_columns(
            config,
            {"hook": ("name", 0), "event": ("event", 1), "description": ("description", 2)},
        ),
        row_renderer=render_hook_reference_row,
        table_header=("| Hook | Event | Description |", "| --- | --- | --- |"),
    )


def component_syncs(root: Path, registry: Registry, schema: dict[str, Any] | None) -> list[ComponentSync]:
    syncs: list[ComponentSync] = []
    skill_config = registry.get("readme_skill_sync")
    if skill_config:
        syncs.append(skill_component_sync(root, skill_config, schema))
    agent_config = registry.get("readme_agent_sync")
    if agent_config:
        syncs.append(agent_component_sync(root, agent_config))
    hook_config = registry.get("readme_hook_sync")
    if hook_config:
        syncs.append(hook_component_sync(root, hook_config))
    return syncs


def check_readme_skill_sync(
    root: Path,
    registry: Registry,
    schema: dict[str, Any],
    failures: list[str],
) -> None:
    for sync in component_syncs(root, registry, schema):
        sync.check(failures)


def render_agent_reference_row(reference: AgentReference) -> str:
    return f"| `{escape_markdown_table_cell(reference.name)}` | {escape_markdown_table_cell(reference.description)} |"


def render_hook_reference_row(reference: HookReference) -> str:
    return (
        f"| `{escape_markdown_table_cell(reference.name)}` | "
        f"{escape_markdown_table_cell(reference.event)} | "
        f"{escape_markdown_table_cell(reference.description)} |"
    )


def replace_generated_readme_block(
    readme: str,
    config: dict[str, Any],
    failures: list[str],
    label: str,
    lines: list[str],
) -> str | None:
    bounds = generated_readme_block_bounds(readme, config, failures, label)
    if bounds is None:
        return None
    start, end = bounds
    readme_lines = readme.splitlines()
    readme_lines[start:end] = lines
    rendered = "\n".join(readme_lines)
    if readme.endswith("\n"):
        rendered += "\n"
    return rendered


def readme_relative_for_component_sync(
    registry: Registry,
    failures: list[str],
) -> str | None:
    configs = [
        registry.get("readme_skill_sync"),
        registry.get("readme_agent_sync"),
        registry.get("readme_hook_sync"),
    ]
    readme_values = {config.get("readme", "README.md") for config in configs if isinstance(config, dict)}
    if not readme_values:
        failures.append("component reference sync: registry has no README sync config")
        return None
    if len(readme_values) > 1:
        failures.append("component reference sync: README sync configs must target the same README file")
        return None
    return next(iter(readme_values))


def render_readme_component_sync(
    root: Path,
    registry: Registry,
) -> tuple[str | None, list[str]]:
    failures: list[str] = []
    schema = load_contract_schema(root, registry, failures)
    readme_relative = readme_relative_for_component_sync(registry, failures)
    if readme_relative is None:
        return None, failures

    readme_path = resolve(root, readme_relative)
    if not readme_path.exists():
        return None, [f"component reference sync: registered path is missing: {readme_relative}"]

    rendered: str | None = read_text(readme_path)
    for sync in component_syncs(root, registry, schema):
        if rendered is None:
            break
        rendered = sync.render(rendered, failures)
    if failures:
        return None, failures
    return rendered, []
