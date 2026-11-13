# code:audit-practice

Use it to check how you work with coding agents against eighteen common mistakes, from effort set too high and overlong skills to lax automated checks and babysitting. It reads the repository, your project and user-level Claude Code and Codex configuration, and this repository's recent sessions, then names the few changes to make first. It is read-only: it reads session transcripts only through a script that reports counts, never their text, and it never prints secret values from settings. For a verdict on each configuration entry, use `trackbed:code:audit-agent-config`; for a score of the codebase, use `trackbed:code:agent-readiness`.

## Options

| Option | Effect |
| --- | --- |
| `--recent N` | Use the `N` most recent sessions from the last year, where `N` is 1 to 100. Without it, the audit uses at most 30 sessions from the last 30 days. Cannot be combined with `--no-sessions`. |
| `--no-sessions` | Leave session evidence out. Mistakes that only sessions reveal are reported as UNOBSERVABLE. |

## Examples

```text
# Audit with the default sample: at most 30 sessions from the last 30 days
/trackbed:code:audit-practice

# Use the 60 most recent sessions from the last year
/trackbed:code:audit-practice --recent 60

# Judge from the repository and the configuration only
/trackbed:code:audit-practice --no-sessions
```

## What you get

- An `Agentic Practice Audit` in the conversation and no file.
- `Fix First`: up to three mistakes, each with its evidence, one concrete change, and the skill or setting to go to next.
- `All Checks`: all eighteen mistakes in a table, each with a verdict (LIKELY, POSSIBLE, CLEAR, or UNOBSERVABLE) and one sentence of evidence.
- `Self-Check` questions for the mistakes it could not observe, and `Audit Gaps` for what it could not read.

The report ends with "No files were changed." Applying a fix is a separate request.
