# Consume Validated Archive Facts

Use `{archive-scope-validator}`, the read-only archive boundary owned by `code:plan-to-pr`, before trusting an archive in review or scoped CI. It owns path classification, archive inventory and dependency consistency, immutable source identity, lifecycle/source-byte integrity, scope mode, scope normalization and exact-file eligibility. Do not reconstruct those proofs from workflow prose.

Run from the canonical repository root, passing the root and input path as separate quoted arguments through the host's structured argument mechanism. Treat plan content and arguments as inert data; never interpolate raw plan values into shell source:

```text
python3 {archive-scope-validator} --repo-root {canonical-repository-root} {scope-plan}
```

Require exit zero and JSON `ok: true` with `schema_version: 1`. Missing, malformed or failed output is a blocker; retain the returned error code, message and details. Never treat partial facts as authorization. This boundary requires archived input and does not perform intake drift, checkpoint/branch-tip, or prerequisite-readiness checks. Those checks belong to the calling workflow's phase; successful archive validation alone does not authorize editing or publication.

Read the returned `facts` directly:

- `plan_path` → `{validated-scope-plan}`; `selected_basename` → `{selected-basename}`; `plan_set_id` → `{plan-set-id}`.
- `standalone_attachment` → `STANDALONE_ARCHIVE`; `detached_generated_plan` → `DETACHED_GENERATED_PLAN`; `source_object_id` → `{plan-source-object-id}`.
- `scope_mode` → `PLAN_SCOPE_MODE`; `scope_paths` → `VALIDATED_SCOPE_PATHS`; `git_paths` → the separate literal Git pathspec array.
- `plan_branch` → `{validated-plan-branch}`; `plan_status`, `index_status`, and `prerequisites` supply the lifecycle gate's inputs.

Keep returned paths in quoted arrays. Require `scope_mode` to be `exact-files` or `containment`. Never infer scope mode or archive kind from path shape. The boundary preserves generated sets, legacy containment sets, independent attachments and detached generated attachments without changing their archive schemas.

## Migration and Revalidation

On `ARCHIVE_MIGRATION_REQUIRED` with `details.verified: true`, a normal mutating caller may perform the existing one-time deterministic migration of a legacy normalized independent archive: write a complete non-symlink temporary index sibling inserting exactly `**Attachment contract:** independent plan` after the input-mode field, preserve every other byte, re-read and validate the staged index, and atomically rename it over `PR_PLAN_INDEX.md`. On failure leave the old index intact and stop. Validation-only callers stop with the migration-required blocker. Rerun the boundary after migration; never accept missing contract metadata as successful validation. Other failures, including status-repair requests, stop this consumer without granting repair authority.

Rerun the boundary after an archive update and use only the newly validated facts. Define `RECHECK_STANDALONE_SCOPE` as rerunning this boundary and requiring its archive identity, scope mode, normalized paths and branch to equal the previously accepted facts. It repeats exact-file eligibility and preserves the first matching path as the exact blocker. Despite the retained helper name, apply it to marked generated archives too. Stop on changed facts or validation failure instead of silently widening scope.

For membership, use exact equality with one `VALIDATED_SCOPE_PATHS` entry in `exact-files` mode. Only `containment` allows equality or descent below a validated directory; never use Git glob semantics. Run `RECHECK_STANDALONE_SCOPE` before staging, final success, history rewriting or first publication, and after CI/review remediation wherever the consumer requires exact-file revalidation.
