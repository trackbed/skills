# pr:triage-risk

Use it before review to decide how much review the current branch needs. It combines fixed risk signals, such as changes to auth, migrations, CI, or dependencies and the size of the change, with a read of the diff, and gives you a low, medium, or high tier, the review commands to run, and the decisions that need a person. It is read-only: it never approves, comments, labels, or writes files, and a low tier means a light review is enough, not that the change is approved. To get the review itself, run the commands it recommends, such as `trackbed:pr:code-review`.

## Before you run it

- The work is committed. Uncommitted changes are counted in the reply but not triaged.
- The repository has an `origin` remote whose default branch is known locally as `origin/HEAD`, `origin/main`, or `origin/master`. A repository's own risk rules in `.github/pr-risk.json` are read from that branch, never from the branch under triage.

## Options

| Option | Effect |
| --- | --- |
| `--base <branch>` | Compare against `<branch>` instead of the detected base branch. |

## Examples

```text
# Triage the committed work on the current branch
/trackbed:pr:triage-risk

# Triage against the develop branch
/trackbed:pr:triage-risk --base develop

# Triage one layer of a manually chained branch against its parent branch
/trackbed:pr:triage-risk --base feature/auth-layer
```

## What you get

- A reply in the conversation that starts with `PR risk: LOW`, `MEDIUM`, or `HIGH` and the main reason. No file is written and nothing is posted.
- The scope that was triaged, each signal with its evidence and whether reading the diff confirmed or discounted it, and any risk that only the diff showed.
- "Review lanes": the review commands to run, in order, with the reason for each.
- "Needs a human": the decisions a person must make, each tied to the file or line it concerns.

A low tier calls for a quick read by one reviewer, a medium tier for a full code review before approval, and a high tier for a full code review plus a person's answer to every "Needs a human" item. `trackbed:pr:review-convergence` uses the same signals to choose its [review profile](../review.md#review-profiles).
