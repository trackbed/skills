# code:audit-agent-config

Use it to clean up the agent configuration stored in your repository: instruction files such as `CLAUDE.md` and `AGENTS.md`, skills, subagents, hooks, MCP servers, permissions, and memory. It splits them into single rules and entries and gives each one a KEEP, IMPROVE, or REMOVE verdict with evidence. It is read-only: it never edits a file and never reads configuration outside the repository, such as `~/.claude/`. To score how well the codebase itself suits agents, use `trackbed:code:agent-readiness`; to review how you work with agents, use `trackbed:code:audit-practice`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[scope-path]` | Audit only the configuration at or under this path. Without it, the whole repository is audited. A path that is missing or outside the repository stops the audit. |

## Examples

```text
# Audit all agent configuration in the repository
/trackbed:code:audit-agent-config

# Audit only the configuration under one directory
/trackbed:code:audit-agent-config packages/api
```

## What you get

- A report in the conversation and no file. It opens with the scope, the kinds of configuration checked (including the ones that came up empty), and the number of items with each verdict.
- One sentence per item: why it stays, the defect and a concrete fix, or the reason to remove it. A REMOVE verdict names its reason: redundant, outdated, conflicting, or irrelevant to this project.
- Under IMPROVE and REMOVE, items that load into every session are marked `[always-on]` and listed first.
- A closing note that no files were changed.

Ask in a follow-up to apply the removals or improvements. When an IMPROVE item names a lint rule, type, test, or check script that could enforce a rule, build it with `trackbed:code:encode-constraint`.
