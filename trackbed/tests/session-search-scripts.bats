#!/usr/bin/env bats

setup() {
	SCRIPTS="$BATS_TEST_DIRNAME/../skills/session:automate-repeats/scripts"
	TEST_DIR=$(mktemp -d)
}

teardown() {
	rm -rf "$TEST_DIR"
}

write_codex_session() {
	cat >"$TEST_DIR/codex.jsonl" <<'JSONL'
{"timestamp":"2026-06-06T10:00:00Z","type":"session_meta","payload":{"cwd":"/tmp/demo-repo","id":"codex-test-session","timestamp":"2026-06-06T10:00:00Z","source":"codex"}}
{"timestamp":"2026-06-06T10:01:00Z","type":"turn_context","payload":{"cwd":"/tmp/demo-repo","model":"gpt-test"}}
{"timestamp":"2026-06-06T10:02:00Z","type":"event_msg","payload":{"type":"user_message","message":"Please debug the auth script. API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456"}}
{"timestamp":"2026-06-06T10:03:00Z","type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"I will inspect the failing auth command and avoid exposing secrets."}]}}
{"timestamp":"2026-06-06T10:04:00Z","type":"event_msg","payload":{"type":"exec_command_end","command":["zsh","-lc","curl -H 'Authorization: Bearer supersecret1234567890' https://example.invalid"],"aggregated_output":"Process exited with code 1\nAuthorization: Bearer supersecret1234567890 failed","stderr":"Authorization: Bearer supersecret1234567890 failed"}}
JSONL
}

@test "discover-sessions exits cleanly when no session stores exist" {
	mkdir -p "$TEST_DIR/home"

	run env -u CLAUDE_CONFIG_DIR -u CODEX_HOME HOME="$TEST_DIR/home" bash "$SCRIPTS/discover-sessions.sh" demo-repo 1

	[ "$status" -eq 0 ]
	[ "$output" = "" ]
}

@test "extract-metadata filters by cwd and keyword without content output" {
	write_codex_session

	run python3 "$SCRIPTS/extract-metadata.py" --cwd-filter demo-repo --keyword debug "$TEST_DIR/codex.jsonl"

	[ "$status" -eq 0 ]
	grep -qF '"platform": "codex"' <<<"$output"
	grep -qF '"match_count": 1' <<<"$output"
	grep -qF '"files_matched": 1' <<<"$output"
	! grep -qF 'sk-abcdefghijklmnopqrstuvwxyz123456' <<<"$output" || false
}

@test "extract-skeleton writes redacted scratch output" {
	write_codex_session
	out="$TEST_DIR/skeleton.txt"

	run python3 "$SCRIPTS/extract-skeleton.py" --output "$out" <"$TEST_DIR/codex.jsonl"

	[ "$status" -eq 0 ]
	grep -qF '"wrote":' <<<"$output"
	grep -qF '[REDACTED]' "$out"
	! grep -qF 'sk-abcdefghijklmnopqrstuvwxyz123456' "$out" || false
	! grep -qF 'supersecret1234567890' "$out" || false
}

@test "extract-errors writes redacted error output" {
	write_codex_session
	out="$TEST_DIR/errors.txt"

	run python3 "$SCRIPTS/extract-errors.py" --output "$out" <"$TEST_DIR/codex.jsonl"

	[ "$status" -eq 0 ]
	grep -qF '"errors_found": 1' <<<"$output"
	grep -qF '[REDACTED]' "$out"
	! grep -qF 'supersecret1234567890' "$out" || false
}

@test "extract-skill-usage writes only validated skill names" {
	cat >>"$TEST_DIR/codex-skill.jsonl" <<'JSONL'
{"timestamp":"2026-06-06T10:00:00Z","type":"session_meta","payload":{"cwd":"/tmp/demo-repo","id":"codex-skill-session","timestamp":"2026-06-06T10:00:00Z","source":"codex"}}
{"timestamp":"2026-06-06T10:01:00Z","type":"response_item","payload":{"type":"function_call","name":"exec_command","arguments":"{\"cmd\":\"sed -n 1,80p /tmp/.codex/skills/trackbed:session:automate-repeats/SKILL.md\",\"token\":\"sk-abcdefghijklmnopqrstuvwxyz123456\"}"}}
JSONL
	out="$TEST_DIR/skill-usage.json"

	run python3 "$SCRIPTS/extract-skill-usage.py" \
		--known-skill trackbed:session:automate-repeats \
		--output "$out" <"$TEST_DIR/codex-skill.jsonl"

	[ "$status" -eq 0 ]
	grep -qF '"skills": ["trackbed:session:automate-repeats"]' "$out"
	grep -qF '"skill_events": 1' "$out"
	grep -qF '"unknown_skill_events": 0' "$out"
	! grep -qF '/tmp/.codex' "$out" || false
	! grep -qF 'sk-abcdefghijklmnopqrstuvwxyz123456' "$out" || false
}

@test "discover-sessions lists Claude projects by encoded cwd prefix, not repo-name glob" {
	# Claude Code encodes /work/my.repo as -work-my-repo, which a "*my.repo*" glob misses.
	local claude="$TEST_DIR/claude-config/projects"
	mkdir -p "$TEST_DIR/home" "$claude/-work-my-repo/subagents" "$claude/-elsewhere-other"
	touch "$claude/-work-my-repo/a.jsonl" "$claude/-work-my-repo/subagents/d.jsonl" "$claude/-elsewhere-other/c.jsonl"

	run env -u CODEX_HOME HOME="$TEST_DIR/home" CLAUDE_CONFIG_DIR="$TEST_DIR/claude-config" \
		bash "$SCRIPTS/discover-sessions.sh" my.repo 1 --platform claude --cwd-prefix /work/my.repo

	[ "$status" -eq 0 ]
	[ "${#lines[@]}" -eq 1 ]
	[[ "${lines[0]}" == "$claude/-work-my-repo/"*"a.jsonl" ]] || false

	run env -u CODEX_HOME HOME="$TEST_DIR/home" CLAUDE_CONFIG_DIR="$TEST_DIR/claude-config" \
		bash "$SCRIPTS/discover-sessions.sh" my.repo 1 --platform claude

	[ "$status" -eq 0 ]
	[[ "$output" == *"a.jsonl"* ]] || false
	[[ "$output" == *"c.jsonl"* ]] || false
	[[ "$output" != *"d.jsonl"* ]] || false
}

@test "discover-sessions honors CODEX_HOME and lists a shared store once" {
	mkdir -p "$TEST_DIR/home/.agents/sessions/2026"
	touch "$TEST_DIR/home/.agents/sessions/2026/rollout-1.jsonl"

	run env -u CLAUDE_CONFIG_DIR HOME="$TEST_DIR/home" CODEX_HOME="$TEST_DIR/home/.agents" \
		bash "$SCRIPTS/discover-sessions.sh" demo-repo 1 --platform codex

	[ "$status" -eq 0 ]
	[ "$output" = "$TEST_DIR/home/.agents/sessions/2026/rollout-1.jsonl" ]
}

@test "discover-sessions works from a relative zsh invocation with CDPATH" {
  mkdir -p "$TEST_DIR/home/.agents/sessions"
  touch "$TEST_DIR/home/.agents/sessions/rollout-1.jsonl"
  cd "$SCRIPTS/.."

  run env HOME="$TEST_DIR/home" CODEX_HOME="$TEST_DIR/home/.agents" CDPATH=. \
    zsh scripts/discover-sessions.sh demo-repo 1 --platform codex

  [ "$status" -eq 0 ]
  [ "$output" = "$TEST_DIR/home/.agents/sessions/rollout-1.jsonl" ]
}
