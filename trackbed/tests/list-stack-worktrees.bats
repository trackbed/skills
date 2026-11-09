#!/usr/bin/env bats

load 'test_helper/common'

setup() {
	REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
	SCRIPT="$REPO_ROOT/scripts/list-stack-worktrees.sh"
	TMP_DIR="$(cd "$(mktemp -d)" && pwd -P)"
	WORK="$TMP_DIR/work"
	BIN_DIR="$TMP_DIR/bin"
	mkdir -p "$BIN_DIR"
	cat > "$BIN_DIR/gh" <<'EOF'
#!/usr/bin/env bash
if [ "$1 $2 $3" != "stack view --json" ]; then
  echo "unexpected gh call: $*" >&2
  exit 99
fi
printf '%s\n' "$MOCK_STACK_VIEW"
exit "${MOCK_STACK_VIEW_STATUS:-0}"
EOF
	chmod +x "$BIN_DIR/gh"
	export PATH="$BIN_DIR:$PATH"

	init_test_git_repo "$WORK"
	cd "$WORK"
	git branch layer-1
	git branch layer-2
	git branch layer-3
	git switch -q layer-2
	export MOCK_STACK_VIEW_STATUS=0
	export MOCK_STACK_VIEW='{"trunk":"main","currentBranch":"layer-2","branches":[
		{"name":"layer-1","isMerged":true},
		{"name":"layer-2","isMerged":false},
		{"name":"layer-3","isMerged":false}]}'
}

teardown() {
	if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
		rm -rf "$TMP_DIR"
	fi
}

@test "prints nothing when no stack branch is checked out elsewhere" {
	run "$SCRIPT"
	[ "$status" -eq 0 ]
	[ -z "$output" ]
}

@test "lists unmerged layers and the trunk checked out in other worktrees" {
	git switch -q layer-1
	git worktree add -q "$TMP_DIR/ws-layer-2" layer-2
	git worktree add -q "$TMP_DIR/ws-layer-3" layer-3
	git worktree add -q "$TMP_DIR/ws-main" main

	run "$SCRIPT"
	[ "$status" -eq 0 ]
	[ "${lines[0]}" = "$(printf 'layer\tlayer-2\t%s' "$TMP_DIR/ws-layer-2")" ]
	[ "${lines[1]}" = "$(printf 'layer\tlayer-3\t%s' "$TMP_DIR/ws-layer-3")" ]
	[ "${lines[2]}" = "$(printf 'trunk\tmain\t%s' "$TMP_DIR/ws-main")" ]
	[ "${#lines[@]}" -eq 3 ]
}

@test "skips merged layers and the current worktree" {
	git switch -q main
	git worktree add -q "$TMP_DIR/ws-layer-1" layer-1
	git worktree add -q "$TMP_DIR/ws-layer-3" layer-3
	cd "$TMP_DIR/ws-layer-3"

	run "$SCRIPT"
	[ "$status" -eq 0 ]
	[ "$output" = "$(printf 'trunk\tmain\t%s' "$WORK")" ]
}

@test "--no-trunk leaves the trunk worktree out but keeps the layers" {
	git switch -q layer-1
	git worktree add -q "$TMP_DIR/ws-main" main
	git worktree add -q "$TMP_DIR/ws-layer-3" layer-3

	run "$SCRIPT" --no-trunk
	[ "$status" -eq 0 ]
	[ "$output" = "$(printf 'layer\tlayer-3\t%s' "$TMP_DIR/ws-layer-3")" ]
}

@test "fails closed when gh stack view fails" {
	export MOCK_STACK_VIEW_STATUS=2
	run "$SCRIPT"
	[ "$status" -eq 1 ]
	[[ "$output" == *"Could not read the stack"* ]]
}

@test "fails closed on a stack view without a trunk or branch list" {
	export MOCK_STACK_VIEW='{"branches":[]}'
	run "$SCRIPT"
	[ "$status" -eq 1 ]
	[[ "$output" == *"did not return a valid stack"* ]]

	export MOCK_STACK_VIEW='{"trunk":"main","branches":[{"name":"bad\tname"}]}'
	run "$SCRIPT"
	[ "$status" -eq 1 ]
}

@test "rejects unknown arguments" {
	run "$SCRIPT" --upstack
	[ "$status" -eq 1 ]
	[[ "$output" == *"Usage:"* ]]
}

@test "stack skills share gh-stack exit codes and cross-worktree rules" {
	local stack_skill="$REPO_ROOT/skills/pr:stack/SKILL.md"
	local rebase_skill="$REPO_ROOT/skills/pr:rebase/SKILL.md"
	local rules="$REPO_ROOT/skills/pr:stack/references/cli-agent-rules.md"
	local shared="$REPO_ROOT/shared/git/references/stack-operations.md"

	for consumer in "$stack_skill" "$rebase_skill"; do
		grep -F '${CLAUDE_PLUGIN_ROOT}/shared/git/references/stack-operations.md' "$consumer"
		grep -F '${CLAUDE_PLUGIN_ROOT}/scripts/list-stack-worktrees.sh' "$consumer"
	done
	grep -F '"${CLAUDE_PLUGIN_ROOT}/scripts/list-stack-worktrees.sh"' "$shared"

	# The exit codes live only in the shared reference, including the clone-wide lock.
	! grep -E '^\| [0-9]+ \|' "$rules" || false
	for code in 0 1 2 3 4 5 6 7 8 9 10; do
		grep -E "^\| $code \|" "$shared"
	done
	grep -F 'Another gh-stack process in any worktree of this clone holds the lock' "$shared"

	# Other workspaces are named and confirmed before every rebase or sync.
	grep -F 'Before every `gh stack rebase` and `gh stack sync`' "$shared"
	grep -F 'should be idle' "$shared"
	grep -F 'This confirmation applies in every mode, including auto and `--force-push`' "$shared"
	grep -F 'In a non-interactive run, stop before the command and report the listed workspaces' "$shared"
	grep -F 'A `--force-push` run delegated by `trackbed:pr:fix-ci` is non-interactive, so it stops and reports' "$rebase_skill"

	# Conflicts resolve where gh-stack paused them, never by touching another workspace's state.
	grep -F 'When it prints `Conflict worktree: <path>`, set `CONFLICT_WORKTREE` to that path and resolve the conflict there' "$shared"
	grep -F 'git -C "$CONFLICT_WORKTREE" add -- <file>' "$shared"
	grep -F 'Never stash, commit, reset, check out, or clean there.' "$shared"
	grep -F 'run `gh stack rebase --abort` and report the path and branch' "$shared"
	grep -F 'resolve each conflicted file in the worktree gh-stack names' "$rebase_skill"
	grep -F 'Resolve them in the worktree gh-stack names' "$stack_skill"

	# Paused rebases belong to the session that started them.
	grep -F 'only for a rebase that this session started and saw pause with exit 3' "$shared"
	grep -F 'Continue or abort only a rebase this session started.' "$stack_skill"
	grep -F 'Continue or abort only a rebase this session started, and pass `--accept-base-change` only under the shared reference' "$rebase_skill"

	# --accept-base-change needs explicit approval in every mode, and trunk changes are reported.
	grep -F 'Pass `--accept-base-change` only when the user explicitly approves it' "$shared"
	grep -F "**Base changes** rules, in every mode including auto mode." "$rebase_skill"
	grep -F 'report the old and the new trunk' "$shared"
	grep -F 'every other workspace it changed, and any change of trunk' "$rebase_skill"
	! grep -R -n -E 'gh stack (rebase|sync)[^`]*--accept-base-change' "$REPO_ROOT/skills" "$REPO_ROOT/shared" || false
}
