# docs:adr

Use it to record a significant, long-lived decision as an Architecture Decision Record: the problem, the choice, the alternatives you rejected, and the consequences. It finds your project's ADR log and matches its template, file naming, and status words; without one it writes to `docs/decisions/` with its own template. It creates one ADR file and, when an accepted decision replaces an older ADR, marks that older record as superseded. For feature scope before coding, use `trackbed:docs:feature-spec`; for rules agents should follow, use `trackbed:docs:update-agents-md`.

## Before you run it

- Know who made the decision, what problem forced it, and at least one alternative that lost. The skill asks for whichever it cannot find, and it never fills in a decider on its own.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[decision title]` | A short title for the decision to record. You can add a short summary of its context. |

## Examples

```text
# Record a decision by its title
/trackbed:docs:adr Store sessions in Postgres instead of Redis

# Record a decision that replaces an earlier ADR
/trackbed:docs:adr Move sessions from cookies to Postgres, replacing ADR 0003
```

## What you get

- One new ADR in your project's ADR folder, named in the scheme the folder already uses, such as `0007-session-storage.md` or `2026-11-08-session-storage.md`. When the project has no ADR log and names no place for one, the file goes to `docs/decisions/` and numbering starts at `0001`.
- Status `PROPOSED`, unless the decision is already adopted.
- When the new ADR is accepted and replaces an older one, the older record's status changes to `SUPERSEDED` with a reference to the new one. Nothing else in it changes, and old records are never deleted.
- A final message that opens with an `ADR WRITTEN` callout: each file created or edited, who started the run, the decision in one line, and how to undo it. Review the files before you commit them.
- A question instead of a file when the skill finds more than one ADR folder, mixed file naming, or an existing ADR that may already record the decision.

The agent can also start this skill on its own for a decision that is hard to reverse, surprising without context, and the result of a real tradeoff. It then only creates a new `PROPOSED` ADR, and asks before it edits an existing record or creates an ADR folder.
