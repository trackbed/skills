#!/usr/bin/env bats

@test "pr product review keeps routing contracts without embedded usage or agent summaries" {
  local skill_text
  local team_text
  skill_text="$(cat "$BATS_TEST_DIRNAME/../skills/pr:product-review/SKILL.md")"

  [[ "$skill_text" == *'argument-hint: "[--subagent-model <model>] [app-url|auto] [--categories a11y,ux,product,visual]'* ]] || false
  [[ "$skill_text" == *'If `--categories` flag → parse comma-separated list.'* ]] || false
  [[ "$skill_text" == *'If `--categories product,visual` → launch trackbed:product-reviewer and trackbed:visual-reviewer'* ]] || false
  [[ "$skill_text" == *'If `--categories all` → launch all 4 agents'* ]] || false
  [[ "$skill_text" == *'The `product` category audits every file in `CHANGED_FILES`'* ]] || false
  [[ "$skill_text" == *'continue with the product reviewer alone'* ]] || false
  [[ "$skill_text" == *'If `--categories` also excludes `product`, stop instead:'* ]] || false
  [[ "$skill_text" == *'the reviewer brief from `references/product-lens.md`, verbatim'* ]] || false
  team_text="$(cat "$BATS_TEST_DIRNAME/../skills/pr:product-review/references/team-mode.md")"
  [[ "$team_text" == *'continue with the product reviewer alone, or stop with the same message as the base skill when `--categories` also excludes `product`'* ]] || false
  [[ "$team_text" == *'keep the full changed-file list as the product reviewer'* ]] || false
  [[ "$team_text" == *'For the product reviewer, the reviewer brief from `references/product-lens.md`, verbatim'* ]] || false
  [[ "$skill_text" != *'## Usage Examples'* ]] || false
  [[ "$skill_text" != *'## Agent Descriptions'* ]] || false
  [[ "$skill_text" != *'/trackbed:pr:product-review http://localhost:4200'* ]] || false
}
