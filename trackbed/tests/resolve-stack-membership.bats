#!/usr/bin/env bats

load 'test_helper/common'

setup() {
	REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
	SCRIPT="$REPO_ROOT/scripts/resolve-stack-membership.sh"
	TMP_DIR="$(mktemp -d)"
	WORK="$TMP_DIR/work"
	BIN_DIR="$TMP_DIR/bin"
	GH_LOG="$TMP_DIR/gh.log"
	mkdir -p "$BIN_DIR"
	write_mock_gh
	export PATH="$BIN_DIR:$PATH"
	export GH_LOG

	init_test_git_repo "$WORK"
	cd "$WORK"
	git switch -c feature >/dev/null 2>&1
	git remote add origin https://github.com/acme/demo.git

	export MOCK_EXTENSION_STATUS=0
	export MOCK_EXTENSION_VERSION=0.3.0
	export MOCK_STACK_VIEW_STATUS=2
	export MOCK_PR_LIST_STATUS=0
	export MOCK_PR_NUMBER=""
	export MOCK_REPO_VIEW_STATUS=0
	export MOCK_STACK_API_STATUS=0
	export MOCK_STACK_NUMBER=""
	export MOCK_TARGET_STACK_JSON='[{"number":41,"pull_requests":[{"number":17},{"number":18}]}]'
	export MOCK_ALL_STACKS_JSON='[[{"number":41}]]'
	export MOCK_STACK_LIST_STATUS=0
}

teardown() {
	if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
		rm -rf "$TMP_DIR"
	fi
}

write_mock_gh() {
	cat >"$BIN_DIR/gh" <<'GH'
#!/bin/sh
{
  printf 'command'
  for argument in "$@"; do
    printf ' [%s]' "$argument"
  done
  printf '\n'
} >>"$GH_LOG"

if [ "$1" = "stack" ] && [ "$2" = "--version" ]; then
  [ "${MOCK_EXTENSION_STATUS:-0}" -eq 0 ] || exit "$MOCK_EXTENSION_STATUS"
  printf 'gh stack version %s\n' "${MOCK_EXTENSION_VERSION:-0.3.0}"
  exit 0
fi

if [ "$1" = "stack" ] && [ "$2" = "view" ] && [ "$3" = "--json" ]; then
  if [ -n "${MOCK_STACK_VIEW_STDOUT+set}" ] || [ -n "${MOCK_STACK_VIEW_STDERR+set}" ]; then
    [ -z "${MOCK_STACK_VIEW_STDOUT:-}" ] || printf '%s\n' "$MOCK_STACK_VIEW_STDOUT"
    [ -z "${MOCK_STACK_VIEW_STDERR:-}" ] || printf '%s\n' "$MOCK_STACK_VIEW_STDERR" >&2
  elif [ "${MOCK_STACK_VIEW_STATUS:-2}" -eq 0 ]; then
    printf '{"trunk":"main","currentBranch":"feature","branches":[{"name":"feature"}]}\n'
  else
    printf 'mock stack view failure\n' >&2
  fi
  exit "${MOCK_STACK_VIEW_STATUS:-2}"
fi

if [ "$1" = "pr" ] && [ "$2" = "list" ]; then
  [ "${MOCK_PR_LIST_STATUS:-0}" -eq 0 ] || {
    printf 'mock PR lookup failure\n' >&2
    exit "$MOCK_PR_LIST_STATUS"
  }
  printf '%s\n' "${MOCK_PR_NUMBER:-}"
  exit 0
fi

if [ "$1" = "repo" ] && [ "$2" = "view" ]; then
  [ "${MOCK_REPO_VIEW_STATUS:-0}" -eq 0 ] || exit "$MOCK_REPO_VIEW_STATUS"
  printf 'acme/demo\n'
  exit 0
fi

if [ "$1" = "api" ] && [ "$2" = "graphql" ]; then
  [ "${MOCK_STACK_API_STATUS:-0}" -eq 0 ] || {
    printf 'mock GraphQL failure\n' >&2
    exit "$MOCK_STACK_API_STATUS"
  }
  printf '%s\n' "${MOCK_STACK_NUMBER:-}"
  exit 0
fi

if [ "$1" = "api" ] && [ "$2" = "--paginate" ] && [ "$3" = "--slurp" ]; then
  [ "${MOCK_STACK_LIST_STATUS:-0}" -eq 0 ] || exit "$MOCK_STACK_LIST_STATUS"
  printf '%s\n' "$MOCK_ALL_STACKS_JSON"
  exit 0
fi

if [ "$1" = "api" ]; then
  [ "${MOCK_STACK_API_STATUS:-0}" -eq 0 ] || exit "$MOCK_STACK_API_STATUS"
  printf '%s\n' "$MOCK_TARGET_STACK_JSON"
  exit 0
fi

if [ "$1" = "stack" ] && [ "$2" = "checkout" ]; then
  [ "${MOCK_STACK_CHECKOUT_STATUS:-0}" -eq 0 ] || exit "$MOCK_STACK_CHECKOUT_STATUS"
  git switch top >/dev/null 2>&1 || exit 97
  exit 0
fi

if [ "$1" = "stack" ] && { [ "$2" = "merge" ] || [ "$2" = "link" ]; }; then
  exit 0
fi

exit 97
GH
	chmod +x "$BIN_DIR/gh"
}

load_assignments() {
	local assignments
	assignments=$(printf '%s\n' "$output" | grep -E '^(STACK_MEMBERSHIP|STACK_CLI_AVAILABLE|STACK_CLI_SUPPORTED|STACK_PR_NUMBER|STACK_NUMBER)=' || true)
	eval "$assignments"
}

@test "reports local membership when gh-stack tracks the current branch" {
	export MOCK_STACK_VIEW_STATUS=0

	run "$SCRIPT"

	[ "$status" -eq 0 ]
	load_assignments
	[ "$STACK_MEMBERSHIP" = "local" ]
	[ "$STACK_CLI_AVAILABLE" = "1" ]
	[ "$STACK_PR_NUMBER" = "" ]
	[ "$STACK_NUMBER" = "" ]
	! grep -q 'command \[pr\] \[list\]' "$GH_LOG"
}

@test "treats a zero-exit stack view without stack JSON as untracked" {
	export MOCK_STACK_VIEW_STATUS=0
	export MOCK_STACK_VIEW_STDOUT=""
	export MOCK_STACK_VIEW_STDERR='✗ current branch "feature" is not part of a stack'
	export MOCK_PR_NUMBER=17

	run "$SCRIPT"

	[ "$status" -eq 0 ]
	load_assignments
	[ "$STACK_MEMBERSHIP" = "none" ]
	[ "$STACK_PR_NUMBER" = "17" ]
	[[ "$output" != *"is not part of a stack"* ]]
	grep -q 'command \[api\] \[graphql\]' "$GH_LOG"
}

