# linear:issue-to-pr

Use it to hand one Linear issue to the agent and get back a reviewed, verified branch, or with `--ship` an open Pull Request with green CI. It implements the issue, reviews and fixes its own work against the issue's requirements, and runs the project's checks. To implement without the review and shipping steps, use `trackbed:linear:issue-implement`.

## Before you run it

- The Linear MCP server is connected and `gh` is authenticated.
- The working tree is clean, unless you resume with `--continue`.
- The issue has no Pull Request and no remote branch yet.

## Arguments

| Argument     | Meaning                                            |
| ------------ | -------------------------------------------------- |
| `<ISSUE-ID>` | The Linear issue to implement, such as `DISC-202`. |

## Options

| Option | Effect |
| --- | --- |
| `--ship` | Delete the project's disposable reports and plans, such as `REVIEW_OVERVIEW.md` and `PR_PLAN_*.md`, rewrite the branch into narrative commits, push it, open the Pull Request, and fix CI and review feedback until both are clear. Without it, the run stops after verification. |
| `--continue` | Resume an interrupted run on the issue's own unpublished branch. The issue must already be started. |
| `--strict` | Require an evidence-based decision on every review finding, and use the full review profile. |
| `--cycles <1-5>` | How many fix-and-review rounds the review may take. The default is 2. |
| `--depth <balanced\|full>` | Raise the review profile above the one the branch's risk calls for. It never lowers it. |
| `--adversarial-review` | Also get a review from the other model provider on medium- and high-risk work. You decide any of its findings the run wants to reject. |
| `--rebase` | With `--ship`, rebase the opened Pull Request onto its base once if the base moved, and force-push it, instead of asking. |
| `--no-rebase` | With `--ship`, keep the pushed branch as it is if the base moved, and do not ask. You cannot combine it with `--rebase`. |
| `--launch-confirmed` | Skip the start confirmation for an issue that is not started yet, because you already gave it. `trackbed:linear:next` sets this when it launches a run. |

## Examples

```text
# Implement, review, and verify, then stop before publishing
/trackbed:linear:issue-to-pr DISC-202

# Do all of that, open the Pull Request, and get CI green
/trackbed:linear:issue-to-pr DISC-202 --ship

# Pick up where an interrupted run stopped
/trackbed:linear:issue-to-pr DISC-202 --continue --ship

# Give review more rounds and the full profile on a risky change
/trackbed:linear:issue-to-pr DISC-202 --strict --cycles 4 --ship
```

## What you get

- The issue moved to your team's started status in Linear, and a branch with the implementation committed.
- A summary of what was built, what review found and fixed, and what to check when you review it yourself.
- With `--ship`, an open Pull Request whose checks pass. Before publishing, `trackbed:workflow:cleanup-artifacts` removes the project's disposable reports and plans, including ones from other work, and keeps specifications and shared diagrams; the branch's commits are rewritten into a narrative history, with a backup.

When the run cannot decide something safely, it stops and asks you one question with its recommendation. The [shipping guide](../shipping.md#linear-issue-to-pull-request) covers each step in full.
