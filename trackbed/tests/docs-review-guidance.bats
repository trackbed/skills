#!/usr/bin/env bats

setup() {
	cd "$BATS_TEST_DIRNAME/.."
	SKILL="skills/docs:review/SKILL.md"
}

@test "a review with findings opens with a verdict before the first finding" {
	local verdict_line finding_line

	grep -qF 'When there are findings, open the report with a verdict before the first finding' "$SKILL"
	grep -qF '<Whether the author can use the document as it stands.> <The one or two problems that matter most, with their IDs.> <What the author still has to decide' "$SKILL"
	verdict_line=$(grep -nxF '   ## Verdict' "$SKILL" | cut -d: -f1)
	finding_line=$(grep -nF '### DOC-001:' "$SKILL" | cut -d: -f1)
	[ -n "$verdict_line" ]
	[ "$verdict_line" -lt "$finding_line" ]
	! grep -qF 'Lead with findings' "$SKILL" || false
}

@test "costly omissions survive the careful-implementer test" {
	grep -qF 'Keep an omission, even one a careful implementer might catch, when following the document as written could cost or misdirect money, expose the system to attack, or damage persisted data, unless the document or something it references already prevents that harm.' "$SKILL"
	grep -qF 'If that prevention would depend on code this skill does not read, keep the finding and mark it `UNVERIFIED`.' "$SKILL"
	grep -qF 'items that require reviewing source code, except a costly omission kept under the rule above.' "$SKILL"
	grep -qF 'Keep a costly omission from step 8 as a finding marked `UNVERIFIED`; list any other unchecked source-code claim under Residual risk.' "$SKILL"
}

@test "residual risk lists only open unknowns no finding covers" {
	grep -qF 'Under Residual risk, list only open unknowns that no finding covers' "$SKILL"
	grep -qF 'Do not repeat a finding, list a check that passed, or bring back a concern step 8 rejected.' "$SKILL"
	[ "$(grep -cF '**Residual risk:** <open unknowns, or "None identified">' "$SKILL")" -eq 2 ]
}