@test "consults the remote stack when a zero-exit stack view prints plain text" {
	export MOCK_STACK_VIEW_STATUS=0
	export MOCK_STACK_VIEW_STDOUT='current branch "feature" is not part of a stack'
	export MOCK_PR_NUMBER=17
	export MOCK_STACK_NUMBER=41

	run "$SCRIPT"

	[ "$status" -eq 0 ]
	load_assignments
	[ "$STACK_MEMBERSHIP" = "remote" ]
	[ "$STACK_NUMBER" = "41" ]
}

@test "reports local membership when stack JSON follows leading whitespace" {
	export MOCK_STACK_VIEW_STATUS=0
	export MOCK_STACK_VIEW_STDOUT='
  {"trunk":"main","currentBranch":"feature","branches":[{"name":"feature"}]}'

	run "$SCRIPT"

	[ "$status" -eq 0 ]
	load_assignments
	[ "$STACK_MEMBERSHIP" = "local" ]
	! grep -q 'command \[pr\] \[list\]' "$GH_LOG"
}

@test "fails closed when a zero-exit stack view prints malformed JSON" {
	export MOCK_STACK_VIEW_STATUS=0
	export MOCK_STACK_VIEW_STDOUT='{not-json'

	run "$SCRIPT"

	[ "$status" -eq 1 ]
	[[ "$output" == *"gh stack view returned invalid stack JSON"* ]]
	! grep -q 'command \[pr\] \[list\]' "$GH_LOG"
}

@test "fails closed when a zero-exit stack view prints the wrong JSON shape" {
	export MOCK_STACK_VIEW_STATUS=0
	export MOCK_STACK_VIEW_STDOUT='[]'

	run "$SCRIPT"

	[ "$status" -eq 1 ]
	[[ "$output" == *"gh stack view returned invalid stack JSON"* ]]
	! grep -q 'command \[pr\] \[list\]' "$GH_LOG"
}

@test "reports no membership only after a definitive remote lookup" {
	export MOCK_PR_NUMBER=17

	run "$SCRIPT"

	[ "$status" -eq 0 ]
	load_assignments
	[ "$STACK_MEMBERSHIP" = "none" ]
	[ "$STACK_CLI_AVAILABLE" = "1" ]
	[ "$STACK_PR_NUMBER" = "17" ]
	[ "$STACK_NUMBER" = "" ]
	grep -q 'command \[api\] \[graphql\]' "$GH_LOG"
}

@test "detects server-side membership when local tracking and extension are absent" {
	export MOCK_EXTENSION_STATUS=1
	export MOCK_PR_NUMBER=17
	export MOCK_STACK_NUMBER=41

	run "$SCRIPT"

	[ "$status" -eq 0 ]
	load_assignments
	[ "$STACK_MEMBERSHIP" = "remote" ]
	[ "$STACK_CLI_AVAILABLE" = "0" ]
	[ "$STACK_CLI_SUPPORTED" = "0" ]
	[ "$STACK_PR_NUMBER" = "17" ]
	[ "$STACK_NUMBER" = "41" ]
}

@test "an old gh-stack still resolves an unstacked branch with an upgrade warning" {
	for version in 0.0.8 0.2.1; do
		export MOCK_EXTENSION_VERSION="$version"
		: >"$GH_LOG"
		run "$SCRIPT"

		[ "$status" -eq 0 ]
		[[ "$output" == *"Warning: gh-stack v$version is older than v0.3.0"* ]]
		[[ "$output" == *"upgrade to v0.3.0 or newer with 'gh extension upgrade stack'."* ]]
		load_assignments
		[ "$STACK_MEMBERSHIP" = "none" ]
		[ "$STACK_CLI_AVAILABLE" = "1" ]
		[ "$STACK_CLI_SUPPORTED" = "0" ]
		grep -q 'command \[stack\] \[view\] \[--json\]' "$GH_LOG"
		grep -q 'command \[pr\] \[list\]' "$GH_LOG"
	done
}

@test "an old gh-stack still reports server-side membership" {
	export MOCK_EXTENSION_VERSION=0.2.1
	export MOCK_PR_NUMBER=17
	export MOCK_STACK_NUMBER=41

	run "$SCRIPT"

	[ "$status" -eq 0 ]
	load_assignments
	[ "$STACK_MEMBERSHIP" = "remote" ]
	[ "$STACK_CLI_SUPPORTED" = "0" ]
	[ "$STACK_NUMBER" = "41" ]
}

@test "an old gh-stack that tracks the branch locally stops with an upgrade instruction" {
	export MOCK_EXTENSION_VERSION=0.2.1
	export MOCK_STACK_VIEW_STATUS=0

	run "$SCRIPT"

	[ "$status" -eq 1 ]
	[[ "$output" == *"Branch 'feature' is in a local gh-stack stack, and stack commands are unsafe on this gh-stack version; upgrade to v0.3.0 or newer with 'gh extension upgrade stack', then retry."* ]]
	[[ "$output" != *"STACK_MEMBERSHIP="* ]]
	! grep -q 'command \[pr\] \[list\]' "$GH_LOG"
}

@test "accepts gh-stack versions at or above the v0.3.0 floor" {
	export MOCK_STACK_VIEW_STATUS=0

	for version in 0.3.0 0.10.0 1.0.0; do
		export MOCK_EXTENSION_VERSION="$version"
		run "$SCRIPT"

		[ "$status" -eq 0 ]
		[[ "$output" != *"Warning:"* ]]
		load_assignments
		[ "$STACK_MEMBERSHIP" = "local" ]
		[ "$STACK_CLI_AVAILABLE" = "1" ]
		[ "$STACK_CLI_SUPPORTED" = "1" ]
	done
}

@test "an unparseable gh-stack version is treated as unsupported, not as a failure" {
	export MOCK_EXTENSION_VERSION=development

	run "$SCRIPT"

	[ "$status" -eq 0 ]
	[[ "$output" == *"Warning: could not parse the installed gh-stack version"* ]]
	load_assignments
	[ "$STACK_MEMBERSHIP" = "none" ]
	[ "$STACK_CLI_SUPPORTED" = "0" ]
}

@test "fails closed on an unexpected gh-stack error" {
	export MOCK_STACK_VIEW_STATUS=4

	run "$SCRIPT"

	[ "$status" -eq 4 ]
	[[ "$output" == *"mock stack view failure"* ]]
	[[ "$output" == *"stack membership is unknown"* ]]
	! grep -q 'command \[pr\] \[list\]' "$GH_LOG"
}

