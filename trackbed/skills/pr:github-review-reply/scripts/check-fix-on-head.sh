#!/usr/bin/env bash
# Check that a fix a reply claims is already on the Pull Request's remote head:
# the claimed paths have no uncommitted changes, and their committed content
# matches the PR head commit.
#
# Usage: check-fix-on-head.sh <repo> <pr-head-oid> <path>...
#
# <pr-head-oid> is the full commit ID GitHub reports as the PR head, already
# fetched into <repo>. Prints nothing and exits 0 when every path is on the PR
# head. Otherwise prints one line per path that is not, as
# "uncommitted <path>" (the working tree differs from HEAD, including untracked
# files) or "not-on-head <path>" (the local commit differs from the PR head,
# usually because it is not pushed yet), and exits 1. Exits 2 on usage or Git
# errors, which callers must treat as "not on the PR head".

set -euo pipefail

# Treat every path argument as a literal path, never as a glob or magic pathspec.
export GIT_LITERAL_PATHSPECS=1

usage() {
  echo "Usage: check-fix-on-head.sh <repo> <pr-head-oid> <path>..." >&2
  exit 2
}

[ "$#" -ge 3 ] || usage
repo=$1
head_oid=$2
shift 2

# A full object ID only: a branch name can resolve to a local ref that lags the
# PR head.
if [[ ! "$head_oid" =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]]; then
  echo "Expected a full commit object ID, got '$head_oid'." >&2
  exit 2
fi
if ! git -C "$repo" rev-parse --verify --quiet "$head_oid^{commit}" > /dev/null; then
  echo "Commit $head_oid is not available in $repo; fetch the PR head first." >&2
  exit 2
fi
if ! git -C "$repo" rev-parse --verify --quiet "HEAD^{commit}" > /dev/null; then
  echo "$repo has no HEAD commit." >&2
  exit 2
fi

# Keep NUL-separated Git output in files: command substitution drops NUL bytes.
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT

if ! git -C "$repo" -c core.quotePath=false status --porcelain=v1 -z \
  --untracked-files=all --no-renames -- "$@" > "$tmp/dirty"; then
  echo "git status failed in $repo." >&2
  exit 2
fi
if ! git -C "$repo" -c core.quotePath=false diff --name-only -z \
  --no-ext-diff --no-textconv --no-renames "$head_oid" HEAD -- "$@" > "$tmp/differs"; then
  echo "git diff against $head_oid failed in $repo." >&2
  exit 2
fi

status=0
# Porcelain -z entries are "XY <path>" terminated by NUL.
while IFS= read -r -d '' entry; do
  printf 'uncommitted %s\n' "${entry:3}"
  status=1
done < "$tmp/dirty"
while IFS= read -r -d '' path; do
  printf 'not-on-head %s\n' "$path"
  status=1
done < "$tmp/differs"

exit "$status"
