#!/usr/bin/env bats

setup() {
  cd "$BATS_TEST_DIRNAME/.."
  REFERENCE="shared/findings/references/disputing-findings.md"
  REFERENCE_PATH='${CLAUDE_PLUGIN_ROOT}/shared/findings/references/disputing-findings.md'
  RESOLVE_AUDIT="skills/siw:resolve-audit/SKILL.md"
  RESOLVE_REVIEW="skills/pr:resolve-review/SKILL.md"
  APPLY_NOW="skills/siw:spec-audit/references/apply-now.md"
  SPEC_AUDIT="skills/siw:spec-audit"
}

@test "a dispute needs evidence the reviewer could have read" {
  grep -qF '**Contest:** the finding is wrong and you can cite evidence the reviewer could have read' "$REFERENCE"
  grep -qF '**Escalate:** the finding looks wrong only because of something no file records' "$REFERENCE"
  grep -qF '"This was intentional" is not evidence.' "$REFERENCE"
  grep -qF 'wanting a finding to be wrong is not evidence that it is' "$REFERENCE"
  grep -qF 'Do not contest a comprehension gap.' "$REFERENCE"
  grep -qF 'Do not add text only to satisfy a reviewer that lacked context.' "$REFERENCE"
  grep -qF 'Do not lower a severity to make a finding go away.' "$REFERENCE"
  grep -qF 'accept the finding, and record your evidence for the lower rating alongside it' "$REFERENCE"
  ! grep -qF 'contest it and say why' "$REFERENCE"
}

@test "resolve-audit checks a finding before offering options" {
  local check_line summary_line

  grep -qF "$REFERENCE_PATH" "$RESOLVE_AUDIT"
  check_line=$(grep -nF '### 4.0 Check the Finding' "$RESOLVE_AUDIT" | cut -d: -f1)
  summary_line=$(grep -nF '#### 4.1 Executive Summary' "$RESOLVE_AUDIT" | head -n 1 | cut -d: -f1)
  [ "$check_line" -lt "$summary_line" ]
  grep -qF 'Create no issue. Add `**Status:** [Contested] {the evidence}`' "$RESOLVE_AUDIT"
}

@test "resolve-audit asks before contesting, unless --auto was given" {
  grep -qF 'With `--auto`, contest it without asking, unless it is Critical or its `Severity Note` says `from Critical`.' "$RESOLVE_AUDIT"
  grep -qF 'so handle it as an escalated finding. Otherwise ask the question below.' "$RESOLVE_AUDIT"
  grep -qF 'label: "Yes, contest it"' "$RESOLVE_AUDIT"
  grep -qF 'label: "No, the finding stands"' "$RESOLVE_AUDIT"
  grep -qF 'a disputed finding takes the Step 4.0 question instead' "$RESOLVE_AUDIT"
}

@test "naming a contested finding reopens it" {
  grep -qF 'Naming the id reopens it at Step 4.0.' "$RESOLVE_AUDIT"
  grep -qF '**Accept:** remove any earlier `[Contested]` line' "$RESOLVE_AUDIT"
}

@test "a finding that ends at the check still completes its cycle" {
  grep -qF 'After creating the SIW issue for one finding, or ending its cycle at Step 4.0:' "$RESOLVE_AUDIT"
  grep -qF 'or ending it at Step 4.0.' "$RESOLVE_AUDIT"
  grep -qF 'complete the full Steps 4-5 cycle or end it at Step 4.0.' "$RESOLVE_AUDIT"
}

@test "resolve-audit never settles unrecorded knowledge on its own" {
  grep -qF 'With `--auto`, do not ask, annotate, or create an issue.' "$RESOLVE_AUDIT"
  grep -qF 'A finding escalated in Step 4.0 gets no issue; report it instead.' "$RESOLVE_AUDIT"
  grep -qF 'Escalated - needs your decision (finding ids + the unrecorded fact' "$RESOLVE_AUDIT"
  grep -qF 'under `## Decision Log` when `siw/LOG.md` has that heading' "$RESOLVE_AUDIT"
  grep -qF 'readers of the spec will not see the fact unless it is added to the spec' "$RESOLVE_AUDIT"
}