@test "fails closed when the GraphQL stack query fails" {
	export MOCK_PR_NUMBER=17
	export MOCK_STACK_API_STATUS=1

	run "$SCRIPT"

	[ "$status" -eq 1 ]
	[[ "$output" == *"Could not query GitHub stack metadata for PR #17"* ]]
}

@test "fails closed when GitHub returns an invalid stack number" {
	export MOCK_PR_NUMBER=17
	local number
	for number in 0 -1 invalid '17 41'; do
		export MOCK_STACK_NUMBER="$number"
		run "$SCRIPT"
		[ "$status" -eq 1 ]
		[[ "$output" == *"invalid stack number for PR #17"* ]]
		[[ "$output" != *"STACK_MEMBERSHIP="* ]]
	done
}

run_documented_stack_merge() {
	local resolution
	local merge
	resolution=$(awk '/^```bash$/ { block = 1; next } block && /^```$/ { exit } block { print }' \
		"$REPO_ROOT/skills/pr:stack/references/merge-target.md")
	merge=$(awk '/^## Merging$/ { section = 1 } section && /^```bash$/ { block = 1; next } block && /^```$/ { exit } block { print }' \
		"$REPO_ROOT/skills/pr:stack/SKILL.md")
	[ -n "$resolution" ]
	[ -n "$merge" ]
	MERGE_METHOD=squash TARGET_PR_NUMBER="$1" run bash -c "$resolution"$'\n'"$merge"
}

@test "whole-stack merge passes the stack number when the top PR number collides" {
	export MOCK_ALL_STACKS_JSON='[[{"number":18},{"number":41}]]'

	run_documented_stack_merge 18

	[ "$status" -eq 0 ]
	grep -F 'command [stack] [merge] [41] [--yes] [--squash]' "$GH_LOG"
	! grep -q 'command \[stack\] \[merge\] \[18\]' "$GH_LOG"
}

@test "partial merge checks every page for a colliding stack before merging" {
	export MOCK_ALL_STACKS_JSON='[[{"number":41}],[{"number":17}]]'

	run_documented_stack_merge 17

	[ "$status" -eq 1 ]
	[[ "$output" == *"stop and ask the user"* ]]
	grep -F 'command [api] [--paginate] [--slurp] [repos/{owner}/{repo}/stacks?per_page=100]' "$GH_LOG"
	! grep -q 'command \[stack\] \[merge\]' "$GH_LOG"
}

@test "partial merge uses the PR boundary only after proving no stack collision" {
	run_documented_stack_merge 17

	[ "$status" -eq 0 ]
	grep -F 'command [api] [--paginate] [--slurp]' "$GH_LOG"
	grep -F 'command [stack] [merge] [17] [--yes] [--squash]' "$GH_LOG"
}

@test "merge stops when the selected PR has no identifiable stack" {
	local response
	for response in '[]' '[{"number":41,"pull_requests":[{"number":19}]}]' '[{"pull_requests":[{"number":17}]}]'; do
		export MOCK_TARGET_STACK_JSON="$response"
		run_documented_stack_merge 17
		[ "$status" -eq 1 ]
		[[ "$output" == *"no identifiable stack"* ]]
		! grep -q 'command \[stack\] \[merge\]' "$GH_LOG"
	done
}

@test "merge stops on a failed target stack lookup" {
	export MOCK_STACK_API_STATUS=4

	run_documented_stack_merge 18

	[ "$status" -eq 1 ]
	[[ "$output" == *"Could not determine the selected PR's stack"* ]]
	! grep -q 'command \[stack\] \[merge\]' "$GH_LOG"
}

@test "partial merge stops on a failed collision lookup" {
	export MOCK_STACK_LIST_STATUS=4

	run_documented_stack_merge 17

	[ "$status" -eq 1 ]
	[[ "$output" == *"Could not check stack-number collisions"* ]]
	! grep -q 'command \[stack\] \[merge\]' "$GH_LOG"
}

@test "partial merge stops on a malformed or incomplete stack list" {
	local response
	for response in 'not-json' '[]' '[{}]' '[[{"number":"17"}]]' '[[{}]]'; do
		export MOCK_ALL_STACKS_JSON="$response"
		run_documented_stack_merge 17
		[ "$status" -eq 1 ]
		[[ "$output" == *"Invalid repository stack list"* ]]
		! grep -q 'command \[stack\] \[merge\]' "$GH_LOG"
	done
}

run_documented_stack_link() {
	local link
	link=$(awk '/^```bash$/ { block = 1; next } block && /^```$/ { exit } block { print }' \
		"$REPO_ROOT/skills/pr:stack/references/link-target.md")
	[ -n "$link" ]
	run bash -c 'STACK_ITEMS=("$@")'$'\n'"$link" -- "$@"
}

@test "link rejects colliding PR leaders and ambiguous numeric branch names" {
	export MOCK_ALL_STACKS_JSON='[[{"number":17}]]'
	local item
	for item in 17 +17 00017; do
		run_documented_stack_link "$item" 18
		[ "$status" -eq 1 ]
		[[ "$output" == *"stop and ask the user"* || "$output" == *"Link requires a valid branch or PR identifier"* ]]
		! grep -q 'command \[stack\] \[link\]' "$GH_LOG"
	done
}

@test "PR-led link preserves the selected PR when its local head has unpublished commits" {
	git update-ref refs/remotes/origin/feature HEAD
	local remote_head
	remote_head=$(git rev-parse refs/remotes/origin/feature)
	printf 'unpublished work\n' >>tracked.txt
	git commit -am "unpublished local commit" >/dev/null
	[ "$(git rev-parse HEAD)" != "$remote_head" ]

	run_documented_stack_link 17 18

	[ "$status" -eq 0 ]
	grep -F 'command [stack] [link] [17] [18]' "$GH_LOG"
	! grep -q 'command \[pr\] \[view\]' "$GH_LOG"
	! grep -q 'command \[stack\] \[link\] \[feature\]' "$GH_LOG"
	[ "$(git rev-parse refs/remotes/origin/feature)" = "$remote_head" ]
}

@test "PR-led link keeps an exact identifier instead of resolving a shared head branch" {
	run_documented_stack_link 18 19

	[ "$status" -eq 0 ]
	grep -F 'command [stack] [link] [18] [19]' "$GH_LOG"
	! grep -q 'command \[pr\] \[view\]' "$GH_LOG"
}

