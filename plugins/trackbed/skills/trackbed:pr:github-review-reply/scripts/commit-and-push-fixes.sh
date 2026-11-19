#!/usr/bin/env bash
# Commit the fixes an --auto run made and push them to the Pull Request branch
# as one new commit on top of the PR head. Never force-pushes, never rewrites
# history, and never commits a path outside the given fix paths.
#
# Usage: commit-and-push-fixes.sh <repo> <pr-head-oid> <remote> <branch> <message-file> <path>...
#
# <pr-head-oid> is the full commit ID GitHub reported as the PR head, and the
# checkout must be on <branch> at exactly that commit. Each <path> is relative
# to the root of <repo>; new and deleted files count. The only untracked files
# allowed outside the paths are this skill's own artifacts:
# GITHUB_REVIEW_REPLY_PLAN.md, GITHUB_REVIEW_REPLY_PLAN.html, and .context/.
#
# Exits 0 after pushing and prints the new commit ID. Exits 2 when it committed
# nothing: a precondition failed, nothing changed in the paths, a tracked file
# outside the paths changed, a new file outside the paths and the artifacts
# appeared, or the commit failed; the index is left as it was
# found and the working tree is untouched. Exits 1 when the commit exists
# locally but was not pushed (a commit hook changed files, or the remote
# rejected the push); it prints the commit ID first.

set -euo pipefail

# Treat every path argument as a literal path, never as a glob or magic pathspec.
export GIT_LITERAL_PATHSPECS=1

usage() {
  echo "Usage: commit-and-push-fixes.sh <repo> <pr-head-oid> <remote> <branch> <message-file> <path>..." >&2
  exit 2
}

[ "$#" -ge 6 ] || usage
repo=$1
head_oid=$2
remote=$3
branch=$4
message_file=$5
shift 5

if [[ ! "$head_oid" =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]]; then
  echo "Expected a full commit object ID, got '$head_oid'." >&2
  exit 2
fi
if [ ! -s "$message_file" ]; then
  echo "Commit message file '$message_file' is missing or empty." >&2
  exit 2
fi

git_repo() {
  git -C "$repo" -c core.quotePath=false "$@"
}

current_branch=$(git_repo symbolic-ref --quiet --short HEAD || true)
if [ "$current_branch" != "$branch" ]; then
  echo "The checkout is on '${current_branch:-a detached HEAD}', not the PR branch '$branch'." >&2
  exit 2
fi
local_head=$(git_repo rev-parse HEAD)
if [ "$local_head" != "$head_oid" ]; then
  echo "Local HEAD $local_head is not the PR head $head_oid; reconcile the branch before publishing." >&2
  exit 2
fi
if ! git_repo diff --cached --quiet; then
  echo "The index already has staged changes; publishing would commit them too." >&2
  exit 2
fi

# The index was clean, so resetting it undoes exactly what this script staged.
unstage() {
  git_repo reset -q
}

if ! git_repo add -A -- "$@"; then
  unstage
  echo "Could not stage the fix paths." >&2
  exit 2
fi
if git_repo diff --cached --quiet; then
  echo "The fix paths have no changes to commit." >&2
  exit 2
fi
outside=$(git_repo diff --name-only)
if [ -n "$outside" ]; then
  unstage
  printf 'Tracked files outside the fix paths changed; nothing was committed:\n' >&2
  printf '%s\n' "$outside" | sed 's/^/outside /' >&2
  exit 2
fi
# The caller starts from a clean tree, so a new file outside the fix paths came
# from the fixes; committing without it would push an incomplete fix.
if ! untracked=$(git_repo ls-files --others --exclude-standard); then
  unstage
  echo "git ls-files failed; nothing was committed." >&2
  exit 2
fi
stray=$(printf '%s\n' "$untracked" | grep -Ev '^(GITHUB_REVIEW_REPLY_PLAN\.(md|html)|\.context/.*)?$' || true)
if [ -n "$stray" ]; then
  unstage
  printf 'New files outside the fix paths appeared; nothing was committed:\n' >&2
  printf '%s\n' "$stray" | sed 's/^/untracked /' >&2
  exit 2
fi

if ! git_repo commit -q -F "$message_file"; then
  unstage
  echo "git commit failed; nothing was committed." >&2
  exit 2
fi
commit=$(git_repo rev-parse HEAD)

if ! git_repo diff --quiet HEAD; then
  echo "$commit"
  echo "A commit hook changed tracked files after commit $commit; it was not pushed." >&2
  exit 1
fi

# No "+" and no --force: the remote accepts only a fast-forward, so a push to
# the PR branch since the run started is rejected rather than overwritten.
if ! git_repo push -q "$remote" "$commit:refs/heads/$branch"; then
  echo "$commit"
  echo "The push of $commit to $remote $branch was rejected; the commit stays local." >&2
  exit 1
fi

echo "$commit"
