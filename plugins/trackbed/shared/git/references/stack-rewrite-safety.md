# Frozen stack publication

Before any stack rewrite, fetch, stash, or reset, resolve `STACK_REMOTE` to the explicit remote, otherwise `remote.pushDefault`, otherwise the sole configured remote. Stop on ambiguity. Read this contract in `trackbed:pr:stack`, `trackbed:pr:rebase`, `trackbed:git:recreate-commits`, `trackbed:git:fixup`, and every stack push path in `trackbed:pr:fix-ci`.

Use `${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.2.1/scripts/git-rewrite/stack-publication.py` for capture, preparation, and publication. It stores one push endpoint, the active branch inventory, local tips, and exact remote OIDs (including absence) in an exclusive snapshot. It never changes confirmation or authorization policy. Keep the snapshot path in run state across fresh shell invocations; never source or evaluate its JSON.

```bash
mkdir -p .context/git-rewrite
STACK_PUBLICATION_STATE=".context/git-rewrite/stack-$(python3 -c 'import uuid; print(uuid.uuid4().hex)').json"
python3 "${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.2.1/scripts/git-rewrite/stack-publication.py" capture \
  --remote "$STACK_REMOTE" --state "$STACK_PUBLICATION_STATE" || exit 1
```

After capture, run this ancestry guard before preparing or rewriting. It checks open PR branches; set `STACK_STOP_ON_BEHIND=1` for Restructure so remote-only work must be synced in a separate operation first. This fetch never changes the captured publication leases.

```bash
: "${STACK_REMOTE:?Resolve the gh-stack remote first}"
STACK_VIEW=$(gh stack view --json) || exit 1
OPEN_STACK_BRANCHES=$(printf '%s' "$STACK_VIEW" | jq -er '
  if (.branches | type) != "array" then error("Invalid stack inventory")
  else [.branches[] | select(.pr.state == "OPEN") | .name]
    | if all(.[]; type == "string" and length > 0 and (test("[\\r\\n]") | not))
      then join("\n") else error("Invalid stack branch") end
  end') || exit 1
while IFS= read -r STACK_BRANCH; do
  [ -n "$STACK_BRANCH" ] || continue
  git check-ref-format --branch "$STACK_BRANCH" > /dev/null || exit 1
  git rev-parse --verify "refs/heads/$STACK_BRANCH^{commit}" > /dev/null || exit 1
  git fetch --no-tags "$STACK_REMOTE" "refs/heads/$STACK_BRANCH" || exit 1
  STACK_COUNTS=$(git rev-list --left-right --count "refs/heads/$STACK_BRANCH...FETCH_HEAD") || exit 1
  read -r STACK_AHEAD STACK_BEHIND <<< "$STACK_COUNTS"
  if [ "$STACK_AHEAD" -gt 0 ] && [ "$STACK_BEHIND" -gt 0 ]; then
    echo "$STACK_REMOTE/$STACK_BRANCH has commits the local branch lacks; integrate them before rebasing." >&2
    exit 1
  fi
  if [ "${STACK_STOP_ON_BEHIND:-0}" = 1 ] && [ "$STACK_BEHIND" -gt 0 ]; then
    echo "$STACK_REMOTE/$STACK_BRANCH has commits the local branch lacks; sync them before restructuring." >&2
    exit 1
  fi
done <<< "$OPEN_STACK_BRANCHES"
```

Before local preparation or rebase, follow the other-workspace and base-change gates in `stack-operations.md`, including confirmation of every affected checkout. Then integrate behind-only remote branches and reject divergence with the original snapshot:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.2.1/scripts/git-rewrite/stack-publication.py" prepare \
  --state "$STACK_PUBLICATION_STATE" || exit 1
```

Preparation fetches the captured objects, fast-forwards behind-only branches in their clean worktrees (or uses expected-old-OID ref updates for branches without a checkout), and rejects local movement since capture. It records its result in the snapshot: `phase: prepared` and, under `prepared`, every branch's tip after preparation, only after every fast-forward succeeds; `phase: prepare_failed` otherwise. A failure can leave earlier safe fast-forwards applied; report them and retain the snapshot, never claim rollback. Do not run preparation again after rewriting; a snapshot already recorded as `prepared` refuses a second run.

After the owning skill's local rewrite, validation, inventory recheck, and separate publication authorization, publish the already-restacked chain once:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.2.1/scripts/git-rewrite/stack-publication.py" publish \
  --state "$STACK_PUBLICATION_STATE" || exit 1
```

The publisher refuses to push when any captured remote head differs from its captured local head and the snapshot does not record `phase: prepared`, because the capture-time lease would still match a branch that was only behind and the push would drop its remote-only commits. A branch absent from the remote at capture does not count as differing, so a stack whose existing remote heads all equalled their local heads at capture publishes without preparation. It rechecks the active inventory and uses explicit local commit IDs, exact original per-ref leases, `--atomic`, and `--no-follow-tags` at the frozen endpoint. It does not fetch or derive leases from tracking refs. An intervening remote update rejects the entire push even if a fetch ran after capture. Unsupported atomic push, stale lease, inventory change, and Git/API errors stop publication; retain the snapshot and local result. Never retry with refreshed leases, `--no-atomic`, or a single-branch push.

Do not use `gh stack push`, `gh stack sync`, or `gh stack submit` to publish rewritten branches: their internal fetch can widen the lease. Initial submission of entirely new, unrewritten branches remains the owning skill's existing path. A branch rename changes the frozen inventory: stop and start a new authorized operation after preserving and reconciling all original tips; never silently extend an existing snapshot.

After `STACK_PUBLISHED=true`, verify local tips still match the pushed heads before updating PR bases or linking existing PR URLs under **Sync outcomes**. API work is separate from the atomic Git ref update. Delete the snapshot only after publication and metadata verification succeed; retain it on any conflict, rejected push, or uncertain API outcome. `--no-push` retains it with the local rewrite for a later authorized publication.
