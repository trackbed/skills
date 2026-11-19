# Bug Investigation Log

## Bug

**Description:** {description} **Source:** {user report / error log / Linear issue} **Date:** {date}

## Timeline

### Phase 1: Reproduce

- **Method:** {how reproduced}
- **Result:** {confirmed / could not reproduce}
- **Evidence:** {test output, error message, stack trace}
- **If unconfirmed:** {conditions under which the failure was reported or seen, and the attempts that did not trigger it}

### Phase 2: Isolate

- **Scope:** {files/functions identified}
- **Callers:** {upstream code that triggers the bug}
- **Classification:** {single function / module interaction / data flow}
- **Evidence:** {grep results, call chain}

### Phase 3: Trace

- **Method:** {manual trace / git bisect / pattern matching}
- **Root Cause:** {description}
- **Location:** {file}:{line}
- **Introducing Commit:** {hash and message, if found}

## Root Cause Analysis

- **What:** {what goes wrong}
- **Where:** {file}:{line}
- **Why:** {explanation of the mechanism}
- **When introduced:** {commit hash or timeframe}

## Fix

- **Applied:** {yes / no}
- **Files Modified:** {list}
- **Regression Test:** {file path}
- **Confidence:** {High / Medium / Low}

## Verification

- **Tests:** {PASS / FAIL}
- **Build:** {PASS / FAIL}
- **Original failure:** {gone / still present / not rechecked}
