#!/usr/bin/env bats

@test "pr code review exposes resolver readiness contract" {
  local skill_text
  local template_text
  local discipline_text
  local team_text
  local relevance_validator_text
  local emphasis_line
  local normalization_line

  skill_text="$(cat "$BATS_TEST_DIRNAME/../skills/pr:code-review/SKILL.md")"
  template_text="$(cat "$BATS_TEST_DIRNAME/../skills/pr:code-review/references/output-template.md")"
  discipline_text="$(cat "$BATS_TEST_DIRNAME/../skills/pr:code-review/references/review-discipline.md")"
  team_text="$(cat "$BATS_TEST_DIRNAME/../skills/pr:code-review/references/team-mode.md")"
  relevance_validator_text="$(cat "$BATS_TEST_DIRNAME/../agents/pr-relevance-validator.md")"

  [[ "$skill_text" == *"After emphasis adjustments, run an **action-class normalization pass**."* ]] || false
  [[ "$discipline_text" == *"default to \`gated_auto\` with owner \`resolver\`"* ]] || false
  [[ "$discipline_text" == *"Every manual Critical/Important finding includes \`Manual blocker\` and \`Next human decision\`"* ]] || false
  [[ "$skill_text" == *"**Auto-resolution Readiness**"* ]] || false
  [[ "$discipline_text" == *"Label every finding produced by this check with \`OVERENGINEERING\`"* ]] || false
  [[ "$discipline_text" == *"Treat findings labeled \`OVERENGINEERING\` by any reviewer the same way."* ]] || false
  [[ "$discipline_text" == *"Overengineering findings default to Suggestion with action class \`advisory\`."* ]] || false
  [[ "$skill_text" == *"Treat validator output as classifications over the original finding records, not replacement findings."* ]] || false
  [[ "$skill_text" == *"Treat meta-review output as annotations over the original finding records."* ]] || false
  [[ "$discipline_text" == *"**MISSING REQUIREMENT**"* ]] || false
  emphasis_line="$(grep -nF "Track the count of promoted findings for the report." <<<"$skill_text" | cut -d: -f1)"
  normalization_line="$(grep -nF "After emphasis adjustments, run an **action-class normalization pass**." <<<"$skill_text" | cut -d: -f1)"
  [ "$normalization_line" -gt "$emphasis_line" ]

  [[ "$template_text" == *"## Auto-resolution Readiness"* ]] || false
  [[ "$template_text" == *'Review producer: trackbed:pr:code-review'* ]] || false
  [[ "$template_text" == *"Manual blockers: product/UX/architecture/maintainer decision X"* ]] || false
  [[ "$template_text" == *"Manual blocker: product/UX/architecture/maintainer decision"* ]] || false
  [[ "$template_text" == *"Next human decision: concrete decision"* ]] || false

  [[ "$discipline_text" == *"Critical or Important PR-caused findings default to \`gated_auto\`"* ]] || false
  [[ "$discipline_text" == *"**OVERENGINEERING** — the finding comes from the Overengineering Check"* ]] || false
  [[ "$discipline_text" == *"Every finding produced by the Overengineering Check is labeled \`OVERENGINEERING\`"* ]] || false
  [[ "$skill_text" == *'apply the `Confidence and merge rules` and `Correctness and security precedence` sections'* ]] || false
  [[ "$skill_text" == *'including its `Deletion dependencies` check, before emphasis'* ]] || false
  [[ "$skill_text" == *"Replace every deletion dependency's provisional finding identity with its final \`CR-XXX\` ID"* ]] || false
  [[ "$skill_text" == *'resolution status, `Depends on` when present, action taken, and evidence'* ]] || false
  [[ "$skill_text" == *'Resolve a carried `Depends on` source ID to the retained current deletion finding'* ]] || false
  [[ "$skill_text" == *'If the referenced deletion finding was dropped, remove the dependency and revalidate the cleanup'* ]] || false
  [[ "$skill_text" != *"Instruct every reviewer to return these fields for each finding"* ]] || false
  [[ "$skill_text" != *"Manual blocker: <one of the blocker categories above>"* ]] || false

  [[ "$team_text" == *'do not reconstruct or abbreviate them here'* ]] || false
  [[ "$team_text" == *'exact shared `collect-review-diff.sh` collection flow'* ]] || false
  [[ "$team_text" != *'`collect-review-diff.sh` JSON flow'* ]] || false
  [[ "$team_text" == *'Apply the `Confidence and merge rules` section'* ]] || false
  [[ "$team_text" == *'Apply the `Correctness and security precedence` section'* ]] || false
  [[ "$team_text" == *'including its `Deletion dependencies` check'* ]] || false
  [[ "$team_text" == *'reconcile cleanup-collision blocker references and deletion-dependency identities'* ]] || false
  [[ "$team_text" == *'Apply the `Action classes`, `Severity and action-class compatibility`, and `Manual blocker tests` sections'* ]] || false
  [[ "$team_text" == *'Use `references/output-template.md` and the `Finding schema` and `Severity prefix grammar` sections'* ]] || false
  [[ "$team_text" != *"Each teammate must also apply this **Codebase Calibration Rule**"* ]] || false
  [[ "$team_text" != *"Critical/Important PR-caused findings default to \`gated_auto\`"* ]] || false
  [[ "$team_text" != *"Label every finding produced by this check with \`OVERENGINEERING\`"* ]] || false
  [[ "$team_text" == *"Treat meta-review output as annotations over the original finding records."* ]] || false
  [[ "$team_text" == *"Treat validator output as classifications over the original finding records, not replacement findings."* ]] || false

  [[ "$relevance_validator_text" == *"Return classifications over the original finding records, not abbreviated replacement findings."* ]] || false
  [[ "$relevance_validator_text" == *"Return every raw finding field and standalone marker unchanged"* ]] || false

  [[ "$discipline_text" == *'every cleanup-dimension finding (`lean`, `refactor`, `simplify`, and any finding marked `OVERENGINEERING`)'* ]] || false
  [[ "$discipline_text" == *'retain the cleanup as a separate advisory finding'* ]] || false
  [[ "$discipline_text" == *'activate after dependency is addressed'* ]] || false
  [[ "$discipline_text" == *'activate if dependency is not addressed after processing'* ]] || false
  [[ "$discipline_text" == *'An open dependency excluded by the current severity filter is unprocessed and leaves the cleanup unchanged.'* ]] || false
  [[ "$discipline_text" == *'the dependency itself does not count as the unresolved Critical/Important finding that blocks the advisory'* ]] || false
  [[ "$template_text" == *'Depends on: CR-NNN — activate after dependency is addressed'* ]] || false
  [[ "$template_text" == *'Depends on: CR-NNN — activate if dependency is not addressed after processing'* ]] || false
}
