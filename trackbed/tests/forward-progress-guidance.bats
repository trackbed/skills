#!/usr/bin/env bats

setup() {
  cd "$BATS_TEST_DIRNAME/.."
}

REFERENCE="shared/implementation/references/forward-progress.md"
CONSUMERS=(
  "skills/code:plan-to-pr"
  "skills/code:work-from-plan"
  "skills/linear:issue-implement"
)

@test "forward progress is a shared advisory reference with explicit safety boundaries" {
  test ! -e "skills/kramme:code:forward-progress"
  grep -qF "# Preserve Forward Progress" "$REFERENCE"
  grep -qF "it never bypasses controls that protect identity, authority, integrity, concurrency, resumability, scope, CI, or publication safety." "$REFERENCE"
  grep -qF "This convention is advisory. It grants no permission" "$REFERENCE"
  grep -qF "Treat workflow control as substantive when getting it wrong could:" "$REFERENCE"
  grep -qF "Follow substantive controls exactly." "$REFERENCE"
  grep -qF "rerun the smallest affected dependency cone" "$REFERENCE"
  grep -qF "Do not run a blocked stage manually, clear a lock, fabricate a receipt" "$REFERENCE"
}

@test "forward progress preserves plan, Linear, resume, verification, and publication controls" {
  direct="skills/code:work-from-plan/references/direct-execution.md"
  work_from_plan="skills/code:work-from-plan/SKILL.md"
  linear="skills/linear:issue-implement/references/implementation-workflows.md"
  linear_skill="skills/linear:issue-implement/SKILL.md"
  plan_to_pr="skills/code:plan-to-pr/SKILL.md"
  resolve='Resolve `${CLAUDE_PLUGIN_ROOT}/shared/implementation/references/forward-progress.md` as `{forward-progress-reference}`'

  grep -qF "Read \`{forward-progress-reference}\` before applying it." "$direct"
  grep -qF "scope boundary, user-approval boundary, and verification requirement" "$direct"
  grep -qF "$resolve, or use the resolved path the caller passed, then read \`{forward-progress-reference}\` before applying it in \`references/direct-execution.md\`." "$work_from_plan"
  grep -qF 'Read and follow `references/direct-execution.md`.' "$work_from_plan"
  grep -qF "During Guided or Autonomous implementation, read \`{forward-progress-reference}\` before applying the convention" "$linear"
  grep -qF "Branch identity, Linear requirements, user confirmations, resume proofs" "$linear"
  grep -qF 'Read the implementation workflow for the selected approach from `references/implementation-workflows.md`.' "$linear_skill"
  grep -qF "$resolve, then read it before applying the convention in that workflow." "$linear_skill"
  grep -qF "$resolve and pass it with the implementation handoff" "$plan_to_pr"
  grep -qF "without invoking the convention outside delegation" "$plan_to_pr"
  grep -qF "a valid checkpoint prevents unnecessary reimplementation while preserving every downstream gate" "$plan_to_pr"
}

@test "forward progress consumers declare its rewritten external inspiration" {
  for consumer in "${CONSUMERS[@]}"; do
    sources="$consumer/references/sources.yaml"
    grep -qF "id: vuk97-forward-implementation-first" "$sources"
    grep -qF "baseline_commit: 2d4dd7eacb4c41a31d85501f6f44d33fef21017a" "$sources"
    grep -qF "The shared forward-progress reference's context-recovery paragraph retains its idea" "$sources"
    grep -qF "Two divergences from this source are deliberate: when a workflow stage is blocked and no documented recovery path exists, the convention reports the exact blocker and stops rather than running the stage by hand, and it treats locks as protected concurrency controls rather than bookkeeping to avoid." "$sources"
    test ! -e "$consumer/references/sources-snapshot"
  done
}

@test "forward progress recovers from a context reset using durable state" {
  grep -qF "after a context reset or compaction, when drift symptoms such as repeated wrong file paths or API signatures or lost decisions appear" "$REFERENCE"
  grep -qF "After a context reset or compaction, rebuild from durable state rather than memory:" "$REFERENCE"
  grep -qF "Reload the current branch, the working-tree status, and the commits and diff since the base the active workflow resolved. Treat them as the record of what changed" "$REFERENCE"
  grep -qF "If a failing check was being fixed when context was lost, rerun that check before continuing the fix" "$REFERENCE"
  grep -qF "Count a confirmation or decision only when a surviving record shows it: a parent handoff, a written plan, or a commit. Otherwise ask again before the step it gates" "$REFERENCE"
}

@test "forward progress fixes defects before replay and defines valid checkpoints" {
  grep -qF "When a demonstrated defect triggers the replay, fix the defect in the stage that produced it before rerunning that stage's dependency cone" "$REFERENCE"
  grep -qF "A checkpoint counts as correctness evidence only when it names the check, the tree or input it ran against, the observed outcome, and the expected outcome." "$REFERENCE"
  grep -qF "A checkpoint missing any of these is advisory progress state" "$REFERENCE"
  grep -qF "It still counts as a substantive control when it establishes a property listed under Preserve Substantive Controls." "$REFERENCE"
}
