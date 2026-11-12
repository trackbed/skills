# Resolution Output

## Review file routing and lifecycle

Write resolutions to the appropriate file in the project root:

- If the source review was `PRODUCT_REVIEW_OVERVIEW.md` → update `PRODUCT_REVIEW_OVERVIEW.md` in place
- If the source review was `COPY_REVIEW_OVERVIEW.md` → update `COPY_REVIEW_OVERVIEW.md` in place
- If the source review was `CONVENTION_REVIEW_OVERVIEW.md` → update `CONVENTION_REVIEW_OVERVIEW.md` in place
- If the source review was `OVERENGINEERING_REVIEW_OVERVIEW.md` or carries `Review producer: trackbed:pr:overengineering-review` → update or create `OVERENGINEERING_REVIEW_OVERVIEW.md`
- If the source review came from Conductor diff comments → create or update `REVIEW_OVERVIEW.md` as an external review
- Otherwise → create or update `REVIEW_OVERVIEW.md`

Updates are **in place**: for each processed finding, replace or add its `Resolution status:` and `Action taken:` fields inside the existing entry. When a reopened manual finding is completed, apply the completed-decision replacement required by Step 2d. Findings present in the source but not addressed in this run (severity-filtered, out-of-scope, already processed, or unrelated) stay verbatim — never delete entries. If the source did not exist, create the producer-specific file named above when a recognized marker is present; otherwise create `REVIEW_OVERVIEW.md`.

## External review template

Use this format for each comment:

#### Comment #N: [Brief description]

**Location:** `path/to/file.ts:123` or `review-scope`

**Depends on:** `CR-NNN — activate after dependency is addressed` or `CR-NNN — activate if dependency is not addressed after processing` (preserve when present; otherwise omit)

**Reviewer's comment:**

> [Quote the original review comment]

**Assessment:** Agree / Agree With Modifications / Disagree

**Rationale:** [Why you agree or disagree with this feedback. A disagreement cites evidence the reviewer could have read, such as a file and line, a test, or a recorded decision.]

