#!/usr/bin/env bats

# Static checks for the eval suites that scripts/skill-eval-compare.js runs.
# Nothing here starts a model: the tests validate the case files and build each
# Git fixture, so a broken case fails here instead of in a paid eval run.

plugin_root() {
  cd "$BATS_TEST_DIRNAME/.." && pwd -P
}

repo_root() {
  cd "$(plugin_root)/.." && pwd -P
}

suite_dirs() {
  local config
  for config in "$(plugin_root)"/evals/*/suite.json; do
    [ -f "$config" ] && dirname "$config"
  done
}

case_dirs() {
  local prompt
  for prompt in "$1"/*/prompt.md; do
    [ -f "$prompt" ] && dirname "$prompt"
  done
}

# The eval runner ends a settings block at the first three hyphens it meets,
# even inside a regex, and then fails to load the case.
settings_block_is_closed() {
  awk '
    NR == 1 { if ($0 != "---") exit 1; next }
    $0 == "---" { closed = 1; exit }
    index($0, "---") { exit 1 }
    END { exit closed ? 0 : 1 }
  ' "$1"
}

@test "every eval suite declares only the grants the compare script reads" {
  local found=0 suite
  while IFS= read -r suite; do
    found=$((found + 1))
    jq -e '
      type == "object"
      and (keys - ["allow_tools", "scaffold"] == [])
      and ((.allow_tools // []) | type == "array" and all(.[]; type == "string" and length > 0))
      and ((.scaffold // false) | type == "boolean")
    ' "$suite/suite.json" > /dev/null || {
      echo "invalid grants: $suite/suite.json"
      return 1
    }
  done < <(suite_dirs)
  [ "$found" -gt 0 ]
}

@test "every eval case is tagged with its suite, named after its folder, and checks that the skill fired" {
  local suite case_dir name grader graders found=0
  while IFS= read -r suite; do
    while IFS= read -r case_dir; do
      found=$((found + 1))
      name=$(basename "$case_dir")
      grep -Eq "^tags: \[([^]]*, )?$(basename "$suite")(, [^]]*)?\]$" "$case_dir/prompt.md" || {
        echo "$name: prompt.md is not tagged $(basename "$suite")"
        return 1
      }
      if [ -f "$case_dir/case.yaml" ]; then
        grep -Fxq "name: $name" "$case_dir/case.yaml" || {
          echo "$name: case.yaml name differs from the folder"
          return 1
        }
        grep -Fxq 'schema_version: "1.1"' "$case_dir/case.yaml" || {
          echo "$name: case.yaml needs schema_version \"1.1\""
          return 1
        }
      fi
      settings_block_is_closed "$case_dir/prompt.md" || {
        echo "$name: prompt.md settings contain --- before they close"
        return 1
      }
      graders=0
      for grader in "$case_dir"/graders/*.md; do
        [ -f "$grader" ] || continue
        graders=$((graders + 1))
        settings_block_is_closed "$grader" || {
          echo "$name: $(basename "$grader") settings contain --- before they close"
          return 1
        }
        grep -Eq '^type: (regex|tool_used|tool_order|file_exists|llm|baseline)$' "$grader" || {
          echo "$name: $(basename "$grader") has no known grader type"
          return 1
        }
        if grep -Fxq 'type: llm' "$grader"; then
          grep -q '^PASS if ' "$grader" && grep -q '^FAIL if ' "$grader" || {
            echo "$name: $(basename "$grader") needs PASS if and FAIL if conditions"
            return 1
          }
        fi
      done
      [ "$graders" -ge 2 ] || {
        echo "$name: needs a result check besides the skill-fired check"
        return 1
      }
      grep -Fxq 'tool: Skill' "$case_dir/graders/skill-fired.md" || {
        echo "$name: graders/skill-fired.md must check the Skill tool"
        return 1
      }
    done < <(case_dirs "$suite")
  done < <(suite_dirs)
  [ "$found" -gt 0 ]
}

@test "eval case names are unique across suites" {
  local duplicates
  duplicates=$(
    while IFS= read -r suite; do
      case_dirs "$suite"
    done < <(suite_dirs) | xargs -n 1 basename | sort | uniq -d
  )
  [ -z "$duplicates" ] || {
    echo "duplicate case names: $duplicates"
    return 1
  }
}

@test "every scaffold script builds a feature branch ahead of a local origin" {
  local suite case_dir name script workspace found=0
  while IFS= read -r suite; do
    while IFS= read -r case_dir; do
      [ -f "$case_dir/case.yaml" ] || continue
      script=$(sed -n 's/^  scaffold_script: //p' "$case_dir/case.yaml")
      [ -n "$script" ] || continue
      found=$((found + 1))
      name=$(basename "$case_dir")
      [ -x "$case_dir/$script" ] || {
        echo "$name: $script is not executable"
        return 1
      }
      workspace="$BATS_TEST_TMPDIR/$name"
      mkdir -p "$workspace"
      # The eval runner starts scaffold scripts with a minimal environment.
      (cd "$workspace" && env -i PATH="$PATH" HOME="$BATS_TEST_TMPDIR/home" TERM=dumb bash "$case_dir/$script") || {
        echo "$name: $script failed"
        return 1
      }
      [ "$(git -C "$workspace" symbolic-ref --short refs/remotes/origin/HEAD)" = "origin/main" ]
      [ "$(git -C "$workspace" branch --show-current)" != "main" ]
      [ "$(git -C "$workspace" rev-list --count origin/main..HEAD)" -ge 1 ]
      [ -z "$(git -C "$workspace" status --porcelain)" ]
      # Stored fixture manifests come back under their real name.
      [ -z "$(git -C "$workspace" ls-files '*package.fixture.json')" ]
    done < <(case_dirs "$suite")
  done < <(suite_dirs)
  [ "$found" -gt 0 ]
}

@test "fixture package manifests are stored under a name dependency scanners skip" {
  run find "$(plugin_root)/evals" -path '*/fixtures/*' -name package.json

  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "eval fixture scripts are included in the shell lint gate" {
  run make --no-print-directory -C "$(plugin_root)" -n lint-shell

  [ "$status" -eq 0 ]
  [[ "$output" == *'evals/_lib/*.sh'* ]]
  [[ "$output" == *'evals/*/*/scaffold.sh'* ]]
}

@test "eval run output stays out of Git" {
  run git -C "$(repo_root)" check-ignore -q trackbed/evals/results/2026-01-01/report.html

  [ "$status" -eq 0 ]
}

@test "skill-eval-compare make target needs a suite and forwards its options" {
  run make --no-print-directory -C "$(plugin_root)" -n skill-eval-compare \
    SUITE=demo BASE=origin/main RUNS=5 ARGS='--concurrency 4'

  [ "$status" -eq 0 ]
  [[ "$output" == *'node scripts/skill-eval-compare.js "demo" --base "origin/main" --runs "5" --concurrency 4'* ]]

  run make --no-print-directory -C "$(plugin_root)" skill-eval-compare

  [ "$status" -ne 0 ]
  [[ "$output" == *'SUITE=<suite>'* ]]
}

@test "skill-eval-compare prints usage and refuses an unknown suite before any run" {
  run node "$(plugin_root)/scripts/skill-eval-compare.js" --help

  [ "$status" -eq 0 ]
  [[ "$output" == *'Usage: node scripts/skill-eval-compare.js <suite>'* ]]

  run node "$(plugin_root)/scripts/skill-eval-compare.js" no-such-suite

  [ "$status" -eq 1 ]
  [[ "$output" == *'skill-eval-compare: No eval suite "no-such-suite"'* ]]
}
