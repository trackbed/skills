---
name: trackbed:siw:init
description: Initialize structured implementation workflow documents in siw/ (spec, LOG.md, issues)
argument-hint: "[spec-file(s) | folder | discover] [--auto]"
disable-model-invocation: true
user-invocable: true
---

# Initialize Structured Implementation Workflow

Set up the three-document system for preparing complex specifications and initial issue sets locally before one-way transfer to Linear.

## Workflow Boundaries

**This command ONLY initializes workflow documents.**

- **DOES**: Create siw/ folder, spec file, siw/LOG.md, siw/OPEN_ISSUES_OVERVIEW.md, siw/issues/, and optionally siw/supporting-specs/
- **DOES NOT**: Define issues, implement features, or make code changes

**Issue definition is a separate workflow.** After this command completes, recommend the next skill that the artifact readiness result names in Phase 5: `$trackbed:siw:generate-phases` only for a `planning-ready` spec, which plans a single issue when the spec describes one coherent change, and `$trackbed:discovery:interview --siw` for a `product-only` or `requirements-only` spec. **Spec hardening is a separate workflow.** To strengthen an existing SIW spec, use `$trackbed:discovery:interview --siw`.

### Artifact Readiness Contract

Use this shared vocabulary in setup summaries and handoffs:

- `product-only`: the source explains the problem, user, or desired outcome but still lacks testable scope or success criteria.
- `requirements-only`: scope and success criteria exist, but the spec lacks enough technical context, dependencies, or planning detail to create issue slices. Phase boundaries are not required; `$trackbed:siw:generate-phases` creates them.
- `planning-ready`: the SIW spec is concrete enough for `$trackbed:siw:generate-phases`.
- `implementation-ready`: an issue file has executable scope, dependencies, acceptance criteria, and verification. This skill never produces implementation-ready artifacts.

`siw:init` creates the tracked planning container. It may preserve a `product-only` or `requirements-only` source as context, or produce a `planning-ready` SIW spec when the imported/discovered content is concrete enough; it must not imply implementation is ready until issues exist.

## Process Overview

```
$trackbed:siw:init [spec-file(s) | folder | discover]
    ↓
[Check for existing files] -> Found? -> Ask: resume or start fresh
    ↓
[Handle arguments] -> file/folder: import content
                   -> discover: run greenfield discovery, then import siw/DISCOVERY_BRIEF.md
                   -> empty: continue to brief interview
    ↓
[Brief interview OR Confirm imported content]
    ↓
[Read product strategy (shared reader)]
    ↓
[Select work context] -> Profile for downstream tool adaptation
    ↓
[Auto-detect spec type] -> Confirm filename
    ↓
[Ask about supporting specs] -> Need detailed specs?
    ↓
[Create documents] -> siw/spec, siw/LOG.md, siw/issues/, (supporting-specs/)
    ↓
[Report success] -> Suggest next readiness-gated skill
```

Before Phase 1, parse `$ARGUMENTS` as shell-style arguments. If `--auto` is present, set `AUTO_MODE=true` and remove it from the remaining input. `--auto` uses safe initialization defaults when enough context is already supplied: keep linked files in place, use all discovered files from an explicit folder, choose the auto-detected work context and spec filename, and create a single spec file without supporting specs. It does not bypass required project context, existing-workflow protection, deletion confirmation, file overwrite checks, or fresh discovery topic requirements.

## Phase 1: Check for Existing Workflow Files

Check if any workflow files already exist:

```bash
find siw -maxdepth 1 \( \
  -name "LOG.md" -o \
  -name "OPEN_ISSUES_OVERVIEW.md" -o \
  -name "AUDIT_IMPLEMENTATION_REPORT.md" -o \
  -name "AUDIT_SPEC_REPORT.md" -o \
  -name "PRODUCT_AUDIT.md" -o \
  -name "SIW_*.md" -o \
  -name "SPEC_STRENGTHENING_PLAN.md" -o \
  -name "DISCOVERY_BRIEF.md" -o \
  -name "issues" \
  \) -print 2> /dev/null
# Permanent SIW spec detection (referenced as `permanent-spec find` elsewhere in this skill).
# Case-insensitive so lowercase/mixed-case filenames like `feature_spec.md` are not missed.
# Synced SIW spec-exclusion contract (keep aligned across SIW spec detectors): `LOG.md`, `OPEN_ISSUES_OVERVIEW.md`, `DISCOVERY_BRIEF.md`, `SPEC_STRENGTHENING_PLAN.md`, `AUDIT_*.md`, `PRODUCT_AUDIT.md`, `SIW_*.md`.
find siw -maxdepth 1 -type f \( -iname "*SPEC*.md" -o -iname "*SPECIFICATION*.md" -o -iname "*PLAN*.md" -o -iname "*DESIGN*.md" \) \
  ! -iname "LOG.md" \
  ! -iname "OPEN_ISSUES_OVERVIEW.md" \
  ! -iname "DISCOVERY_BRIEF.md" \
  ! -iname "SPEC_STRENGTHENING_PLAN.md" \
  ! -iname "AUDIT_*.md" \
  ! -iname "PRODUCT_AUDIT.md" \
  ! -iname "SIW_*.md" \
  2> /dev/null
```

