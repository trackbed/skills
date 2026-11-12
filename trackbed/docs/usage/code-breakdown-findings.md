# code:breakdown-findings

Use it after a review, audit, or QA run to turn validated findings into implementation plans, each sized for one Pull Request. It groups the findings into themes and writes one self-contained plan file per theme, plus an index and a record of what it left out; it never edits product code. `--split` plans how to cut the current branch's changes into smaller Pull Requests instead, and `--reconcile` brings an existing plan set up to date. To create Linear issues from findings, use `trackbed:linear:breakdown-findings`.

## Before you run it

- You have validated findings: a report in the project root such as `REVIEW_OVERVIEW.md`, files you pass, text you paste, or a findings set in the conversation. Raw bug lists and single issues are not suitable.
- The project root holds no `PR_PLAN_*.md` files from an earlier run, unless you pass `--resume` or `--reconcile`. Otherwise the skill stops and lists them.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[source ...]` | Report files to read, or findings pasted as text. Without any, it uses the reports it recognizes in the project root and offers reports from other worktrees of the repository; if it finds none, it looks for findings in the conversation. |
| `[plan-file ...]` | With `--reconcile`, the plan files to update, such as `PR_PLAN_W01A_AUTH_CLEANUP.md`. Without any, every plan in the index is in scope. |
| `[--]` | Ends the options. Put it before pasted findings that begin with a hyphen. |

## Options

| Option | Effect |
| --- | --- |
| `--auto` | Skip the confirmation of the proposed themes or slices. With `--reconcile`, apply low-risk updates such as status changes without asking; other questions are still asked. |
| `--resume` | Regenerate only the plan files missing from an existing set, after checking that the sources match and asking you. Not available for a set made with `--split`. |
| `--reconcile` | Check an existing plan set against the current code and propose updates to plan statuses, outdated code excerpts, and the rejection record. Without `--auto`, it waits for your confirmation before writing. |
| `--split` | Plan mergeable Pull Request slices from the current branch's changes instead of from findings. It accepts only `--auto`, `--base`, and `--visual`, and may answer KEEP AS ONE and write nothing. |
| `--visual` | Also write `PR_PLAN_INDEX.html`, an interactive page of the whole plan set. See [Visual Reports](../visual-reports.md). |
| `--all` | With `--reconcile`, update every plan in the index that is not `DONE` or `SUPERSEDED`. Cannot be combined with plan files. |
| `--worktree <path>` | With `--reconcile`, read the implementation from this Git worktree instead of the directory that holds the plans. |
| `--source <ref>` | With `--reconcile`, compare the plans against this branch or commit instead of the worktree's checked-out files. |
| `--base <ref>` | Compare against `<ref>` instead of the detected base branch. Only with `--split` or `--reconcile`. |

## Examples

```text
# Plan the findings from the reports in the project root
/trackbed:code:breakdown-findings

# Plan the findings from one report and skip the theme confirmation
/trackbed:code:breakdown-findings --auto REVIEW_OVERVIEW.md

# Plan how to split the current branch into smaller Pull Requests
/trackbed:code:breakdown-findings --split --base main

# Update one plan against the branch that implemented it
/trackbed:code:breakdown-findings --reconcile PR_PLAN_W01A_AUTH_CLEANUP.md --source feature/auth-cleanup
```

## What you get

- In the project root: one `PR_PLAN_<label>_<SLUG>.md` per theme, `PR_PLAN_INDEX.md` with the order, dependencies, and status of the plans, and `PR_PLAN_REJECTIONS.md` with the findings left out and why. A label such as `W01A` gives the wave and the lane: plans in the same wave can run in parallel.
- Plans that each stand alone, so you can hand one to an agent without the source report or the other plans.
- A closing summary with `PLANS GENERATED`, `THINGS I DIDN'T TOUCH`, and `POTENTIAL CONCERNS`, then a `LAUNCH SHEET:` with the command to start each plan and what the waiting plans wait on.
- A set of more than four plans may also leave scratch drafts under the Git-ignored `.context/breakdown-findings/`.

Run each plan with `trackbed:code:plan-to-pr`. Plans from `--split` are implemented by hand, each in its own worktree, and then updated with `--reconcile`. See the [shipping guide](../shipping.md#plan-to-pull-request).
