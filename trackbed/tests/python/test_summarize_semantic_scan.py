from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "summarize-semantic-scan.py"
SPEC = importlib.util.spec_from_file_location("summarize_semantic_scan", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
summarize_semantic_scan = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = summarize_semantic_scan
SPEC.loader.exec_module(summarize_semantic_scan)


def issue(rule: str, file: str, line: int, severity: str = "MEDIUM", text: str = "why it matters") -> dict[str, Any]:
    return {
        "id": rule,
        "severity": severity,
        "location": {"file": file, "start_line": line, "end_line": None},
        "explanation": text,
    }


class SummarizeTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.static_dir = Path(tmp.name) / "skillspector"
        self.semantic_dir = Path(tmp.name) / "skillspector-semantic"
        self.static_dir.mkdir()
        self.semantic_dir.mkdir()

    def write_static(self, stem: str, issues: list[dict[str, Any]]) -> None:
        report = {"issues": issues, "metadata": {"llm_requested": False, "llm_available": False}}
        (self.static_dir / f"{stem}.json").write_text(json.dumps(report))

    def write_semantic(
        self, stem: str, issues: list[dict[str, Any]], *, used_model: bool = True, log: str = ""
    ) -> None:
        report = {"issues": issues, "metadata": {"llm_requested": True, "llm_available": used_model}}
        (self.semantic_dir / f"{stem}.json").write_text(json.dumps(report))
        (self.semantic_dir / f"{stem}.log").write_text(log)

    def summarize(self, model: str = "gpt-6.1-terra") -> tuple[str, bool]:
        result: tuple[str, bool] = summarize_semantic_scan.summarize(self.static_dir, self.semantic_dir, model)
        return result

    def test_findings_are_split_into_kept_added_and_dropped(self) -> None:
        kept = issue("EA2", "SKILL.md", 12)
        dropped = issue("AST4", "scripts/run.py", 40, text="subprocess call")
        added = issue("SSD-3", "SKILL.md", 7, severity="HIGH", text="asks the agent to echo credentials")
        self.write_static("pr_create", [kept, dropped])
        self.write_semantic("pr_create", [kept, added])

        summary, trusted = self.summarize()

        self.assertTrue(trusted)
        self.assertIn("Model `gpt-6.1-terra` scanned 1 directory.", summary)
        self.assertIn("| `pr_create` | 1 | 1 | 1 |", summary)
        added_section, dropped_section = summary.split("### Static findings the model dropped")
        self.assertIn(
            "- **HIGH** `SSD-3` in `pr_create` at `SKILL.md:7`: asks the agent to echo credentials", added_section
        )
        self.assertIn("- **MEDIUM** `AST4` in `pr_create`, `scripts/run.py` line 40: subprocess call", dropped_section)
        self.assertNotIn("EA2", summary)
        self.assertNotIn("### Problems", summary)

    def test_the_same_rule_on_another_line_is_a_different_finding(self) -> None:
        self.write_static("one", [issue("EA2", "SKILL.md", 12)])
        self.write_semantic("one", [issue("EA2", "SKILL.md", 30)])

        summary, _ = self.summarize()

        self.assertIn("| `one` | 0 | 1 | 1 |", summary)

    def test_dropped_findings_are_grouped_by_rule_and_file(self) -> None:
        repeated = [issue("TM1", "SKILL.md", line, "HIGH", "rule text") for line in (252, 31, 252, 96)]
        self.write_static(
            "one", [*repeated, issue("TM1", "references/a.md", 5, "HIGH", "rule text"), issue("LP3", "SKILL.md", 1)]
        )
        self.write_semantic("one", [])

        summary, _ = self.summarize()

        self.assertIn("| `one` | 0 | 0 | 6 |", summary)
        dropped = summary.split("### Static findings the model dropped")[1].strip().splitlines()
        self.assertEqual(
            dropped,
            [
                "- **HIGH** `TM1` in `one`, `SKILL.md` lines 31, 96, 252: rule text",
                "- **HIGH** `TM1` in `one`, `references/a.md` line 5: rule text",
                "- **MEDIUM** `LP3` in `one`, `SKILL.md` line 1: why it matters",
            ],
        )

    def test_findings_in_files_left_out_of_the_llm_scan_are_not_called_dropped(self) -> None:
        bundle = issue("SC3", "assets/vendor.min.js", 2, "HIGH")
        script = issue("AST4", "scripts/run.py", 9)
        static = {
            "issues": [bundle, bundle, script],
            "components": [{"path": "SKILL.md"}, {"path": "assets/vendor.min.js"}, {"path": "scripts/run.py"}],
        }
        semantic = {
            "issues": [],
            "components": [{"path": "SKILL.md"}, {"path": "scripts/run.py"}],
            "metadata": {"llm_requested": True, "llm_available": True},
        }
        (self.static_dir / "one.json").write_text(json.dumps(static))
        (self.semantic_dir / "one.json").write_text(json.dumps(semantic))

        summary, trusted = self.summarize()

        self.assertTrue(trusted)
        self.assertIn("| `one` | 0 | 0 | 1 |", summary)
        self.assertIn("Not counted: 2 static findings in files left out of the LLM scan.", summary)
        self.assertNotIn("SC3", summary)
        self.assertIn("`AST4` in `one`, `scripts/run.py` line 9", summary)

    def test_findings_are_listed_most_severe_first(self) -> None:
        self.write_static("one", [])
        self.write_semantic(
            "one",
            [
                issue("SQP-1", "SKILL.md", 3, "LOW"),
                issue("SSD-1", "SKILL.md", 9, "CRITICAL"),
                issue("SDI-2", "a.py", 1, "HIGH"),
            ],
        )

        summary, _ = self.summarize()

        self.assertLess(summary.index("`SSD-1`"), summary.index("`SDI-2`"))
        self.assertLess(summary.index("`SDI-2`"), summary.index("`SQP-1`"))

    def test_a_failed_model_call_makes_the_report_untrusted(self) -> None:
        log = (
            "Report saved to: /tmp/one.json\n"
            "WARNING [skillspector.nodes.analyzers.static_yara] yara rules skipped\n"
            "WARNING [skillspector.nodes.meta_analyzer] LLM call failed, using fallback: Error code: 429 - "
            "Rate limit reached in organization org-abc123DEF456 for key sk-proj-********abcd\n"
            "WARNING [skillspector.nodes.analyzers.semantic_quality_policy] semantic_quality_policy failed: timeout\n"
            "WARNING [skillspector.model_info] No token-limit info for model 'gpt-9' — using 128000-token default.\n"
        )
        self.write_static("one", [])
        self.write_semantic("one", [], log=log)

        summary, trusted = self.summarize()

        self.assertFalse(trusted)
        problems = summary.split("### Problems")[1]
        self.assertIn("`one`: WARNING [skillspector.nodes.meta_analyzer] LLM call failed", problems)
        self.assertIn("semantic_quality_policy failed: timeout", problems)
        self.assertIn("No token-limit info for model 'gpt-9'", problems)
        self.assertNotIn("static_yara", summary)
        self.assertNotIn("org-abc123DEF456", summary)
        self.assertNotIn("sk-proj-", summary)
        self.assertIn("in organization [redacted] for key [redacted]", problems)

    def test_a_report_that_did_not_use_the_model_is_untrusted(self) -> None:
        self.write_static("one", [])
        self.write_semantic("one", [], used_model=False)

        summary, trusted = self.summarize()

        self.assertFalse(trusted)
        self.assertIn("`one`: the report says no model was used.", summary)

    def test_missing_or_broken_reports_are_problems(self) -> None:
        self.write_semantic("no_baseline", [issue("SSD-1", "SKILL.md", 2)])
        (self.semantic_dir / "broken.json").write_text("{not json")
        (self.semantic_dir / "crashed.log").write_text("Error: something went wrong\n")

        summary, trusted = self.summarize()

        self.assertFalse(trusted)
        self.assertIn("`no_baseline`: no static report to compare with", summary)
        self.assertIn("| `no_baseline` | 0 | 1 | 0 |", summary)
        self.assertIn("`broken`: the LLM report is not readable JSON.", summary)
        self.assertIn("`crashed`: the scan wrote no report.", summary)

    def test_model_written_text_is_flattened_escaped_and_shortened(self) -> None:
        text = "first line\n<script>alert(1)</script> " + "x" * 400
        self.write_static("one", [])
        self.write_semantic("one", [issue("SSD-2", "SKILL.md", 1, text=text)])

        summary, _ = self.summarize()

        line = next(line for line in summary.splitlines() if "`SSD-2`" in line)
        self.assertIn("first line &lt;script>alert(1)&lt;/script>", line)
        self.assertNotIn("<script>", line)
        self.assertTrue(line.endswith("…"))
        self.assertLess(len(line), 320)

    def test_long_lists_are_capped(self) -> None:
        many = [issue("SQP-1", "SKILL.md", number) for number in range(1, 106)]
        self.write_static("one", [])
        self.write_semantic("one", many)

        summary, _ = self.summarize()

        self.assertEqual(summary.count("- **MEDIUM** `SQP-1`"), 100)
        self.assertIn("- …and 5 more in the report files.", summary)

    def test_nothing_scanned_is_reported_plainly(self) -> None:
        summary, trusted = self.summarize()
        self.assertTrue(trusted)
        self.assertEqual(summary, "## SkillSpector LLM scan\n\nNo skill directories were scanned.\n")

        missing = self.semantic_dir / "missing"
        summary, trusted = summarize_semantic_scan.summarize(self.static_dir, missing, "")
        self.assertTrue(trusted)
        self.assertIn("No skill directories were scanned.", summary)

    def test_the_command_prints_the_summary_and_fails_on_problems(self) -> None:
        self.write_static("one", [])
        self.write_semantic("one", [])
        arguments = ["--static-dir", str(self.static_dir), "--semantic-dir", str(self.semantic_dir)]

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = summarize_semantic_scan.main([*arguments, "--model", "gpt-6.1-terra"])
        self.assertEqual(status, 0)
        self.assertIn("Model `gpt-6.1-terra` scanned 1 directory.", output.getvalue())

        self.write_semantic("two", [], used_model=False)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = summarize_semantic_scan.main(arguments)
        self.assertEqual(status, 1)
        self.assertIn("The model scanned 2 directories.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
