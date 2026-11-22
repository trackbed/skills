#!/usr/bin/env bats

load 'test_helper/common'

teardown() {
  if [[ -n "${MAKEFILE_RUNTIME_ROOT:-}" && "$MAKEFILE_RUNTIME_ROOT" == "$BATS_TEST_DIRNAME/../../.context/makefile-coverage-runtime."* ]]; then
    rm -rf -- "$MAKEFILE_RUNTIME_ROOT"
  fi
}

create_fake_tool() {
  local path="$1"
  mkdir -p "$(dirname "$path")"
  cat >"$path" <<'SH'
#!/bin/sh
exit 0
SH
  chmod +x "$path"
}

setup_check_deps_repo() {
  CHECK_DEPS_REPO="$BATS_TEST_TMPDIR/repo"
  CHECK_DEPS_BIN="$BATS_TEST_TMPDIR/bin"
  mkdir -p \
    "$CHECK_DEPS_REPO/trackbed/skills/test" \
    "$CHECK_DEPS_REPO/node_modules/.bin" \
    "$CHECK_DEPS_BIN"
  cp "$BATS_TEST_DIRNAME/../Makefile" "$CHECK_DEPS_REPO/trackbed/Makefile"

  for tool in python3 shellcheck ruff mypy bats jq node npm; do
    create_fake_tool "$CHECK_DEPS_BIN/$tool"
  done
  create_fake_tool "$CHECK_DEPS_REPO/node_modules/.bin/prettier"
  create_fake_tool "$CHECK_DEPS_REPO/node_modules/.bin/tsc"
  create_fake_tool "$CHECK_DEPS_REPO/node_modules/.bin/eslint"

  cat >"$CHECK_DEPS_REPO/trackbed/skills/test/SKILL.md" <<'MD'
---
name: test
description: Test skill
---
MD

  init_empty_test_git_repo "$CHECK_DEPS_REPO"
  git -C "$CHECK_DEPS_REPO" add .
  git -C "$CHECK_DEPS_REPO" commit -m "initial" >/dev/null
  git -C "$CHECK_DEPS_REPO" branch -M main
  git -C "$CHECK_DEPS_REPO" switch -c feature >/dev/null
}

setup_makefile_contract_repo() {
  local repo_name="${1:-makefile-contract}"
  local parent_dir="${2:-$BATS_TEST_TMPDIR}"
  MAKEFILE_CONTRACT_REPO="$parent_dir/$repo_name"
  MAKEFILE_CONTRACT_BIN="$MAKEFILE_CONTRACT_REPO/bin"
  mkdir -p \
    "$MAKEFILE_CONTRACT_REPO/.agents/skills" \
    "$MAKEFILE_CONTRACT_REPO/plugin/config" \
    "$MAKEFILE_CONTRACT_REPO/plugin/evals" \
    "$MAKEFILE_CONTRACT_REPO/plugin/hooks" \
    "$MAKEFILE_CONTRACT_REPO/plugin/scripts" \
    "$MAKEFILE_CONTRACT_REPO/plugin/skills" \
    "$MAKEFILE_CONTRACT_REPO/plugin/tests" \
    "$MAKEFILE_CONTRACT_BIN"
  cp "$BATS_TEST_DIRNAME/../Makefile" "$MAKEFILE_CONTRACT_REPO/plugin/Makefile"
  cp "$BATS_TEST_DIRNAME/../scripts/coverage-gate.py" "$MAKEFILE_CONTRACT_REPO/plugin/scripts/"
  cp "$BATS_TEST_DIRNAME/../mypy.ini" "$MAKEFILE_CONTRACT_REPO/plugin/mypy.ini"

  cat >"$MAKEFILE_CONTRACT_REPO/plugin/config/coverage-production-sources.json" <<'JSON'
{
  "javascript": {
    "measured": [
      "plugin/scripts/example.js"
    ],
    "contract_only": {}
  },
  "python": {
    "measured": [
      "plugin/hooks/example.py"
    ],
    "contract_only": {
      "plugin/scripts/coverage-gate.py": ["plugin/tests/example.bats"],
      "plugin/scripts/contract.py": [
        "plugin/tests/example.bats"
      ]
    }
  },
  "shell": {
    "contract_only": {
      "plugin/hooks/example.sh": [
        "plugin/tests/example.bats"
      ]
    }
  }
}
JSON
  printf '"use strict";\n' >"$MAKEFILE_CONTRACT_REPO/plugin/scripts/example.js"
  printf 'VALUE = 1\n' >"$MAKEFILE_CONTRACT_REPO/plugin/hooks/example.py"
  printf 'VALUE = 2\n' >"$MAKEFILE_CONTRACT_REPO/plugin/scripts/contract.py"
  printf '#!/bin/sh\nexit 0\n' >"$MAKEFILE_CONTRACT_REPO/plugin/hooks/example.sh"
  printf '%s\n' \
    '#!/usr/bin/env bats' \
    '' \
    '@test "example shell contract" {' \
    '  true' \
    '}' \
    >"$MAKEFILE_CONTRACT_REPO/plugin/tests/example.bats"
}

