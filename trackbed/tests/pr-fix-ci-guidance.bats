#!/usr/bin/env bats

@test "fix-ci auto mode consolidates pipeline fix commits" {
  local skill_text
  local consolidation_text
  local scoped_plan_text
  skill_text="$(cat "$BATS_TEST_DIRNAME/../skills/pr:fix-ci/SKILL.md")"
  consolidation_text="$(cat "$BATS_TEST_DIRNAME/../skills/pr:fix-ci/references/consolidation-flow.md")"
  scoped_plan_text="$(cat "$BATS_TEST_DIRNAME/../skills/pr:fix-ci/references/scoped-plan.md")"

  [[ "$skill_text" == *'Auto mode is the default: run the CI fix loop unattended'* ]] || false
  [[ "$skill_text" == *'If `AUTO_MODE=true`, choose **Automated** without prompting'* ]] || false
  [[ "$skill_text" == *'**Skip this step if:** `--fixup` mode was used, or `--no-consolidate` flag is set.'* ]] || false
  [[ "$skill_text" != *'Alias for `--no-consolidate`'* ]] || false
  [[ "$skill_text" != *'`--no-consolidate` / `--auto` flag'* ]] || false
  [[ "$skill_text" == *'`--scope-plan <archived-plan>` - Reconstruct and enforce a plan-to-PR mutation boundary'* ]] || false
  [[ "$skill_text" == *'read `references/scoped-plan.md` completely'* ]] || false

  [[ "$scoped_plan_text" == *'SCOPED_PLAN_LIFECYCLE=initial'* ]] || false
  [[ "$scoped_plan_text" == *'Use the runtime-derived `{validated-plan-branch}` before trusting mutable lifecycle fields.'* ]] || false
  [[ "$scoped_plan_text" == *'Before each edit, validate every intended path.'* ]] || false

  [[ "$consolidation_text" == *'If `AUTO_MODE=true`, do not offer "Keep separate".'* ]] || false
  [[ "$consolidation_text" == *'Before any automated rebase, confirm one of these is true:'* ]] || false
  [[ "$consolidation_text" == *'If `AUTO_MODE=true`, apply the pre-rebase safety gate above, then select **Automated**'* ]] || false
}

@test "fix-ci offers an explicit rebase or skip choice before CI remediation" {
  local skill_text
  local choice_line
  local delegate_line
  local resume_line
  local skip_line
  local watch_line
  skill_text="$(cat "$BATS_TEST_DIRNAME/../skills/pr:fix-ci/SKILL.md")"

  [[ "$skill_text" == *'When `PLAN_SCOPE_ACTIVE=false` and no rule above has already decided, read `${CLAUDE_PLUGIN_ROOT}/shared/implementation/references/decision-request.md` and ask in that format with `AskUserQuestion`.'* ]] || false
  [[ "$skill_text" == *'**Rebase then fix CI (recommended)** - Rebases onto `origin/$BASE` and force-pushes the Pull Request with a lease, which restarts CI and can dismiss approvals'* ]] || false
  [[ "$skill_text" == *'Require success and the same `BASE` recorded in Step 2'* ]] || false
  [[ "$skill_text" == *'**Skip rebase and fix CI** - Keeps the pushed head and fixes CI on the current base'* ]] || false
  [[ "$skill_text" == *'do not watch the stale remote branch or silently choose the skip path'* ]] || false
  [[ "$skill_text" == *'Do not run `git rebase` or force-push inline from this skill'* ]] || false

  choice_line="$(grep -nF 'Present exactly these choices, each with what it causes:' <<<"$skill_text" | cut -d: -f1)"
  delegate_line="$(grep -nF 'Invoke `$trackbed:pr:rebase --force-push --base <BASE>` through the platform skill mechanism' <<<"$skill_text" | cut -d: -f1)"
  resume_line="$(grep -nF 'return to Step 1 with the original parsed `fix-ci` modes still active' <<<"$skill_text" | cut -d: -f1)"
  skip_line="$(grep -nF '**Skip rebase and fix CI**' <<<"$skill_text" | cut -d: -f1)"
  watch_line="$(grep -nF '### Step 3: Check CI status first' <<<"$skill_text" | cut -d: -f1)"

  [ "$choice_line" -lt "$delegate_line" ]
  [ "$delegate_line" -lt "$resume_line" ]
  [ "$resume_line" -lt "$watch_line" ]
  [ "$skip_line" -lt "$watch_line" ]
}

