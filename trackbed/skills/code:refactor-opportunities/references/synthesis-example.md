# From problems to fixes

Read this before Phase 3 step 8. This fictional seed-library scan shows how to replace several local patches with one fix to their shared cause. Paths, counts, and edit sizes are illustrative, not evidence from the scanned repository.

## Problems collected

- **RO-001 (high):** `loans/checkout.ts:24` allows lending a returned seed packet because it checks total quantity without checking whether inspection passed. Suggested fix: add a pending-inspection check.
- **RO-002 (medium):** `catalog/availability.ts:38` counts returned packets as available before inspection. Suggested fix: subtract the inspection queue.
- **RO-003 (medium):** `returns/accept.ts:51` marks every returned packet available, with an exception for packets needing inspection. Suggested fix: add another status flag.
- **RO-004 (low):** `catalog/label.ts:12` forwards its argument unchanged to the label formatter and has one caller. Suggested fix: inline it.

## Fixes in recommended order

### FIX-1: Model packet readiness in the stock ledger

Availability is calculated differently by checkout, the catalog, and returns. Give the stock ledger responsibility for packet readiness: returned packets enter inspection, and only inspected packets become available. Have checkout and the catalog read availability from that ledger. This removes the need for three separate checks; adding their suggested patches would preserve the disagreement.

- **Findings removed:** RO-001 — checkout lends before inspection; RO-002 — catalog advertises uninspected packets; RO-003 — returns needs an inspection exception.
- **Edit size (lines):** 240, including the ledger, all three callers, and their tests.
- **Automation candidate:** no.
- **Order:** first, because it corrects the shared readiness model and removes the highest-severity problem. Verify that a returned packet stays unavailable until inspection passes.

### FIX-2: Inline the label forwarding function at its only caller

The label helper adds a hop without owning behavior. Inline the formatter call and remove the helper.

- **Findings removed:** RO-004 — a forwarding function with no independent responsibility.
- **Edit size (lines):** 8, including its caller and import.
- **Automation candidate:** no.
- **Order:** independent of the ledger fix; do it second because it has less impact.

The four findings appear once each under two fixes. Their severity rows remain available as reference. The first fix comes from the shared requirement that only inspected packets can be lent, rather than from combining the proposed patches. The independent finding keeps its own entry.