setup_bats_runner_repo() {
  bats_require_minimum_version 1.5.0
  # A timed or parallel outer run exports these; each test sets its own mode.
  unset TRACKBED_BATS_TIMINGS TRACKBED_BATS_JOBS
  setup_makefile_contract_repo
  cp "$BATS_TEST_DIRNAME/run-tests.sh" "$MAKEFILE_CONTRACT_REPO/plugin/tests/run-tests.sh"
  mkdir -p "$MAKEFILE_CONTRACT_REPO/plugin/tests/test_helper/mocks" \
    "$MAKEFILE_CONTRACT_REPO/plugin/tests/nested"
  touch "$MAKEFILE_CONTRACT_REPO/plugin/tests/test_helper/mocks/git" \
    "$MAKEFILE_CONTRACT_REPO/plugin/tests/a suite.bats" \
    "$MAKEFILE_CONTRACT_REPO/plugin/tests/z.bats" \
    "$MAKEFILE_CONTRACT_REPO/plugin/tests/nested/ignored.bats"
  create_fake_tool "$MAKEFILE_CONTRACT_BIN/jq"
  cat >"$MAKEFILE_CONTRACT_BIN/bats" <<'SH'
#!/bin/sh
printf 'argc=%s\n' "$#"
printf 'arg=%s\n' "$@"
if [ "$2" = "${FAIL_SUITE:-}" ]; then exit 7; fi
SH
  chmod +x "$MAKEFILE_CONTRACT_BIN/bats"
}

