# Author Mode (`--mine`)

Answer "where does each of my open Pull Requests stand, and what does it need next?" Each Pull Request gets exactly one state and one next action, computed by plain code that runs no model. A timer can run the same script later and read the same JSON.

- **Read-only.** Never rebase, push, comment, approve, merge, re-run a job, or start a workspace. Report, and let the user pick the next step.
- **No Conductor steps.** Steps 5 and 7 of the reviewer view do not apply.
- **Fresh state only.** Every claim comes from a snapshot taken this turn; give its time in UTC.

`{author-script}` is the resolved path the skill passes in.

## Step 1: Take a Snapshot

Run the script with the user's other arguments, each one single-quoted. `--mine` itself is not passed:

```bash
python3 "{author-script}" [--repo OWNER/NAME | --all-repos] [--since ISO-8601]
```

It needs `gh` (authenticated) and `git`. With `--all-repos` and many open Pull Requests it can take a few minutes, so give it a timeout of at least ten minutes. It prints one JSON document on one line; parse it and never `eval` it.

- Exit 0 and `"status": "ok"`: the snapshot.
- Exit 1 and `"status": "error"`: GitHub could not be read. Report `message` and stop; never rebuild the report by hand.
- Exit 2: malformed arguments, or no GitHub repository in the current directory without `--repo` or `--all-repos`. Nothing is printed on stdout; show the reason from stderr and stop.

Carry every entry of `warnings` into the report's notes.

## The Output

The top level:

| Field | Meaning |
| --- | --- |
| `schemaVersion` | `1`. A change that removes or renames a field or a state raises it. |
| `status` | `ok` or `error`; `message` says why on `error`. |
| `checkedAt` | Snapshot time in UTC, taken before the first search. Pass it as the next `--since`. |
| `me` | Your GitHub login. |
| `scope` | The repository searched, or `all` with `--all-repos`. |
| `localRepository` | The GitHub repository of the current directory, or null. Only its worktrees are inspected. |
| `prs` | One entry per open Pull Request you authored, in report order (below). |
| `closed` | With `--since`: your Pull Requests that closed since then, each with `pr`, `url`, `title`, `state` (`MERGED` or `CLOSED`), and `at`. Empty without it. |
| `warnings` | Searches capped at 1,000 results, Pull Requests with more than 100 checks or review threads, workflow runs that could not be listed, and a current repository, local worktrees, or protected branches that could not be read. |

Each entry of `prs`:

| Field | Meaning |
| --- | --- |
| `pr`, `url`, `title` | `OWNER/NAME#N`, its link, and its title. |
| `state` | One of the states below. |
| `next` | `owner`, `action`, and `skill`, from the next-action table below. |
| `worktree` | `path` of the eligible local worktree, or null with `reason` saying why there is none. |
| `base`, `basePr` | The base branch, and the number of the open Pull Request in the same repository whose head branch is that base, or null. As in the reviewer view, a base that is the default branch or that branch protection or a ruleset covers is never a stack. |
| `headBranch`, `head` | The head branch and the published head commit. |
| `mergeable`, `mergeStateStatus`, `reviewDecision` | GitHub's values, after the one re-read of an `UNKNOWN` merge state. |
| `ci` | `state` (`failing`, `running`, `green`, or `none`), the `failing` and `running` check names, and `superseded`, the number of checks dropped because a newer run replaced theirs. |
| `threads` | `ai` and `human`: unresolved review threads you have not answered since the latest reviewer comment. |

## States

Rules apply in this order, and the first match wins.

| # | `state` | Applies when |
| --- | --- | --- |
| 1 | `draft` | The Pull Request is a draft. |
| 2 | `conflicts` | `mergeable` is `CONFLICTING` or the merge state is `DIRTY`. |
| 3 | `ci-failing` | A check that counts failed or was cancelled. Checks from a run that a newer run of the same workflow and event on the same head replaced do not count; a skipped run replaces nothing. Past the first 100 checks, a failing rollup counts. |
| 4 | `ai-feedback` | An unresolved review thread whose reviewer comments all come from bot or app accounts, with no reply from you after the latest of them. |
| 5 | `human-feedback` | An unresolved thread with feedback from a person and no reply from you after the latest reviewer comment, or `reviewDecision` is `CHANGES_REQUESTED`. |
| 6 | `ci-running` | A check is still running or pending. |
| 7 | `behind` | The merge state is `BEHIND`: branch protection wants the branch updated, and nothing else stands in the way. |
| 8 | `awaiting-review` | The merge state is `BLOCKED`: a required approval or check is missing. |
| 9 | `ready` | The merge state is `CLEAN`, `HAS_HOOKS`, or `UNSTABLE`: mergeable, green, and approved or not requiring review. `UNSTABLE` lands here only after rule 3 and rule 6 found nothing, which happens when the check GitHub counts was superseded. |
| 10 | `unknown` | GitHub still reports the merge state as `UNKNOWN` after one re-read a few seconds later, or reports a value this list does not name. |

