# Finding Lifecycle

Shared finding fields, statuses, and previous-review rules for the Pull Request review loop:

- `trackbed:pr:code-review`, `trackbed:pr:convention-review`, and `trackbed:pr:overengineering-review` produce findings and read their own previous report.
- `trackbed:pr:resolve-review` processes findings and writes their status.

Each producer keeps its own report file, finding ID prefix, matching method, relevance rules, and report sections. This reference owns only what the four skills must agree on.

## Finding fields

Every active finding carries:

- `Finding ID`: the producer's prefix and a three-digit number, such as `CR-001`, `CONV-001`, or `OE-001`. An ID names one root cause for the life of the report; never reuse it for a different one.
- `Location`: `path/to/file:line`, or a non-file location the producer defines, such as `review-scope` or `PR description`.
- `Resolution status`: one of the statuses below. A new finding starts as `open`.
- `Action taken`: written by the resolver, or by a producer that closes a finding itself.

When parsing an earlier report, accept `- Location:`, `**Location:**`, and the legacy `**File:**` label as the same field, and accept `Resolution status:` with or without bold.

## Statuses

| Status | Meaning | Typical writer |
| --- | --- | --- |
| `open` | Needs action, or a decision is still pending. | Producer (new or carried-forward finding); resolver (a fix or its validation failed, the finding is blocked or needs another run, or the user has not yet answered an escalated dispute) |
| `addressed` | The change the finding asked for is made, or the code no longer contains the root cause. | Resolver; producer when revalidation finds the root cause gone |
| `deferred` | Valid, but left for later: out of scope, manual follow-up, waiting on an owner, or the user chose to defer it. | Resolver |
| `acknowledged` | Kept as is by decision: an advisory finding, a dismissal with rationale, or complexity the requirements justify. | Resolver; overengineering review after a `JUSTIFIED` verdict |
| `skipped` | Declined by decision, such as a disagreement the user confirmed. | Resolver |

No other values. When an entry has no explicit status, infer it conservatively from `Action taken`:

- an implemented fix → `addressed`
- `Deferred …` or a `Reason deferred:` field → `deferred`
- `Acknowledged …` or `No action …` → `acknowledged`
- `Skipped …` → `skipped`
- no action or status field → `open`

Only `addressed` counts as previously addressed. `open`, `deferred`, `acknowledged`, and `skipped` are not addressed: never filter them as resolved.

## Previous-review rules

Apply these when a producer reads its previous report. "The same issue" means the producer's own matching method finds the same root cause at the same place; never match on title or line distance alone.

1. **Filter as previously addressed** a current finding that is the same issue as a previous `addressed` finding. Do not filter it when the root cause differs, the severity escalated, or the finding is a problem with the fix itself.
2. **Treat as settled** a previous finding with `Resolution status: acknowledged` or `skipped` when the same root cause is still present and nothing new has turned up: no concrete failure path the earlier decision did not cover, no escalated severity, and no change to the code that decision was about. Do not raise a settled finding again as active, even when a reviewer still prefers a different approach. Keep it out of the active sections and count it as settled.
3. **Raise again** an `acknowledged` or `skipped` finding when there is new evidence. It is active again with `Resolution status: open`, its previous ID, and the new evidence. Acting on it reverses a recorded decision; each producer says how it presents that.
4. **Carry forward as active** a previous `open` or `deferred` finding that still applies. Keep its ID, refresh location, severity, confidence, and evidence when the current run has better data, set `Resolution status: open`, and note that it was carried forward from the previous review.
5. **Revalidate** a previous finding that is not `addressed` and matches no current finding. When its root cause is still present, apply rule 2, 3, or 4. When the file or root cause is gone, do not carry it forward. When the evidence is uncertain, do not fabricate a finding; record the uncertainty in `Previous Review Context`.
6. When unsure whether a finding is the same issue, keep it active.

## What each producer adds

- `pr:code-review` matches by file, enclosing block, and root cause, and matches `review-scope` and `PR description` findings by location label. It raises a finding again under rule 3 as `manual` with the maintainer-decision blocker, and carries `Depends on` links forward.
- `pr:convention-review` matches by file, enclosing block, and root cause.
- `pr:overengineering-review` matches by location or scope and root cause, and uses each finding's `Region fingerprint` as the evidence for "no change to the code that decision was about". The fingerprint records whole files, so a changed fingerprint alone is not new evidence: an `acknowledged` or `skipped` finding is raised again only for a concrete cost or failure path the earlier decision did not cover, or a change to the decided code itself that adds to the complexity. A carried-forward finding keeps its earlier status instead of becoming `open`, so resolver decisions survive reruns; it reopens only when raised again under rule 3 or when an addressed fix failed, and every earlier entry that is not active stays in its `Previously Processed` section.

## Previous Review Context counts

Every producer's report states, under `Previous Review Context`, the previous source (or none) and these counts:

- parseable previous findings
- previously addressed findings filtered
- findings carried forward as active
- non-addressed findings not carried forward
- acknowledged or skipped findings settled, not raised again
- unparseable previous entries

A producer may add its own counts, such as findings carried forward on an unchanged region.