@test "contested findings are not processed again" {
  grep -qF -- '- The finding is marked `**Status:** [Contested]` and the arguments do not name its id.' "$RESOLVE_AUDIT"
  grep -qF -- '- Findings marked `**Status:** [Contested]`' "$RESOLVE_AUDIT"
  grep -qF -- '- Already marked `**Status:** [Contested]`' "$APPLY_NOW"
  grep -qF 'Contested (finding ids + the evidence)' "$RESOLVE_AUDIT"
  grep -qF 'skipping findings marked `**Status:** [Contested]`' "skills/discovery:interview/references/siw-mode.md"
  grep -qF 'without its findings marked `**Status:** [Contested]`' "shared/findings/references/findings-intake.md"
}

@test "a contested finding carried into a re-audit stays out of counts and issues" {
  local rules="$SPEC_AUDIT/references/post-processing-rules.md"
  local format="$SPEC_AUDIT/assets/spec-audit-report-format.md"

  grep -qF 'report it under `## Contested Findings`' "$SPEC_AUDIT/SKILL.md"
  grep -qF 'It does not count toward severity totals, dimension scores, preserved-critical caps, or the overall assessment.' "$rules"
  grep -qF 'Leave out every finding marked `**Status:** [Contested]`, whichever selection applies:' "$rules"
  grep -qF 'leaving out contested findings' "$SPEC_AUDIT/SKILL.md"
  grep -qF '## Contested Findings' "$format"
  grep -qF '**Contested:** {count} (not counted above; see Contested Findings)' "$format"
  grep -qF 'follows the Step 4.2 rule for contested findings' "$SPEC_AUDIT/references/product-mode.md"
  grep -qF 'or under `## Contested Findings` for one marked `**Status:** [Contested]`' "$SPEC_AUDIT/references/product-mode.md"
  grep -qF 'Count product findings, except contested ones,' "$SPEC_AUDIT/references/product-mode.md"
  grep -qF 'Keep the carried findings, except those marked `**Status:** [Contested]`,' "$SPEC_AUDIT/references/product-mode.md"
  grep -qF 'Unless contested, they count toward severity totals' "$rules"
}

@test "resolve-review disagreements cite evidence and unrecorded knowledge goes to a person" {
  grep -qF "$REFERENCE_PATH" "$RESOLVE_REVIEW"
  grep -qF 'return `disagreed` with the evidence as the `rationale`' "$RESOLVE_REVIEW"
  grep -qF 'return `blocked-implementation` with a `rationale` that starts `Needs author decision:`' "$RESOLVE_REVIEW"
  grep -qF 'A disagreement cites evidence the reviewer could have read' "skills/pr:resolve-review/references/resolution-output.md"
  grep -qF 'or, with a `rationale` that starts `Needs author decision:`, that it needs a fact only the author can settle' "$RESOLVE_REVIEW"
  grep -qF 'Under `--implement-only`, implement it, because the parent already accepted the change.' "$RESOLVE_REVIEW"
}

@test "github-review-reply stops on the status an escalation returns and asks" {
  local reply="skills/pr:github-review-reply/SKILL.md"

  grep -qF '`blocked-implementation` or `blocked-validation` → keep the item as `needs-code-change`, mark `Implementation status: blocked`, and stop before posting replies.' "$reply"
  grep -qF 'A `blocked-implementation` whose `rationale` starts `Needs author decision:` is a question rather than a failed fix.' "$reply"
  grep -qF 'Do not invoke resolve-review again: its checkpoint would stash those changes' "$reply"
  grep -qF 'Otherwise make the fix yourself with their answer, on top of the first run'"'"'s uncommitted changes.' "$reply"
}

