# pr:resolve-review

Use it after a review to fix what the review found. It reads the findings, sets aside the ones outside the Pull Request's scope, implements the rest, runs the project's fast checks, and commits. It edits files and commits on the current branch; it never pushes, posts to GitHub, or resolves threads. To answer reviewers on GitHub, use `trackbed:pr:github-review-reply`.

## Before you run it

- There is a review to resolve: a report from a review skill in the project root, such as `REVIEW_OVERVIEW.md` or `PRODUCT_REVIEW_OVERVIEW.md`, Conductor diff comments, a review in the conversation, or review comments on the branch's Pull Request.
- `gh` is authenticated when the review comes from GitHub.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[review\|url\|instructions]` | A pasted review to resolve, a Pull Request URL whose review comments are fetched from GitHub, or plain instructions such as "only security issues" that steer which findings are fixed and how. Without it, the skill looks for a local report, then Conductor diff comments, then a review in the conversation, then GitHub. |

## Options

| Option | Effect |
| --- | --- |
| `--team` | Fix findings in parallel with several agents, each owning its own set of files. It needs multi-agent execution (Agent Teams in Claude Code) and cannot be combined with `--implement-only`. It makes no commits; you commit the result. |
| `--implement-only` | Fix and validate only: no commits, no review file, no draft replies. It needs a structured list of findings as input and writes its result to `.context/resolve-review/implement-only-summary.json`. Set by `trackbed:pr:github-review-reply` and `trackbed:pr:review-convergence` when they delegate; you rarely need it. |
| `--granular` | Make one commit per finding instead of one commit for all fixes. |
| `--severity ...` | Process only findings of the listed severities: a comma-separated list of `critical`, `important`, and `suggestion`. The others stay untouched for a later run. |
| `--source local\|online\|conductor` | Read the review from one place only: `local` report files, `online` for GitHub review comments, or `conductor` for Conductor diff comments. |

## Examples

```text
# Fix the findings in the local review report
/trackbed:pr:resolve-review

# Fix only critical and important findings, one commit per finding
/trackbed:pr:resolve-review --severity critical,important --granular

# Fix the review comments on the branch's Pull Request
/trackbed:pr:resolve-review --source online

# Steer the run with an instruction
/trackbed:pr:resolve-review focus on the security findings
```

## What you get

- The fixes committed on your branch as one `review:` commit, or one per finding with `--granular`. If a check that the fixes broke still fails after one repair attempt, nothing is committed and you are offered a rollback.
- The review report updated in place with a resolution status and the action taken for each finding. A review from GitHub or Conductor is recorded in `REVIEW_OVERVIEW.md`, with a draft reply for each comment.
- A recommended resolution for each finding that needs your decision. Reply with the finding and the option you choose, then run the skill again.
- A summary of the changes with their commits, each check and its result, and counts of findings addressed, deferred, and waiting on a decision.

Uncommitted work is stashed while the skill runs and restored at the end.
