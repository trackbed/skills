#!/usr/bin/env bats
#
# scripts/review-artifact-patterns.sh is how skills read the commit hook's
# protected report list without depending on hooks/ or keeping a copy.

setup() {
	PLUGIN_ROOT="$BATS_TEST_DIRNAME/.."
	FAKE_ROOT="$BATS_TEST_TMPDIR/plugin"
	mkdir -p "$FAKE_ROOT/scripts" "$FAKE_ROOT/hooks"
	cp "$PLUGIN_ROOT/scripts/review-artifact-patterns.sh" "$FAKE_ROOT/scripts/"
}

@test "prints the list's patterns without comments or blank lines" {
	printf '# header\n\nREVIEW_OVERVIEW.md  # trailing note\n  PR_PLAN_*.md\n' >"$FAKE_ROOT/hooks/confirm-review-artifacts.txt"
	run "$FAKE_ROOT/scripts/review-artifact-patterns.sh"
	[ "$status" -eq 0 ]
	[ "$output" = $'REVIEW_OVERVIEW.md\nPR_PLAN_*.md' ]
}

@test "fails when the list is missing" {
	run "$FAKE_ROOT/scripts/review-artifact-patterns.sh"
	[ "$status" -eq 1 ]
	[[ "$output" == *"Review artifact list not found"* ]] || false
}

@test "fails when the list has no patterns" {
	printf '# only a comment\n\n' >"$FAKE_ROOT/hooks/confirm-review-artifacts.txt"
	run "$FAKE_ROOT/scripts/review-artifact-patterns.sh"
	[ "$status" -eq 1 ]
	[[ "$output" == *"has no patterns"* ]] || false
}

@test "rejects arguments" {
	run "$PLUGIN_ROOT/scripts/review-artifact-patterns.sh" extra
	[ "$status" -eq 2 ]
}
