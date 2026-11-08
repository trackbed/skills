# gh-stack CLI: agent rules and reference

<!-- Adapted from github/gh-stack skills/gh-stack/SKILL.md at commit a1b4a3d4d0bcde9ec3a78ab99b2d63af121857a9 under the MIT License. Full notice: github-gh-stack-LICENSE. -->

Condensed operating reference for driving `gh stack` non-interactively. Every command must be invoked so it cannot prompt — a prompt or TUI hangs the session.

## Non-interactive invocation rules

| Rule | Why |
| --- | --- |
| Validate user-supplied branches with `git check-ref-format --branch`, keep operands in arrays, and invoke them with quoted expansion such as `"${STACK_BRANCHES[@]}"` | Git ref syntax permits shell metacharacters. Never interpolate operands into a command string or pass them through `eval`/`sh -c`. |
| Always pass branch names as positional arguments to `init`, `add`, and `checkout` | Running them bare opens interactive prompts. Names are used verbatim — never prefixed or transformed (`refactor/foo` stays `refactor/foo`). |
| Always use `gh stack submit --auto` | Without `--auto`, submit opens a per-PR title editor. `--auto` creates new PRs as **drafts**; add `--open` to mark them ready for review. |
| Always use `gh stack view --json` | Bare `view` (and `view --short`) launch a TUI. |
| Never use `gh stack modify` | TUI-only. Record the existing trunk, then restructure by tearing down and rebuilding: `gh stack unstack` (PRs and branches survive), make the structural change with plain git, then `gh stack init --base <recorded-trunk> <branches bottom-to-top>`. If a repo is stuck mid-modify, `gh stack modify --abort` restores it. |
| Never run bare `gh stack checkout`, `switch` | Interactive pickers. Use a resolved stack number for remote checkout or a validated nonnumeric branch for local navigation. A PR number or PR URL can select another stack with that number. A stack-number import selects the top branch; restore the recorded entry branch before retrying the caller. If local tracking conflicts with the remote stack, run `gh stack unstack --local` first, then retry. |
| Run `gh stack merge` only with a resolved target, `--yes`, and one validated method flag (`--merge`, `--squash`, or `--rebase`) | Use the stack number for the whole stack. A partial PR target requires a successful collision check from `merge-target.md`; stop and ask on a collision. Never use an unchecked PR number. |
| Preserve supplied PR identifiers in `gh stack link` | A leading bare number requires local-branch and stack-number collision checks from `link-target.md`. Explicit PR URLs bypass numeric selection. Retain the original array; use a nonnumeric branch first only for supplied branch input. |
| Multiple remotes: set `git config remote.pushDefault origin` or pass `--remote <name>` | `push`, `submit`, `sync`, `rebase`, and `link` accept `--remote`; `checkout` and `trunk` rely on `remote.pushDefault` and error without it. |
| Pre-configure `git config rerere.enabled true` | `init` enables rerere and may prompt on first run; pre-setting skips the prompt and lets repeat conflicts auto-resolve. |
| Stage and commit with plain `git add` / `git commit` | Full control over which changes land in which layer. `gh stack add -Am "msg" branch` exists as a one-shot shortcut but bypasses deliberate staging. |

A clean "remote is ahead" update can fast-forward automatically. Active branch divergence is not reconciled by `sync`; run the shared stack rewrite preflight required by the owning skill before syncing. Pruning merged branches only happens with an explicit `--prune`.

Clear `GH_STACK_NO_ATOMIC` for pushes and syncs that require atomic Git ref updates. PR/API updates are separate; never retry with `--no-atomic`.

## Command map

| Task | Command |
| --- | --- |
| Create a stack (first branch, or several bottom-to-top) | `gh stack init --base <resolved-trunk> <branch...>` |
| Adopt existing local branches into a stack | `gh stack init --base <resolved-trunk> <existing-branch...>` (existing branches adopted, missing ones created) |
| Add a branch on top | `gh stack add <branch>` (must be on the topmost branch; exit 5 otherwise — `gh stack top` first) |
| Push all branches | `env -u GH_STACK_NO_ATOMIC gh stack push` (`--force-with-lease --atomic`, skips merged/queued) |
| Push + create/update chained PRs + link stack | `gh stack submit --auto` (drafts) / `gh stack submit --auto --open` |
| Routine sync (fetch, cascade-rebase, push, PR state) | `env -u GH_STACK_NO_ATOMIC gh stack sync` (`--prune` to delete local branches for merged PRs) |
| Cascade rebase only | `gh stack rebase` (`--upstack`, `--downstack`, `--no-trunk`, `--continue`, `--abort`) |
| Restack above the current branch after editing it | `gh stack rebase --upstack --no-trunk`, then `env -u GH_STACK_NO_ATOMIC gh stack push` |
| Inspect state (JSON to stdout) | `gh stack view --json` |
| Navigate | `gh stack up [n]` / `down [n]` / `top` / `bottom` / `trunk` |
| Check out a stack from GitHub | `gh stack checkout "$STACK_NUMBER"` (resolved positive stack number; stop if unavailable) |
| Stack PRs managed by external tools (jj, Sapling, git-town, worktree chains) | `gh stack link "${STACK_ITEMS[@]}"` after the `link-target.md` guard (bottom to top; preserves supplied PR identifiers) |
| Atomically merge the whole stack or a checked partial target | `gh stack merge "$MERGE_TARGET" --yes <--merge \| --squash \| --rebase>` (resolve through `merge-target.md` first) |
| Remove stack grouping (PRs/branches survive) | `gh stack unstack` (`--local` keeps the GitHub stack) |

