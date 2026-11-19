#!/usr/bin/env bats

setup() {
  ROOT="$BATS_TEST_DIRNAME/.."
  POLICY="$ROOT/shared/pr-review/references/model-selection.md"
}

@test "review model policy defines the requested provider ladders and floors" {
  run python3 - "$POLICY" <<'PY'
import pathlib
import sys

rows = []
for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
    cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
    if len(cells) == 3 and cells[0] in ('Claude', 'Codex'):
        rows.append(tuple(cells))
assert rows == [
    ('Claude', 'Fable', 'Opus'),
    ('Claude', 'Opus', 'Sonnet'),
    ('Claude', 'Sonnet', 'Haiku'),
    ('Claude', 'Haiku', 'Haiku'),
    ('Codex', 'Astra', 'Sol'),
    ('Codex', 'Sol', 'Luna'),
    ('Codex', 'Luna', 'Luna'),
], rows
PY
  [ "$status" -eq 0 ]
}

@test "every review producer loads the one shared policy" {
  local skill
  for skill in code-review convention-review github-review overengineering-review product-review review-convergence; do
    [[ "$(cat "$ROOT/skills/pr:$skill/SKILL.md")" == *'read and apply `${CLAUDE_PLUGIN_ROOT}/shared/pr-review/references/model-selection.md`'* ]] || false
    [ ! -e "$ROOT/skills/pr:$skill/references/model-selection.md" ]
  done
}

@test "subagent model override is advertised and parsed before review routing" {
  run python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
for name in ['code-review', 'product-review', 'convention-review',
             'overengineering-review', 'github-review', 'review-convergence']:
    text = (root / f'skills/pr:{name}/SKILL.md').read_text()
    hint = next(line for line in text.splitlines() if line.startswith('argument-hint:'))
    assert '[--subagent-model <model>]' in hint, name
    body = text.split('---', 2)[2]
    for line in body.splitlines():
        if 'Usage:' in line:
            assert '[--subagent-model <model>]' in line, name
    work_start = '## Step 2: Validate' if name == 'review-convergence' else '```bash'
    assert body.index('references/model-selection.md') < body.index(work_start), name
    if name in ('code-review', 'product-review'):
        assert body.index('references/model-selection.md') < body.index('## Team Mode'), name
PY
  [ "$status" -eq 0 ]
}

@test "override parsing validates values without interpreting requirements or shell text" {
  local policy
  policy="$(cat "$POLICY")"
  [[ "$policy" == *'parse `--subagent-model <model>` at most once'* ]] || false
  [[ "$policy" == *'matching `[A-Za-z0-9][A-Za-z0-9._:/-]*`'* ]] || false
  [[ "$policy" == *'Reject duplicate occurrences, a missing value, a following flag in place of a value, and invalid characters'* ]] || false
  [[ "$policy" == *'never parse flag-shaped text in the inert requirements remainder'* ]] || false
  [[ "$policy" == *'Do not evaluate or interpolate the value as shell code'* ]] || false
  [[ "$policy" == *'remove the flag and its value from the remaining arguments before parsing aspects, categories, positional selectors, or Team Mode'* ]] || false
  [[ "$policy" == *'flag takes precedence over conversational model preferences and the `TRACKBED_REVIEW_SUBAGENT_LEVEL` setting'* ]] || false
  [[ "$policy" == *'preserve an exact model ID unchanged'* ]] || false
  [[ "$policy" == *'Validate availability before repository work'* ]] || false
  [[ "$policy" == *'`--subagent-model inherit` uses the orchestrator'* ]] || false
  [[ "$policy" == *'bypasses the step-down ladder'* ]] || false
  [[ "$(cat "$ROOT/skills/pr:code-review/SKILL.md")" == *'removing the model pair must not merge later positional aspects into an emphasis span'* ]] || false
}

@test "level environment setting chooses step-down or same-level reviewers" {
  local policy
  policy="$(cat "$POLICY")"
  [[ "$policy" == *'read the `TRACKBED_REVIEW_SUBAGENT_LEVEL` environment variable'* ]] || false
  [[ "$policy" == *'Accept `lower` or `same` case-insensitively after trimming whitespace; unset or empty means `same`'* ]] || false
  [[ "$policy" == *'Reject any other value before repository work and report `Expected TRACKBED_REVIEW_SUBAGENT_LEVEL=lower|same.`'* ]] || false
  [[ "$policy" == *'`same`, the default, keeps review subagents on the orchestrator'* ]] || false
  [[ "$policy" == *'`lower` opts into the step-down ladder below'* ]] || false
  [[ "$policy" == *'When `SUBAGENT_MODEL_LEVEL` is `lower`, select one class lower within the same provider'* ]] || false
  [[ "$policy" == *'otherwise honor a conversational reviewer-model choice; otherwise follow `SUBAGENT_MODEL_LEVEL`: `same` uses the orchestrator'*'and `lower` applies the ladder in step 3'* ]] || false
  [[ "$policy" == *'do not convert the setting into a forwarded `--subagent-model` flag'* ]] || false
}

@test "non-review roles share the model controls without changing review defaults or duplicating the ladder" {
  local policy
  policy="$(cat "$POLICY")"
  [[ "$policy" == *'## Non-Review Subagent Roles'* ]] || false
  [[ "$policy" == *'**Lens or scan agents**'* ]] || false
  [[ "$policy" == *'**Recon or exploration agents**'* ]] || false
  [[ "$policy" == *'**Drafting agents**'* ]] || false
  [[ "$policy" == *'**Filter or validator agents**'* ]] || false
  [[ "$policy" == *'It changes nothing for review subagents'* ]] || false
  [[ "$policy" == *'`same` remains the default for every role'* ]] || false
  [[ "$policy" == *'a role never steps down twice'* ]] || false
  [[ "$policy" == *'any agent that edits files, commits, or applies fixes'* ]] || false
  [[ "$policy" == *'explicit different-provider or cross-model modes'* ]] || false
  run python3 - "$POLICY" <<'PY'
from pathlib import Path
import re
import sys

section = Path(sys.argv[1]).read_text().split('## Non-Review Subagent Roles\n', 1)[1]
assert not re.search(r'^\s*\|\s*(Claude|Codex)\s*\|', section, re.MULTILINE)
PY
  [ "$status" -eq 0 ]
}