@test "resolve-audit derives every issue's priority from the audit's severity" {
  local template

  grep -qF 'Map it the same way for every finding type: Critical → High, Major → Medium, Minor → Low.' "$RESOLVE_AUDIT"
  grep -qF -- '- Set `Priority` with the Step 3 severity-to-priority rule, whatever the finding type.' "$RESOLVE_AUDIT"
  ! grep -qF 'severity-inheritance' "$RESOLVE_AUDIT"
  for template in skills/siw:resolve-audit/assets/issue-{div-ext,spec,prod}.md.template; do
    grep -qF '**Priority:** {High/Medium/Low — see Step 3 severity-to-priority rule}' "$template"
    grep -qF '**Audit Severity:** {Critical | Major | Minor, as the report states it} {Severity Note copied verbatim from the audit report, if present}' "$template"
    grep -qF "**Resolver's Rating Evidence:**" "$template"
  done
}

@test "resolve-audit accepts an over-rated finding and records its evidence" {
  grep -qF 'if you believe the finding is real but rated too high, accept it. Keep the priority the Step 3 rule derives' "$RESOLVE_AUDIT"
  grep -qF 'Never adjust the result, even when Step 4.0 accepts the finding as over-rated.' "$RESOLVE_AUDIT"
  grep -qF "When Step 4.0 accepted the finding as over-rated, fill \`Resolver's Rating Evidence\` with the evidence from the executive summary." "$RESOLVE_AUDIT"
}

@test "resolve-audit lists escalations first in its final summary" {
  local escalated_line processed_line

  grep -qF 'When any finding was escalated, list the escalations first, before the counts' "$RESOLVE_AUDIT"
  escalated_line=$(grep -nF -- '- Escalated - needs your decision' "$RESOLVE_AUDIT" | cut -d: -f1)
  processed_line=$(grep -nF -- '- Findings processed count' "$RESOLVE_AUDIT" | cut -d: -f1)
  [ "$escalated_line" -lt "$processed_line" ]
}

@test "resolve-review ends every escalation with a recorded outcome and counts disputes" {
  local resolution="skills/pr:resolve-review/references/resolution-output.md"

  grep -qF 'record the outcome as `references/resolution-output.md` § Escalations describes' "$RESOLVE_REVIEW"
  grep -qxF '## Escalations' "$resolution"
  grep -qF 'Record **Escalation:** on the entry and end it with exactly one outcome:' "$resolution"
  grep -qF '**Action taken:** `Skipped — disagreement confirmed by the user.`' "$resolution"
  grep -qF '**The user corrects or does not confirm the fact:** process the finding through the normal path' "$resolution"
  grep -qF '**Action taken:** `Open — escalated; awaiting the user'"'"'s decision.`' "$resolution"
  grep -qF 'The accepted write is an implementation candidate, so Step 2.5 creates its checkpoint' "$resolution"
  grep -qF 'The **Rationale** cites the user'"'"'s decision as its evidence' "$resolution"
  grep -qF 'offer once to write it where later reviewers will see it' "$resolution"
  grep -qF '**Escalation:** [Only for a finding Step 2b escalated' "$resolution"
  grep -qF -- '- Contested and escalated findings: count each, and list every one with a pointer to its evidence.' "$resolution"
}