@test "Bats timing mode runs every top-level suite once and reports to stderr" {
  setup_bats_runner_repo

  run --separate-stderr env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" LC_ALL=C TRACKBED_BATS_TIMINGS=1 \
    bash "$MAKEFILE_CONTRACT_REPO/plugin/tests/run-tests.sh"

  [ "$status" -eq 0 ]
  [ "$output" = "Running hook tests...
============================================
argc=2
arg=--tap
arg=a suite.bats
argc=2
arg=--tap
arg=example.bats
argc=2
arg=--tap
arg=z.bats
============================================
All tests passed!" ]
  [ "${#stderr_lines[@]}" -eq 3 ]
  local i=0 suite
  for suite in 'a suite.bats' example.bats z.bats; do
    [[ "${stderr_lines[$i]}" =~ ^BATS\ timing:\ suite=$suite\ elapsed_seconds=[0-9]+\ status=0$ ]] || false
    i=$((i + 1))
  done
}

@test "Bats timing mode preserves focused paths with spaces and failure status" {
  setup_bats_runner_repo

  run --separate-stderr env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" TRACKBED_BATS_TIMINGS=1 FAIL_SUITE='a suite.bats' \
    bash "$MAKEFILE_CONTRACT_REPO/plugin/tests/run-tests.sh" 'a suite.bats'

  [ "$status" -eq 7 ]
  [[ "$output" == *$'argc=2\narg=--tap\narg=a suite.bats' ]] || false
  [[ "$output" != *'All tests passed!'* ]] || false
  [ "${#stderr_lines[@]}" -eq 1 ]
  [[ "$stderr" =~ ^BATS\ timing:\ suite=a\ suite.bats\ elapsed_seconds=[0-9]+\ status=7$ ]] || false
}

@test "Bats timing mode records failures and continues through remaining suites" {
  setup_bats_runner_repo

  run --separate-stderr env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" LC_ALL=C TRACKBED_BATS_TIMINGS=1 FAIL_SUITE=example.bats \
    bash "$MAKEFILE_CONTRACT_REPO/plugin/tests/run-tests.sh"

  [ "$status" -eq 7 ]
  [ "${#stderr_lines[@]}" -eq 3 ]
  [[ "${stderr_lines[1]}" =~ suite=example.bats\ elapsed_seconds=[0-9]+\ status=7$ ]] || false
  [[ "${stderr_lines[2]}" =~ suite=z.bats\ elapsed_seconds=[0-9]+\ status=0$ ]] || false
  [[ "$output" == *'arg=z.bats'* ]] || false
  [[ "$output" != *'All tests passed!'* ]] || false
}

@test "Bats runner retains one default TAP invocation unless timing is exactly enabled" {
  setup_bats_runner_repo
  local mode
  for mode in '' 0 true; do
    run --separate-stderr env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" LC_ALL=C TRACKBED_BATS_TIMINGS="$mode" \
      bash "$MAKEFILE_CONTRACT_REPO/plugin/tests/run-tests.sh"

    [ "$status" -eq 0 ]
    [[ "$output" == *$'argc=4\narg=--tap\narg=a suite.bats\narg=example.bats\narg=z.bats'* ]] || false
    [ -z "$stderr" ]
  done
}

create_fake_parallel() {
  local version="$1"
  printf '#!/bin/sh\nprintf "%%s\\n" "%s"\n' "$version" >"$MAKEFILE_CONTRACT_BIN/parallel"
  chmod +x "$MAKEFILE_CONTRACT_BIN/parallel"
}

@test "Bats parallel mode runs every suite in one parallel batch when none is marked" {
  setup_bats_runner_repo
  create_fake_parallel 'GNU parallel 20261022'

  run --separate-stderr env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" LC_ALL=C TRACKBED_BATS_JOBS=4 \
    bash "$MAKEFILE_CONTRACT_REPO/plugin/tests/run-tests.sh"

  [ "$status" -eq 0 ]
  [ "$output" = "Running hook tests...
============================================
argc=7
arg=--tap
arg=--jobs
arg=4
arg=--no-parallelize-within-files
arg=a suite.bats
arg=example.bats
arg=z.bats
============================================
All tests passed!" ]
  [ -z "$stderr" ]
}

@test "Bats parallel mode runs unmarked suites in parallel, then marked suites serially" {
  setup_bats_runner_repo
  create_fake_parallel 'GNU parallel 20261022'
  printf '# trackbed-bats: serial (fixture shares state)\n' >"$MAKEFILE_CONTRACT_REPO/plugin/tests/z.bats"

  run --separate-stderr env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" LC_ALL=C TRACKBED_BATS_JOBS=4 \
    bash "$MAKEFILE_CONTRACT_REPO/plugin/tests/run-tests.sh"

  [ "$status" -eq 0 ]
  [ "$output" = "Running hook tests...
============================================
argc=6
arg=--tap
arg=--jobs
arg=4
arg=--no-parallelize-within-files
arg=a suite.bats
arg=example.bats
argc=2
arg=--tap
arg=z.bats
============================================
All tests passed!" ]
  [ -z "$stderr" ]
}

@test "Bats parallel mode runs the serial suites after a parallel failure and keeps the first failure" {
  setup_bats_runner_repo
  create_fake_parallel 'GNU parallel 20261022'
  printf '# trackbed-bats: serial (fixture shares state)\n' >"$MAKEFILE_CONTRACT_REPO/plugin/tests/z.bats"
  local failing
  for failing in --jobs z.bats; do
    run env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" LC_ALL=C TRACKBED_BATS_JOBS=4 FAIL_SUITE="$failing" \
      bash "$MAKEFILE_CONTRACT_REPO/plugin/tests/run-tests.sh"

    [ "$status" -eq 7 ]
    [[ "$output" == *$'argc=2\narg=--tap\narg=z.bats'* ]] || false
    [[ "$output" != *'All tests passed!'* ]] || false
  done
}

@test "Bats parallel mode refuses to start without GNU parallel" {
  setup_bats_runner_repo
  # Shadows any parallel in /usr/bin; moreutils ships a different tool of that name.
  create_fake_parallel 'parallel from moreutils'

  run env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" TRACKBED_BATS_JOBS=4 \
    bash "$MAKEFILE_CONTRACT_REPO/plugin/tests/run-tests.sh"

  [ "$status" -eq 1 ]
  [[ "$output" == *"TRACKBED_BATS_JOBS=4 needs GNU parallel,"* ]] || false
  [[ "$output" != *"argc="* ]] || false

  run env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" TRACKBED_BATS_JOBS=4 \
    bash "$MAKEFILE_CONTRACT_REPO/plugin/tests/run-tests.sh" 'a suite.bats'

  [ "$status" -eq 0 ]
  [[ "$output" == *$'argc=2\narg=--tap\narg=a suite.bats'* ]] || false
}

@test "Bats runner keeps the serial default for one job and rejects invalid job counts" {
  setup_bats_runner_repo
  run env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" LC_ALL=C TRACKBED_BATS_JOBS=1 \
    bash "$MAKEFILE_CONTRACT_REPO/plugin/tests/run-tests.sh"

  [ "$status" -eq 0 ]
  [[ "$output" == *$'argc=4\narg=--tap\narg=a suite.bats\narg=example.bats\narg=z.bats'* ]] || false

  local jobs
  for jobs in -2 1.5 many; do
    run env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" TRACKBED_BATS_JOBS="$jobs" \
      bash "$MAKEFILE_CONTRACT_REPO/plugin/tests/run-tests.sh"

    [ "$status" -eq 2 ]
    [[ "$output" == *"TRACKBED_BATS_JOBS must be a whole number, got '$jobs'"* ]] || false
  done

  run env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" TRACKBED_BATS_JOBS=4 TRACKBED_BATS_TIMINGS=1 \
    bash "$MAKEFILE_CONTRACT_REPO/plugin/tests/run-tests.sh"

  [ "$status" -eq 2 ]
  [[ "$output" == *"unset TRACKBED_BATS_JOBS"* ]] || false
  [[ "$output" != *"argc="* ]] || false
}

@test "test-bats forwards BATS_JOBS to the runner only when set" {
  # An outer `make test BATS_JOBS=N` passes the value down through MAKEFLAGS.
  unset BATS_JOBS MAKEFLAGS MFLAGS MAKELEVEL
  run make -C "$BATS_TEST_DIRNAME/.." --no-print-directory --dry-run test-bats

  [ "$status" -eq 0 ]
  [ "$(printf '%s\n' "$output" | tail -n 1)" = "./tests/run-tests.sh" ]

  run make -C "$BATS_TEST_DIRNAME/.." --no-print-directory --dry-run test-bats BATS_JOBS=6

  [ "$status" -eq 0 ]
  [ "$(printf '%s\n' "$output" | tail -n 1)" = "TRACKBED_BATS_JOBS='6' ./tests/run-tests.sh" ]
}

create_fake_node_coverage_tool() {
  cat >"$MAKEFILE_CONTRACT_BIN/node" <<'SH'
#!/bin/sh
case "$1" in
  -e) exit 0 ;;
esac

reporter_one=
reporter_two=
destination_one=
destination_two=
for argument in "$@"; do
  case "$argument" in
    --test-reporter=*)
      if [ -z "$reporter_one" ]; then
        reporter_one=${argument#*=}
      else
        reporter_two=${argument#*=}
      fi
      ;;
    --test-reporter-destination=*)
      if [ -z "$destination_one" ]; then
        destination_one=${argument#*=}
      else
        destination_two=${argument#*=}
      fi
      ;;
  esac
done

write_report() {
  reporter="$1"
  destination="$2"
  case "$reporter" in
    spec)
      printf '%s\n' "${NODE_TEST_OUTPUT:-fake node tests passed}" >"$destination"
      ;;
    lcov)
      cat "$NODE_COVERAGE_FIXTURE" >"$destination"
      ;;
    *)
      echo "unexpected reporter: $reporter" >&2
      exit 2
      ;;
  esac
}

write_report "$reporter_one" "$destination_one"
write_report "$reporter_two" "$destination_two"
exit "${NODE_TEST_STATUS:-0}"
SH
  chmod +x "$MAKEFILE_CONTRACT_BIN/node"
}

write_node_lcov_record() {
  local path="$1"
  local line_hit="$2"
  local line_total="$3"
  local branch_hit="$4"
  local branch_total="$5"
  local function_hit="$6"
  local function_total="$7"
  cat >>"$MAKEFILE_CONTRACT_REPO/node-coverage.lcov" <<REPORT
TN:
SF:$path
FNF:$function_total
FNH:$function_hit
BRF:$branch_total
BRH:$branch_hit
LF:$line_total
LH:$line_hit
end_of_record
REPORT
}

@test "format dependency check accepts PRETTIER command from PATH" {
  BIN_DIR="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$BIN_DIR"
  create_fake_tool "$BIN_DIR/prettier"

  run env PATH="$BIN_DIR:$PATH" make -C "$BATS_TEST_DIRNAME/.." --no-print-directory check-format-deps PRETTIER=prettier

  [ "$status" -eq 0 ]
}

@test "format-check sends changed Python files to Ruff and propagates failures" {
  setup_check_deps_repo
  mkdir -p "$CHECK_DEPS_REPO/trackbed/scripts"
  printf 'VALUE = 0\n' >"$CHECK_DEPS_REPO/trackbed/scripts/modified.py"
  git -C "$CHECK_DEPS_REPO" add .
  git -C "$CHECK_DEPS_REPO" commit -m "add base Python source" >/dev/null
  git -C "$CHECK_DEPS_REPO" branch -f main HEAD
  printf 'VALUE = 1\n' >"$CHECK_DEPS_REPO/trackbed/scripts/committed.py"
  git -C "$CHECK_DEPS_REPO" add .
  git -C "$CHECK_DEPS_REPO" commit -m "add Python source" >/dev/null
  printf 'VALUE = 2\n' >"$CHECK_DEPS_REPO/trackbed/scripts/modified.py"
  printf 'VALUE = 2\n' >"$CHECK_DEPS_REPO/trackbed/scripts/untracked.py"
  cat >"$CHECK_DEPS_BIN/ruff" <<'SH'
#!/bin/sh
printf 'ruff-args=%s\n' "$*"
exit "${RUFF_EXIT_STATUS:-0}"
SH
  chmod +x "$CHECK_DEPS_BIN/ruff"

  run env PATH="$CHECK_DEPS_BIN:/usr/bin:/bin" make -C "$CHECK_DEPS_REPO/trackbed" --no-print-directory format-check FORMAT_BASE=main RUFF=ruff

  [ "$status" -eq 0 ]
  [[ "$output" == *"ruff-args=format --check --config"*"trackbed/scripts/committed.py"* ]] || false
  [[ "$output" == *"trackbed/scripts/modified.py"* ]] || false
  [[ "$output" == *"trackbed/scripts/untracked.py"* ]] || false

  run env PATH="$CHECK_DEPS_BIN:/usr/bin:/bin" RUFF_EXIT_STATUS=7 make -C "$CHECK_DEPS_REPO/trackbed" --no-print-directory format-check FORMAT_BASE=main RUFF=ruff

  [ "$status" -ne 0 ]
}

@test "format and format-check share changed files and settings with write or check modes" {
  setup_check_deps_repo
  CHECK_DEPS_REPO=$(cd "$CHECK_DEPS_REPO" && pwd -P)
  mkdir -p "$CHECK_DEPS_REPO/trackbed/scripts"
  printf 'base\n' >"$CHECK_DEPS_REPO/trackbed/scripts/modified.py"
  printf 'base\n' >"$CHECK_DEPS_REPO/modified.js"
  printf 'base\n' >"$CHECK_DEPS_REPO/deleted.py"
  git -C "$CHECK_DEPS_REPO" add .
  git -C "$CHECK_DEPS_REPO" commit -m "base sources" >/dev/null
  git -C "$CHECK_DEPS_REPO" branch -f main HEAD
  printf 'committed\n' >"$CHECK_DEPS_REPO/committed.py"
  printf 'committed\n' >"$CHECK_DEPS_REPO/committed.js"
  git -C "$CHECK_DEPS_REPO" add .
  git -C "$CHECK_DEPS_REPO" commit -m "committed sources" >/dev/null
  printf 'dirty\n' >"$CHECK_DEPS_REPO/trackbed/scripts/modified.py"
  printf 'dirty\n' >"$CHECK_DEPS_REPO/modified.js"
  printf 'untracked\n' >"$CHECK_DEPS_REPO/untracked.py"
  printf 'untracked\n' >"$CHECK_DEPS_REPO/untracked.md"
  rm "$CHECK_DEPS_REPO/deleted.py"
  for tool in ruff prettier; do
    cat >"$CHECK_DEPS_BIN/$tool" <<'SH'
#!/bin/sh
printf '%s:%s:%s\n' "${0##*/}" "$PWD" "$*"
exit "${FORMATTER_EXIT_STATUS:-0}"
SH
    chmod +x "$CHECK_DEPS_BIN/$tool"
  done

  run env PATH="$CHECK_DEPS_BIN:/usr/bin:/bin" make -C "$CHECK_DEPS_REPO/trackbed" --no-print-directory format FORMAT_BASE=main RUFF=ruff PRETTIER=prettier
  [ "$status" -eq 0 ]
  [[ "$output" == *"prettier:$CHECK_DEPS_REPO:--write --ignore-unknown committed.js modified.js untracked.md"* ]] || false
  [[ "$output" == *"ruff:$CHECK_DEPS_REPO:format --config $CHECK_DEPS_REPO/trackbed/.ruff.toml committed.py trackbed/scripts/modified.py untracked.py"* ]] || false
  write_output="$output"

  run env PATH="$CHECK_DEPS_BIN:/usr/bin:/bin" make -C "$CHECK_DEPS_REPO/trackbed" --no-print-directory format-check FORMAT_BASE=main RUFF=ruff PRETTIER=prettier
  [ "$status" -eq 0 ]
  [ "$(printf '%s' "$write_output" | sed 's/--write/--check/; s/format --config/format --check --config/')" = "$output" ]

  run env PATH="$CHECK_DEPS_BIN:/usr/bin:/bin" FORMATTER_EXIT_STATUS=7 make -C "$CHECK_DEPS_REPO/trackbed" --no-print-directory format FORMAT_BASE=main RUFF=ruff PRETTIER=prettier
  [ "$status" -ne 0 ]
}

@test "check-deps does not require skillspector without changed skill directories" {
  setup_check_deps_repo

  run env PATH="$CHECK_DEPS_BIN:/usr/bin:/bin" make -C "$CHECK_DEPS_REPO/trackbed" --no-print-directory check-deps SKILLSPECTOR_BASE=main

  [ "$status" -eq 0 ]
  [[ "$output" == *"All verification dependencies installed."* ]] || false
}

@test "check-deps requires skillspector when a skill directory changed" {
  setup_check_deps_repo
  printf '\nChanged.\n' >>"$CHECK_DEPS_REPO/trackbed/skills/test/SKILL.md"

  run env PATH="$CHECK_DEPS_BIN:/usr/bin:/bin" make -C "$CHECK_DEPS_REPO/trackbed" --no-print-directory check-deps SKILLSPECTOR_BASE=main

  [ "$status" -eq 2 ]
  [[ "$output" == *"skillspector not found. Install SkillSpector before running skill-security or verify."* ]] || false
}

@test "check-deps requires mypy" {
  setup_check_deps_repo
  rm "$CHECK_DEPS_BIN/mypy"

  run env PATH="$CHECK_DEPS_BIN:/usr/bin:/bin" make -C "$CHECK_DEPS_REPO/trackbed" --no-print-directory check-deps SKILLSPECTOR_BASE=main

  [ "$status" -eq 2 ]
  [[ "$output" == *"mypy not found. Install development dependencies from requirements-dev.txt before running lint or verify."* ]] || false
}

@test "check-deps only verifies dependencies" {
  run make -C "$BATS_TEST_DIRNAME/.." --no-print-directory --dry-run check-deps

  [ "$status" -eq 0 ]
  [[ "$output" == *"All verification dependencies installed."* ]] || false
  [[ "$output" != *"--severity="* ]] || false
  [[ "$output" != *"coverage-gate.py"*"node-lcov"* ]] || false
  [[ "$output" != *"run-skillspector.sh --changed"* ]] || false
}

@test "pr-verify runs the documented local Pull Request gates including coverage" {
  awk '
    $1 == "pr-verify:" {
      for (position = 2; position <= NF; position++) {
        if ($position == "test") found = 1
      }
    }
    END { exit !found }
  ' "$BATS_TEST_DIRNAME/../Makefile"

  run make -C "$BATS_TEST_DIRNAME/.." --no-print-directory --dry-run pr-verify

  [ "$status" -eq 0 ]
  [[ "$output" == *"All verification dependencies installed."* ]] || false
  [[ "$output" == *"--severity="* ]] || false
  [[ "$output" == *"prettier"*"--check"* ]] || false
  [[ "$output" == *"lint-skill-contracts.py"* ]] || false
  [[ "$output" == *"run-skillspector.sh --changed"* ]] || false
  [[ "$output" == *"coverage-gate.py"*"node-lcov"* ]] || false
  [[ "$output" == *"coverage-gate.py"*"python-trace"* ]] || false
  [[ "$output" == *"coverage-gate.py"*"bats-contracts"* ]] || false
}

@test "verify adds the standalone skill-review eval to the pr-verify gates" {
  run make -C "$BATS_TEST_DIRNAME/.." --no-print-directory --dry-run verify

  [ "$status" -eq 0 ]
  [[ "$output" == *"coverage-gate.py"*"node-lcov"* ]] || false
  [[ "$output" == *"evals/skill-review/run-eval.js --split all"* ]] || false
}

@test "npm check:deps aliases invoke the read-only dependency target" {
  [ "$(jq -r '.scripts["check:deps"]' "$BATS_TEST_DIRNAME/../../package.json")" = "make -C trackbed check-deps" ]
  [ "$(jq -r '.scripts["check:deps"]' "$BATS_TEST_DIRNAME/../package.json")" = "make check-deps" ]
}

@test "npm aliases resolve to defined Makefile targets" {
  local makefile="$BATS_TEST_DIRNAME/../Makefile"
  local manifest
  local target
  local missing=""

  for manifest in "$BATS_TEST_DIRNAME/../../package.json" "$BATS_TEST_DIRNAME/../package.json"; do
    while IFS= read -r target; do
      grep -Eq "^$target:" "$makefile" || missing="$missing $manifest -> $target"
    done < <(jq -r '.scripts[] | select(test("(^| )make ")) | sub("^.*make (-C [^ ]+ )?"; "") | split(" ")[0]' "$manifest")
  done

  [ -z "$missing" ] || {
    echo "npm scripts without Makefile targets:$missing"
    return 1
  }
}

@test "lint-shell uses the local virtualenv from repository paths containing spaces" {
  setup_makefile_contract_repo "repo with spaces"
  mkdir -p "$MAKEFILE_CONTRACT_REPO/.venv/bin"
  cat >"$MAKEFILE_CONTRACT_REPO/.venv/bin/shellcheck" <<'SH'
#!/bin/sh
printf 'venv-shellcheck=%s\n' "$0"
exit 0
SH
  chmod +x "$MAKEFILE_CONTRACT_REPO/.venv/bin/shellcheck"

  run env PATH="/usr/bin:/bin" \
    make -C "$MAKEFILE_CONTRACT_REPO/plugin" --no-print-directory lint-shell

  [ "$status" -eq 0 ]
  [[ "$output" == *"repo with spaces/.venv/bin/shellcheck"* ]] || false
}

@test "test-python discovers repository and maintenance tests" {
  run make -C "$BATS_TEST_DIRNAME/.." --no-print-directory --dry-run test-python

  [ "$status" -eq 0 ]
  [[ "$output" == *"unittest discover -s tests/python -p 'test_*.py'"* ]] || false
  [[ "$output" == *"unittest discover -s ../.agents/skills/trackbed:skill:audit-sources/scripts -p 'test_*.py'"* ]] || false
}

@test "Python static inventory accepts every registered production module" {
  setup_makefile_contract_repo

  run make -C "$MAKEFILE_CONTRACT_REPO/plugin" --no-print-directory check-python-static-inventory

  [ "$status" -eq 0 ]
  [[ "$output" == *"Python static inventory: 3 production files registered."* ]] || false
}

@test "typecheck-python checks the production inventory and reports scoped ratchets" {
  setup_makefile_contract_repo
  cat >"$MAKEFILE_CONTRACT_BIN/mypy" <<'SH'
#!/bin/sh
printf 'mypy-args=%s\n' "$*"
config_path=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --config-file)
      config_path="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
python3 - "$config_path" <<'PY'
import configparser
import sys

config = configparser.ConfigParser()
config.read(sys.argv[1])
codes = {
    code.strip()
    for code in config["mypy-changelog"]["disable_error_code"].split(",")
}
assert codes == {"assignment"}
print("mypy-ratchet-syntax=valid")
PY
SH
  chmod +x "$MAKEFILE_CONTRACT_BIN/mypy"

  run env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" make -C "$MAKEFILE_CONTRACT_REPO/plugin" --no-print-directory typecheck-python MYPY=mypy

  [ "$status" -eq 0 ]
  [[ "$output" == *"mypy ratchet exceptions (owner: repository maintainers):"*"changelog"* ]] || false
  [[ "$output" == *"mypy-args=--config-file plugin/mypy.ini plugin/hooks/example.py plugin/scripts/contract.py plugin/scripts/coverage-gate.py"* ]] || false
  [[ "$output" == *"mypy-ratchet-syntax=valid"* ]] || false
}

