#!/usr/bin/env bats

setup() {
  cd "$BATS_TEST_DIRNAME/.."
  SKILL="skills/siw:spec-audit/SKILL.md"
  DIMENSIONS="skills/siw:spec-audit/references/dimension-instructions.md"
  CLAIMS_PROMPT="skills/siw:spec-audit/references/claims-check-prompt.md"
  AUDIT_PROMPT="skills/siw:spec-audit/references/audit-agent-prompt.md"
  TEAM="skills/siw:spec-audit/references/team-mode.md"
  AGENT="agents/codebase-pattern-reviewer.md"
}

@test "the claims check tests what exists today, not whether code implements the spec" {
  grep -qF 'This is not an implementation audit' "$AGENT"
  grep -qF 'Do not perform an implementation audit.' "$AGENT"
  grep -qF '**Contradicts the code**: the spec describes current behavior the code does not have. Report as **Critical**.' "$AGENT"
  grep -qF 'Report this once as **Major**, not once per path.' "$AGENT"
  grep -qF 'Anything the plan proposes to create is not a finding' "$AGENT"
  grep -qF '### CLAIM-NNN:' "$AGENT"
}

@test "standard mode runs only the claims part, and only when the spec names existing code" {
  grep -qF '| Current-State References |' "$SKILL"
  grep -qF 'record `skipped (spec names no existing code)`' "$SKILL"
  grep -qF 'Run only the Current-State Claims check from your instructions and skip the pattern review.' "$CLAIMS_PROMPT"
  grep -qF '**Dimension**: Technical Design' "$CLAIMS_PROMPT"
  grep -qF '**Source**: Current-State Claims' "$CLAIMS_PROMPT"
  grep -qF '{fix-confidence rubric path}' "$CLAIMS_PROMPT"
}

@test "claims the reviewer could not verify stay visible in the report" {
  grep -qF 'including any claims the reviewer could not verify' "$SKILL"
  grep -qF 'checked, {N} unverified: {the claims}' "skills/siw:spec-audit/assets/spec-audit-report-format.md"
  grep -qF 'Current-state claims you could not verify' "$AGENT"
}

@test "team mode widens the pattern reviewer to both checks" {
  grep -qF 'whether what it says' "$TEAM"
  grep -qF 'Current-State Claims for a `CLAIM-NNN` finding' "$TEAM"
  grep -qF 'Keep current-state claim findings.' "$TEAM"
}

@test "actionability flags design decisions left to the implementer" {
  grep -qF '**Decisions left to the implementer.**' "$DIMENSIONS"
  grep -qF 'Mechanical choices with one defensible answer, such as a local variable name, are not findings.' "$DIMENSIONS"
  grep -qF 'File paths belong to the file-boundary check, not to this exemption.' "$DIMENSIONS"
  ! grep -qiF 'such as a file name' "$DIMENSIONS"
}

@test "actionability requires a file boundary of full repository paths" {
  grep -qF '**File boundary.** When the spec has implementation tasks, does it list every file to be added, changed, or removed by its full repository path' "$DIMENSIONS"
  grep -qF 'A folder pattern is acceptable only for generated files whose names are not known in advance.' "$DIMENSIONS"
  grep -F -- '- Major:' "$DIMENSIONS" | grep -qF 'a missing or open-ended file list'
  grep -F -- '- Minor:' "$DIMENSIONS" | grep -qF 'one file path the spec implies but does not write'
}

@test "the scope check names one remedy and a severity for each flagged caveat" {
  grep -qF 'recommend one remedy: **delete** it when the spec establishes no risk it guards against, **rescale** it when it overstates an established risk, or **move** it' "$DIMENSIONS"
  grep -qF 'A caveat at the right strength and in the right place is not a finding.' "$DIMENSIONS"
  grep -F -- '- Minor:' "$DIMENSIONS" | grep -qF 'a caveat to rescale or move, a caveat to delete that adds no requirement or mechanism'
}

@test "a remedy that would undo an accepted fix becomes a choice citing both findings" {
  grep -qF 'When the only remedy for a Scope finding would undo the fix for a finding in the `Previously Resolved Findings` block, do not recommend removing that fix.' "$DIMENSIONS"
  grep -qF 'Cite both finding IDs and write the recommendation as a choice' "$DIMENSIONS"
}

@test "a re-audit checks what earlier fixes added without reopening settled decisions" {
  grep -qF '**Defensive accretion.**' "$DIMENSIONS"
  grep -qF 'Do not reopen a decision the spec records as settled.' "$DIMENSIONS"
  grep -qF '## Previously Resolved Findings' "$AUDIT_PROMPT"
  grep -qF 'fill the group that audits Scope with its Previously Resolved Findings block' "$SKILL"
  grep -qF 'add the Previously Resolved Findings block' "$TEAM"
}

