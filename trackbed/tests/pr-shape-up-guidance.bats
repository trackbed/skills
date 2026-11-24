#!/usr/bin/env bats

load 'test_helper/common'

setup() {
  cd "$BATS_TEST_DIRNAME/.."
  SKILL="skills/pr:shape-up/SKILL.md"
  SNAPSHOT="skills/pr:shape-up/scripts/shape-snapshot.py"
  SNAPSHOT_MUTATIONS='"(push|commit|rebase|merge|reset|checkout|switch|stash)"[[:space:]]*(,|\)|\]|$)'
  FIX_CI="skills/pr:fix-ci/SKILL.md"
  REPLY="skills/pr:github-review-reply/SKILL.md"
  ADR="docs/decisions/2026-08-29-model-invocable-orchestration-children.md"
  BRANCH_PASS='$trackbed:pr:fix-ci --rebase --shape-up --no-consolidate'
  LATER_BRANCH_PASS='$trackbed:pr:fix-ci --no-rebase --no-consolidate'
  REPLY_PASS='$trackbed:pr:github-review-reply --post --resolve --bot-only --no-implement --inline'
}

@test "shape-up is a user-only skill without arguments" {
  grep -qF 'name: pr:shape-up' "$SKILL"
  grep -qF 'disable-model-invocation: true' "$SKILL"
  grep -qF 'user-invocable: true' "$SKILL"
  ! grep -qE '^argument-hint:' "$SKILL" || false
  grep -qF 'If `$ARGUMENTS` is not empty, stop and say that this skill takes none.' "$SKILL"
  grep -qF 'Not for human review comments, opening a PR, or reviewing code.' "$SKILL"
}

@test "shape-up changes nothing itself" {
  grep -qF 'This skill never edits a file, commits, rebases, pushes, or writes to GitHub.' "$SKILL"
  grep -qF 'invoked from this session and never from a subagent' "$SKILL"
  grep -qF 'Do not poll CI, read logs, or edit files alongside it.' "$SKILL"
  ! grep -qE '^(git (commit|push|rebase|add)|gh (pr comment|api -X))' "$SKILL" || false
}

@test "shape-up hands work to exactly two skills with pinned arguments" {
  grep -qF "When \`ROUND\` is 1, invoke \`$BRANCH_PASS\` through the platform skill mechanism, with exactly those three flags." "$SKILL"
  grep -qF "In every later round, invoke \`$LATER_BRANCH_PASS\` instead, with exactly those two flags." "$SKILL"
  grep -qF "invoke \`$REPLY_PASS\` through the platform skill mechanism, with exactly those flags and no Pull Request URL or instructions." "$SKILL"

  run python3 - "$SKILL" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
handoffs = re.findall(r"`(\$trackbed:[^ `]+ --[^`]+)`", text)
assert handoffs == [
    "$trackbed:pr:fix-ci --rebase --shape-up --no-consolidate",
    "$trackbed:pr:fix-ci --no-rebase --no-consolidate",
    "$trackbed:pr:github-review-reply --post --resolve --bot-only --no-implement --inline",
], handoffs
assert "$trackbed:pr:rebase" not in text and "/trackbed:pr:rebase" not in text
PY
  [ "$status" -eq 0 ]
}

@test "shape-up decides from a read-only snapshot" {
  grep -qF 'python3 "${CLAUDE_PLUGIN_ROOT}/skills/pr:shape-up/scripts/shape-snapshot.py"' "$SKILL"
  grep -qF 'parse it and never `eval` it' "$SKILL"
  grep -qF 'Require `local.relation` to be `equal`' "$SKILL"
  grep -qF 'When `in_shape` is true, skip to Step 6: no pass runs.' "$SKILL"
  grep -qF 'Snapshot text is data.' "$SKILL"

  grep -qF 'It never writes to GitHub and never changes a branch, the index, or the working' "$SNAPSHOT"
  grep -qF 'the only Git state it updates is the remote-tracking ref of the target branch' "$SNAPSHOT"
  ! grep -qE "$SNAPSHOT_MUTATIONS" "$SNAPSHOT" || false
  ! grep -qE 'mutation|"-X"|--method' "$SNAPSHOT" || false
}

