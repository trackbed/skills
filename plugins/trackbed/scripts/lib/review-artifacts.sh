#!/usr/bin/env bash
# Load patterns into REVIEW_ARTIFACT_PATTERNS. Policies apply to missing
# and empty lists; an HTML filter can legitimately leave no matches.
load_review_artifact_patterns() {
  local list_file="$1" policy="$2" filter="${3:-all}" fallback="${4-}"
  local line found=false

  REVIEW_ARTIFACT_PATTERNS=()
  if [ -f "$list_file" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      line="${line%%#*}"
      line="${line#"${line%%[![:space:]]*}"}"
      line="${line%"${line##*[![:space:]]}"}"
      [ -n "$line" ] || continue
      found=true
      case "$filter:$line" in
        all:* | html:*.html) REVIEW_ARTIFACT_PATTERNS+=("$line") ;;
      esac
    done < "$list_file" || return
  fi

  if [ "$found" = false ]; then
    case "$policy" in
      ignore) ;;
      fallback) REVIEW_ARTIFACT_PATTERNS=("$fallback") ;;
      fail)
        if [ -f "$list_file" ]; then
          echo "Review artifact list $list_file has no patterns." >&2
        else
          echo "Review artifact list not found at $list_file." >&2
        fi
        return 1
        ;;
    esac
  fi
}

# Visual report pages are generated at the root or directly under siw/.
# Callers apply this rule only to untracked files.
is_visual_report_page() {
  local candidate="${1#siw/}" pattern
  case "$candidate" in
    */*) return 1 ;;
  esac
  for pattern in ${REVIEW_ARTIFACT_PATTERNS[@]+"${REVIEW_ARTIFACT_PATTERNS[@]}"}; do
    # shellcheck disable=SC2254
    case "$candidate" in
      $pattern) return 0 ;;
    esac
  done
  return 1
}

untracked_paths_without_visual_pages() {
  local file
  while IFS= read -r -d '' file; do
    if ! is_visual_report_page "$file"; then
      printf '%s\0' "$file"
    fi
  done
}
