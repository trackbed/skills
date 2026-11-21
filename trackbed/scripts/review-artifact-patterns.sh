#!/usr/bin/env bash
# Read protected patterns, or filter a NUL-delimited list of untracked paths.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/review-artifacts.sh
source "$SCRIPT_DIR/lib/review-artifacts.sh"
LIST_FILE="$SCRIPT_DIR/../hooks/confirm-review-artifacts.txt"

case "$#:${1-}" in
  0:)
    load_review_artifact_patterns "$LIST_FILE" fail
    printf '%s\n' "${REVIEW_ARTIFACT_PATTERNS[@]}"
    ;;
  1:--without-visual-pages)
    load_review_artifact_patterns "$LIST_FILE" fail html
    untracked_paths_without_visual_pages
    ;;
  *)
    echo "Usage: review-artifact-patterns.sh [--without-visual-pages]" >&2
    exit 2
    ;;
esac
