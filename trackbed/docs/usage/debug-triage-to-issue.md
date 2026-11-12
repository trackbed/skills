# debug:triage-to-issue

Use it to turn one bug into a ticket that someone else, or an agent, can implement later. It investigates the root cause, plans the fix as a series of failing tests and the changes that make them pass, and files one issue in Linear, in your local SIW tracker, or as a Markdown file. It never fixes the bug or edits code. The skill is experimental. To fix the bug now, use `trackbed:debug:investigate`; to log several bugs from a test pass, use `trackbed:qa:intake`.

## Before you run it

- For a Linear issue, connect the [Linear MCP server](../mcp-servers.md#linear). Without it, the issue goes to the SIW tracker when `siw/OPEN_ISSUES_OVERVIEW.md` exists, and otherwise to a Markdown file.
- When both Linear and SIW are available, you are asked once where the issue should go.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[bug description, error message, or Linear/SIW issue ref]` | The bug to triage: a description, an error message, or an issue reference. A Linear issue ID such as `TEAM-123` is fetched and used as the bug report. Without it, you are asked. |

## Options

| Option | Effect |
| --- | --- |
| `--yes` | File the issue without asking you to approve the draft, and skip the investigation's questions about reproduction and bisecting. You are still asked for what the issue needs, such as a Linear team, and an open issue with the same title is reported instead of duplicated. Put the flag last. |
| `--auto` | The same as `--yes`. |

## Examples

```text
# Investigate a bug and approve the drafted issue before it is filed
/trackbed:debug:triage-to-issue Expired tokens are still accepted at login

# Use a Linear issue as the bug report
/trackbed:debug:triage-to-issue TEAM-123

# File the issue without the approval step
/trackbed:debug:triage-to-issue Export fails for empty reports --yes
```

## What you get

- One new issue titled `Fix [observable behavior] in [public surface]`, with the sections Problem, Root Cause Analysis, TDD Fix Plan, Acceptance Criteria, and Out of Scope.
- In Linear, the issue's URL. In SIW, `siw/issues/ISSUE-{prefix}-{NNN}-{slug}.md` plus updates to `siw/OPEN_ISSUES_OVERVIEW.md` and `siw/LOG.md`. Otherwise `BUG-{slug}-{YYYY-MM-DD}.md` in the project root.
- A body that names behavior and public interfaces, not file paths or line numbers, so it stays valid after a refactor. Secrets are replaced with `[REDACTED]`, and a bug that could not be reproduced is marked `UNVERIFIED`.
- A closing block with `CHANGES MADE`, `THINGS I DIDN'T TOUCH`, and `POTENTIAL CONCERNS`.

Implement the issue with `trackbed:linear:issue-implement`. Move a local SIW ticket to Linear first with `trackbed:siw:transfer-to-linear`.
