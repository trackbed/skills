"""Exercise the coverage gates with reports and inventory data in memory."""

import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tests.test_helper.script_loader import load_script

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "coverage-gate.py"
gate = load_script("coverage_gate", SCRIPT)

JS = "plugin/scripts/example.js"
PYTHON = "plugin/hooks/example.py"
SHELL = "plugin/hooks/example.sh"
SUITE = "plugin/tests/example.bats"
LOW = "plugin/hooks/low.py"


def lcov(path, lines=(8, 10), branches=(7, 10), functions=(8, 10)):
    return (
        f"TN:\nSF:{path}\nFNF:{functions[1]}\nFNH:{functions[0]}\n"
        f"BRF:{branches[1]}\nBRH:{branches[0]}\nLF:{lines[1]}\nLH:{lines[0]}\nend_of_record\n"
    )


def trace(path, coverage=35, lines=100):
    return f"{lines} {coverage}% example ({path})\n"


class CoverageGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="coverage gate ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.inventory_path = self.root / "inventory.json"
        self.data = {
            "javascript": {"measured": [JS], "contract_only": {}},
            "python": {"measured": [PYTHON], "contract_only": {}},
            "shell": {"contract_only": {SHELL: [SUITE]}},
        }
        for path in (JS, PYTHON, SHELL, SUITE):
            self.write(path, '@test "example" {\n  true\n}\n' if path == SUITE else "")

    def write(self, path, content):
        filename = self.root / path
        filename.parent.mkdir(parents=True, exist_ok=True)
        filename.write_text(content, encoding="utf-8")

    def load(self):
        self.inventory_path.write_text(json.dumps(self.data), encoding="utf-8")
        return gate.load_inventory(self.inventory_path, 35)

    def check(self, checker, args, expected=True, messages=(), absent=()):
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            result = checker(*args)
        self.assertEqual(result, expected, output.getvalue())
        for message in messages:
            self.assertIn(message, output.getvalue())
        for message in absent:
            self.assertNotIn(message, output.getvalue())
        return output.getvalue()

    def node(self, report, expected=True, *messages):
        return self.check(
            gate.check_node_lcov,
            (report, self.root, "plugin", self.load()["javascript"], (80, 70, 80)),
            expected,
            messages,
        )

    def python(self, report, expected=True, *messages):
        return self.check(
            gate.check_python_trace,
            (report, self.root, "plugin", self.load()["python"], 35, 20, 15),
            expected,
            messages,
        )

    def bats(self, expected=True, *messages):
        return self.check(gate.check_bats_contracts, (self.root, "plugin", self.load()), expected, messages)

    def python_inventory(self, expected=True, *messages):
        return self.check(
            gate.check_python_inventory, (self.root, "plugin", self.load()["python"], False), expected, messages
        )

    def test_lcov_baselines_and_zero_denominators(self):
        cases = (
            (lcov(JS), True, "lines 80.00% (8/10), branches 70.00% (7/10), functions 80.00% (8/10)"),
            (lcov(JS, (9, 10), (8, 10), (9, 10)), True, "lines 90.00%"),
            (lcov(JS, (7999, 10000)), False, "Node coverage below baseline"),
            (lcov(JS, branches=(0, 0), functions=(0, 0)), True, "branches 100.00% (0/0), functions 100.00% (0/0)"),
        )
        for report, expected, message in cases:
            with self.subTest(message=message):
                self.node(report, expected, message)

    def test_lcov_aggregates_counters_and_ignores_tests(self):
        large = "plugin/scripts/large.js"
        self.data["javascript"]["measured"].append(large)
        self.node(
            lcov(JS, (1, 1), (1, 1), (1, 1))
            + lcov(large, (78, 99), (69, 99), (78, 99))
            + lcov("tests/node/example.test.js", (1000, 1000), (1000, 1000), (1000, 1000)),
            False,
            "lines 79.00% (79/100), branches 70.00% (70/100), functions 79.00% (79/100)",
            "Node coverage below baseline",
        )

    def test_lcov_inventory_membership(self):
        self.node("", False, f"Node coverage missing inventory files (1): {JS}")
        contract = "plugin/scripts/contract.js"
        extra = lcov(contract, (0, 100), (0, 100), (0, 100))
        self.node(lcov(JS) + extra, False, f"Node coverage report has unregistered production files (1): {contract}")
        self.data["javascript"]["contract_only"][contract] = [SUITE]
        self.node(lcov(JS) + extra, True, "lines 80.00% (8/10)")
        self.data["javascript"]["excluded"] = {"plugin/scripts/vendor.js": "vendored"}
        self.node(
            lcov(JS) + lcov("plugin/scripts/vendor.js", (0, 100)),
            False,
            "Node coverage report has unregistered production files (1): plugin/scripts/vendor.js",
        )

    def test_lcov_malformed_records(self):
        record = lcov(JS)
        cases = {
            "missing counter": record.replace("LH:8\n", ""),
            "duplicate counter": record.replace("LH:8\n", "LH:8\nLH:7\n"),
            "nonnumeric counter": record.replace("LF:10", "LF:ten"),
            "duplicate source": record + lcov("scripts/example.js"),
            "impossible hits": lcov(JS, (11, 10)),
            "no line obligations": lcov(JS, (0, 0), (0, 0), (0, 0)),
            "unterminated record": record.removesuffix("end_of_record\n"),
            "empty path": lcov(""),
            "counter outside record": "LH:1\n" + record,
        }
        for name, report in cases.items():
            with self.subTest(case=name):
                self.node(report, False, "Node LCOV coverage report is malformed")

    def test_report_path_normalization(self):
        for prefix in ("", "./", "../", f"{self.root}/"):
            with self.subTest(prefix=prefix):
                node_path = prefix + ".agents/skills/demo/scripts/example.js"
                python_path = prefix + ".agents/skills/demo/scripts/example.py"
                self.data["javascript"]["measured"] = [".agents/skills/demo/scripts/example.js"]
                self.data["python"]["measured"] = [".agents/skills/demo/scripts/example.py"]
                self.node(lcov(node_path.replace("/", "\\")))
                self.python(trace(python_path))
        self.python(trace("/different/checkout/.agents/skills/demo/scripts/example.py"))
        self.data["javascript"]["measured"] = [JS]
        self.data["python"]["measured"] = [PYTHON]
        self.node(lcov("scripts/example.js"))
        self.python(trace("hooks/example.py"))
        self.python(trace(self.root / PYTHON))
        self.node(lcov("/different/checkout/" + JS), False, f"Node coverage missing inventory files (1): {JS}")

    def test_reports_ignore_checkout_root_test_paths(self):
        self.node(lcov(JS) + lcov(self.root / "tests/fixture.js"))
        self.python(trace(PYTHON) + trace(self.root / "tests/fixture.py", 100))

    def test_trace_aggregate_baselines_and_missing_summary(self):
        self.python(trace(PYTHON), True, "Python production aggregate: 35.00%")
        self.python(trace(PYTHON, 34), False, "Python coverage below baseline")
        self.python(trace(PYTHON, 35.4), True, "Python production aggregate: 35.40%")
        self.python("no production rows\n", False, "Python production coverage summary not found")
        self.data["python"]["measured"].append(LOW)
        self.python(trace(PYTHON, 100, 1) + trace(LOW, 30, 99), False, "aggregate: 30.70% (100 executable lines)")
        self.python(trace(PYTHON), False, f"Python coverage missing inventory files (1): {LOW}")

    def test_trace_inventory_membership_and_ignored_rows(self):
        report = trace(PYTHON)
        contract = "plugin/hooks/contract.py"
        extra = trace(contract, 100)
        self.python(report + extra, False, f"Python coverage report has unregistered production files (1): {contract}")
        self.data["python"]["contract_only"][contract] = [SUITE]
        report += extra + trace("plugin/hooks/__init__.py", 100) + trace("plugin/hooks/test_helper.py", 100)
        report += trace("plugin/tests/python/helper.py", 100) + trace("/opt/python/lib/argparse.py", 100)
        output = self.python(report, True, "Python production aggregate: 35.00%")
        self.assertNotIn("unregistered production files", output)

    def test_trace_per_file_floors(self):
        self.data["python"]["measured"].append(LOW)
        cases = (
            (45, None, True, "45.00% (floor 20%)"),
            (0, None, False, f"{LOW} (0.00% < 20%)"),
            (19, None, False, f"{LOW} (19.00% < 20%)"),
            (19, 10, True, "19.00% (floor 10%)"),
            (35, 10, False, "Python per-file floors are obsolete"),
            (34, 34, True, "34.00% (floor 34%)"),
            (19.4, 19.5, False, f"{LOW} (19.40% < 19.50%)"),
        )
        for percent, floor, expected, message in cases:
            with self.subTest(percent=percent, floor=floor):
                self.data["python"]["measured_floors"] = {} if floor is None else {LOW: floor}
                self.python(
                    trace(PYTHON, 100) + trace(LOW, percent),
                    expected,
                    message,
                    "Python per-file coverage (2 lowest of 2 measured files, floor 20%)",
                )

    def test_rejects_malformed_floors(self):
        for value in (False, None, {PYTHON: "disabled"}, {LOW: 10}, {PYTHON: 35}, {PYTHON: -1}, {PYTHON: True}):
            with self.subTest(floors=value):
                self.data["python"]["measured_floors"] = value
                with self.assertRaisesRegex(ValueError, "invalid python measured floors"):
                    self.load()

    def test_rejects_malformed_inventory(self):
        original = copy.deepcopy(self.data)
        cases = (
            ("javascript", "measured", []),
            ("javascript", "measured", [None]),
            ("javascript", "measured", [JS, JS]),
            ("javascript", "excluded", {JS: "duplicate"}),
            ("javascript", "excluded", {JS: ""}),
            ("python", "measured", []),
            ("python", "contract_only", {PYTHON: [SUITE]}),
            ("python", "contract_only", {"": [SUITE]}),
            ("shell", "contract_only", {SHELL: []}),
            ("shell", "contract_only", {SHELL: [""]}),
        )
        for language, field, invalid in cases:
            with self.subTest(language=language, field=field, invalid=invalid):
                self.data = copy.deepcopy(original)
                self.data[language][field] = invalid
                with self.assertRaises(ValueError):
                    self.load()
        self.inventory_path.write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            gate.load_inventory(self.inventory_path, 35)

    def test_invalid_inventory_fails_with_python_optimization(self):
        self.data["python"] = {"measured": [], "contract_only": {PYTHON: [SUITE]}}
        self.inventory_path.write_text(json.dumps(self.data), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "-O",
                str(SCRIPT),
                "--root",
                str(self.root),
                "--plugin",
                "plugin",
                "--inventory",
                str(self.inventory_path),
                "--file-minimum",
                "20",
                "--stale-margin",
                "15",
                "inventory",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Production coverage inventory is malformed", result.stderr)

    def test_static_inventory_discovery(self):
        self.python_inventory(True, "Python static inventory: 1 production file registered.")
        paths = ["plugin/scripts/lint-skill-contracts.py", "plugin/scripts/lint_skill_contracts.py"]
        self.data["python"]["measured"].extend(paths)
        for path in paths:
            self.write(path, "")
        self.python_inventory(True, "Python static inventory: 3 production files registered.")
        self.write(LOW, "")
        (self.root / paths[0]).unlink()
        self.python_inventory(
            False,
            f"Python production files missing static inventory entries (1): {LOW}",
            f"Python static inventory entries missing production files (1): {paths[0]}",
        )

    def test_bats_inventory_complete(self):
        self.bats(
            True,
            "Shell source-to-contract inventory proxy: 1 production file mapped",
            "Bats contract inventory: 1 files, 1 tests",
        )
        self.write("plugin/scripts/unmapped.sh", "")
        self.bats(False, "Shell production files missing inventory entries (1): plugin/scripts/unmapped.sh")

    def test_bats_contract_requires_discovered_suite_with_tests(self):
        self.write(SUITE, "# no tests\n")
        self.bats(False, f"Production contract has no Bats tests: {SUITE}")
        for undiscovered in ("plugin/tests/nested/example.bats", "plugin/tests/.hidden.bats"):
            with self.subTest(suite=undiscovered):
                self.write(undiscovered, '@test "example" {\n  true\n}\n')
                self.data["shell"]["contract_only"][SHELL] = [undiscovered]
                self.bats(False, f"Production contract is not discovered by tests/run-tests.sh: {undiscovered}")
        self.data["shell"]["contract_only"][SHELL] = ["plugin/tests/missing.bats"]
        self.bats(False, "Production contract file not found: plugin/tests/missing.bats")

    def test_path_diagnostics_show_at_most_ten_entries(self):
        paths = [f"path{index}" for index in range(13)]
        self.check(gate.report_paths, ("Nodes", paths), True, ("Nodes (13):", "path9, ... (+3 more)"), ("path10",))


if __name__ == "__main__":
    unittest.main()
