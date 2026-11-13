# pr:fix-ci

Use it on a branch whose open Pull Request has failing checks or review feedback to act on. It reads the failing logs and the review comments, makes targeted fixes, commits and pushes them, waits for CI, and repeats until the checks pass and the feedback is handled. By default it runs unattended: it may rebase a branch that is behind its base, and it rewrites history at the end to fold the fix commits into your own commits. It posts no replies; for those, use `trackbed:pr:github-review-reply`.

## Before you run it

- `gh` is installed and authenticated.
- The current branch has an open Pull Request.

## Options

| Option | Effect |
| --- | --- |
| `--fixup` | Fold each fix into the branch commit that last touched the file instead of adding fix commits, then force-push with a lease. Files that no branch commit touched get a new commit. |
| `--manual` | Ask before rebasing a branch that is behind its base, and let you choose what happens to the fix commits after CI passes. |
| `--no-consolidate` | Leave the `[FIX PIPELINE]` commits as they are after CI passes, and ask before rebasing a branch that is behind its base. |
| `--rebase` | When the branch is behind its base, rebase and force-push through `trackbed:pr:rebase` before fixing CI, without asking. |
| `--no-rebase` | When the branch is behind its base, fix CI on the current base without asking and never rebase in this run. |
| `--scope-plan <archived-plan>` | Keep every fix inside the files that an archived plan from `trackbed:code:plan-to-pr` lists as in scope, and stop when a fix needs another file. Requires `--no-consolidate` and excludes `--fixup`, `--rebase`, and `--no-rebase`. Set by that skill when it delegates; you rarely need it. |

## Examples

```text
# Fix CI and review feedback, then fold the fix commits into the branch's commits
/trackbed:pr:fix-ci

# Keep the fix commits separate and decide about a rebase yourself
/trackbed:pr:fix-ci --no-consolidate

# Rebase a branch that is behind its base first, without being asked
/trackbed:pr:fix-ci --rebase

# Amend the original commits as you go instead of adding fix commits
/trackbed:pr:fix-ci --fixup
```

## What you get

- Fix commits pushed to the Pull Request, each prefixed `[FIX PIPELINE]`. Only the files a fix changed are committed; uncommitted work you had before the run stays untouched.
- After CI passes, the fix commits folded into the original commits and the branch force-pushed with a lease, unless you passed `--no-consolidate` or chose to keep them under `--manual`.
- No silenced checks: it does not skip hooks, add suppression comments, or disable tests without your approval.
- A closing line, `CI remediation JSON: [...]`, that lists each failure and feedback item it looked at, what it decided, and why.

It stops and asks you when the same failure persists after three attempts, when feedback needs your decision, or when a failure is unrelated to the branch. The [shipping guide](../shipping.md#unattended-by-default) explains the unattended default.