@test "fix-ci --rebase and auto mode settle the rebase question without asking by default" {
  local skill_text
  local rebase_line
  local no_rebase_line
  local auto_line
  local choice_line
  skill_text="$(cat "$BATS_TEST_DIRNAME/../skills/pr:fix-ci/SKILL.md")"

  grep -qE '^argument-hint: .*\[--rebase\|--no-rebase\]' <<<"$skill_text"
  [[ "$skill_text" == *'- `--rebase` - When the branch is behind its base, rebase and push through `trackbed:pr:rebase --force-push` before fixing CI, without asking.'* ]] || false
  [[ "$skill_text" == *'if `--rebase` is present, set `REBASE_MODE=true`'* ]] || false
  [[ "$skill_text" == *'never invent `--rebase`, a scope plan, or a push destination'* ]] || false
  [[ "$skill_text" == *'decide whether a rebase would help and ask only when in doubt'* ]] || false
  [[ "$skill_text" == *'runs at most once per invocation. If the branch is behind again after that proven push, note the drift and continue to Step 3 without rebasing.'* ]] || false
  [[ "$skill_text" == *'Choice 1, whether selected, requested with `--rebase`, or decided in auto mode, uses the rebase workflow'"'"'s safe unattended push mode'* ]] || false

  rebase_line="$(grep -nF 'When `PLAN_SCOPE_ACTIVE=false` and `REBASE_MODE=true`, the user already chose: take choice 1 below' <<<"$skill_text" | cut -d: -f1)"
  no_rebase_line="$(grep -nF 'When `PLAN_SCOPE_ACTIVE=false` and `REBASE_MODE=false`, the caller already chose: take choice 2 below' <<<"$skill_text" | cut -d: -f1)"
  choice_line="$(grep -nF 'Present exactly these choices, each with what it causes:' <<<"$skill_text" | cut -d: -f1)"

  auto_line="$(grep -nF '`AUTO_MODE=true`, decide from that inspection instead of asking' <<<"$skill_text" | cut -d: -f1)"
  [[ "$skill_text" == *'take choice 2 when the base movement clearly cannot affect CI for this Pull Request'* ]] || false
  [[ "$skill_text" == *'unless `gh pr view --json reviewDecision` reports `APPROVED` or `gh pr checks` shows every check passing'* ]] || false
  [[ "$skill_text" == *'Ask only when in doubt, which includes that approved-or-green case.'* ]] || false

  [ "$rebase_line" -lt "$no_rebase_line" ]
  [ "$no_rebase_line" -lt "$auto_line" ]
  [ "$auto_line" -lt "$choice_line" ]
}

