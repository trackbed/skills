---
name: docs:adr
description: "Author Architecture Decision Records for significant, long-lived decisions, with lifecycle states (PROPOSED / ACCEPTED / SUPERSEDED / DEPRECATED). Finds the project's existing ADR log and matches its format and numbered or dated filenames; falls back to docs/decisions/ and a Nygard-style template otherwise. Use when adopting a new pattern, committing to a dependency, changing a public interface, changing the data model, or rejecting an alternative a future maintainer might reasonably re-propose. Initiative-local SIW decisions stay in the spec and LOG for transfer to Linear."
argument-hint: "[decision title]"
disable-model-invocation: false
user-invocable: true
---

# Architecture Decision Record

Author an ADR for a significant, long-lived decision: state the problem, the choice, the alternatives rejected, and the consequences.

The model may run this skill without a user request. Every run that writes an ADR file, whoever started it, must announce the write with the `ADR WRITTEN` callout in step 6.

When the model started the skill and the user did not ask for this ADR in this session:

- Write only when the decision passes the three-criterion test in step 1; otherwise write nothing.
- Apply that test before pre-flight, so a decision that fails it stops there instead of asking about the ADR log.
- Create only a new ADR file, with Status PROPOSED.
- Emit `ASK FIRST` before editing, superseding, or deprecating an existing ADR, and before creating an ADR directory the project does not have.

## When to use

For a run the user requested, a decision warrants an ADR if **any** of these are true. A run nobody requested must also pass the stricter test in step 1.

- It affects more than one module.
- It commits to a dependency (library, service, data store, cloud provider).
- It changes a public interface.
- It changes the data model.
- It rejects an alternative a future maintainer might reasonably re-propose.

Route elsewhere if:

- **Initiative-local decisions during SIW preparation** → record them in the specification and `siw/LOG.md` so `/trackbed:siw:transfer-to-linear` carries them into the Linear project. This skill handles repo-level ADRs that outlive any single initiative.
- **Feature spec / scope decisions before implementation** → use `/trackbed:docs:feature-spec`.
- **Agent-facing rules** (commit style, package manager, conventions) → use `/trackbed:docs:update-agents-md`.

## Pre-flight: find the ADR log and its convention

Before drafting, find the project's ADR log. Read the repository signals below in order, and **preserve the convention they establish** rather than imposing this template.

1. **Project instructions.** Read the agent and contributor instructions at the repository root, such as `AGENTS.md`, `CLAUDE.md`, and `CONTRIBUTING.md`, and any decision index or guide they link to. Note every ADR location, filename format, template, and status vocabulary they name.
2. **ADR tool configuration.** Check for ADR tool settings that name the log's folder, such as `.adr-dir` (adr-tools) or `.log4brains.yml` (log4brains).
3. **ADR folders anywhere in the repository.** Search below the repository root, not only at it, for folders named `decisions`, `adr`, or `adrs`, which also covers paths like `docs/architecture/decisions/`. Run this from the repository root:

   ```bash
   find . \( -name .git -o -name node_modules -o -name vendor -o -name dist -o -name build \) -prune \
     -o -type d \( -iname decisions -o -iname adr -o -iname adrs \) -print
   ```

   Keep a folder as a candidate only when it holds Markdown decision records. An index such as `README.md` or a template file is not a record.

Stop with `CONFUSION` and ask the user before drafting when the signals conflict:

- More than one candidate folder holds ADR records.
- Instructions or tool configuration name a location or filename format that the records on disk do not follow. Records the next rule treats as legacy do not count.
- One folder mixes numbering schemes, such as `0001-` records beside `2026-11-02-` records, and no project instruction names the scheme for new records. When an instruction names it and the folder already holds records in that scheme, follow the instruction and treat records in the other scheme as legacy: keep them, and never number from them.

With one log established:

1. Read 1–2 of the most recent ADRs. Identify:
   - Template style (Nygard, MADR, custom).
   - Status vocabulary (may differ from the four states below).
   - Filename scheme: sequential integer (`0001-` vs `001-` vs `ADR-001-` vs `adr-001-`) or dated (`YYYY-MM-DD-`).
   - Filename contract: literal prefix before the number or date, numeric zero-padding width, separator after it, and slug convention.
2. Treat that folder as `ADR_DIR` for the rest of the workflow.
3. Match that style for the new ADR.

Use `assets/adr-template.md` and the default `docs/decisions/` folder only when no signal above establishes a convention. When no folder holds records yet, the log is the folder an instruction or tool setting names, or else the only ADR folder found that holds just an index or template. Use it as `ADR_DIR` with the filename scheme the instructions name, or `0001-` numbering when they name none.

If the existing style uses a vocabulary that conflicts with the four lifecycle states below, prefer the project's vocabulary — but surface the mismatch with a `CONFUSION` marker so the user can decide whether to reconcile.

