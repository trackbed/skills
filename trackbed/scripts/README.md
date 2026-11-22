# Shared Scripts

This folder holds two kinds of top-level files:

- **Runtime helpers** run inside an installed plugin: skills, agents, and hooks call them through `${CLAUDE_PLUGIN_ROOT}/scripts/...`.
- **Maintainer tools** run only from a repository checkout: Make targets, CI workflows, releases, and contributor checks.

Claude Code installs the whole `trackbed/` folder, so both kinds reach Claude Code users. The Codex converter copies only the runtime helpers. Its `sharedRuntimeFor` function in [`convert-plugin/codex-transformer.js`](convert-plugin/codex-transformer.js) is the authoritative list of shipped scripts.

Test paths below are relative to `trackbed/`. Run one with the matching `make -C trackbed test-*-file` target from the [code map](../docs/code-map.md#test-entry-points).

## Runtime Helpers

Each file below is listed in `sharedRuntimeFor` and ships in the converted Codex plugin.

| File | Main users | Closest test |
| --- | --- | --- |
| `code-outline.py` | `code:refactor-opportunities` | `tests/python/test_code_outline.py` |
| `collect-review-diff.sh` | `pr:code-review`, `code:refactor-pass`, `test:audit`, `git:fixup`, `code:breakdown-findings` | `tests/review-diff-scripts.bats` |
| `list-stack-worktrees.sh` | `pr:rebase`, `pr:stack` | `tests/list-stack-worktrees.bats` |
| `plan_archive.py` | `code:plan-to-pr` (through its `validate-plan-state.py`) | `tests/plan-to-pr-validation.bats` |
| `pr-artifacts.py` | `pr:create` | `tests/python/test_pr_artifacts.py` |
| `pr-evidence.py` | `pr:create`, `pr:generate-description` | `tests/python/test_pr_evidence.py` |
| `resolve-base.sh` | Branch-aware skills such as `pr:generate-description`, `git:recreate-commits`, `code:plan-to-pr`, and `linear:issue-implement` | `tests/resolve-base.bats` |
| `resolve-stack-context.py` | `pr:github-review`, `pr:review-convergence`, `collect-review-diff.sh` | `tests/python/test_resolve_stack_context.py` |
| `resolve-stack-membership.sh` | `pr:create`, `pr:fix-ci`, `pr:rebase`, `pr:review-queue`, `pr:stack`, `git:recreate-commits` | `tests/resolve-stack-membership.bats` |
| `review-artifact-patterns.sh` | `pr:code-review`, `code:refactor-pass` | `tests/review-artifact-patterns.bats` |
| `review-tree-fingerprint.sh` | `pr:code-review`, `pr:product-review`, `pr:generate-description` | `tests/review-shared-tree.bats` |
| `risk-signals.py` | `pr:triage-risk`, `pr:review-convergence` | `tests/python/test_risk_signals.py` |
| `risk_classification.py` | `pr:triage-risk`, `pr:review-convergence`, `pr:github-review` | `tests/python/test_risk_signals.py` |
| `risk_patterns.py` | `risk-signals.py`, `pr:triage-risk`, `pr:review-convergence`, `pr:github-review` | `tests/python/test_risk_signals.py` |
| `siw-issue-reservation.sh` | `siw:generate-phases`, `debug:triage-to-issue` | `tests/siw-issue-reservation.bats` |
| `skill-usage.js` | `skill-usage-stats` hook, `session:automate-repeats` | `tests/node/skill-usage.test.js` |
| `validate-archive-scope.py` | `code:plan-to-pr`, `pr:fix-ci`, `pr:review-convergence` | `tests/plan-to-pr-validation.bats` |
| `verify-rewrite-state.sh` | `git:recreate-commits` | `tests/resolve-base.bats` |
| `visual-report.py` | Review and audit skills that render HTML reports, such as `pr:code-review` and `code:refactor-opportunities` | `tests/python/test_visual_report.py` |
| `visual_evidence_images.py` | `discovery:interview`, `visual:decisions` | `tests/python/test_visual_decisions_build.py` |
| `worktree-tree-id.sh` | `verify:run`, `code:refactor-opportunities`, `code:outside-view`, `code:agent-readiness` | `tests/worktree-tree-id.bats` |

## Maintainer Tools

Each file below stays out of `sharedRuntimeFor`. No shipped skill, agent, or hook may depend on it.

| File | Main users | Closest test |
| --- | --- | --- |
| `benchmark-hook-overhead.sh` | Contributors measuring hook latency ([development guide](../docs/development.md)) | `tests/benchmark-hook-overhead.bats` |
| `bootstrap-dev.sh` | `make bootstrap-check` and `make bootstrap-install` | `tests/bootstrap-dev.bats` |
| `changed-tests.py` | `make test-changed`, selecting suites for changed files | `tests/python/test_changed_tests.py` |
| `changelog.py` | `release.py` | `tests/python/test_changelog.py` |
| `check-doc-citations.py` | The Python test suite, checking `path:line` citations in maintainer guides | `tests/python/test_doc_citations.py` |
| `check-installed-resources.js` | `make installed-resources` and `make pre-commit` | `tests/skill-resource-references.bats` |
| `check-skill-edit.sh` | The project Claude Code `PostToolUse` hook in `.claude/settings.json`, checking skill edits under `skills/` | `tests/check-skill-edit.bats` |
| `convert-plugin.js` | Codex conversion entry point for `install-codex.sh`, the `setup` checkout instructions, and CI | `tests/convert-plugin.bats` |
| `coverage-gate.py` | The `make coverage` targets, which check the coverage inventory and per-file floors | `tests/python/test_coverage_gate.py` |
| `generate-component-reference.py` | Contributors regenerating `docs/component-catalog.json` after component changes | `tests/lint-skill-contracts.bats` |
| `install-codex.sh` | Codex checkout installs and the installer CI workflow | `tests/convert-plugin.bats` |
| `json_object.py` | `lint-skill-contracts.py` and `generate-component-reference.py` | `tests/python/test_lint_skill_contract_inputs.py` |
| `lint-skill-contracts.py` | `make skill-contracts` and `make lint`; implementation in `lint_skill_contracts/` | `tests/python/test_lint_skill_contracts.py` |
| `probe-cold-reader-isolation.js` | On-demand live check of the `cold-reader` agent | `tests/node/probe-cold-reader-isolation.test.js` |
| `release.py` | The release workflow ([release guide](../RELEASE.md)) | `tests/release.bats` |
| `run-skillspector.sh` | `make skill-security`, `make skill-security-changed`, and the semantic variants | `tests/skillspector-runner.bats` |
| `skill-eval-compare.js` | `make skill-eval-compare` | `tests/node/skill-eval-compare.test.js` |
| `summarize-semantic-scan.py` | The semantic SkillSpector CI workflow | `tests/python/test_summarize_semantic_scan.py` |
| `synced-contracts.yaml` | Data, not code: the contract registry read by `lint-skill-contracts.py` and the documentation site | `tests/lint-skill-contracts.bats` |

## Subfolders

| Folder | Kind | Guide |
| --- | --- | --- |
| `convert-plugin/` | Maintainer: the Codex converter behind `convert-plugin.js` | [README](convert-plugin/README.md) |
| `dev-server/` | Runtime: shared dev-server detection for browser and visual workflows | [README](dev-server/README.md) |
| `git-rewrite/` | Runtime: `stack-publication.py` freezes stack leases before a rewrite and publishes the stack atomically; `sources.yaml` records its external sources | none |
| `lib/` | Runtime: shell, Python, and Node helpers that other scripts source or import | [README](lib/README.md) |
| `lint_skill_contracts/` | Maintainer: the skill-contract linter package | [README](lint_skill_contracts/README.md) |
| `schemas/` | Maintainer: the contract schema in `skill-contracts.json`, loaded for the converter by `skill-contracts.js` and read by the linter | none |

## Adding a Script

1. Register the file in the coverage inventory, [`config/coverage-production-sources.json`](../config/coverage-production-sources.json): under `javascript.measured` or `python.measured` when the native coverage report includes it, otherwise under that language's `contract_only` with the top-level Bats suites that cover it, as the [development guide](../docs/development.md) describes. Shell scripts always use `shell.contract_only`.
2. For a runtime helper, add an entry to `sharedRuntimeFor` in [`convert-plugin/codex-transformer.js`](convert-plugin/codex-transformer.js), with `executable: true` for a script that callers run directly. Without the entry, the Codex plugin ships without the file and every skill that calls it breaks there.
3. In shipped JavaScript, require only Node core modules and files inside the plugin: the converted plugin installs no npm dependencies.
4. Add every new JavaScript file to the `include` list in [`jsconfig.json`](../jsconfig.json) so `make lint` type-checks it and applies the type-aware ESLint rules in [`eslint.config.mjs`](../eslint.config.mjs).

Then add a row to the matching table above and to the [code map](../docs/code-map.md), and name the `${CLAUDE_PLUGIN_ROOT}/scripts/...` path in the body of every `SKILL.md` that runs it.
