#!/usr/bin/env bats

load 'test_helper/common'

setup() {
  SCOPE_HELPER="$BATS_TEST_DIRNAME/../scripts/lib/review-scope.sh"
  TMP_DIR=$(mktemp -d)
  init_test_git_repo "$TMP_DIR/work"
  cd "$TMP_DIR/work"
  BASE_COMMIT=$(git rev-parse HEAD)
  mkdir -p nested sibling
}

teardown() {
  rm -rf "$TMP_DIR"
}

@test "scope helper sets repository-relative values and caller directory from a subdirectory" {
  printf 'changed\n' >> tracked.txt
  printf 'new\n' > 'root é.txt'
  printf 'new\n' > 'sibling/quote"file.txt'
  cd nested

  run bash -c '
    source "$1"
    collect_review_scope --strict --base "$2" || exit 1
    [ "$PWD" = "$(git rev-parse --show-toplevel)" ] || exit 1
    [ "$BASE_REF" = "$2" ] || exit 1
    [ "$MERGE_BASE" = "$2" ] || exit 1
    [ -z "$STACK_CONTEXT" ] || exit 1
    while IFS= read -r path; do [ -f "$path" ] || exit 1; done <<< "$CHANGED_FILES"
    printf "%s\n" "$CHANGED_FILES"
  ' _ "$SCOPE_HELPER" "$BASE_COMMIT"

  [ "$status" -eq 0 ]
  [ "$output" = $'root é.txt\nsibling/quote"file.txt\ntracked.txt' ]
}

@test "scope helper forwards consumer exclusions and validates root previous-review state" {
  printf 'new\n' > OVERENGINEERING_REVIEW_OVERVIEW.md
  printf 'new\n' > sibling/OVERENGINEERING_REVIEW_OVERVIEW.md
  cd nested

  run bash -c '
    source "$1"
    collect_review_scope --strict --base "$2" --exclude-review-artifacts \
      --require-local-artifact OVERENGINEERING_REVIEW_OVERVIEW.md || exit 1
    printf "%s\n" "$CHANGED_FILES"
  ' _ "$SCOPE_HELPER" "$BASE_COMMIT"

  [ "$status" -eq 0 ]
  [ "$output" = sibling/OVERENGINEERING_REVIEW_OVERVIEW.md ]

  git -C .. add OVERENGINEERING_REVIEW_OVERVIEW.md
  run bash -c '
    source "$1"
    collect_review_scope --strict --base "$2" \
      --require-local-artifact OVERENGINEERING_REVIEW_OVERVIEW.md
  ' _ "$SCOPE_HELPER" "$BASE_COMMIT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"refusing branch-controlled review state"* ]] || false
}

@test "scope helper propagates collection and incomplete-field failures and removes temporary files" {
  mkdir -p "$TMP_DIR/plugin/scripts/lib" "$TMP_DIR/fields"
  cp "$SCOPE_HELPER" "$TMP_DIR/plugin/scripts/lib/review-scope.sh"
  cat > "$TMP_DIR/plugin/scripts/collect-review-diff.sh" <<'SH'
#!/usr/bin/env bash
printf 'partial\0'
exit "${COLLECTOR_EXIT:-0}"
SH
  chmod +x "$TMP_DIR/plugin/scripts/collect-review-diff.sh"
  for collector_exit in 0 1; do
    run env TMPDIR="$TMP_DIR/fields" COLLECTOR_EXIT="$collector_exit" bash -c '
      source "$1"
      collect_review_scope --strict
    ' _ "$TMP_DIR/plugin/scripts/lib/review-scope.sh"
    [ "$status" -ne 0 ]
    if [ "$collector_exit" -eq 0 ]; then
      [[ "$output" == *"Decoded review-diff fields were incomplete"* ]] || false
    else
      [[ "$output" == *"Base/diff collection failed"* ]] || false
    fi
    [ -z "$(find "$TMP_DIR/fields" -type f -print)" ]
  done
}

@test "untracked content handoff preserves raw names and omits excluded reports from a subdirectory" {
  SCOPE_HELPER="$SCOPE_HELPER" BASE_COMMIT="$BASE_COMMIT" WORK="$PWD" python3 - <<'PYTEST'
import os
from pathlib import Path
import subprocess

root = Path(os.environ["WORK"])
names = ['café.txt', 'sibling/quote"file.txt', 'sibling/back\\slash.txt', 'nested/tab\tfile.txt', 'sibling/glob[*?].txt', 'sibling/REVIEW_OVERVIEW.html']
expected = {}
for index, name in enumerate(names):
    expected[name] = f"content {index}\n"
    (root / name).write_text(expected[name])
(root / "REVIEW_OVERVIEW.html").write_text("excluded visual report\n")
(root / "REVIEW_OVERVIEW.md").write_text("excluded review report\n")
result = subprocess.run(
    ["bash", "-c", '''
source "$1"
collect_review_scope --base "$2" --strict --exclude-review-artifacts || exit 1
review_untracked_paths "$CHANGED_FILES"
''', "_", os.environ["SCOPE_HELPER"], os.environ["BASE_COMMIT"]],
    cwd=root / "nested", capture_output=True, check=True,
)
paths = result.stdout.decode().split("\0")
assert paths.pop() == "", paths
received = {name: (root / name).read_text() for name in paths}
assert received == expected, received
PYTEST
}

@test "untracked content handoff propagates Git listing failures" {
  mkdir "$TMP_DIR/bin"
  cat > "$TMP_DIR/bin/git" <<'SH'
#!/bin/sh
if [ "$1" = rev-parse ]; then
  printf '%s\n' "$PWD"
else
  echo 'listing failed' >&2
  exit 1
fi
SH
  chmod +x "$TMP_DIR/bin/git"
  run env PATH="$TMP_DIR/bin:$PATH" bash -c '
    source "$1"
    review_untracked_paths tracked.txt
  ' _ "$SCOPE_HELPER"
  [ "$status" -ne 0 ]
  [[ "$output" == *"listing failed"* ]] || false
}

@test "standard and team review handoffs use the raw untracked scope helper" {
  PLUGIN_ROOT="$BATS_TEST_DIRNAME/.." python3 - <<'PYTEST'
import os
from pathlib import Path

root = Path(os.environ["PLUGIN_ROOT"]) / "skills"
for relative in ["pr:code-review/SKILL.md", "pr:product-review/SKILL.md", "code:copy-review/SKILL.md",
                 "pr:code-review/references/team-mode.md", "pr:product-review/references/team-mode.md"]:
    text = (root / relative).read_text()
    assert '`review_untracked_paths "$CHANGED_FILES"`' in text, relative
    assert "decodes NUL records as raw repository-relative names" in text, relative
    assert "Before launching reviewers, the orchestrator runs" in text, relative
    assert "Pass the resulting paths and contents to agents, not the helper command" in text, relative
    assert "git ls-files --others --exclude-standard`" not in text, relative
PYTEST
}
