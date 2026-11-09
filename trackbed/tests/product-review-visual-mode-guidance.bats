#!/usr/bin/env bats

setup() {
  REPO_DIR="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  SKILL="$REPO_DIR/skills/pr:product-review/SKILL.md"
  TEAM_MODE="$REPO_DIR/skills/pr:product-review/references/team-mode.md"
  TEMPLATE="$REPO_DIR/skills/pr:product-review/assets/product-review-report-format.md"
}

@test "product-review confirms a detected URL and asks for one when nothing answers" {
  grep -qF 'In an interactive session, ask the user to confirm it before use, offering to enter another URL or to continue in code-only mode; if non-interactive, use it.' "$SKILL"
  grep -qF "\`__NO_RUNNING_SERVER__\` — in an interactive session, say that no dev server answered and ask the user for this checkout's dev-server URL or to continue in code-only mode; if non-interactive, clear \`app_url\`, warn, and continue in code-only mode." "$SKILL"
  grep -qF 'Accept a URL the user enters only when it starts with `http://` or `https://`.' "$SKILL"
}

@test "product-review labels Mode by browser evidence and names its URL" {
  grep -qF 'end its output with `Browser evidence: yes` when it inspected `app_url` in the browser, or `Browser evidence: no`' "$SKILL"
  grep -qF 'Set `Mode` to `Visual + Code` only when at least one reviewer that completed reports `Browser evidence: yes`; otherwise set `Code-only`, even when an `app_url` was requested.' "$SKILL"
  grep -qF '3. If none found, clear `app_url` and warn:' "$SKILL"
  grep -qF 'or `served from <checkout root>` when the user chose a `__FOREIGN_SERVER__` URL.' "$SKILL"

  local field='**Visual evidence:** {app URL (provided | detected | entered by user[, serving checkout unconfirmed | served from <checkout root>]) | none — reason}'
  grep -qF "$field" "$TEMPLATE"
  grep -qF "$field" "$TEAM_MODE"
  grep -qF "set \`Mode\` and \`Visual evidence\` by the base skill's Step 7 Mode field rule" "$TEAM_MODE"
}
