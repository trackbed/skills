---
name: trackbed:docs:track-rejected-enhancements
description: (experimental) Record, check, append, or reconsider rejected enhancement concepts in the project's `.out-of-scope/` directory. Use when the team rejects an enhancement and wants to remember why, or when checking whether a new request matches a prior rejection. Not for bug rejections (close as wontfix with a comment), not for deferrals (use issue priority/status instead), not for features that already exist, not for cross-repo aggregation.
argument-hint: <record|check|append|reconsider> <concept>
disable-model-invocation: true
user-invocable: true
---

# Out-of-Scope Knowledge Base

Maintain a `.out-of-scope/` directory at the project root: one short markdown file per rejected enhancement concept, capturing what was rejected and why so future sessions can check before re-litigating.

## When to use

Use this skill when:

- The team has just rejected an enhancement during discovery, triage, refactor planning, or review and wants to record the rejection so it does not get re-proposed in six months.
- A new request arrives and you suspect it has been rejected before — `check` looks up matches by concept similarity.
- A previously-rejected concept is being re-proposed with new evidence — `append` records the new request alongside the original.
- Priorities have changed and a prior rejection no longer applies — `reconsider` removes the entry.

Route elsewhere if:

- **Bug rejection** → close the issue as `wontfix` with a comment. This skill is for enhancement scope, not bug triage.
- **Deferral** ("not now, but maybe later") → use issue priority/status. A deferral is not a settled rejection, and `record` will gate on this distinction.
- **Already implemented** → point the requester to where the feature lives. Never record it: a built feature is not a rejection, and recording it would make later `check` runs report a false one.
- **Architectural decision with rejected alternatives** → use `$trackbed:docs:adr`, which preserves rejected alternatives inside the ADR itself.
- **Initiative-local decisions during SIW preparation** → record them in the specification or `siw/LOG.md` for transfer to Linear.

## Argument parsing

1. Parse `$ARGUMENTS` by spaces. The first token is the subcommand.
2. Recognize `record`, `check`, `append`, `reconsider` as exclusive subcommands.
3. The remaining tokens form the concept. For `append`, the last token is the issue reference and the rest form the concept — but only when the last token looks like an issue reference (`#123`, `ABC-123`, or a URL). If it does not (e.g. `append dark mode`), treat all remaining tokens as the concept and ask the user for the issue reference instead of guessing.
4. If no arguments are given or the subcommand is unknown, print the supported subcommands and stop.

## Slug rule

Lowercase, replace spaces and underscores with hyphens, strip characters outside `[a-z0-9-]`, collapse repeated hyphens. Example: `"Dark Mode"` → `dark-mode`. The skill always keys files by slug; the user-facing concept name is preserved verbatim inside the file body.

If the computed slug is empty (the concept was missing or contained no usable characters), print an error naming the offending input and stop before any file operation. This guard applies to every subcommand, including `append` when the concept token is missing.

## Find an existing record

One concept keeps one record, however the request is worded. `record`, `append`, and `reconsider` look up the concept's record in this order before acting:

1. **Exact slug.** If `.out-of-scope/<slug>.md` exists, it is the record.
2. **Similar concept.** Otherwise, if `.out-of-scope/` exists and is not empty, list its filenames and apply the same similarity judgment as `check` step 3. Read each plausible match's heading and "Why this is out of scope" section to confirm it describes the same concept. If more than one record plausibly matches, list them and let the user pick one or none (via the structured question tool when available, otherwise in plain prose). The pick is the user's choice, so the subcommand does not ask about that record again.
3. **No record.** If neither step finds one, the concept has no record.

Below, `<record>` is the slug of the record found: the exact slug, or the similar match being offered or picked. Never act on a similar match without the user's explicit choice; a declined match counts as no record.

## Subcommands

### `record <concept>`

Capture a settled rejection.

1. Slug the concept and run **Find an existing record**.
2. If `.out-of-scope/<slug>.md` already exists, ask whether the user meant `append`. Stop unless overridden.
3. If only a similar record exists, offer it before creating a new file. If the user already picked it from several matches, continue with `append` as below without asking again. Otherwise ask (via the structured question tool when available, otherwise in plain prose) and wait for an explicit choice:

   Ask the user directly in chat:
   Question label: Existing record found
   Question: This is similar to `.out-of-scope/<record>.md` (decided <date>). Add this request to that record, or record a separate concept?
   Suggested options:
   - Append to the existing record
   - Record a separate concept
   - Cancel
   On append, continue with `append` from its duplicate-reference step against `.out-of-scope/<record>.md`, asking for the issue reference if it is not known. On cancel, stop without writing. On a separate concept, continue below.

4. **Settled-vs-deferral gate** — ask the user (via the structured question tool when available, otherwise in plain prose) and wait for an explicit choice:

   Ask the user directly in chat:
   Question label: Is this a settled rejection?
   Question: Recording a rejection here means future sessions will surface it before re-litigating. Is this a settled decision, a deferral that might come back later, or a request for a feature that already exists?
   Suggested options:
   - Settled rejection — record it
   - Deferral — cancel
   - Feature already exists — cancel
   If the user picks deferral, stop without writing. If the feature already exists, stop without writing and suggest pointing the requester to where it lives.

5. Gather rejection content from the user in prose — these are free-text fields, not multiple choice, so do not ask the user directly in chat here. Pull from the surrounding conversation where the answer is already known and ask for the rest:
   - Substantive reason (project scope, technical constraints, or strategic decision; not "we're too busy").
   - Optional code sample illustrating a technical constraint.
   - Prior-request references (issue links or PR references that triggered or shaped the rejection).
   - Decider name or role.
