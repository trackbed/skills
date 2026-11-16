#!/usr/bin/env bats

@test "CLAUDE.md delegates exclusively to the canonical AGENTS.md instructions" {
	project_root="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
	expected="$BATS_TEST_TMPDIR/CLAUDE.md"
	printf '%s\n' '@AGENTS.md' >"$expected"

	run cmp -s "$expected" "$project_root/CLAUDE.md"

	[ "$status" -eq 0 ]
}

@test "maintainer source and focused-test pointers resolve from the repository root" {
	project_root="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
	run python3 - "$project_root" <<'PYTEST'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
code_map = (root / "trackbed/docs/code-map.md").read_text()
for row in code_map.splitlines():
    if not row.startswith("| "):
        continue
    cells = row.split(" | ")
    if len(cells) < 3:
        continue
    for path in re.findall(r"`(trackbed/[^`]+)`", cells[1]):
        if re.fullmatch(r"[A-Za-z0-9_./:-]+", path):
            assert (root / path).exists(), path
for path in re.findall(r"(?:BATS|NODE|PYTHON)_TEST_FILE=([A-Za-z0-9_./-]+\.(?:bats|py|js))", code_map):
    assert (root / "trackbed" / path).is_file(), path
for owner in ["Setup and installation discovery", "Contract configuration and schemas",
              "Local maintenance skills", "Shared workflow and findings contracts",
              "Shared audit and writing methods"]:
    assert f"| {owner} |" in code_map, owner
PYTEST
	[ "$status" -eq 0 ]
}
