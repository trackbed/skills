"""Behavioral tests for the trackbed:visual:decisions builder.

Each test writes a small content file, runs the builder's CLI entry point in-process, and reads the page it
wrote. The choices-carrying cases come from a fixture shared with tests/node/visual-decisions-runtime.test.js,
so the builder's `--choices` option and the page's own import accept and refuse the same payloads.
"""

from __future__ import annotations

import base64
import contextlib
import copy
import hashlib
import importlib
import io
import json
import os
import re
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from typing import Any
from unittest import mock

from tests.test_helper.script_loader import load_script

PLUGIN = Path(__file__).resolve().parents[2]
SKILL_DIR = PLUGIN / "skills" / "visual:decisions"
EXAMPLE_DIR = SKILL_DIR / "assets" / "example"
FIXTURE = json.loads(
    (PLUGIN / "tests" / "fixtures" / "visual-decisions-choices-cases.json").read_text(encoding="utf-8")
)
SCRIPTS = SKILL_DIR / "scripts"
# The command imports its sibling modules, which a script-form run finds on sys.path[0].
sys.path.insert(0, str(SCRIPTS))
builder = load_script("build_decisions", SCRIPTS / "build-decisions.py")
images = importlib.import_module("visual_evidence_images")
inline_page = importlib.import_module("inline_page")
evidence_module = importlib.import_module("decisions_evidence")

