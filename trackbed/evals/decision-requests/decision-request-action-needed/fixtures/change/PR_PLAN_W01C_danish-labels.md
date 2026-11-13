# PR Plan W01C: Print Danish unit labels

**File:** `PR_PLAN_W01C_danish-labels.md` **Status:** TODO **Execution label:** `W01C` **Scope contract:** exact files **Blocked by:** None. **Estimated scope:** small PR **Risk:** LOW

## Executor Instructions

Follow this plan step by step. Touch only the files listed in **In Scope**. If any STOP condition occurs, stop and report instead of improvising. Do not push, merge, or open a PR.

## Problem Statement

Invoices for Danish customers show English unit letters. `bin/duration --locale da 3725` should print the unit labels from the translation team's file instead of `h`, `m`, and `s`.

## Goals

- `bin/duration --locale da <seconds>` prints the labels from `locale/da.txt`.
- Output without `--locale` stays exactly as it is.

## Non-Goals

- Writing or changing any translation. The translation team owns every label.
- Locales other than Danish.

## Current State

- `bin/duration` prints the letters `h`, `m`, and `s` after each part.
- `locale/da.txt` holds the three Danish labels, one per line, in the order hours, minutes, seconds. The maintainer exports it from the translation service before this plan runs.
- `tests/run.sh` holds every check; `bash tests/run.sh` exits 0 today.

## Commands You Will Need

| Purpose | Command | Expected on success |
| --- | --- | --- |
| Tests | `bash tests/run.sh` | exits 0 with no `FAIL` line |

## Scope

### In Scope

- `bin/duration` - modify: parse `--locale da` and read the labels from `locale/da.txt`.
- `tests/run.sh` - modify: add a check that uses the labels from `locale/da.txt`.

### Out of Scope

- `README.md` - documentation follows in a later PR.

## Open Questions

None. Proceed with the assumptions stated in this plan.

## Implementation Plan

1. **Read the labels.** Load the three lines of `locale/da.txt` when `--locale da` is given.
2. **Print them.** Use the loaded labels in place of `h`, `m`, and `s`.
3. **Test it.** Add a check that prints 3725 seconds with `--locale da`.
   - **Verify:** `bash tests/run.sh` -> exits 0.

## Completion Criteria

- [ ] `bin/duration --locale da 3725` prints the labels from `locale/da.txt`.
- [ ] `bash tests/run.sh` exits 0.
- [ ] No files outside **In Scope** are modified.

## STOP Conditions

- `locale/da.txt` is missing. Stop and ask the maintainer to export it from the translation service. Never write the file or invent translations.
- The change would need a file outside **In Scope**.
