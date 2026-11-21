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

@test "scripts README classifies every top-level script the way the Codex converter ships it" {
	project_root="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
	run python3 - "$project_root" <<'PYTEST'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
scripts = root / "trackbed/scripts"
readme = (scripts / "README.md").read_text()
transformer = (scripts / "convert-plugin/codex-transformer.js").read_text()

body = transformer.split("function sharedRuntimeFor(", 1)[1].split("\n}\n", 1)[0]
shipped = set(re.findall(r'sourceFile:\s*path\.join\(\s*plugin\.root,\s*"scripts",\s*"([^"/]+)"\s*,?\s*\)', body))
assert shipped, "no top-level scripts found in sharedRuntimeFor"

def rows(heading):
    section = readme.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]
    return [re.match(r"\| `([^`]+)` \|", line).group(1) for line in section.splitlines() if re.match(r"\| `[^`]+` \|", line)]

runtime = rows("Runtime Helpers")
maintainer = rows("Maintainer Tools")
files = {path.name for path in scripts.iterdir() if path.is_file() and path.name != "README.md" and not path.name.startswith(".")}

assert len(runtime) == len(set(runtime)) and len(maintainer) == len(set(maintainer)), "duplicate rows"
assert set(runtime) == shipped, ("runtime rows differ from sharedRuntimeFor", sorted(set(runtime) ^ shipped))
assert set(runtime) | set(maintainer) == files, ("rows differ from files", sorted((set(runtime) | set(maintainer)) ^ files))
assert not set(runtime) & set(maintainer), "file listed as both kinds"
for test_path in re.findall(r"\| `(tests/[^`]+)` \|", readme):
    assert (root / "trackbed" / test_path).is_file(), test_path
PYTEST
	[ "$status" -eq 0 ]
}

@test "AGENTS.md links the add-a-script checklist, which names all four requirements" {
	project_root="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
	run python3 - "$project_root" <<'PYTEST'
from pathlib import Path
import sys

root = Path(sys.argv[1])
adding = (root / "AGENTS.md").read_text().split("## Adding Components", 1)[1].split("\n## ", 1)[0]
assert "trackbed/scripts/README.md#adding-a-script" in adding
checklist = (root / "trackbed/scripts/README.md").read_text().split("\n## Adding a Script\n", 1)[1]
for requirement in ["coverage-production-sources.json", "sharedRuntimeFor", "Node core modules", "jsconfig.json"]:
    assert requirement in checklist, requirement
PYTEST
	[ "$status" -eq 0 ]
}
