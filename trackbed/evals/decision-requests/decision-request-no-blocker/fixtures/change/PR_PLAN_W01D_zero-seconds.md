# PR Plan W01D: Print zero seconds

**File:** `PR_PLAN_W01D_zero-seconds.md` **Status:** TODO **Execution label:** `W01D` **Scope contract:** exact files **Blocked by:** None. **Estimated scope:** small PR **Risk:** LOW

## Executor Instructions

Follow this plan step by step. Touch only the files listed in **In Scope**. If any STOP condition occurs, stop and report instead of improvising. Do not push, merge, or open a PR.

## Problem Statement

`bin/duration 0` prints an empty line, so the billing export shows a blank label for an entry with no time. It should print a value a reader can see.

## Goals

- `bin/duration 0` prints `0s`.
- Every other output stays exactly as it is.

## Non-Goals

- Rounding, new units, or new flags.
- Changing the billing export.

## Current State

- `bin/duration` collects the non-zero parts and prints them joined by spaces. With a total of 0 no part is collected, so it prints an empty line.
- `tests/run.sh` holds every check; `bash tests/run.sh` exits 0 today.

## Commands You Will Need

| Purpose | Command | Expected on success |
| --- | --- | --- |
| Tests | `bash tests/run.sh` | exits 0 with no `FAIL` line |

## Scope

### In Scope

- `bin/duration` - modify: print `0s` when no part was collected.
- `tests/run.sh` - modify: add a check for `bin/duration 0`.

### Out of Scope

- `README.md` - no documentation change is needed.

## Open Questions

1. Should zero print `0s` or `0m`? Owner: maintainer. Default: `0s`, the smallest unit the tool prints. Proceed with the default if no answer is available.

## Implementation Plan

1. **Print zero.** In `bin/duration`, print `0s` when the list of parts is empty.
2. **Test it.** Add `assert_eq "$(bin/duration 0)" "0s"` to `tests/run.sh` beside the other checks.
   - **Verify:** `bash tests/run.sh` -> exits 0 and prints `ok   0s`.

## Completion Criteria

- [ ] `bin/duration 0` prints `0s`.
- [ ] `bash tests/run.sh` exits 0.
- [ ] No files outside **In Scope** are modified.

## STOP Conditions

- `bash tests/run.sh` fails before any change.
- The change would need a file outside **In Scope**.