## Lifecycle states

Four states (use verbatim unless the project already uses a different vocabulary):

- **PROPOSED** — under discussion; not yet adopted.
- **ACCEPTED** — in effect.
- **SUPERSEDED** — replaced by a later ADR; still preserved as historical context.
- **DEPRECATED** — no longer applies; preserved for history.

## Preservation rule

Keep every ADR in the directory once it is written, including SUPERSEDED and DEPRECATED ones. An old record explains _why_ the current approach replaced the previous one, and deleting it erases the reasoning a future maintainer needs to avoid re-making a rejected choice.

## Markers

Emit these markers as you draft. They are non-optional when the condition applies.

### SIMPLICITY CHECK

Before expanding sections past the minimum, state the minimum viable ADR.

```
SIMPLICITY CHECK: minimum ADR = Context + Decision + one rejected alternative. Expanding Consequences because the decision has downstream effects on two services.
```

A minimum viable ADR has Context, Decision, and at least one rejected alternative. Expand only when a concrete reason forces it.

### NOTICED BUT NOT TOUCHING

When drafting, you will spot prior decisions that were never documented. Do not backfill them silently.

```
NOTICED BUT NOT TOUCHING: caching strategy choice (Redis over Memcached, ~2024) was never captured as an ADR
Why skipping: out-of-scope for this ADR; log for a future backfill pass
```

Log the gap; do not retroactively invent ADRs for decisions you weren't present for.

### UNVERIFIED

Any claim in Context or Consequences that rests on measurement, benchmark, or external source must be verified. If you cannot verify it now, mark it.

```
UNVERIFIED: "Postgres writes are ~3x slower than Redis for our workload"
Source needed: benchmark in #perf channel or ops dashboard
```

An ADR built on unverified claims misleads future readers more than no ADR at all.

### MISSING REQUIREMENT

Gate drafting if any of these are absent:

- Deciders (at least one named person or role).
- Context framing (what problem forced the choice).
- At least one rejected alternative.

```
MISSING REQUIREMENT: no deciders named
Cannot proceed past draft until resolved
```

### CONFUSION

If the decision scope is unclear — "is this one ADR or three?" — stop and clarify with the user before drafting.

```
CONFUSION: proposed ADR covers both session storage AND session encryption. These are separable decisions with different alternatives. Split into two ADRs?
```

### PLAN

Superseding produces a multi-file change (new ADR + predecessor update). State the plan before editing.

```
PLAN:
1. Write the new ADR in ADR_DIR using the detected filename convention (for example `0007-title.md`, `ADR-007-title.md`, or `adr-007-title.md`) with status PROPOSED unless the decision is already adopted
2. If the new ADR is already ACCEPTED, update #MMMM: change status to "SUPERSEDED by #NNNN", add forward-reference
3. Do not edit any other content of #MMMM
```

### ASK FIRST

These are Tier-2 decisions — ask the user before proceeding:

- Deprecating a live ADR.
- Changing the project's established ADR format.
- Superseding an ADR authored by someone else.

```
ASK FIRST: about to supersede #0003 (ACCEPTED, authored by @alice 2024-06). Confirm before writing new ADR?
```

## Core workflow

Six steps. Do not skip steps.

### 1. Detect significance

Apply the **When to use** criteria. If the decision affects only one function or is a purely tactical choice, emit a `NOTICED BUT NOT TOUCHING` marker naming the decision and why it is not ADR-worthy, and stop.

A run counts as requested when the user asked for this ADR in the session, including by accepting another skill's ADR offer. For a run nobody requested, the decision must also meet **all three** criteria before you write anything:

- **Hard to reverse** — undoing it later would be costly or destructive.
- **Surprising without context** — a future maintainer would reasonably ask "why this?" and not be able to infer the answer from the code alone.
- **Result of a real tradeoff** — a credible alternative was rejected for a stated reason.

If any criterion fails, write nothing. Emit `NOTICED BUT NOT TOUCHING` naming the decision and each failed criterion, and stop.

### 2. Find the next ADR number or filename

Use `ADR_DIR` and the filename scheme from pre-flight. Match the project's detected filename contract, including any literal prefix, zero-padding, separator, and slug style. Do not silently normalize the project onto `ADR-`, bare-number, or dated filenames.

While scanning, also check existing ADR titles and slugs for one that already records this decision. If a match exists, emit `CONFUSION` ("an ADR for this decision may already exist: #NNNN — supersede it instead of creating a duplicate?") and resolve with the user before naming a new file.

- **Dated scheme**: name the file with today's date and a new slug, such as `2026-11-08-session-storage.md`. No number scan applies; also check that no record already has that name.
- **Sequential integer scheme**: scan `ADR_DIR` for the highest existing ADR number and increment it.

In a dated log, cite records by filename wherever this skill shows `#NNNN` or `#MMMM`.