@test "typecheck-python validates the production inventory before mypy" {
  setup_makefile_contract_repo
  create_fake_tool "$MAKEFILE_CONTRACT_BIN/mypy"
  printf 'VALUE = 3\n' >"$MAKEFILE_CONTRACT_REPO/plugin/hooks/unlisted.py"

  run env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" make -C "$MAKEFILE_CONTRACT_REPO/plugin" --no-print-directory typecheck-python MYPY=mypy

  [ "$status" -ne 0 ]
  [[ "$output" == *"Python production files missing static inventory entries (1): plugin/hooks/unlisted.py"* ]] || false
}

@test "test-smoke covers representative Node Python and Bats contracts" {
  run make -C "$BATS_TEST_DIRNAME/.." --no-print-directory --dry-run test-smoke

  [ "$status" -eq 0 ]
  [[ "$output" == *"node --test tests/node/frontmatter.test.js tests/node/scorer.test.js"* ]] || false
  [[ "$output" == *"python3 -m unittest tests/python/test_git_command_parser.py"* ]] || false
  [[ "$output" == *"bats tests/linear-issue-implement-guidance.bats"* ]] || false
}

@test "test-changed passes FORMAT_BASE to the selection helper" {
  run make -C "$BATS_TEST_DIRNAME/.." --no-print-directory --dry-run test-changed FORMAT_BASE=origin/feature-base

  [ "$status" -eq 0 ]
  [[ "$output" == *'python3 scripts/changed-tests.py --base "origin/feature-base"'* ]] || false
}

