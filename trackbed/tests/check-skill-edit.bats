#!/usr/bin/env bats

load 'test_helper/common'

bats_require_minimum_version 1.5.0

# The hook resolves the repository from its own location, so each test runs a
# copy of trackbed/scripts inside a fixture repository with one clean skill.
setup() {
  PLUGIN_DIR="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  FIXTURE="$(mktemp -d)"
  mkdir -p "$FIXTURE/trackbed"
  cp -R "$PLUGIN_DIR/scripts" "$FIXTURE/trackbed/scripts"
  HOOK="$FIXTURE/trackbed/scripts/check-skill-edit.sh"
  SKILL_DIR="$FIXTURE/trackbed/skills/demo:clean"
  write_file "$SKILL_DIR/SKILL.md" <<'EOF'
---
name: demo:clean
description: Fixture skill for the skill-edit hook.
disable-model-invocation: false
user-invocable: true
---
# Demo

Read `references/guide.md` before starting.
EOF
  write_file "$SKILL_DIR/references/guide.md" <<'EOF'
# Guide
EOF
  write_file "$FIXTURE/README.md" <<'EOF'
# Fixture
EOF
  unset TRACKBED_SKILL_EDIT_CHECK
}

teardown() {
  rm -rf "$FIXTURE"
}

edit_event() {
  jq -cn --arg path "$1" --arg text "${2:-}" \
    '{tool_name: "Edit", tool_input: {file_path: $path, new_string: $text}}'
}

# Claude Code shows the agent only stderr from an exit-2 hook, so keep it apart.
run_hook_for() {
  run --separate-stderr bash -c 'printf "%s" "$1" | bash "$2"' _ "$(edit_event "$@")" "$HOOK"
}

run_hook_with_path() {
  run --separate-stderr env PATH="$1" "$BASH" -c 'printf "%s" "$1" | "$0" "$2"' \
    "$BASH" "$(edit_event "$2" "${3:-}")" "$HOOK"
}

break_guide_reference() {
  printf '\nRead [the code map](../../docs/code-map.md) first.\n' >>"$SKILL_DIR/references/guide.md"
}

@test "project settings register the hook for Write and Edit" {
  run jq -r '.hooks.PostToolUse[] | select(.matcher == "Write|Edit") | .hooks[].command' \
    "$PLUGIN_DIR/../.claude/settings.json"

  [ "$status" -eq 0 ]
  [ "$output" = 'bash "$CLAUDE_PROJECT_DIR/trackbed/scripts/check-skill-edit.sh"' ]
}

@test "a clean SKILL.md edit prints nothing" {
  run_hook_for "$SKILL_DIR/SKILL.md"

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "a broken resource reference is reported to the agent with the checker message" {
  break_guide_reference

  run_hook_for "$SKILL_DIR/references/guide.md"

  [ "$status" -eq 2 ]
  [ -z "$output" ]
  [[ "$stderr" == *"Skill checks failed after editing trackbed/skills/demo:clean/references/guide.md:"* ]] || false
  [[ "$stderr" == *"skills/demo:clean/references/guide.md:3: escapes skill directory: ../../docs/code-map.md"* ]] || false
  [[ "$stderr" != *"lint-skill-contracts.py"* ]] || false
}

@test "a SKILL.md frontmatter mistake is reported by the single-skill linter" {
  sed -i.bak '/^user-invocable:/d' "$SKILL_DIR/SKILL.md"
  rm "$SKILL_DIR/SKILL.md.bak"

  run_hook_for "$SKILL_DIR/SKILL.md"

  [ "$status" -eq 2 ]
  [ -z "$output" ]
  [[ "$stderr" == *"lint-skill-contracts.py --skill trackbed/skills/demo:clean/SKILL.md:"* ]] || false
  [[ "$stderr" == *"missing frontmatter field 'user-invocable'"* ]] || false
  [[ "$stderr" != *"check-installed-resources.js:"* ]] || false
}

@test "edits outside trackbed/skills are ignored even when their text names skills" {
  break_guide_reference

  run_hook_for "$FIXTURE/README.md" "See trackbed/skills/demo:clean/SKILL.md."

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "edits outside trackbed/skills stay silent when jq is missing" {
  mkdir "$FIXTURE/bin"
  ln -s "$(command -v cat)" "$FIXTURE/bin/cat"

  run_hook_with_path "$FIXTURE/bin" "$FIXTURE/README.md" "See trackbed/skills/demo:clean/SKILL.md."

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "a trackbed/skills path in another checkout is ignored" {
  break_guide_reference
  write_file "$FIXTURE/other/trackbed/skills/demo:other/SKILL.md" <<'EOF'
# No frontmatter
EOF

  run_hook_for "$FIXTURE/other/trackbed/skills/demo:other/SKILL.md"

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "a missing interpreter skips the check instead of reporting a failure" {
  mkdir "$FIXTURE/bin"
  ln -s "$(command -v cat)" "$FIXTURE/bin/cat"
  ln -s "$(command -v jq)" "$FIXTURE/bin/jq"

  run_hook_with_path "$FIXTURE/bin" "$SKILL_DIR/SKILL.md"

  [ "$status" -eq 1 ]
  [[ "$stderr" == *"skill edit check skipped: node not found"* ]] || false
  [[ "$stderr" != *"Skill checks failed"* ]] || false
}

@test "TRACKBED_SKILL_EDIT_CHECK=0 turns the hook off" {
  break_guide_reference

  TRACKBED_SKILL_EDIT_CHECK=0 run_hook_for "$SKILL_DIR/references/guide.md"

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}