@test "PR-led link rejects a same-number local branch with unpublished commits" {
	git branch 17
	git update-ref refs/remotes/origin/17 HEAD
	git switch 17 >/dev/null 2>&1
	printf 'unpublished work\n' >>tracked.txt
	git commit -am "unpublished numeric branch" >/dev/null
	[ "$(git rev-parse HEAD)" != "$(git rev-parse refs/remotes/origin/17)" ]

	run_documented_stack_link 17 18

	[ "$status" -eq 1 ]
	[[ "$output" == *"stop and ask for its explicit PR URL"* ]]
	[ ! -e "$GH_LOG" ]
}

@test "PR-led link stops when local branch inspection fails" {
	local real_git
	real_git=$(command -v git)
	cat >"$BIN_DIR/git" <<GIT
#!/bin/sh
if [ "\$1" = "show-ref" ]; then exit 128; fi
exec "$real_git" "\$@"
GIT
	chmod +x "$BIN_DIR/git"

	run_documented_stack_link 17 18

	[ "$status" -eq 1 ]
	[[ "$output" == *"Could not inspect local branch names"* ]]
	[ ! -e "$GH_LOG" ]
}

@test "URL-led link preserves the explicit URL despite same-number branches and stacks" {
	git branch 17
	export MOCK_ALL_STACKS_JSON='[[{"number":17}]]'
	run_documented_stack_link https://github.com/acme/demo/pull/17 18

	[ "$status" -eq 0 ]
	! grep -q 'command \[api\]' "$GH_LOG"
	grep -F 'command [stack] [link] [https://github.com/acme/demo/pull/17] [18]' "$GH_LOG"
}

@test "PR-led link checks later pages and stops on API or parsing failure" {
	export MOCK_ALL_STACKS_JSON='[[{"number":41}],[{"number":17}]]'
	run_documented_stack_link 17 18
	[ "$status" -eq 1 ]
	[[ "$output" == *"stop and ask the user"* ]]
	! grep -q 'command \[stack\] \[link\]' "$GH_LOG"
	export MOCK_ALL_STACKS_JSON='[[{"number":41}]]'
	export MOCK_STACK_LIST_STATUS=4
	run_documented_stack_link 17 18
	[ "$status" -eq 1 ]
	[[ "$output" == *"Could not check stack-number collisions"* ]]
	! grep -q 'command \[stack\] \[link\]' "$GH_LOG"
	export MOCK_STACK_LIST_STATUS=0
	export MOCK_ALL_STACKS_JSON='[{}]'
	run_documented_stack_link 17 18
	[ "$status" -eq 1 ]
	[[ "$output" == *"Invalid repository stack list"* ]]
	! grep -q 'command \[stack\] \[link\]' "$GH_LOG"
}

@test "link preserves a leading branch and remaining PR operands as inert arguments" {
	local branch='topic-$(touch${IFS}$PWNED_FILE)'
	export PWNED_FILE="$TMP_DIR/pwned"

	run_documented_stack_link "$branch" 18

	[ "$status" -eq 0 ]
	grep -F "command [stack] [link] [$branch] [18]" "$GH_LOG"
	[ ! -e "$PWNED_FILE" ]
}

run_documented_stack_checkout() {
	local checkout
	checkout=$(awk '/^```bash$/ { block = 1; next } block && /^```$/ { exit } block { print }' \
		"$REPO_ROOT/shared/git/references/stack-checkout.md")
	[ -n "$checkout" ]
	run bash -c 'STACK_NUMBER=$1'$'\n'"$checkout" -- "$1"
}

@test "stack-number checkout restores the original lower-layer branch" {
	git branch top

	run_documented_stack_checkout 41

	[ "$status" -eq 0 ]
	grep -F 'command [stack] [checkout] [41]' "$GH_LOG"
	[ "$(git branch --show-current)" = feature ]
}

@test "stack-number checkout restores a numeric entry branch with plain Git" {
	git branch top
	git switch -c 17 >/dev/null 2>&1

	run_documented_stack_checkout 41

	[ "$status" -eq 0 ]
	[ "$(git branch --show-current)" = 17 ]
	! grep -q 'command \[stack\] \[checkout\] \[17\]' "$GH_LOG"
}

@test "stack checkout refuses an undetermined stack number or a dirty tree" {
	run_documented_stack_checkout ''
	[ "$status" -eq 1 ]
	[[ "$output" == *"stack number could not be determined"* ]]
	! grep -q 'command \[stack\] \[checkout\]' "$GH_LOG"
	printf 'uncommitted work\n' >>tracked.txt
	run_documented_stack_checkout 41
	[ "$status" -eq 1 ]
	[[ "$output" == *"clean working tree is required"* ]]
	! grep -q 'command \[stack\] \[checkout\]' "$GH_LOG"
}

@test "stack checkout stops when importing fails" {
	export MOCK_STACK_CHECKOUT_STATUS=4

	run_documented_stack_checkout 41

	[ "$status" -eq 1 ]
	[ "$(git branch --show-current)" = feature ]
}

@test "passes a metacharacter branch to gh as one inert argument" {
	local branch='topic-$(touch${IFS}$PWNED_FILE)'
	export PWNED_FILE="$TMP_DIR/pwned"
	git switch -c "$branch" >/dev/null 2>&1

	run "$SCRIPT"

	[ "$status" -eq 0 ]
	load_assignments
	[ "$STACK_MEMBERSHIP" = "none" ]
	grep -F "[$branch]" "$GH_LOG"
	[ ! -e "$PWNED_FILE" ]
}

@test "returns none without consulting gh for a non-GitHub remote" {
	git remote set-url origin https://example.com/acme/demo.git
	export MOCK_EXTENSION_STATUS=97

	run "$SCRIPT"

	[ "$status" -eq 0 ]
	load_assignments
	[ "$STACK_MEMBERSHIP" = "none" ]
	[ ! -s "$GH_LOG" ]
}

@test "checks local stack membership when a non-origin remote points to GitHub" {
	git remote set-url origin https://example.com/acme/demo.git
	git remote add upstream git@github.com:acme/demo.git
	export MOCK_STACK_VIEW_STATUS=0

	run "$SCRIPT"

	[ "$status" -eq 0 ]
	load_assignments
	[ "$STACK_MEMBERSHIP" = "local" ]
	grep -q 'command \[stack\] \[view\]' "$GH_LOG"
}

