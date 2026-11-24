# Resolve an unambiguous merge target

The selected positive `TARGET_PR_NUMBER` expresses the user's merge boundary. Query its server-side stack rather than inferring a stack from the current checkout. A whole-stack merge uses the stack number; a partial merge can use its PR number only after a complete repository stack list proves that number is unused by any stack. gh-stack tries stack numbers first, and a collision removes the intended PR boundary.

Run this immediately before the Merging command, after choosing the method. Any API or parsing failure stops the workflow. Do not interpret a failed request as proof that a stack is absent.

```bash
[[ "$TARGET_PR_NUMBER" =~ ^[1-9][0-9]*$ ]] || exit 1
TARGET_STACK_JSON=$(gh api "repos/{owner}/{repo}/stacks?pull_request=$TARGET_PR_NUMBER") || {
  echo "Could not determine the selected PR's stack; stop before merging." >&2
  exit 1
}
STACK_NUMBER=$(printf '%s\n' "$TARGET_STACK_JSON" | jq -er --argjson pr "$TARGET_PR_NUMBER" '
  select(type == "array" and length == 1) | .[0]
  | select(any(.pull_requests[]; .number == $pr))
  | .number | select(type == "number" and . > 0 and floor == .)
') || {
  echo "The selected PR is in no identifiable stack, or its stack number could not be determined; stop before merging." >&2
  exit 1
}
TOP_PR_NUMBER=$(printf '%s\n' "$TARGET_STACK_JSON" | jq -er '.[0].pull_requests[-1].number | select(type == "number" and . > 0 and floor == .)') || exit 1
if [ "$TARGET_PR_NUMBER" = "$TOP_PR_NUMBER" ]; then
  MERGE_TARGET=$STACK_NUMBER
else
  ALL_STACKS_JSON=$(gh api --paginate --slurp 'repos/{owner}/{repo}/stacks?per_page=100') || {
    echo "Could not check stack-number collisions; stop before merging." >&2
    exit 1
  }
  printf '%s\n' "$ALL_STACKS_JSON" | jq -e '
    type == "array" and length > 0 and all(.[]; type == "array")
    and all(.[][]; .number | type == "number" and . > 0 and floor == .)
  ' > /dev/null || {
    echo "Invalid repository stack list; stop before merging." >&2
    exit 1
  }
  if printf '%s\n' "$ALL_STACKS_JSON" | jq -e --argjson pr "$TARGET_PR_NUMBER" 'any(.[][]; .number == $pr)' > /dev/null; then
    echo "A stack uses PR #$TARGET_PR_NUMBER's number; stop and ask the user how to proceed with this partial merge." >&2
    exit 1
  fi
  MERGE_TARGET=$TARGET_PR_NUMBER
fi
```

On a collision, identify the selected PR and colliding stack in the question. Do not execute a merge until a new unambiguous action is agreed. A PR URL is not an escape hatch, and neither is merging the whole stack when the user selected a lower PR. Keep the existing merge-method, confirmation, and post-merge flow.
