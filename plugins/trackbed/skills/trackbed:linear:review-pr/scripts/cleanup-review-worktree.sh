#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "Usage: cleanup-review-worktree.sh <repository> <temporary-parent> <worktree>" >&2
  exit 2
fi
ORIG_ROOT=$1
TMP_PARENT=$2
WORKTREE_DIR=$3

cleanup_review_worktree() {
  local registered=false
  local unexpected_path=""
  local worktree_lookup_path="$WORKTREE_DIR"
  cd "$ORIG_ROOT" || return 1

  if [ -d "$WORKTREE_DIR" ]; then
    worktree_lookup_path=$(cd "$WORKTREE_DIR" && pwd -P) || return 1
  fi
  if git worktree list --porcelain | grep -Fqx "worktree $worktree_lookup_path"; then
    registered=true
  fi

  if [ -d "$WORKTREE_DIR" ]; then
    unexpected_path=$(find "$WORKTREE_DIR" -mindepth 1 -maxdepth 1 \
      ! -name .git -print -quit)
  fi
  if [ -n "$unexpected_path" ]; then
    echo "Temporary review worktree retained for inspection: $WORKTREE_DIR" >&2
    echo "Unexpected materialized content: $unexpected_path" >&2
    echo "Inspect it before removing the worktree manually." >&2
    return 1
  fi

  if [ "$registered" = true ]; then
    if ! git worktree remove --force "$WORKTREE_DIR" 2> /dev/null; then
      echo "Temporary review worktree retained for inspection: $WORKTREE_DIR" >&2
      echo "Inspect it, then remove it with: git worktree remove --force '$WORKTREE_DIR'" >&2
      return 1
    fi
  else
    if [ ! -e "$WORKTREE_DIR" ] && [ ! -L "$WORKTREE_DIR" ]; then
      rmdir "$TMP_PARENT" 2> /dev/null || true
      return 0
    fi
    if [ -d "$WORKTREE_DIR/.git" ]; then
      echo "Partial review worktree retained for inspection: $WORKTREE_DIR" >&2
      echo "Its .git administrative path is unexpectedly a directory." >&2
      return 1
    fi
    if [ -e "$WORKTREE_DIR/.git" ] || [ -L "$WORKTREE_DIR/.git" ]; then
      rm -- "$WORKTREE_DIR/.git" || return 1
    fi
    if ! rmdir "$WORKTREE_DIR" 2> /dev/null; then
      echo "Partial review worktree retained for inspection: $WORKTREE_DIR" >&2
      return 1
    fi
  fi
  rmdir "$TMP_PARENT" 2> /dev/null || true
}

cleanup_review_worktree
