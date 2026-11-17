# Refactor Opportunities Report

**Project:** {{project}} **Date:** {{date}} **Scope:** {{scope description}} **Files scanned:** {{count}}

## Report Provenance

- **Producer:** trackbed:code:refactor-opportunities ({{mode}})
- **Scope:** {{scope description}}
- **Scanned commit:** {{full git rev-parse HEAD at scan start, or none (not a git repository)}}
- **Working tree:** {{clean / dirty (N paths) / none (not a git repository)}}
- **Base branch:** {{PR scope: base ref and merge-base commit; otherwise none}}
- **Generated:** {{YYYY-MM-DD}}
- **Schema:** breakdown-ready-findings v1

---

## Executive Summary

{{1-3 sentences: overall health, highest-value fixes, recommended starting point; with --for, the refactor that would make the planned change easiest, or that the change needs none}}

{{Nothing worth changing, in every scope: when no finding or deepening candidate survived Phase 3 steps 3-5, or every surviving finding had LOW confidence and no deepening candidate survived, write `Nothing worth changing in <scope>.` in place of the summary above and name which trigger applied. Write "None." in the Fixes and the severity tables, and fill every other section as usual.}}

---

## Fixes

{{Outside PR scope, include: `Special cases: N found; M removed by proposed fixes.` Count distinct cases before filtering and only removals from surviving proposed fixes, including zero counts. Omit this line in PR scope, where category 12 is skipped.}}

{{List fixes in recommended execution order from Phase 3 step 10. Each heading names the coordinated fix, not the problem category. Include every active finding exactly once, including a standalone entry for each ungrouped finding. A fix may differ from the individual suggested fixes when it removes their common cause. For each entry, give its edit size as defined by the Phase 3 Rule of 500 and an explicit automation-candidate mark. Keep dependencies and the reason for this position brief. When nothing is worth changing, write "None." here while retaining the special-case counts outside PR scope. The severity tables below are reference.}}

### 1. {{Fix to make}}

{{Plain statement of what is wrong and how this fix removes the shared cause.}}

- **Findings removed:** {{RO-001 — problem removed; RO-003 — problem removed; …}}
- **Edit size (lines):** {{count, including call sites}}
- **Automation candidate:** {{yes — codemod / AST transform / batch refactor; or no}}
- **Order:** {{why this comes here; prerequisite fix, if any}}

---

{{Severity tables: In Current PR scope only, add a `PR Relevance` column between `Location` and `Description` and populate it for every active finding. In full, path, and feature scopes, omit PR relevance entirely. With --for, add a `Change Relevance` column in the same position instead and populate it for every active finding.}}

## High Severity

| ID     | Category | Location      | Description | Suggested Fix |
| ------ | -------- | ------------- | ----------- | ------------- |
| RO-001 | {{cat}}  | {{file:line}} | {{desc}}    | {{fix}}       |

## Medium Severity

| ID     | Category | Location      | Description | Suggested Fix |
| ------ | -------- | ------------- | ----------- | ------------- |
| RO-001 | {{cat}}  | {{file:line}} | {{desc}}    | {{fix}}       |

## Low Severity

| ID     | Category | Location      | Description | Suggested Fix |
| ------ | -------- | ------------- | ----------- | ------------- |
| RO-001 | {{cat}}  | {{file:line}} | {{desc}}    | {{fix}}       |

---

## Deepening Candidates

{{One block per deepening candidate, strongest evidence first. Write "None found." when the scan produced none. Name each candidate with the project's domain terms.}}

### {{RO-NNN}}: {{candidate name}}

- **Files involved:** {{paths}}
- **Evidence:** {{co-change counts, or the files one ordinary change has to touch}}
- **Proposed interface:** {{what callers would call}}
- **What moves behind it:** {{files, helpers, or caller logic that become implementation}}
- **Tests:** {{tests that move to the new interface; old tests on the shallow pieces that get deleted}}
- **Benefit:** {{locality or leverage gained}}
- **Special cases removed:** {{for special-case candidates only: shared requirement and each exception the proposed fix removes, with file:line; omit for other candidates}}

## State Machines

{{One block per implicit state machine finding (category 11), highest severity first. Outside PR scope, start with one line: `Inventory: N candidates found, M traced, K with a risk.`, using the scan agent's counts from before synthesis filtered any machine out. Write "None found." when no machine is reported below. Name each machine with the project's domain terms. Each machine also has a row in the severity tables and an `RO-NNN` block under Breakdown-Ready Finding Data.}}

### {{RO-NNN}}: {{machine name}} — `{{where its state lives}}`

- **Kind:** {{persisted enum / timestamp combination / flag combination / lease or claim / job or outbox / mirror / client state / …}}
- **States:** {{reachable states; terminal ones marked}}
- **Writers:** {{count}}: {{path:line from → to (guard)}}; …
- **Owner today:** {{none / partial: what / bypassed: owner, n of m writers}}
- **Risks:** {{shape, or the planned change under --for}}: {{path:line evidence}} ({{re-read / not re-read}})
- **Proposed owner:** {{transition table, guard, or reducer}}, following {{exemplar path, or none in the repository}}
- **Tests:** {{transition test; regression tests that fail today}}

## Breakdown-Ready Finding Data

{{One block per `RO-NNN` finding and deepening candidate, in ID order, following the shared breakdown-ready findings schema. Write "None." when there are no active findings. Never include Noticed But Not Touching entries or filtered PR-scope observations.}}

### RO-001: {{title}}

- **Severity:** {{high / medium / low / suggestion}}
- **Confidence:** {{HIGH / MED / LOW}}
- **Locations:** {{path:line or path:start-end; …}}
- **Evidence:** {{one to three sentences of concrete evidence}}
- **Suggested fix:** {{smallest useful first fix}}
- **Effort:** {{S / M / L}}
- **Category:** {{category, or Deepening candidate}}
- **Scope notes:** {{PR scope: PR relevance sentence; with --for: change relevance sentence; omit otherwise}}

## Noticed But Not Touching

{{Observations agents recorded outside their assigned category group, LOW-confidence items set aside by a nothing-worth-changing outcome, and, with --for, findings that would not ease the planned change. Not findings — surface them here so the user can decide whether to request a follow-up scan.}}

## Filtered PR-Scope Observations

{{Only include this section when Scope is Current PR. List observations that were considered but filtered because they were pre-existing, outside the PR relevance gate, or required broad cleanup in untouched files. These are not findings and must not appear in severity totals or Fixes.}}
