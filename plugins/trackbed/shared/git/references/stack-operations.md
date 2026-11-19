# gh-stack exit codes and cross-worktree rules

`trackbed:pr:stack` and `trackbed:pr:rebase` both follow this reference whenever they run gh-stack. Since v0.2, `gh stack rebase` and `gh stack sync` rebase each stack branch inside whichever worktree has it checked out, fast-forward a checked-out trunk in its own worktree, and restore those worktrees if something fails. gh-stack also keeps one lock and one paused-rebase record for the whole clone, not for each worktree. Each Conductor workspace is a worktree of the same clone, so a stack command run in one workspace can rewrite another workspace's checkout while an agent is working there.

## Exit codes

| Code | Meaning | Response |
| --- | --- | --- |
| 0 | The command finished | After `sync` or `merge`, check the outcome under **Sync outcomes** or **Merge outcomes** below before reporting success; both can exit 0 without syncing or landing anything. Otherwise continue. |
| 1 | Generic error | Read stderr. A `rerun with --accept-base-change` message is a base change; follow **Base changes** below. |
| 2 | Not in a stack, or stack not found | Report the missing stack. Never guess a PR number or a stack number. |
| 3 | Rebase conflict, or a merge conflict on GitHub | After `rebase` or `sync`, follow **Conflicts** below. After `merge`, follow **Merge outcomes** instead. |
| 4 | GitHub API failure | After `merge`, never retry; follow **Merge outcomes**. Otherwise check `gh auth status` and retry once. |
| 5 | Invalid arguments | Fix the invocation. |
| 6 | The branch belongs to several stacks, or the remote is ambiguous | Check out a branch that belongs to one stack, or pass `--remote`. |
| 7 | A rebase is already paused | Follow **Paused rebases** below. |
| 8 | Lock held | Another gh-stack process in any worktree of this clone holds the lock, possibly a session in another workspace; gh-stack waits about 5 seconds before giving up. Retry once. If it fails again, stop and report that another workspace may be running a stack command. |
| 9 | Stacked PRs are not enabled for the repository | Stop and tell the user. Fall back to a manual branch chain or a single PR. |
| 10 | An interrupted `modify` session needs recovery | Stop and report. Run `gh stack modify --abort` only on the user's approval. |

## Before every rebase or sync: name the other workspaces

Before every `gh stack rebase` and `gh stack sync`, after the owning skill's stack rewrite preflight, list the stack branches that the command would change in another worktree. `--continue` and `--abort` are not new commands and need no new preflight. Pass `--no-trunk` when the command itself uses `--no-trunk`:

