# code:work-from-plan

Use it to carry out one implementation plan, such as a `PR_PLAN_*.md` file, a pasted plan, or a checklist, on the current branch. It first decides whether the plan is small and clear enough to implement directly: if so, it edits the code and runs fast checks, and if not, it tells you which workflow fits and hands a plan that names a Linear issue to `trackbed:linear:issue-implement`. It does not create a branch, push, open a Pull Request, or watch CI. For the full run from a plan file to a reviewed branch or Pull Request, use `trackbed:code:plan-to-pr`.

## Before you run it

- For direct implementation, the plan describes one bounded task with the files or modules it touches and its completion criteria, and the project has checks the run can find.
- If you have uncommitted changes unrelated to the plan, you are asked before the run works alongside them.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[plan path]` | A Markdown plan file, such as `PR_PLAN_W01A_DEFINE_ERROR_TYPES.md`. |
| `[inline plan]` | The plan as text. A one-line task without acceptance criteria is not enough: the run asks for what is missing before it edits code. With neither argument, you are asked for a plan. |

## Examples

```text
# Carry out a generated plan file on the current branch
/trackbed:code:work-from-plan PR_PLAN_W01A_DEFINE_ERROR_TYPES.md

# Carry out a plan you wrote yourself
/trackbed:code:work-from-plan docs/plans/add-csv-export.md

# Give a short plan inline
/trackbed:code:work-from-plan Rename exportCsv to exportReport in src/export.ts and update its tests. Done when npm test passes.
```

## What you get

- A `PLAN ROUTE:` line with the reason, shown before any edit. `direct` means the run implements the plan. `linear` means the plan names a Linear issue, so the run hands it to `trackbed:linear:issue-implement`. `siw` and `recommend-siw` mean the work needs tracking or more planning first; the run recommends the next step and creates no files. `blocked` means something is missing or contradictory, and you are asked one question.
- For a `direct` plan, edits on the current branch that stay inside the plan's scope, checked at the end with `trackbed:verify:run` in its fast mode.
- A closeout: the changes made, each completion criterion as `MET`, `UNMET`, or `UNVERIFIED` with evidence, the plan defaults it assumed for open questions, the checks it ran, what it left untouched, and remaining concerns.
- A `MISSING REQUIREMENT` line and a stop, instead of a guess, when a fact it needs to work safely is absent.