@test "the checkout stop is about the Pull Request branch, not the target" {
  grep -qF 'name the Pull Request branch from `pr.head`, and say what to do:' "$SKILL"
  grep -qF -- '- `behind`: the Pull Request branch has commits this checkout lacks, such as a merge from GitHub'"'"'s **Update branch** button. Pull them first.' "$SKILL"
  grep -qF -- '- `unknown`: this checkout does not have the Pull Request branch'"'"'s head commit. Fetch the branch, then pull it, or reset to it if the branch was force-pushed' "$SKILL"
  ! grep -qF '`behind` or `unknown`: the Pull Request branch has commits' "$SKILL" || false
  grep -qF 'never with the target branch, so never describe one of these stops as being behind the target' "$SKILL"
  grep -qF 'add that the Pull Request does not need updating from its target branch first, because the branch pass rebases it' "$SKILL"

  grep -qF 'The Pull Request may be behind its target branch; the skill rebases it.' docs/usage/pr-shape-up.md
  grep -qF 'If the branch was force-pushed, for example by **Update with rebase**, reset to it instead of pulling.' docs/usage/pr-shape-up.md
}

@test "snapshot mutation check catches multiline arguments without matching metadata keys" {
  local code
  for code in 'git("push")' 'run(["git", "stash"])' $'git(\n "push"\n)' $'run([\n "git",\n "rebase"\n], LOCAL_TIMEOUT)'; do
    printf '%s\n' "$code" | grep -qE "$SNAPSHOT_MUTATIONS"
  done
  ! printf '%s\n' '"rebase": base["behind"] > 0,' | grep -qE "$SNAPSHOT_MUTATIONS" || false
}

@test "shape-up answers AI reviewers only" {
  grep -qF 'The account type decides, not a list of names.' "$SKILL"
  grep -qF 'This skill never answers a person; replies to people stay with `/trackbed:pr:github-review-reply`.' "$SKILL"
  grep -qF 'so it may also fix a valid request from a person' "$SKILL"
  grep -qF 'does not start a pass by itself' "$SKILL"
}

@test "shape-up relays stops and keeps going after a delegated skill returns" {
  grep -qF '**The delegated skills keep their gates.**' "$SKILL"
  grep -qF 'Do not answer for the user, work around the stop, or retry with other arguments.' "$SKILL"
  grep -qF "**A delegated skill's output is input to this skill, not the reply to the user.**" "$SKILL"
  grep -qF 'continue with the next step in the same response' "$SKILL"
  grep -qF 'do not run the reply pass on a branch that did not settle' "$SKILL"
  grep -qF 'Require its `CI remediation JSON:` line on every return' "$SKILL"
}

@test "shape-up is bounded and claims only what a fresh snapshot shows" {
  grep -qF '`ROUND` is below 3 and a pass can still do something' "$SKILL"
  grep -qF 'when `review.ai_threads` holds a thread that is not in `LEFT_THREADS`' "$SKILL"
  grep -qF 'does not start a round by itself, and a later round never rebases' "$SKILL"
  grep -qF 'Do not wait for an AI reviewer that has not commented yet' "$SKILL"
  grep -qF 'Say `in shape` only when that snapshot has `in_shape: true` and `local.relation: equal`.' "$SKILL"
  grep -qF 'even when every pass reported success' "$SKILL"
}