@test "test-node-file requires NODE_TEST_FILE" {
  setup_makefile_contract_repo
  cat >"$MAKEFILE_CONTRACT_BIN/node" <<'SH'
#!/bin/sh
case "$1" in
  -e) exit 0 ;;
esac
exit 0
SH
  chmod +x "$MAKEFILE_CONTRACT_BIN/node"

  run env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" make -C "$MAKEFILE_CONTRACT_REPO/plugin" --no-print-directory test-node-file

  [ "$status" -eq 2 ]
  [[ "$output" == *"NODE_TEST_FILE is required"* ]] || false
}

@test "test-node-file forwards a path as one argument" {
  setup_makefile_contract_repo
  cat >"$MAKEFILE_CONTRACT_BIN/node" <<'SH'
#!/bin/sh
printf 'argc=%s\narg1=%s\narg2=%s\n' "$#" "$1" "$2"
SH
  chmod +x "$MAKEFILE_CONTRACT_BIN/node"

  run env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" make -C "$MAKEFILE_CONTRACT_REPO/plugin" --no-print-directory test-node-file NODE_TEST_FILE="tests/node/path with spaces.test.js"

  [ "$status" -eq 0 ]
  [[ "$output" == *"argc=2"* ]] || false
  [[ "$output" == *"arg1=--test"* ]] || false
  [[ "$output" == *"arg2=tests/node/path with spaces.test.js"* ]] || false
}

