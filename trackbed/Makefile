.PHONY: test-walkthrough-browser test-python38-compatibility lint lint-shell lint-python lint-js typecheck-python format format-check pre-commit pr-verify verify test test-smoke test-changed installed-resources test-bootstrap test-bats test-bats-file test-node test-node-watch test-node-file test-python test-python-file test-verbose test-convert test-block test-format test-skill-usage test-skill-contracts test-skill-review-eval test-skill-review-live-eval coverage unit-coverage coverage-node coverage-python coverage-bats-contract check-python-static-inventory skill-contracts skill-security skill-security-changed skill-security-semantic skill-security-semantic-changed skill-eval-skill-review skill-eval-compare skillopt-candidate-check bootstrap-check bootstrap-install install-test-deps check-deps check-bats-deps check-node-deps check-python-deps check-coverage-inventory-deps check-shell-deps check-ruff-deps check-mypy-deps check-js-deps check-static-deps check-test-deps check-format-deps check-security-deps check-security-changed-deps

ROOT_DIR := $(abspath ..)
PLUGIN_REL := $(shell basename "$(CURDIR)")
DEV_VENV_BIN ?= $(ROOT_DIR)/.venv/bin
dev_tool = $(shell if [ -x "$(DEV_VENV_BIN)/$(1)" ]; then printf '%s\n' "$(DEV_VENV_BIN)/$(1)"; else printf '%s\n' "$(1)"; fi)
SHELLCHECK ?= $(call dev_tool,shellcheck)
SHELLCHECK_SEVERITY ?= warning
RUFF ?= $(call dev_tool,ruff)
MYPY ?= $(call dev_tool,mypy)
ESLINT ?= $(ROOT_DIR)/node_modules/.bin/eslint
PRETTIER ?= $(ROOT_DIR)/node_modules/.bin/prettier
PYTHON38 ?= python3.8
TSC ?= $(ROOT_DIR)/node_modules/.bin/tsc
SKILLSPECTOR_FORMAT ?= markdown
SKILLSPECTOR_SEMANTIC_FORMAT ?= json
SKILLSPECTOR_FAIL_ON ?= none
SKILLSPECTOR_BASE ?= $(if $(BASE_REF),$(BASE_REF),origin/main)
NODE_TEST_FILES = tests/node/*.test.js
CONVERTER_NODE_TEST_FILES = \
	tests/node/converter-core.test.js \
	tests/node/converter-build.test.js \
	tests/node/converter-integration.test.js \
	tests/node/codex-cli.test.js \
	tests/node/codex-hook-compat.test.js \
	tests/node/legacy-install-cleanup.test.js
CONVERTER_BATS_TEST_FILE = tests/convert-plugin.bats
SMOKE_NODE_TEST_FILES = tests/node/frontmatter.test.js tests/node/scorer.test.js
SMOKE_PYTHON_TEST_FILE = tests/python/test_git_command_parser.py
SMOKE_BATS_TEST_FILE = tests/linear-issue-implement-guidance.bats
BOOTSTRAP_BATS_TEST_FILE = tests/bootstrap-dev.bats
PYTHON_TEST_DIR = tests/python
PYTHON_TEST_PATTERN = test_*.py
PYTHON_MAINTENANCE_TEST_DIR = ../.agents/skills/trackbed:skill:audit-sources/scripts
PYTHON_MYPY_CONFIG = mypy.ini
PYTHON_RUFF_CONFIG = .ruff.toml
NODE_COVERAGE_LINES ?= 80
NODE_COVERAGE_BRANCHES ?= 70
NODE_COVERAGE_FUNCTIONS ?= 80
PYTHON_COVERAGE_MIN ?= 35
# Per-file floor for measured Python sources. Kept conservative because `trace`
# attributes lines differently across supported Python versions; seed
# python.measured_floors for legacy debt instead of lowering this value.
PYTHON_FILE_COVERAGE_MIN ?= 20
PYTHON_FILE_COVERAGE_STALE_MARGIN ?= 15
COVERAGE_PRODUCTION_INVENTORY = config/coverage-production-sources.json
COVERAGE_GATE = python3 scripts/coverage-gate.py --root "$(ROOT_DIR)" --plugin "$(PLUGIN_REL)" --inventory "$(COVERAGE_PRODUCTION_INVENTORY)" --file-minimum "$(PYTHON_FILE_COVERAGE_MIN)" --stale-margin "$(PYTHON_FILE_COVERAGE_STALE_MARGIN)"

FORMAT_BASE ?= $(if $(GITHUB_BASE_REF),origin/$(GITHUB_BASE_REF),origin/main)
FORMAT_FILE_PATTERNS = '*.js' '*.mjs' '*.json' '*.md' '*.sh' '*.yaml' '*.yml'
PYTHON_FORMAT_FILE_PATTERNS = '*.py'

SHELLCHECK_FILES = \
	hooks/*.sh \
	hooks/lib/*.sh \
	scripts/*.sh \
	scripts/dev-server/*.sh \
	scripts/lib/*.sh \
	evals/skillopt/scripts/*.sh \
	evals/_lib/*.sh \
	evals/*/*/scaffold.sh \
	skills/*/scripts/*.sh \
	skills/*/assets/*.sh \
	tests/run-tests.sh \
	$(wildcard tests/test_helper/*.bash tests/test_helper/*.sh) \
	tests/test_helper/mocks/codex \
	tests/test_helper/mocks/skillspector

JAVASCRIPT_BROWSER_ASSETS = $(filter-out \
	skills/pr:walkthrough/assets/d3.v7.9.0.min.js, \
	$(wildcard skills/*/assets/*.js shared/*/assets/*.js))

# Keep ShellCheck warning-clean by default so new shell risks stay visible.
lint: lint-shell lint-python lint-js skill-contracts check-bats-assertions

lint-shell: check-shell-deps
	@"$(SHELLCHECK)" --severity=$(SHELLCHECK_SEVERITY) $(SHELLCHECK_FILES)
	@"$(SHELLCHECK)" --shell=bats --severity=warning --exclude=SC2164 tests/*.bats

lint-python: check-python-deps check-ruff-deps typecheck-python
	@"$(RUFF)" check --config "$(PYTHON_RUFF_CONFIG)" . ../.agents/skills/trackbed:skill:audit-sources/scripts

typecheck-python: check-python-deps check-mypy-deps
	@files=$$($(COVERAGE_GATE) inventory --list) || exit $$?; \
		ratchets=$$(sed -n 's/^\[mypy-\(.*\)\]$$/\1/p' "$(PYTHON_MYPY_CONFIG)" | awk '{ printf "%s%s", (NR > 1 ? ", " : ""), $$0 }'); \
		if test -n "$$ratchets"; then echo "mypy ratchet exceptions (owner: repository maintainers): $$ratchets"; fi; \
		cd "$(ROOT_DIR)" && "$(MYPY)" --config-file "$(PLUGIN_REL)/$(PYTHON_MYPY_CONFIG)" $$files

check-python-static-inventory: check-python-deps
	@$(COVERAGE_GATE) inventory

lint-js: check-js-deps
	@"$(TSC)" -p jsconfig.json && \
		"$(TSC)" --allowJs --checkJs --noEmit --skipLibCheck --strict true \
			--noUnusedLocals --noUnusedParameters --noFallthroughCasesInSwitch \
			--ignoreDeprecations 6.0 --target ES2022 --module commonjs --moduleResolution node10 \
			--lib ES2022,DOM --types node \
			skills/pr:walkthrough/assets/walkthrough-types.d.ts $(JAVASCRIPT_BROWSER_ASSETS) && \
		"$(ESLINT)" .

format: FORMAT_PRETTIER_MODE = --write
format: FORMAT_RUFF_MODE =
format-check: FORMAT_PRETTIER_MODE = --check
format-check: FORMAT_RUFF_MODE = --check
format format-check: check-format-deps check-ruff-deps
	@cd "$(ROOT_DIR)" && \
		prettier_files=$$( \
			if git rev-parse --verify --quiet "$(FORMAT_BASE)^{commit}" >/dev/null; then \
				git diff --name-only --diff-filter=ACMR "$(FORMAT_BASE)...HEAD" -- $(FORMAT_FILE_PATTERNS); \
			fi; \
			git diff --name-only --diff-filter=ACMR HEAD -- $(FORMAT_FILE_PATTERNS); \
			git ls-files --others --exclude-standard -- $(FORMAT_FILE_PATTERNS); \
		) && prettier_files=$$(printf '%s\n' "$$prettier_files" | sed '/^$$/d' | sort -u | while IFS= read -r path; do test ! -e "$$path" || printf '%s\n' "$$path"; done) && \
		python_files=$$( \
			if git rev-parse --verify --quiet "$(FORMAT_BASE)^{commit}" >/dev/null; then \
				git diff --name-only --diff-filter=ACMR "$(FORMAT_BASE)...HEAD" -- $(PYTHON_FORMAT_FILE_PATTERNS); \
			fi; \
			git diff --name-only --diff-filter=ACMR HEAD -- $(PYTHON_FORMAT_FILE_PATTERNS); \
			git ls-files --others --exclude-standard -- $(PYTHON_FORMAT_FILE_PATTERNS); \
		) && python_files=$$(printf '%s\n' "$$python_files" | sed '/^$$/d' | sort -u | while IFS= read -r path; do test ! -e "$$path" || printf '%s\n' "$$path"; done) && \
		if [ -n "$$prettier_files" ]; then \
			"$(PRETTIER)" $(FORMAT_PRETTIER_MODE) --ignore-unknown $$prettier_files; \
		else \
			echo "No changed Prettier-maintained files to format."; \
		fi && \
		if [ -n "$$python_files" ]; then \
			"$(RUFF)" format $(FORMAT_RUFF_MODE) --config "$(CURDIR)/$(PYTHON_RUFF_CONFIG)" $$python_files; \
		else \
			echo "No changed Python files to format."; \
		fi

# Optional contributor gate; this does not install or modify repository Git hooks.
pre-commit: format-check lint test-smoke installed-resources

installed-resources: check-node-deps
	@node scripts/check-installed-resources.js

# Pre-PR gate: local test, coverage, lint, format, contract, and changed-skill
# SkillSpector checks. CI also owns runtime-compatibility and installer jobs.
pr-verify: SKILLSPECTOR_FORMAT=json
pr-verify: SKILLSPECTOR_FAIL_ON=high
pr-verify: check-deps lint format-check skill-contracts skill-security-changed test coverage

# Full local/release gate: PR checks plus the standalone skill-review eval split.
verify: pr-verify skill-eval-skill-review

skill-contracts: check-python-deps
	@python3 scripts/lint-skill-contracts.py

# Default target - run all tests
test: check-test-deps check-bats-assertions test-node test-python test-bats

# Representative cross-language loop; historical timings are in docs/development.md.
test-smoke: check-test-deps test-bootstrap
	@node --test $(SMOKE_NODE_TEST_FILES)
	@python3 -m unittest $(SMOKE_PYTHON_TEST_FILE)
	@bats $(SMOKE_BATS_TEST_FILE)

# Suites mapped to the files changed against FORMAT_BASE, including uncommitted
# and untracked files; the mapping rules are in scripts/changed-tests.py.
test-changed: check-test-deps
	@chmod +x tests/test_helper/mocks/*
	@python3 scripts/changed-tests.py --base "$(FORMAT_BASE)"

# Focused entry point for the portable bootstrap contracts.
test-bootstrap: check-bats-deps
	@bats $(BOOTSTRAP_BATS_TEST_FILE)

# Reject Bash 3.2 assertions whose failures can be hidden by later commands.
.PHONY: check-bats-assertions
check-bats-assertions: check-python-deps
	@python3 tests/test_helper/check_bats_assertions.py

# Run all Bats integration tests; BATS_JOBS=N runs N suites at a time (needs GNU parallel).
test-bats: check-bats-deps check-bats-assertions
	@$(if $(BATS_JOBS),TRACKBED_BATS_JOBS='$(BATS_JOBS)' )./tests/run-tests.sh

# Run one Bats integration test file.
test-bats-file: check-bats-deps
	@test -n "$(BATS_TEST_FILE)" || { echo "BATS_TEST_FILE is required (for example: tests/block-rm-rf.bats)"; exit 2; }
	@chmod +x tests/test_helper/mocks/*
	@bats "$(BATS_TEST_FILE)"

# Run Node unit tests
test-node: check-node-deps
	@node --test $(NODE_TEST_FILES)

# Re-run affected Node tests as their files or dependencies change.
test-node-watch: check-node-deps
	@node --test --watch $(NODE_TEST_FILES)

# Run the Node test file mapped from a changed source file.
test-node-file: check-node-deps
	@test -n "$(NODE_TEST_FILE)" || { echo "NODE_TEST_FILE is required (for example: tests/node/frontmatter.test.js)"; exit 2; }
	@node --test "$(NODE_TEST_FILE)"

# Run Python unit tests
test-python: check-python-deps
	@python3 -m unittest discover -s $(PYTHON_TEST_DIR) -p '$(PYTHON_TEST_PATTERN)'
	@python3 -m unittest discover -s $(PYTHON_MAINTENANCE_TEST_DIR) -p '$(PYTHON_TEST_PATTERN)'

# Run one Python unit test file.
test-python-file: check-python-deps
	@test -n "$(PYTHON_TEST_FILE)" || { echo "PYTHON_TEST_FILE is required (for example: tests/python/test_git_command_parser.py)"; exit 2; }
	@python3 -m unittest "$(PYTHON_TEST_FILE)"

# Required CI browser interaction check; missing Chrome is a failure.
test-walkthrough-browser:
	@command -v bats >/dev/null 2>&1 || { echo "BATS not found."; exit 1; }
	@TRACKBED_REQUIRE_BROWSER_SMOKE=1 bats --filter '^PR walkthrough supports initial render, tab switch, search, and tour navigation$$' tests/pr-walkthrough.bats

# Isolated legacy extractor compatibility, separate from the contributor floor.
test-python38-compatibility:
	@"$(PYTHON38)" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 8) else "Use Python 3.8 for this compatibility check")'
	@"$(PYTHON38)" tests/python/test_session_search_python38.py

# Verbose output (shows each test name)
test-verbose:
	@chmod +x tests/test_helper/mocks/*
	@bats tests/*.bats

# Run the converter Node contracts and Bats CLI smoke tests.
test-convert: check-node-deps check-bats-deps
	@node --test $(CONVERTER_NODE_TEST_FILES)
	@chmod +x tests/test_helper/mocks/*
	@bats $(CONVERTER_BATS_TEST_FILE)

# Run only block-rm-rf tests
test-block:
	@chmod +x tests/test_helper/mocks/*
	@bats tests/block-rm-rf.bats

# Run only auto-format tests
test-format:
	@chmod +x tests/test_helper/mocks/*
	@bats tests/auto-format.bats

# Run only skill usage stats tests
test-skill-usage:
	@chmod +x tests/test_helper/mocks/*
	@bats tests/skill-usage-stats.bats

# Run only skill contract lint tests
test-skill-contracts:
	@bats tests/lint-skill-contracts.bats

# Run only skill review eval harness tests
test-skill-review-eval:
	@bats tests/skill-review-eval.bats

# Live adapter checks use fake SDK sessions and Responses endpoints; this target never spends credits.
test-skill-review-live-eval: check-node-deps check-bats-deps
	@node --test tests/node/credit-pool.test.js tests/node/eval-state.test.js tests/node/claude-predict.test.js tests/node/openai-predict.test.js tests/node/run-live-eval.test.js tests/node/ci-checkpoint.test.js
	@bats tests/skill-review-live-eval.bats

skill-security: check-security-deps
	@./scripts/run-skillspector.sh --all --format "$(SKILLSPECTOR_FORMAT)" --fail-on "$(SKILLSPECTOR_FAIL_ON)"

skill-security-changed:
	@./scripts/run-skillspector.sh --changed --base "$(SKILLSPECTOR_BASE)" --format "$(SKILLSPECTOR_FORMAT)" --fail-on "$(SKILLSPECTOR_FAIL_ON)"

skill-security-semantic: check-security-deps
	@./scripts/run-skillspector.sh --all --semantic --format "$(SKILLSPECTOR_SEMANTIC_FORMAT)" --fail-on "$(SKILLSPECTOR_FAIL_ON)"

skill-security-semantic-changed:
	@./scripts/run-skillspector.sh --changed --base "$(SKILLSPECTOR_BASE)" --semantic --format "$(SKILLSPECTOR_SEMANTIC_FORMAT)" --fail-on "$(SKILLSPECTOR_FAIL_ON)"

skill-eval-skill-review:
	@node evals/skill-review/run-eval.js --split all --json

# Compare one eval suite on a base commit against the working tree. This starts
# real model sessions through `claude plugin eval`, so no verification gate
# runs it.
skill-eval-compare:
	@test -n "$(SUITE)" || { echo "Usage: make skill-eval-compare SUITE=<suite> [BASE=<ref>] [RUNS=<n>] [ARGS='<options>']"; exit 2; }
	@node scripts/skill-eval-compare.js "$(SUITE)" $(if $(BASE),--base "$(BASE)") $(if $(RUNS),--runs "$(RUNS)") $(ARGS)

skillopt-candidate-check:
	@python3 scripts/lint-skill-contracts.py
	@./scripts/run-skillspector.sh --changed --base "$(SKILLSPECTOR_BASE)" --format json --fail-on high
	@node --test $(NODE_TEST_FILES)
	@python3 -m unittest discover -s $(PYTHON_TEST_DIR) -p '$(PYTHON_TEST_PATTERN)'
	@./tests/run-tests.sh
	@node evals/skill-review/run-eval.js --split all --json

coverage: unit-coverage coverage-bats-contract

# Node/Python line coverage gates, including the per-file Python floor; Bats
# integration behavior uses an inventory proxy.
unit-coverage: coverage-node coverage-python

# Native coverage thresholds were added after the Node 20 version used in CI,
# so aggregate its LCOV counters here. See https://nodejs.org/api/test.html#coverage-reporters
coverage-node: check-node-deps check-coverage-inventory-deps
	@$(COVERAGE_GATE) node-lcov --minimums $(NODE_COVERAGE_LINES) $(NODE_COVERAGE_BRANCHES) $(NODE_COVERAGE_FUNCTIONS) $(NODE_TEST_FILES)

coverage-python: check-coverage-inventory-deps test-python
	@$(COVERAGE_GATE) python-trace --minimum "$(PYTHON_COVERAGE_MIN)" --test-dir "$(PYTHON_TEST_DIR)" --maintenance-dir "$(PYTHON_MAINTENANCE_TEST_DIR)" --test-pattern '$(PYTHON_TEST_PATTERN)'

coverage-bats-contract: check-coverage-inventory-deps
	@$(COVERAGE_GATE) bats-contracts

# Portable development setup. Check mode is read-only; install mode is explicit.
bootstrap-check:
	@bash scripts/bootstrap-dev.sh --check

bootstrap-install:
	@bash scripts/bootstrap-dev.sh --install

# Backward-compatible setup alias.
install-test-deps: bootstrap-install

# Read-only prerequisite check. This verifies that the tools the verification
# targets need are installed; it never lints, tests, or installs anything.
check-deps: check-static-deps check-test-deps check-format-deps check-security-changed-deps
	@echo "All verification dependencies installed."

check-bats-deps:
	@command -v bats >/dev/null 2>&1 || { echo "BATS not found. Run 'make install-test-deps'"; exit 1; }
	@command -v jq >/dev/null 2>&1 || { echo "jq not found. Run 'make install-test-deps'"; exit 1; }

check-node-deps:
	@command -v node >/dev/null 2>&1 || { echo "node not found. Install Node.js before running Node unit tests or coverage."; exit 1; }
	@node -e "require.resolve('yaml')" >/dev/null 2>&1 || { echo "Node dependencies not installed. Run 'npm ci' from the repository root before running Node unit tests or coverage."; exit 1; }

check-python-deps:
	@command -v python3 >/dev/null 2>&1 || { echo "python3 not found."; exit 1; }

check-coverage-inventory-deps: check-python-deps

check-shell-deps:
	@command -v "$(SHELLCHECK)" >/dev/null 2>&1 || { echo "$(SHELLCHECK) not found. Install shellcheck before running lint or verify."; exit 1; }

check-ruff-deps:
	@command -v "$(RUFF)" >/dev/null 2>&1 || { echo "$(RUFF) not found. Install ruff before running lint or verify."; exit 1; }

check-mypy-deps:
	@command -v "$(MYPY)" >/dev/null 2>&1 || { echo "$(MYPY) not found. Install development dependencies from requirements-dev.txt before running lint or verify."; exit 1; }

check-js-deps:
	@command -v node >/dev/null 2>&1 || { echo "node not found. Install Node.js before running lint-js or verify."; exit 1; }
	@command -v "$(TSC)" >/dev/null 2>&1 || { echo "TypeScript not found at $(TSC). Run 'npm ci' from the repository root or set TSC to an executable command."; exit 1; }
	@command -v "$(ESLINT)" >/dev/null 2>&1 || { echo "ESLint not found at $(ESLINT). Run 'npm ci' from the repository root or set ESLINT to an executable command."; exit 1; }

check-static-deps: check-python-deps check-shell-deps check-ruff-deps check-mypy-deps check-js-deps

check-test-deps: check-bats-deps check-node-deps check-python-deps

check-format-deps:
	@command -v node >/dev/null 2>&1 || { echo "node not found. Install Node.js before running format-check or verify."; exit 1; }
	@command -v npm >/dev/null 2>&1 || { echo "npm not found. Install npm before running format-check or verify."; exit 1; }
	@command -v "$(PRETTIER)" >/dev/null 2>&1 || { echo "Prettier not found at $(PRETTIER). Run 'npm ci' from the repository root or set PRETTIER to an executable command."; exit 1; }

check-security-deps:
	@command -v skillspector >/dev/null 2>&1 || { echo "skillspector not found. Install SkillSpector before running skill-security or verify."; exit 1; }

check-security-changed-deps:
	@if git -C "$(ROOT_DIR)" rev-parse --show-toplevel >/dev/null 2>&1 && merge_base=$$(git -C "$(ROOT_DIR)" merge-base "$(SKILLSPECTOR_BASE)" HEAD 2>/dev/null); then \
		if { git -C "$(ROOT_DIR)" diff --name-only "$$merge_base"; git -C "$(ROOT_DIR)" ls-files --others --exclude-standard; } | grep -Eq '^$(PLUGIN_REL)/skills/[^/]+/'; then \
			command -v skillspector >/dev/null 2>&1 || { echo "skillspector not found. Install SkillSpector before running skill-security or verify."; exit 1; }; \
		fi; \
	fi
