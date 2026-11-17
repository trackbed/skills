#!/usr/bin/env bats
# Tests for the shared assert_required_contracts_registered helper

load 'test_helper/common'

setup() {
	REGISTERED_CONTRACT="workflow-artifact-cleanup-names"
}

@test "accepts a contract that the registry declares" {
	assert_required_contracts_registered "$REGISTERED_CONTRACT"
}

@test "reports every unregistered contract in one sorted diagnostic" {
	run assert_required_contracts_registered \
		zz-second-absent-contract \
		"$REGISTERED_CONTRACT" \
		zz-first-absent-contract

	[ "$status" -ne 0 ]
	[[ "$output" == *"missing required_file_contracts: zz-first-absent-contract, zz-second-absent-contract"* ]] || false
	[[ "$output" != *"$REGISTERED_CONTRACT"* ]] || false
}

# Guidance suites call the helper between a `run` and its `[ "$status" -eq 0 ]` assertion,
# so it must not run through `run` itself or change the directory the suite works from.
@test "leaves the caller's status and working directory untouched" {
	local before_pwd="$PWD"

	run false
	assert_required_contracts_registered "$REGISTERED_CONTRACT"

	[ "$status" -eq 1 ]
	[ "$PWD" = "$before_pwd" ]
}

@test "required text reports the inspected path and missing phrase" {
	local fixture="$BATS_TEST_TMPDIR/required.txt"
	printf 'existing phrase\n' >"$fixture"

	run assert_required_text "$fixture" 'missing phrase'

	[ "$status" -ne 0 ]
	[[ "$output" == *"$fixture"* ]] || false
	[[ "$output" == *"missing phrase"* ]] || false
}

@test "absent text reports the inspected path and forbidden phrase" {
	local fixture="$BATS_TEST_TMPDIR/absent.txt"
	printf 'forbidden phrase\n' >"$fixture"

	run assert_absent_text "$fixture" 'forbidden phrase'

	[ "$status" -ne 0 ]
	[[ "$output" == *"$fixture"* ]] || false
	[[ "$output" == *"forbidden phrase"* ]] || false
}

@test "order reports the inspected path and both out-of-order phrases" {
	local fixture="$BATS_TEST_TMPDIR/order.txt"
	printf 'later phrase\nearlier phrase\n' >"$fixture"

	run assert_text_order "$fixture" 'earlier phrase' 'later phrase'

	[ "$status" -ne 0 ]
	[[ "$output" == *"$fixture"* ]] || false
	[[ "$output" == *"earlier phrase"* ]] || false
	[[ "$output" == *"later phrase"* ]] || false
}

@test "guidance assertions preserve literal text, filtered line counts, and occurrence order" {
	local fixture="$BATS_TEST_TMPDIR/literals.txt"
	printf '%s\n' 'guard' 'push' 'boundary' 'guard --flag $value' 'push' 'push' >"$fixture"

	assert_required_text "$fixture" '--flag $value'
	assert_absent_text "$fixture" 'missing [pattern]'
	assert_text_count "$fixture" 'push' 3
	assert_text_count "$fixture" 'guard' 1 '--flag'
	assert_text_order "$fixture" 'guard' 'push' 2 2
	assert_text_order "$fixture" 'guard' 'push' 1 1 'boundary'
}

@test "count and missing order occurrences fail with file and text diagnostics" {
	local fixture="$BATS_TEST_TMPDIR/count.txt"
	printf 'first\nsecond\n' >"$fixture"

	run assert_text_count "$fixture" 'first' 2
	[ "$status" -ne 0 ]
	[[ "$output" == *"$fixture"*"first"*"found 1"* ]] || false

	run assert_text_order "$fixture" 'first' 'second' 2
	[ "$status" -ne 0 ]
	[[ "$output" == *"$fixture"*"first"*"second"* ]] || false

	run assert_text_order "$fixture" 'first' 'second' 1 1 'missing boundary'
	[ "$status" -ne 0 ]
	[[ "$output" == *"$fixture"*"missing boundary"* ]] || false
}

@test "missing guidance files fail absent-text checks instead of passing silently" {
	local fixture="$BATS_TEST_TMPDIR/missing.txt"

	run assert_absent_text "$fixture" 'forbidden phrase'

	[ "$status" -ne 0 ]
	[[ "$output" == *"$fixture"*"forbidden phrase"* ]] || false
}
