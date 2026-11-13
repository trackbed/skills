# pr:create

Use it when your branch is ready and has no Pull Request yet. It commits your uncommitted work, rewrites unpublished commits into a clean sequence unless they are already well formed, writes a title and description, pushes the branch, and opens the Pull Request assigned to you. It runs without asking; pass `--manual` to keep the prompts. For a branch stacked on another feature branch, use `trackbed:pr:stack`.

## Before you run it

- `gh` is installed and authenticated, and the repository has an `origin` remote.
- The branch has changes compared with the base branch, committed or not. It has no open Pull Request and is not part of a stack.
- No merge, rebase, cherry-pick, or revert is in progress.

## Options

| Option | Effect |
| --- | --- |
| `--manual` | Ask how to handle uncommitted work and how to structure the commits, and confirm before the commit rewrite and before publishing. |
| `--draft` | Open the Pull Request as a draft. Without it, the Pull Request is ready for review. |
| `--rebase` | First rebase the branch onto the base branch and force-push it through `trackbed:pr:rebase`, then continue. |
| `--base <branch>` | Open the Pull Request against `<branch>` instead of the detected base branch. See [Base Branch](../shipping.md#base-branch). |
| `--linear-issue <ISSUE-ID>` | Use this Linear issue for the description and its closing line, instead of the ID read from the branch name. |
| `--independent-review-line <line>` | Put this one-line record of an independent review in the description unchanged. Set by `trackbed:linear:issue-to-pr` when it delegates; you rarely need it. |
| `--require-generated-description` | Stop when no title and body can be generated, even with `--manual`, and never skip the commit rewrite on a new branch. Set by `trackbed:linear:issue-to-pr` and `trackbed:code:plan-to-pr` when they delegate; you rarely need it. |
| `--authorize-history-rewrite` | With `--manual`, skip the confirmation before the commit rewrite. |

## Examples

```text
# Publish the current branch as a Pull Request, without prompts
/trackbed:pr:create

# Open a draft and decide each step yourself
/trackbed:pr:create --draft --manual

# Rebase onto the base branch first, then publish
/trackbed:pr:create --rebase

# Target the development branch and link a Linear issue
/trackbed:pr:create --base development --linear-issue DISC-202
```

## What you get

- An open Pull Request on GitHub, assigned to you, with a Conventional Commits title and a generated description.
- The branch pushed to `origin`, with your uncommitted work committed. On a branch that is not on the remote yet, the commits are rewritten unless they are already well formed, and the old history stays on a local backup branch. Commits already on the remote are never rewritten.
- A feature branch created for you when you start on the base branch or a detached `HEAD`.
- A closing message with the Pull Request URL, what happened to uncommitted work, and the commits included.

When a step fails before the push, your branch and uncommitted work are put back as they were when that is safe. Next, run `/trackbed:pr:fix-ci` to get the checks green. The [shipping guide](../shipping.md#publishing-a-pull-request) covers branches that already exist on the remote.