Feedback is every visible comment you did not write; a minimized comment does not count. A thread with any comment from a person counts as `human`, even if a bot also commented.

Rules 3 to 6 do not depend on the merge state, so they still apply while it is `UNKNOWN`.

## Next Actions

| `state` | `owner` | `action` | `skill` |
| --- | --- | --- | --- |
| `conflicts`, `ci-failing`, `ai-feedback`, `behind` | `run` | `shape-up` | `trackbed:pr:shape-up`, run in `worktree.path` |
| the same, with no eligible worktree | `author` | `no-worktree` | null; `worktree.reason` says why |
| `human-feedback` | `author` | `review-reply` | `trackbed:pr:github-review-reply` |
| `ready` | `author` | `merge` | null; the merge is your decision |
| `ci-running`, `awaiting-review` | `wait` | `wait` | null |
| `unknown` | `wait` | `recheck` | null |
| `draft` | `none` | `none` | null |

A Pull Request that is behind gets `trackbed:pr:shape-up` only when nothing above `behind` applies. One with conflicts always gets it unless it is a draft, or says why there is no worktree to run it in.

`prs` is sorted by `owner` (`author`, `run`, `wait`, `none`), then by state order, then by `pr`.

## Worktree Eligibility

A worktree is eligible when it belongs to the repository in the current directory, has the Pull Request's head branch checked out, and is clean at the published head. The rules follow the batch rebase in `trackbed:pr:rebase --all-open`; unlike it, this report never changes a worktree or branch. Otherwise `path` is null and `reason` is the first that applies:

| `reason` | Meaning |
| --- | --- |
| `repository not checked out here` | The Pull Request is in another repository than the current directory's. |
| `fork head` | The head branch is in a fork. |
| `stacked on #N` | The base branch is the head of open Pull Request #N in the same repository, and it is not the default branch or a branch that branch protection or a ruleset covers, such as develop under a release Pull Request. The state is still computed; work the stack from its bottom Pull Request. |
| `worktree unavailable` | The worktree list could not be read. |
| `not checked out in a local worktree` | No worktree has the branch checked out. |
| `worktree unavailable` | The worktree is locked, prunable, missing, or unreadable, or its path has control characters. |
| `agent isolation worktree` | The worktree is under `.claude/worktrees/`. |
| `protected branches unknown` | The protected branches could not be resolved, so no worktree is named. |
| `protected branch` | The head branch is one the batch rebase protects: `main`, `master`, `develop`, the configured base branch, or the Conductor or remote default branch. |
| `operation in progress` | A merge, rebase, cherry-pick, revert, or bisect is in progress there, including a rebase that detached the worktree from the branch. |
| `dirty worktree` | It has changes, including untracked files, submodule changes, and edits to paths marked assume-unchanged or skip-worktree. |
| `local head differs from the published head` | The local branch is ahead of, behind, or diverged from the Pull Request head. |
| `stack member`, `stack membership unknown` | gh-stack or GitHub tracks the branch as part of a stack, or that could not be checked. |

## Step 2: Report

1. **One opening sentence:** the snapshot time in UTC, how many open Pull Requests you have, how many need you, how many a run can handle, and how many wait. On a recheck, what changed.
2. **A table per repository**, in the order of `prs`, with these columns in this order. Bold the rows whose `owner` is `author`.

   | Column | Holds |
   | --- | --- |
   | `PR` | The number and title, linked to `url` |
   | `State` | `state`, with the failing or running check, or the thread counts, when one name says it |
   | `Next action` | From the next-action table, such as "Run `$trackbed:pr:shape-up`", "Reply with `$trackbed:pr:github-review-reply`", "Your merge decision", "Wait for CI", "Wait for review", "Recheck", or "None (draft)". For `no-worktree`, say "No eligible worktree" and the reason. |
   | `Worktree` | `worktree.path`, or `worktree.reason` |

3. **Notes:** one line each, only where the table cannot carry it: a red Pull Request page from a superseded run (`ci.superseded > 0` while `ci.state` is `green`), a stack's base Pull Request, a merge state that stayed unknown, or a script warning.

**On a recheck,** run the script with `--since <previous checkedAt>`, keep the table layout, and call out each transition: a Pull Request that changed state, merged or closed (from `closed`), opened since the last report, or changed head. Mark new rows with 🆕.

Close by offering the first `run` row's command in its worktree, or the first `author` row's next step.
