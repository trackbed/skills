from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tests.test_helper.script_loader import load_script

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "changed-tests.py"
changed_tests = load_script("changed_tests", SCRIPT_PATH)

SKILL = "plugin/skills/pr:create/SKILL.md"
INVENTORY: dict[str, Any] = {
    "skill_contracts": [
        {"kind": "guidance", "suite": "plugin/tests/pr-create-guidance.bats", "skills": [SKILL]},
        {"kind": "executable", "suite": "plugin/tests/python/test_pr_create_preflight.py", "skills": [SKILL]},
        {"kind": "guidance", "suite": "plugin/tests/other-guidance.bats", "skills": ["plugin/skills/other/SKILL.md"]},
    ],
    "javascript": {"measured": [], "contract_only": {"plugin/scripts/check.js": ["plugin/tests/check.bats"]}},
    "python": {"measured": [], "contract_only": {"plugin/scripts/risk-signals.py": ["plugin/tests/risk.bats"]}},
    "shell": {"contract_only": {"plugin/scripts/resolve-base.sh": ["plugin/tests/resolve-base.bats"]}},
}
SUITES = [
    "plugin/tests/pr-create-guidance.bats",
    "plugin/tests/python/test_pr_create_preflight.py",
    "plugin/tests/other-guidance.bats",
    "plugin/tests/check.bats",
    "plugin/tests/risk.bats",
    "plugin/tests/resolve-base.bats",
    "plugin/tests/python/test_risk_signals.py",
    "plugin/tests/node/check.test.js",
    "plugin/tests/node/frontmatter.test.js",
    ".agents/skills/audit/scripts/test_normalize.py",
]


def git(root: Path, *args: str) -> str:
    command = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "-C", str(root), *args]
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


class Fixture(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name).resolve()
        self.plugin = self.repo / "plugin"
        self.write("plugin/config/coverage-production-sources.json", json.dumps(INVENTORY))
        for suite in SUITES:
            self.write(suite, "")

    def write(self, path: str, text: str = "change\n") -> None:
        file = self.repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")

    def select(self, *paths: str) -> tuple[dict[str, list[str]], list[str]]:
        result: tuple[dict[str, list[str]], list[str]] = changed_tests.select_suites(
            list(paths), INVENTORY, self.repo, "plugin"
        )
        return result