@test "fix-ci --no-consolidate keeps unrelated base drift and asks only when it can affect the PR" {
  local skill_text
  local auto_line
  local keep_line
  local ask_line
  skill_text="$(cat "$BATS_TEST_DIRNAME/../skills/pr:fix-ci/SKILL.md")"

  [[ "$skill_text" == *'Initialize `AUTO_MODE=true` and `KEEP_UNRELATED_DRIFT=false`.'* ]] || false
  [[ "$skill_text" == *'set `NO_CONSOLIDATE=true` and `AUTO_MODE=false`, and set `KEEP_UNRELATED_DRIFT=true` unless `--manual` is also present'* ]] || false
  [[ "$skill_text" == *'- `--manual` - Turn off auto mode: ask every time a branch is behind its base, even with `--no-consolidate`'* ]] || false
  [[ "$skill_text" == *'It never rebases without `--rebase` or the user'"'"'s answer, and keeps the pushed head when the drift cannot affect the Pull Request (Step 2).'* ]] || false
  [[ "$skill_text" == *'A guarded parent'"'"'s `--no-consolidate` run that does not pass `--manual` still keeps unrelated base drift under Step 2, because keeping the pushed head rewrites nothing.'* ]] || false
  [[ "$skill_text" == *'Take choice 2 without asking when no path that moved on the base is a file this Pull Request changes (`git diff --no-renames --name-only "origin/$BASE"...HEAD`), a CI workflow or configuration file, a lockfile, or shared build tooling, and say so in one line'* ]] || false
  [[ "$skill_text" == *'When any moved path is one of those, or you cannot tell (including when the fetch failed), ask.'* ]] || false
  [[ "$skill_text" == *'inspect what moved (`git log --no-renames --name-only --format= HEAD.."origin/$BASE"`)'* ]] || false
  [[ "$skill_text" == *'Once a proven rebase sets `rebased onto …`, keep it for the rest of the invocation; a later pass through Step 2 does not overwrite it.'* ]] || false
  [[ "$skill_text" == *'The evidence says how many commits the branch is behind `origin/$BASE` and lists the moved paths that touch this Pull Request'"'"'s files, CI configuration, lockfiles, or shared build tooling'* ]] || false
  [[ "$skill_text" == *'Record the result as `BASE_DRIFT_OUTCOME` for Step 12'* ]] || false
  [[ "$skill_text" == *'Also return `Base drift: {BASE_DRIFT_OUTCOME}` on its own line'* ]] || false
  [[ "$skill_text" == *'issue-to-pr only when its user typed `--rebase` with `--ship`'* ]] || false

  auto_line="$(grep -nF '`AUTO_MODE=true`, decide from that inspection instead of asking' <<<"$skill_text" | cut -d: -f1)"
  keep_line="$(grep -nF 'When `PLAN_SCOPE_ACTIVE=false`, `REBASE_MODE` is unset, and `KEEP_UNRELATED_DRIFT=true`, never rebase without an answer.' <<<"$skill_text" | cut -d: -f1)"
  ask_line="$(grep -nF 'Present exactly these choices, each with what it causes:' <<<"$skill_text" | cut -d: -f1)"
  [ -n "$keep_line" ]
  [ "$auto_line" -lt "$keep_line" ]
  [ "$keep_line" -lt "$ask_line" ]
}

@test "scoped fix-ci lifecycle preserves valid state transitions" {
  local scoped_plan_text
  local archive_validation_line
  local lifecycle_validation_line
  scoped_plan_text="$(cat "$BATS_TEST_DIRNAME/../skills/pr:fix-ci/references/scoped-plan.md")"

  archive_validation_line="$(grep -nF 'invoke `{archive-scope-validator}` under its contract' <<<"$scoped_plan_text" | cut -d: -f1)"
  lifecycle_validation_line="$(grep -nF 'Reject unknown, duplicate, or misplaced lifecycle sections before trusting checkpoint or publication text.' <<<"$scoped_plan_text" | cut -d: -f1)"

  [ -n "$archive_validation_line" ]
  [ -n "$lifecycle_validation_line" ]
  [ "$archive_validation_line" -lt "$lifecycle_validation_line" ]
  [[ "$scoped_plan_text" == *"Use the runtime boundary's lifecycle/source-byte integrity proof"* ]] || false
  [[ "$scoped_plan_text" == *'In initial lifecycle, require its repository, base ref, and head branch to match'* ]] || false
  [[ "$scoped_plan_text" == *'retain its head OID only for the live-head agreement and adoption proof in item 7'* ]] || false
  [[ "$scoped_plan_text" == *'In recovery lifecycle, require the execution result to record the exact Pull Request number and URL, repository, base ref, head branch, and head OID'* ]] || false
  [[ "$scoped_plan_text" == *'require the execution-result completion commit to equal the recorded workflow checkpoint before any recovery action'* ]] || false
  [[ "$scoped_plan_text" == *'initial or post-create lifecycle may adopt the live head only through one of these proofs:'* ]] || false
  [[ "$scoped_plan_text" == *'**Ancestor-only scoped push:**'* ]] || false
  [[ "$scoped_plan_text" == *'**Tree-identical narrative rewrite:**'* ]] || false
  [[ "$scoped_plan_text" == *'Require the recorded checkpoint not to be an ancestor of `{live-head}`'* ]] || false
  [[ "$scoped_plan_text" == *'atomically refresh both the workflow checkpoint head/tree and execution-result completion commit and Pull Request head OID'* ]] || false
  [[ "$scoped_plan_text" == *'In initial lifecycle mode, immediately after every proven push use the atomic archive update contract above to replace only the archived workflow-state checkpoint head/tree'* ]] || false
  [[ "$scoped_plan_text" == *'never adding an execution result'* ]] || false
}