@test "wrappers and reruns forward the override without changing requirements or adversarial models" {
  local policy team skill
  policy="$(cat "$POLICY")"
  [[ "$policy" == *'Insert it before `--requirements` when that sentinel is present'* ]] || false
  [[ "$policy" == *'Do not place it inside the requirements block or append it after the sentinel'* ]] || false
  [[ "$(cat "$ROOT/skills/pr:github-review/SKILL.md")" == *'include `--subagent-model <model>` in both the code-review and product-review invocations'* ]] || false
  [[ "$(cat "$ROOT/skills/pr:code-review/references/closeout-loop.md")" == *'Restore `--subagent-model <model>` from a non-empty `SUBAGENT_MODEL_OVERRIDE` in every nested review invocation; preserve explicit `inherit` as well'* ]] || false
  for skill in code-review product-review; do
    team="$(cat "$ROOT/skills/pr:$skill/references/team-mode.md")"
    [[ "$team" == *'Preserve `SUBAGENT_MODEL_OVERRIDE` from startup parsing'* ]] || false
  done
  policy="$(cat "$ROOT/skills/pr:review-convergence/references/review-convergence.md")"
  [[ "$policy" == *'forward `--subagent-model <model>` to every code-review, convention-review, and overengineering-review invocation, including reruns, validation-only mode, and bounded-stop validation'* ]] || false
  [[ "$policy" == *'keep the requirements remainder byte-for-byte unchanged'* ]] || false
  [[ "$policy" == *'`--adversarial-model` controls that gate independently'* ]] || false
}

@test "team and loop entry points preserve the reviewer selection" {
  local skill
  for skill in code-review product-review; do
    [[ "$(cat "$ROOT/skills/pr:$skill/references/team-mode.md")" == *'selected reviewer model for every teammate and later validation spawn'* ]] || false
  done
  [[ "$(cat "$ROOT/skills/pr:code-review/references/closeout-loop.md")" == *'for review reruns and the independent termination verifier'* ]] || false
  [[ "$(cat "$POLICY")" == *"Do not step down again from a review subagent's model"* ]] || false
}

@test "model policy sets launch parameters and handles Codex fork constraints" {
  local policy
  policy="$(cat "$POLICY")"
  [[ "$policy" == *'Set the actual agent-launch `model` parameter on every spawn'* ]] || false
  [[ "$policy" == *'pass the selected model to `spawn_agent`'* ]] || false
  [[ "$policy" == *'use `fork_turns="none"` or a supported bounded fork'* ]] || false
  [[ "$policy" == *'include the complete review mission, frozen scope, applicable conventions, and required review contracts'* ]] || false
  [[ "$policy" == *'Preserve the current reasoning effort when supported'* ]] || false
}

@test "model policy preserves explicit choices and reports unsupported defaults" {
  local policy
  policy="$(cat "$POLICY")"
  [[ "$policy" == *'Honor an explicit user model choice for review subagents over these defaults'* ]] || false
  [[ "$policy" == *'trusted session/runtime metadata'* ]] || false
  [[ "$policy" == *'If the active class is unknown, the selected step-down model is unavailable, or the host cannot select a subagent model'* ]] || false
  [[ "$policy" == *"retain the host's inherited/default behavior and report the limitation once"* ]] || false
  [[ "$policy" == *'If an explicit user model choice cannot be honored, report that blocker'* ]] || false
  [[ "$policy" == *'Explicit different-provider adversarial reviews retain their own provider/model policy'* ]] || false
}

@test "review wrappers preserve orchestrator class and forward explicit reviewer choices" {
  local file text
  for file in \
    "$ROOT/skills/pr:github-review/SKILL.md" \
    "$ROOT/skills/pr:review-convergence/references/review-convergence.md"; do
    text="$(cat "$file")"
    [[ "$text" == *"Keep delegated review orchestrators on this session's model"* ]] || false
    [[ "$text" == *'do not lower the orchestrator first and cause a second step-down'* ]] || false
    [[ "$text" == *'Forward any explicit user reviewer-model choice with the review handoff'* ]] || false
  done
}

@test "stepped-down Claude Code reviewers keep or report the orchestrator's effort" {
  local policy
  policy="$(cat "$POLICY")"
  [[ "$policy" == *"A subagent inherits the session's effort level only while it runs on the orchestrator's model"* ]] || false
  [[ "$policy" == *"trusted session/runtime metadata gives the orchestrator's effort level"* ]] || false
  [[ "$policy" == *"otherwise report once that stepped-down reviewers run at the selected model's default effort"* ]] || false
  grep -qF "does not inherit the session's effort level" "$ROOT/docs/review.md"
}

@test "every skill that loads the model policy declares Claude Code's subagent docs" {
  local consumer consumers
  consumers=$(cd "$ROOT" && grep -rlF "shared/pr-review/references/model-selection.md" skills --include='*.md' | cut -d/ -f2 | sort -u)
  [ -n "$consumers" ]
  for consumer in $consumers; do
    grep -qF "id: anthropic-claude-code-subagents" "$ROOT/skills/$consumer/references/sources.yaml" || { echo "$consumer does not declare the subagent docs"; return 1; }
  done
}
