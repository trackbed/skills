# Refactor opportunities eval

Three invented Parcel Desk cases exercise the unchanged
`trackbed:code:refactor-opportunities` skill in path scope. They check one
shared delivery rule across three channels, a stable quote module importing a
volatile tariff module, and a clean weight conversion module. Every case checks
that the skill fired, inspects `REFACTOR_OPPORTUNITIES_OVERVIEW.md`, and grades
the reply. No refactor should be implemented.

Run a local, advisory comparison before changing the skill:

```bash
make -C trackbed skill-eval-compare SUITE=refactor-opportunities
```

For one run per case on the current working tree:

```bash
make -C trackbed skill-eval-compare SUITE=refactor-opportunities ARGS='--candidate-only --runs 1'
```

The comparison script supplies working Git, Python, and Make wrappers for macOS
sandboxes. The suite grants Agent because the scan delegates its lenses. Runs
have no network and never run in CI. The default comparison uses three runs per
case per version; a single baseline is only a wiring check and a record of gaps,
not evidence of a reliable pass rate.

## History

Each scaffold chooses a UTC date thirty days before execution, then passes it
through the shared `FIXTURE_DATE` override. All fourteen commits remain inside
the scan's rolling twelve-month window, including runs after January 2027. The
shared helper retains its January 2026 default for other suites. An explicit
`FIXTURE_DATE` can be supplied for deterministic fixture tests.

The tariff has thirteen file-touching commits (initial plus twelve changes).
The quote module has one and eight direct importers. A report that explicitly
excludes the initial commit may instead count twelve and zero. The fixture's
own checks run with `node tests/run.mjs`.

## Baseline

On 2026-11-16, Claude Code 2.1.322 ran the three cases once each with
`--candidate-only --runs 1`, using the unchanged main skill at commit
`450910786b7a12168de525c7022f0ab3400b5dd2` (model `claude-opus-5-5`). With
the corrected artifact graders, the runner measured **$2.53 at list price,
including judges, and 241 seconds**: about $0.84 and 80 seconds per case.
These are measurements, not a budget, latency guarantee, or reliable pass rate.
Keep the default three runs for future comparisons.

Eleven of twelve checks passed:

- **Shared rule:** all four checks passed. The saved report proposed one shared
  policy covering all three callers. The source-review hypothesis was not
  reproduced; this protects a regression contract.
- **Stable import:** the semantic report check failed (all three judge votes).
  The scan reported two small cleanups and the tariff's churn, but did not flag
  the stable quote module's import of the volatile tariff or measure both sides.
  This is the observed gap for later skill changes.
- **Clean module:** all four checks passed; no worthwhile refactors were reported.

Review caught two grader bugs: keyword checks accepted contradictory saved
reports, and semantic reply checks could reject a correct report with a concise
summary. Semantic graders now use the runner's supported
`focus: { source: file, path: REFACTOR_OPPORTUNITIES_OVERVIEW.md }`; a separate
grader checks the reply summary. Criteria explicitly reject separate local
fixes, reversed churn counts, and active findings in the clean control.

A static contract pins those input boundaries. Six temporary calibration cases
then used the same built-in runner with three correct and three contradictory
seeded reports, all paired with the identical reply "The report is correct."
Every correct report passed and every contradictory report failed (all eighteen
judge votes agreed). Calibration cost $0.26 including judges and took 36 seconds.
No custom scorer, adapter, or additional shipped suite was added.

Reports and traces stay local under
`trackbed/.context/skill-evals/refactor-opportunities/artifact-baseline/` and
`.context/refactor-grader-calibration/`; generated model outputs are not committed.
A preliminary fixture's unused duplicate wrappers were replaced with eight
distinct, tested consumers before measuring the baseline. No skill instructions
were changed.

## Outline helper comparison

On 2026-11-17, Claude Code 2.1.325 compared the stable-import case three times
on each version: the importer search at `origin/main` (`cee7aee6`) against the
outline and import-graph helper (`scripts/code-outline.py`) at `0351af98`:

```bash
make -C trackbed skill-eval-compare SUITE=refactor-opportunities BASE=origin/main ARGS='--case refactor-stable-import --concurrency 3'
```

Both versions passed all 12 checks, so the runner reported no detectable
difference: the importer search already fixed the gap the baseline recorded.
The candidate cost $1.43 per run against $0.69, and took 140 seconds against 84.
That gap most likely comes from fan-out rather than from the helper. A candidate-only rerun with
`--keep-temp` ($2.96) kept the traces: the helper ran in every run and reported
the quote-to-tariff lead. Runs that launched the four prescribed scan agents
cost $1.73 to $1.84; runs that scanned the ten files in the main thread cost
$0.61 to $0.63. Two of three candidate runs in the comparison launched agents.
The base traces were not kept; their 10 to 12 turns and $0.66 to $0.74 match
the main-thread runs. The comparison and rerun together cost $9.30.
