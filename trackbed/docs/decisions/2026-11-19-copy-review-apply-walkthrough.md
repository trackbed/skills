# Copy Review Fixes Its Findings and Shows Them Before and After

- Status: PROPOSED
- Date: 2026-11-19
- Deciders: repository maintainer (design choices made during the implementation request)

## Context

`trackbed:code:copy-review` reported redundant interface text and stopped. Fixing it meant a second command, `trackbed:pr:resolve-review`, which is built for code-review findings: it commits, and it knows nothing about what removing visible text can break, such as a button's only accessible name or a test that finds a control by its label.

A copy change is also hard to judge from a diff. Whether a label was redundant shows on the screen, next to its icon or under its page title. The maintainer asked for the fixes to be built into the skill, with an HTML walkthrough that shows each change before and after in the real app.

Three earlier decisions constrain this:

- [Guarded model-invocable children](2026-08-29-model-invocable-orchestration-children.md) lists the only parents that may invoke `trackbed:pr:resolve-review`, and records that `trackbed:pr:code-review --loop` fixes its findings itself instead.
- [The visual report style](2026-11-10-visual-report-style.md) keeps Markdown as the record and lets only the user's own `--visual` turn on a page, which takes the shape of its report.
- [Pull Request screenshot evidence](2026-11-18-pr-screenshot-evidence.md) could rarely show a "before" image, because by the time a Pull Request is written the branch already holds the change. It deferred capturing "before" images during implementation.

## Decision

- `trackbed:code:copy-review` accepts `--apply`. After the review it fixes the Critical and Important findings in the working tree, following its own `references/apply-findings.md`. It never invokes `trackbed:pr:resolve-review`.
- The skill stays model-invocable for review. `--apply` and `--revert` edit files, so the skill honors them only when the user typed the flag or asked in the session for the findings to be fixed, the rule `--loop` already follows.
- Applying commits nothing. It removes or shortens only the text a finding names, keeps an accessible name for a control that loses its visible one, removes what the text leaves behind, and updates tests that pinned the text. The fast verification tier runs before and after editing so the workflow can identify failures it introduced. Suggestions, text shared with screens outside the scope, and text that may serve onboarding, legal, or accessibility purposes are left for the user.
- Each outcome is written into `COPY_REVIEW_OVERVIEW.md` with the shared finding statuses, the displayed text before and after, and the exact source edits per finding. A later revert restores from those source edits, so `--apply` cannot be combined with `--inline`, which writes no file. The report keeps the user's revert decisions across reruns, including scans that omit the affected findings.
- `--apply --visual` writes the page in a seventh shape, `changes`, whose reader asks what was changed, whether each change looks right, and which to keep. Each change holds a comparison of two figures, before and after. The checker requires one on every change the reader decides on, and the shared runtime styles it.
- The comparison shows screenshots from the running app. The skill takes the "before" shot of every candidate before its first edit and the "after" shot once verification has settled which changes stay, from the same URL, viewport, steps, and region. It uses only a server the detector ties to this checkout, or the one the user passes with `--url`, and never starts, restarts, or stops one. A screen that needs a sign-in, a destructive action, or would show private data is skipped, and its change is shown as text.
- Screenshots live under `.trackbed/copy-review/`, which the skill adds to Git's local exclude file and registers for cleanup.
- A `changes` page labels its decisions Keep and Revert. Its copied prompt names the changes to undo and includes the apply run's identifier. The follow-up is `trackbed:code:copy-review --revert`, which checks the run identifier against the current report and reverses the named changes by editing.

## Consequences

- One command reviews, fixes, and shows the result, and a "before" image exists for every change the app can display, because the skill owns the moment before the edit.
- A `--apply --visual` run is slower: two browser passes over every changed screen, capped at 20 pairs.
- Screenshot safety rests on the agent's check of each image, as it does for Pull Request evidence.
- Without a running server from this checkout the walkthrough has no screenshots. The skill says so and does not start one.
- The page shows a snapshot. After a revert it still shows the reverted change until the skill is rerun.
- The visual report contract, checker, runtime, and tests gain a shape. Other skills that make changes can adopt it without new machinery.

## Alternatives Considered

### Delegate to `trackbed:pr:resolve-review`

Rejected because the skill is not an authorized parent of it, the resolver commits, and it could not take the "before" screenshots, which must happen between the review and the first edit.

### A separate walkthrough page with its own builder

A script could build a self-contained page from a manifest, as `trackbed:visual:decisions` does. Rejected because the walkthrough needs what the report runtime already provides: an outline, stepping between entries, a decision per entry, and a prompt to hand back. A second runtime would duplicate it.

### A separate `--walkthrough` flag

Rejected because `--visual` already means "also give me the page for this run". After `--apply`, the page for the run is the walkthrough.

### Start the development server when none is running

Rejected for now. The user is present for an `--apply` run and can start it, and the bounded start the Pull Request skills use exists for unattended runs.

### Commit the fixes

Rejected because an audit often runs on the base branch, and uncommitted edits are easier to review and to revert one at a time.