@test "test-python-file requires PYTHON_TEST_FILE" {
  run make -C "$BATS_TEST_DIRNAME/.." --no-print-directory test-python-file

  [ "$status" -eq 2 ]
  [[ "$output" == *"PYTHON_TEST_FILE is required"* ]] || false
}

@test "test-python-file forwards a path as one argument" {
  setup_makefile_contract_repo
  cat >"$MAKEFILE_CONTRACT_BIN/python3" <<'SH'
#!/bin/sh
printf 'argc=%s\narg1=%s\narg2=%s\narg3=%s\n' "$#" "$1" "$2" "$3"
SH
  chmod +x "$MAKEFILE_CONTRACT_BIN/python3"

  run env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" make -C "$MAKEFILE_CONTRACT_REPO/plugin" --no-print-directory test-python-file PYTHON_TEST_FILE="tests/python/path with spaces.py"

  [ "$status" -eq 0 ]
  [[ "$output" == *"argc=3"* ]] || false
  [[ "$output" == *"arg1=-m"* ]] || false
  [[ "$output" == *"arg2=unittest"* ]] || false
  [[ "$output" == *"arg3=tests/python/path with spaces.py"* ]] || false
}

@test "test-bats-file requires BATS_TEST_FILE" {
  run make -C "$BATS_TEST_DIRNAME/.." --no-print-directory test-bats-file BATS_TEST_FILE=

  [ "$status" -eq 2 ]
  [[ "$output" == *"BATS_TEST_FILE is required"* ]] || false
}