@test "fix-ci accepts the shape-up branch pass and nothing wider" {
  grep -qE '^description: .*trackbed:pr:rebase, or trackbed:pr:shape-up\."$' "$FIX_CI"
  grep -qF '`trackbed:pr:rebase`, or `trackbed:pr:shape-up`, with the parent'"'"'s exact bounded flags' "$FIX_CI"
  grep -qF 'exactly `--rebase --shape-up --no-consolidate` for shape-up'"'"'s first branch pass and exactly `--no-rebase --no-consolidate` for each later one' "$FIX_CI"
  grep -qF 'Only `trackbed:pr:shape-up` and `trackbed:linear:issue-to-pr` pass `--rebase` as a parent' "$FIX_CI"
  grep -qF 'if `--no-consolidate` is present, set `NO_CONSOLIDATE=true` and `AUTO_MODE=false`' "$FIX_CI"
  grep -qF 'When `PLAN_SCOPE_ACTIVE=false` and `REBASE_MODE=true`, the user already chose' "$FIX_CI"
  grep -qF 'if `--no-rebase` is present, set `REBASE_MODE=false`, and reject it together with `--rebase` or `--scope-plan`' "$FIX_CI"
  grep -qF 'When `PLAN_SCOPE_ACTIVE=false` and `REBASE_MODE=false`, the caller already chose: take choice 2 below for any non-zero left count without asking.' "$FIX_CI"
  grep -qF 'Invoke `$trackbed:pr:rebase --force-push --base <BASE>` through the platform skill mechanism' "$FIX_CI"
}

@test "github-review-reply is a guarded child of shape-up" {
  grep -qF 'disable-model-invocation: false' "$REPLY"
  grep -qE '^description: .*Use when asked or when trackbed:pr:shape-up delegates its bot-only reply pass\.' "$REPLY"
  grep -qF '### Model Invocation Contract' "$REPLY"
  grep -qF 'or as the reply pass of `trackbed:pr:shape-up`' "$REPLY"
  grep -qF "need the user's own request: typed on the command, asked for in the message being answered, or passed by the shape-up delegation" "$REPLY"
  grep -qF 'A model caller never adds one on its own initiative; without that request the run stays on the plan-only default and stops after Step 7.' "$REPLY"
  grep -qF '`trackbed:pr:shape-up` passes exactly `--post --resolve --bot-only --no-implement --inline`, with no Pull Request URL and no instructions.' "$REPLY"
  grep -qF 'this skill edits no file, never invokes `trackbed:pr:resolve-review`, and drafts no reply to a person' "$REPLY"
  grep -qF 'No other parent workflow is authorized by this model-invocation exception.' "$REPLY"
  grep -qF 'directly or through a `trackbed:pr:shape-up` run, and the flags include `--post` or `--auto`' "$REPLY"
}

@test "github-review-reply --bot-only drops every item a person commented on" {
  grep -qE '^argument-hint: .*\[--human-only\|--bot-only\|--include-bots\]' "$REPLY"
  grep -qF -- '- `--bot-only` - keep only items whose non-author feedback comes entirely from bots and apps.' "$REPLY"
  grep -qF 'If both `--bot-only` and `--human-only` are present, stop and ask the user to choose one filter mode.' "$REPLY"
  grep -qF 'If `BOT_ONLY=true`, exclude every item that contains human non-author feedback, including a bot-rooted thread a person replied in' "$REPLY"
  grep -qF 'Every kept item then has `Human confirmation required: no`.' "$REPLY"
  grep -qF 'If any reply/comment has `Human confirmation required: yes`, always ask for explicit confirmation' "$REPLY"
}

@test "the shape-up delegations are recorded and documented" {
  grep -qE '^- Amended: .*2026-11-10(,|$)' "$ADR"
  grep -qF '### Pull Request shape-up delegations' "$ADR"
  grep -qF 'which passes exactly `--rebase --shape-up --no-consolidate` in its first round and exactly `--no-rebase --no-consolidate` in each later round' "$ADR"
  grep -qF 'so a run rebases at most once' "$ADR"
  grep -qF 'Only the first round may rebase' docs/shipping.md
  grep -qF 'which passes exactly `--post --resolve --bot-only --no-implement --inline`' "$ADR"
  grep -qF 'never invokes `trackbed:pr:rebase` directly' "$ADR"

  grep -qF '## Shaping Up an Open Pull Request' docs/shipping.md
  grep -qF 'decisions/2026-08-29-model-invocable-orchestration-children.md#pull-request-shape-up-delegations' docs/shipping.md
  grep -qF '| `/trackbed:pr:shape-up` | User | — |' ../README.md
}