@test "only findings that were really addressed count as previously resolved" {
  grep -qF 'carrying an `Existing issue:` note for an issue that is `DONE` in `siw/OPEN_ISSUES_OVERVIEW.md`' "$SKILL"
  grep -qF 'If a listed gap still exists, report it as usual.' "$AUDIT_PROMPT"
  ! grep -qF 'Do not re-raise the findings themselves' "$AUDIT_PROMPT"
}

@test "team mode waits for the comprehension reply" {
  grep -qF 'Start the cross-reviewer only after the reply is back or the read has failed.' "$TEAM"
  grep -qF '{Collected findings from all 4 dimension auditors, the codebase pattern reviewer, and the comprehension read}' "$TEAM"
  grep -qF '1. Collect all findings from dimension auditors, the codebase pattern reviewer, the comprehension read, and the cross-reviewer' "$TEAM"
}

@test "a contested finding stays settled across re-audits until its evidence changes" {
  grep -qF 'A finding that matches one marked `**Status:** [Contested]` in the previous report stays settled unless the spec text or the cited evidence has changed' "$SKILL"
}

@test "technical design asks about failure signals, rollback, and running cost only for runtime changes" {
  grep -qF '**Failure signals, rollback, and running cost.** When the spec adds a runtime path, stored data, or a paid or rate-limited dependency' "$DIMENSIONS"
  grep -qF 'how a half-finished migration or rollout is undone and what happens to data written in between' "$DIMENSIONS"
  grep -qF 'including quotas and LLM token spend' "$DIMENSIONS"
  grep -qF 'A docs-only or refactor-only change gets no finding here.' "$DIMENSIONS"
  grep -F -- '- Major:' "$DIMENSIONS" | grep -qF 'a change to stored data with no way back'
  grep -F -- '- Minor:' "$DIMENSIONS" | grep -qF 'a missing failure signal or running-cost estimate'
  grep -qF 'id: egm-brainstorm-lenses' "skills/siw:spec-audit/references/sources.yaml"
}

@test "product mode reads compound pulse reports from the configured docs root" {
  PRODUCT_MODE="skills/siw:spec-audit/references/product-mode.md"
  grep -qF 'Read `docs_root` from `<repo-root>/.compound-engineering/config.yaml` only; never from `config.local.yaml`. When the file or key is absent, `<root>` is `docs`.' "$PRODUCT_MODE"
  grep -qF 'A set value is valid only when it uses only letters, digits, `.`, `_`, `-`, and `/`, checked before the value reaches any command' "$PRODUCT_MODE"
  grep -qF 'For an invalid value, read no reports and record `MISSING PRODUCT CONTEXT: pulse reports (invalid docs_root)`.' "$PRODUCT_MODE"
  grep -qF 'Look only in `<root>/pulse-reports/`.' "$PRODUCT_MODE"
  ! grep -qF 'If `docs/pulse-reports/` exists' "$PRODUCT_MODE" || false
}

@test "product mode picks the newest pulse reports by filename and dates each one" {
  PRODUCT_MODE="skills/siw:spec-audit/references/product-mode.md"
  grep -qF 'whose names match `YYYY-MM-DD_HH-MM.md`, and ignore every other file and subfolder' "$PRODUCT_MODE"
  grep -qF 'Sort the names in descending order and read the newest three, or all of them when fewer exist.' "$PRODUCT_MODE"
  grep -qF 'Never order reports by file modification time.' "$PRODUCT_MODE"
  grep -qF 'The covered period is the window in its title line, `# <product> Pulse - <window> - <timestamp>`' "$PRODUCT_MODE"
  grep -qF 'Label every pulse signal as `<filename> (<window>)`, such as `2026-11-02_09-30.md (7d)`' "$PRODUCT_MODE"
  grep -qF 'the filename shows the report date and time.' "$PRODUCT_MODE"
  grep -qF 'each cited as `<filename> (<window>)`, which shows its report date and period' "skills/siw:spec-audit/references/product-element-extraction.md"
  grep -qF 'for each report used, its label as `<filename> (<window>)`, whose filename shows the report date and time' "skills/siw:spec-audit/assets/spec-audit-report-format.md"
}

@test "product mode reads only compound's pulse sections and keeps figures neutral" {
  PRODUCT_MODE="skills/siw:spec-audit/references/product-mode.md"
  PROMPT="skills/siw:spec-audit/references/product-reviewer-prompt.md"
  grep -qF 'Compound writes Headlines, Usage, System performance, and Followups' "$PRODUCT_MODE"
  ! grep -rqiF 'customer-signal' skills/siw:spec-audit || false
  ! grep -rqiF 'customer signals' skills/siw:spec-audit || false
  grep -qF 'Pulse figures carry no verdicts' "$PROMPT"
  grep -qF 'must quote the figure and cite its report as `<filename> (<window>)`' "$PROMPT"
}