@test "stack skills use the shared fail-closed membership resolver" {
	local consumer
	for consumer in \
		"$REPO_ROOT/skills/git:fixup/SKILL.md" \
		"$REPO_ROOT/skills/git:recreate-commits/SKILL.md" \
		"$REPO_ROOT/skills/pr:fix-ci/SKILL.md" \
		"$REPO_ROOT/skills/pr:rebase/SKILL.md" \
		"$REPO_ROOT/skills/pr:stack/SKILL.md"; do
		grep -F 'resolve-stack-membership.sh' "$consumer"
		grep -F '${CLAUDE_PLUGIN_ROOT}/shared/git/references/stack-checkout.md' "$consumer"
		! grep -F 'gh stack checkout "$STACK_PR_NUMBER"' "$consumer"
	done
	grep -F 'gh stack checkout "$STACK_NUMBER"' "$REPO_ROOT/shared/git/references/stack-checkout.md"
	grep -F 'git switch -- "$STACK_RESTORE_BRANCH"' "$REPO_ROOT/shared/git/references/stack-checkout.md"
	grep -F 'Retry only when the branch still equals `STACK_RESTORE_BRANCH` and membership is `local`' "$REPO_ROOT/shared/git/references/stack-checkout.md"

	! grep -R -E 'gh stack view --json.*&& IN_STACK=true' \
		"$REPO_ROOT/skills/git:fixup" \
		"$REPO_ROOT/skills/git:recreate-commits" \
		"$REPO_ROOT/skills/pr:fix-ci" \
		"$REPO_ROOT/skills/pr:rebase"
}

@test "stack command examples preserve operand and placeholder boundaries" {
	local stack_skill="$REPO_ROOT/skills/pr:stack/SKILL.md"
	local strategies="$REPO_ROOT/skills/code:breakdown-findings/references/split-strategies.md"

	grep -F 'git check-ref-format --branch "$branch"' "$stack_skill"
	grep -F 'gh stack init --base "$BASE_BRANCH" "${STACK_BRANCHES[@]}"' "$stack_skill"
	grep -F 'gh stack link "${STACK_ITEMS[@]}"' "$stack_skill"
	grep -F 'gh stack init --base "$BASE_BRANCH" stack-1-schema' "$strategies"
	grep -F 'git checkout "$REFERENCE_BRANCH" -- db/migrations/' "$strategies"
	! grep -E '< (base|reference)-branch >' "$strategies"
}

@test "breakdown stack recipe matches current gh-stack behavior" {
	local strategies="$REPO_ROOT/skills/code:breakdown-findings/references/split-strategies.md"

	! grep -iF 'private preview' "$strategies" || false
	grep -F 'requires the repository to have stacked PRs enabled' "$strategies"
	grep -F 'gh stack link --base "$BASE_BRANCH" stack-1-schema stack-2-service stack-3-ui' "$strategies"
	grep -F 'becomes the whole description of every PR that `submit --auto` creates' "$strategies"
	grep -F 'followed by a gh-stack attribution footer' "$strategies"
	grep -F 'keeps or removes that footer' "$strategies"
}

@test "pr:stack guidance matches gh-stack v0.3 behavior" {
	local stack_skill="$REPO_ROOT/skills/pr:stack/SKILL.md"
	local rules="$REPO_ROOT/skills/pr:stack/references/cli-agent-rules.md"

	! grep -R -i -E 'private preview|waitlist|stacksbeta' "$REPO_ROOT/skills" || false
	grep -F 'stacked PRs must be enabled for the repository' "$stack_skill"
	grep -F 'The minimum supported extension version is v0.3.0' "$stack_skill"
	! grep -iF 'linear history' "$rules" || false
	grep -F 'Stacks accept merge-commit, squash, and rebase merges.' "$rules"
	grep -F '`view --short` never does' "$rules"
	grep -F 'Only JSON output is machine-readable.' "$rules"
	grep -F 'a worktree chain needs `init`, not `link`' "$stack_skill"
	! grep -F 'worktree chains)' "$stack_skill" "$rules" || false

	local rebase_line init_line
	rebase_line=$(grep -n -F 'git rebase --onto <new-parent> <recorded-old-parent-tip> <branch>' "$stack_skill" | cut -d: -f1)
	init_line=$(grep -n -F 'gh stack init --base <recorded-trunk> <branches bottom-to-top>' "$stack_skill" | cut -d: -f1)
	[ -n "$rebase_line" ]
	[ -n "$init_line" ]
	[ "$rebase_line" -lt "$init_line" ]
	grep -F 'Confirm each layer holds only its own commits' "$stack_skill"
	grep -F 'Stop on any unpaired commit' "$stack_skill"
	grep -F 'which rebase and check every moved layer before `gh stack unstack` and `init`' "$rules"
}

@test "stack workflow does not delegate mutating description generation" {
	local stack_skill="$REPO_ROOT/skills/pr:stack/SKILL.md"

	grep -F 'Do not invoke `trackbed:pr:generate-description` from inside this skill' "$stack_skill"
	grep -F 'every model-initiated call to that child must use output-only `--no-update`' "$stack_skill"
	grep -F 'ask the user to invoke `/trackbed:pr:generate-description` directly' "$stack_skill"
	! grep -F 'run `trackbed:pr:generate-description` per PR' "$stack_skill"
}

@test "history rewrite flows restack before their stack-wide push" {
	local flow
	for flow in \
		"$REPO_ROOT/skills/pr:fix-ci/SKILL.md" \
		"$REPO_ROOT/skills/pr:fix-ci/references/fixup-flow.md" \
		"$REPO_ROOT/skills/pr:fix-ci/references/consolidation-flow.md"; do
		local rebase_line
		local push_line
		rebase_line=$(grep -n 'gh stack rebase --upstack --no-trunk' "$flow" | tail -1 | cut -d: -f1)
		push_line=$(grep -n '^[[:space:]]*env -u GH_STACK_NO_ATOMIC gh stack push' "$flow" | tail -1 | cut -d: -f1)
		[ -n "$rebase_line" ]
		[ -n "$push_line" ]
		[ "$rebase_line" -lt "$push_line" ]
	done
}

@test "fixup restacks locally without publishing the stack" {
	local fixup="$REPO_ROOT/skills/git:fixup/SKILL.md"
	local report_step
	report_step=$(sed -n '/### Step 7: Report Results/,/## Error Handling/p' "$fixup")

	grep -F 'gh stack rebase --upstack --no-trunk' <<<"$report_step"
	! grep -E '^[[:space:]]*env -u GH_STACK_NO_ATOMIC gh stack push' <<<"$report_step"
	grep -F 'Do not run `env -u GH_STACK_NO_ATOMIC gh stack push` automatically' <<<"$report_step"
}