The highest-number scan is valid only when every record it reads follows one integer scheme. The example scan below reads a dated record such as `2026-11-02-cookie-sessions.md` as record 2026, so a scan over a mixed folder proposes the wrong number. Exclude legacy records that pre-flight set aside.

If the existing filenames follow no scheme you can continue safely (for example they are prose-only), emit `CONFUSION` and ask whether to preserve that scheme or bootstrap a new ADR log.

For the common `prefix + integer + separator + slug` shapes, extract the integer with a pattern adjusted to the detected prefix and separator. Example starting point:

```bash
find "$ADR_DIR" -maxdepth 1 -type f -print \
  | sed 's#.*/##' \
  | sed -nE 's/^[^0-9]*([0-9]+)([-_].*)$/\1/p' \
  | sort -n \
  | tail -1
```

Treat that snippet as an example, not a universal regex: tighten it to the exact convention you detected in pre-flight (for example `ADR-`, `adr-`, bare digits, or another fixed prefix) before trusting the result.

If `ADR_DIR` does not exist yet, create the folder pre-flight chose, or `docs/decisions/` when no signal names one, and start with the filename scheme pre-flight chose, or `0001` when none applies.

### 3. Draft using the detected or default template

- If a project template was detected in pre-flight, match it.
- Otherwise, use `assets/adr-template.md` verbatim.

Populate: Status (PROPOSED to start), Date (today — the date of writing, not the decision date), Deciders, Context, Decision, Consequences (positive / negative / neutral-or-follow-on), Alternatives considered (at least one; implicit alternatives such as "do nothing" or "keep what we have" count).

Keep the Decision no longer than the Context — a decision without problem framing is a preference, not an ADR. If you must stop before the ADR is complete, revert what you already wrote (delete the new file, undo any predecessor edit) rather than leave a half-written successor.

Emit `SIMPLICITY CHECK` before expanding Consequences or Alternatives past the minimum.

### 4. Set status

Start as PROPOSED. Transition to ACCEPTED only when the decision is adopted (e.g. PR merged, team consensus recorded, external approval granted). Do not mark ACCEPTED pre-emptively.

### 5. If superseding

Emit a `PLAN` marker first. Then:

1. In the new ADR's header, set Status to `PROPOSED` by default and add a line noting the intended predecessor, such as `Proposed successor to #MMMM`.
2. If the decision is already adopted, set the new ADR's Status to `ACCEPTED` and replace that note with `Supersedes #MMMM`.
3. Once the new ADR is `ACCEPTED`, update the old ADR (#MMMM): change Status to `SUPERSEDED by #NNNN` and add a line referencing the successor. Do not edit any other content of the predecessor.
4. Keep both files (see Preservation rule).

If the predecessor was authored by someone else, emit `ASK FIRST` before proceeding.

### 6. Announce the write

Skip this step only when the run left no ADR file created or edited. Otherwise, start the final message to the user with this block, before any other text, even when the ADR was a side step of a larger task:

```text
> [!IMPORTANT]
> **ADR WRITTEN — review before you commit**
> - Created: `docs/decisions/0007-session-storage.md` (Status: PROPOSED)
> - Edited: `docs/decisions/0003-cookie-sessions.md` (Status: SUPERSEDED by #0007)
> - Started by: model, no user request
> - Decision: store sessions in Postgres instead of Redis
> - Undo: delete #0007; in #0003 restore Status ACCEPTED and remove the successor reference added by this run
```

Send the block as Markdown, not inside a code fence, so it renders as a callout. List one line per created or edited file. Set `Started by` to `user` or `model, no user request`. Do not fold the block into prose, shorten it, or move it below a summary. A skill or workflow that invoked this skill must repeat the block unchanged at the top of its own final message.

Tailor `Undo` to the actual changes: name the files this run created and the exact edits to reverse in existing ADRs. Preserve pre-existing and later edits. Never recommend whole-file `git restore` for an edited ADR.

## Integration with other skills

- **Sibling — API surface decisions**: `trackbed:code:api-design` often surfaces choices that warrant an ADR (public surface shape, backwards-compatibility policy, versioning).
- **Sibling — migration strategy**: `trackbed:code:migrate` frequently produces an ADR recording the chosen migration path and what alternatives were rejected.
- **Sibling — initiative-local decisions**: `trackbed:siw:init` establishes the spec and decision log; `trackbed:siw:transfer-to-linear` carries them into the Linear project. Do not double-log those here.

## Inline-offer pattern (for other skills)

Skills that resolve decisions during their own workflow (discovery interviews, refactor explorations, architecture critiques) can surface an ADR opportunity and hand off here rather than authoring inline. The offer contract — the three-criterion test, the canonical offer message, the handoff rule, and session de-duplication — lives in `references/inline-offer-pattern.md`. Read it only when implementing that handoff in another skill.
