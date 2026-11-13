# PR Plan W01B: Handle long durations

**File:** `PR_PLAN_W01B_long-durations.md` **Status:** TODO **Execution label:** `W01B` **Scope contract:** exact files **Blocked by:** None. **Estimated scope:** small PR **Risk:** LOW

## Executor Instructions

Follow this plan step by step. Touch only the files listed in **In Scope**. If any STOP condition occurs, stop and report instead of improvising. Do not push, merge, or open a PR.

## Problem Statement

Support exports time logged on long-running tickets, and `bin/duration` prints those totals in hours only: `bin/duration 90000` prints `25h`. Support also found entries of several years, which came from a timer nobody stopped, printed as if they were real work. This PR settles how long durations print and what happens to impossible ones.

## Goals

- Long durations print in the unit support agreed on.
- Impossible totals are handled the way support agreed on.

## Non-Goals

- Changing how durations under a day print.
- Changing the billing export.

## Current State

- `bin/duration` splits the total into hours, minutes, and seconds; hours have no upper limit.
- `tests/run.sh` holds every check; `bash tests/run.sh` exits 0 today.

## Commands You Will Need

| Purpose | Command | Expected on success |
| --- | --- | --- |
| Tests | `bash tests/run.sh` | exits 0 with no `FAIL` line |

## Scope

### In Scope

- `bin/duration` - modify: add the day unit and the upper limit.
- `tests/run.sh` - modify: add checks for both.

### Out of Scope

- `README.md` - documentation follows in a later PR.

## Open Questions

1. MISSING REQUIREMENT: Should 90000 seconds print `1d 1h` or stay `25h`? Support agents asked for days; the billing team reads hours and would have to convert. Owner: support lead. No default.
2. MISSING REQUIREMENT: What should `bin/duration` do with a total above one year (31536000 seconds)? It could exit with an error, so the export flags the entry, or print the total as usual and leave cleanup to support. Owner: billing team. No default. This is independent of question 1.

## Implementation Plan

1. **Add the day unit** as Open Question 1 decides.
2. **Add the upper limit** as Open Question 2 decides.
3. **Test both** in `tests/run.sh`.
   - **Verify:** `bash tests/run.sh` -> exits 0.

## Completion Criteria

- [ ] `bin/duration 90000` prints what support chose.
- [ ] A total above one year is handled the way the billing team chose.
- [ ] `bash tests/run.sh` exits 0.
- [ ] No files outside **In Scope** are modified.

## STOP Conditions

- An open question marked `MISSING REQUIREMENT` has no answer.
- The change would need a file outside **In Scope**.
