# Full Backlog Report

Use this workflow for `--all`. Pagination, grading, and reporting each have their own completion check.

## Collect and grade in batches

1. Create a fresh local report directory under `.context/linear-backlog-refine/` if it is gitignored, or under the system temporary directory otherwise. Keep the files local. Record the team and filters in an `index.md` and link the batch files from it.
2. As each page arrives, record the deduplicated matching issue identifiers in the batch files and track which state queries or team-wide queries reached their final page. Record any fetch error with the affected query. Keep the collected identifiers available for reconciliation even if later work stops.
3. Enrich and grade the collected issues in batches that fit the available context. Write each batch's grades, evidence, and the inputs needed for clustering and conflict checks before loading another batch. With `--apply`, also save the state, title, and description used to grade each issue for the Step 11 change check. Load only the relevant records as needed. Cluster and search for conflicts across the entire collected set, including issues in different batch files. Record conflict results and update affected grades before proposing actions.

## Write and verify the report

1. Finalize the report one batch at a time after conflict review. Save every issue's final grade, evidence, proposed action, and any validated drafts or questions. Give each collected issue one final row, including `keep`. Put cross-batch conflicts and aggregate counts in the index or linked files, and retain the identifiers or draft keys behind each count there.
2. Read back the files and reconcile the final rows against the deduplicated collected identifiers. Check that every collected issue has exactly one readable final row and that required evidence and drafts are present. Calculate reported totals from these verified records.
3. Claim full coverage only when all matching pages were exhausted, the cross-batch conflict search is complete, and all collected identifiers reconcile with the saved final rows. If fetching, grading, conflict review, writing, or verification stops early, report partial coverage with the reason and affected scope. Give the counts of collected and verified issues and link any saved results.
4. In chat, give the coverage, action and readiness counts, unresolved conflict counts, and the absolute path to the report index. Keep the detailed rows, drafts, evidence, and conflict identifiers in the files. When handing off to `trackbed:linear:next`, link the unresolved contradictions and say to leave those issues out until the decision is recorded.

For `--apply`, load verified proposals and their saved grading snapshots by action type in the order in Step 11. Split large groups into batches small enough to list every issue at confirmation. Keep per-issue write outcomes with the saved proposals. Step 11 still requires approval for each batch and verification before and after writes.
