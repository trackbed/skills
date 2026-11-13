# debug:investigate

Use it to track down a bug, an error, or a regression. It reproduces the problem, narrows it to the code responsible, traces the root cause, and then asks how to proceed: fix it with a regression test, fix it without one, or report only. A fix edits files in your working tree. To file the bug as a ticket for later instead, use `trackbed:debug:triage-to-issue`.

## Before you run it

- To start from a Linear issue ID, connect the [Linear MCP server](../mcp-servers.md#linear). Without it, you are asked to paste the issue text.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[bug description, error message, or issue reference]` | What to investigate: a description in your own words, an error message to search the code for, or a Linear issue ID such as `TEAM-123`. Without it, you are asked. |

## Options

| Option | Effect |
| --- | --- |
| `--auto` | Run without the questions about reproduction, focus area, bisecting, and fix strategy. It fixes only when the bug was reproduced, or when confidence is high and a regression test can be written from the code alone. With low confidence it reports and changes nothing. |

## Examples

```text
# Investigate from an error message
/trackbed:debug:investigate "TypeError: Cannot read property 'id' of undefined"

# Investigate the bug described in a Linear issue
/trackbed:debug:investigate TEAM-123

# Investigate and fix without stopping for questions
/trackbed:debug:investigate Login fails after a password reset --auto
```

## What you get

- A summary headed `Bug Investigation Complete`: the root cause, its location, a confidence rating of High, Medium, or Low, and the investigation log with the evidence.
- If you chose a fix: the smallest code change that addresses the cause, a regression test when you asked for one, and the result of the project's checks and of re-running the original failure. A fix that fails is adjusted up to three times, then the failures are shown to you.
- A list of things it noticed but left alone, and a list of concerns such as a reproduction that could not be confirmed.

Once the bug is fixed, `trackbed:debug:find-sibling-bugs` searches for the same flaw elsewhere.