@test "recreate-commits restacks before no-push and local-only exits" {
	local recreate="$REPO_ROOT/skills/git:recreate-commits/SKILL.md"
	local restack_line
	local no_push_line
	local local_only_line
	restack_line=$(grep -n 'the rewrite has orphaned every branch' "$recreate" | tail -1 | cut -d: -f1)
	no_push_line=$(grep -n 'If `--no-push` was passed' "$recreate" | tail -1 | cut -d: -f1)
	local_only_line=$(grep -n 'the recreation is local-only' "$recreate" | tail -1 | cut -d: -f1)

	[ "$restack_line" -lt "$no_push_line" ]
	[ "$restack_line" -lt "$local_only_line" ]
}

@test "merge and conflict guidance match gh-stack semantics" {
	local stack_skill="$REPO_ROOT/skills/pr:stack/SKILL.md"
	local rules="$REPO_ROOT/skills/pr:stack/references/cli-agent-rules.md"

	grep -F 'highest PR the user intends to land' "$stack_skill"
	grep -F 'use the top PR to land the entire stack' "$stack_skill"
	grep -F 'gh stack merge "$MERGE_TARGET" "${MERGE_ARGS[@]}"' "$stack_skill"
	grep -F 'Read `references/merge-target.md`' "$stack_skill"
	grep -F 'On a partial-target collision, stop and ask the user how to proceed' "$stack_skill"
	! grep -E 'gh stack (checkout|merge) <(branch-or-pr-number|pr-number|stack-number \\)' "$stack_skill" "$rules"
	! grep -F 'Merging from the CLI is not supported' "$stack_skill" "$rules"
	grep -F 'After `env -u GH_STACK_NO_ATOMIC gh stack sync`, all branches were restored' "$stack_skill"
	grep -F 'After `gh stack rebase`, a rebase session remains active' "$stack_skill"
	grep -F '`gh stack sync` restores every branch before it returns exit 3' "$REPO_ROOT/shared/git/references/stack-operations.md"
}

@test "rebase verification keeps the revision range in one shell argument" {
	local rebase_skill="$REPO_ROOT/skills/pr:rebase/SKILL.md"

	grep -F 'git log --oneline "origin/$BASE_BRANCH..HEAD"' "$rebase_skill"
	! grep -F 'git log --oneline origin/ < base-branch > ..HEAD' "$rebase_skill"
}

@test "rebase fix-ci mode is opt-in and delegates only after a successful push" {
	local rebase_skill="$REPO_ROOT/skills/pr:rebase/SKILL.md"
	local opt_in_guard_line
	local push_guard_line
	local manual_delegate_line
	local auto_delegate_line

	grep -F 'argument-hint: "[--manual] [--force-push] [--fix-ci] [--base <branch>] [--all-open]"' "$rebase_skill"
	grep -F 'set `FIX_CI_MODE=true`' "$rebase_skill"
	grep -F 'Set it to true only after the applicable validated push command returns success.' "$rebase_skill"

	opt_in_guard_line=$(grep -nF 'If `FIX_CI_MODE` is not true, skip to Step 7.' "$rebase_skill" | cut -d: -f1)
	push_guard_line=$(grep -nF 'Require `PUSH_COMPLETED=true` before delegating.' "$rebase_skill" | cut -d: -f1)
	manual_delegate_line=$(grep -nF 'invoke `$trackbed:pr:fix-ci --manual`' "$rebase_skill" | cut -d: -f1)
	auto_delegate_line=$(grep -nF 'invoke `$trackbed:pr:fix-ci` with no additional flags' "$rebase_skill" | cut -d: -f1)
	[ -n "$opt_in_guard_line" ]
	[ -n "$push_guard_line" ]
	[ -n "$manual_delegate_line" ]
	[ -n "$auto_delegate_line" ]
	[ "$opt_in_guard_line" -lt "$manual_delegate_line" ]
	[ "$opt_in_guard_line" -lt "$auto_delegate_line" ]
	[ "$push_guard_line" -lt "$manual_delegate_line" ]
	[ "$push_guard_line" -lt "$auto_delegate_line" ]

	grep -F 'Do not poll CI separately before invoking it.' "$rebase_skill"
	grep -F 'do not claim that sibling Pull Requests were watched.' "$rebase_skill"
	grep -F 'if CI reached green before a later consolidation or coordination blocker, report both facts' "$rebase_skill"
	grep -F 'When `FIX_CI_MODE=true` and `PUSH_COMPLETED=true`' "$rebase_skill"
	grep -F 'When `FIX_CI_MODE=true` and `PUSH_COMPLETED=false`' "$rebase_skill"
	grep -F 'do not require or fabricate a remediation handoff.' "$rebase_skill"
}

@test "rebase model invocation is limited to the guarded fix-ci child call" {
	local rebase_skill="$REPO_ROOT/skills/pr:rebase/SKILL.md"

	grep -qF 'disable-model-invocation: false' "$rebase_skill"
	grep -F 'Invoke automatically only as a delegated child of `trackbed:pr:fix-ci`, with the exact `--force-push` argument selected by that parent.' "$rebase_skill"
	grep -F 'Never omit `--force-push`, and do not add `--fix-ci` or an invented `--base` override.' "$rebase_skill"
	grep -F 'No other parent workflow is authorized by this model-invocation exception.' "$rebase_skill"
}

@test "rebase pins its force-with-lease to the remote OID captured before rebasing" {
	local rebase_skill="$REPO_ROOT/skills/pr:rebase/SKILL.md"
	local capture_line
	local ancestry_stop_line
	local rebase_line

	grep -F 'REMOTE_REFS=$(git ls-remote --heads origin "refs/heads/$LEASE_BRANCH") || {' "$rebase_skill"
	grep -F 'PRE_REBASE_REMOTE_OID=$(printf' "$rebase_skill"
	grep -F 'if [ -n "$PRE_REBASE_REMOTE_OID" ] && ! git merge-base --is-ancestor "$PRE_REBASE_REMOTE_OID" HEAD 2> /dev/null; then' "$rebase_skill"
	grep -F 'origin/$LEASE_BRANCH has commits the local branch lacks; integrate them before rebasing.' "$rebase_skill"
	grep -F '[ "$CURRENT_BRANCH" = "$LEASE_BRANCH" ] ||' "$rebase_skill"
	grep -F '[[ "$PRE_REBASE_REMOTE_OID" =~ ^([0-9a-f]{40}|[0-9a-f]{64})?$ ]] ||' "$rebase_skill"
	grep -F 'git push --no-follow-tags --force-with-lease="refs/heads/$CURRENT_BRANCH:$PRE_REBASE_REMOTE_OID" origin "refs/heads/$CURRENT_BRANCH:refs/heads/$CURRENT_BRANCH"' "$rebase_skill"
	! grep -F 'git push --force-with-lease origin "$CURRENT_BRANCH"' "$rebase_skill"

	capture_line=$(grep -nF 'PRE_REBASE_REMOTE_OID=$(printf' "$rebase_skill" | cut -d: -f1)
	ancestry_stop_line=$(grep -nF 'origin/$LEASE_BRANCH has commits the local branch lacks; integrate them before rebasing.' "$rebase_skill" | cut -d: -f1)
	rebase_line=$(grep -nFx 'git rebase --autostash origin/<base-branch>' "$rebase_skill" | cut -d: -f1)
	[ -n "$capture_line" ]
	[ -n "$ancestry_stop_line" ]
	[ -n "$rebase_line" ]
	[ "$capture_line" -lt "$ancestry_stop_line" ]
	[ "$ancestry_stop_line" -lt "$rebase_line" ]
}

