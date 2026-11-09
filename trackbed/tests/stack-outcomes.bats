#!/usr/bin/env bats

load 'test_helper/common'

setup() {
	REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
	SHARED="$REPO_ROOT/shared/git/references/stack-operations.md"
	STACK_SKILL="$REPO_ROOT/skills/pr:stack/SKILL.md"
	REBASE_SKILL="$REPO_ROOT/skills/pr:rebase/SKILL.md"
	TMP_DIR="$(mktemp -d)"
	BIN_DIR="$TMP_DIR/bin"
	mkdir -p "$BIN_DIR"
	write_mock_gh
	export PATH="$BIN_DIR:$PATH"
}

teardown() {
	if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
		rm -rf "$TMP_DIR"
	fi
}

# extract_block <file> <heading> <index> <output>: write the index-th bash block
# (1-based) that follows the exact Markdown heading line.
extract_block() {
	python3 - "$1" "$2" "$3" "$4" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text()
section = text.split("\n" + sys.argv[2] + "\n", 1)[1]
blocks = section.split("```bash\n")[1:]
Path(sys.argv[4]).write_text(blocks[int(sys.argv[3]) - 1].split("```", 1)[0])
PY
}

write_mock_gh() {
	cat >"$BIN_DIR/gh" <<'GH'
#!/bin/bash
if [ "$1 $2" = "stack sync" ]; then
  printf '%s\n' "${MOCK_SYNC_OUTPUT:-}" >&2
  exit "${MOCK_SYNC_STATUS:-0}"
fi
if [ "$1 $2 $3" = "stack view --json" ]; then
  printf '%s\n' "${MOCK_STACK_VIEW_STDOUT:-}"
  exit "${MOCK_STACK_VIEW_STATUS:-0}"
fi
if [ "$1 $2" = "api graphql" ]; then
  number="" jq_expr=""
  shift 2
  while [ "$#" -gt 0 ]; do
    case "$1" in
      -F) [[ "$2" == number=* ]] && number=${2#number=}; shift 2 ;;
      --jq) jq_expr=$2; shift 2 ;;
      *) shift ;;
    esac
  done
  printf '%s\n' "$number" >>"$MOCK_GRAPHQL_LOG"
  [ "${MOCK_GRAPHQL_STATUS:-0}" -eq 0 ] || exit "$MOCK_GRAPHQL_STATUS"
  state_var="MOCK_PR_$number"
  printf '%s\n' "${!state_var}" | jq -r "$jq_expr"
  exit
fi
echo "unexpected gh call: $*" >&2
exit 99
GH
	chmod +x "$BIN_DIR/gh"
}

prepare_synced_stack() {
	init_test_git_repo "$TMP_DIR/work" --origin "$TMP_DIR/remote.git"
	cd "$TMP_DIR/work"
	git switch -c feature >/dev/null 2>&1
	git commit --allow-empty -m "Feature work" >/dev/null
	git switch -c layer >/dev/null 2>&1
	git commit --allow-empty -m "Layer work" >/dev/null
	git push origin feature layer >/dev/null 2>&1
	export STACK_REMOTE=origin
	export MOCK_SYNC_OUTPUT=$'Pushed 2 branches\nStack synced'
	export MOCK_STACK_VIEW_STDOUT='{"trunk":"main","branches":[{"name":"gone","isMerged":true,"isQueued":false},{"name":"waiting","isMerged":false,"isQueued":true},{"name":"feature","isMerged":false,"isQueued":false},{"name":"layer","isMerged":false,"isQueued":false}]}'
	SYNC_CHECK="$TMP_DIR/sync-check.sh"
	extract_block "$SHARED" "## Sync outcomes" 1 "$SYNC_CHECK"
}

@test "sync check reports synced only when every active remote head matches" {
	prepare_synced_stack

	run bash "$SYNC_CHECK"

	[ "$status" -eq 0 ]
	[[ "$output" == *"STACK_SYNCED=true"* ]]
}

