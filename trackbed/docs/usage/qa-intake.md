# qa:intake

Use it after a manual test pass when you have several bugs to log. You describe one bug at a time, it asks at most two or three short questions, and it files a ticket for each until you say you are done. It creates tickets in Linear, or as local files when Linear is not available. It writes no code and does not edit or close existing tickets. To test a running app automatically, use `trackbed:qa`; for one thoroughly refined ticket, use `trackbed:linear:issue-define`.

## Before you run it

- For Linear tickets, connect the [Linear MCP server](../mcp-servers.md#linear). Without it, tickets go to the SIW tracker when `siw/OPEN_ISSUES_OVERVIEW.md` and `siw/issues/` exist, and otherwise to an `intake-issues/` folder in the project root.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[optional starting context]` | Your first bug description. With it, the session skips the opening question. |

## Examples

```text
# Start a session and describe the bugs one by one
/trackbed:qa:intake

# Start with the first bug
/trackbed:qa:intake The profile page shows a success message on save but the old name is back after a reload
```

## What you get

- One ticket per report, written in terms of what you saw, without file paths or internal names. In Linear the title starts with `QA:` and the ticket's URL is printed.
- Without Linear, `siw/issues/ISSUE-G-{NNN}-qa-{slug}.md` with a row in `siw/OPEN_ISSUES_OVERVIEW.md` and an entry in `siw/LOG.md`, or `intake-issues/{NNN}-{slug}.md`.
- A proposed split into a parent ticket and linked child tickets when one report holds several independent failures. Nothing is filed until you agree.
- A note instead of a second ticket when a bug is already logged from an earlier session or earlier in this one.
- A closing summary with `CHANGES MADE`, `THINGS I DIDN'T TOUCH`, and `POTENTIAL CONCERNS`.

After ten tickets in one session it checks that you want to keep going.
