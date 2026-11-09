#!/usr/bin/env bats

setup() {
  cd "$BATS_TEST_DIRNAME/.."
  READER="shared/product/references/strategy-reader.md"
  READER_PATH='${CLAUDE_PLUGIN_ROOT}/shared/product/references/strategy-reader.md'
  INIT="skills/siw:init/SKILL.md"
  AUDIT="skills/siw:spec-audit/SKILL.md"
  PRODUCT_MODE="skills/siw:spec-audit/references/product-mode.md"
}

@test "both SIW skills read STRATEGY.md through the shared reader" {
  [ -f "$READER" ]
  grep -qF "read the repository's product strategy as \`$READER_PATH\` describes" "$INIT"
  grep -qF "Its strategy step reads \`STRATEGY.md\` through the shared reader at \`$READER_PATH\`" "$AUDIT"
  grep -qF "Read the repository's product strategy as \`$READER_PATH\` describes" "$PRODUCT_MODE"
  ! grep -qF 'If repo-root `STRATEGY.md` exists, read it' "$PRODUCT_MODE" || false
  ! grep -qF 'when `last_updated` is older than 90 days' "$INIT" || false
}

@test "compound current and legacy headings alias the local headings" {
  grep -qF '| Target problem | Target Problem | Purpose | Target problem |' "$READER"
  grep -qF '| Approach | Approach | Positioning | Our approach |' "$READER"
  grep -qF "| Users | Who It Is For | Users | Who it's for |" "$READER"
  grep -qF '| Key metrics | Key Metrics | Key metrics | Key metrics |' "$READER"
  grep -qF '| Active tracks | Active Tracks | Tracks | Tracks |' "$READER"
  grep -qF '| Non-goals | Non-Goals | Boundaries | Not working on |' "$READER"
  grep -qF 'The same strategy must yield the same users, tracks, metrics, and non-goals whether it uses local, compound current, compound legacy, or no recognized headings.' "$READER"
}

@test "hand-written files are read by meaning, not by exact heading" {
  grep -qF 'a topic is present when the file states it anywhere, under any heading or in running prose' "$READER"
  grep -qF 'Report a topic as missing only when the file states it nowhere' "$READER"
}

@test "a file without last_updated is dated from a stated or commit date before it is called current" {
  grep -qF '1. `last_updated` in YAML frontmatter, when it holds a valid date.' "$READER"
  grep -qF '2. A date the file states for the whole document' "$READER"
  grep -qF '3. The date of the last commit that touched the file, from `git log -1 --format=%cs -- "<path>"`.' "$READER"
  grep -qF 'Never present context of unknown age as current, and never mark it stale.' "$READER"
  grep -qF 'Date `STRATEGY.md`, a linked document, and each fallback file separately.' "$READER"
  grep -qF '**Age:** for each file read, its date and its marker' "$READER"
  grep -qF 'Skip this step in a shallow clone, where `git rev-parse --is-shallow-repository` prints `true`' "$READER"
  grep -qF 'Keep every marker and label in this result (`STALE:`, `AGE UNKNOWN:`, `not read (<path>)`, and each linked or fallback source label) in anything written from it.' "$READER"
  grep -qF 'keeps every marker and label the strategy reader returns' "$INIT"
  grep -qF 'Keep every marker and label the strategy reader returns in the report.' "$PRODUCT_MODE"
  [ "$(grep -cF 'Keep every marker and label the strategy reader returns.' skills/siw:init/assets/spec-templates.md)" -eq 3 ]
  grep -qF 'and every marker and label the strategy reader returns}' skills/siw:spec-audit/assets/spec-audit-report-format.md
}

@test "pointer lines and fallback documents stay labeled and local" {
  grep -qF 'it is a regular file inside the repository with no symlink on its path. Never fetch a URL or read a path outside the repository.' "$READER"
  grep -qF 'When the two disagree, `STRATEGY.md` wins.' "$READER"
  grep -qF 'Follow one level only' "$READER"
  grep -qF 'read a root `PRODUCT.md` or `VISION.md` as fallback context' "$READER"
  grep -qF 'label every fact taken from it with its source file' "$READER"
  grep -qF 'Label each fact taken from it with its source file' "$READER"
  grep -qF 'When only fallback files were read, the consuming skill still treats `STRATEGY.md` as missing and names the fallback file it read.' "$READER"
  grep -qF 'If no `STRATEGY.md` exists and the work is broad product-direction work, include `MISSING PRODUCT CONTEXT: no STRATEGY.md found`' "$INIT"
  [ "$(grep -cF 'If no `STRATEGY.md` exists and the work is broad product-direction work: `MISSING PRODUCT CONTEXT: no STRATEGY.md found`, naming any fallback file read' skills/siw:init/assets/spec-templates.md)" -eq 3 ]
  grep -qF 'report the topics the pointer covers as `not read (<path>)` instead of `missing`' "$READER"
}

@test "the 90-day staleness threshold is unchanged" {
  grep -qF 'Mark context from a file `STALE:` when that file'"'"'s date is more than 90 days old.' "$READER"
}

@test "both consuming skills credit the compound strategy references" {
  grep -qF 'id: compound-ce-strategy-references' "skills/siw:init/references/sources.yaml"
  grep -qF 'id: compound-ce-strategy-references' "skills/siw:spec-audit/references/sources.yaml"
}
