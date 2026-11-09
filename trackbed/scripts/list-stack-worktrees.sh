#!/usr/bin/env bash
#
# List the stack branches that a gh-stack rebase or sync may change inside a
# worktree other than the current one.
#
# Usage: list-stack-worktrees.sh [--no-trunk]
#
# Prints one tab-separated line per affected branch:
#   <kind>	<branch>	<worktree-path>
# where <kind> is "layer" for an unmerged stack branch and "trunk" for the
# stack's trunk. Pass --no-trunk for "gh stack rebase --no-trunk", which leaves
# the trunk alone. No output means no other worktree is affected.
#
# gh-stack v0.3 rebases each stack branch inside the worktree that has it
# checked out and fast-forwards a checked-out trunk there. The list is a
# superset: it ignores --upstack, --downstack, and branches already up to date,
# so every worktree the command can change is listed. In Conductor, each
# worktree is a workspace.
#
# Any failure to read the stack or the worktree list exits 1, so a caller never
# treats an unknown state as "no other worktree".

set -euo pipefail

die() {
  printf '%s\n' "$*" >&2
  exit 1
}

INCLUDE_TRUNK=1
case "$#" in
  0) ;;
  1)
    [ "$1" = --no-trunk ] || die "Usage: ${0##*/} [--no-trunk]"
    INCLUDE_TRUNK=0
    ;;
  *) die "Usage: ${0##*/} [--no-trunk]" ;;
esac

STACK_VIEW=$(gh stack view --json) || die "Could not read the stack with gh stack view --json."
STACK_TARGETS=$(printf '%s' "$STACK_VIEW" | jq -er --argjson trunk "$INCLUDE_TRUNK" '
  if (.branches | type) != "array" or (.trunk | type) != "string" or (.trunk | length) == 0
  then error("Invalid stack inventory")
  else
    [.branches[] | select(.isMerged != true) | ["layer", .name]]
      + (if $trunk == 1 then [["trunk", .trunk]] else [] end)
    | if all(.[]; .[1] | type == "string" and length > 0 and (test("[\\t\\r\\n]") | not))
      then map(join("\t")) | join("\n")
      else error("Invalid stack branch") end
  end') || die "gh stack view --json did not return a valid stack."

# A branch is checked out in at most one worktree, so skipping the current
# branch leaves exactly the other worktrees. Empty on a detached HEAD.
CURRENT_BRANCH=$(git symbolic-ref --quiet --short HEAD || true)

LISTING=$(mktemp "${TMPDIR:-/tmp}/list-stack-worktrees.XXXXXX") || die "Could not create a temporary file."
trap 'rm -f "$LISTING"' EXIT
git worktree list --porcelain -z > "$LISTING" || die "Could not list Git worktrees."

WT_PATHS=()
WT_BRANCHES=()
add_worktree() {
  if [ -n "$1" ] && [ -n "$2" ]; then
    case "$1" in
      *$'\t'* | *$'\n'* | *$'\r'*) die "A worktree path contains a tab or line break: cannot report it safely." ;;
    esac
    WT_PATHS+=("$1")
    WT_BRANCHES+=("$2")
  fi
}

path=''
branch=''
while IFS= read -r -d '' field; do
  case "$field" in
    'worktree '*)
      add_worktree "$path" "$branch"
      path=${field#worktree }
      branch=''
      ;;
    'branch refs/heads/'*) branch=${field#branch refs/heads/} ;;
    '')
      add_worktree "$path" "$branch"
      path=''
      branch=''
      ;;
  esac
done < "$LISTING"
add_worktree "$path" "$branch"

while IFS=$'\t' read -r kind name; do
  [ -n "$name" ] || continue
  i=0
  while [ "$i" -lt "${#WT_BRANCHES[@]}" ]; do
    if [ "${WT_BRANCHES[$i]}" = "$name" ] && [ "$name" != "$CURRENT_BRANCH" ]; then
      printf '%s\t%s\t%s\n' "$kind" "$name" "${WT_PATHS[$i]}"
    fi
    i=$((i + 1))
  done
done <<< "$STACK_TARGETS"