CATALOG_RE = re.compile(r'<script type="application/json" id="trackbed-decisions-catalog">(.*?)</script>', re.S)
STATE_RE = re.compile(r'<script type="application/json" id="trackbed-decisions-state">(.*?)</script>', re.S)
SCRIPT_RE = re.compile(r"<script>(.*?)</script>", re.S)
POLICY_RE = re.compile(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">')


def png(width: int, height: int) -> bytes:
    """A valid one-color PNG of the given size."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    rows = b"".join(b"\x00" + b"\x80" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def content(**item_overrides: Any) -> dict[str, Any]:
    """The smallest valid content file, with overrides applied to its one item."""
    item: dict[str, Any] = {
        "id": "T-1",
        "title": "A thing to decide",
        "summary": "What is true.",
        "options": [{"id": "do-it", "name": "Do it", "summary": "Go ahead."}],
        "recommendation": {"option": "do-it", "summary": "Do it.", "reasoning": "It is the only real option."},
    }
    item.update(item_overrides)
    return {
        "schemaVersion": 1,
        "document": {
            "id": "test-doc",
            "title": "Test document",
            "summary": "Decide one thing.",
            "generated": "2026-01-15",
        },
        "items": [item],
    }


class BuilderCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name).resolve()
        self.page = self.dir / "page.html"

    def run_builder(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = int(builder.main(list(args)))
        return code, out.getvalue(), err.getvalue()

    def build(self, data: Any, *extra: str, base_dir: Path | None = None) -> tuple[int, str, str]:
        source = self.dir / "content.json"
        source.write_text(json.dumps(data), encoding="utf-8")
        return self.run_builder(
            "--data", str(source), "--output", str(self.page), "--base-dir", str(base_dir or self.dir), *extra
        )

    def built(self, data: Any, *extra: str, base_dir: Path | None = None) -> str:
        code, _, err = self.build(data, *extra, base_dir=base_dir)
        self.assertEqual(code, 0, err)
        return self.page.read_text(encoding="utf-8")

    def problems(self, data: Any, *extra: str) -> str:
        self.page.unlink(missing_ok=True)
        code, out, err = self.build(data, *extra)
        self.assertEqual(code, 1, out + err)
        self.assertFalse(self.page.exists(), "a rejected build must write nothing")
        self.assertIn("nothing was written", err)
        return err


class HomePathTests(BuilderCase):
    def test_a_quoted_home_path_is_written_under_home(self) -> None:
        home = self.dir / "home"
        source = self.dir / "content.json"
        source.write_text(json.dumps(FIXTURE["content"]), encoding="utf-8")
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            code, _, err = self.run_builder("--data", str(source), "--output", "~/decisions/page.html")
        self.assertEqual(code, 0, err)
        self.assertTrue((home / "decisions" / "page.html").is_file())
        self.assertFalse(Path("~").exists(), "no literal ~ folder in the working directory")


class ExampleDocumentTests(BuilderCase):
    """The packaged example is what an agent reads to learn the format, so it must build as shipped."""

    def setUp(self) -> None:
        super().setUp()
        self.data = json.loads((EXAMPLE_DIR / "content.json").read_text(encoding="utf-8"))
        code, out, err = self.build(self.data, base_dir=EXAMPLE_DIR)
        self.assertEqual(code, 0, err)
        self.report = json.loads(out)
        self.html = self.page.read_text(encoding="utf-8")

    def test_report_counts_what_was_built(self) -> None:
        self.assertEqual(self.report["output"], str(self.page))
        self.assertEqual(self.report["documentId"], "lanternworks-booking-review")
        self.assertEqual((self.report["items"], self.report["options"], self.report["images"]), (4, 8, 4))
        self.assertEqual(self.report["bytes"], len(self.html.encode("utf-8")))
        self.assertNotIn("choices", self.report)

    def test_page_is_one_file_that_needs_no_network(self) -> None:
        self.assertTrue(self.html.startswith("<!doctype html>"))
        for remote in ("<link", "@import", "url(", 'src="http', "src='http", 'href="http', "//fonts."):
            self.assertNotIn(remote, self.html)
        sources = re.findall(r'<img[^>]*\ssrc="([^"]*)"', self.html)
        self.assertEqual(len(sources), 4)
        self.assertTrue(all(source.startswith("data:image/svg+xml;base64,") for source in sources))

    def test_policy_allows_only_the_shipped_script_and_embedded_images(self) -> None:
        scripts = SCRIPT_RE.findall(self.html)
        self.assertEqual(len(scripts), 1, "one executable script; the two data blocks are not script")
        digest = base64.b64encode(hashlib.sha256(scripts[0].encode("utf-8")).digest()).decode("ascii")
        policy = POLICY_RE.search(self.html)
        assert policy is not None
        self.assertEqual(
            policy.group(1),
            f"default-src 'none'; script-src 'sha256-{digest}'; style-src 'unsafe-inline'; "
            "img-src data:; base-uri 'none'; form-action 'none'",
        )
        self.assertEqual(
            scripts[0].strip(), (SKILL_DIR / "assets" / "decisions.js").read_text(encoding="utf-8").strip()
        )
        self.assertNotIn("<form", self.html)
        self.assertIsNone(re.search(r"\son[a-z]+=", self.html), "no inline event handlers")

    def test_page_shares_the_report_palette(self) -> None:
        tokens = (PLUGIN / "shared" / "visual" / "assets" / "report-tokens.css").read_text(encoding="utf-8")
        self.assertIn(tokens.strip(), self.html)
        self.assertIn((SKILL_DIR / "assets" / "decisions.css").read_text(encoding="utf-8").strip(), self.html)

    def test_page_has_overview_index_choices_and_a_walkthrough_per_item(self) -> None:
        for view in ("overview", "order", "items", "choices", "item", "about"):
            self.assertIn(f'data-view="{view}"', self.html)
        for item in self.data["items"]:
            self.assertIn(f'<article class="td-item" id="item-{item["id"]}" data-item="{item["id"]}"', self.html)
            self.assertIn(f'data-index-row="{item["id"]}"', self.html)
            self.assertIn(f'data-choice-row="{item["id"]}"', self.html)
            self.assertIn(f'data-nav-state="{item["id"]}"', self.html)
        self.assertIn("Booking a studio mostly works, but two people can still end up with the same room.", self.html)
        self.assertIn(">Start here<", self.html)
        self.assertIn("All 4 findings", self.html)

    def test_each_item_reads_summary_evidence_options_recommendation_decision(self) -> None:
        article = self.html[self.html.index('id="item-BOOK-001"') : self.html.index('id="item-BOOK-002"')]
        order = [
            article.index(marker)
            for marker in (
                ">Summary<",
                ">Why it matters<",
                'data-part="evidence"',
                'data-part="options"',
                'class="td-recommendation"',
                'data-part="choice"',
                ">How to tell it worked<",
                ">Limits of the evidence<",
                ">Source and details<",
            )
        ]
        self.assertEqual(order, sorted(order))
        self.assertIn(">What is uncertain<", article)
        self.assertIn("Source: BOOKING_REVIEW.md, capture 3 (synthetic)", article)
        self.assertIn("two confirmed glazing sessions in Studio B", article)
        self.assertIn(">What it gives you<", article)
        self.assertIn(">What it costs<", article)

    def test_recommendation_is_marked_but_nothing_is_chosen(self) -> None:
        self.assertEqual(self.html.count('<input type="radio"'), 8 + 4 + 3 + 2)
        self.assertIsNone(re.search(r"<input[^>]*\schecked", self.html.replace('value="keep" checked', "")))
        self.assertEqual(json.loads(STATE_RE.search(self.html).group(1))["decisions"], [])  # type: ignore[union-attr]
        self.assertIn('data-option="reserve-on-book" data-recommended>', self.html)
        self.assertIn('data-option="no-change" data-recommended>', self.html)
        self.assertEqual(self.html.count(">Your decision</h2>"), 4)
        self.assertEqual(self.html.count('class="td-kicker" id="rec-'), 4)

    def test_decision_statuses_are_the_four_and_decided_waits_for_a_choice(self) -> None:
        select = re.search(r'<select id="status-BOOK-001"[^>]*>(.*?)</select>', self.html)
        assert select is not None
        self.assertEqual(
            re.findall(r'<option value="([a-z]+)"( disabled)?>([^<]+)</option>', select.group(1)),
            [
                ("open", "", "Not decided"),
                ("decided", " disabled", "Decided"),
                ("discuss", "", "Needs discussion"),
                ("deferred", "", "Deferred"),
            ],
        )
        self.assertIn("Open in the review · reproduced twice on 14 January", self.html)

    def test_no_change_and_custom_follow_the_item(self) -> None:
        third = self.html[self.html.index('id="item-BOOK-003"') : self.html.index('id="item-BOOK-004"')]
        self.assertIn('value="custom"', third)
        self.assertNotIn('value="no-change"', third, "this item sets noChange to false")
        self.assertNotIn("data-recommended", third, "no option is recommended for this item")
        fourth = self.html[self.html.index('id="item-BOOK-004"') :]
        self.assertIn("Keep the 24-hour window", fourth)

    def test_catalog_gives_the_runtime_identities_not_content(self) -> None:
        catalog = json.loads(CATALOG_RE.search(self.html).group(1))  # type: ignore[union-attr]
        self.assertEqual(catalog["documentId"], "lanternworks-booking-review")
        self.assertEqual((catalog["nounOne"], catalog["nounMany"]), ("finding", "findings"))
        first = catalog["items"][0]
        self.assertEqual(sorted(first), ["fingerprint", "id", "noChange", "options", "recommended", "title"])
        self.assertEqual(
            first["options"][1],
            {"id": "staff-conflict-alert", "name": "Keep booking as it is and alert staff to conflicts", "letter": "B"},
        )
        self.assertEqual(first["recommended"], "reserve-on-book")
        self.assertEqual(catalog["items"][2]["noChange"], "")
        self.assertEqual(catalog["items"][2]["recommended"], "")


class ContentChecksTests(BuilderCase):
    def test_minimal_content_builds_with_default_nouns(self) -> None:
        html = self.built(content())
        self.assertIn("All 1 decision", html)
        self.assertNotIn('data-view="order"', html, "no suggested order unless the content gives one")
        self.assertNotIn('data-part="evidence"', html, "no evidence block unless the content has evidence")

    def test_every_problem_is_reported_in_one_run(self) -> None:
        data = content(
            id="bad id",
            options=[
                {"id": "Option A", "name": "A", "summary": "x"},
                {"id": "custom", "name": "B", "summary": "x"},
                {"id": "fine", "name": "C"},
            ],
            recommendation={"option": "missing", "summary": "x", "reasoning": "y"},
            evidence=[
                {"type": "video", "caption": "x"},
                {"type": "table", "caption": "x", "rows": [["a", "b"], ["c"]]},
            ],
            colour="red",
        )
        data["document"]["id"] = "No"
        data["document"]["generated"] = "15 January"
        err = self.problems(data)
        for expected in (
            "document.id: must be 3 to 64 lowercase letters",
            "document.generated: must be a date written as YYYY-MM-DD",
            "items[0].id: must be letters, digits, dots, hyphens, or underscores",
            ".options[0].id: must be lowercase letters, digits, and hyphens",
            '.options[1].id: must be lowercase letters, digits, and hyphens, and not "custom" or "no-change"',
            ".options[2]: needs a summary or benefits",
            ".recommendation.option: must be the id of one of this item's options",
            ".evidence[0].type: must be one of image, table, excerpt",
            ".evidence[1].rows: every row, and columns when given, must have the same number of cells",
            ".colour: is not a field this format has",
        ):
            self.assertIn(expected, err)

    def test_required_parts_are_named_when_missing(self) -> None:
        err = self.problems({"schemaVersion": 2, "document": {"title": "x"}, "items": [{"id": "T-1"}]})
        for expected in (
            "schemaVersion: must be 1",
            "document.id: is required",
            "document.summary: is required",
            "items[0] (T-1).title: is required",
            "items[0] (T-1).summary: is required",
            "items[0] (T-1).recommendation: is required",
        ):
            self.assertIn(expected, err)

    def test_ids_must_be_unique_and_references_must_resolve(self) -> None:
        data = content()
        data["items"].append(copy.deepcopy(data["items"][0]))
        data["items"][0]["options"].append({"id": "do-it", "name": "Again", "summary": "x"})
        data["document"]["startWith"] = ["T-9"]
        data["document"]["order"] = [{"title": "First", "items": ["T-1", "T-1", "T-8"]}]
        err = self.problems(data)
        self.assertIn('items[1].id: "T-1" is used more than once', err)
        self.assertIn('"do-it" is used more than once in this item', err)
        self.assertIn('document.startWith[0].item: "T-9" is not the id of an item', err)
        self.assertIn('"T-1" is placed in more than one group', err)
        self.assertIn('"T-8" is not the id of an item', err)

    def test_no_recommendation_needs_a_reason_and_no_change_must_be_offered(self) -> None:
        html = self.built(
            content(recommendation={"option": None, "summary": "Cannot say.", "reasoning": "Depends on cost."})
        )
        self.assertNotIn("data-recommended", html)
        self.assertNotIn('class="td-rec-target"', html)
        err = self.problems(content(recommendation={"option": None, "summary": "Cannot say."}))
        self.assertIn(".recommendation.reasoning: is required", err)
        err = self.problems(
            content(noChange=False, recommendation={"option": "no-change", "summary": "x", "reasoning": "y"})
        )
        self.assertIn(".recommendation.option: must be the id", err)

    def test_an_item_may_offer_no_ready_made_option(self) -> None:
        html = self.built(
            content(
                options=[],
                recommendation={"option": "no-change", "summary": "Leave it.", "reasoning": "No case for change."},
            )
        )
        self.assertIn("No ready-made option is offered here.", html)
        self.assertIn('value="custom"', html)
        self.assertIn('value="no-change"', html)

    def test_content_is_escaped_and_only_code_spans_pass(self) -> None:
        hostile = '<img src=x onerror="alert(1)"> & </script><script>alert(2)</script>'
        html = self.built(
            content(
                title=f"Title {hostile}",
                summary=f"Run `npm test --watch` then {hostile}",
                evidence=[{"type": "excerpt", "caption": "Log", "text": f"line one\n{hostile}", "source": hostile}],
                options=[{"id": "do-it", "name": hostile, "summary": hostile}],
            )
        )
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("<script>alert", html)
        self.assertEqual(len(SCRIPT_RE.findall(html)), 1)
        self.assertIn("<code>npm test --watch</code>", html)
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; &lt;/script&gt;", html)
        catalog = CATALOG_RE.search(html)
        assert catalog is not None
        self.assertNotIn("<", catalog.group(1))
        self.assertEqual(json.loads(catalog.group(1))["items"][0]["options"][0]["name"], hostile)

    def test_evidence_keeps_the_order_the_content_gives_it(self) -> None:
        (self.dir / "a.png").write_bytes(png(8, 4))
        (self.dir / "b.png").write_bytes(png(8, 4))
        html = self.built(
            content(
                evidence=[
                    {"type": "excerpt", "caption": "Read this first.", "text": "the request"},
                    {"type": "image", "file": "a.png", "caption": "First capture."},
                    {"type": "table", "caption": "Then the numbers.", "rows": [["Tries", 3]]},
                    {"type": "image", "file": "b.png", "caption": "Second capture."},
                ]
            )
        )
        order = [html.index(marker) for marker in ("Read this first.", "data-gallery", "Then the numbers.")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(html.count('<div class="td-gallery" data-gallery>'), 1, "the images share one gallery")
        gallery = html[html.index("data-gallery") : html.index("Then the numbers.")]
        self.assertIn("First capture.", gallery)
        self.assertIn("Second capture.", gallery)

    def test_evidence_table_and_excerpt_carry_caption_and_source(self) -> None:
        html = self.built(
            content(
                evidence=[
                    {
                        "type": "table",
                        "label": "Measured",
                        "caption": "From the log.",
                        "columns": ["What", "Value"],
                        "rows": [["Tries", 3], ["Rate", 0.5]],
                        "source": "run 7",
                    },
                    {"type": "excerpt", "caption": "The error.", "text": "  indented\nsecond", "source": "src/a.ts:12"},
                ]
            )
        )
        self.assertIn('<th scope="col">What</th><th scope="col">Value</th>', html)
        self.assertIn('<th scope="row">Tries</th><td>3</td>', html)
        self.assertIn('<th scope="row">Rate</th><td>0.5</td>', html)
        self.assertIn('<p class="td-source">Source: run 7</p>', html)
        self.assertIn('<pre tabindex="0"><code>  indented\nsecond</code></pre>', html)
        self.assertIn('<p class="td-source">Source: src/a.ts:12</p>', html)


class VisualAidTests(BuilderCase):
    """Charts the builder draws, and the mark on anything made for the document."""

    def chart(self, **fields: Any) -> dict[str, Any]:
        entry = {"type": "chart", "caption": "Export time grows with the range.", "source": "REVIEW.md, table 2"}
        entry.update(fields)
        return content(evidence=[entry])

    def test_a_chart_is_bars_on_one_scale_with_every_value_readable(self) -> None:
        html = self.built(self.chart(label="Time to export", unit="s", rows=[["1 month", 4], ["12 months", 48]]))
        self.assertIn('<section class="td-record td-chart"><h3>Time to export</h3>', html)
        self.assertIn(
            '<tr><th scope="row">1 month</th><td><span class="td-bar-track">'
            '<span class="td-bar" style="--size:0.0833"></span><span class="td-bar-value">4 s</span></span></td></tr>',
            html,
        )
        self.assertIn('style="--size:1.0000"></span><span class="td-bar-value">48 s</span>', html)
        self.assertNotIn("data-muted", html.split("<body>")[1].split("<script")[0])
        self.assertNotIn('class="td-limit"', html)

    def test_a_limit_sets_the_scale_and_emphasis_mutes_the_rest(self) -> None:
        html = self.built(
            self.chart(
                unit="s",
                rows=[["1 month", 4], ["3 months", 12], ["12 months", 20]],
                emphasize=["12 months"],
                limit={"label": "The proxy closes the connection", "value": 40},
            )
        )
        self.assertIn('<tr data-muted><th scope="row">1 month</th>', html)
        self.assertIn('<tr><th scope="row">12 months</th>', html)
        self.assertIn('style="--size:0.5000"></span><span class="td-bar-value">20 s</span>', html)
        self.assertEqual(html.count('<span class="td-limit" style="--at:1.0000" aria-hidden="true"></span>'), 3)
        self.assertIn("</span>The proxy closes the connection: 40 s</p>", html)

    def test_values_are_written_the_way_a_reader_expects(self) -> None:
        self.assertEqual(evidence_module.amount_text(51000, ""), "51,000")
        self.assertEqual(evidence_module.amount_text(4.5, "s"), "4.5 s")
        self.assertEqual(evidence_module.amount_text(62.0, "%"), "62%")
        self.assertEqual(evidence_module.amount_text(0.125, "ms"), "0.125 ms")
        self.assertEqual(evidence_module.amount_text(48.3333333, "s"), "48.333 s")

    def test_a_chart_is_marked_as_made_for_the_document_and_names_its_numbers(self) -> None:
        html = self.built(self.chart(rows=[["a", 1], ["b", 2]]))
        self.assertIn(
            '<p class="td-source"><span class="td-added">Made for this document</span>Source: REVIEW.md, table 2</p>',
            html,
        )
        data = self.chart(rows=[["a", 1], ["b", 2]])
        del data["items"][0]["evidence"][0]["source"]
        self.assertIn(".evidence[0].source: is required for something made for this document", self.problems(data))
        data["items"][0]["evidence"][0]["origin"] = "source"
        problems = self.problems(data)
        self.assertIn('.evidence[0].origin: must be "added" or left out: a chart is always made', problems)
        self.assertIn(".evidence[0].source: is required for something made for this document", problems)

    def test_charts_that_would_mislead_or_say_nothing_are_refused(self) -> None:
        cases: list[tuple[dict[str, Any], str]] = [
            ({"rows": []}, ".rows: needs 2 to 12 bars"),
            ({"rows": [["only", 3]]}, ".rows: needs 2 to 12 bars"),
            ({"rows": [[str(n), n] for n in range(1, 14)]}, ".rows: needs 2 to 12 bars"),
            ({"rows": [["a", -1], ["b", 2]]}, ".rows[0]: needs a number of zero or more"),
            ({"rows": [["a", "4"], ["b", 2]]}, ".rows[0]: needs a number of zero or more"),
            ({"rows": [["a", True], ["b", 2]]}, ".rows[0]: needs a number of zero or more"),
            ({"rows": [["a", 1], ["a", 2]]}, '.rows[1]: "a" appears more than once'),
            ({"rows": [["a", 0], ["b", 0]]}, ".rows: has no value above zero"),
            ({"rows": [["a", 1], ["b", 2]], "emphasize": ["c"]}, '.emphasize: "c" is not the label of a bar'),
            ({"rows": [["a", 1], ["b", 2]], "limit": {"label": "Cap", "value": 0}}, ".limit: must be an object"),
            ({"rows": [["a", 1], ["b", 2]], "limit": {"value": 3}}, ".limit.label: is required"),
            ({"rows": "a,b"}, ".rows: is required: a list of [label, number] pairs"),
            ({"rows": [["a", 1], ["b", 2]], "colour": "red"}, ".colour: is not a field this format has"),
        ]
        for fields, expected in cases:
            with self.subTest(expected):
                self.assertIn(f".evidence[0]{expected}", self.problems(self.chart(**fields)))

    def test_anything_made_for_the_document_is_marked_and_must_say_what_from(self) -> None:
        (self.dir / "flow.png").write_bytes(png(8, 4))
        added = {"type": "image", "file": "flow.png", "caption": "How it happens.", "origin": "added"}
        html = self.built(content(evidence=[{**added, "source": "Drawn from REVIEW.md, section 2"}]))
        self.assertIn(
            '<span class="td-source"><span class="td-added">Made for this document</span>'
            "Source: Drawn from REVIEW.md, section 2</span>",
            html,
        )
        # An image's source falls back to its path, so the mark is never left without one.
        self.assertIn("Made for this document</span>Source: flow.png", self.built(content(evidence=[added])))
        plain = self.built(content(evidence=[{"type": "image", "file": "flow.png", "caption": "A capture."}]))
        self.assertNotIn('class="td-added"', plain)
        excerpt = {"type": "excerpt", "caption": "Quoted.", "text": "x", "origin": "added"}
        self.assertIn(
            ".evidence[0].source: is required for something made for this document",
            self.problems(content(evidence=[excerpt])),
        )
        self.assertIn(
            ".evidence[0].origin: must be one of source, added",
            self.problems(content(evidence=[{**excerpt, "origin": "mine"}])),
        )

    def test_the_diagram_starter_and_the_example_diagram_are_embeddable_as_shipped(self) -> None:
        for name in ("diagram-template.svg", "example/double-booking-flow.svg"):
            with self.subTest(name):
                url, width, height = images.embed_image(SKILL_DIR / "assets" / name)
                self.assertTrue(url.startswith("data:image/svg+xml;base64,"))
                self.assertEqual(width, 960)
                self.assertGreater(height, 300)

    def test_the_example_shows_each_kind_of_visual_aid(self) -> None:
        data = json.loads((EXAMPLE_DIR / "content.json").read_text(encoding="utf-8"))
        kinds = {entry["type"] for item in data["items"] for entry in item.get("evidence", [])}
        self.assertEqual(kinds, {"image", "table", "excerpt", "chart"})
        self.assertTrue(any(item.get("steps") for item in data["items"]))
        drawn = [e for item in data["items"] for e in item.get("evidence", []) if e.get("origin") == "added"]
        self.assertEqual([entry["file"] for entry in drawn], ["double-booking-flow.svg"])


class EvidenceImageTests(BuilderCase):
    def image_item(self, **fields: Any) -> dict[str, Any]:
        return content(evidence=[{"type": "image", "caption": "What it shows.", **fields}])

    def test_png_is_embedded_with_its_size_and_a_default_source(self) -> None:
        (self.dir / "shots").mkdir()
        (self.dir / "shots" / "wide.png").write_bytes(png(8, 4))
        html = self.built(self.image_item(file="shots/wide.png"))
        data_url = "data:image/png;base64," + base64.b64encode(png(8, 4)).decode("ascii")
        self.assertIn(f'<img src="{data_url}" alt="What it shows." width="8" height="4" decoding="async">', html)
        self.assertIn('<span class="td-source">Source: shots/wide.png</span>', html)
        self.assertNotIn('class="td-shot td-shot--tall"', html)
        self.assertNotIn('class="td-tabs"', html, "one image needs no tabs")

    def test_tall_captures_several_images_and_a_focus_point(self) -> None:
        (self.dir / "phone.png").write_bytes(png(4, 9))
        (self.dir / "wide.png").write_bytes(png(9, 4))
        data = content(
            evidence=[
                {"type": "image", "file": "phone.png", "label": "Phone", "caption": "Tall.", "alt": "A phone screen"},
                {
                    "type": "image",
                    "file": str(self.dir / "wide.png"),
                    "caption": "Wide.",
                    "focus": "50% 20%",
                    "source": "round 2",
                },
            ]
        )
        html = self.built(data)
        self.assertIn('class="td-shot td-shot--tall"', html)
        self.assertIn('alt="A phone screen"', html)
        self.assertIn('<button type="button" class="td-tab" data-shot="0" aria-pressed="true">Phone</button>', html)
        self.assertIn('data-shot="1" aria-pressed="false">View 2</button>', html)
        self.assertIn('class="td-shot td-shot--focus"', html)
        self.assertIn('style="object-position:50% 20%"', html)
        self.assertIn("Cropped · open the full capture", html)
        self.assertIn("Source: round 2", html)

    def test_other_formats_are_recognized_by_their_bytes(self) -> None:
        self.assertEqual(images.sniff_image(b"GIF89a" + struct.pack("<HH", 5, 7) + b"\x00" * 8), ("image/gif", 5, 7))
        jpeg = b"\xff\xd8\xff\xe0\x00\x04\x00\x00\xff\xc0\x00\x11\x08" + struct.pack(">HH", 30, 40) + b"\x00" * 16
        self.assertEqual(images.sniff_image(jpeg), ("image/jpeg", 40, 30))
        self.assertEqual(images.sniff_image(b"RIFF\x00\x00\x00\x00WEBPVP8 ")[0], "image/webp")
        self.assertEqual(images.sniff_image(b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00")[0], "image/avif")
        self.assertEqual(
            images.sniff_image(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 390 760"></svg>'),
            ("image/svg+xml", 390, 760),
        )
        self.assertEqual(images.sniff_image(b'<?xml version="1.0"?>\n<svg></svg>'), ("image/svg+xml", 0, 0))
        self.assertIsNone(images.sniff_image(b"%PDF-1.7"))

    def test_missing_wrong_and_active_files_are_refused(self) -> None:
        (self.dir / "notes.txt").write_text("not an image", encoding="utf-8")
        (self.dir / "active.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', encoding="utf-8"
        )
        (self.dir / "handler.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" onload="x()"></svg>', encoding="utf-8"
        )
        (self.dir / "remote.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/a.png"/></svg>', encoding="utf-8"
        )
        self.assertIn(".evidence[0].file: cannot be read", self.problems(self.image_item(file="absent.png")))
        self.assertIn(
            ".evidence[0].file: is not a PNG, JPEG, GIF, WebP, AVIF, or SVG image",
            self.problems(self.image_item(file="notes.txt")),
        )
        for name in ("active.svg", "handler.svg", "remote.svg"):
            self.assertIn(
                "is an SVG with script, event handlers, embedded HTML, or remote references",
                self.problems(self.image_item(file=name)),
            )
        self.assertIn(
            '.evidence[0].focus: must be two percentages such as "50% 20%"',
            self.problems(self.image_item(file="notes.txt", focus="top")),
        )
        self.assertIn(
            ".evidence[0].caption: is required",
            self.problems(content(evidence=[{"type": "image", "file": "notes.txt"}])),
        )


class IdentityTests(BuilderCase):
    def fingerprints(self, data: Any) -> dict[str, str]:
        catalog = CATALOG_RE.search(self.built(data))
        assert catalog is not None
        return {item["id"]: item["fingerprint"] for item in json.loads(catalog.group(1))["items"]}

    def test_fixture_fingerprints_are_pinned(self) -> None:
        catalog = CATALOG_RE.search(self.built(FIXTURE["content"]))
        assert catalog is not None
        self.assertEqual(json.loads(catalog.group(1)), FIXTURE["catalog"])

    def test_supporting_material_does_not_change_an_item_version(self) -> None:
        base = self.fingerprints(content())["T-1"]
        refined = content(
            title="A  thing to\n decide",
            impact="Now with a reason.",
            labels=["New label"],
            status="Rechecked",
            evidence=[{"type": "excerpt", "caption": "New.", "text": "proof"}],
            recommendation={"option": None, "summary": "Changed my mind.", "reasoning": "New evidence."},
            uncertainty="Some.",
            successCriteria=["It works."],
            details=[{"label": "Owner", "value": "Someone"}],
        )
        self.assertEqual(self.fingerprints(refined)["T-1"], base)

    def test_statement_and_options_do_change_it(self) -> None:
        base = self.fingerprints(content())["T-1"]
        changes: list[dict[str, Any]] = [
            {"title": "A different thing to decide"},
            {"summary": "What is now true."},
            {"options": [{"id": "do-it", "name": "Do it", "summary": "Go ahead, slowly."}]},
            {"options": [{"id": "do-it", "name": "Do it", "summary": "Go ahead.", "tradeoffs": "Costs a week."}]},
            {
                "options": [{"id": "do-it-now", "name": "Do it", "summary": "Go ahead."}],
                "recommendation": {"option": None, "summary": "x", "reasoning": "y"},
            },
            {"noChange": False},
            {"noChange": {"label": "Keep the rule"}},
        ]
        seen = {base}
        for change in changes:
            with self.subTest(change=sorted(change)):
                changed = self.fingerprints(content(**change))["T-1"]
                self.assertNotIn(changed, seen)
                seen.add(changed)


class CarryChoicesTests(BuilderCase):
    def carry(self, payload: Any, name: str = "choices.json") -> tuple[int, str, str]:
        choices = self.dir / name
        choices.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
        return self.build(FIXTURE["content"], "--choices", str(choices))

    def test_shared_cases_match_the_page_runtime(self) -> None:
        for entry in FIXTURE["cases"]:
            with self.subTest(entry["name"]):
                self.page.unlink(missing_ok=True)
                code, out, err = self.carry(entry["payload"])
                if entry["expect"].get("error"):
                    self.assertEqual(code, 1, out)
                    self.assertIn("build-decisions: choices: ", err)
                    self.assertFalse(self.page.exists())
                    continue
                self.assertEqual(code, 0, err)
                report = json.loads(out)["choices"]
                self.assertEqual(
                    {
                        "carried": report["carried"],
                        "needsReview": report["needsReview"],
                        "dropped": [entry["itemId"] for entry in report["dropped"]],
                    },
                    entry["expect"],
                )
                seed = STATE_RE.search(self.page.read_text(encoding="utf-8"))
                assert seed is not None
                embedded = [record["itemId"] for record in json.loads(seed.group(1))["decisions"]]
                self.assertEqual(sorted(embedded), sorted([*report["carried"], *report["needsReview"]]))

    def test_carried_records_are_embedded_as_recorded(self) -> None:
        notes = 'Keep.\n</script><script>alert(1)</script> & "quoted"'
        record = {
            "itemId": "A-1",
            "option": "swap-b",
            "status": "decided",
            "notes": notes,
            "updatedAt": "2026-01-16T09:00:00.000Z",
            "itemFingerprint": FIXTURE["catalog"]["items"][0]["fingerprint"],
        }
        payload = {
            "format": "trackbed-decisions",
            "schemaVersion": 1,
            "document": {"id": "fixture-doc"},
            "decisions": [record],
        }
        code, _, err = self.carry(payload)
        self.assertEqual(code, 0, err)
        html = self.page.read_text(encoding="utf-8")
        seed = STATE_RE.search(html)
        assert seed is not None
        self.assertNotIn("<", seed.group(1))
        state = json.loads(seed.group(1))
        self.assertEqual(state["decisions"], [record])
        self.assertEqual(
            (state["format"], state["schemaVersion"], state["document"]["id"]), ("trackbed-decisions", 1, "fixture-doc")
        )
        self.assertEqual(len(SCRIPT_RE.findall(html)), 1)
        self.assertIsNone(
            re.search(r"<input[^>]*\schecked", html.replace('value="keep" checked', "")),
            "the runtime applies the choice; the markup starts clear",
        )

    def test_a_saved_copy_is_read_for_its_choices(self) -> None:
        record = {
            "itemId": "A-2",
            "option": "custom",
            "status": "discuss",
            "notes": "Talk first.",
            "updatedAt": "2026-01-16T09:00:00.000Z",
            "itemFingerprint": FIXTURE["catalog"]["items"][1]["fingerprint"],
        }
        payload = {
            "format": "trackbed-decisions",
            "schemaVersion": 1,
            "document": {"id": "fixture-doc"},
            "decisions": [record],
        }
        copy_html = (
            '<!doctype html><html><body><script type="application/json" id="trackbed-decisions-state">'
            f"{inline_page.json_script(payload)}</script></body></html>"
        )
        code, out, err = self.carry(copy_html, "saved-copy.html")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["choices"], {"carried": ["A-2"], "needsReview": [], "dropped": []})

    def test_dropped_records_are_named_with_their_reason(self) -> None:
        payload = {
            "format": "trackbed-decisions",
            "schemaVersion": 1,
            "document": {"id": "fixture-doc"},
            "decisions": [
                {
                    "itemId": "Z-9",
                    "itemTitle": "Removed item",
                    "option": "x",
                    "status": "decided",
                    "notes": "Gone.",
                    "updatedAt": "2026-01-16T09:00:00.000Z",
                    "itemFingerprint": "abc",
                }
            ],
        }
        code, out, err = self.carry(payload)
        self.assertEqual(code, 0, err)
        self.assertEqual(
            json.loads(out)["choices"]["dropped"],
            [{"itemId": "Z-9", "itemTitle": "Removed item", "reason": "no item with this id in the rebuilt document"}],
        )

    def test_unreadable_choices_files_are_file_errors(self) -> None:
        code, _, err = self.carry("{ not json")
        self.assertEqual(code, 2)
        self.assertIn("is not valid JSON", err)
        code, _, err = self.carry("<html><body>just a page</body></html>", "other.html")
        self.assertEqual(code, 2)
        self.assertIn("is not a decision document, so it holds no choices to carry over", err)
        code, _, err = self.build(FIXTURE["content"], "--choices", str(self.dir / "absent.json"))
        self.assertEqual(code, 2)
        self.assertIn("cannot read the choices file", err)
        self.assertFalse(self.page.exists())


class CommandTests(BuilderCase):
    def test_file_and_usage_errors_exit_2(self) -> None:
        code, _, err = self.run_builder("--data", str(self.dir / "absent.json"), "--output", str(self.page))
        self.assertEqual(code, 2)
        self.assertIn("cannot read the content file", err)
        broken = self.dir / "broken.json"
        broken.write_text("{", encoding="utf-8")
        code, _, err = self.run_builder("--data", str(broken), "--output", str(self.page))
        self.assertEqual(code, 2)
        self.assertIn("is not valid JSON", err)
        source = self.dir / "content.json"
        source.write_text(json.dumps(content()), encoding="utf-8")
        code, _, err = self.run_builder("--data", str(source), "--output", str(self.dir / "page.txt"))
        self.assertEqual(code, 2)
        self.assertIn("the output must be an .html file", err)

    def test_a_rebuild_replaces_the_page_and_a_failed_one_leaves_it(self) -> None:
        first = self.built(content())
        second = self.built(content(title="A second title"))
        self.assertNotEqual(first, second)
        code, _, _ = self.build(content(id="bad id"))
        self.assertEqual(code, 1)
        self.assertEqual(self.page.read_text(encoding="utf-8"), second)
        self.assertEqual([path.name for path in self.dir.iterdir() if path.name.startswith(".")], [])

    def test_output_directories_are_created(self) -> None:
        source = self.dir / "content.json"
        source.write_text(json.dumps(content()), encoding="utf-8")
        target = self.dir / "new" / "nested" / "page.html"
        code, out, err = self.run_builder("--data", str(source), "--output", str(target))
        self.assertEqual(code, 0, err)
        self.assertTrue(target.is_file())
        self.assertEqual(json.loads(out)["output"], str(target))

    def test_shipped_assets_cannot_close_their_own_element(self) -> None:
        for name, closing in (("decisions.css", "</style"), ("decisions.js", "</script")):
            self.assertNotIn(closing, (SKILL_DIR / "assets" / name).read_text(encoding="utf-8").lower())
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.js"
            bad.write_text("const x = '</script>';", encoding="utf-8")
            with self.assertRaises(builder.BuildError):
                builder.read_asset(bad, "</script")


if __name__ == "__main__":
    unittest.main()
