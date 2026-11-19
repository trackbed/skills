# Deprecation decision checklist

Extended guidance for the five-question checklist in Step 1 of the skill. Each question has: what a clear answer looks like, signals that mean "not yet — gather more data", and an escalation path when the answer is unknown.

Assumes the surface (compile-time / internal-only, runtime / internal, or external / public) has already been classified per SKILL.md > "Choose the surface first". Each question below picks evidence sources that match that surface.

---

## 1. Does this code still provide unique value?

**Clear YES** — callers still need a capability that no existing or committed replacement is meant to provide, and removing the code would remove user-facing or developer-facing functionality.

**Clear NO** — a replacement already covers the same surface or is committed to cover it, and the old code persists only until callers move to it. Question 3 decides whether the replacement still has to be built.

**"Not yet — gather more data" signals:**

- You can name the replacement but haven't verified it covers edge cases (error handling, null inputs, specific formats).
- Two modules do overlapping work but each covers cases the other misses.
- The code is branded "legacy" but the team can't agree on what replaces it.

**Outcome:** a clear YES means keep and maintain the code. Record `Outcome: Keep and maintain` with a revisit trigger and stop; this is neither a deprecation nor a feature deletion. A clear NO continues to question 3.

**Escalation when unknown:** read the tests. Tests are the documented contract — if the tests only exist for the old code, the replacement probably doesn't cover parity yet.

---

## 2. Who are the dependents (internal + external)?

**Clear answer** — a list of concrete callers from the evidence sources required by the chosen surface:

1. **Compile-time / internal-only** — import graph / build graph, tests or fixtures that still exercise the old path, and config / package / publish references.
2. **Runtime / internal** — import graph / build graph plus access logs, analytics, or telemetry covering the last meaningful window.
3. **External / public** — runtime telemetry plus external docs, SDK publishing, and partner integrations. If the code is behind a public API, the external caller list matters more than the internal import graph.

If more than one surface applies, use the stricter evidence set.

**"Not yet — gather more data" signals:**

- Grep alone, with no corroborating import/build/test/config evidence.
- Runtime deprecation with no access logs or telemetry.
- Public API deprecation with no SDK/docs/partner inventory check.
- "Nobody I asked uses it" — surveyed teams, not data.
- Access logs show "low usage" but the sampling window is under 30 days.
- Dynamic imports or reflection is used in the codebase and the grep couldn't resolve them.

**Escalation when unknown:** emit `UNVERIFIED: <missing-data-source>` and gather it. If runtime logs don't exist, instrument first — add a counter on the old path and let it run for a rollback window before trusting "zero usage". If compile-time evidence is ambiguous, add a temporary build/test guard or consumer check before trusting "zero references".

---

## 3. Does a replacement exist?

**Clear YES** — you can name the replacement module/endpoint/feature, and its contract covers the documented surface of the old code.

**Committed, not built** — name it. Step 4.1 (Build the replacement) builds and verifies it _before_ any announcement, and that work counts toward the question 4 migration effort.

**Clear NO** — no replacement exists or is committed. Removing the code is "delete the feature" — a different decision with a different stakeholder set; tell the user, delete the plan, and stop.

**"Not yet — gather more data" signals:**

- A replacement exists but covers the happy path only — edge cases still use the old module.
- "We'll build the replacement as part of the deprecation PR" — pushes Step 4.1 work into Step 4.4, a common cause of rollback.

**Escalation when unknown:** do not start announcements before the replacement is merged and verified; runtime or public replacements must also be deployed before announcement.

---

## 4. What is the migration cost for dependents?

**Clear answer** — choose the migration boundary first, then estimate each dependent inside it:

- **Persisted data or schema contract** — use Database Expand/Migrate/Contract regardless of whether dependent work is Low, Medium, or High. Do not route database evolution through the framework/library-only `trackbed:code:migrate` workflow.
- **Framework or library version migration** — use `trackbed:code:migrate`, then return here to retire the old surface.
- **Other boundaries, Low** — single-line change, codemod-able, takes a caller under an hour. Expect Adapter pattern with a codemod.
- **Other boundaries, Medium** — multi-line or multi-file refactor per caller. Expect Adapter or Feature Flag with batched migration PRs.
- **Other boundaries, High** — long-lived service-boundary or ownership changes use Strangler.

**"Not yet — gather more data" signals:**

- Estimate is a guess, not based on looking at 1–2 real caller sites.
- Migration pattern has not been picked (Step 3 skipped).
- "It depends" answers that don't tier the dependents.

**Escalation when unknown:** pick one representative caller and migrate it by hand before estimating. The real cost is visible after one real migration; theoretical cost is not.

---

## 5. What is the maintenance cost of NOT deprecating?

**Clear answer** — a concrete list of costs:

- Security patch obligations (dependency CVEs, base image updates).
- Framework upgrades that require touching this code.
- Test suite maintenance (flakes, slow tests, environmental coupling).
- Onboarding time for new contributors encountering the module.
- Cognitive overhead in code review when adjacent code is modified.
- Platform compatibility (Node major bumps, Python EOL).

A short list makes a Defer outcome likely in the weighing step below; if migration still wins, expect Advisory classification and a long window. A long or growing list means the deprecation has a clock — Compulsory classification when a specific forcing function is named.

**"Not yet — gather more data" signals:**

- "It's fine" — not enumerated.
- List exists but no item has a concrete forcing event (date, CVE, version bump).
- The list is growing across multiple evaluations but no deprecation is being planned.

**Escalation when unknown:** log the list in the deprecation plan. Under a Defer outcome, a growing list is a revisit trigger; under an Advisory deprecation, it is the signal to escalate to Compulsory.

---

## Weigh migration against keeping

Run the weighing in SKILL.md Step 1: question 4's total migration effort, plus any replacement build from question 3, against question 5's cost of keeping the old code over the same horizon. When keeping is cheaper, record `Outcome: Defer` with a revisit trigger and stop before any announcement; otherwise record `Outcome: Deprecate`.

**"Not yet — gather more data" signals:** either side is an unenumerated guess, or the two sides cover different horizons.

---

## Decision tree

```
Q1: Still provides unique value?
 ├─ YES → Keep and maintain; record revisit trigger; stop
 └─ NO
     ▼
Q3: Replacement exists?
 ├─ NO, but committed → build it in Step 4.1 before any announcement; continue
 ├─ NO, none committed → "delete the feature" is a different decision; delete the plan; stop
 └─ YES
     ▼
Q2: Dependents audited from the required sources for the surface?
 ├─ NO  → UNVERIFIED; gather data
 └─ YES
     ▼
Zombie-code gate: owner identified?
 ├─ NO  → ASK FIRST; establish owner
 └─ YES
     ▼
Q4 (migration effort) vs Q5 (cost of keeping): keeping cheaper?
 ├─ YES → Defer; record revisit trigger; stop
 └─ NO  → Deprecate: pick pattern and classification
     ▼
Proceed to Step 4 (build replacement → announce → migrate → remove).
```

If any answer is `UNVERIFIED` at the point the decision tree asks for it, stop and resolve the gap. Proceeding with an unverified answer is the most common source of "the deprecation broke production".
