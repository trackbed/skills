#!/usr/bin/env bats

setup() {
	cd "$BATS_TEST_DIRNAME/.."
	SKILL="skills/docs:review/SKILL.md"
	FC_READ="skills/docs:review/references/false-compromise-read.md"
	SOURCES="skills/docs:review/references/sources.yaml"
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

@test "the false-compromise read is opt-in and leaves the default review unchanged" {
	grep -qF 'argument-hint: "[markdown-path] [--trade-offs] [--inline|--file|--output <path>]"' "$SKILL"
	grep -qF 'If `--trade-offs` is present, set `TRADE_OFFS=true`; otherwise set `TRADE_OFFS=false`.' "$SKILL"
	grep -qF 'The false-compromise read in step 7 runs only when it is `true`.' "$SKILL"
	grep -qF 'Omit the False Compromises section and its Coverage line when `TRADE_OFFS=false`' "$SKILL"
	[ "$(grep -cF '**False-compromise read:** <status from its reference; include only when TRADE_OFFS=true>' "$SKILL")" -eq 2 ]
	[ "$(grep -cxF '   ## False Compromises' "$SKILL")" -eq 2 ]
}

@test "the false-compromise read runs as a separate cold reader on proposals, decisions, and plans" {
	local read_line review_line

	grep -qF 'When the primary type from step 5 is `implementation-plan` or `proposal-decision`, launch a second, separate cold reader the same way' "$SKILL"
	grep -qF 'For any other type, record `skipped (<type> is not a proposal, decision draft, or implementation plan)`.' "$SKILL"
	read_line=$(grep -nF 'When `TRADE_OFFS=true`, also run the false-compromise read.' "$SKILL" | cut -d: -f1)
	review_line=$(grep -nF '**Review for findings**' "$SKILL" | cut -d: -f1)
	[ -n "$read_line" ]
	[ "$read_line" -lt "$review_line" ]
	grep -qF '{document-path}' "$FC_READ"
	grep -qF 'send this prompt, and nothing else, to the cold reader' "$FC_READ"
}

@test "the false-compromise prompt keeps its four rules" {
	grep -qF 'Finding no false compromise is a normal result. Do not invent one to fill the reply.' "$FC_READ"
	grep -qF 'A physical, mathematical, or theoretical limit is not a compromise.' "$FC_READ"
	grep -qF "State the cost of each pattern you suggest in this design; never suggest one without its cost." "$FC_READ"
	grep -qF 'Never supply a missing cost yourself; drop the item instead.' "$FC_READ"
	grep -qF 'Rate every kept item `Minor`, never higher' "$FC_READ"
	grep -qF '### FC-001: <short trade-off title> [Minor]' "$SKILL"
	grep -qF 'These findings stay out of `## Findings` and the verdict' "$FC_READ"
}

@test "a failed or skipped false-compromise read is never shown as clean" {
	grep -qF 'A failed or skipped read is not a clean read: omit the False Compromises section rather than writing "No false compromise found."' "$FC_READ"
	grep -qF 'Never write the reply yourself to fill the gap.' "$FC_READ"
	grep -qF 'Never report "No false compromise found." for a read that did not run.' "$SKILL"
}

@test "the false-compromise read credits EGM as inspiration without copying its catalog" {
	grep -qF 'id: egm-inventive-catalyst' "$SOURCES"
	grep -qF 'url: https://raw.githubusercontent.com/google/elephant-goldfish-model/6a8001ea31ccf72430ba0603a467ec6df9f69dd7/agents/inventive_catalyst.md' "$SOURCES"
	grep -qF 'The opt-in false-compromise read (`--trade-offs`) in `trackbed:docs:review`: Informed by its [inventive catalyst]' ../README.md
	! grep -qF 'Blessing in Disguise' "$FC_READ" || false
	! grep -qF 'Beforehand Cushioning' "$FC_READ" || false
}
