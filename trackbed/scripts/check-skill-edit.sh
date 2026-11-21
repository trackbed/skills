#!/usr/bin/env bash
#
# Project PostToolUse hook for Claude Code sessions in this repository,
# registered in .claude/settings.json. After a Write or Edit under
# trackbed/skills/, it runs the self-contained-skill check, plus the
# single-skill linter mode when the edited file is a skill's SKILL.md.
#
# Silent on success. On a failed check it prints the checker output to stderr
# and exits 2, which Claude Code shows to the agent right after the edit.
# Set TRACKBED_SKILL_EDIT_CHECK=0 to turn it off.
set -uo pipefail
# No -e: exit codes are semantic here (2 reports a failure to the agent).

input=$(cat)

[ "${TRACKBED_SKILL_EDIT_CHECK:-1}" = "0" ] && exit 0
# Cheap filter on the file_path field first, so edits elsewhere stay silent
# even without jq.
skills_path_pattern='"file_path"[[:space:]]*:[[:space:]]*"[^"]*trackbed/skills/'
[[ $input =~ $skills_path_pattern ]] || exit 0

skip_if_missing() {
  command -v "$1" > /dev/null 2>&1 && return 0
  echo "skill edit check skipped: $1 not found (see CONTRIBUTING.md setup)" >&2
  exit 1
}

skip_if_missing jq
file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2> /dev/null)
[ -n "$file_path" ] || exit 0

# Compare physical paths so a symlinked checkout or temp directory still matches.
file_dir=$(cd "${file_path%/*}" 2> /dev/null && pwd -P) || exit 0
repo_root=$(cd "${BASH_SOURCE[0]%/*}/../.." && pwd -P) || exit 0
skills_dir="$repo_root/trackbed/skills"
case "$file_dir/" in
  "$skills_dir"/*) ;;
  *) exit 0 ;;
esac
edited="$file_dir/${file_path##*/}"
relative="${edited#"$skills_dir"/}"

skip_if_missing node
skip_if_missing python3

resources_output=$(mktemp) || exit 1
trap 'rm -f "$resources_output"' EXIT

node "$repo_root/trackbed/scripts/check-installed-resources.js" > "$resources_output" 2>&1 &
resources_pid=$!

lint_status=0
lint_output=""
# Only SKILL.md has the frontmatter the single-skill mode checks.
if [ "${relative##*/}" = "SKILL.md" ]; then
  lint_output=$(python3 "$repo_root/trackbed/scripts/lint-skill-contracts.py" --skill "$edited" 2>&1) || lint_status=$?
fi

wait "$resources_pid"
resources_status=$?

[ "$resources_status" -eq 0 ] && [ "$lint_status" -eq 0 ] && exit 0

{
  echo "Skill checks failed after editing trackbed/skills/$relative:"
  if [ "$resources_status" -ne 0 ]; then
    echo "node trackbed/scripts/check-installed-resources.js:"
    cat "$resources_output"
  fi
  if [ "$lint_status" -ne 0 ]; then
    echo "python3 trackbed/scripts/lint-skill-contracts.py --skill trackbed/skills/$relative:"
    printf '%s\n' "$lint_output"
  fi
} >&2
exit 2
