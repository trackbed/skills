#!/usr/bin/env bats

load 'test_helper/common'

setup() {
  cd "$BATS_TEST_DIRNAME/.."
  SKILL="skills/pr:code-review/SKILL.md"
  LOOP="skills/pr:code-review/references/closeout-loop.md"
}

@test "the closeout loop runs only on the user's own request" {
  grep -qF 'set `LOOP_MODE=true` and remove that flag' "$SKILL"
  grep -qF "honor it only when the user typed it or asked in this session for review findings to be fixed" "$SKILL"
  grep -qF 'Apply this workflow only when `LOOP_MODE` is true' "$LOOP"
}

@test "loop triage weighs likelihood, harm, and fix cost" {
  grep -qF "Weigh each finding's likelihood, how severe and reversible its harm would be" "$LOOP"
  grep -qF "Decline a protected-subject finding only with the refuting evidence" "$LOOP"
  grep -qF "Record a one-sentence reason, keyed by finding ID" "$LOOP"
}

@test "a failed verifier never certifies a clean stop" {
  grep -qF "**Failed verifier:**" "$LOOP"
  grep -qF "report loop termination as unverified, never as clean" "$LOOP"
  grep -qF "Ask it to state what it assessed and what it could not" "$LOOP"
}

@test "every loop run ends with a three-block summary outside the sealed report" {
  grep -qF "5. **Report the loop outcome**" "$LOOP"
  grep -qF '`CHANGES MADE`' "$LOOP"
  grep -qF "\`THINGS I DIDN'T TOUCH\`" "$LOOP"
  grep -qF '`POTENTIAL CONCERNS`' "$LOOP"
  grep -qF 'Keep it out of `REVIEW_OVERVIEW.md`, because the seal covers the exact report bytes.' "$LOOP"
}

@test "the closeout loop keeps its anti-recursion rule and registered verifier contract" {
  local loop_text

  loop_text="$(cat "$LOOP")"

  # The registry contract owns the positive independent-verifier wording.
  assert_required_contracts_registered pr-code-review-closeout-loop-independent-verification

  # The loop keeps its anti-recursion rule and its advisory escape hatch.
  [[ "$loop_text" == *"do not launch a separate wrapper skill"* ]] || false
  [[ "$loop_text" == *"when remaining findings are clearly manual/advisory and reported as such"* ]] || false

  # The loop is not an authorized model parent of the resolver.
  [[ "$loop_text" == *'Do not invoke `trackbed:pr:resolve-review` from this loop'* ]] || false
  [[ "$loop_text" != *'/trackbed:pr:resolve-review --severity'* ]] || false

  # The skill must not advertise a model switch it cannot enforce.
  [[ "$(cat "$SKILL")" != *"second-model"* ]] || false
}