## Exit codes

| Code | Meaning | Response |
| --- | --- | --- |
| 0 | Success | Proceed. |
| 1 | Generic error | Read stderr. |
| 2 | Not in a stack / stack not found | Report the missing stack. Resolve the trunk and use `gh stack init --base <resolved-trunk> <branch...>` to create one, or resolve a positive stack number before `gh stack checkout "$STACK_NUMBER"`. Never guess a PR number. |
| 3 | Rebase conflict | Recovery depends on the command: `sync` restores all branches, so start a fresh `gh stack rebase`; `rebase` leaves its session active, so resolve/stage files and run `gh stack rebase --continue` directly. Give up with `gh stack rebase --abort`. |
| 4 | GitHub API failure | Check `gh auth status`, retry once. |
| 5 | Invalid arguments | Fix the invocation. |
| 6 | Branch belongs to multiple stacks | Check out a non-shared branch first. |
| 7 | Rebase already in progress | `gh stack rebase --continue` or `--abort`. |
| 8 | Stack locked by another gh-stack process | Wait (lock times out after ~5s) and retry. |
| 9 | Stacked PRs not enabled on this repository | Stop and tell the user: the repository needs stacked-PRs preview access (waitlist: gh.io/stacksbeta). Fall back to a manual branch chain or a single PR. |
| 10 | Interrupted `modify` session | `gh stack modify --abort` to restore. |

## `view --json` shape

Status messages go to **stderr** (with `✓ ✗ ⚠ ℹ` prefixes); JSON goes to **stdout**.

```json
{
  "trunk": "main",
  "currentBranch": "api-routes",
  "branches": [
    {
      "name": "auth",
      "head": "<sha>",
      "base": "<parent sha at last sync>",
      "isCurrent": false,
      "isMerged": true,
      "isQueued": false,
      "needsRebase": false,
      "pr": {
        "number": 42,
        "url": "https://github.com/o/r/pull/42",
        "state": "MERGED"
      }
    }
  ]
}
```

`pr` is omitted when no PR exists; `pr.state` is `OPEN`, `MERGED`, or `QUEUED`. `needsRebase: true` means the parent is no longer an ancestor — run `gh stack rebase`. Useful probes:

```bash
gh stack view --json | jq -r '.branches[] | select(.pr.state == "OPEN") | .pr.url' # open PR URLs
gh stack view --json | jq '[.branches[] | select(.needsRebase)] | length'          # branches needing rebase
gh stack view --json | jq '[.branches[] | .isMerged] | all'                        # fully merged?
```

## Server-side behavior worth knowing

- The stack is a GitHub object, not CLI state: reviewers get a Stack Map UI, and `gh stack link` / the web UI can manage stacks without local tracking.
- Branch protection, CODEOWNERS, and CI evaluate **as if each PR targeted the stack base** (e.g. `main`), not its direct parent. Actions workflows see `github.event.pull_request.stack` (position, size, base, number).
- Merging a mid-stack PR lands it **and every unmerged PR below it** atomically; the PRs above are re-targeted and rebased automatically. With a merge queue, all stack PRs enter the queue together.
- Squash merges are handled: `env -u GH_STACK_NO_ATOMIC gh stack sync` detects them and replays remaining branches with `git rebase --onto`.
- Limits: strictly linear stacks (one parent, one child), no cross-fork stacks, linear history required, and auto-merge unavailable. In v0.1.0 or newer, `gh stack merge "$MERGE_TARGET" --yes <method-flag>` runs without prompting after resolving the target through `merge-target.md`; it cannot bypass repository merge requirements. `submit` cannot set custom PR titles/bodies in `--auto` mode — edit them afterward through `gh api --method PATCH repos/{owner}/{repo}/pulls/<number> --hostname <pr-host>`, deriving `<pr-host>` from that PR's URL; stop if the hostname cannot be determined.