@test "sync check reports a divergence abort as not synced" {
	prepare_synced_stack
	export MOCK_SYNC_OUTPUT=$'⚠ Your local stack has diverged from the stack on GitHub\nℹ Sync aborted — no changes were made'

	run bash "$SYNC_CHECK"

	[ "$status" -eq 1 ]
	[[ "$output" == *"Not synced: gh-stack aborted because the local and GitHub branch lists diverged."* ]]
	[[ "$output" != *"STACK_SYNCED=true"* ]]
}

@test "sync check reports a failed gh stack sync as not synced even when the heads match" {
	prepare_synced_stack
	export MOCK_SYNC_OUTPUT='Another gh-stack command is running' MOCK_SYNC_STATUS=8

	run bash "$SYNC_CHECK"

	[ "$status" -eq 1 ]
	[[ "$output" == *"Not synced: gh stack sync exited 8."* ]]
	[[ "$output" == *"SYNC_STATUS=8"* ]]
	[[ "$output" != *"STACK_SYNCED=true"* ]]
}

@test "sync check needs no stack inventory once every branch merged" {
	prepare_synced_stack
	export MOCK_SYNC_OUTPUT='No active branches to push (all merged)' MOCK_STACK_VIEW_STATUS=6

	run bash "$SYNC_CHECK"

	[ "$status" -eq 0 ]
	[[ "$output" == *"STACK_SYNCED=true"* ]]
}

@test "sync check reports a failed push as not synced even when the heads match" {
	prepare_synced_stack
	export MOCK_SYNC_OUTPUT=$'⚠ Push failed: exit status 1\n  Run `gh stack push` to retry.\n✓ Branches synced'

	run bash "$SYNC_CHECK"

	[ "$status" -eq 1 ]
	[[ "$output" == *"Not synced: gh-stack could not push the stack branches."* ]]
}

@test "sync check compares each active branch with the remote" {
	prepare_synced_stack
	git commit --allow-empty -m "Unpushed layer work" >/dev/null

	run bash "$SYNC_CHECK"

	[ "$status" -eq 1 ]
	[[ "$output" == *"Not synced: origin/layer is at "*", but the local branch is at $(git rev-parse layer)."* ]]
	[[ "$output" != *"origin/feature"* ]]

	git push origin --delete feature >/dev/null 2>&1
	git push origin layer >/dev/null 2>&1
	run bash "$SYNC_CHECK"
	[ "$status" -eq 1 ]
	[[ "$output" == *"Not synced: origin/feature is at no branch"* ]]
}

@test "sync check reports an unknown outcome when the inventory cannot be read" {
	prepare_synced_stack
	export MOCK_STACK_VIEW_STATUS=1
	run bash "$SYNC_CHECK"
	[ "$status" -eq 2 ]
	[[ "$output" != *"STACK_SYNCED=true"* ]]

	export MOCK_STACK_VIEW_STATUS=0
	export MOCK_STACK_VIEW_STDOUT='{"branches":[{"name":"missing","isMerged":false,"isQueued":false}]}'
	run bash "$SYNC_CHECK"
	[ "$status" -eq 2 ]

	export MOCK_STACK_VIEW_STDOUT='{}'
	run bash "$SYNC_CHECK"
	[ "$status" -eq 2 ]
}

prepare_merge_check() {
	MERGE_CHECK="$TMP_DIR/merge-check.sh"
	extract_block "$SHARED" "## Merge outcomes" 1 "$MERGE_CHECK"
	export MOCK_GRAPHQL_LOG="$TMP_DIR/graphql.log"
	export TARGET_STACK_JSON='[{"number":41,"pull_requests":[{"number":17},{"number":18},{"number":19}]}]'
	export TARGET_PR_NUMBER=18
	export MOCK_PR_17='{"data":{"repository":{"pullRequest":{"state":"MERGED","isInMergeQueue":false}}}}'
	export MOCK_PR_18='{"data":{"repository":{"pullRequest":{"state":"OPEN","isInMergeQueue":true}}}}'
	export MOCK_PR_19='{"data":{"repository":{"pullRequest":{"state":"OPEN","isInMergeQueue":false}}}}'
}