```bash
"${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.1.1/scripts/list-stack-worktrees.sh" || exit 1
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

## Sync outcomes

Replace the combined `gh stack sync` command with these separate steps. Never run it as a fallback: its internal fetch/push cannot consume the original frozen leases.

1. Before fetching or rewriting, capture the snapshot under `stack-rewrite-safety.md`. Read the local stack and its linked GitHub stack inventory read-only; if GitHub has added, removed, reordered, or retargeted layers, stop before rewriting and use the owning skill's guarded checkout/link reconciliation first. Begin a fresh authorized snapshot after reconciliation; do not adopt new layers into an existing authorization.
2. Run the other-workspace preflight and base-change gates above, then run the snapshot's `prepare` command. It integrates behind-only branches without discarding local commits and stops on divergence.
3. Record the trunk, run `gh stack rebase --remote "$STACK_REMOTE"`, handle conflicts and paused sessions under the rules above, and verify the resulting patches. Pass `--accept-base-change` only with the existing explicit approval. A failed rebase never proceeds to publication.
4. Run the snapshot's atomic `publish` command only after the owning skill's publication authorization. Require `STACK_PUBLISHED=true` (an empty active inventory has nothing to publish). Verify every local active tip still equals its remote head at the frozen endpoint.
5. Update existing PR bases bottom-to-top with `gh pr edit <PR-URL> --base <parent-branch>`, starting from the resolved trunk, and link the existing PR URLs with `gh stack link <PR-URLs bottom-to-top>` when at least two remain. Use explicit URLs, never branch operands: this phase updates GitHub metadata and must not push or open replacement PRs. Re-read PR base/head identities and the linked stack order before reporting success. An API failure retains the snapshot and reports `branches published; metadata incomplete`; never rerun publication to repair metadata.
6. For an explicitly requested pruning sync after merged PRs, delete only local branches verified merged and not checked out in any worktree, using `git branch -d -- <branch>`. Leave checked-out branches and gh-stack's merged-layer metadata in place and report them; do not force-delete or change another workspace's checkout. Skip queued branches until GitHub shows them merged.

Report `STACK_SYNCED=true` only when the frozen publication and PR metadata checks both pass. Otherwise say which phase failed, what local fast-forwards or rewrites remain, whether branches were published, and the retained snapshot path. A rejected push is not a successful sync. This split path keeps Git ref atomicity distinct from API updates and preserves all existing collaborator, cross-worktree, conflict, and base-change approvals.

## Merge outcomes

A `gh stack merge` that exits 0 may only have added the PRs to a merge queue, and one that exits 4 may still be running on GitHub. The owning skill captures the merge's output as `MERGE_OUTPUT` and prints its exit code as `MERGE_STATUS`. After every merge, whatever its exit code, read the state of each PR through the target. Run this check in the same Bash call as the merge-target resolution and the merge, because it reads their `TARGET_STACK_JSON` and `TARGET_PR_NUMBER` and shell variables do not carry over to the next call:

```bash
: "${TARGET_STACK_JSON:?Run the merge-target resolution in this Bash call first}"
: "${TARGET_PR_NUMBER:?Run the merge-target resolution in this Bash call first}"
MERGE_PRS=$(printf '%s\n' "$TARGET_STACK_JSON" | jq -er --argjson pr "$TARGET_PR_NUMBER" '
  .[0].pull_requests | (map(.number) | index($pr)) as $i
  | if $i == null then error("Target PR is not in the stack") else .[:$i + 1][].number end
  | if type == "number" and . > 0 and floor == . then . else error("Invalid PR number") end') || exit 2
MERGED_PRS="" QUEUED_PRS="" OPEN_PRS=""
while IFS= read -r PR_NUMBER; do
  PR_STATE=$(gh api graphql -F owner='{owner}' -F repo='{repo}' -F number="$PR_NUMBER" -f query='
    query($owner: String!, $repo: String!, $number: Int!) {
      repository(owner: $owner, name: $repo) { pullRequest(number: $number) { state isInMergeQueue } }
    }' --jq '.data.repository.pullRequest | if .state == "MERGED" then "merged"
      elif .state == "OPEN" and .isInMergeQueue == true then "queued"
      elif .state == "OPEN" then "open" else "closed" end') || exit 2
  case "$PR_STATE" in
    merged) MERGED_PRS="$MERGED_PRS #$PR_NUMBER" ;;
    queued) QUEUED_PRS="$QUEUED_PRS #$PR_NUMBER" ;;
    open) OPEN_PRS="$OPEN_PRS #$PR_NUMBER" ;;
    *) OPEN_PRS="$OPEN_PRS #$PR_NUMBER($PR_STATE)" ;;
  esac
done <<< "$MERGE_PRS"
printf 'MERGED_PRS=%s\nQUEUED_PRS=%s\nOPEN_PRS=%s\n' "${MERGED_PRS# }" "${QUEUED_PRS# }" "${OPEN_PRS# }"
```

Report the merged and the queued PRs separately; never call a queued PR merged. A nonzero exit from this block means the states are unknown: report that and stop without a retry or a sync. Then act on the states and `MERGE_STATUS`:

- **Every PR merged:** the merge landed, whatever the exit code. Run the owning skill's pruning sync and its **Sync outcomes** check.
- **Some PRs queued, none open:** the merge queue owns them now. Do not run the pruning sync; tell the user to run it once the queue has merged them.
- **Exit 3:** GitHub reported a merge conflict, and stack merges are atomic, so nothing landed. Restack before merging again: run the owning skill's routine sync and its **Sync outcomes** check, resolve any conflicts under **Conflicts**, then resolve the merge target again.
- **Exit 4 with PRs still open:** a merge may still be running on GitHub, and running it again can submit it twice. Never re-run the merge yourself: report the states and gh-stack's message, and tell the user to check the PRs on GitHub before merging again. A Merging call that printed `MERGE_STARTED=true` but ends without printing `MERGE_STATUS`, for example because the Bash tool timed out, counts as exit 4: never re-run it, and read the states by running the merge-target resolution and this check alone in a fresh call. A call that stopped before printing `MERGE_STARTED=true` never ran the merge: follow the stop message from the target resolution or method check.
- **Any other open PR:** report gh-stack's message and the open PRs, and stop.
