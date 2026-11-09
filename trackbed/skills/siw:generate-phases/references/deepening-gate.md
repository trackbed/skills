# Planning Confidence Deepening Gate

Use this selective gate after Phase 4 passes the hard gates and before Phase 5 user approval. Small, clear plans with no risk signals proceed directly to Phase 5.

## Risk Signals

Run one targeted confidence deepening pass when any of these signals are present:

- Large or complex breakdown: more than 4 phases, more than 10 issues, several `L` tasks, or dense dependency chains.
- Cross-cutting architecture, shared API/CLI/schema contracts, multi-surface parity, or other work where an early sequencing mistake would cause churn.
- Security, auth, privacy, payments, data migrations, backfills, persistent data changes, rollout, monitoring, or operational risk.
- Uncertain plan input: multiple `UNVERIFIED` assumptions, any unresolved `CONFUSION`, missing technical design needed for decomposition, or unclear prerequisites.
- Coordination-heavy plan: any phase or group marked `Needs coordination` where the contract-defining issue and consumers are not clearly separated.

If no signal is present, continue to Phase 5. Do not run a broad review out of habit.

## Deepening Pass Checks

When a signal is present, run one targeted pass over the risky sections before Phase 5. Check:

- sequencing and hidden prerequisites,
- hidden cross-phase or cross-issue dependencies,
- oversized tasks that escaped Phase 4 despite not being XL,
- insufficient verification for risky work,
- missing rollback, rollout, migration, security, or data-safety treatment when relevant,
- whether any split, deletion, or reordering would accidentally renumber existing issue IDs.

Use the smallest useful review surface. Prefer a single focused subagent review when the risk is mostly sequencing/decomposition and the host exposes subagents; otherwise perform the same focused pass inline. Add a specialist subagent only when the host exposes one and the risk maps directly to that domain, for example security, data migration, performance, or architecture; otherwise perform the specialist check inline.

In the prompt, pass the risk signals, the proposed phase plan, any `UNVERIFIED` assumptions, and the specific questions above. Ask for concrete plan improvements only; no implementation code or shell commands.

## Finding Threshold

A finding that would add a safeguard or other mechanism the spec did not ask for becomes a task, or a change to an existing task, only when at least one of these holds:

- **Contract requires it:** a shared API/CLI/schema contract or a stated compatibility, security, or data-safety requirement calls for the work.
- **Failure would go unnoticed until costly:** without it, a failure would surface only after it has caused data loss, user-visible breakage, or other expensive damage.
- **Later is expensive:** adding it after the planned work lands would cost far more than adding it now, for example a rollback path that cannot be retrofitted after a migration runs.

Decline every other such finding, including speculative safeguards against unlikely failures. Record each declined finding as one line naming the concern and why it failed the threshold. Show the list at the end of the Phase 5 `PLAN:` block so the user can promote any of them, and carry the findings still declined into the Phase 7 `POTENTIAL CONCERNS`.

## Incorporation Rules

Incorporate valid findings into the draft plan before Phase 5; a finding that would add a mechanism the spec did not ask for must first pass the finding threshold. Preserve all existing append-mode IDs. If a new draft task splits from another new draft task before file creation, keep the original ID on the original concept and assign the split-out concept the next unused draft number in that prefix group.

If the deepening pass adds, changes, splits, deletes, or reorders any task, loop back through Phase 4 with the revised plan before Phase 5; the final user-facing plan must be the same plan that passed Phase 4's hard gates.

If the pass surfaces a true product or scope blocker, use `MISSING REQUIREMENT:` or `CONFUSION:` and stop for user input. In `AUTO_MODE=true`, stop instead of inventing assumptions.