@test "merge check reports merged and queued PRs separately up to the target" {
	prepare_merge_check

	run bash "$MERGE_CHECK"

	[ "$status" -eq 0 ]
	[[ "$output" == *"MERGED_PRS=#17"* ]]
	[[ "$output" == *"QUEUED_PRS=#18"* ]]
	[[ "$output" == *"OPEN_PRS="* ]]
	[[ "$output" != *"#19"* ]]
	[ "$(cat "$MOCK_GRAPHQL_LOG")" = $'17\n18' ]
}

@test "merge check keeps open and closed PRs out of the landed lists" {
	prepare_merge_check
	export TARGET_PR_NUMBER=19
	export MOCK_PR_18='{"data":{"repository":{"pullRequest":{"state":"CLOSED","isInMergeQueue":false}}}}'

	run bash "$MERGE_CHECK"

	[ "$status" -eq 0 ]
	[[ "$output" == *"MERGED_PRS=#17"* ]]
	[[ "$output" == *"QUEUED_PRS="$'\n'* ]]
	[[ "$output" == *"OPEN_PRS=#18(closed) #19"* ]]
}

@test "merge check fails closed on an API failure or a target outside the stack" {
	prepare_merge_check
	export MOCK_GRAPHQL_STATUS=1
	run bash "$MERGE_CHECK"
	[ "$status" -ne 0 ]
	[[ "$output" != *"MERGED_PRS="* ]]

	export MOCK_GRAPHQL_STATUS=0
	export TARGET_PR_NUMBER=99
	run bash "$MERGE_CHECK"
	[ "$status" -ne 0 ]

	export TARGET_PR_NUMBER=18 TARGET_STACK_JSON='[{"number":41,"pull_requests":[{"number":"17"},{"number":18}]}]'
	run bash "$MERGE_CHECK"
	[ "$status" -ne 0 ]
	[[ "$output" != *"MERGED_PRS="* ]]

	unset TARGET_STACK_JSON
	run bash "$MERGE_CHECK"
	[ "$status" -ne 0 ]
	[[ "$output" == *"Run the merge-target resolution in this Bash call first"* ]]
}

@test "merge guidance prunes only after every PR merged and never re-runs a possibly running merge" {
	grep -qF 'Only when every PR through the target shows as merged, repeat the routine-sync preflight and run **Routine sync** with `--prune`.' "$STACK_SKILL"
	grep -qF "follow the shared reference's **Merge outcomes** section next" "$STACK_SKILL"
	grep -qF 'MERGE_OUTPUT=$(gh stack merge "$MERGE_TARGET" "${MERGE_ARGS[@]}" 2>&1)' "$STACK_SKILL"
	grep -qF "printf '%s\\nMERGE_STATUS=%s\\n' \"\$MERGE_OUTPUT\" \"\$MERGE_STATUS\"" "$STACK_SKILL"
	grep -qF "Report the stack as synced only when the block prints \`STACK_SYNCED=true\`." "$STACK_SKILL"
	grep -qF 'Do not run the pruning sync; tell the user to run it once the queue has merged them.' "$SHARED"
	grep -qF "Never re-run the merge yourself: report the states and gh-stack's message" "$SHARED"
	grep -qF 'stack merges are atomic, so nothing landed. Restack before merging again' "$SHARED"
	grep -qF '| 4 | GitHub API failure | After `merge`, never retry; follow **Merge outcomes**.' "$SHARED"
	grep -qF 'Run the merge-target resolution, this block, and the shared **Merge outcomes** check in one Bash call with the maximum Bash timeout' "$STACK_SKILL"
	grep -qF 'A Merging call that printed `MERGE_STARTED=true` but ends without printing `MERGE_STATUS`, for example because the Bash tool timed out, counts as exit 4: never re-run it' "$SHARED"
	grep -qF 'A call that stopped before printing `MERGE_STARTED=true` never ran the merge: follow the stop message from the target resolution or method check.' "$SHARED"
	grep -qxF 'echo "MERGE_STARTED=true"' "$STACK_SKILL"
	grep -A1 -xF 'echo "MERGE_STARTED=true"' "$STACK_SKILL" | grep -qF 'MERGE_OUTPUT=$(gh stack merge "$MERGE_TARGET"'
	! grep -E '^gh stack merge' "$STACK_SKILL"
}

