# Refactor Opportunity Checklist

Scan every category below. For each finding, record:

- **Location** — file path and line range
- **Category** — from the list below
- **Severity** — high (actively harmful), medium (degrades maintainability), low (cosmetic / nice-to-have)
- **Description** — what the problem is, in one sentence
- **Suggested fix** — concrete action, not vague advice
- **Confidence** — HIGH (callers, tests, or history traced and the evidence is direct), MED (clear code evidence, likely impact), or LOW (plausible, lightly evidenced)
- **Effort** — S, M, or L as defined in the shared breakdown-ready schema
- **PR relevance** — only when the caller set `SCOPE_MODE=pr`: one sentence tying the issue to an added/modified hunk, new/untracked file, deleted code with surviving references, an unchanged line within ~5 lines of a changed hunk with a concrete causal chain, or unchanged code directly affected by a changed caller/API contract. "File was touched" is not a valid relevance claim.
- **Change relevance** — only when the caller set `PLANNED_CHANGE`: one sentence naming how the fix eases that change, such as fewer files it must touch, a smaller interface it must alter, a seam where the new behavior plugs in, or one interface where its tests can run. "Cleaner code" is not a valid relevance claim.

---

## 1. Dead Code

- Unused exports (functions, classes, constants, types exported but never imported)
- Unreachable branches (conditions that are always true/false, dead `else`/`catch`/`default`)
- Commented-out code blocks (more than 2 lines)
- Unused function parameters that aren't part of a public API contract
- Unused local variables and imports
- Deprecated wrappers that only forward to the replacement
- Feature-flagged code where the flag is permanently on/off
- Test utilities or fixtures that no test references

## 2. Duplication

- Near-identical functions or methods (same logic, different names or minor variations)
- Copy-pasted blocks across files (3+ lines of structural similarity)
- Repeated inline constants or magic values that should be named
- Parallel type definitions that describe the same shape
- Multiple implementations of the same algorithm or validation rule

## 3. Complexity

- Functions longer than ~60 lines (candidates for extraction)
- Cyclomatic complexity: functions with 5+ branches (nested `if`/`switch`/ternary chains)
- Deeply nested code (3+ levels of nesting)
- God files (files doing too many unrelated things, >400 lines without clear cohesion)
- God classes/objects with too many responsibilities
- Long parameter lists (4+ params — candidate for options object or decomposition)
- Boolean parameter flags that select between different behaviors

## 4. Abstraction Issues

- **Over-abstraction**: wrappers, factories, or indirection layers that add no value (single implementation behind an interface, trivial delegation)
- **Under-abstraction**: repeated patterns that would benefit from a shared helper (3+ occurrences)
- Leaky abstractions exposing implementation details to callers
- Wrong abstraction level: low-level details mixed with high-level orchestration in the same function
- Unnecessary class hierarchies where composition or plain functions suffice

## 5. Naming & Readability

- Misleading names (function name suggests one thing, implementation does another)
- Overly generic names (`data`, `info`, `result`, `item`, `handle`, `process`, `manager`)
- Inconsistent naming conventions within the same module
- Abbreviations that obscure meaning
- Boolean variables/parameters without `is`/`has`/`should`/`can` prefix

## 6. Type & Safety Issues

- `any` casts or type assertions that bypass the type system
- Overly permissive types (`string` where a union of literals is appropriate)
- Missing `null`/`undefined` handling at module boundaries
- Unsafe type narrowing (casting instead of discriminated unions or type guards)
- Stringly-typed APIs (magic strings where enums or constants would be safer)

## 7. Error Handling

- Swallowed errors (empty `catch` blocks, `catch` that only logs)
- Inconsistent error handling patterns across similar operations
- Errors that lose context (re-throwing without wrapping or adding info)
- Missing error handling at I/O boundaries (network, filesystem, parsing)
- Overly broad `catch` blocks that mask different failure modes

## 8. Coupling & Dependencies

- Circular dependencies between modules
- Internal imports: modules reaching into other modules' implementation files instead of their public entry points
- Tight coupling to concrete implementations where an interface/injection would help
- Import chains that pull in far more than needed (barrel file bloat)
- Shared mutable state across module boundaries

## 9. Structural & Architectural

- Files in the wrong directory per project conventions
- Mixed concerns in a single file (e.g., UI + business logic + data access)
- Inconsistent module boundaries (some features split across many files, others monolithic)
- Configuration or constants scattered across multiple locations
- Test files that don't mirror source structure
- Deepening candidates — behavior that belongs behind one smaller interface (record them with the glossary's deepening fields, not as table rows):
  - One concept, many files: understanding or changing one concept means visiting many small modules, or a `CO_CHANGE` pair keeps changing together across modules
  - Leaks across a seam: callers use internal imports or must know a module's call-order rules or intermediate data to use it correctly
  - Helpers extracted only for testability: pure functions unit-tested in isolation while the behavior callers depend on goes untested at the module's interface
  - Hard to test through its interface: the behavior callers depend on is untested, or tests can reach it only by patching internals or driving real I/O; the candidate's Tests field names the interface-level tests the deepening makes possible

## 10. Performance Candidates

Only flag when there is evidence of actual or likely impact — do not speculate.

- Redundant computation in loops or hot paths
- Missing memoization / caching for expensive pure computations
- N+1 query patterns or unbatched I/O
- Large synchronous operations that could be lazy or streamed
- Unnecessary re-renders (framework-specific: missing keys, unstable references, over-subscribing)

## 11. Implicit State Machines

State with a finite set of states, more than one writer, and no single owner of its transitions. Before scanning this category, read the shared method at `${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.0.1/shared/state-machines/references/implicit-state-machines.md`, using the resolved path the lead passes. It defines what to inventory, how to trace writers, and the risk shapes.

- Writers of one state that each check their own from-state, with no transition table, guard function, or reducer that all of them use
- An explicit owner that some writers bypass
- A terminal state that some writer can leave
- A queued or pending state with no cleanup, expiry, or exit
- A scheduled job, callback, or late response that acts without re-checking the state it assumed
- Fields that belong to a state but are not set or cleared with it
- Two state fields on one record with invalid combinations that nothing prevents
- A copy of another machine's state kept in sync by hand
- The same state condition restated in several places, with differences
- Check-then-act across an `await`, double submits, or locks released before their work finishes
- One client flow re-implemented with different rules, or dialogs, locks, and consents that survive a cancel, close, or change of identity
- Old records missing the field, read differently by different readers

**Severity:**

- **High:** a reachable illegal transition, stuck state, or reversed terminal state that affects money, access, consent, data deletion, or live user sessions.
- **Medium:** an owner is bypassed, the copies have already drifted, or a reachable illegal transition, stuck state, or race outside those areas.
- **Low:** a risk shape applies, but the writers are consistent today and nothing illegal is reachable; with `--for`, also a machine with no owner that the planned change adds a writer or state to.

A machine with no concrete risk is not a finding.

**In PR scope,** check only whether the PR does one of these, and record it under the risk shape in parentheses:

- adds a writer of an existing state outside its owner (shape 4);
- adds a state without updating the owner, terminal set, and readers (shape 1 or 8);
- adds a queued state with no cleanup or exit (shape 2);
- adds a flag that combines with existing flags into a hidden mode (shape 6).

**Recording:** in addition to the standard fields, record Kind, States, Writers, Owner today, Risks, Proposed owner, and Tests, as the shared method defines them.