6. Create the directory if missing (`mkdir -p .out-of-scope`).
7. Render and write `.out-of-scope/<slug>.md` from `assets/out-of-scope-template.md`:
   - `{Concept Name}` → user-facing concept (preserve original casing, not the slug).
   - `{YYYY-MM-DD}` → today's absolute date. Capture the date in the file body so `git mv`, re-checkout, or copy operations cannot reset it via mtime.
   - `{name or role}` → decider.
   - "Why this is out of scope" → substantive reason.
   - "Prior requests" → bullet list of issue references with one-line context each.
8. If `.gitignore` would hide `.out-of-scope/`, ask once per record run (via the structured question tool when available, otherwise in plain prose — wait for an explicit choice) whether to keep it gitignored or remove the ignore rule. Default recommendation: committed (institutional memory).
9. Print `recorded .out-of-scope/<slug>.md`.

### `check <concept>`

Look up whether a concept has been rejected before.

1. If `.out-of-scope/` is missing or empty, print `no prior rejections recorded` and stop.
2. List filenames in `.out-of-scope/` (`ls .out-of-scope/`).
3. Reason about which slugs plausibly match the concept. Concept similarity is judgmental, not fuzzy: `dark-mode` and `night-theme` plausibly match; `dark-mode` and `darken-image-filter` do not.
4. For each plausible match, read the file body and surface:

   ```
   This is similar to `.out-of-scope/<slug>.md` (decided <date>) — we rejected this before because <one-line summary of "Why this is out of scope">. Continue, or honor the prior rejection?
   ```

5. Ask the user (via the structured question tool when available, otherwise in plain prose) and wait for an explicit choice:

   Ask the user directly in chat:
   Question label: Honor prior rejection?
   Question: <surface format above>
   Suggested options:
   - Honor the prior rejection — stop
   - Continue anyway
   If continuing, note the prior rejection in subsequent output so callers can see the override.

6. If no plausible match, print `no prior rejections found for <concept>`.

### `append <concept> <issue-ref>`

Record an additional request that asked for an already-rejected concept.

1. Slug the concept and run **Find an existing record**.
2. If only a similar record exists and the user has not already picked it, surface it as `This is similar to .out-of-scope/<record>.md (decided <date>). Append to it?` and wait for an explicit yes before continuing against that file.
3. If no record exists, ask whether the user meant `record`. Stop unless overridden.
4. If `<issue-ref>` already appears under "Prior requests", print `<issue-ref> already recorded in .out-of-scope/<record>.md` and stop — re-running must not duplicate bullets.
5. Otherwise append a new bullet under the "Prior requests" heading: `- <issue-ref> — <short context>`. Ask for the short context if not provided.
6. Print `appended <issue-ref> to .out-of-scope/<record>.md`.

### `reconsider <concept>`

Remove a rejection that no longer applies.

1. Slug the concept and run **Find an existing record**.
2. If no record exists, print `no rejection recorded for <concept>` and stop.
3. Read `.out-of-scope/<record>.md` and surface its content so the user sees what is being removed. For a similar match, say that it was found by similarity rather than by exact slug; the removal confirmation below is the user's choice to accept it.
4. Confirm with the user (via the structured question tool when available, otherwise in plain prose) and wait for an explicit choice:

   Ask the user directly in chat:
   Question label: Remove this rejection?
   Question: Remove `.out-of-scope/<record>.md`? Future sessions will no longer surface it.
   Suggested options:
   - Remove
   - Keep
5. If confirmed, delete the file. Print `removed .out-of-scope/<record>.md — rejection no longer recorded`.
6. Reopening the original issue is a separate action — this skill does not touch Linear or git history.

## File format

Files in `.out-of-scope/` follow the canonical structure in `assets/out-of-scope-template.md` — the single source of truth; read it before rendering. The load-bearing elements, in order:

1. `# {Concept Name}` — the first heading; it keeps the user's wording of the concept.
2. `Decided: {YYYY-MM-DD} Decided by: {name or role}` — date and decider on one line.
3. `## Why this is out of scope` — the substantive reason, plus an optional code sample.
4. `## Prior requests` — the bullet list `append` grows.

`check` and **Find an existing record** match on filenames first and read a file's heading and body only for a plausible match; `append` locates the "Prior requests" list by heading. Manual edits must preserve heading text and order.

## Reading guidance for consuming skills

Skills that read `.out-of-scope/` during their context-gathering phase — discovery, issue-definition, and refactor-planning skills among them — each carry their own inline instruction so they stay self-contained when this skill is missing. The shared protocol they follow:

1. **Cheap-list filenames first.** Run `ls .out-of-scope/` (or equivalent). If absent or empty, skip silently.
2. **Read file bodies only on plausible match.** Concept similarity is judgmental, not fuzzy. Read at most a handful of files per session.
3. **Surface format:** `This is similar to .out-of-scope/<slug>.md (decided <date>) — we rejected this before because <one-line summary>. Continue, or honor the prior rejection?`
4. **User is the gate.** Never auto-fail; ask the user (via the structured question tool when available, otherwise in plain prose) and let them override.

## Verification

- `.out-of-scope/<slug>.md` is created with the canonical template when `record` writes a new concept.
- `Decided:` line in the file body is today's absolute date (not just file mtime).
- `append` grows the "Prior requests" list by one bullet per new issue reference; a duplicate reference is rejected, not re-appended.
- An empty slug (missing or fully stripped concept) errors out before any file operation.
- `reconsider` deletes the matching file and prints a confirmation.