@test "rebase exits early when the branch already contains the base tip" {
	local rebase_skill="$REPO_ROOT/skills/pr:rebase/SKILL.md"
	local early_exit_line
	local rebase_line

	grep -F 'When `IN_STACK=false`, run this read-only preflight before rebasing' "$rebase_skill"
	grep -F 'ALREADY_CONTAINS_BASE=true' "$rebase_skill"
	grep -F 'git rev-list --count --merges "$BASE_TIP..HEAD"' "$rebase_skill"
	grep -F 'nothing to rebase or push' "$rebase_skill"
	grep -F 'keep `PUSH_COMPLETED=false`, and skip to Step 7.' "$rebase_skill"
	grep -F 'nothing was rebased or pushed, so CI stabilization was not started' "$rebase_skill"
	grep -F 'Branch already contains `origin/<base-branch>`; nothing was rebased or pushed.' "$rebase_skill"
	grep -F 'A stack (`IN_STACK=true`) uses the shared stack preflight above instead of this single-branch block, then keeps `env -u GH_STACK_NO_ATOMIC gh stack push`.' "$rebase_skill"

	early_exit_line=$(grep -nF '  echo "ALREADY_CONTAINS_BASE=true"' "$rebase_skill" | cut -d: -f1)
	rebase_line=$(grep -nFx 'git rebase --autostash origin/<base-branch>' "$rebase_skill" | cut -d: -f1)
	[ -n "$early_exit_line" ]
	[ -n "$rebase_line" ]
	[ "$early_exit_line" -lt "$rebase_line" ]
}

@test "a pinned lease rejects a remote update that a later fetch made visible" {
	local remote="$BATS_TEST_TMPDIR/remote.git"
	local publisher="$BATS_TEST_TMPDIR/publisher"
	local contender="$BATS_TEST_TMPDIR/contender"
	local observed
	local contender_head
	local rewritten_head
	local remote_head

	init_test_git_repo "$publisher" --origin "$remote"
	git --git-dir="$remote" symbolic-ref HEAD refs/heads/main
	git -C "$publisher" checkout -b feature >/dev/null
	printf 'published\n' >>"$publisher/tracked.txt"
	git -C "$publisher" commit -am "published work" >/dev/null
	git -C "$publisher" push -u origin feature >/dev/null
	observed=$(git -C "$publisher" ls-remote --heads origin refs/heads/feature | awk '{print $1}')
	git -C "$publisher" merge-base --is-ancestor "$observed" HEAD

	git clone "$remote" "$contender" >/dev/null
	git -C "$contender" config user.name "Other User"
	git -C "$contender" config user.email "other@example.com"
	git -C "$contender" config commit.gpgsign false
	git -C "$contender" checkout feature >/dev/null
	printf 'remote\n' >>"$contender/tracked.txt"
	git -C "$contender" commit -am "remote work" >/dev/null
	git -C "$contender" push origin HEAD:refs/heads/feature >/dev/null
	contender_head=$(git -C "$contender" rev-parse HEAD)

	git -C "$publisher" fetch origin
	[ "$(git -C "$publisher" rev-parse origin/feature)" = "$contender_head" ]
	git -C "$publisher" commit --amend -m "rebased published work" >/dev/null
	rewritten_head=$(git -C "$publisher" rev-parse HEAD)
	[ "$rewritten_head" != "$observed" ]

	run "${CONDUCTOR_REAL_GIT_PATH:-git}" -C "$publisher" push \
		--no-follow-tags \
		--force-with-lease=refs/heads/feature:"$observed" \
		origin refs/heads/feature:refs/heads/feature
	[ "$status" -ne 0 ]
	[[ "$output" == *"stale info"* ]]

	remote_head=$(git -C "$publisher" ls-remote --heads origin refs/heads/feature | awk '{print $1}')
	[ "$remote_head" = "$contender_head" ]
	[ "$remote_head" != "$rewritten_head" ]
}