Read `references/existing-workflow-handling.md` and follow the first matching branch for `siw/DISCOVERY_BRIEF.md` only, `siw/DISCOVERY_BRIEF.md` + `siw/SPEC_STRENGTHENING_PLAN.md`, `siw/SPEC_STRENGTHENING_PLAN.md` only, other workflow files, or no files.

## Phase 1.5: Handle Arguments

Read `references/argument-handling.md` and follow the matching case for file paths, folder paths, `discover` / `interview`, or no arguments. This phase sets `linked_spec_files`, `linked_spec_readiness_context`, `discovered_content`, `project_description`, or `resolved_arguments` for later phases.

## Phase 2: Brief Interview

**Skip this phase if Phase 1.5 set `linked_spec_files` or `discovered_content`.**

If `AUTO_MODE=true` and Phase 2 would run, stop before asking with `MISSING REQUIREMENT: project context required for --auto; pass a spec file, folder, discovery brief, or use discover <topic>`.

Read the Phase 2 templates from `references/interviews.md`, use them to gather project context, urgency and outcome, scope boundaries, and decision boundaries, then store the responses as `project_description`, `why_now`, `out_of_scope_non_goals`, and `decision_boundaries_notes`.

## Phase 2.5: Confirm Linked Sources

**Only executed if `linked_spec_files` exists from Phase 1.5 (file/folder import).**

**Skip this phase if `discovered_content` exists (discover mode already has confirmation built in).**

Show the files that will be linked:

```
Linked Specification Files:
───────────────────────────

The following files will be referenced (not duplicated) in the SIW spec:

1. {file1} - "{title from first heading}"
2. {file2} - "{title from first heading}"
...

These files remain the source of truth. The SIW spec will link to them.
```

Before choosing a location, record each linked file's owner in `linked_spec_owners`. A file is tool-managed when its path or content shows that another specification system owns it, for example OpenSpec (`openspec/`), GitHub Spec Kit (`specs/NNN-feature/` in a repository whose root has `.specify/`), or Kiro (`.kiro/specs/`); record that tool as the owner. Otherwise record `none`. That tool keeps owning the file's format and location, so always keep a tool-managed file in place: never move or copy it into `siw/`, and offer the location question only for files whose owner is `none`.

If `AUTO_MODE=true`, choose **Keep in place**. Otherwise read the Phase 2.5 file-location template from `references/interviews.md` and ask the user directly in chat.

For both **"Move to siw/"** and **"Copy to siw/"**, before transferring each file, check the target path with `[ -e "siw/{filename}" ]`. If a file already exists at the target, read the Phase 2.5 collision template from `references/interviews.md` and ask the user directly in chat before overwriting.

Apply the user's choice per file, then:

- **"Keep in place"**: Store paths as-is in `linked_spec_files`, continue to Phase 2.6
- **"Move to siw/"**:
  - Move each file to `siw/{filename}` (or the renamed/skipped path per the collision prompt above)
  - Update `linked_spec_files` with the resulting paths
  - Continue to Phase 2.6
- **"Copy to siw/"**:
  - Warn: "This creates duplicate files. Consider using 'Keep in place' to maintain a single source of truth."
  - If user confirms, copy files to `siw/` (or the renamed/skipped path per the collision prompt above)
  - Update `linked_spec_files` with the resulting paths
  - Continue to Phase 2.6

## Phase 2.6: Confirm Project Context

**Only executed if `linked_spec_files` exists.**

If `AUTO_MODE=true`, use the inferred default value. Otherwise read the Phase 2.6 project-context template from `references/interviews.md` and ask the user directly in chat.

Store the response as `project_description`.

If user provides empty response or selects "Skip", use a generic description derived from the linked file names.

## Phase 2.8: Work Context Selection

