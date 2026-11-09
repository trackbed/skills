# Success Report

Use these templates during Phase 5 after the SIW documents have been created.

Display summary:

```
Structured Implementation Workflow Initialized

Created:
  siw/{spec_filename}          - Main specification (permanent)
  siw/supporting-specs/        - Detailed specifications (permanent) [if enabled]
  siw/LOG.md                   - Progress and decisions (temporary)
  siw/OPEN_ISSUES_OVERVIEW.md  - Issue tracking (temporary)
  siw/issues/                  - Individual issue files (temporary)

Artifact readiness: {product-only|requirements-only|planning-ready} - {one-line reason}
Strategy: {used|flagged stale|missing} - {source files read, or "no STRATEGY.md or fallback file"}
  Unresolved conflicts: {each entry in strategy_conflicts | none}
  {If strategy_status is missing and the work is broad product-direction work:}
  Run /trackbed:product:strategy to create STRATEGY.md for later SIW runs

Next Steps:
  {If product-only or requirements-only:}
  1. Run /trackbed:discovery:interview --siw to harden the spec before phase or issue creation

  {If planning-ready:}
  1. Run /trackbed:siw:generate-phases to create the initial issue set (a single issue when the spec is one coherent change)
  2. Run /trackbed:siw:transfer-to-linear after reviewing the issue set

Tips:
  - Until transfer, the spec file is permanent; keep it updated as the local source of truth
  - siw/LOG.md and siw/issues are temporary preparation artifacts
  - After a verified transfer, update requirements in Linear and use /trackbed:workflow:cleanup-artifacts --siw to retire the local SIW files
```

**If external files were linked, also show:**

```
Linked Specifications:
  {If managed by another spec tool:}
  - {file} (managed by {owner})
  {owner} keeps owning this file's format and location. Leave it in place and never copy it into siw/. The SIW spec links to its path. siw:transfer-to-linear does not migrate the file and reports its path as an unresolved local reference.

  {If kept in place and owner is none:}
  - {file1} (external)
  - {file2} (external)
  Until captured for transfer, these files remain the local source of truth. The SIW spec references them.
  Before transfer, capture every authoritative linked source that no spec tool manages:
    - Copy Markdown specs into siw/supporting-specs/ and update the SIW links.
    - Copy non-Markdown sources under siw/ so transfer can require relocation or upload before cleanup.
  If any of these sources cannot be captured, stop and keep the local SIW source of truth.
  Treat Linear as authoritative only after transfer verifies the disposition of each of these sources.

  {If moved to siw/:}
  - siw/{file1} (moved)
  - siw/{file2} (moved)
  Files were moved into siw/ for co-location.
```

**If content was discovered via interview, also show:**

```
Discovery:
  Spec populated from discovery interview.
  {n} key decisions documented.
  {n} open questions to address during implementation.
```

**If supporting specs enabled, also show:**

```
Supporting Specs:
  - Create files in siw/supporting-specs/ with naming: NN-descriptor.md
  - Example: 01-data-model.md, 02-api-specification.md
  - Update the TOC in the main spec when adding new supporting specs
```
