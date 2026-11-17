#!/usr/bin/env bats
# Tests for the conductor-slash-command.sh hook wrapper. The Node tests in
# tests/node/conductor-slash-command.test.js cover parsing and skill lookup.

load 'test_helper/common'

setup() {
	HOOK="$HOOKS_DIR/conductor-slash-command.sh"
	export TRACKBED_HOOK_STATE_FILE="$BATS_TEST_TMPDIR/hook-state.json"
	export CLAUDECODE=1
	unset TRACKBED_AGENT_PLATFORM
}

conductor_payload() {
	jq -cn --arg command "$1" \
		'{hook_event_name: "UserPromptSubmit", prompt: ("<system_instruction>\nYou are working inside Conductor.\n</system_instruction>\n\n" + $command)}'
}

@test "adds context for a command typed after Conductor's block" {
	if ! command -v node >/dev/null 2>&1; then
		skip "node is required for this hook"
	fi

	run bash -c 'printf "%s" "$1" | bash "$2"' _ "$(conductor_payload '/trackbed:pr:github-review 8704')" "$HOOK"
	[ "$status" -eq 0 ]
	[ "$(jq -r '.hookSpecificOutput.hookEventName' <<<"$output")" = "UserPromptSubmit" ]
	context="$(jq -r '.hookSpecificOutput.additionalContext' <<<"$output")"
	[[ "$context" == *"skills/pr:github-review/SKILL.md"* ]] || false
	[[ "$context" == *$'<arguments>\n8704\n</arguments>'* ]] || false
}

@test "prints an empty object for prompts without a Conductor block" {
	run bash -c 'printf "%s" "$1" | bash "$2"' _ '{"prompt":"/trackbed:pr:create"}' "$HOOK"
	[ "$status" -eq 0 ]
	[ "$output" = "{}" ]
}

@test "prints an empty object for an unknown skill" {
	if ! command -v node >/dev/null 2>&1; then
		skip "node is required for this hook"
	fi

	run bash -c 'printf "%s" "$1" | bash "$2"' _ "$(conductor_payload '/trackbed:pr:missing')" "$HOOK"
	[ "$status" -eq 0 ]
	[ "$output" = "{}" ]
}

@test "prints an empty object when the hook is disabled" {
	printf '{"disabled":["conductor-slash-command"]}\n' >"$TRACKBED_HOOK_STATE_FILE"

	run bash -c 'printf "%s" "$1" | bash "$2"' _ "$(conductor_payload '/trackbed:pr:github-review')" "$HOOK"
	[ "$status" -eq 0 ]
	[ "$output" = "{}" ]
}

@test "prints an empty object when Node.js is unavailable" {
	run env PATH="/usr/bin:/bin" bash -c 'command -v node >/dev/null && exit 99; printf "%s" "$1" | bash "$2"' _ "$(conductor_payload '/trackbed:pr:github-review')" "$HOOK"
	if [ "$status" -eq 99 ]; then
		skip "node is on the system PATH"
	fi
	[ "$status" -eq 0 ]
	[ "$output" = "{}" ]
}
