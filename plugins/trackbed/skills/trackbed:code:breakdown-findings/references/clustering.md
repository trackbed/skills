# Clustering rules and process

Load this during Phase 2 for findings-mode input. For a pre-clustered handoff, use only the dependency graph, execution-label, and `PLAN:` mapping guidance; do not split or merge themes. Handoff validity and oversized-theme confirmation are handled in `SKILL.md` before Phase 3.

## Rules

1. **Target size**: each theme should map to a realistic single PR (roughly 1-8 findings, touching a bounded set of files). If a theme grows beyond what a single PR can cover, split it into a short series and note the dependency. Size every theme with **Size themes** in `${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.0.1/shared/findings/references/findings-intake.md`; any theme that sizes XL MUST split before generating plans.
2. **Avoid overlap**: every finding belongs to exactly one theme. If a finding could fit multiple themes, assign it to the one where it shares the strongest implementation dependency.
3. **Singleton themes are fine**: if a finding does not cluster with others, it becomes its own single-finding theme.
4. **Exclusions**: if any finding should be excluded from all plans (e.g., duplicates, already resolved, not actionable), record it with a reason. These go into the index under "Excluded or Included Scope" as one marker-prefixed line per finding. If nothing is excluded, write a plain sentence with no marker.
5. **Conflicts**: if two findings contradict each other (e.g., "add abstraction" vs. "remove abstraction" for the same code), flag the conflict as an open question in the relevant plan(s) and do not assume a resolution.
6. **Controls land with or before the capabilities they limit**: when one theme adds or widens access to a capability, such as an endpoint, command, tool, or job, and another theme adds the control that limits it, such as an authorization check, a rate or spending limit, input validation, or an audit record, the control theme blocks the capability theme. If the control can only be built into the new capability itself, rule 8 would also make the capability theme block the control theme, so put both findings in one theme instead of creating a dependency cycle. As the alternative to that dependency, the capability theme ships the capability disabled, or, for an authorization check, limited to callers that check would admit, and states that restriction in its steps and completion criteria. The capability theme then blocks the control theme, which lifts the restriction: the restricting file belongs in the control theme's In Scope, and its completion criteria prove the capability works with the control in place.
7. **Deferred controls keep the surface restricted**: when a control-type finding is excluded, deferred, or recorded in `PR_PLAN_REJECTIONS.md` instead of planned, and another theme widens access to the same surface, that theme keeps the surface restricted as rule 6 describes and states that restriction in its steps and completion criteria. If that restriction would defeat the theme's purpose, the plan instead carries a `MISSING REQUIREMENT:` naming the deferred control and a STOP condition that blocks widening access until the control exists. Never let a plan widen access on the assumption that a deferred control will land later.
8. **Single introducer for each new shared artifact**: every new shared artifact, such as a type, endpoint, schema migration, config key, or feature flag, that two or more themes use is introduced by exactly one theme, and every other theme that uses it is blocked by the introducer. Check the artifact itself, because two themes can rely on the same new artifact without sharing a file.
9. **Prioritization metadata**: every theme must receive a normalized Impact and Leverage value. Use the highest confirmed impact among included findings, then adjust leverage by effort, fix risk, confidence, dependency value, and whether the theme unblocks later work. If the value is inferred, prefix it with `UNVERIFIED:`.

## Process

1. Read all findings. Identify natural groupings by scanning for shared files, shared root causes, and shared fix patterns.
2. Draft theme names using the pattern `verb-noun` in kebab-case (e.g., `add-api-error-handling`, `consolidate-config-parsing`, `remove-dead-code`).
3. Build a dependency graph across themes before naming files:
   - A dependency exists when a theme cannot start until another theme lands, or when landing one theme materially reduces risk for another.
   - A blocker exists when a theme must land before one or more downstream themes.
   - Themes with no direct or transitive dependency between them are parallel candidates.
   - Add every dependency that rules 6 and 8 require, even when the themes share no files. For a pre-clustered handoff, stop for a corrected handoff when its declared dependencies omit or contradict one of these, instead of reordering its themes.
   - If dependency direction is unclear, add an open question and choose the most conservative ordering.
4. Assign impact/leverage values and use them to order independent themes within each wave:
   - Put dependency blockers first.
   - Among independent same-wave themes, prefer higher leverage, then higher impact, then lower risk/effort.
   - Do not let leverage ordering override a real dependency.
5. Assign every theme an execution label before generating files, following **Assign execution labels** in the shared findings intake reference. Name the exact blocker labels of a later-wave plan in the plan title, index, and summary.
6. Keep the theme slug separate from the execution label: derive `{SLUG}` from the theme name only, then prefix it with `{EXECUTION_LABEL}` only in the final filename. Example: execution label `W01A` plus theme slug `define-error-types` becomes `PR_PLAN_W01A_DEFINE_ERROR_TYPES.md`.
7. Verify no theme is too large (touches 9+ files per the shared sizing grammar). Split if needed.
8. Verify no two themes overlap in affected files without an explicit dependency note.

## User confirmation block

Present the clustering to the user before generating files. Prefix the block with the `PLAN:` output marker so downstream tooling can parse the proposed clustering:

```text
PLAN: Proposed themes
  Wave W01 (parallel):
    W01A add-api-error-handling (4 findings, size M, impact HIGH, leverage HIGH) -- blocks W02A -- files: src/api/*.ts
    W01B remove-dead-exports (2 findings, size S, impact LOW, leverage MED) -- independent -- files: src/lib/*.ts
  Wave W02:
    W02A consolidate-config-parsing (3 findings, size S, impact MED, leverage HIGH) -- blocked by W01A -- files: src/config/*, src/utils/config.ts
  0 excluded findings

Proceed? (yes / adjust)
```

Wait for user confirmation. If the user requests adjustments, re-cluster accordingly.

If `AUTO_MODE=true`, do not ask for confirmation. Print the same `PLAN:` block, add `AUTO: proceeding with the proposed clustering`, and continue directly to Phase 3. Still stop before Phase 3 if the plan contains an unresolved contradiction that would make the generated plan misleading rather than merely conservative.
