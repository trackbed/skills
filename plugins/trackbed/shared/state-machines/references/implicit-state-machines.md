# Implicit State Machines

A method for finding state that changes in several places with no single owner of its rules. Read it before scanning for implicit state machines, and record each finding with the fields under **Recording**.

## Definition

An implicit state machine is a value, or a combination of values, that:

1. **Has a finite set of states.** For example, a string union or enum, enum-like constants, nullable timestamps that together mark progress (`startedAt`, `completedAt`, `cancelledAt`), attempt counters, or booleans and refs that together encode one mode.
2. **Changes in more than one place.** Several handlers, jobs, webhooks, callbacks, setters, or effects write it.
3. **Has no single owner.** No transition table, guard function, or closed reducer decides every transition. Scattered guards, write calls, or the order in which setters happen to run are all that define the legal transitions.

A machine that is documented but enforced only by scattered guards still counts. An explicit owner that some writers bypass is a finding on its own.

## Inventory First

List the candidates before reading any of them in depth.

- **Persisted state:**
  - fields named like `status`, `state`, `phase`, `stage`, `lifecycle`, or `outcome`;
  - nullable timestamps on one record that together encode a lifecycle;
  - boolean flag clusters;
  - leases, locks, and claims with an expiry or fence;
  - jobs, outboxes, and retry records with attempts, next-attempt times, or dead letters;
  - progress receipts;
  - idempotency records with pending and complete states;
  - projections that copy another machine's state.
- **Client state:**
  - clusters of local state that encode one mode;
  - refs that gate effects or duplicate state;
  - effect chains that sequence phases;
  - client copies of server state;
  - connection, media, upload, and timer flows;
  - wizards and gates;
  - autosave and dirty tracking;
  - state in the URL;
  - module-level singletons that hold a mode;
  - renderers that derive a phase from several fields.
- **Existing owners:** transition tables, `canTransition`-style guards, reducers, and state-machine libraries already in the repository. They show the fix pattern to follow, and every bypass of one is a finding.

Leave out:

- append-only logs and insert-only receipts;
- result values that are never stored or re-read;
- independent form fields;
- one-shot display values;
- animation and CSS state;
- developer tooling.

## Trace Each Candidate

For every candidate, record:

- **Home:** where its states are declared.
- **Writers:** every place that changes it. Include writes made through helpers, the insert that sets the initial state, scheduled jobs, webhooks, and effects. Note the from→to transition each writer performs and the guard it checks first.
- **Readers** that branch on the state, when a reader's assumption is part of a risk.
- **Partial owner:** a helper, table, document, or test matrix that centralizes some of the rules.

When the inventory is too large to trace in one pass, trace in this order:

1. existing owners and their bypasses;
2. candidates in high-churn files;
3. candidates with the most writers.

Count the rest instead of tracing them.

## Risk Shapes

A candidate is a finding only when one of these shapes applies, with `path:line` evidence.

1. **A terminal state can be left.** A reconciler, upsert, retry, or revision moves a record out of a state the code or docs treat as final. Fix: declare the terminal set, and have the owner refuse to leave it unless an edge is listed.
2. **A queued state has no exit.** Pending, prepared, or dead-lettered rows assume a job always runs, and nothing cleans them up or lets an operator resolve them. Fix: a cleanup job or lease expiry for each non-terminal state, or an audited operator exit.
3. **Delayed work doesn't re-check its assumptions.** A scheduled job, callback, or late response acts on a record whose state or parent has moved on. Fix: one shared guard at the top of each handler.
4. **An owner exists but writers bypass it.** Fix: route every writer through the owner.
5. **Fields that belong to a state don't move with it.** Timestamps, reasons, or counters stay set after the state they describe is left, or are not set on entry. Fix: the transition writes them together with the state.
6. **Two machines on one record have no shared rule.** Some combinations of their states are invalid, and nothing prevents them. Fix: one combined state, or a guard over the valid combinations.
7. **A copy is kept in sync by hand.** A mirror or projection of another machine is refreshed at many call sites. Fix: derive it, or sync it with a mechanism the repository already uses.
8. **One condition is restated in many places, with differences.** Fix: one named predicate.
9. **Check-then-act races and repeated actions.** A guard is checked before an `await` and acted on after it. A double submit reaches the server twice. A lock is released before the work it protects finishes. Fix: re-check inside the write, or use a synchronous single-flight guard.
10. **Client flows disagree, or reset at the wrong time.** The same flow is re-implemented with different rules, or a dialog, lock, consent, or flag survives a cancel, a close, or a change of user, device, or target. Fix: one shared hook or reducer that resets on those events.
11. **Old records are missing the field.** Readers treat a missing value differently. Fix: backfill and make the field required, or read it through one normalizing reader.

## Evidence Bar

- A candidate that no shape applies to is not a finding. Count it in the inventory line. The exception is a candidate with no owner that the caller's planned change adds a writer or state to: report it at low severity, naming the planned change as its risk, because adding to such a machine is when its writers drift.
- Before rating a finding high, re-read the writer and guard it cites. Check whether the behavior is deliberate: a retired field, a documented exception, or a product rule that needs the odd edge.
- Priority weighs writer count, drift that is already visible, concrete defects, and product impact. Money, access, consent, data deletion, and live user sessions rank highest.

## Fix Direction

Name the repository's own exemplar owner, when one exists, and follow it.

- **One module owns the rules.** It declares the states, the edges, and the terminal set.
- **One transition function.** Every writer goes through a function that checks the stored state, then writes the state and its fields together.
- **Named transitions.** Callers that need different edges name their transition instead of passing a bare target state.
- **Tests.** Add a table-driven test over every (from, to) pair, and a regression test for each risk that fails today.
- **No new library.** Do not introduce a state-machine library the repository doesn't already use.

## Recording

Record these fields in addition to the standard finding fields:

- **Kind:** persisted enum, timestamp combination, flag combination, lease or claim, job or outbox, mirror, client state, ref-gated effect, wizard, autosave, URL state, or module singleton.
- **States:** the reachable states, with terminal ones marked.
- **Writers:** the count, plus each writer's from→to transition and guard.
- **Owner today:** none; partial (say what); or bypassed (say which owner and how many writers bypass it).
- **Risks:** the shape, the `path:line` evidence, and whether it was re-read.
- **Proposed owner:** the transition table, guard, or reducer to add, and the exemplar it follows.
- **Tests:** the transition test, and the regression tests that fail today.
