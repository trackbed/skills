# Development Guide

Contributor reference for testing, verification, skill security scanning, skill-change evals, and the SkillOpt eval pilot. For the contribution workflow see [CONTRIBUTING.md](../../CONTRIBUTING.md); for component conventions see the repo-root [AGENTS.md](../../AGENTS.md).

## Running the Tests

The hooks are tested using [BATS](https://github.com/bats-core/bats-core) (Bash Automated Testing System). Pure JavaScript and Python helper modules also have focused unit test runners. The Bats suite requires `jq` for JSON parsing in hooks.

### Setup

```bash
# Read-only prerequisite check
bash trackbed/scripts/bootstrap-dev.sh --check

# Explicit setup (Node.js 20+, npm, and Python 3.10+ must already be available on Linux)
bash trackbed/scripts/bootstrap-dev.sh --install
```

### Running Tests

Start with the closest single-file target in [code-map.md](code-map.md#source-to-test-map). Use smoke for representative feedback and the complete gates below for Pull Request and release validation; focused and smoke checks do not replace those gates. The [dated Bats measurements](#measuring-bats-suite-cost) record host conditions and suite costs separately from the older aggregate timings.

```bash
# Run the representative cross-language smoke loop (budget: under 30 seconds)
make -C trackbed test-smoke

# Run the complete Node, Python, and Bats suite
make -C trackbed test

# Run only Bats integration tests
make -C trackbed test-bats

# Run one Bats integration test file
make -C trackbed test-bats-file BATS_TEST_FILE=tests/block-rm-rf.bats

# Run only Node unit tests
make -C trackbed test-node

# Re-run affected Node tests when their files or dependencies change
make -C trackbed test-node-watch

# Run the closest Node test for a changed source file
make -C trackbed test-node-file NODE_TEST_FILE=tests/node/frontmatter.test.js

# Run only Python unit tests
make -C trackbed test-python

# Run one Python unit test file
make -C trackbed test-python-file PYTHON_TEST_FILE=tests/python/test_git_command_parser.py

# Enforce conservative Node/Python coverage baselines
make -C trackbed unit-coverage

# Run all coverage gates and validate the production-source inventory
make -C trackbed coverage

# Run with verbose output (show test names)
make -C trackbed test-verbose

# Run converter Node contracts and Bats CLI smoke tests
make -C trackbed test-convert

# Run only block-rm-rf tests
make -C trackbed test-block

# Run only auto-format tests
make -C trackbed test-format

# Run only skill usage stats tests
make -C trackbed test-skill-usage
```

The initial coverage baselines are 80% lines, 70% branches, and 80% functions for Node, plus a 35% production-line aggregate for Python. They sit below the measured results (91.82%/82.66%/95.24% for the Node production aggregate on Node 20.20.2, and 49.59% for Python locally against 51.23% in CI) and should only ratchet upward.

`coverage-node` keeps the human-readable test report separate from the machine-readable LCOV report. The gate matches each LCOV source to the JavaScript production inventory, sums hit and total counters for `measured` sources, and applies the baselines to those weighted production totals. Test files and registered `contract_only` sources do not contribute to the denominator. Missing measured sources, unregistered production sources, malformed records, duplicate source records, and impossible hit/total pairs fail the gate. A valid zero branch or function denominator is treated as 100% because the measured sources contain no obligations for that metric.

The copied-Makefile regression fixture was exercised with Node 20.20.2 and the development runtime, Node 24.14.1. On both runtimes, deliberately undercovered production failed the gate despite a test file containing 120 fully executed assertions; the counter fixtures also cover unequal file sizes so a simple average of per-file percentages cannot satisfy the contract.

`coverage-python` also enforces a 20% per-file floor (`PYTHON_FILE_COVERAGE_MIN`) on every `measured` source and prints the ten lowest-covered files with the floor each one must clear. Sources that predate the floor are seeded in `python.measured_floors` with the lower value they currently hold; a seeded file that climbs 15 points past the default floor (`PYTHON_FILE_COVERAGE_STALE_MARGIN`) fails the gate until its entry is deleted, so the ratchet only moves upward. Keep floors conservative: `trace` attributes lines slightly differently across supported Python versions, so a floor set at a file's exact measurement will flap.

Bats exercises shell integration behavior, so `coverage` reports its complete top-level `tests/*.bats` file/test inventory as a contract proxy rather than claiming line coverage.

Production sources are registered in `trackbed/config/coverage-production-sources.json`. The `coverage` target reconciles that inventory with executable JavaScript, Python, and shell files under the plugin's `evals/`, `hooks/`, and `scripts/` directories. It also discovers JavaScript and shell files in plugin skill-local `scripts/` and `assets/` directories, plus executable files in repository-maintenance skill-local `scripts/` directories under `.agents/skills/`.

Put JavaScript and Python files in `measured` when the native coverage report includes them consistently across supported runtimes; otherwise put them in `contract_only` and map each source to one or more top-level `trackbed/tests/*.bats` contracts. A contract-only source may still appear incidentally in a native report, but the coverage gate does not require it there or include its Python result in the measured aggregate. Vendored JavaScript assets that are intentionally outside coverage may instead be registered in `javascript.excluded` with a non-empty rationale. Shell sources, including skill assets, use `contract_only`. The Bats runner does not recurse into nested test directories, so mapped contracts must be top-level files. Update the inventory whenever a production source is added, moved, removed, or changes coverage mode.

The optional `python.measured_floors` map records accepted debt against the per-file floor by mapping a measured Python source to the lower percentage it currently holds. Keys must name measured sources, and values must be non-negative numbers below the stale-floor threshold (`PYTHON_FILE_COVERAGE_MIN + PYTHON_FILE_COVERAGE_STALE_MARGIN`); invalid entries fail every coverage target that consumes the map.

For Node changes, `test-node-watch` uses the [built-in test runner's dependency watching](https://nodejs.org/docs/latest-v20.x/api/test.html#watch-mode). For a focused change-to-test loop, use `test-node-file` with the closest mapping in [code-map.md](code-map.md); the equivalent npm command is `npm run test:node:file -- trackbed/tests/node/<file>.test.js` from the repository root.

The `NODE_TEST_FILE`, `PYTHON_TEST_FILE`, and `BATS_TEST_FILE` values are paths relative to `trackbed/`, because `make -C trackbed` enters that directory before running the target. Each single-file target exits with a usage error when its variable is omitted.

### Pre-PR Verification

Run the closest focused target first when iterating on a change. `make -C trackbed test-smoke` provides representative cross-language feedback; `make -C trackbed test` is the complete default suite. It runs the Node unit tests, Python unit tests, and Bats integration tests. For ordinary Pull Request verification, run:

```bash
make -C trackbed pr-verify
```

The `pr-verify` target runs the repository's local pre-PR gates: the read-only dependency check, shell/Python/JS linting, format checks, skill-contract linting, changed-skill SkillSpector scanning with `--fail-on high`, the test suite, and the coverage gates. CI additionally runs environment-specific compatibility and isolated installer jobs that are not part of this local target. `pr-verify` does not add a separate `skill-eval-skill-review` pass beyond the skill-review eval coverage already exercised by the Bats suite.

To verify prerequisites without running any gate, use `make -C trackbed check-deps` (or `npm run check:deps`). It is read-only: it reports missing tools and installs nothing.

Historical runtimes measured locally on an Apple silicon laptop, for choosing the smallest useful gate (the original sample did not record a date or detailed host/runtime versions):

| Target | Runtime | Notes |
| --- | --- | --- |
| `check-deps` | 0.4s | Read-only tool check |
| `test-smoke` | 8.9s | Representative cross-language loop |
| `coverage` | 51s | Includes its own `test-python` run |
| `pr-verify` | 28m | Dominated by `test-bats`; coverage adds roughly 36s on top of `test` |

In that historical sample, the coverage gates were cheap relative to the suite they joined: `coverage-python` reuses the `test-python` run that `pr-verify` already performs, so folding `coverage` into `pr-verify` costs about 36 seconds. Run `make -C trackbed coverage` on its own when only the inventory or floors are in question.

#### Measuring Bats suite cost

Set `TRACKBED_BATS_TIMINGS=1` to run each selected top-level suite serially in its own Bats process and report `suite`, `elapsed_seconds`, and numeric exit `status` to stderr. Use `LC_ALL=C` for repeatable filename ordering:

```bash
LC_ALL=C TRACKBED_BATS_TIMINGS=1 bash trackbed/tests/run-tests.sh

# Repeat one suite; the path is relative to tests/, including paths with spaces.
LC_ALL=C TRACKBED_BATS_TIMINGS=1 bash trackbed/tests/run-tests.sh makefile.bats
```

The existing `test-bats` Make target also inherits the switch. Only the exact value `1` enables timing. The default runner still invokes `bats --tap` once, and `test-smoke` retains its separate representative selection. Timing mode uses the same top-level `*.bats` inventory without recursion, records failing suites, completes the remaining suites, and returns the first nonzero suite status. Focused mode preserves the selected suite's status.

Elapsed values use Bash's whole-second `SECONDS` counter; zero means less than one counter tick, not no work. Each interval includes Bats startup, fixtures, tests, and teardown. Timing mode adds a process per suite and emits a separate TAP stream for each, so its stdout is diagnostic output rather than one aggregate TAP document. Compare repeated suites under the same instrumentation and host conditions; these samples do not establish a speedup, a CI threshold, or safe parallel execution.

Measurement on 2026-09-08, based on commit `183f1728` plus this timing change: Apple M4 Max, 36 GiB RAM, macOS 26.4.1 arm64, Bash 5.3.9, Bats 1.14.0, Node 24.14.1, and Python 3.14.7. Locked Node dependencies were installed before measurement. One full serial run and immediate serial repeats of its three slowest suites used the commands above, with no concurrent test or scan jobs launched by this workflow. Background host activity and cache state were not controlled.

All 73 selected suites passed. Their elapsed intervals sum to **1,649 seconds (27m 29s)**; this excludes runner setup/reporting outside those intervals and is not a measurement of the full `pr-verify` gate. Every repeated suite also passed. Values below are seconds; a dash means no repeat was collected.

| Suite | Full run | Focused repeat | Status |
| --- | --: | --: | --- |
| `adversarial-review-guidance.bats` | 2 | — | Passed |
| `adversarial-review-runner.bats` | 57 | — | Passed |
| `audit-agent-config-guidance.bats` | 1 | — | Passed |
| `auto-format.bats` | 39 | — | Passed |
| `benchmark-hook-overhead.bats` | 6 | — | Passed |
| `block-rm-rf.bats` | 55 | — | Passed |
| `bootstrap-dev.bats` | 17 | — | Passed |
| `check-enabled.bats` | 13 | — | Passed |
| `check-environment.bats` | 38 | — | Passed |
| `clean-gone-branches.bats` | 56 | — | Passed |
| `code-deprecate-guidance.bats` | 4 | — | Passed |
| `code-migrate-guidance.bats` | 2 | — | Passed |
| `confirm-review-responses.bats` | 121 | 60 | Passed |
| `context-links.bats` | 14 | — | Passed |
| `contract-registry-helper.bats` | 3 | — | Passed |
| `convert-plugin.bats` | 290 | 90 | Passed |
| `demo-reel-skill.bats` | 3 | — | Passed |
| `dev-server-scripts.bats` | 16 | — | Passed |
| `discovery-delegation-guidance.bats` | 1 | — | Passed |
| `docs-sync-release-guidance.bats` | 2 | — | Passed |
| `experience-quality-guidance.bats` | 1 | — | Passed |
| `feature-spec-guidance.bats` | 1 | — | Passed |
| `find-sibling-bugs-guidance.bats` | 1 | — | Passed |
| `forward-progress-guidance.bats` | 1 | — | Passed |
| `git-fixture-helper.bats` | 8 | — | Passed |
| `github-review-guidance.bats` | 2 | — | Passed |
| `guidance-contract-helper.bats` | 4 | — | Passed |
| `gut-check-guidance.bats` | 1 | — | Passed |
| `harden-security-guidance.bats` | 1 | — | Passed |
| `issue-and-plan-to-pr-guidance.bats` | 3 | — | Passed |
| `linear-backlog-refine-guidance.bats` | 1 | — | Passed |
| `linear-breakdown-findings-guidance.bats` | 1 | — | Passed |
| `linear-issue-define-guidance.bats` | 16 | — | Passed |
| `linear-issue-implement-guidance.bats` | 0 | — | Passed |
| `linear-issue-to-pr-guidance.bats` | 3 | — | Passed |
| `linear-review-pr-guidance.bats` | 4 | — | Passed |
| `linear-select-next-guidance.bats` | 2 | — | Passed |
| `lint-skill-contracts.bats` | 79 | — | Passed |
| `makefile.bats` | 49 | — | Passed |
| `noninteractive-git.bats` | 24 | — | Passed |
| `optimize-skill.bats` | 9 | — | Passed |
| `outside-view-guidance.bats` | 0 | — | Passed |
| `plan-to-pr-validation.bats` | 64 | — | Passed |
| `pr-create-guidance.bats` | 39 | — | Passed |
| `pr-generate-description-guidance.bats` | 4 | — | Passed |
| `pr-walkthrough.bats` | 7 | — | Passed |
| `product-describe-behavior-guidance.bats` | 2 | — | Passed |
| `product-pulse-guidance.bats` | 0 | — | Passed |
| `qa-intake-guidance.bats` | 0 | — | Passed |
| `recreate-commits-push-target.bats` | 27 | — | Passed |
| `refactor-pass-guidance.bats` | 2 | — | Passed |
| `release.bats` | 61 | — | Passed |
| `repository-instructions.bats` | 0 | — | Passed |
| `resolve-base.bats` | 85 | — | Passed |
| `resolve-stack-membership.bats` | 16 | — | Passed |
| `review-diff-scripts.bats` | 29 | — | Passed |
| `review-execution-guidance.bats` | 1 | — | Passed |
| `review-shared-tree.bats` | 11 | — | Passed |
| `session-automate-repeats-guidance.bats` | 2 | — | Passed |
| `session-search-scripts.bats` | 1 | — | Passed |
| `siw-issue-reservation.bats` | 177 | 218 | Passed |
| `skill-create-guidance.bats` | 1 | — | Passed |
| `skill-resource-references.bats` | 7 | — | Passed |
| `skill-review-eval.bats` | 8 | — | Passed |
| `skill-source-audit-guidance.bats` | 0 | — | Passed |
| `skill-usage-stats.bats` | 6 | — | Passed |
| `skillopt-adapter.bats` | 9 | — | Passed |
| `skillopt-candidate-review.bats` | 8 | — | Passed |
| `skillspector-runner.bats` | 77 | — | Passed |
| `test-audit-guidance.bats` | 1 | — | Passed |
| `visual-check-slop.bats` | 34 | — | Passed |
| `workflow-artifacts-cleanup.bats` | 2 | — | Passed |
| `worktree-helper.bats` | 17 | — | Passed |

The first investigation target is `convert-plugin.bats`, the largest contributor in the full run (290 seconds, about 18% of the total). Its 90-second repeat shows substantial variability; suite timing alone cannot attribute that difference to fixture setup, package installation, filesystem/cache state, or background load. Measure those phases and the individual full-plugin installation cases next before proposing a fixture change. `siw-issue-reservation.bats` (177/218 seconds) is another substantial contributor; preserve its lock-contention and recovery assertions in any follow-up. These measurements justify further attribution, not removed tests, shared mutable fixtures, or parallel Bats execution.

GitHub Actions also runs the standalone skill-review eval as a separate path-filtered, scheduled, and manual workflow. That workflow uploads the aggregate JSON result as the `skill-review-eval` artifact and is meant to catch harness or fixture regressions without treating score movement as a merge gate.

The separate **Live Skill Review Eval** workflow has one opt-in job per provider, enabled once that provider's model and organization variables are set; its key secret supplies the keys. The Claude job runs the Agent SDK and the OpenAI job runs a Responses API adapter against the same pilot. Each switches organizations only on confirmed credit exhaustion and preserves unfinished runs through its own checkpoint artifacts. Its daily/manual trusted-main runs are outside required merge gates. Setup and behavior are in the [skill-review eval guide](../evals/skill-review/README.md#live-provider-adapters). Run `make -C trackbed test-skill-review-live-eval` for focused fake-SDK, fake-Responses, and CLI/workflow tests; all default verification remains credential-free. The archive round-trip test uses `zip` and `unzip` (install on Linux development hosts when absent). Do not deplete an organization's real balance to test rotation.

Before a release candidate or before marking a larger Pull Request ready, run the stronger local gate:

```bash
make -C trackbed verify
```

The `verify` target runs `pr-verify` plus the standalone full skill-review eval split. These verification targets expect the existing local tools used by those checks to be installed: `shellcheck`, `ruff`, `skillspector`, `bats`, `jq`, Python 3.10+, and Node.js.

Python development tool pins used by CI live in `requirements-dev.txt`. First party `actions/*` workflow actions are pinned to commit SHAs with a trailing comment naming the major tag used for lookup. Refresh them with `git ls-remote` against the upstream action repository before updating the SHA.

### Skill Security Scans

SkillSpector scans complement tests, linting, and human review. Run them for new or materially changed skills, before installing third-party skills, and as a full-tree check for release candidates. Static-only scanning is the default; semantic analysis is opt-in.

The GitHub Actions release workflow runs the full-tree static scan before creating a release branch or Pull Request. Release scan findings are advisory for now, but SkillSpector installation or execution errors fail the release workflow. The workflow uploads the full report as the `skillspector-release-report` artifact and includes a concise scan summary in the generated release Pull Request body.

The Pull Request workflow runs a static SkillSpector scan for changed skill directories and changed `shared/<topic>` resource directories. Pull Requests with no changed skills exit successfully without running the scanner. Changed-skill scans are blocking: enforceable high and critical findings fail `Skill Lint / SkillSpector static skill scan` and should block merge. Repository branch protection should require that check on `main`; if GitHub lists only the job name, require `SkillSpector static skill scan`.

```bash
# Scan every plugin skill
make -C trackbed skill-security

# Scan only skill directories and shared resource topics changed against BASE_REF, defaulting to origin/main
make -C trackbed skill-security-changed

# Scan every plugin skill with SkillSpector semantic analysis enabled.
# Defaults to JSON to avoid running a second LLM-backed companion report.
make -C trackbed skill-security-semantic

# The same LLM scan for the directories changed against BASE_REF
make -C trackbed skill-security-semantic-changed
```

For third-party skill intake, scan the source before installing it:

```bash
# Scan an external Git URL, zip, directory, or SKILL.md without LLM analysis
skillspector scan SOURCE --no-llm
```

Reports are written to `.context/skillspector/` by default, or `$RUNNER_TEMP/skillspector` in CI. Semantic scans write to a sibling `skillspector-semantic` directory, because an LLM report keeps only the findings the model confirmed and must not replace the static report. Override behavior with `SKILLSPECTOR_FORMAT`, `SKILLSPECTOR_SEMANTIC_FORMAT`, `SKILLSPECTOR_FAIL_ON`, and `SKILLSPECTOR_BASE`.

Triage high and critical findings before installation, release, or merge. In ordinary Pull Requests, fix enforceable high and critical findings or record a specific accepted finding before merging. Enable semantic scanning only when provider credentials are intentionally configured and the skill contents are acceptable to send to that provider. Semantic scans are never part of a Pull Request gate.

#### Semantic scan after merge

The **Skill Security Semantic Scan** workflow is a report-only trial; the [decision record](decisions/2026-11-11-semantic-skill-scan-trial.md) explains why it runs after merge and what the trial must show. After a push to `main` that changes `trackbed/skills/` or `trackbed/shared/`, it runs the static scan and then the LLM scan on the directories that push changed. A manual run scans the whole tree.

To turn it on, add the provider key as the `SKILLSPECTOR_OPENAI_API_KEY` secret and name the model in the `SKILLSPECTOR_SEMANTIC_MODEL` repository variable. Clear the variable to turn it off. The model must have an entry in `trackbed/config/skillspector-model-registry.yaml`, because the pinned SkillSpector release only knows the token limits of older models.

The job summary lists the findings the model added and the static findings it dropped, and the `skillspector-semantic-reports` artifact holds both sets of JSON reports. Findings never fail the run. It fails when the scanner fails, when a report shows the model was not used, or when a model call failed; the Problems section of the summary says which.

`trackbed/config/skillspector-semantic-excludes.txt` lists files the LLM scan leaves out, such as a vendored bundle. Each entry is a repository-relative path, and the static scan still covers it.

`trackbed/scripts/summarize-semantic-scan.py` finds failed model calls by SkillSpector's logger names. After changing the pinned SkillSpector commit, rehearse the failure on a branch that changes a skill: point the scan at a closed local port and confirm the summary lists the failed calls and exits 1. Nothing is sent to a provider.

```bash
OPENAI_API_KEY=unused OPENAI_BASE_URL=http://127.0.0.1:9/v1 \
  SKILLSPECTOR_PROVIDER=openai SKILLSPECTOR_MODEL=gpt-6.1-terra \
  SKILLSPECTOR_MODEL_REGISTRY="$PWD/trackbed/config/skillspector-model-registry.yaml" \
  make -C trackbed skill-security-changed skill-security-semantic-changed SKILLSPECTOR_FORMAT=json

python3 trackbed/scripts/summarize-semantic-scan.py \
  --static-dir .context/skillspector --semantic-dir .context/skillspector-semantic
```

Accepted findings live in `trackbed/config/skillspector-accepted-findings.json`. Keep this registry small: add an entry only when a finding has been reviewed and the risk is intentionally accepted or proven to be scanner noise. Each entry must name the exact repo-relative `path`, `rule_id`, `reason`, `owner`, `accepted_at`, and either `expires_at` or `review_after`.

```json
{
  "accepted_findings": [
    {
      "path": "trackbed/skills/example:skill/SKILL.md",
      "rule_id": "E4",
      "reason": "Reviewed scanner false positive; command is documented-only.",
      "owner": "Security",
      "accepted_at": "2026-06-13",
      "expires_at": "2026-09-13"
    }
  ]
}
```

Accepted findings are excluded from `--fail-on` threshold calculations only when both path and rule match and the entry is still active. They are still counted in runner output as accepted findings, and the JSON reports remain unchanged. Entries past `expires_at` or `review_after` fail blocking scans (`SKILLSPECTOR_FAIL_ON=high` or `critical`) and warn in advisory scans. Use `--accepted-findings <path>` to test a policy file other than the default registry.

### Review Completion Checks

`/trackbed:pr:code-review` seals each run with local completion evidence; the [review guide](review.md#completion-evidence) describes the contract. Run the completion regression checks with:

```bash
node --test trackbed/tests/node/review-execution.test.js trackbed/tests/node/review-completion-eval.test.js
```

The execution helper's `record --manifest` command records a batch of reviewer jobs in one call.

The [completion evaluation guide](../evals/review-completion/README.md) provides seven early-stop and control cases for live model checks. Passing fixture tests is not a claim that Astra passed those live cases.

### Cold Reader Isolation Probe

`trackbed:cold-reader` promises to start without the project's instruction files. The offline tests check the probe's logic; only a live run checks the promise, so run it after a Claude Code or Agent SDK upgrade that touches subagent startup. It runs the `claude` on your `PATH`, uses your Claude login or `ANTHROPIC_API_KEY`, and spends a few short sessions of model usage:

```bash
node trackbed/scripts/probe-cold-reader-isolation.js
```

Pass `--model <model>` to change the default `sonnet`, `--variant isolated`, `control`, or `unreadable` to run one variant, or `--claude-path <path>` to test another binary. It prints a JSON report naming the Claude Code version it tested and exits `0` when every variant passes. The `isolated` variant needs the `control` variant to mean anything: if a normal agent cannot see the planted markers either, the setup is broken and the cold reader's result proves nothing. See the [decision](decisions/2026-11-02-cold-reader-isolation.md).

#### Probe Run Record

Add a row after every live run, passed or failed, so anyone can see when isolation last held and on which Claude Code version. Put the newest run first. Take the version, model, and each variant's result from the JSON report, and mark a variant you skipped with `--variant` as `not run`. Use Notes for the reason you ran it and, for a failure, the variant's `problems`.

| Date | Claude Code | Model | `isolated` | `control` | `unreadable` | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-09 | 2.1.319 | `sonnet` | passed | passed | passed | Seed run made when this record was added |

### Skill Change Evals

`scripts/skill-eval-compare.js` answers one question: is this change to a skill an improvement? It runs an eval suite with [`claude plugin eval`](https://code.claude.com/docs/en/plugin-evals) against two versions of the plugin, a base commit and your working tree, and reports which checks improved, got worse, or stayed within noise. Both versions run the working tree's cases, so the plugin is the only difference. See the [decision](decisions/2026-11-11-skill-change-evals.md).

```bash
make -C trackbed skill-eval-compare SUITE=pr-generate-description
```

Each run is a real Claude Code session on your Claude login or `ANTHROPIC_API_KEY`, so no verification gate starts one. It needs Claude Code 2.1.269 or later. A full comparison of the `pr-generate-description` suite is 42 sessions: seven cases, three runs each, on two versions. On 2026-11-11 that cost about $28 at list price and took 14 minutes with `--concurrency 4`.

| To | Pass |
| --- | --- |
| Compare against another commit than the merge-base with `origin/main` | `BASE=<ref>` |
| Change the runs per case per version (default 3) | `RUNS=<n>` |
| Stop at a list-price cost ceiling, split across the two versions | `ARGS='--max-cost-usd 20'` |
| Run some cases only | `ARGS='--case pr-description-small-*'` |
| Run sessions in parallel | `ARGS='--concurrency 4'` |
| Try a case you are writing, on the working tree alone | `ARGS='--candidate-only --runs 1'` |

The report goes to stdout and to `.context/skill-evals/<suite>/<time>/comparison.md`, beside `comparison.json` and the runner's own HTML report for each version. The command exits `0` for a finished report, `2` when a run stopped early or the runner reported a problem, and `1` when it could not run.

Read the report from the top:

- **Verdict.** Better, worse, mixed, or no detectable difference. A check counts as changed when its pass rate moves by more than half its runs, so three runs catch a check that flips and miss a small shift. No detectable difference is a normal answer, not a failure.
- **Checks passed, cost per run, and time per run.** A change that passes the same checks for less cost or time is also an improvement; the verdict does not weigh that for you.
- **Unstable checks.** They passed in some runs and failed in others on the same version. Treat a change in one with suspicion, and raise `RUNS` before relying on it.
- **Measure the noise when in doubt.** Compare a commit with itself on a clean tree, with `BASE=HEAD`: every check reported as changed is noise.

A suite is a folder under `evals/` holding a `suite.json` and one folder per case in the layout `claude plugin eval` reads. `suite.json` lists the grants the suite needs, `allow_tools` and `scaffold`, because the runner never lets a case widen its own access. When you add a case:

- Write it for a failure you have seen, a fix that just merged, or a contract another skill relies on, and say which in `expected_outcome`. A case the skill passes every time can only show a regression; showing an improvement takes a check the current skill sometimes fails.
- Tag it with the suite name, give it a `graders/skill-fired.md` check, and prefer `regex` and `tool_used` checks. Keep `llm` checks for meaning, written as `PASS if` and `FAIL if` conditions.
- Check the part of the reply you mean. A skill's reply often holds its result and then notes about the run, and a pattern over the whole reply matches both. The `pr-generate-description` checks about the description only look between the two `---` lines around it.
- Never write `---` inside a grader's or prompt's settings block: the runner ends the block there and the case fails to load. Write `-{3}` in a pattern.
- Build fixtures from invented code. This repository is public, and the eval directory ships with the plugin. Name a fixture's `package.json` `package.fixture.json`; the fixture helper restores the name, and dependency scanners do not read the invented project as this repository's own.
- Run `make -C trackbed test-bats-file BATS_TEST_FILE=tests/skill-eval-suites.bats`. It validates every case and builds every Git fixture without starting a model.

Shell commands in a run have no network, so `gh` and Linear lookups fail there; the `pr-generate-description` prompts pass `--base main` for that reason. On macOS the script puts wrappers for the real developer tools first on `PATH`, because the `/usr/bin` launchers for Git, Python, and Make cannot run inside the runner's sandbox.

### Bash Hook Invocation Benchmark

Run the reusable process-level benchmark for the hooks registered against the `Bash` matcher:

```bash
./trackbed/scripts/benchmark-hook-overhead.sh
./trackbed/scripts/benchmark-hook-overhead.sh --iterations 50 --warmups 5
```

The benchmark uses temporary hook-state files to run enabled and disabled arms through the normal toggle mechanism. It launches the Bash-matched hook processes concurrently to mirror [Claude Code's matching-hook execution model](https://code.claude.com/docs/en/hooks#hook-handler-fields) and measures them for `echo hi` and `git status --short`; it does not include the hook dispatcher or execution of the user's command. Samples are interleaved, and added gating overhead is the median of the paired enabled-minus-disabled samples.

#### 2026-07-29 measurement and decision

This measurement predates the removal of `noninteractive-git`, so it covers the three Bash-matched hooks registered at the time.

The baseline and optimized versions were each measured twice with 30 samples per arm after three warmups on an x86_64 Vercel cloud sandbox running Linux 6.12.76 with glibc 2.34 and Python 3.11.15. The bare `python3 -c pass` startup median was 8.9-9.5 ms. Values below are the ranges across the two consecutive runs:

| Command | Version | Enabled parallel set | Disabled parallel set | Added gating overhead |
| --- | --- | --: | --: | --: |
| `echo hi` | Before | 62.981-64.495 ms | 6.573-6.962 ms | 56.013-57.814 ms |
| `echo hi` | After | 48.402-50.104 ms | 7.024-7.078 ms | 41.249-42.447 ms |
| `git status --short` | Before | 63.428-64.167 ms | 7.017-7.098 ms | 56.135-57.182 ms |
| `git status --short` | After | 48.843-49.459 ms | 6.643-6.697 ms | 42.021-42.035 ms |

The default acceptance threshold was 150 ms of median added gating latency. The corrected parallel baseline was already below that threshold for both command shapes; the earlier serial experiment had incorrectly summed three handlers that Claude Code runs concurrently. Component timing still showed no dominant hook: all three baseline hooks took roughly 55-60 ms.

The shared safety wrapper now launches the parser as the `git_command_parser` module from its own directory with an explicit `PYTHONPATH=.`, allowing normal Python bytecode caching while preventing safe-path mode or an inherited module path from redirecting the import. The repeated measurement reduced steady-state added gating latency by roughly 24-29%. The 174 `block-rm-rf` cases, 149 `noninteractive-git` cases, the parallel benchmark contract test, and manual missing-`python3` checks continued to block or allow the expected commands.

### Test Structure

This is a representative inventory by test language, not an exhaustive list of the top-level Bats contracts:

```
trackbed/tests/
├── run-tests.sh                      # Complete top-level Bats runner
├── node/
│   ├── codex-cli.test.js             # Codex CLI registration through the fake codex
│   ├── codex-hook-compat.test.js     # Codex hook packaging contracts
│   ├── converter-build.test.js       # Plugin package and marketplace build
│   ├── converter-core.test.js        # Converter loading and transforms
│   ├── converter-integration.test.js # Cross-module converter flows
│   ├── frontmatter.test.js           # Frontmatter unit contracts
│   ├── legacy-install-cleanup.test.js # Removal of pre-plugin converter output
│   └── scorer.test.js                # Skill-review scorer contracts
├── python/
│   ├── test_changelog.py
│   ├── test_git_command_parser.py
│   ├── test_lint_skill_contracts.py
│   ├── test_session_search_extractors.py
│   └── test_session_search_python38.py
├── fixtures/                         # Shared parser/frontmatter cases
├── test_helper/
│   ├── common.bash                   # Shared Bats utilities
│   └── mocks/                        # Mock codex and skillspector commands
├── makefile.bats                      # Make target contracts
├── convert-plugin.bats                # Converter CLI smoke tests
└── … other top-level *.bats           # Hook, skill, script, and guidance contracts
```

The aggregate Python target also discovers repository-maintenance tests under `.agents/skills/trackbed:skill:audit-sources/scripts/`.

## SkillOpt Adoption

SkillOpt is currently a conservative pilot for `trackbed:skill:review` only. The deterministic eval split lives in `trackbed/evals/skill-review/`, and the repo-local SkillOpt bridge lives in `trackbed/evals/skillopt/`. Keep the external SkillOpt checkout, model credentials, run output, and candidate review artifacts outside tracked source under `.context/`.

The entry points are the split check, dry-run or real SkillOpt runner, candidate export, and candidate review packet documented in [`evals/skillopt/README.md`](../evals/skillopt/README.md). Generated `best_skill.md` output is never auto-applied. A candidate is eligible for a normal source edit only after the manual review packet under `.context/skillopt-runs/skill-review/<run-id>/candidate-review/` has been inspected, the patch applies cleanly, the eval scores do not regress, and the candidate gate passes:

```bash
make -C trackbed skillopt-candidate-check
```

The candidate gate runs skill contract linting, changed-skill SkillSpector scanning with JSON output and `--fail-on high`, Node unit tests, Python unit tests, Bats integration tests, and the full skill-review eval split.

Do not add another skill to the optimization loop until it has a deterministic train/val/test split, false-positive coverage, a candidate gate, and the same manual acceptance model. SkillOpt-Sleep is proposal-only: it may suggest candidate edits from prior sessions, but deterministic held-out evals and the manual review packet remain the acceptance gate.