@test "every resolve-review implement-only path has exactly one defined status" {
  run python3 - "$RESOLVE_REVIEW" "skills/pr:resolve-review/references/resolution-output.md" "skills/pr:github-review-reply/SKILL.md" <<'PY'
import pathlib
import re
import sys

skill, output, reply = [pathlib.Path(path).read_text() for path in sys.argv[1:]]
enum = re.search(r'"status": "(implemented\|[^"]+)"', skill).group(1).split("|")
assert "deferred" in enum, enum
table = output[output.index("## Implement-only statuses"):output.index("## Dependent findings")]
rows = [line for line in table.splitlines() if line.startswith("| ") and not line.startswith(("| Path", "| ---"))]
pairs = []
for row in rows:
    path, status_cell = [cell.strip() for cell in row.strip().strip("|").split("|")]
    statuses = [token for token in re.findall(r"`([a-z-]+)`", status_cell) if token in enum]
    assert len(statuses) == 1, row
    pairs.append((path, statuses[0]))
assert {status for _, status in pairs} == set(enum), (sorted(pairs), sorted(enum))


def status_of(fragment):
    matches = [status for path, status in pairs if fragment in path]
    assert len(matches) == 1, (fragment, matches)
    return matches[0]


assert status_of("Escalated (Step 2b)") == "blocked-implementation"
assert status_of("Contested with evidence") == "disagreed"
assert status_of("A dependency that is missing") == "blocked-implementation"
assert status_of("a comment without a file anchor whose target stays unclear") == "deferred"
reconcile = reply[reply.index("- `implemented` → reclassify"):reply.index("- Record the validation commands and outcomes resolve-review reported.")]
for status in enum:
    assert re.search(rf"`{re.escape(status)}`(?: or `[a-z-]+`)? →", reconcile), f"github-review-reply does not handle {status}"
for field in ['"blocker"', '"decision_needed"', '"recommendation"', '"alternatives"']:
    assert field in skill, f"decision object lost {field}"
assert "Only a `deferred` finding carries `decision`, and every field in it is optional" in skill
assert "Return exactly one entry per payload finding" in skill
assert "an item with no file anchor, such as a review summary or general PR comment, may carry no location, and Step 1's rule for comments without a file anchor finds its target" in skill
assert "only a non-file location the review itself recorded, such as `review-scope` or `PR description`, keeps the route below" in skill
order = re.findall(r"`([a-z-]+)`", re.search(r"in this order: (.*?)\. ", output).group(1))
assert sorted(order) == sorted(enum), order
assert order == ["blocked-validation", "blocked-implementation", "deferred", "disagreed", "skipped-invalid", "skipped-out-of-scope", "implemented", "already-addressed"], order
assert "When the unaddressed asks mix escalations and deferrals and no other ask is blocked, return `deferred` instead" in output
assert "When its `rationale` names an escalated fact, ask them to confirm or correct that fact too" in reply
assert set(re.findall(r"[Rr]eturns? `([a-z-]+)`", skill)) <= set(enum)
assert "Any status other than `implemented` with a non-empty `files_changed`" in reply
assert "leave a comment without a file anchor unlabeled for the rule below" in skill
assert "A payload item that asks for several changes, such as a review summary, still gets one entry. Give it the worst status among its asks" in output
assert "name each ask left unaddressed in `rationale`" in output
assert "Find its target from the comment text and the branch diff against its base" in skill
assert "When its target stays unclear, defer it" in skill
assert "Every finding this step would defer or acknowledge without a change, including an advisory finding stopped by a condition no request path bypasses, returns `deferred`" in skill
PY
  [ "$status" -eq 0 ] || { echo "$output"; false; }
}

@test "resolve-review team-mode agents return one result per finding and the lead re-judges blocked ones" {
  local team="skills/pr:resolve-review/references/team-mode.md"

  grep -qF 'Each resolver agent returns exactly one result per assigned finding:' "$team"
  grep -qF -- '- `outcome`: `implemented`, `already-addressed`, `disagreed`, or `blocked`' "$team"
  grep -qF -- '- `files_changed`: the files the fix changed, or `none`' "$team"
  grep -qF 'Treat a missing or duplicate result as `blocked`.' "$team"
  grep -qF 'Re-judge every `blocked` finding through the standard Step 2 and Step 3 path' "$team"
}

@test "resolve-review parents handle a deferred implement-only result" {
  grep -qF -- '- `deferred` → a decision the fix needs first, not a failed fix. Keep the item as `needs-code-change`' "skills/pr:github-review-reply/SKILL.md"
  grep -qF '| Implementation status | one of `not needed`, `implemented`, `not attempted`, `blocked`, `deferred` |' "skills/pr:github-review-reply/SKILL.md"
  grep -qF 'including `deferred` and its `decision` fields, as evidence for this skill'"'"'s own disposition rather than as one' "skills/pr:review-convergence/references/review-convergence.md"
}