class SelectSuitesTests(Fixture):
    def test_a_changed_skill_selects_its_skill_contract_suites(self) -> None:
        suites, unmapped = self.select(SKILL)
        self.assertEqual(
            suites,
            {
                "plugin/tests/pr-create-guidance.bats": [f"{SKILL} (skill contract)"],
                "plugin/tests/python/test_pr_create_preflight.py": [f"{SKILL} (skill contract)"],
            },
        )
        self.assertEqual(unmapped, [])

    def test_any_file_in_a_skill_directory_selects_that_skills_suites(self) -> None:
        suites, _ = self.select("plugin/skills/pr:create/references/body.md")
        self.assertEqual(
            sorted(suites), ["plugin/tests/pr-create-guidance.bats", "plugin/tests/python/test_pr_create_preflight.py"]
        )

    def test_a_mapped_source_selects_its_contract_suites_and_name_matched_unit_tests(self) -> None:
        suites, unmapped = self.select("plugin/scripts/risk-signals.py", "plugin/scripts/check.js")
        self.assertEqual(
            suites,
            {
                "plugin/tests/check.bats": ["plugin/scripts/check.js (contract_only)"],
                "plugin/tests/node/check.test.js": ["plugin/scripts/check.js (name match)"],
                "plugin/tests/python/test_risk_signals.py": ["plugin/scripts/risk-signals.py (name match)"],
                "plugin/tests/risk.bats": ["plugin/scripts/risk-signals.py (contract_only)"],
            },
        )
        self.assertEqual(unmapped, [])

    def test_an_unmapped_source_still_selects_its_name_matched_unit_test(self) -> None:
        suites, unmapped = self.select(
            "plugin/scripts/convert-plugin/frontmatter.js", ".agents/skills/audit/scripts/normalize.py"
        )
        self.assertEqual(
            sorted(suites), [".agents/skills/audit/scripts/test_normalize.py", "plugin/tests/node/frontmatter.test.js"]
        )
        self.assertEqual(unmapped, [])

    def test_a_changed_test_file_selects_itself(self) -> None:
        suites, unmapped = self.select(
            "plugin/tests/other-guidance.bats",
            "plugin/tests/node/frontmatter.test.js",
            "plugin/tests/python/test_risk_signals.py",
        )
        self.assertEqual(
            {suite: reasons[0] for suite, reasons in suites.items()},
            {
                "plugin/tests/node/frontmatter.test.js": "plugin/tests/node/frontmatter.test.js (changed test)",
                "plugin/tests/other-guidance.bats": "plugin/tests/other-guidance.bats (changed test)",
                "plugin/tests/python/test_risk_signals.py": "plugin/tests/python/test_risk_signals.py (changed test)",
            },
        )
        self.assertEqual(unmapped, [])

    def test_files_without_a_mapping_are_reported(self) -> None:
        suites, unmapped = self.select(
            "README.md",
            "plugin/Makefile",
            "plugin/skills/unregistered/SKILL.md",
            "plugin/tests/test_helper/helper.bash",
        )
        self.assertEqual(suites, {})
        self.assertEqual(
            unmapped,
            [
                "README.md",
                "plugin/Makefile",
                "plugin/skills/unregistered/SKILL.md",
                "plugin/tests/test_helper/helper.bash",
            ],
        )

    def test_a_deleted_test_or_missing_suite_is_not_run(self) -> None:
        (self.repo / "plugin/tests/check.bats").unlink()
        suites, unmapped = self.select("plugin/tests/deleted.bats", "plugin/scripts/check.js")
        self.assertEqual(list(suites), ["plugin/tests/node/check.test.js"])
        self.assertEqual(unmapped, [])

    def test_name_matching_ignores_files_outside_the_plugin_and_maintenance_skills(self) -> None:
        _, unmapped = self.select("site/scripts/check.js")
        self.assertEqual(unmapped, ["site/scripts/check.js"])

    def test_one_suite_lists_every_file_that_selected_it(self) -> None:
        suites, _ = self.select(SKILL, "plugin/skills/pr:create/scripts/helper.sh")
        self.assertEqual(
            suites["plugin/tests/pr-create-guidance.bats"],
            [f"{SKILL} (skill contract)", "plugin/skills/pr:create/scripts/helper.sh (skill contract)"],
        )


class RunnerCommandTests(Fixture):
    def test_commands_group_by_runner_with_paths_relative_to_the_plugin(self) -> None:
        commands = changed_tests.runner_commands(
            [
                "plugin/tests/risk.bats",
                "plugin/tests/node/check.test.js",
                ".agents/skills/audit/scripts/test_normalize.py",
                "plugin/tests/check.bats",
                "plugin/tests/python/test_risk_signals.py",
            ],
            self.repo,
            self.plugin,
        )
        self.assertEqual(
            commands,
            [
                ("node", ["node", "--test", "tests/node/check.test.js"]),
                (
                    "python",
                    [
                        "python3",
                        "-m",
                        "unittest",
                        "discover",
                        "-s",
                        "../.agents/skills/audit/scripts",
                        "-p",
                        "test_normalize.py",
                    ],
                ),
                (
                    "python",
                    ["python3", "-m", "unittest", "discover", "-s", "tests/python", "-p", "test_risk_signals.py"],
                ),
                ("bats", ["bats", "tests/check.bats", "tests/risk.bats"]),
            ],
        )


class ChangedFilesTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name).resolve()
        git(self.repo, "init", "-q", "-b", "main")
        for name in ("committed.txt", "staged.txt", "unstaged.txt", "renamed.txt", "same.txt"):
            (self.repo / name).write_text(f"{name}\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "base")
        git(self.repo, "checkout", "-q", "-b", "work")

    def test_committed_staged_unstaged_untracked_and_renamed_paths_count(self) -> None:
        (self.repo / "committed.txt").write_text("changed\n", encoding="utf-8")
        git(self.repo, "mv", "renamed.txt", "moved.txt")
        git(self.repo, "commit", "-q", "-am", "work")
        (self.repo / "staged.txt").write_text("changed\n", encoding="utf-8")
        git(self.repo, "add", "staged.txt")
        (self.repo / "unstaged.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / "dir with space").mkdir()
        (self.repo / "dir with space" / "new.txt").write_text("new\n", encoding="utf-8")

        paths, has_base = changed_tests.changed_files("main", self.repo)

        self.assertTrue(has_base)
        self.assertEqual(
            paths, ["committed.txt", "dir with space/new.txt", "moved.txt", "renamed.txt", "staged.txt", "unstaged.txt"]
        )

    def test_changes_on_the_base_after_the_branch_point_do_not_count(self) -> None:
        git(self.repo, "checkout", "-q", "main")
        (self.repo / "same.txt").write_text("changed on main\n", encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", "main moves ahead")
        git(self.repo, "checkout", "-q", "work")
        (self.repo / "committed.txt").write_text("changed\n", encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", "work")

        self.assertEqual(changed_tests.changed_files("main", self.repo), (["committed.txt"], True))

    def test_a_missing_base_still_counts_uncommitted_files(self) -> None:
        (self.repo / "unstaged.txt").write_text("changed\n", encoding="utf-8")
        paths, has_base = changed_tests.changed_files("origin/missing", self.repo)
        self.assertFalse(has_base)
        self.assertEqual(paths, ["unstaged.txt"])

    def test_no_changes_returns_nothing(self) -> None:
        self.assertEqual(changed_tests.changed_files("main", self.repo), ([], True))


class MainTests(Fixture):
    def setUp(self) -> None:
        super().setUp()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "base")
        self.commands: list[tuple[list[str], Path]] = []
        self.statuses: dict[str, int] = {}

    def run_command(self, command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        self.commands.append((command, cwd))
        return subprocess.CompletedProcess(command, self.statuses.get(command[0], 0))

    def main(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = changed_tests.main(["--base", "main", *argv], self.repo, self.plugin, self.run_command)
        return status, out.getvalue(), err.getvalue()

    def test_no_changes_reports_that_nothing_ran_and_exits_zero(self) -> None:
        status, out, _ = self.main()
        self.assertEqual(status, 0)
        self.assertEqual(out, "No files changed against main; no tests ran.\n")
        self.assertEqual(self.commands, [])

    def test_a_changed_skill_runs_its_suites_and_explains_why(self) -> None:
        self.write(SKILL)
        status, out, _ = self.main()
        self.assertEqual(status, 0)
        self.assertIn(f"Selected suites: 2\n  tests/pr-create-guidance.bats\n    <- {SKILL} (skill contract)\n", out)
        self.assertEqual(
            [command for command, _ in self.commands],
            [
                ["python3", "-m", "unittest", "discover", "-s", "tests/python", "-p", "test_pr_create_preflight.py"],
                ["bats", "tests/pr-create-guidance.bats"],
            ],
        )
        self.assertEqual({cwd for _, cwd in self.commands}, {self.plugin})
        self.assertIn("all 2 selected suites passed", out)

    def test_unmapped_files_are_reported_and_nothing_runs(self) -> None:
        self.write("notes.md")
        status, out, _ = self.main()
        self.assertEqual(status, 0)
        self.assertIn("Changed files with no mapped suite: 1; choose a suite from docs/code-map.md\n  notes.md\n", out)
        self.assertIn("No tests ran.", out)
        self.assertEqual(self.commands, [])

    def test_every_runner_runs_and_a_failure_exits_one(self) -> None:
        self.write("plugin/scripts/check.js")
        self.write("plugin/scripts/risk-signals.py")
        self.statuses = {"node": 3, "bats": 1}
        status, _, err = self.main()
        self.assertEqual(status, 1)
        self.assertEqual([command[0] for command, _ in self.commands], ["node", "python3", "bats"])
        self.assertIn("node, bats suites failed", err)

    def test_a_missing_base_is_reported(self) -> None:
        self.write("notes.md")
        _, _, err = self.main("--base", "origin/missing")
        self.assertIn("origin/missing not found; only uncommitted and untracked files count.", err)


class RepositoryInventoryTests(unittest.TestCase):
    def test_the_real_inventory_maps_a_skill_and_a_source(self) -> None:
        plugin_root = SCRIPT_PATH.parents[1]
        inventory = json.loads((plugin_root / changed_tests.INVENTORY).read_text(encoding="utf-8"))
        plugin = plugin_root.name
        suites, unmapped = changed_tests.select_suites(
            [f"{plugin}/skills/pr:create/SKILL.md", f"{plugin}/scripts/changed-tests.py"],
            inventory,
            plugin_root.parent,
            plugin,
        )
        self.assertIn(f"{plugin}/tests/pr-create-guidance.bats", suites)
        self.assertIn(f"{plugin}/tests/python/test_changed_tests.py", suites)
        self.assertEqual(unmapped, [])


if __name__ == "__main__":
    unittest.main()
