#!/usr/bin/env bats

setup() {
	cd "$BATS_TEST_DIRNAME/.."
	SKILL_DIR="skills/siw:generate-phases"
	DEEPENING="$SKILL_DIR/references/deepening-gate.md"
}

@test "generate-phases loops added deepening tasks back through the hard gates" {
	grep -qF "If the deepening pass adds, changes, splits, deletes, or reorders any task, loop back through Phase 4" "$DEEPENING"
	grep -qF "looped back through Phase 4 if it added, changed, split, deleted, or reordered tasks." "$SKILL_DIR/references/quality-gates.md"
}

@test "generate-phases turns deepening findings into work only past the finding threshold" {
	grep -qF "A finding that would add a safeguard or other mechanism the spec did not ask for becomes a task" "$DEEPENING"
	grep -qF "**Contract requires it:**" "$DEEPENING"
	grep -qF "**Failure would go unnoticed until costly:**" "$DEEPENING"
	grep -qF "**Later is expensive:**" "$DEEPENING"
	grep -qF "Decline every other such finding, including speculative safeguards against unlikely failures." "$DEEPENING"
	grep -qF 'Show the list at the end of the Phase 5 `PLAN:` block so the user can promote any of them, and carry the findings still declined into the Phase 7 `POTENTIAL CONCERNS`.' "$DEEPENING"
	grep -qF "Declined deepening findings:" "$SKILL_DIR/assets/phase-plan-template.md"
	grep -qF "deepening findings declined under the finding threshold" "$SKILL_DIR/references/summary-template.md"
	grep -qF "Incorporate valid findings into the draft plan before Phase 5; a finding that would add a mechanism the spec did not ask for must first pass the finding threshold." "$DEEPENING"
	grep -qF "If the change promotes a declined deepening finding, loop back through Phase 4 first." "$SKILL_DIR/SKILL.md"
}

@test "generate-phases issues state test limits and list only needed blockers" {
	grep -qF -- "- Test limits: {what the named tests catch, and what they can't catch" "$SKILL_DIR/references/issue-template.md"
	grep -qF "flag any the task could start without, because each unneeded edge keeps ready work waiting." "$SKILL_DIR/references/breakdown-review-prompt.md"
}