@test "test-bats-file forwards a path as one argument" {
  setup_makefile_contract_repo
  mkdir -p "$MAKEFILE_CONTRACT_REPO/plugin/tests/test_helper/mocks"
  touch "$MAKEFILE_CONTRACT_REPO/plugin/tests/test_helper/mocks/git"
  create_fake_tool "$MAKEFILE_CONTRACT_BIN/jq"
  cat >"$MAKEFILE_CONTRACT_BIN/bats" <<'SH'
#!/bin/sh
printf 'argc=%s\narg1=%s\n' "$#" "$1"
SH
  chmod +x "$MAKEFILE_CONTRACT_BIN/bats"

  run env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" make -C "$MAKEFILE_CONTRACT_REPO/plugin" --no-print-directory test-bats-file BATS_TEST_FILE="tests/path with spaces.bats"

  [ "$status" -eq 0 ]
  [[ "$output" == *"argc=1"* ]] || false
  [[ "$output" == *"arg1=tests/path with spaces.bats"* ]] || false
}

@test "test-convert composes Node contracts and the Bats CLI smoke" {
  run make -C "$BATS_TEST_DIRNAME/.." --no-print-directory --dry-run test-convert

  [ "$status" -eq 0 ]
  [[ "$output" == *"node --test tests/node/converter-core.test.js tests/node/converter-build.test.js tests/node/converter-integration.test.js tests/node/codex-cli.test.js tests/node/codex-hook-compat.test.js tests/node/legacy-install-cleanup.test.js"* ]] || false
  [[ "$output" == *"bats tests/convert-plugin.bats"* ]] || false
}

@test "test-convert fails before the Bats smoke when Node contracts fail" {
  setup_makefile_contract_repo
  mkdir -p "$MAKEFILE_CONTRACT_REPO/plugin/tests/test_helper/mocks"
  touch "$MAKEFILE_CONTRACT_REPO/plugin/tests/test_helper/mocks/git"
  create_fake_tool "$MAKEFILE_CONTRACT_BIN/jq"
  cat >"$MAKEFILE_CONTRACT_BIN/node" <<'SH'
#!/bin/sh
case "$1" in
  -e) exit 0 ;;
  --test)
    echo "NODE_CONTRACT_FAILED"
    exit 1
    ;;
esac
exit 0
SH
  cat >"$MAKEFILE_CONTRACT_BIN/bats" <<'SH'
#!/bin/sh
echo "BATS_SMOKE_RAN"
exit 0
SH
  chmod +x "$MAKEFILE_CONTRACT_BIN/node" "$MAKEFILE_CONTRACT_BIN/bats"

  run env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" make -C "$MAKEFILE_CONTRACT_REPO/plugin" --no-print-directory test-convert

  [ "$status" -ne 0 ]
  [[ "$output" == *"NODE_CONTRACT_FAILED"* ]] || false
  [[ "$output" != *"BATS_SMOKE_RAN"* ]] || false
}

@test "coverage-node preserves the Node test process exit status" {
  setup_makefile_contract_repo
  create_fake_node_coverage_tool
  write_node_lcov_record "scripts/example.js" 8 10 7 10 8 10

  run env PATH="$MAKEFILE_CONTRACT_BIN:$PATH" NODE_COVERAGE_FIXTURE="$MAKEFILE_CONTRACT_REPO/node-coverage.lcov" NODE_TEST_OUTPUT="fixture test failed" NODE_TEST_STATUS=7 make -C "$MAKEFILE_CONTRACT_REPO/plugin" --no-print-directory coverage-node

  [ "$status" -ne 0 ]
  [[ "$output" == *"fixture test failed"* ]] || false
  [[ "$output" == *"Error 7"* ]] || false
  [[ "$output" != *"Node production coverage"* ]] || false
}

