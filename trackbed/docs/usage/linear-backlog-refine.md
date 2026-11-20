# linear:backlog-refine

Use it to groom a Linear team's backlog before planning. It grades the issues it collects for clarity, size, freshness, and whether an agent could implement them unattended. It groups related issues, flags conflicts, and proposes an action for each issue. Nothing changes in Linear unless you pass `--apply` and approve each batch. Use `trackbed:linear:next` to pick work or `trackbed:linear:issue-define` to refine one issue through an interview.

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
| `--all` | Grade every matching backlog issue without a cap. Project and label filters still apply. Cannot be combined with `--limit`. |
| `--apply` | After the report, present the proposed changes one batch at a time and write the ones you confirm to Linear. |

## Examples

```text
# Grade up to 200 backlog issues from the ENG team
/trackbed:linear:backlog-refine ENG

# Grade the full matching backlog for one project
/trackbed:linear:backlog-refine ENG --project "Checkout" --all

# Look at one project only, and treat 60 days without an update as stale
/trackbed:linear:backlog-refine ENG --project "Checkout" --stale-days 60

# Grade, then apply the changes you approve batch by batch
/trackbed:linear:backlog-refine ENG --apply
```

## What you get

- An inline report for capped runs. With `--all`, the conversation gives the coverage and counts and links to a local report saved in batches. The detailed report includes issue grades, proposed actions, conflicts, drafts, and open questions.
- With `--all`, full coverage requires fetching every matching page, checking for conflicts across batches, and verifying a report entry for every collected issue. If the run stops early, it reports the gap and links to any saved results.
- Without `--apply`, no change in Linear.
- With `--apply`, the batches you confirm are written. Completed and canceled issues get a comment and move to the team's completed or canceled status. Rewrites replace the title and description. Splits create sub-issues under the original. Duplicates hand their unique detail to the issue that stays, then move to the team's duplicate or canceled status with a comment. No issue is deleted, and each one is reported as applied, partially applied, skipped, or failed.

Issues already in progress are left out. Next, pick work with `trackbed:linear:next`.
