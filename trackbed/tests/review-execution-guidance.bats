#!/usr/bin/env bats

@test "code review modes and consumers require execution evidence" {
  local root="$BATS_TEST_DIRNAME/.."
  local skill="$root/skills/pr:code-review"
  run node --test "$root/tests/node/review-completion-eval.test.js"
  [ "$status" -eq 0 ]
  [[ "$(cat "$skill/SKILL.md")" == *'references/execution-contract.md'* ]] || false
  [[ "$(cat "$skill/references/team-mode.md")" == *'seal the exact temporary'* ]] || false
  [[ "$(cat "$skill/references/closeout-loop.md")" == *'Missing, incomplete, filtered-to-a-different-scope, or stale evidence blocks this loop'* ]] || false
  [[ "$(cat "$skill/references/output-template.md")" != *'Coverage Status (omit when complete)'* ]] || false
  [[ "$(cat "$root/skills/pr:review-convergence/references/review-convergence.md")" == *'--report <saved-report> --aspects all'* ]] || false
}

@test "execution helper rejects malformed commands without completing review" {
  run node "$BATS_TEST_DIRNAME/../skills/pr:code-review/scripts/review-execution.js" check
  [ "$status" -ne 0 ]
  [[ "$output" == *'INCOMPLETE:'* ]] || false
}

@test "review modes freeze no-cleanup without narrowing default aspect scope" {
  local skill="$BATS_TEST_DIRNAME/../skills/pr:code-review"
  local contract
  contract="$(cat "$skill/references/execution-contract.md")"
  [[ "$(cat "$skill/SKILL.md")" == *'Save this boolean as `noCleanup` in the execution plan while retaining `["all"]`'* ]] || false
  [[ "$(cat "$skill/references/team-mode.md")" == *'as `noCleanup` and `emphasizedDimensions` per `references/execution-contract.md`'* ]] || false
  [[ "$contract" == *'"noCleanup": false'* ]] || false
  [[ "$contract" == *'"emphasizedDimensions": []'* ]] || false
  [[ "$contract" == *'retain `aspects: ["all"]` for default scope'* ]] || false
  [[ "$contract" == *'still evaluates `removal` independently'* ]] || false
  [[ "$contract" == *'including convergence delta reviews with `noCleanup: true`'* ]] || false
}

@test "code review resumes only an interrupted, unsealed, fresh run" {
  local skill="$BATS_TEST_DIRNAME/../skills/pr:code-review"
  local contract
  contract="$(cat "$skill/references/execution-contract.md")"
  [[ "$(cat "$skill/SKILL.md")" == *'${CLAUDE_PLUGIN_ROOT}/shared/agents/references/resumable-fanout.md'* ]] || false
  [[ "$(cat "$skill/SKILL.md")" == *'first check for a resumable run under `Resume an interrupted run`'* ]] || false
  [[ "$(cat "$skill/SKILL.md")" == *'record each reviewer in the execution ledger as soon as its result arrives'* ]] || false
  [[ "$contract" == *'## Resume an interrupted run'* ]] || false
  [[ "$contract" == *'mktemp -d "${TMPDIR:-/tmp}/trackbed-code-review.XXXXXX"'* ]] || false
  [[ "$contract" == *'review-execution.js" status "$CANDIDATE_RUN"'* ]] || false
  [[ "$contract" == *'review-execution.js" requeue "$REVIEW_RUN"'* ]] || false
  [[ "$contract" == *'interrupts running jobs without failing them, so never record those jobs as `failed`'* ]] || false
  [[ "$contract" == *'and no `failed` job'* ]] || false
  [[ "$contract" == *'Team Mode and closeout-loop reruns skip this section and always `init` a fresh run'* ]] || false
  [[ "$contract" == *'Review resumed: <M> of <N> agent results reused from run <run-id>'* ]] || false
  [[ "$contract" == *'A job the host cut off without a result has not failed'* ]] || false
}

@test "execution helper usage lists the status and requeue commands" {
  run node "$BATS_TEST_DIRNAME/../skills/pr:code-review/scripts/review-execution.js" status
  [ "$status" -ne 0 ]
  [[ "$output" == *'init|start|finish|record|requeue|status|seal|check'* ]] || false
}
