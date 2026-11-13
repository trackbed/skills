# git:recreate-commits

Use it to turn a branch's working commits into a clean sequence that reads like a story for reviewers. The final content of the branch stays exactly the same; only the commits change. It rewrites history and, when the branch exists on a remote, force-pushes with a lease. It runs without asking by default, so do not use it on merged or shared branches. `trackbed:pr:create` runs it for you when it publishes a branch.

## Before you run it

- The working tree is clean, including untracked files.
- You are on a feature branch, not the base branch or a detached HEAD.
- A branch in a gh-stack stack needs `--manual` or `--authorize-history-rewrite`.

## Options

| Option | Effect |
| --- | --- |
| `--manual` | Ask for the granularity on a large diff, and confirm before the reset and before any force-push. |
| `--coarse` | One commit per major grouping, typically 5 to 15 commits. Cannot be combined with `--granular`. |
| `--granular` | The finest split: each commit adds one function, type, config entry, or test. For very large changes where 100 or more commits are appropriate. |
| `--base <branch>` | Compare against `<branch>` instead of the detected base branch. Commits after the point where the branch left it are rewritten. |
| `--base-commit <oid>` | Pin the base to this full commit ID while keeping the branch named by `--base`. For workflows that delegate to this skill, such as `trackbed:pr:create`; you rarely need it. |
| `--backup-ref <branch>` | Name the recovery branch yourself. Mainly for `trackbed:pr:create`, which sets it when it delegates. |
| `--after <commit>` | Rewrite only the commits after `<commit>` and keep earlier history. The commit must be an ancestor of `HEAD`. |
| `--force-backup` | Let the run replace an existing backup branch that points at a different commit. Inspect that backup first. |
| `--require-unstacked` | Stop before the rewrite if the branch is part of a stack. Set by `trackbed:pr:create` when it delegates; you rarely need it. |
| `--no-push` | Rewrite the local branch and leave the remote alone. `trackbed:pr:create` always sets it. |
| `--authorize-history-rewrite` | Skip the confirmations before the reset and the push. Required to rewrite and publish a stack without `--manual`. |

## Examples

```text
# Rewrite the branch's commits and update the remote
/trackbed:git:recreate-commits

# Be asked before the reset and before the force-push
/trackbed:git:recreate-commits --manual

# Rewrite only the last few commits, locally
/trackbed:git:recreate-commits --after HEAD~5 --no-push

# One commit per major grouping, against develop
/trackbed:git:recreate-commits --coarse --base develop
```

## What you get

- New commits on the current branch, each holding one idea, with a final tree identical to the one you started with.
- A backup branch, `<branch>-recreate-backup` by default, at the original tip. `git reset --hard` to it undoes the rewrite.
- A force-push with a lease when the branch exists on a remote, unless you passed `--no-push`. In a stack, the branches above are rebased and the whole stack is pushed.
- Your local copy of the base branch, if you have one, fast-forwarded to its remote, unless `--base-commit` pins the base.
- A closing summary with `CHANGES MADE`, `THINGS I DIDN'T TOUCH`, and `POTENTIAL CONCERNS`.

The [shipping guide](../shipping.md#rewriting-history) lists what is checked before anything is reset.
