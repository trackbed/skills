#!/usr/bin/env bash
#
# Print the protected review report patterns, one per line.
#
# hooks/confirm-review-artifacts.txt is the only list of protected report
# names. Skills may depend only on their own directory, shared/, and scripts/,
# so they read the list through this helper instead of hooks/ or a copy.
# Comments and blank lines are dropped. Each caller keeps its own matching
# rules; the list's header describes the commit hook's.
#
# A missing or empty list exits non-zero, so a caller that filters with it
# stops instead of treating every report as ordinary content.

set -euo pipefail

if [ "$#" -ne 0 ]; then
  echo "Usage: review-artifact-patterns.sh" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIST_FILE="$SCRIPT_DIR/../hooks/confirm-review-artifacts.txt"

if [ ! -f "$LIST_FILE" ]; then
  echo "Review artifact list not found at $LIST_FILE." >&2
  exit 1
fi

found=false
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%%#*}"
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  [ -n "$line" ] || continue
  printf '%s\n' "$line"
  found=true
done < "$LIST_FILE"

if [ "$found" != true ]; then
  echo "Review artifact list $LIST_FILE has no patterns." >&2
  exit 1
fi
