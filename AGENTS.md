# AGENTS.md

Edit shipped components in the canonical plugin source under `trackbed/`. Installed copies, app bundles, and generated Codex output are derived from that source.

## Context Map

- **ALWAYS** read [CONTRIBUTING.md](CONTRIBUTING.md) for setup, authoring conventions, and verification. Use the [code map](trackbed/docs/code-map.md) to find source files and focused tests.
- **ALWAYS** read the [architecture guide](trackbed/docs/architecture.md) before changing subsystem boundaries or runtime flow, and the [portability guide](trackbed/docs/agent-portability.md) before changing converter, hook, MCP, or host-adapter behavior.
- **ALWAYS** consult the [decision index](trackbed/docs/decisions/README.md) before revisiting a settled decision.
- **PREFER** the [component catalog](trackbed/docs/component-catalog.json) when looking up a shipped skill, agent, or hook. Repository-only maintenance skills live in [.agents/skills/](.agents/skills/) and are listed in [Local Repository Maintenance](README.md#local-repository-maintenance).

## Issue Tracking

- **ALWAYS** track this repository's issues in the **Trackbed Skills** team (`SKILLS`) of the `trackbed` Linear workspace.
- **ALWAYS** verify the MCP connection belongs to `trackbed` before using it. If that connection is unavailable or belongs to another workspace, use `https://api.linear.app/graphql` with `LINEAR_TRACKBED_API_KEY` in the `Authorization` header. For this repository, that fallback also satisfies the Linear access prerequisite in `trackbed:linear:*` workflows. Keep their approval and verification steps and never print the key.

## Adding Components

- **ALWAYS** use the [frontmatter schema](trackbed/scripts/schemas/skill-contracts.json) for shipped skills and agents. Use kebab-case names and omit the host-added `trackbed:` prefix from their source names. The local maintenance skill keeps its [explicit namespace](trackbed/docs/decisions/2026-11-05-trackbed-plugin-namespace.md).
- **ALWAYS** create agents at `trackbed/agents/<agent-name>.md` with `model: inherit`. For agents that report findings, set `disallowedTools: Write, Edit, NotebookEdit` and retain the `**Read-only agent.**` body rule. Bash can still write files, and the Codex converter drops the frontmatter restriction.
- **ALWAYS** launch outsider readers through the [cold-reader contract](trackbed/shared/agents/references/cold-reader.md). Only `trackbed:cold-reader` may set `omitClaudeMd`.
- **ALWAYS** give a new or renamed shipped skill exactly two kebab-case segments in `trackbed/skills/<domain>:<skill-name>/SKILL.md` and its frontmatter name, unless an accepted ADR grants an exception. Use the [catalog decision](trackbed/docs/decisions/2026-07-29-skill-catalog-shape.md) when adding domains or deciding whether skills should merge.
- **ALWAYS** set `disable-model-invocation: true` by default for side-effecting skills. Follow the accepted exceptions for [guarded orchestration children](trackbed/docs/decisions/2026-08-29-model-invocable-orchestration-children.md) and [model-initiated ADR authoring](trackbed/docs/decisions/2026-11-02-model-invocable-adr-authoring.md).
- **ALWAYS** set `trackbed-platforms: [claude-code]` when a skill requires a Claude Code-only feature, such as Agent Teams, to run.
- **ALWAYS** keep each shipped skill self-contained within the installed plugin. Follow the [shared-resource decision](trackbed/docs/decisions/2026-10-01-plugin-level-shared-skill-resources.md) for runtime paths and subagent prompts.
- **ALWAYS** follow the [skill epilogue decision](trackbed/docs/decisions/2026-09-07-skill-epilogue-verification-only.md) when writing a skill's gates and verification section.
- **ALWAYS** register hooks in [hooks.json](trackbed/hooks/hooks.json) and call `exit_if_hook_disabled` from [check-enabled.sh](trackbed/hooks/lib/check-enabled.sh) before the hook does work.

## Documentation and Verification

- **ALWAYS** update the [public README and linked guides](trackbed/docs/decisions/2026-10-28-readme-entry-point.md) at their sources. For site placement and shipped user-invocable skills' usage guides, follow the [site guide](site/README.md).
- **ALWAYS** follow the [source and licensing rules](CONTRIBUTING.md#external-sources-and-rights) when using third-party material.
- **ALWAYS** regenerate the component reference after changing a skill, agent, or hook with `python3 trackbed/scripts/generate-component-reference.py --write`.
- **ALWAYS** run `make -C trackbed skill-security-changed` for new or materially changed shipped skills and shared resources. Follow the [scan guide](trackbed/docs/development.md#skill-security-scans) for release checks, third-party intake, and finding triage.
