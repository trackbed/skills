#!/usr/bin/env bats

setup() {
	cd "$BATS_TEST_DIRNAME/.."
	SKILL="skills/code:api-design/SKILL.md"
	RETRY="skills/code:api-design/references/retry-safety.md"
	NAMING="skills/code:api-design/references/naming-conventions.md"
	ERRORS="skills/code:api-design/references/error-shapes.md"
	TS="skills/code:api-design/references/typescript-patterns.md"
}

@test "contract rule requires every state-changing operation to state its retry behavior" {
	grep -qF "The contract is: input type, output type, error cases, HTTP status mapping, naming, and retry behavior." "$SKILL"
	grep -qF "every state-changing operation's contract states whether repeating the call is safe and what the repeat returns" "$SKILL"
	grep -qF 'Read `references/retry-safety.md`' "$SKILL"
	test -f "$RETRY"
	grep -qF "## State the repeat behavior for every state-changing operation" "$RETRY"
	grep -qF "1. **Is a repeat safe?**" "$RETRY"
	grep -qF "2. **What does the repeat return?**" "$RETRY"
}

@test "costly duplicates use an idempotency key that covers all five cases" {
	grep -qF "the contract uses an idempotency key and covers five cases: a key reused with a different body, a duplicate arriving while the first call runs, an unknown outcome after a timeout, how long keys are kept, and at-least-once delivery for webhook and queue consumers" "$SKILL"

	grep -qF "### 1. Key reused with a different body" "$RETRY"
	grep -qF '"code": "IDEMPOTENCY_KEY_REUSED"' "$RETRY"
	grep -qF "### 2. Duplicate arrives while the first call runs" "$RETRY"
	grep -qF '"code": "REQUEST_IN_PROGRESS"' "$RETRY"
	grep -qF "### 3. Unknown outcome after a timeout" "$RETRY"
	grep -qF 'retry with the **same** key' "$RETRY"
	grep -qF "### 4. How long keys are kept" "$RETRY"
	grep -qF "State the retention window in the contract" "$RETRY"
	grep -qF "### 5. At-least-once delivery to webhook and queue consumers" "$RETRY"
	grep -qF 'stable, unique `eventId`' "$RETRY"
}

@test "error codes and union tags follow the UPPER_SNAKE enum rule" {
	grep -qF -- '- **Error codes and union tag values** — sent over the wire, so they follow the enum rule: `UPPER_SNAKE`' "$SKILL"
	grep -qF '| Error codes | `UPPER_SNAKE` (the enum rule) |' "$NAMING"
	grep -qF '| Union tag values | `UPPER_SNAKE` (the enum rule) |' "$NAMING"
	grep -qF "an existing API keeps the casing found during convention detection" "$NAMING"
	grep -qF '`UPPER_SNAKE`, following the enum rule' "$ERRORS"
	grep -qF '"code": "INVALID_REQUEST"' "$ERRORS"
	grep -qF '{ type: "SUCCESS"; task: Task }' "$TS"
}

@test "no error-shape, retry, or union example uses kebab-case or lowercase wire values" {
	local file
	for file in "$ERRORS" "$RETRY"; do
		if grep -nE '"code": "[^"]*[a-z-]' "$file"; then
			echo "error codes in $file must be UPPER_SNAKE" >&2
			return 1
		fi
	done
	if grep -nE '"?fields"?: \{[^}]*: "[^"]*[a-z-]' "$ERRORS" || grep -nE '^ +"[A-Za-z]+": "[a-z][a-z0-9_-]*"' "$ERRORS"; then
		echo "field-level error codes in $ERRORS must be UPPER_SNAKE" >&2
		return 1
	fi
	if grep -nE 'type: "[^"]*[a-z-]' "$TS" "$RETRY" "$SKILL" || grep -nE '=== "[^"]*[a-z-]|`"?[a-z]+"?` \||\| `"?[a-z]+"?`' "$TS"; then
		echo "union tag values must be UPPER_SNAKE" >&2
		return 1
	fi
	if grep -nE 'Kebab-case or snake_case' "$ERRORS"; then
		echo "error-shapes.md must not allow kebab-case codes" >&2
		return 1
	fi
}
