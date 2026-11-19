# Preserve link operands and reject number collisions

Validate every `STACK_ITEMS` operand under Step 0, including current-repository ownership for PR URLs, and keep the original bottom-to-top array. Never replace a PR identifier with its head branch: gh-stack can resolve a different PR sharing that head, and branch operands can push unpublished local commits.

For a leading bare PR number, reject an identically named local branch and check every repository stack for a number collision before linking. An explicit PR URL bypasses numeric target selection; preserve it unchanged. For an explicitly supplied branch, require a validated nonnumeric name. Do not normalize ambiguous numeric branch names. Run this block immediately before linking; any failed or malformed lookup stops the operation.

```bash
FIRST_STACK_ITEM=${STACK_ITEMS[0]:-}
LINK_PR_NUMBER=""
if [[ "$FIRST_STACK_ITEM" =~ ^[1-9][0-9]*$ ]]; then
  if git show-ref --verify --quiet "refs/heads/$FIRST_STACK_ITEM"; then
    echo "Leading PR #$FIRST_STACK_ITEM also names a local branch; stop and ask for its explicit PR URL before linking." >&2
    exit 1
  else
    LINK_REF_STATUS=$?
    [ "$LINK_REF_STATUS" -eq 1 ] || {
      echo "Could not inspect local branch names; stop before linking." >&2
      exit 1
    }
  fi
  LINK_PR_NUMBER=$FIRST_STACK_ITEM
elif [[ "$FIRST_STACK_ITEM" =~ ^https://github\.com/[^/]+/[^/]+/pull/([1-9][0-9]*)$ ]]; then
  :
elif [ -z "$FIRST_STACK_ITEM" ] || [[ "$FIRST_STACK_ITEM" =~ ^\+?[0-9]+$ ]] \
  || ! git check-ref-format --branch "$FIRST_STACK_ITEM" > /dev/null; then
  echo "Link requires a valid branch or PR identifier as its first item; stop before linking." >&2
  exit 1
fi
if [ -n "$LINK_PR_NUMBER" ]; then
  ALL_STACKS_JSON=$(gh api --paginate --slurp 'repos/{owner}/{repo}/stacks?per_page=100') || {
    echo "Could not check stack-number collisions; stop before linking." >&2
    exit 1
  }
  printf '%s\n' "$ALL_STACKS_JSON" | jq -e '
    type == "array" and length > 0 and all(.[]; type == "array")
    and all(.[][]; .number | type == "number" and . > 0 and floor == .)
  ' > /dev/null || {
    echo "Invalid repository stack list; stop before linking." >&2
    exit 1
  }
  if printf '%s\n' "$ALL_STACKS_JSON" | jq -e --argjson pr "$LINK_PR_NUMBER" 'any(.[][]; .number == $pr)' > /dev/null; then
    echo "A stack uses PR #$LINK_PR_NUMBER's number; stop and ask the user how to proceed with this link." >&2
    exit 1
  fi
fi
gh stack link "${STACK_ITEMS[@]}"
```