@test "coverage-node rejects undercovered production on the actual Node runtime" {
  mkdir -p "$BATS_TEST_DIRNAME/../../.context"
  MAKEFILE_RUNTIME_ROOT=$(mktemp -d "$BATS_TEST_DIRNAME/../../.context/makefile-coverage-runtime.XXXXXX")
  setup_makefile_contract_repo "makefile-contract" "$MAKEFILE_RUNTIME_ROOT"
  mkdir -p \
    "$MAKEFILE_CONTRACT_REPO/plugin/node_modules/yaml" \
    "$MAKEFILE_CONTRACT_REPO/plugin/tests/node"
  printf 'module.exports = {};\n' >"$MAKEFILE_CONTRACT_REPO/plugin/node_modules/yaml/index.js"
  cat >"$MAKEFILE_CONTRACT_REPO/plugin/scripts/example.js" <<'JS'
"use strict";

function classify(value) {
  if (value > 20) return "very-large";
  if (value > 10) return "large";
  if (value > 5) return "medium";
  if (value > 0) return "small";
  return "none";
}

function unused(value) {
  if (value > 3) return value + 1;
  if (value > 2) return value + 2;
  if (value > 1) return value + 3;
  return value + 4;
}

module.exports = { classify, unused };
JS
  {
    printf '%s\n' \
      '"use strict";' \
      'const assert = require("node:assert/strict");' \
      'const test = require("node:test");' \
      'const { classify } = require("../../scripts/example.js");' \
      'test("covers one production path and many test lines", () => {'
    for value in $(seq 1 120); do
      printf '  assert.equal(%d, %d);\n' "$value" "$value"
    done
    printf '%s\n' \
      '  assert.equal(classify(25), "very-large");' \
      '});'
  } >"$MAKEFILE_CONTRACT_REPO/plugin/tests/node/coverage-runtime.test.js"

  run make -C "$MAKEFILE_CONTRACT_REPO/plugin" --no-print-directory coverage-node NODE_TEST_FILES=tests/node/coverage-runtime.test.js

  [ "$status" -ne 0 ]
  [[ "$output" == *"Node coverage below baseline"* ]] || false
}

@test "coverage-python reads trace output from the Makefile runners" {
  mkdir -p "$BATS_TEST_DIRNAME/../../.context"
  MAKEFILE_RUNTIME_ROOT=$(mktemp -d "$BATS_TEST_DIRNAME/../../.context/makefile-coverage-runtime.XXXXXX")
  setup_makefile_contract_repo "makefile-contract" "$MAKEFILE_RUNTIME_ROOT"
  mkdir -p "$MAKEFILE_CONTRACT_REPO/plugin/maintenance"
  cat >"$MAKEFILE_CONTRACT_REPO/plugin/tests/test_example.py" <<'PYTHON'
import unittest

from hooks import example


class ExampleTest(unittest.TestCase):
    def test_value(self):
        self.assertEqual(example.VALUE, 1)
PYTHON
  cp "$MAKEFILE_CONTRACT_REPO/plugin/tests/test_example.py" \
    "$MAKEFILE_CONTRACT_REPO/plugin/maintenance/test_maintenance.py"

  run make -C "$MAKEFILE_CONTRACT_REPO/plugin" --no-print-directory coverage-python \
    PYTHON_TEST_DIR=tests PYTHON_MAINTENANCE_TEST_DIR=maintenance

  [ "$status" -eq 0 ]
  [[ "$output" == *"Python production aggregate: 100.00%"* ]] || false
}

@test "coverage-bats-contract accepts a complete shell source mapping" {
  setup_makefile_contract_repo

  run make -C "$MAKEFILE_CONTRACT_REPO/plugin" --no-print-directory coverage-bats-contract

  [ "$status" -eq 0 ]
  [[ "$output" == *"Shell source-to-contract inventory proxy: 1 production file mapped"* ]] || false
  [[ "$output" == *"not measured execution coverage"* ]] || false
}

@test "pre-commit runs the authoritative installed resource checker" {
  run make -C "$BATS_TEST_DIRNAME/.." --no-print-directory --dry-run pre-commit

  [ "$status" -eq 0 ]
  [[ "$output" == *"node scripts/check-installed-resources.js"* ]] || false
}

@test "required browser target selects the interaction case and propagates failure" {
  setup_makefile_contract_repo
  cat >"$MAKEFILE_CONTRACT_BIN/bats" <<'SH'
#!/bin/sh
printf 'required=%s\narg=%s\n' "$TRACKBED_REQUIRE_BROWSER_SMOKE" "$1"
printf 'filter=%s\nfile=%s\n' "$2" "$3"
exit 7
SH
  chmod +x "$MAKEFILE_CONTRACT_BIN/bats"

  run env PATH="$MAKEFILE_CONTRACT_BIN:/usr/bin:/bin" make -C "$MAKEFILE_CONTRACT_REPO/plugin" --no-print-directory test-walkthrough-browser

  [ "$status" -ne 0 ]
  [[ "$output" == *"required=1"* ]] || false
  [[ "$output" == *"arg=--filter"* ]] || false
  [[ "$output" == *'filter=^PR walkthrough supports initial render, tab switch, search, and tour navigation$'* ]] || false
  [[ "$output" == *"file=tests/pr-walkthrough.bats"* ]] || false
}

@test "Python 3.8 compatibility target refuses a different runtime under optimization" {
  run env PYTHONOPTIMIZE=1 make -C "$BATS_TEST_DIRNAME/.." --no-print-directory test-python38-compatibility PYTHON38=python3

  [ "$status" -ne 0 ]
  [[ "$output" == *"Use Python 3.8 for this compatibility check"* ]] || false
}
