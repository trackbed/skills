# gh-stack exit codes and cross-worktree rules

`trackbed:pr:stack` and `trackbed:pr:rebase` both follow this reference whenever they run gh-stack. Since v0.2, `gh stack rebase` and `gh stack sync` rebase each stack branch inside whichever worktree has it checked out, fast-forward a checked-out trunk in its own worktree, and restore those worktrees if something fails. gh-stack also keeps one lock and one paused-rebase record for the whole clone, not for each worktree. Each Conductor workspace is a worktree of the same clone, so a stack command run in one workspace can rewrite another workspace's checkout while an agent is working there.

## Exit codes

| Code | Meaning | Response |
| --- | --- | --- |
| 0 | Success | Continue. |
| 1 | Generic error | Read stderr. A `rerun with --accept-base-change` message is a base change; follow **Base changes** below. |
| 2 | Not in a stack, or stack not found | Report the missing stack. Never guess a PR number or a stack number. |
| 3 | Rebase conflict | Follow **Conflicts** below. |
| 4 | GitHub API failure | Check `gh auth status` and retry once. |
| 5 | Invalid arguments | Fix the invocation. |
| 6 | The branch belongs to several stacks, or the remote is ambiguous | Check out a branch that belongs to one stack, or pass `--remote`. |
| 7 | A rebase is already paused | Follow **Paused rebases** below. |
| 8 | Lock held | Another gh-stack process in any worktree of this clone holds the lock, possibly a session in another workspace; gh-stack waits about 5 seconds before giving up. Retry once. If it fails again, stop and report that another workspace may be running a stack command. |
| 9 | Stacked PRs are not enabled for the repository | Stop and tell the user. Fall back to a manual branch chain or a single PR. |
| 10 | An interrupted `modify` session needs recovery | Stop and report. Run `gh stack modify --abort` only on the user's approval. |

## Before every rebase or sync: name the other workspaces

Before every `gh stack rebase` and `gh stack sync`, after the owning skill's stack rewrite preflight, list the stack branches that the command would change in another worktree. `--continue` and `--abort` are not new commands and need no new preflight. Pass `--no-trunk` when the command itself uses `--no-trunk`:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/list-stack-worktrees.sh" || exit 1
```

The script prints one `<kind> <branch> <worktree-path>` line, tab-separated, for each unmerged layer (`layer`) and the trunk (`trunk`) checked out in a worktree other than the current one. It lists every unmerged layer, which also covers `--upstack` and `--downstack`. A nonzero exit means the set is unknown: stop rather than treat it as empty.

When the script exits 0 and prints nothing, run the command. Otherwise:

1. Name every listed workspace path with its branch, and say that gh-stack may rebase that branch in place there, or fast-forward the trunk there.
2. Warn that any agent session in those workspaces should be idle and their worktrees clean until the command finishes, because gh-stack rewrites the files under them.
3. Ask: `Run this stack command, which changes the listed workspaces?` Run it only after the user confirms, and record the confirmed paths as `CONFIRMED_STACK_WORKTREES`.

This confirmation applies in every mode, including auto and `--force-push`; no mode bypasses it. In a non-interactive run, stop before the command and report the listed workspaces instead of asking. A run is non-interactive when it is a delegated child, such as `trackbed:pr:rebase --force-push` under `trackbed:pr:fix-ci`, or when the host cannot ask the user. A confirmation covers one command and its `--continue` rounds. Before the next `rebase` or `sync`, run the script again and ask again when the list names a workspace that the user has not confirmed.

## Conflicts

gh-stack pauses a conflict in the worktree that has the conflicting branch checked out, which may be another workspace. Keep its output. When it prints `Conflict worktree: <path>`, set `CONFLICT_WORKTREE` to that path and resolve the conflict there:

```bash
git -C "$CONFLICT_WORKTREE" diff --name-only --diff-filter=U
# Resolve the markers in each listed file under "$CONFLICT_WORKTREE", then:
git -C "$CONFLICT_WORKTREE" add -- <file>
gh stack rebase --continue
```

Without that line, the conflict is in the current worktree; set `CONFLICT_WORKTREE` to its root. gh-stack accepts `gh stack rebase --continue` from any worktree of the clone, so run it from the current one.

- If `<path>` is neither the current worktree nor in `CONFIRMED_STACK_WORKTREES`, run `gh stack rebase --abort` and report the path and branch instead of resolving it.
- Inside another workspace, only edit and `git add` the conflicted files. Never stash, commit, reset, check out, or clean there.
- `gh stack sync` restores every branch before it returns exit 3, so it leaves nothing paused. The owning skill then starts a fresh `gh stack rebase`, which needs its own stack rewrite preflight and this section's preflight.

## Paused rebases

gh-stack records one paused rebase for the whole clone, so a session in any workspace can see it and continue or abort it. Run `gh stack rebase --continue` or `gh stack rebase --abort` only for a rebase that this session started and saw pause with exit 3. When a command returns exit 7, or this session finds a paused rebase it did not start, stop and report gh-stack's message. Never continue or abort it, because the session that started it may still be resolving it.

## Base changes

When GitHub retargets a stack because its base branch was deleted, `gh stack rebase` and `gh stack sync` move the stack onto the new base. If gh-stack cannot show that the old base merged, it stops with `stack not rebased; rerun with --accept-base-change`, because moving would drop the old base's unmerged commits from the stack.

- Pass `--accept-base-change` only when the user explicitly approves it for this stack in this run, after you name the old base and the new base and explain that the old base's unmerged commits leave the stack. This applies in every mode, including auto and `--force-push`; a non-interactive run stops and reports.
- Record the trunk before every `rebase` or `sync` with `gh stack view --json | jq -er '.trunk | select(type == "string" and length > 0)'` and read it again afterwards. If either read fails, report the trunk as unknown instead of comparing. When it changed, report the old and the new trunk, whether or not the flag was passed: gh-stack also moves a stack whose old base did merge.
