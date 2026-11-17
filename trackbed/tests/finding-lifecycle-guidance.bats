#!/usr/bin/env bats
#
# The Pull Request review loop shares one finding lifecycle: three producers
# read their previous report under it, and pr:resolve-review writes statuses
# from it. These tests pin the shared rules and keep the four skills on them.

setup() {
  cd "$BATS_TEST_DIRNAME/.."
  REFERENCE="shared/findings/references/finding-lifecycle.md"
  REFERENCE_PATH='${CLAUDE_PLUGIN_ROOT}/shared/findings/references/finding-lifecycle.md'
  CODE_REVIEW="skills/pr:code-review/SKILL.md"
  CONVENTION="skills/pr:convention-review/SKILL.md"
  OVERENGINEERING="skills/pr:overengineering-review/SKILL.md"
  RESOLVE_REVIEW="skills/pr:resolve-review/SKILL.md"
}

@test "the shared lifecycle defines the five statuses and nothing else" {
  local status
  for status in open addressed deferred acknowledged skipped; do
    grep -qF "| \`$status\` |" "$REFERENCE"
  done
  grep -qF "No other values." "$REFERENCE"
  grep -qF "Only \`addressed\` counts as previously addressed." "$REFERENCE"
}

@test "a finding the user chooses to defer is deferred, not open" {
  grep -qF "waiting on an owner, or the user chose to defer it." "$REFERENCE"
  run grep -qF "the user deferred the decision" "$REFERENCE"
  [ "$status" -eq 1 ]
}

@test "a carried-forward open or deferred finding stays active as open" {
  grep -qF "**Carry forward as active** a previous \`open\` or \`deferred\` finding that still applies." "$REFERENCE"
  grep -qF "set \`Resolution status: open\`, and note that it was carried forward from the previous review" "$REFERENCE"
}

@test "a settled acknowledged or skipped finding is not raised again" {
  grep -qF "**Treat as settled** a previous finding with \`Resolution status: acknowledged\` or \`skipped\` when the same root cause is still present and nothing new has turned up" "$REFERENCE"
  grep -qF "Do not raise a settled finding again as active, even when a reviewer still prefers a different approach." "$REFERENCE"
  grep -qF "acknowledged or skipped findings settled, not raised again" "$REFERENCE"
}

@test "an acknowledged finding with new evidence is raised again" {
  grep -qF "**Raise again** an \`acknowledged\` or \`skipped\` finding when there is new evidence." "$REFERENCE"
  grep -qF "It is active again with \`Resolution status: open\`, its previous ID, and the new evidence." "$REFERENCE"
}

@test "the four review-loop skills name the shared lifecycle" {
  local skill
  for skill in "$CODE_REVIEW" "$CONVENTION" "$OVERENGINEERING" "$RESOLVE_REVIEW"; do
    grep -qF "$REFERENCE_PATH" "$skill" || {
      echo "missing shared lifecycle path: $skill"
      false
    }
  done
}

@test "convention and overengineering reviews apply the settled rule" {
  grep -qF "**Treat as settled** a previous \`acknowledged\` or \`skipped\` finding under the shared settled rule" "$CONVENTION"
  grep -qF -- "- X acknowledged or skipped findings settled, not raised again" "$CONVENTION"
  grep -qF "an unchanged region means the decision is settled" "$OVERENGINEERING"
  grep -qF "how many acknowledged or skipped findings were settled and not raised again" "$OVERENGINEERING"
  grep -qF "uses each finding's \`Region fingerprint\` as the evidence" "$REFERENCE"
}

@test "overengineering review needs new evidence, not a changed file, to reopen a decision" {
  grep -qF "A changed \`Region fingerprint\` alone is not new evidence, because it records whole files" "$OVERENGINEERING"
  grep -qF "Without new evidence the decision stays settled" "$OVERENGINEERING"
  grep -qF "becomes \`Resolution status: open\` only when the supplemental batch cites new evidence" "$OVERENGINEERING"
  run grep -qF "raised again because its region changed" "$OVERENGINEERING"
  [ "$status" -eq 1 ]
  grep -qF "a changed fingerprint alone is not new evidence" "$REFERENCE"
}

@test "review-loop skills write no status outside the shared five" {
  run python3 - <<'PY'
import pathlib
import re

allowed = {"open", "addressed", "deferred", "acknowledged", "skipped"}
roots = [
    "skills/pr:code-review",
    "skills/pr:convention-review",
    "skills/pr:overengineering-review",
    "skills/pr:resolve-review",
    "shared/findings/references/finding-lifecycle.md",
]
problems = []
seen = 0
for root in roots:
    path = pathlib.Path(root)
    for file in [path] if path.is_file() else sorted(path.rglob("*.md")):
        for number, line in enumerate(file.read_text().splitlines(), 1):
            for match in re.finditer(r"Resolution status:\**\s*`?([a-z]+(?:\s*[|/]\s*[a-z]+)*)", line):
                seen += 1
                for value in re.split(r"\s*[|/]\s*", match.group(1)):
                    if value and value not in allowed:
                        problems.append(f"{file}:{number}: {value}")
if seen < 20:
    problems.append(f"only {seen} status values found; the scan is not reading them")
raise SystemExit("\n".join(problems) if problems else 0)
PY
  [ "$status" -eq 0 ] || {
    echo "$output"
    false
  }
}