prepare_linked_worktree() {
	init_test_git_repo "$TMP_DIR/main"
	cd "$TMP_DIR/main"
	git worktree add -q -b topic "$TMP_DIR/linked" >/dev/null 2>&1
	IN_PROGRESS_CHECK="$TMP_DIR/in-progress.sh"
	python3 - "$REBASE_SKILL" "$IN_PROGRESS_CHECK" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text()
section = text.split("**Check for rebase/merge in progress:**", 1)[1]
block = section.split("```bash\n", 1)[1].split("```", 1)[0]
Path(sys.argv[2]).write_text("\n".join(line.removeprefix("   ") for line in block.splitlines()) + "\n")
PY
}

@test "pr:rebase detects a paused rebase inside a linked worktree" {
	prepare_linked_worktree
	cd "$TMP_DIR/linked"
	[ -f .git ]

	run bash "$IN_PROGRESS_CHECK"
	[ "$status" -eq 0 ]

	printf 'topic\n' >tracked.txt
	git commit -qam "topic change"
	git -C "$TMP_DIR/main" switch -q -c other main
	printf 'other\n' >"$TMP_DIR/main/tracked.txt"
	git -C "$TMP_DIR/main" commit -qam "other change"
	run git rebase other
	[ "$status" -ne 0 ]

	run bash "$IN_PROGRESS_CHECK"
	[ "$status" -eq 1 ]
	[[ "$output" == *"In progress: rebase-merge"* ]]

	cd "$TMP_DIR"
	run bash "$IN_PROGRESS_CHECK"
	[ "$status" -eq 1 ]
	[[ "$output" != *"In progress"* ]]
	grep -qF "If it exits 1, stop. When it printed \`In progress\`, use this error; otherwise report Git's message:" "$REBASE_SKILL"
	! grep -qF 'ls -d .git/' "$REBASE_SKILL"
}

@test "pr:rebase detects a paused merge inside a linked worktree" {
	prepare_linked_worktree
	cd "$TMP_DIR/linked"
	printf 'topic\n' >tracked.txt
	git commit -qam "topic change"
	git -C "$TMP_DIR/main" switch -q -c other main
	printf 'other\n' >"$TMP_DIR/main/tracked.txt"
	git -C "$TMP_DIR/main" commit -qam "other change"
	run git merge other
	[ "$status" -ne 0 ]

	run bash "$IN_PROGRESS_CHECK"
	[ "$status" -eq 1 ]
	[[ "$output" == *"In progress: MERGE_HEAD"* ]]
}

@test "pr:rebase stack path stops with a reason on every other gh-stack failure" {
	grep -qF 'this stack path continues after a nonzero exit in exactly three cases' "$REBASE_SKILL"
	grep -qF 'including 7 (a rebase is paused, possibly in another workspace), 8 (another gh-stack command holds the lock), and 4 (a GitHub lookup failed)' "$REBASE_SKILL"
	grep -qF 'This skill does not retry them' "$REBASE_SKILL"
	grep -qF 'report the command, its exit code, the table' "$REBASE_SKILL"
	grep -qF 'Never fall back to `git rebase` or a single-branch push for a stack branch' "$REBASE_SKILL"
}
