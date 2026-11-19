#!/usr/bin/env bats

setup() {
	WAYFINDER="$BATS_TEST_DIRNAME/../skills/discovery:wayfinder"
	HANDOFF="$WAYFINDER/references/conductor-parallel-handoffs.md"
}

@test "a dispatched Wayfinder worker verifies the claim and skips frontier selection" {
	grep -qF 'A verified worker goes directly to Step 5. Stop on an invalid assignment.' "$WAYFINDER/SKILL.md"
	grep -qF 'use `WhoAmI` to verify that this session' "$HANDOFF"
	grep -qF 'both the ticket and its index row are `CLAIMED` with the same token' "$HANDOFF"
	grep -qF 'Write only the packet at the validated handoff path' "$HANDOFF"
}

@test "Wayfinder recovers confirmed failed dispatch without releasing an uncertain claim" {
	grep -qF 'returns a session with `messageError`, deliver the same assignment to that session through `SendSessionMessage`' "$HANDOFF"
	grep -qF 'reports `failed`, or appears in `missingIds`' "$HANDOFF"
	grep -qF 'If creation or delivery remains ambiguous, keep the claim' "$HANDOFF"
	grep -qF 'If the claim still matches this dispatch, record the failure, clear the claim fields' "$HANDOFF"
	grep -qF 'Update the ticket first and its index row second' "$HANDOFF"
}
