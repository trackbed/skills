#!/usr/bin/env bash
# Source this helper so repository-relative paths also resolve in the caller.

# Scope fields are output variables consumed by the sourcing skill.
# shellcheck disable=SC2034
collect_review_scope() {
  local scope_script_dir scope_root scope_fields
  scope_script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P) || return 1
  scope_root=$(git rev-parse --show-toplevel) || return 1
  cd -- "$scope_root" || return 1
  scope_fields=$(mktemp "${TMPDIR:-/tmp}/review-diff.XXXXXX") || {
    echo "Could not create temporary review-diff file; stop." >&2
    return 1
  }
  "$scope_script_dir/collect-review-diff.sh" "$@" --format nul > "$scope_fields" || {
    rm -f "$scope_fields"
    echo "Base/diff collection failed; see the message above and stop." >&2
    return 1
  }
  if ! {
    IFS= read -r -d '' BASE_REF \
      && IFS= read -r -d '' BASE_BRANCH \
      && IFS= read -r -d '' MERGE_BASE \
      && IFS= read -r -d '' CHANGED_FILES \
      && IFS= read -r -d '' STACK_CONTEXT
  } < "$scope_fields"; then
    rm -f "$scope_fields"
    echo "Decoded review-diff fields were incomplete; stop." >&2
    return 1
  fi
  rm -f "$scope_fields"
}

# Emit only untracked paths in the collected scope, without Git's text quoting.
# Keep pipefail local to this function so a failed listing cannot look empty.
review_untracked_paths() (
  set -o pipefail
  local scope_root untracked_path
  local changed_files="${1?review_untracked_paths requires the collected CHANGED_FILES}"
  scope_root=$(git rev-parse --show-toplevel) || return 1
  git -C "$scope_root" ls-files --others --exclude-standard -z | while IFS= read -r -d '' untracked_path; do
    case $'\n'"$changed_files"$'\n' in
      *$'\n'"$untracked_path"$'\n'*) printf '%s\0' "$untracked_path" ;;
    esac
  done
)
