# Reports keep Markdown as the record and add an opt-in visual page

- Status: PROPOSED
- Date: 2026-11-10
- Deciders: repository maintainer (design choices made during the implementation request)

## Context

About twenty skills write a Markdown report or plan into the working tree: review overviews, audits, QA reports, and plan sets. The maintainer asked for interactive HTML reports that can be filtered, searched, and triaged in a browser.

Those Markdown files are not only read by people. `trackbed:pr:resolve-review` writes resolutions back into the review it read. `skills/pr:code-review/scripts/review-execution.js` seals `REVIEW_OVERVIEW.md` by hash and checks exact lines in it before review convergence accepts a run. The two breakdown skills and `trackbed:siw:resolve-audit` parse report sections, and plan files are executed by `trackbed:code:plan-to-pr`. The commit-confirmation hook and `trackbed:workflow:cleanup-artifacts` look the files up by name.

Report content also quotes repository files, diffs, Pull Request text, and tool output, which someone else may have written.

## Decision

Markdown stays the default report style and the record. A skill that writes a Markdown report or plan set accepts `--visual`, which adds one interactive HTML page beside that output.

- **Nothing reads the page.** Every consumer, the review seal, and resolution write-back stay on Markdown. The page is a snapshot of the Markdown output: it adds nothing the output does not state and drops nothing it states.
- **Only the user turns it on.** A skill writes the page only for its own invocation's `--visual`. Orchestrating skills never add the flag for a child, and `--visual` is rejected in any mode that writes no Markdown file, such as `--inline`.
- **The model writes the page by hand.** It follows one shared contract, `shared/visual/references/visual-report.md`, and the template for its page's shape, and chooses the page's figures from the report's own data.
- **The page takes the shape of its report.** A review, a plan, a test run, a set of open questions, and a scored audit answer different questions. Each has a shape (`findings`, `plan`, `qa`, `inquiry`, `assessment`) with its own template under `shared/visual/assets/`, its own reading order, and its own entry structure. Every skill names its shape and who its reader is; the checker requires the shape and the part that shape exists for, a scorecard on an assessment and the tested journeys on a QA page.
- **The page is for reading first.** The maintainer's stated priority is that a report helps its reader understand and navigate the findings. The contract therefore opens with reader-first rules: the verdict before anything else, findings on the first screen, each entry ordered as title, location, what is wrong, evidence, fix, and then details, and reference material folded at the end. The checker rejects an entry that has no lead paragraph, and the runtime keeps an outline of every entry beside the text with ways to step through them.
- **The interactive parts are shared and deterministic.** `scripts/visual-report.py` checks the page against the contract and then copies in one runtime, `shared/visual/assets/report-runtime.{css,js}`: the outline, stepping between entries by button or keyboard, foldable sections, summary counts, filters, search, sorting, accept and dismiss triage with a copyable prompt for the follow-up skill, copy buttons, and open-in-editor links.
- **The page cannot run other script or reach the network.** The checker rejects any script, stylesheet link, remote image, or event-handler attribute the model wrote, and the injected Content-Security-Policy allows only the runtime's hash and no requests. Triage decisions stay in the browser's local storage.
- **The page is a working artifact.** Its fixed default names are registered for cleanup and for commit confirmation, and the code-review seal ignores `REVIEW_OVERVIEW.html` the way it ignores the untracked root report.

The flag covers the findings reports and four plan outputs: `PR_PLAN_*.md` sets, `GITHUB_REVIEW_REPLY_PLAN.md`, `DEPRECATION_PLAN*.md`, and `siw/SPEC_STRENGTHENING_PLAN.md`. Specifications, discovery briefs, product requirement documents, decision records, and SIW issue files stay Markdown only.

## Alternatives and consequences

Replacing the Markdown reports with HTML was the first request. It would have moved every consumer, the seal, the write-back path, and about 330 test references onto a format that costs more tokens to read and is harder to edit in place, for no gain to the skills that consume reports. The maintainer chose to keep Markdown and add the visual style beside it.

Rendering the page from the Markdown with a script would cost no model tokens and give every report the same structure. The maintainer preferred pages the model writes, so a report can carry figures drawn from its own data. Keeping the runtime shared recovers the part of that option that matters for reliability: the behavior is one tested file instead of script the model rewrites for every page.

Letting the model write the whole page, scripts included, as `trackbed:visual:explain` does for diagrams, would spend several thousand output tokens per report on untested script and would let quoted repository content run in the reader's browser.

Consequences:

- A `--visual` run writes the report twice, once as Markdown and once as the page body. The added output tokens have not been measured.
- The page goes stale once the Markdown changes, for example after `trackbed:pr:resolve-review` records resolutions. The page says so in its header.
- The finalize step needs `python3`, which the safety hooks already require.
- One synced sentence now appears in every participating `SKILL.md`, and the linter keeps the copies identical.
