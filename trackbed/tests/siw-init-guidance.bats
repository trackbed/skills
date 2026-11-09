#!/usr/bin/env bats

setup() {
  cd "$BATS_TEST_DIRNAME/.."
  INIT="skills/siw:init/SKILL.md"
  TEMPLATES="skills/siw:init/assets/spec-templates.md"
  REPORT="skills/siw:init/references/success-report.md"
  PHASES="skills/siw:generate-phases/SKILL.md"
}

@test "every spec template applies the same stale-strategy and conflict rule" {
  rule='Flag stale strategy by keeping each `STALE:` marker with the context it dates. Record each unresolved conflict in `strategy_conflicts` as an open question instead of resolving it silently:'
  [ "$(grep -cF "$rule" "$TEMPLATES")" -eq 3 ]
  [ "$(grep -cF 'this template has no Open Questions section, so list each one at the end of this section as `Open question: {conflict}`.' "$TEMPLATES")" -eq 2 ]
  grep -qF 'add each one to `## Open Questions`.' "$TEMPLATES"
  grep -qF '{Add each unresolved strategy conflict from `strategy_conflicts`.}' "$TEMPLATES"
  ! grep -qF 'Include strategy conflicts as open questions rather than resolving them silently.' "$TEMPLATES" || false
}

@test "the success report shows strategy status and unresolved conflicts" {
  grep -qF 'Strategy: <used|flagged stale|missing>' "$INIT"
  grep -qF 'Strategy: {used|flagged stale|missing}' "$REPORT"
  grep -qF 'Unresolved conflicts: {each entry in strategy_conflicts | none}' "$REPORT"
  grep -qF 'Run /trackbed:product:strategy to create STRATEGY.md' "$REPORT"
  grep -qF 'Set `strategy_status` to `used`' "$INIT"
  grep -qF '`missing` when no `STRATEGY.md` exists, even if fallback context was read' "$INIT"
  grep -qF '  Unresolved conflicts: <each conflict|none>' "$INIT"
  grep -qF '{If strategy_status is missing and the work is broad product-direction work:}' "$REPORT"
}

@test "generate-phases is recommended only for planning-ready specs" {
  ! grep -qF 'recommend that the user run `/trackbed:siw:generate-phases`' "$INIT" || false
  grep -qF '`/trackbed:siw:generate-phases` only for a `planning-ready` spec' "$INIT"
  grep -qF 'Once the spec is planning-ready, use /trackbed:siw:generate-phases' "$TEMPLATES"
}

@test "the brief-interview skip condition names only variables Phase 1.5 sets" {
  ! grep -qF 'imported_spec_content' "$INIT" || false
  grep -qF 'This phase sets `linked_spec_files`, `linked_spec_readiness_context`, `discovered_content`' "$INIT"
  grep -qF '**Skip this phase if Phase 1.5 set `linked_spec_files` or `discovered_content`.**' "$INIT"
}

@test "specs managed by another spec tool stay in place with a recorded owner" {
  grep -qF 'record each linked file'"'"'s owner in `linked_spec_owners`' "$INIT"
  grep -qF 'never move or copy it into `siw/`' "$INIT"
  grep -qF 'offer the location question only for files whose owner is `none`' "$INIT"
  grep -qF '{owning spec tool from `linked_spec_owners`, or "None"}' "$TEMPLATES"
  grep -qF 'never copy it into siw/' "$REPORT"
  grep -qF 'Before transfer, capture every authoritative linked source that no spec tool manages:' "$REPORT"
}

@test "siw:init and siw:generate-phases define requirements-only the same way" {
  definition='scope and success criteria exist, but the spec lacks enough technical context, dependencies, or planning detail to create issue slices.'
  grep -qF -- "- \`requirements-only\`: $definition" "$INIT"
  grep -qF -- "- \`requirements-only\`: $definition" "$PHASES"
  ! grep -qF 'still lacks phase boundaries' "$INIT" || false
}
