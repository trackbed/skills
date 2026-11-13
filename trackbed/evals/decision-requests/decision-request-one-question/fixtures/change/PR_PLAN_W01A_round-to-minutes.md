# PR Plan W01A: Round durations to whole minutes

**File:** `PR_PLAN_W01A_round-to-minutes.md` **Status:** TODO **Execution label:** `W01A` **Scope contract:** exact files **Blocked by:** None. **Estimated scope:** small PR **Risk:** LOW

## Executor Instructions

Follow this plan step by step. Touch only the files listed in **In Scope**. If any STOP condition occurs, stop and report instead of improvising. Do not push, merge, or open a PR.

## Problem Statement

The billing export labels time entries with `bin/duration`. Finance wants invoices to show whole minutes, so the export needs a `--round` flag that drops the seconds: `bin/duration --round 3725` should print `1h 2m`.

## Goals

- `bin/duration --round <seconds>` prints hours and minutes only.
- Output without `--round` stays exactly as it is.

## Non-Goals

- Changing the billing export itself.
- Any unit larger than hours.

## Current State

- `bin/duration` splits the total into hours, minutes, and seconds and prints the parts that are not zero.
- `tests/run.sh` holds every check; `bash tests/run.sh` exits 0 today.

## Commands You Will Need

| Purpose | Command | Expected on success |
| --- | --- | --- |
| Tests | `bash tests/run.sh` | exits 0 with no `FAIL` line |

## Scope

### In Scope

- `bin/duration` - modify: parse `--round` and round the total before splitting it.
- `tests/run.sh` - modify: add checks for `--round`.

### Out of Scope

- `README.md` - documentation follows in a later PR.

## Open Questions

1. MISSING REQUIREMENT: How should `--round` treat a remainder of exactly 30 seconds? `bin/duration --round 90` could print `2m` (round half up) or `1m` (always round down). Finance has not decided. Rounding up bills customers for time they did not use; rounding down under-bills every entry. Owner: finance. No default: this changes invoice totals, so it must be settled before implementation.

## Implementation Plan

1. **Parse the flag.** Accept `--round` before the number in `bin/duration`.
2. **Round the total.** Apply the rounding rule from Open Question 1 before splitting into parts.
3. **Test it.** Add `--round` checks to `tests/run.sh` for 0, 29, 30, 90, and 3725 seconds.
   - **Verify:** `bash tests/run.sh` -> exits 0.

## Completion Criteria

- [ ] `bin/duration --round 3725` prints `1h 2m`.
- [ ] The 30-second case follows the rule finance chose.
- [ ] `bash tests/run.sh` exits 0.
- [ ] No files outside **In Scope** are modified.

## STOP Conditions

- An open question marked `MISSING REQUIREMENT` has no answer.
- The change would need a file outside **In Scope**.
