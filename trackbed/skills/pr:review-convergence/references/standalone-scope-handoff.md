# Standalone Scope Handoff

Read `{archive-validation-reference}` completely and invoke `{archive-scope-validator}` under that contract before trusting the archive. Use its returned classification, provenance, branch and scope facts; do not restate their proof rules here.

## Review Lifecycle

Require plan/index status agreement. In normal review, accept `IN_PROGRESS`; for a legacy checkpoint, accept `TODO` or `READY`, or `BLOCKED` only when `DETACHED_GENERATED_PLAN=true` and named blockers exist. Require exactly one complete `## Workflow State` at `IMPLEMENTED` or `QUALITY_BLOCKED` and no `## Execution Result`. A detached generated plan's caller has already proven blockers before the executor-owned transition; do not rerun intake readiness during review.

In validation-only review, retain the caller's terminal lifecycle and require its complete workflow checkpoint as Step 2 specifies. The runtime boundary verifies standalone source integrity for both nonterminal and terminal lifecycle sections; the caller still proves checkpoint, base, branch, committed paths and publication identity.

Apply the shared migration rule only in normal mode; validation-only never writes archive metadata. Preserve `RECHECK_STANDALONE_SCOPE` and the shared exact-or-containment membership rule through remediation and publication.
