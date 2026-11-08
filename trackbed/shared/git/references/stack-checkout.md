# Import a remote stack and restore the entry branch

Use this only after the membership resolver reports `STACK_MEMBERSHIP=remote`. Install gh-stack if unavailable. Import with the resolved stack number: a PR number or PR URL can select a different stack. Checkout by stack number lands on the topmost unmerged branch, so return to the recorded entry branch before retrying the caller.

```bash
[[ "${STACK_NUMBER:-}" =~ ^[1-9][0-9]*$ ]] || {
  echo "The stack number could not be determined; stop without guessing." >&2
  exit 1
}
STACK_RESTORE_BRANCH=$(git symbolic-ref --quiet --short HEAD) || exit 1
git check-ref-format --branch "$STACK_RESTORE_BRANCH" > /dev/null || exit 1
STACK_CHECKOUT_STATUS=$(git status --porcelain --untracked-files=all) || exit 1
if [ -n "$STACK_CHECKOUT_STATUS" ]; then
  echo "A clean working tree is required before importing the stack." >&2
  exit 1
fi
gh stack checkout "$STACK_NUMBER" || exit 1
git switch -- "$STACK_RESTORE_BRANCH" || {
  echo "Could not restore the entry branch; stop before retrying the workflow." >&2
  exit 1
}
[ "$(git symbolic-ref --quiet --short HEAD)" = "$STACK_RESTORE_BRANCH" ] || exit 1
```

Rerun the caller's membership check on that restored branch. Retry only when the branch still equals `STACK_RESTORE_BRANCH` and membership is `local`. If import, restoration, or revalidation fails, report the failure and current branch; do not continue on the top branch or substitute a PR number.
