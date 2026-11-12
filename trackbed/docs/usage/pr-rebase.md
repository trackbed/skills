# pr:rebase

Use it when your branch has fallen behind the branch its Pull Request targets. It rebases the current branch onto the latest base and force-pushes it with a lease; a branch in a gh-stack stack is rebased and pushed together with the rest of its stack. Typed as a command it runs unattended: it resolves conflicts itself, including risky ones, and pushes without verification or confirmation. Pass `--force-push` or `--manual` to keep those checks, and use `trackbed:pr:shape-up` to also fix CI and answer AI reviewers.

## Before you run it

- You are on a feature branch. The skill never rewrites the base branch or a protected branch such as `main`, `master`, or `develop`.
- No rebase or merge is in progress.
- Pull in commits that exist only on the remote branch first. The run stops when the two histories have diverged.

## Options

| Option | Effect |
| --- | --- |
| `--manual` | Turn off unattended mode. The run stops on a risky conflict (a migration or generated file, logic it does not fully understand, or a resolution that only deletes a block) and asks before the force-push. Cannot be combined with `--force-push`. |
| `--force-push` | Skip only the final confirmation. The run still stops on a risky conflict, and after it resolves a conflict it pushes only when the project's checks pass; otherwise it asks you. Skills that delegate a rebase, such as `trackbed:pr:fix-ci`, use this mode. |
| `--fix-ci` | After a successful push, hand over to `trackbed:pr:fix-ci`, which watches CI and pushes fixes until the Pull Request is green. Cannot be combined with `--all-open`. |
| `--base <branch>` | Rebase onto `<branch>` instead of the detected base branch. Cannot be combined with `--all-open`. |
| `--all-open` | Rebase every open Pull Request of yours whose branch is checked out in a clean local worktree and is behind its base, after one confirmation. It never resolves conflicts: a conflicting branch is left unchanged. |

## Examples

```text
# Rebase onto the Pull Request's target and force-push, unattended
/trackbed:pr:rebase

# Stop on risky conflicts and confirm before the push
/trackbed:pr:rebase --manual

# Rebase, push without the final confirmation, then fix CI until it is green
/trackbed:pr:rebase --force-push --fix-ci

# Rebase all of your open Pull Requests that are checked out locally and behind
/trackbed:pr:rebase --all-open
```

## What you get

- The branch rebased onto the latest base and force-pushed, with a lease pinned to the remote commit seen before the rebase. Nothing is rebased or pushed when the branch already contains the base.
- A summary of each conflict it resolved and how, the commit log against the base, and a `POTENTIAL CONCERNS` list of every risky conflict an unattended run continued past.
- When a conflict cannot be resolved, the rebase is aborted and the branch is restored.
- With `--fix-ci`, whether CI reached green. With `--all-open`, a plan table before the confirmation and a result table for each Pull Request after it.

The [shipping guide](../shipping.md#unattended-by-default) compares the unattended default with `--manual`.
