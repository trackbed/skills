# linear:issue-define

Use it to create a new Linear issue from a description, or to improve an existing one by passing its ID. It explores the codebase, interviews you, and drafts a structured issue, then writes to Linear only after you approve the draft. Every issue must fit one Pull Request, so larger work becomes a parent issue with one sub-issue per Pull Request. It never changes code; to implement the issue, use `trackbed:linear:issue-implement`.

## Before you run it

- The Linear MCP server is connected. See [MCP servers](../mcp-servers.md#linear).

## Arguments

| Argument | Meaning |
| --- | --- |
| `[issue-id]` | An existing issue to improve: an identifier such as `ENG-123`, a `linear.app` issue URL, or a UUID. |
| `[description]` | What the new issue is about. Without an ID or a description, you are asked what to define. |
| `[file paths]` | Files to read for technical context. |
| `--` | Ends the options, so everything after it is read as input. |

## Options

| Option | Effect |
| --- | --- |
| `--auto` | Create a new issue with at most two clarifying questions instead of the full interview. You still approve the draft. It stops when the input names an existing issue. `trackbed:linear:breakdown-findings` uses it to create each of its issues. |
| `--ask` | With `--auto`, ask every relevant interview question before drafting. It is rejected without `--auto`, because the normal run already asks them. |

## Examples

```text
# Create a new issue through the full interview
/trackbed:linear:issue-define Users cannot reset their password from the mobile app

# Improve an existing issue
/trackbed:linear:issue-define ENG-123

# Create an issue quickly from rough input, with a file for context
/trackbed:linear:issue-define --auto Export fails for large reports src/export/report.ts

# Create quickly, but answer every relevant question first
/trackbed:linear:issue-define --auto --ask Add an audit log for permission changes
```

## What you get

- For a new issue, likely duplicates and related issues first, so you can continue, link them, or improve the existing issue instead.
- A draft to approve, refine, or cancel: title, description, and metadata. For an existing issue, the draft shows what changed.
- If the work needs more than one Pull Request, the choice to split it into a parent with sub-issues, to narrow it to the first slice, or to cancel.
- After approval, the issue created or updated in Linear with its relations, and its URL. A split returns the parent and every sub-issue.
- If you cancel or Linear rejects the write, the full draft is printed so the work is not lost.

The run stops once the URL is returned. Implement with `trackbed:linear:issue-implement`; for a split, run it on each sub-issue in order, never on the parent.
