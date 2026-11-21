#!/usr/bin/env bats
#
# scripts/review-artifact-patterns.sh is how skills read the commit hook's
# protected report list without depending on hooks/ or keeping a copy.

setup() {
	PLUGIN_ROOT="$BATS_TEST_DIRNAME/.."
	FAKE_ROOT="$BATS_TEST_TMPDIR/plugin"
	mkdir -p "$FAKE_ROOT/scripts/lib" "$FAKE_ROOT/hooks"
	cp "$PLUGIN_ROOT/scripts/review-artifact-patterns.sh" "$FAKE_ROOT/scripts/"
	cp "$PLUGIN_ROOT/scripts/lib/review-artifacts.sh" "$FAKE_ROOT/scripts/lib/"
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

@test "visual query drops root and direct siw pages and preserves other paths" {
	printf '  REVIEW_*.html # generated page\nREVIEW_OVERVIEW.md' >"$FAKE_ROOT/hooks/confirm-review-artifacts.txt"
	printf '%s\0' REVIEW_OVERVIEW.html siw/REVIEW_OVERVIEW.html siw/REVIEW_OVERVIEW.md src/REVIEW_OVERVIEW.html siw/nested/REVIEW_OVERVIEW.html >"$BATS_TEST_TMPDIR/paths"
	"$FAKE_ROOT/scripts/review-artifact-patterns.sh" --without-visual-pages <"$BATS_TEST_TMPDIR/paths" >"$BATS_TEST_TMPDIR/actual"
	printf '%s\0' siw/REVIEW_OVERVIEW.md src/REVIEW_OVERVIEW.html siw/nested/REVIEW_OVERVIEW.html >"$BATS_TEST_TMPDIR/expected"
	cmp "$BATS_TEST_TMPDIR/expected" "$BATS_TEST_TMPDIR/actual"
}

@test "shared reader supports ignoring or using a fallback for absent patterns" {
	source "$FAKE_ROOT/scripts/lib/review-artifacts.sh"
	for list in "$BATS_TEST_TMPDIR/missing" "$BATS_TEST_TMPDIR/empty"; do
		touch "$BATS_TEST_TMPDIR/empty"
		load_review_artifact_patterns "$list" ignore html
		[ "${#REVIEW_ARTIFACT_PATTERNS[@]}" -eq 0 ]
		load_review_artifact_patterns "$list" fallback all CUSTOM.md
		[ "${REVIEW_ARTIFACT_PATTERNS[*]}" = CUSTOM.md ]
	done
}
