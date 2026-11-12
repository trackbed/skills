# linear:backlog-refine

Use it to groom a Linear team's backlog before planning. It grades every open backlog issue for clarity, size, freshness, and whether an agent could implement it unattended, groups related issues, flags issues that contradict each other, and proposes one action per issue: complete, cancel, merge, split, rewrite, ask, or keep. Nothing changes in Linear unless you pass `--apply` and approve each batch. To pick an issue to work on, use `trackbed:linear:next`; to refine one issue through an interview, use `trackbed:linear:issue-define`.

## Before you run it

- The Linear MCP server is connected. See [MCP servers](../mcp-servers.md#linear).

## Arguments

| Argument | Meaning |
| --- | --- |
| `[team]` | The team's name, key, or ID. Without it, the only team is used, or you are asked which one. |

## Options

| Option | Effect |
| --- | --- |
| `--project <name>` | Grade only issues in this project. |
| `--label <name>` | Grade only issues with this label. |
| `--stale-days <n>` | Flag an issue as stale after this many days without an update. The default is 90. |
| `--limit <n>` | Collect at most this many backlog issues, least recently updated first. The default is 200 and the maximum is 400. |
| `--apply` | After the report, present the proposed changes one batch at a time and write the ones you confirm to Linear. |

## Examples

```text
# Grade the backlog of the ENG team and report the proposed actions
/trackbed:linear:backlog-refine ENG

# Look at one project only, and treat 60 days without an update as stale
/trackbed:linear:backlog-refine ENG --project "Checkout" --stale-days 60

# Grade, then apply the changes you approve batch by batch
/trackbed:linear:backlog-refine ENG --apply
```

## What you get

- A report in the conversation: a count per action, a table of the issues with their grades and the reason for each action, conflicts between issues that need a decision, drafts for every rewrite, split, and merge, and the questions that keep an issue from being ready.
- Without `--apply`, no change in Linear.
- With `--apply`, the batches you confirm are written. Completed and canceled issues get a comment and move to the team's completed or canceled status. Rewrites replace the title and description. Splits create sub-issues under the original. Duplicates hand their unique detail to the issue that stays, then move to the team's duplicate or canceled status with a comment. No issue is deleted, and each one is reported as applied, partially applied, skipped, or failed.

Issues already in progress are left out. Next, pick work with `trackbed:linear:next`.