**Escalation:** [Only for a finding Step 2b escalated: the unrecorded fact, the user's answer, and where the fact was written, or `not written`]

**Resolution status:** open | addressed | deferred | acknowledged | skipped

**Action taken:** [Description of the fix implemented, deferral/acknowledgement/skip, or why the finding remains open]

**Draft reply:**

> [Suggested response to post to the reviewer]

---

## Internal review template

Use this simplified format for each finding:

#### Finding #N: [Brief description]

**Location:** `path/to/file.ts:123` or `review-scope`

**Depends on:** `CR-NNN — activate after dependency is addressed` or `CR-NNN — activate if dependency is not addressed after processing` (preserve when present; otherwise omit)

**Issue:** [Description of the issue]

**Resolution status:** open | addressed | deferred | acknowledged | skipped

**Action taken:** [Description of the fix implemented, deferral/acknowledgement/skip, or why the finding remains open]

---

## Out-of-scope template

If any findings were identified as scope creep, document them:

#### Deferred: [Brief description]

**Location:** `path/to/file.ts:123` or `review-scope`

**Finding:**

> [Quote the original finding/comment]

**Resolution status:** deferred

**Reason deferred:** [Why this is out of scope for this PR]

**Action taken:** Deferred — out of scope.

**Recommendation:** [Suggested follow-up: create a separate PR, open an issue, discuss with team, etc.]

---

## Manual findings

Use this format for every finding routed through Step 2d's manual-proposal flow, including `Action class: manual` findings and process-level external or legacy findings without an action class.

Extend the existing internal- or external-review entry with the proposal-field suffix below. Append each field inside the existing entry while preserving that entry's field marker and indentation; the bold field names below are semantic placeholders, not a replacement layout. Do not replace an external comment entry with the internal finding template.

**Manual blocker:** [Preserved from the review when present]

**Next human decision:** [Preserved from the review when present]

**Recommended resolution:** [Concrete recommendation answering the next human decision — what to change, where, and why this option wins]

**Alternatives:** (omit when no genuinely distinct option exists)

- [Option — one-line trade-off versus the recommendation]

End the suffix with exactly one next-step field that matches who can act:

**To proceed:** [For a user-selectable code or process decision: reply naming this finding and the chosen option, then rerun `$trackbed:pr:resolve-review`. Code changes enter implementation; accepted process decisions transition to `Selected resolution` and `Process handoff`.]

**Process handoff:** [For an accepted process decision: record `Selected resolution`, then name the exact command or workflow that applies it; keep deferred until completion is confirmed.]

**Waiting on:** [For a decision the user cannot supply: the required owner, approval, or access; do not invite the user to choose an option or rerun.]

A selected code resolution becomes retry-eligible implementation state, not another pending decision. Before implementation, remove the decision-pending fields (`Manual blocker`, `Next human decision`, `Recommended resolution`, `Alternatives`, `To proceed`, and `Waiting on`) and record **Selected resolution**. If implementation or validation fails, retain **Selected resolution**, keep **Resolution status: open**, and record the failed attempt in **Action taken**. On the next run, reuse that recorded authorization rather than reopening the completed decision gate.

After the finding is completed, remove the decision-pending fields and any `Process handoff` or `Waiting on` field, retain or record:

**Selected resolution:** [The option or process decision that was chosen]

**Decision outcome:** [What was implemented or completed, including the relevant files or process action]

Do not leave proposal-only fields on an addressed or acknowledged finding.

## Escalations

Step 2b escalates a finding when only unrecorded knowledge says it is wrong. Record **Escalation:** on the entry and end it with exactly one outcome:

- **The user confirms the fact:** set **Assessment:** Disagree, **Resolution status:** skipped, and **Action taken:** `Skipped — disagreement confirmed by the user.` The **Rationale** cites the user's decision as its evidence, in their words where possible, and the **Draft reply** states it.
- **The user corrects or does not confirm the fact:** process the finding through the normal path and record that outcome.
- **The user defers the decision:** keep **Resolution status:** open with **Action taken:** `Open — escalated; awaiting the user's decision.`

After a confirmed fact, offer once to write it where later reviewers will see it: a code comment at the finding's location when the fact explains that code, otherwise the place the project already keeps such rules, such as its agent instructions file or a decision record. Write it only when the user accepts. The accepted write is an implementation candidate, so Step 2.5 creates its checkpoint and Step 3 writes it even when no other fix remains. The written file is a fix file for Step 4, and **Escalation:** names where it went.

## Implement-only statuses

Under `--implement-only`, every payload finding gets exactly one status in `implement-only-summary.json`:

| Path | Status |
| --- | --- |
| Fix made and validation passed, shows only pre-existing failures, or could not run (`validation.status` is `not-run`) | `implemented` |
| The current code already does what the finding asks | `already-addressed` |
| Out of scope (Step 2a) | `skipped-out-of-scope` |
| The finding names code or behavior that is not in the current tree | `skipped-invalid` |
| Contested with evidence the reviewer could have read (Step 2b) | `disagreed` |
| Escalated (Step 2b) | `blocked-implementation`, `rationale` starting `Needs author decision:` |
| A preference (Step 2b), a nitpick (Step 2e), or a manual finding with **Selected resolution** | implement it, then `implemented` |
| Gray-area scope (Step 2a), a manual or process-level finding (Step 2d), an advisory finding stopped by a condition no request path bypasses (Step 2d), a comment without a file anchor whose target stays unclear (Step 1), or an unclear fix or business rule | `deferred` |
| A fallback dependent whose dependency was addressed (Step 3) | `already-addressed` |
| A dependency that is missing, malformed, cyclic, or still awaiting its outcome (Step 2d, Step 3) | `blocked-implementation` |
| The fix could not be completed | `blocked-implementation` |
| A new validation failure remains after the repair attempt | `blocked-validation` |

A `deferred` finding's `decision` fields carry the manual proposal Step 2d would write: `blocker` from **Manual blocker**, `decision_needed` from **Next human decision**, `recommendation` from **Recommended resolution**, and `alternatives` from **Alternatives**. For any other deferral, `blocker` says why the skill stopped and `decision_needed` names the question it would have asked.

A payload item that asks for several changes, such as a review summary, still gets one entry. Give it the worst status among its asks, in this order: `blocked-validation`, `blocked-implementation`, `deferred`, `disagreed`, `skipped-invalid`, `skipped-out-of-scope`, `implemented`, `already-addressed`. When the unaddressed asks mix escalations and deferrals and no other ask is blocked, return `deferred` instead, fill `decision` for the deferred asks, and name each escalated fact in `rationale`. List every file changed for any of its asks in `files_changed`, and name each ask left unaddressed in `rationale`, with the decision it needs. Start `rationale` with `Needs author decision:` only when every unaddressed ask is an escalation.

## Dependent findings

Preserve `Depends on` on every lifecycle update so later runs retain the ordering and activation condition. When a dependent finding is not yet active, keep `Resolution status: open` and record which dependency outcome it awaits. When a fallback dependency is addressed, use `Resolution status: acknowledged` with `Action taken: Acknowledged — dependency addressed; conditional cleanup is no longer needed.`

When the user explicitly reopens a deletion, also reset each fallback dependent acknowledged by that deletion to `Resolution status: open` with `Action taken: Open — dependency reopened; awaiting its new outcome.` Do this before reprocessing the deletion so the dependent can be evaluated after the new verified outcome. This narrow transition does not reopen unrelated acknowledged findings or follow-on cleanup that was already completed.

## Summary

At the end, include:

- Summary of changes made, with each fix commit SHA, or the reason no commit was made.
- Each validation command and its outcome: passed, failed with the new failure that blocked the commit, or pre-existing failure with the failing files.
- Contested and escalated findings: count each, and list every one with a pointer to its evidence. For a contested finding, give its entry heading and the file and line, test, or recorded decision its **Rationale** cites. For an escalated finding, give its entry heading, the user's decision or `awaiting decision`, and where the fact was written or `not written`. Count an escalated finding only as escalated, and write `0` for an empty count.
- Count of findings: N addressed, M deferred as out-of-scope, R open selected-resolution retries or blocked implementations, A manual findings awaiting a user decision, P accepted process handoffs awaiting completion, and X manual findings waiting on an external owner, approval, or access.
- Any breaking changes to API contracts or config behavior.
- Areas that need manual verification due to potential edge cases or risk.
