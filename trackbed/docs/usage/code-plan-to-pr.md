# code:plan-to-pr

Use it to hand one plan file, sized for a single Pull Request, to the agent and get back a reviewed, verified branch, or with `--ship` an open Pull Request with green CI. The plan is a `PR_PLAN_*.md` from `trackbed:code:breakdown-findings` or a plan file attached to the conversation. The run creates a new branch from your base branch, implements the plan inside the paths it lists, commits, reviews and fixes its own work, and runs the project's checks. To carry out a pasted plan on the current branch, use `trackbed:code:work-from-plan`; for a Linear issue, use `trackbed:linear:issue-to-pr`.

## Before you run it

- `gh` is authenticated, and `.context/` is ignored by Git.
- The working tree is clean, unless you resume with `--continue`. An untracked plan set in the repository root does not count when you run one of its plans.
- The plan's branch has no Pull Request and no remote branch yet.
- Every plan this one depends on has landed on the base branch.

## Arguments

| Argument | Meaning |
| --- | --- |
| `<PR_PLAN_W##L_*.md>` | One plan from a generated set, with its `PR_PLAN_INDEX.md` beside it. The first run moves the set into an archive; after that, pass the archived path the run reports. |
| `<attached plan>` | One self-contained plan file under `.context/attachments/`. It is the whole input: the run never asks for an index or for the other plans of its set. |

## Options

| Option | Effect |
| --- | --- |
| `--continue` | Resume an interrupted run that left work behind. You must be on the plan's branch and pass the archived plan, which must be `IN_PROGRESS`, and every existing change must be inside the plan's paths. |
| `--strict` | Require an evidence-based decision on every review finding, and use the full [review profile](../review.md#review-profiles). |
| `--cycles <1-5>` | How many fix-and-review rounds the review may take before it asks you. The default is 2. When the last round made progress and nothing needs you, review runs one extra round without asking, never more than five in total. |
| `--depth <balanced\|full>` | Raise the review profile above the one the branch's risk calls for. It never lowers it. |
| `--ship` | Rewrite the branch into narrative commits, push it, open the Pull Request, and fix CI and review feedback until both are clear. Without it, the run stops after verification. |

## Examples

```text
# Implement, review, and verify one plan, then stop before publishing
/trackbed:code:plan-to-pr PR_PLAN_W01A_DEFINE_ERROR_TYPES.md

# Do all of that with strict review, open the Pull Request, and get CI green
/trackbed:code:plan-to-pr PR_PLAN_W01A_DEFINE_ERROR_TYPES.md --strict --ship

# Run a plan that was attached to the conversation
/trackbed:code:plan-to-pr .context/attachments/<id>/pasted_text.txt --ship

# Pick up where an interrupted run stopped
/trackbed:code:plan-to-pr .context/code-plan-to-pr/<plan-set-id>/plans/PR_PLAN_W01A_DEFINE_ERROR_TYPES.md --continue --ship
```

## What you get

- The plan set moved from the repository root into `.context/code-plan-to-pr/<plan-set-id>/plans/`, where the run marks the plan `IN_PROGRESS` and then `DONE`. An attached plan is copied there and the attachment is left as it was. Plan files never enter the Pull Request.
- A new local `plan/...` branch with the implementation committed.
- A [final report](../shipping.md#final-reports) that starts with the outcome and what needs your attention, such as any default the run assumed for an open question in the plan. Then come what was built and what review found, and last the completion result: the review profile, the findings fixed, rejected, and deferred, the verification result, and the archive path.
- With `--ship`, an open Pull Request whose checks pass. Without it, the result names `trackbed:pr:create` as the next step.

When the run cannot decide something safely, it stops and shows a [decision request](../shipping.md#decision-requests). The [shipping guide](../shipping.md#plan-to-pull-request) covers the workflow.
