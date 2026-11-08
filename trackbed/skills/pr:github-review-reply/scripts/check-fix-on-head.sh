#!/usr/bin/env bash
# Check that a fix a reply claims is already on the Pull Request's remote head:
# the claimed paths have no uncommitted changes, and their committed content
# matches the PR head commit.
#
# Usage: check-fix-on-head.sh <repo> <pr-head-oid> <path>...
#
# <pr-head-oid> is the full commit ID GitHub reports as the PR head, already
# fetched into <repo>. Each <path> is relative to the root of <repo>. Prints
# nothing and exits 0 when every path is on the PR head. Otherwise prints one
# line per path that is not, as "uncommitted <path>" (the working tree differs
# from HEAD, including untracked files) or "not-on-head <path>" (the path's
# content at HEAD differs from the PR head: unpushed commits, a checkout behind
# the PR head, or a diverged branch), and exits 1. Exits 2 on usage or Git
# errors, and for a path Git knows neither locally nor in the PR head's history
# (a typo, a wrong-case name, or an ignored file the PR head never had), which
# callers must treat as "not on the PR head".

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

# Status and diff print nothing for a path Git does not know, which would read
# as "on the PR head". A path the PR head once had still counts, so a pushed
# deletion passes.
for path in "$@"; do
  if ! known=$(git -C "$repo" ls-files --cached --others --exclude-standard -- "$path"); then
    echo "git ls-files failed in $repo." >&2
    exit 2
  fi
  if [ -z "$known" ] && ! known=$(git -C "$repo" log -1 --format=%H "$head_oid" -- "$path"); then
    echo "git log failed in $repo." >&2
    exit 2
  fi
  if [ -z "$known" ]; then
    echo "Path '$path' is not known in $repo or in the history of $head_oid." >&2
    exit 2
  fi
done

if ! dirty=$(git -C "$repo" -c core.quotePath=false status --porcelain=v1 \
  --untracked-files=all --no-renames -- "$@"); then
  echo "git status failed in $repo." >&2
  exit 2
fi
if ! differs=$(git -C "$repo" -c core.quotePath=false diff --name-only \
  --no-renames "$head_oid" HEAD -- "$@"); then
  echo "git diff against $head_oid failed in $repo." >&2
  exit 2
fi

status=0
# Porcelain entries are "XY <path>".
if [ -n "$dirty" ]; then
  printf '%s\n' "$dirty" | sed 's/^.. /uncommitted /'
  status=1
fi
if [ -n "$differs" ]; then
  printf '%s\n' "$differs" | sed 's/^/not-on-head /'
  status=1
fi

exit "$status"