@test "rebase lease handoff preserves apostrophes and shell syntax in branch names" {
	local rebase_skill="$REPO_ROOT/skills/pr:rebase/SKILL.md"
	local remote="$BATS_TEST_TMPDIR/remote.git"
	local publisher="$BATS_TEST_TMPDIR/publisher"
	local branch="topic/o'brien-"'$(touch${IFS}branch-name-executed)'
	local preflight
	local push
	local assignments
	local original_head
	local rebased_head

	preflight=$(awk '
		/^### Step 2:/ { section = 1 }
		section && /^```bash$/ { block = 1; next }
		block && /^```$/ { exit }
		block { print }
	' "$rebase_skill" | sed 's/<base-branch>/main/g')
	push=$(awk '
		/^### Step 5:/ { section = 1 }
		section && /^```bash$/ { block = 1; next }
		block && /^```$/ { exit }
		block { print }
	' "$rebase_skill")
	[ -n "$preflight" ]
	[ -n "$push" ]

	init_test_git_repo "$publisher" --origin "$remote"
	cd "$publisher"
	git checkout -b "$branch" >/dev/null
	printf 'feature\n' >>tracked.txt
	git commit -am "feature work" >/dev/null
	git push origin "refs/heads/$branch:refs/heads/$branch" >/dev/null
	original_head=$(git rev-parse HEAD)
	git checkout main >/dev/null
	printf 'base advance\n' >base.txt
	git add base.txt
	git commit -m "advance base" >/dev/null
	git push origin main >/dev/null
	git checkout "$branch" >/dev/null

	assignments=$(bash -c "$preflight")
	git rebase --autostash origin/main
	rebased_head=$(git rev-parse HEAD)
	[ "$rebased_head" != "$original_head" ]

	run bash -c "$assignments"$'\n'"$push"
	[ "$status" -eq 0 ]
	[ "$(git ls-remote --heads origin "refs/heads/$branch" | awk '{print $1}')" = "$rebased_head" ]
	[ ! -e branch-name-executed ]
}

prepare_stack_preflight() {
	git init --bare "$TMP_DIR/remote.git" >/dev/null 2>&1
	git remote set-url origin "$TMP_DIR/remote.git"
	git branch layer
	git push origin feature layer >/dev/null 2>&1
	export MOCK_STACK_VIEW_STATUS=0
	export MOCK_STACK_VIEW_STDOUT='{"branches":[{"name":"feature","pr":{"state":"OPEN"}},{"name":"layer","pr":{"state":"OPEN"}},{"name":"gone","pr":{"state":"MERGED"}}]}'
	export STACK_REMOTE=origin
	PREFLIGHT="$TMP_DIR/preflight.sh"
	python3 - "$REPO_ROOT/shared/git/references/stack-rewrite-safety.md" "$PREFLIGHT" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text()
Path(sys.argv[2]).write_text(text.split('```bash\n', 1)[1].split('```', 1)[0])
PY
}

advance_stack_remote() {
	local branch="$1" tip next
	tip=$(git --git-dir="$TMP_DIR/remote.git" rev-parse "refs/heads/$branch")
	next=$(git --git-dir="$TMP_DIR/remote.git" -c user.name=Test -c user.email=test@example.com \
		commit-tree "$tip^{tree}" -p "$tip" -m "Remote review suggestion")
	git --git-dir="$TMP_DIR/remote.git" update-ref "refs/heads/$branch" "$next"
}

@test "stack preflight stops divergence on a later open branch before rewriting" {
	prepare_stack_preflight
	git switch layer >/dev/null 2>&1
	git commit --allow-empty -m "Local layer work" >/dev/null
	advance_stack_remote layer
	local before
	before=$(git rev-parse HEAD)

	run bash "$PREFLIGHT"

	[ "$status" -ne 0 ]
	[[ "$output" == *"origin/layer has commits the local branch lacks; integrate them before rebasing."* ]]
	[ "$(git rev-parse HEAD)" = "$before" ]
	[ -z "$(git status --porcelain)" ]
}

@test "stack preflight allows behind-only ahead-only and equal histories" {
	prepare_stack_preflight
	advance_stack_remote layer
	git commit --allow-empty -m "Local feature work" >/dev/null

	run bash "$PREFLIGHT"

	[ "$status" -eq 0 ]
	[[ "$output" != *"integrate them"* ]]
	# A behind-only layer is not fast-forwarded by the read-only guard.
	[ "$(git rev-list --count layer..FETCH_HEAD)" -eq 1 ]
}

@test "restructure preflight also stops a behind-only branch" {
	prepare_stack_preflight
	advance_stack_remote layer
	local before
	before=$(git rev-parse layer)

	STACK_STOP_ON_BEHIND=1 run bash "$PREFLIGHT"

	[ "$status" -ne 0 ]
	[[ "$output" == *"origin/layer has commits the local branch lacks; sync them before restructuring."* ]]
	[ "$(git rev-parse layer)" = "$before" ]

	local stack_skill="$REPO_ROOT/skills/pr:stack/SKILL.md"
	local preflight_line rebase_line
	preflight_line=$(grep -n -F 'run its complete preflight with `STACK_STOP_ON_BEHIND=1` before every Restructure' "$stack_skill" | cut -d: -f1)
	rebase_line=$(grep -n -F 'git rebase --onto <new-parent> <recorded-old-parent-tip> <branch>' "$stack_skill" | cut -d: -f1)
	[ -n "$preflight_line" ]
	[ "$preflight_line" -lt "$rebase_line" ]
}

@test "stack preflight fails closed on inventory fetch or missing local branch" {
	prepare_stack_preflight
	git --git-dir="$TMP_DIR/remote.git" update-ref -d refs/heads/layer
	run bash "$PREFLIGHT"
	[ "$status" -ne 0 ]

	export MOCK_STACK_VIEW_STDOUT='{}'
	run bash "$PREFLIGHT"
	[ "$status" -ne 0 ]

	export MOCK_STACK_VIEW_STDOUT='{"branches":[{"name":"missing","pr":{"state":"OPEN"}}]}'
	run bash "$PREFLIGHT"
	[ "$status" -ne 0 ]
}

@test "both rewrite entry points require the shared preflight and matching remote" {
	local consumer
	for consumer in "$REPO_ROOT/skills/pr:rebase/SKILL.md" "$REPO_ROOT/skills/pr:stack/SKILL.md"; do
		grep -qF '${CLAUDE_PLUGIN_ROOT}/shared/git/references/stack-rewrite-safety.md' "$consumer"
		grep -qF 'run its complete preflight' "$consumer"
		grep -qF 'STACK_REMOTE' "$consumer"
	done
	grep -qF 'in every mode including auto mode' "$REPO_ROOT/skills/pr:rebase/SKILL.md"
}

@test "all atomic stack push instructions clear the environment opt-out" {
	local consumer line
	for consumer in \
		"$REPO_ROOT/skills/pr:stack/SKILL.md" \
		"$REPO_ROOT/skills/pr:stack/references/cli-agent-rules.md" \
		"$REPO_ROOT/skills/pr:rebase/SKILL.md" \
		"$REPO_ROOT/skills/pr:fix-ci/SKILL.md" \
		"$REPO_ROOT/skills/pr:fix-ci/references/fixup-flow.md" \
		"$REPO_ROOT/skills/pr:fix-ci/references/consolidation-flow.md" \
		"$REPO_ROOT/skills/git:fixup/SKILL.md" \
		"$REPO_ROOT/skills/git:recreate-commits/SKILL.md"; do
		while IFS= read -r line; do
			[[ "$line" == *'env -u GH_STACK_NO_ATOMIC gh stack push'* ]]
		done < <(grep -F 'gh stack push' "$consumer")
	done
	! grep -E '^[[:space:]]*gh stack sync' "$REPO_ROOT/skills/pr:stack/SKILL.md"
}

@test "atomic push command clears even a false-looking nonempty opt-out" {
	cat >"$BIN_DIR/gh" <<'GH'
#!/bin/sh
[ "${GH_STACK_NO_ATOMIC+x}" != x ] || exit 98
[ "$1 $2" = 'stack push' ]
GH
	export GH_STACK_NO_ATOMIC=0
	run env -u GH_STACK_NO_ATOMIC gh stack push
	[ "$status" -eq 0 ]
}