Before selecting the work context, read the repository's product strategy as `${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.0.1/shared/product/references/strategy-reader.md` describes. When it returns context, including fallback `PRODUCT.md` or `VISION.md` context, store a concise `strategy_context` that keeps every marker and label the strategy reader returns. Apply one strategy rule in every spec template and the success report:

- **Flag stale strategy.** Keep each `STALE:` marker with the context it dates.
- **Record conflicts.** Store each unresolved conflict between this work and an active track or non-goal in `strategy_conflicts`, and record it as an open question in the spec instead of resolving it silently. Conflicts never block initialization.

Set `strategy_status` to `used` when `STRATEGY.md` was read and none of its context is `STALE:`, `flagged stale` when any of it is, or `missing` when no `STRATEGY.md` exists, even if fallback context was read. If no `STRATEGY.md` exists and the work is broad product-direction work, include `MISSING PRODUCT CONTEXT: no STRATEGY.md found` in the generated spec's strategy context note, name any fallback file read, and suggest `$trackbed:product:strategy` in the success report. For narrow work with no strategy or fallback context, add nothing to the spec.

Select a work context profile that tells downstream tools (spec-audit, product-review, discovery, generate-phases) how to adapt their rigor and focus.

Read the profile definitions and auto-detection heuristics from `references/work-context-profiles.md`.

Based on `project_description` or `discovered_content` topic, use the keyword heuristics from the reference file to suggest a profile. If `AUTO_MODE=true`, choose the auto-detected profile; otherwise read the Phase 2.8 work-context template from `references/interviews.md`, deduplicate options as documented there, and ask the user directly in chat.

Store the selected profile as `work_context_profile` with all attribute values from the reference file (work_type, maturity, priority_dimensions, deprioritized, notes).

## Phase 3: Auto-detect Spec Type and Confirm

Use the Phase 3 filename detection heuristics in `references/interviews.md` to auto-detect the most appropriate spec filename. If `AUTO_MODE=true`, choose it automatically. Otherwise read the Phase 3 specification-document template from `references/interviews.md` and ask the user directly in chat; if "Custom name" is selected, ask the user directly in chat to get the filename.

Store as `spec_filename`.

## Phase 3.5: Ask About Supporting Specs

If `AUTO_MODE=true`, choose **No - single spec file is enough**. Otherwise read the Phase 3.5 supporting-specifications template from `references/interviews.md` and ask the user directly in chat.

Store as `use_supporting_specs`.

## Phase 4: Create Documents

Read `references/document-creation.md`, apply its readiness classification procedure, and follow it to create `siw/`, `siw/{spec_filename}`, `siw/LOG.md`, `siw/OPEN_ISSUES_OVERVIEW.md`, `siw/issues/`, and optional `siw/supporting-specs/`.

When `strategy_context` exists, include a concise `## Product Strategy Context` section in the generated SIW spec using the relevant placeholders from `assets/spec-templates.md`. Keep it to strategy facts and, in templates without an Open Questions section, the open questions that record conflicts; do not duplicate the entire `STRATEGY.md`.

## Phase 5: Report Success

Read the Phase 5 success-report templates from `references/success-report.md`, display the applicable summary sections, then stop.

Include one readiness line and one strategy line in the success report:

```
Artifact readiness: <product-only|requirements-only|planning-ready> — <one-line reason and next skill>
Strategy: <used|flagged stale|missing> — <source files read>
  Unresolved conflicts: <each conflict|none>
```

If the result is `product-only` or `requirements-only`, point to `$trackbed:discovery:interview --siw` before phase or issue creation. If it is `planning-ready`, point to `$trackbed:siw:generate-phases` (which plans one issue for one coherent change), then `$trackbed:siw:transfer-to-linear`.

**STOP HERE.** Wait for the user's next instruction.

## Important Guidelines

1. **Link, don't duplicate** - When external specs are provided, reference them; never copy their content into the SIW spec (single source of truth)
2. **Smart input handling** - Accept file paths, folders, or "discover" keyword; fall back to brief interview if no arguments
3. **Offer file relocation** - Ask if linked files should be moved into siw/ or kept in place; under `--auto`, keep them in place. Never relocate a spec that another spec tool manages
4. **Delegate discovery** - In discover mode, `$trackbed:discovery:interview --siw` runs the interview; do not repeat it here
5. **Smart defaults** - Auto-detect spec type and confirm it, except under `--auto`, which uses the detected type
6. **Clear next steps** - Always point user to the next skill implied by readiness: discovery for hardening or generate-phases for issue planning
7. **Respect existing work** - Never overwrite without explicit confirmation
