# Stack rewrite preflight

Run this before `gh stack rebase` in `trackbed:pr:rebase` and before routine `gh stack sync` and every Restructure in `trackbed:pr:stack`, including a fresh rebase after sync conflicts. Resolve `STACK_REMOTE` to the remote the following gh-stack command will use: its explicit `--remote`, otherwise `remote.pushDefault`, otherwise the sole configured remote. Stop on an ambiguous remote; never check origin and then rewrite a different remote's stack.

Run the block in Bash. Fetch every open PR branch before any rewrite or stash. A fetch, inventory, ref, or ancestry failure stops the operation. Keep branch names as quoted data. A branch that is only behind is allowed; gh-stack can reconcile a fast-forward. A branch with commits on both sides must be integrated first. A Restructure rebases from local tips and then force-pushes, which would drop a behind branch's remote commits, so it sets `STACK_STOP_ON_BEHIND=1` to stop on behind-only branches too.

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

Only after every branch passes may the caller rewrite or sync, using the same `STACK_REMOTE`. This is an ancestry guard before rewriting, not a pinned lease across gh-stack's later fetches. If another actor updates a branch during the operation, stop and coordinate; do not claim protection against concurrent writes from this check alone.

For stack pushes, run `env -u GH_STACK_NO_ATOMIC gh stack push`; use the same prefix for `sync`, which also pushes. Never add `--no-atomic` or retry non-atomically. Atomicity covers Git ref updates only, not PR creation, base changes, or other API updates. Preserve the caller's separate publication authorization.
