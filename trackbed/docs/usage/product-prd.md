# product:prd

Use it after prototyping to record which built candidate ships and why, how success is measured, and when the feature rolls back. Run it again after launch to log results. It writes or edits one PRD file and touches nothing else: no code, prototypes, feature flags, or analytics. For a spec before anything is built, use `trackbed:docs:feature-spec`; for a tracked initiative, use `trackbed:siw:init`.

## Before you run it

- At least one prototype candidate has been built. Without one, the skill recommends building candidates first and drafts only if you ask.
- Have the evidence at hand: the baseline number and its source, user quotes, the graduation metric, the rollout steps, and who owns the kill switch. The skill does not invent any of it; what is missing is asked for or marked as a gap.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[feature name or path to an existing PRD]` | A feature name starts a new PRD, or updates the PRD that already exists for that feature. A path to an existing PRD updates it. With no argument, the skill uses the feature under discussion and asks for a name when that is unclear. |

## Examples

```text
# Record the ship decision for a feature you prototyped
/trackbed:product:prd smart reply suggestions

# Log launch results or a scope change in an existing PRD
/trackbed:product:prd docs/prd/smart-reply-suggestions.md
```

## What you get

- One Markdown file: at the path you give, else in the folder where the repository already keeps PRDs, else `docs/prd/<slug>.md`. It has a header with status, owner, results link, and date, then eight sections: Decision, Problem and Evidence, Prototype, Scope, Behavior, Success Metrics and Evals, Rollout and Rollback, and Done and Change Log.
- Before the draft, a `PRD EVIDENCE CHECK` that shows the evidence found and what is missing. Fill the gaps, or reply "draft with gaps" to have them marked `MISSING PRODUCT CONTEXT:`. Inferences are marked `UNVERIFIED:`.
- After the draft, a short summary and a request to approve. The status stays `draft` until you approve that version.
- On an update, a new change log entry with the results link, the surprises, and the decision: `iterate`, `scale`, or `retire`. Earlier entries are never edited. On approval the status becomes `live`, `retired`, or `approved`.

When a model produces the feature's output, the PRD also holds a behavior contract of 15 to 25 examples, a golden set of offline test inputs, and a human review rubric. An existing file is never overwritten without asking.
