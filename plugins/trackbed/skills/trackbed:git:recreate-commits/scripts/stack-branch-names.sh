#!/usr/bin/env bash
set -euo pipefail

stack_view_json=$(gh stack view --json) || exit 1
printf '%s\n' "$stack_view_json" | jq -er '
  .branches
  | if type != "array"
      or length == 0
      or any(.[]; ((.name | type) != "string") or ((.name | length) == 0))
    then error("invalid stack branch inventory")
    else .[].name
    end
'