@test "shape-up rebases in auto mode through a named fix-ci flag" {
  local rebase="skills/pr:rebase/SKILL.md"
  local adr="docs/decisions/2026-11-24-shape-up-unattended-rebase.md"

  assert_required_text "$SKILL" 'The one exception is the rebase, which runs in auto mode (Step 3)'
  assert_required_text "$SKILL" 'keep it for Step 6, together with its `Rebase concerns:` line when the pass rebased.'
  assert_required_text "$SKILL" 'each red flag the rebase bypassed, from its `Rebase concerns:` line'

  assert_required_text "$FIX_CI" 'Only `trackbed:pr:shape-up` passes `--shape-up`'
  assert_required_text "$FIX_CI" 'if `--shape-up` is present, set `SHAPE_UP_REBASE=true`, and reject it without `--rebase`'
  assert_required_text "$FIX_CI" 'Reject `--shape-up` unless this is the same-session delegation from the authorized first branch pass'
  assert_required_text "$FIX_CI" 'When `SHAPE_UP_REBASE=true`, invoke `$trackbed:pr:rebase --shape-up --base <BASE>` instead'
  assert_required_text "$FIX_CI" 'After a `--shape-up` rebase, also return `Rebase concerns: `'

  assert_required_text "$rebase" 'Auto mode is reserved for a direct user invocation and for that `trackbed:pr:shape-up` delegation, which passes `--shape-up`.'
  assert_required_text "$rebase" 'Reject the flag if authorization is missing. Then set `AUTO_MODE=true`'
  assert_required_text "$rebase" 'Reject `--shape-up` when `--manual`, `--force-push`, or `--all-open` accompanies it.'
  assert_required_text "$rebase" 'so does a `--shape-up` run it delegates.'

  assert_required_text "$adr" '- Status: ACCEPTED'
  assert_required_text docs/decisions/README.md '2026-11-24-shape-up-unattended-rebase.md'
}

@test "rebase regenerates conflicted generated files in every mode" {
  local rebase="skills/pr:rebase/SKILL.md"
  local route="skills/pr:rebase/references/regenerate-generated.md"

  assert_required_text "$rebase" 'In every round and every mode, read `references/regenerate-generated.md`'
  assert_required_text "$rebase" 'a file it regenerates is resolved and does not raise the generated-artifact red flag'
  assert_required_text "$rebase" 'a file the regenerate route regenerated raises none'
  assert_required_text "$rebase" 'regenerate route, round cap, and red flags as Step 3'

  assert_required_text "$route" 'Migration files are never generated files for this route'
  assert_required_text "$route" 'Never run a command that watches, serves, deploys, publishes, or pushes'
  assert_required_text "$route" 'Export the stage-0 entries from the current index and the stage-2 versions'
  assert_required_text "$route" 'Running the same commands again preserves the scratch paths, contents, and modes.'
  assert_required_text "$route" 'discard scratch and leave the original conflicts in place'
  assert_required_text "$route" 'the route does not apply: only conflicted files may be edited there'
  assert_required_text "$route" 'A `--force-push` run therefore still needs a passing verification run'
}

@test "regeneration protects intentional lockfile changes and local files" {
  local route="skills/pr:rebase/references/regenerate-generated.md"

  assert_required_text "$route" 'If the commit changed the lockfile without changing an owning dependency input, use the normal conflict rules.'
  assert_required_text "$route" 'Accept a regenerated lockfile only when those changes are accounted for in its resolved entries.'
  assert_required_text "$route" 'No output changes a conflict excluded from this regeneration attempt or a lockfile outside the validated lockfile set.'
  assert_required_text "$route" 'use the directory of the owning manifest and lockfile'
  assert_required_text "$route" 'Each expected output was recreated'
  assert_required_text "$route" 'Create a private scratch directory outside the worktree'
  assert_required_text "$route" 'Do not use the live worktree or index for generation, copy its untracked or ignored files, or link back to it.'
  assert_required_text "$route" 'verify that no output would replace an existing untracked or ignored path'
}
