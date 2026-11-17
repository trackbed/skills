from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "code-outline.py"
SPEC = importlib.util.spec_from_file_location("code_outline", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
code_outline = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = code_outline
SPEC.loader.exec_module(code_outline)

TYPESCRIPT_TREE = {
    "src/core/pricing.ts": (
        'import { rate } from "../rates/tariff.js";\n\n'
        "export function price(weightKg: number): number {\n  return weightKg * rate;\n}\n"
    ),
    "src/rates/tariff.ts": "export const rate = 10;\n",
    "src/features/a.ts": 'import { price } from "../core/pricing";\nexport const a = price(1);\n',
    "src/features/b.ts": 'import { price } from "../core/pricing";\nexport const b = price(2);\n',
    "src/features/c.ts": 'import { price } from "../core/pricing";\nexport const c = price(3);\n',
    "src/features/d.ts": (
        'import React from "react";\nimport "./d.css";\n'
        'import { price } from "../core/pricing";\nexport const d = price(4);\n'
    ),
    "src/features/e.ts": 'import { price } from "@/core/pricing";\nexport const e = price(5);\n',
    "src/cycle/left.ts": 'import { right } from "./right";\nexport const left = () => right;\n',
    "src/cycle/right.ts": 'import { left } from "./left";\nexport const right = () => left;\n',
    # A widely imported test helper that imports the volatile tariff is never the stable side.
    "tests/helpers/fixture.ts": 'import { rate } from "../../src/rates/tariff";\nexport const fixture = rate;\n',
    **{
        f"tests/case{index}.test.ts": (
            f'import {{ fixture }} from "./helpers/fixture";\nexport const t{index} = fixture;\n'
        )
        for index in range(5)
    },
}

PYTHON_TREE = {
    "pkg/__init__.py": "",
    "pkg/core.py": (
        "from .volatile import RATE\n\n\nclass Pricing:\n"
        "    def price(self, weight: int) -> int:\n        return weight * RATE\n"
    ),
    "pkg/volatile.py": "RATE = 10\n",
    "pkg/users/__init__.py": "",
    "pkg/users/a.py": "from ..core import Pricing\n\nA = Pricing()\n",
    "pkg/users/b.py": "from pkg import core\n\nB = core.Pricing()\n",
    "pkg/users/c.py": "import os\nfrom pkg.core import Pricing\n\nC = Pricing()\n",
    "pkg/users/d.py": "from pkg.core import Pricing\n\nD = Pricing()\n",
    "pkg/users/e.py": "from pkg.core import Pricing\n\n\nasync def run() -> None:\n    Pricing()\n",
    "pkg/loop_a.py": "from . import loop_b\n\nTHING = 1\n",
    "pkg/loop_b.py": "from .loop_a import THING\n",
}


class CodeOutlineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / "repo"
        self.root.mkdir()
        self.out = self.root / ".context" / "outline"

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.root, text=True, capture_output=True, check=True).stdout

    def init_repo(self, tree: dict[str, str], volatile: str) -> None:
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.git("config", "commit.gpgsign", "false")
        self.write_tree(tree)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "initial")
        # Twelve more changes give the volatile file thirteen commits.
        for rate in range(11, 23):
            target = self.root / volatile
            target.write_text(target.read_text().replace(str(rate - 1), str(rate)), encoding="utf-8")
            self.git("commit", "-q", "-am", f"rate {rate}")

    def write_tree(self, tree: dict[str, str]) -> None:
        for path, content in tree.items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def run_outline(self, paths: list[str], *extra: str) -> tuple[int, dict[str, Any]]:
        listing = Path(self.tmp.name) / "files.txt"
        listing.write_text("\n".join(paths) + "\n", encoding="utf-8")
        argv = ["--files", str(listing), "--out", str(self.out), "--root", str(self.root), *extra]
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            status = code_outline.main(argv)
        return status, json.loads(stdout.getvalue())

    def snapshot(self) -> dict[str, str]:
        # Every file in the temporary directory except the listing, so a write anywhere else under it is caught.
        tmp = Path(self.tmp.name).resolve()
        return {
            str(path.relative_to(tmp)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(tmp.rglob("*"))
            if path.is_file() and self.out not in path.parents and path.name != "files.txt"
        }

    def test_typescript_tree_resolves_relative_imports_cycle_and_direction_lead(self) -> None:
        self.init_repo(TYPESCRIPT_TREE, "src/rates/tariff.ts")

        status, report = self.run_outline(sorted(TYPESCRIPT_TREE))

        self.assertEqual(status, 0)
        self.assertEqual(report["files"]["read"], len(TYPESCRIPT_TREE))
        # Four feature imports, pricing's tariff import, the cycle, and the test helper chain;
        # the stylesheet is not counted.
        self.assertEqual(report["imports"]["relative"], 13)
        self.assertEqual(report["imports"]["relative_resolved"], 13)
        # "react" stays external; "@/core/pricing" resolves by its unique path suffix.
        self.assertEqual(report["imports"]["statements"], 15)
        self.assertEqual(report["imports"]["resolved"], 14)
        self.assertEqual(report["cycles"], [{"size": 2, "files": ["src/cycle/left.ts", "src/cycle/right.ts"]}])
        self.assertEqual(
            report["direction_leads"],
            [
                {
                    "stable": "src/core/pricing.ts",
                    "stable_importers": 5,
                    "stable_commits": 1,
                    "volatile": "src/rates/tariff.ts",
                    "volatile_commits": 13,
                    "import_line": 1,
                }
            ],
        )
        self.assertEqual(report["history"]["status"], "ok")

        imports = (self.out / "imports.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            imports[0],
            "# resolved 13 of 13 relative imports (100%); 14 of 15 import statements resolved to a listed file",
        )
        self.assertIn("src/features/e.ts\tsrc/core/pricing.ts\t1", imports)

        outline = (self.out / "outline.md").read_text(encoding="utf-8").splitlines()
        self.assertIn("3: export function price(weightKg: number): number", outline)
        self.assertNotIn("return weightKg * rate;", "\n".join(outline))
        rows = {
            row.split("\t")[0]: row.split("\t")
            for row in (self.out / "folders.tsv").read_text(encoding="utf-8").splitlines()[1:]
        }
        folder, files, lines, importers, imported, commits, outline_lines = rows["src/core"]
        self.assertEqual((files, lines, importers, imported, commits), ("1", "5", "5", "1", "1"))
        start, end = (int(value) for value in outline_lines.split("-"))
        self.assertEqual(outline[start - 1], "## src/core")
        self.assertEqual(outline[end - 1], "3: export function price(weightKg: number): number")
        self.assertEqual(rows["src/rates"][5], "13")

    def test_python_tree_resolves_relative_and_suffix_imports(self) -> None:
        self.init_repo(PYTHON_TREE, "pkg/volatile.py")

        status, report = self.run_outline(sorted(PYTHON_TREE))

        self.assertEqual(status, 0)
        self.assertEqual(report["imports"]["relative"], 4)
        self.assertEqual(report["imports"]["relative_resolved"], 4)
        self.assertEqual(report["cycles"], [{"size": 2, "files": ["pkg/loop_a.py", "pkg/loop_b.py"]}])
        leads = [(lead["stable"], lead["volatile"], lead["stable_importers"]) for lead in report["direction_leads"]]
        self.assertEqual(leads, [("pkg/core.py", "pkg/volatile.py", 5)])
        outline = (self.out / "outline.md").read_text(encoding="utf-8")
        self.assertIn("4: class Pricing\n  5: def price(self, weight: int) -> int\n", outline)
        self.assertIn("4: async def run() -> None", outline)
        imports = (self.out / "imports.tsv").read_text(encoding="utf-8")
        self.assertIn("pkg/users/b.py\tpkg/core.py\t1", imports)
        self.assertNotIn("os.py", imports)

    def test_suffix_matches_need_a_unique_path_of_two_or_more_segments(self) -> None:
        tree = {
            "proj/celery.py": "",
            "app/logging.py": "",
            "app/tasks.py": (
                "import logging\nfrom celery import shared_task\n"
                "from shared.utils import helper\nfrom proj.celery import app\n"
            ),
            "src/a/shared/utils.py": "",
            "src/b/shared/utils.py": "",
            "web/a/lib/helpers.ts": "",
            "web/b/lib/helpers.ts": "",
            "web/page.ts": 'import { h } from "@/lib/helpers";\nimport { a } from "@/a/lib/helpers";\n',
        }
        self.write_tree(tree)

        status, _ = self.run_outline(sorted(tree))

        self.assertEqual(status, 0)
        # "logging" and "celery" are package names; "shared/utils" and "lib/helpers" match two files each.
        edges = (self.out / "imports.tsv").read_text(encoding="utf-8").splitlines()[2:]
        self.assertEqual(edges, ["app/tasks.py\tproj/celery.py\t4", "web/page.ts\tweb/a/lib/helpers.ts\t2"])

    def test_direction_leads_rank_by_importers_then_churn_gap(self) -> None:
        importers = {
            "core/a.py": {f"user{index}.py" for index in range(7)},
            "core/b.py": {f"user{index}.py" for index in range(5)},
            "core/c.py": {f"user{index}.py" for index in range(5)},
            "core/d.py": {f"user{index}.py" for index in range(4)},
        }
        commits = {
            "core/a.py": {"c1"},
            "core/b.py": {"c1"},
            "core/c.py": {"c1", "c2"},
            "core/d.py": set(),
            "volatile/hot.py": {f"h{index}" for index in range(12)},
            "volatile/warm.py": {f"w{index}" for index in range(9)},
        }
        edges = {
            "core/a.py": {"volatile/hot.py": 1},
            "core/b.py": {"volatile/hot.py": 1},
            "core/c.py": {"volatile/hot.py": 1, "volatile/warm.py": 2},
            "core/d.py": {"volatile/hot.py": 1},
        }

        leads = code_outline.direction_leads(edges, importers, commits)

        # d has too few importers and warm too few commits; b's churn gap is wider than c's.
        self.assertEqual(
            [(lead["stable"], lead["volatile"]) for lead in leads],
            [("core/a.py", "volatile/hot.py"), ("core/b.py", "volatile/hot.py"), ("core/c.py", "volatile/hot.py")],
        )

    def test_cycles_and_leads_are_capped_with_totals(self) -> None:
        tree = {
            **TYPESCRIPT_TREE,
            "src/loop/x.ts": 'import { y } from "./y";\nexport const x = () => y;\n',
            "src/loop/y.ts": 'import { x } from "./x";\nexport const y = () => x;\n',
        }
        self.init_repo(tree, "src/rates/tariff.ts")

        with mock.patch.multiple(code_outline, MAX_LEADS=0, MAX_CYCLES=1, MAX_CYCLE_FILES=1):
            status, report = self.run_outline(sorted(tree))

        self.assertEqual(status, 0)
        self.assertEqual((report["direction_leads"], report["direction_leads_total"]), ([], 1))
        self.assertEqual(report["cycles"], [{"size": 2, "files": ["src/cycle/left.ts"]}])
        self.assertEqual(report["cycles_total"], 2)

    def test_non_utf8_path_in_history_keeps_the_report(self) -> None:
        self.init_repo(TYPESCRIPT_TREE, "src/rates/tariff.ts")
        blob = self.git("hash-object", "-w", "src/rates/tariff.ts").strip()
        # The surrogate becomes the raw byte 0xE9 in the path git records.
        self.git("update-index", "--add", "--cacheinfo", f"100644,{blob},caf\udce9.txt")
        self.git("commit", "-q", "-m", "latin-1 name")

        status, report = self.run_outline(sorted(TYPESCRIPT_TREE))

        self.assertEqual(status, 0)
        self.assertEqual(report["history"]["status"], "ok")
        self.assertEqual(report["direction_leads"][0]["volatile_commits"], 13)

    def test_import_followed_by_long_whitespace_is_parsed_in_linear_time(self) -> None:
        source = code_outline.SourceFile("src/a.ts", "javascript", 1)

        code_outline.parse_javascript(source, "import" + " " * 200_000 + "x\nimport ( './c' );\n")

        self.assertEqual([statement.groups for statement in source.imports], [[["src/c"]]])

    def test_unknown_language_gives_empty_result_and_exit_zero(self) -> None:
        self.write_tree({"main.go": "package main\n", "lib/util.go": "package lib\n"})

        status, report = self.run_outline(["main.go", "lib/util.go"])

        self.assertEqual(status, 0)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(
            report["files"], {"listed": 2, "read": 0, "skipped_unsupported": 2, "missing": 0, "parse_errors": 0}
        )
        self.assertEqual((report["cycles"], report["direction_leads"]), ([], []))
        self.assertEqual(report["imports"]["statements"], 0)
        self.assertEqual((self.out / "folders.tsv").read_text(encoding="utf-8").splitlines()[1:], [])

    def test_writes_only_inside_the_output_directory(self) -> None:
        self.init_repo(TYPESCRIPT_TREE, "src/rates/tariff.ts")
        before = self.snapshot()

        status, _ = self.run_outline(sorted(TYPESCRIPT_TREE))

        self.assertEqual(status, 0)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(sorted(path.name for path in self.out.iterdir()), ["folders.tsv", "imports.tsv", "outline.md"])

    def test_without_history_counts_are_unknown_and_no_leads_are_reported(self) -> None:
        self.write_tree(TYPESCRIPT_TREE)

        status, report = self.run_outline(sorted(TYPESCRIPT_TREE))

        self.assertEqual(status, 0)
        self.assertEqual(report["history"]["status"], "unavailable")
        self.assertEqual(report["direction_leads"], [])
        self.assertEqual(len(report["cycles"]), 1)
        row = (self.out / "folders.tsv").read_text(encoding="utf-8").splitlines()[1].split("\t")
        self.assertEqual(row[5], "unknown")

    def test_unparseable_python_is_listed_without_declarations(self) -> None:
        self.write_tree({"broken.py": "def broken(:\n", "ok.py": "import broken\n"})

        status, report = self.run_outline(["broken.py", "ok.py", "missing.py", "../outside.py"])

        self.assertEqual(status, 0)
        self.assertEqual(report["files"]["parse_errors"], 1)
        self.assertEqual(report["files"]["missing"], 2)
        self.assertIn("### broken.py (1 lines, could not parse)", (self.out / "outline.md").read_text(encoding="utf-8"))

    def test_unreadable_file_list_is_an_error(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            status = code_outline.main(["--files", str(self.root / "absent.txt"), "--out", str(self.out)])

        self.assertEqual(status, 1)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "error")
        self.assertFalse(self.out.exists())

    def test_test_paths_are_recognized(self) -> None:
        test_paths = (
            "tests/x.ts",
            "src/__tests__/x.ts",
            "src/x.spec.ts",
            "pkg/test_x.py",
            "pkg/x_test.py",
            "conftest.py",
        )
        for path in test_paths:
            self.assertTrue(code_outline.is_test_path(path), path)
        for path in ("src/contest.ts", "src/testing.py", "src/latest.ts"):
            self.assertFalse(code_outline.is_test_path(path), path)


if __name__ == "__main__":
    unittest.main()
