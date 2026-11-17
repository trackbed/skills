#!/bin/bash
set -uo pipefail
# Policy: -u/-pipefail only. No -e: this hook is fail-open and must always print a JSON response.
# Hook: Run a /trackbed:* command typed at the start of a Conductor chat's first message.
#
# Conductor puts a <system_instruction> block in front of that message, so
# Claude Code does not expand the command. When the user's own text starts with
# /trackbed:<skill>, the hook adds context that tells the model to read and
# follow that skill. Every other prompt gets an empty response.

source "${CLAUDE_PLUGIN_ROOT}/hooks/lib/check-enabled.sh"
exit_if_hook_disabled "conductor-slash-command" "json"

input=$(cat)

# Skip Node for the prompts that cannot match.
case "$input" in
  *'</system_instruction>'*'/trackbed:'*) ;;
  *)
    echo '{}'
    exit 0
    ;;
esac

if ! command -v node > /dev/null 2>&1; then
  echo '{}'
  exit 0
fi

output=$(printf '%s' "$input" | node "${CLAUDE_PLUGIN_ROOT}/hooks/lib/conductor-slash-command.js" 2> /dev/null)
status=$?
if [ "$status" -ne 0 ] || [ -z "$output" ]; then
  echo '{}'
  exit 0
fi

echo "$output"
