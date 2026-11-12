# git:fixup

Use it when you have uncommitted changes that belong in commits already on your branch, such as fixes after a review. It maps each changed file to the branch commit that last touched it, checks the changes, creates fixup commits, and squashes them into their targets. This rewrites the branch's local history; it does not push. To rebuild the whole history of a branch, use `trackbed:git:recreate-commits`.

## Before you run it

- You are on a feature branch with commits ahead of its base, not on the base branch or a detached HEAD.
- Nobody else has built on the branch's current commits.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[instructions]` | Free text after the flags that steers the run, such as which files to include or how to group the changes. |

## Options

| Option | Effect |
| --- | --- |
| `--skip-tests` | Do not run the tests for the changed files. |
| `--skip-build` | Do not run the build check. |
| `--skip-lint` | Do not run the lint and format checks. |
| `--skip-all` | Skip all three checks. |
| `--no-confirm` | Ask no questions. Staged changes are included, files that match no commit are left alone, and leftover fixup commits are squashed. The run stops on a failing check, on merge commits in the branch, or when the upstream has commits you lack. |
| `--base=<branch>` | Compare against `<branch>` instead of the detected base branch. Only commits ahead of it can receive changes. |

## Examples

```text
# Check the changes, then fold them into the commits they belong to
/trackbed:git:fixup

# Skip the tests because you already ran them
/trackbed:git:fixup --skip-tests

# Run without checks and without questions
/trackbed:git:fixup --skip-all --no-confirm

# Fold in only part of the changes
/trackbed:git:fixup Only process the API controller changes
```

## What you get

- A fixup plan first: each changed file under the commit it goes into, and the files that match no commit on the branch. New files never match; you choose to commit them separately, leave them, or stop.
- The branch's commits rewritten with your changes folded in, and the resulting commit log.
- If `REVIEW_OVERVIEW.md` exists in the project root, its `**Commit:**` fields updated. The file is not committed.
- In a gh-stack stack, the branches above this one rebased locally onto the new history.
- If the squash hits a conflict, the rebase is undone and the fixup commits stay on the branch.

Nothing is pushed. If the branch was already pushed, update the remote yourself.
