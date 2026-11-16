from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from lint_skill_contracts.checks.invocation_graph import check_invocation_graph, skill_inventory
from lint_skill_contracts.checks.mechanical import check_agent_frontmatter, check_mechanical
from lint_skill_contracts.checks.routing_distinctness import check_routing_distinctness
from lint_skill_contracts.checks.types import LintContext
from lint_skill_contracts.frontmatter import frontmatter_string_value, frontmatter_type_errors
from lint_skill_contracts.readme import load_agent_references, load_skill_references

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "component-scalars.json"


class ComponentMetadataTest(unittest.TestCase):
    def test_registry_negative_forms_return_diagnostics(self):
        for section, check, fields in [
            (
                "mechanical",
                check_mechanical,
                [
                    "max_skill_lines",
                    "warn_skill_lines",
                    "skill_line_report_limit",
                    "max_description_chars",
                    "warn_description_chars",
                    "skill_description_report_limit",
                    "allow_line_count_over",
                    "required_frontmatter",
                    "skill_glob",
                    "agent_glob",
                ],
            ),
            ("routing_distinctness", check_routing_distinctness, ["pair_report_limit", "stopwords", "skill_glob"]),
        ]:
            for bad in [False, 3, [], "invalid"]:
                result = check(LintContext(Path("/unused"), {section: bad}, {}))
                self.assertTrue(result.failures, (section, bad))
            for field in fields:
                for bad in [None, True, {}, 1.5]:
                    with self.subTest(section=section, field=field, bad=bad):
                        result = check(LintContext(Path("/unused"), {section: {field: bad}}, {}))
                        self.assertTrue(any(field in failure for failure in result.failures), result.failures)

    def test_agent_schema_preserves_inherit_and_tool_forms(self):
        for tools in ["Read, Grep", "[Read, Grep]", "\n  - Read\n  - Grep"]:
            text = (
                "---\nname: reviewer\nmodel: inherit\ncolor: blue\ndescription: Reviews code\n"
                f"capabilities: []\ntools: {tools}\nomitClaudeMd: true\n---\n"
            )
            self.assertEqual(frontmatter_type_errors(text, component="agent"), [])
        for field in [
            "name",
            "description",
            "model",
            "color",
            "tools",
            "disallowedTools",
            "capabilities",
            "omitClaudeMd",
        ]:
            errors = frontmatter_type_errors(f"---\n{field}:\n  bad: value\n---\n", component="agent")
            self.assertIn(field, [key for key, _ in errors])

    def test_array_fields_reject_a_literal_scalar_that_looks_like_a_list(self):
        self.assertIn(
            ("capabilities", "an array of strings"),
            frontmatter_type_errors("---\ncapabilities: |\n  []\n---\n", component="agent"),
        )

    def test_shared_valid_agent_forms(self):
        fixtures = json.loads(FIXTURES.with_name("agent-metadata.json").read_text())
        for case in fixtures:
            with self.subTest(case=case["name"]):
                text = "---\n" + case["frontmatter"] + "\n---\n"
                self.assertEqual(frontmatter_type_errors(text, component="agent"), [])

    def test_decoded_identity_invocation_and_argument_consumers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for style in ("|-", ">-"):
                agent = root / "agents/example.md"
                agent.parent.mkdir(exist_ok=True)
                agent.write_text(
                    f"---\nname: {style}\n  example\ndescription: Reviews\nmodel: inherit\ncolor: blue\n---\n"
                )
                result = check_agent_frontmatter(LintContext(root, {"mechanical": {"agent_glob": "agents/*.md"}}, {}))
                self.assertEqual(result.failures, [])
            child = root / "skills/target/SKILL.md"
            child.parent.mkdir(parents=True)
            child.write_text(
                "---\nname: |-\n  target\ndescription: Target\n"
                "disable-model-invocation: |-\n  true\nuser-invocable: |-\n  false\n---\n"
            )
            parent = root / "skills/parent/SKILL.md"
            parent.parent.mkdir(parents=True)
            parent.write_text(
                "---\nname: parent\ndescription: Parent\nuser-invocable: true\n"
                'argument-hint: |-\n  "literal"\n---\nInvoke `trackbed:target`.\n'
            )
            inventory, _ = skill_inventory(root, "skills/*/SKILL.md")
            self.assertTrue(inventory["trackbed:target"].model_disabled)
            self.assertFalse(inventory["trackbed:target"].user_invocable)
            context = LintContext(
                root, {"invocation_graph": {"skill_glob": "skills/*/SKILL.md", "scan_globs": ["skills/**/*.md"]}}, {}
            )
            self.assertTrue(
                any(
                    "sets disable-model-invocation: true" in failure
                    for failure in check_invocation_graph(context).failures
                )
            )
            self.assertEqual(load_skill_references(root, "skills", [])["trackbed:parent"].arguments, '"literal"')

    def test_block_scalar_consumers(self):
        for case in json.loads(FIXTURES.read_text()):
            with self.subTest(case=case["name"]), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                text = (
                    "---\nname: example\nuser-invocable: true\ndisable-model-invocation: false\ndescription: "
                    + case["source"]
                    + "\n---\n"
                )
                self.assertEqual(frontmatter_string_value(text, "description"), case["expected"])
                self.assertEqual(frontmatter_type_errors(text), [])
                (root / "skills/example").mkdir(parents=True)
                (root / "skills/example/SKILL.md").write_text(text)
                (root / "agents").mkdir()
                (root / "agents/example.md").write_text(text)
                failures = []
                skill = load_skill_references(root, "skills", failures)["trackbed:example"]
                agent = load_agent_references(root, "agents", failures)["trackbed:example"]
                self.assertEqual(failures, [])
                self.assertEqual(skill.description, case["expected"])
                self.assertEqual(agent.description, case["expected"])
