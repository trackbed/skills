# linear:issue-implement

Use it to start work on one Linear issue. It fetches the issue and the issues and documents it links to, switches to the issue's branch, explores the codebase, asks about anything unclear, and shows a technical plan before any code changes; you then choose how the implementation proceeds. It creates or switches branches and can edit and commit code; it writes to Linear only with `--set-in-progress`. For the whole route to a reviewed Pull Request, use `trackbed:linear:issue-to-pr`.

## Before you run it

- The Linear MCP server is connected. See [MCP servers](../mcp-servers.md#linear).
- With uncommitted changes, you are asked whether to stash, commit, discard, or abort. With `--auto`, the run stops instead.
- Work prepared in SIW is moved to Linear first with `trackbed:siw:transfer-to-linear`.

## Arguments

| Argument     | Meaning                                           |
| ------------ | ------------------------------------------------- |
| `<ISSUE-ID>` | The Linear issue to implement, such as `ABC-123`. |

## Options

| Option | Effect |
| --- | --- |
| `--auto` | Skip the plan confirmation and the approach question when the technical path is clear, and implement autonomously. It still asks about ambiguities that would change scope or behavior. `trackbed:linear:issue-to-pr` sets it when it delegates. |
| `--set-in-progress` | Move the issue to its team's started status, preferring one named In Progress, before any branch work. It asks first unless the issue is in Backlog. Without the flag, Linear is not changed. |

## Examples

```text
# Plan the issue, then choose how to implement it
/trackbed:linear:issue-implement ABC-123

# Also move the issue to In Progress before starting
/trackbed:linear:issue-implement ABC-123 --set-in-progress

# Implement autonomously when the path is clear
/trackbed:linear:issue-implement ABC-123 --auto
```

## What you get

- The issue's branch checked out, under the name Linear suggests. A new branch starts from the repository's [base branch](../shipping.md#base-branch).
- A summary of the issue: requirements, acceptance criteria, and linked context, including anything that could not be opened.
- A technical plan to confirm, then a choice of approach:
  - Guided Implementation: step by step, with your review after each task.
  - Context Setup Only: a todo list and starting points, and you drive.
  - Autonomous Implementation: the agent implements, commits as it goes, and runs the project's fast checks.
- After an autonomous run, a report of the changes, the check results, each acceptance criterion with its evidence, and anything that needs your action outside the repository.

When you are ready to publish, run `trackbed:pr:create`. The [shipping guide](../shipping.md#implementing-an-issue-directly) has more detail.
