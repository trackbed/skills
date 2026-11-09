#!/usr/bin/env bats

load 'test_helper/common'

setup() {
  cd "$BATS_TEST_DIRNAME/.."
}

COMMIT_MESSAGE="skills/git:commit-message/SKILL.md"
HARDEN_SECURITY="skills/code:harden-security/SKILL.md"

secret_scan_command() {
  sed -n '/^git diff --cached -i -G /p' "$1"
}

@test "commit-message routes drafting for pasted diffs and names the checks it skips" {
  local description drafting
  description="$(sed -n 's/^description: //p' "$COMMIT_MESSAGE")"
  drafting="$(sed -n '/^## Drafting only$/,/^## /p' "$COMMIT_MESSAGE")"

  grep -qF "drafting a message for a pasted diff or change summary" <<<"$description"
  grep -qF "Skip the Prerequisites branch check" <<<"$drafting"
  grep -qF "verification, the secret scan, the stray-file check, and the working-state check" <<<"$drafting"
  grep -qF "Still apply the format, the commit convention, the body guidelines, and the AI-attribution rules" <<<"$drafting"
  grep -qF "Never paste a credential you notice in the pasted diff back into the message or your reply" <<<"$drafting"
}

@test "commit-message checklist requires a names-only secret scan and a stray-file check" {
  local checklist
  checklist="$(sed -n '/^## Pre-commit checklist$/,/^## Body Guidelines$/p' "$COMMIT_MESSAGE")"

  grep -qF "confirm all seven:" <<<"$checklist"
  [ "$(grep -c '^- \[ \] ' <<<"$checklist")" -eq 7 ]
  grep -qF "**No credentials staged.**" <<<"$checklist"
  grep -qF "**No stray files staged.**" <<<"$checklist"
  grep -qF "Settle each listed path before committing" <<<"$checklist"
  grep -qF "without echoing credentials into terminal or agent logs" <<<"$checklist"
  grep -qF "Never print, quote, or repeat a matched value" <<<"$checklist"
  grep -qF "A nonzero exit is a failed check, not a clean scan." <<<"$checklist"
  grep -qF "Build output" <<<"$checklist"
  grep -qF "Dependency directories" <<<"$checklist"
  grep -qF "Local env files" <<<"$checklist"
  grep -qF "private key files" <<<"$checklist"
  grep -qF "Personal editor and OS settings" <<<"$checklist"
  grep -qF "A generated file is allowed only when the project already versions it" <<<"$checklist"
}

@test "commit-message and harden-security run the same names-only secret scan" {
  local commit_scan harden_scan
  commit_scan="$(secret_scan_command "$COMMIT_MESSAGE")"
  harden_scan="$(secret_scan_command "$HARDEN_SECURITY")"

  [ -n "$commit_scan" ]
  [ "$commit_scan" = "$harden_scan" ]
}
