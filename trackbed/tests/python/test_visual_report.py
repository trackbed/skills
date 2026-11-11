"""Contract checks and runtime injection for `scripts/visual-report.py`."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import importlib.util
import io
import re
import stat
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PLUGIN / "scripts" / "visual-report.py"
ASSETS = PLUGIN / "shared" / "visual" / "assets"
TEMPLATE = ASSETS / "report-findings.html"
SHAPES = ("findings", "plan", "qa", "inquiry", "assessment")
NEEDS_SHAPE = (
    "<main data-report> needs data-shape, one of findings, plan, qa, inquiry, assessment, as the skill names it"
)

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("visual_report", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
visual_report = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = visual_report
SPEC.loader.exec_module(visual_report)

PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Sample</title>
    {head}
    <style data-trackbed-runtime></style>
  </head>
  <body>
    <main data-report data-shape="findings" data-producer="trackbed:qa" data-source="QA_REPORT.md"
          data-generated="2026-01-15T14:02:00+0100" {main}>
      <header data-report-header><h1>Sample</h1></header>
      <section data-section id="findings">
        <h2>Findings</h2>
        {body}
      </section>
    </main>
    <script data-trackbed-runtime></script>
  </body>
</html>
"""
ENTRY = '<article data-entry data-id="E-01" data-severity="high"><h3>Title</h3><p>Body</p></article>'


def page(body: str = ENTRY, head: str = "", main: str = "") -> str:
    return PAGE.format(body=body, head=head, main=main)


def problems(source: str) -> list[str]:
    return [re.sub(r"^line \d+: ", "", problem) for problem in visual_report.scan_page(source).problems]


class ContractTests(unittest.TestCase):
    def test_the_shipped_template_follows_the_contract(self) -> None:
        scan = visual_report.scan_page(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(scan.problems, [])
        self.assertEqual((scan.entries, scan.sections), (4, 5))

    def test_template_comments_do_not_read_as_hidden_instructions(self) -> None:
        # SkillSpector's P2 rule spans from the first HTML comment to any later one and
        # fires at HIGH on these words in between, which fails the security gate.
        hidden = re.compile(r"<!--.*?(?:system|instructions?|ignore|POST|GET|send|transmit).*?-->", re.I | re.S)
        templates = [ASSETS / f"report-{shape}.html" for shape in SHAPES]
        for path in (*templates, PLUGIN / "shared" / "visual" / "references" / "visual-report.md"):
            with self.subTest(path=path.name):
                match = hidden.search(path.read_text(encoding="utf-8"))
                self.assertIsNone(match, match.group(0)[-160:] if match else "")

    def test_every_shape_has_a_template_that_follows_the_contract(self) -> None:
        for shape in SHAPES:
            with self.subTest(shape=shape):
                source = (ASSETS / f"report-{shape}.html").read_text(encoding="utf-8")
                self.assertEqual(visual_report.scan_page(source).problems, [])
                self.assertIn(f'data-shape="{shape}"', source)
        self.assertEqual(tuple(visual_report.SHAPES), SHAPES)

    def test_a_minimal_page_passes(self) -> None:
        self.assertEqual(problems(page()), [])

    def test_problems_name_the_line_they_are_on(self) -> None:
        found = visual_report.scan_page(page(body='<p onclick="x()">hi</p>')).problems
        self.assertEqual(len(found), 1)
        self.assertRegex(found[0], r"^line 16: <p> has the event handler attribute onclick")

    def test_the_page_may_carry_no_script_or_remote_resource_of_its_own(self) -> None:
        cases = {
            "<script>alert(1)</script>": "only <script data-trackbed-runtime></script> may appear",
            '<link rel="stylesheet" href="https://example.com/a.css">': "<link> is not allowed",
            '<iframe src="https://example.com"></iframe>': "<iframe> is not allowed",
            '<img src="https://example.com/a.png" alt="">': "<img src> must use a relative path or a data URL",
            '<img src="//example.com/a.png" alt="">': "<img src> must use a relative path or a data URL",
            '<img src="data:text/html;base64,AAAA" alt="">': "<img src> data URL must be a base64",
            '<img src="a.png" srcset="https://example.com/a.png 1x" alt="">': "<img srcset> must use a relative",
            '<img src="a.png" srcset="b.png 1x, //example.com/c.png 2x" alt="">': "<img srcset> must use a relative",
            '<picture><source srcset="https://example.com/a.png"></picture>': "<source srcset> must use a relative",
            '<p srcset="a.png">x</p>': "<p srcset> is not allowed",
            '<svg width="1" role="img" aria-label="x"><image href="https://example.com/p.png"/></svg>': (
                "<image href> must use a relative path"
            ),
            '<svg width="1" role="img" aria-label="x"><use xlink:href="//example.com/s.svg#a"/></svg>': (
                "<use xlink:href> must use a relative path"
            ),
            '<a href="javascript:alert(1)">x</a>': '<a href> uses the "javascript:" scheme',
            '<a href=" JavaScript:alert(1)">x</a>': '<a href> uses the "javascript:" scheme',
            '<a href="java&#9;script:alert(1)">x</a>': '<a href> uses the "javascript:" scheme',
            '<a href="java&#10;script:alert(1)">x</a>': '<a href> uses the "javascript:" scheme',
            '<a href="&#1;javascript:alert(1)">x</a>': '<a href> uses the "javascript:" scheme',
            '<video src="clip.mp4"></video>': "<video src> is not allowed",
            '<p onmouseover="x()">x</p>': "event handler attribute onmouseover",
            '<form action="/x"></form>': "<form> is not allowed",
        }
        for body, expected in cases.items():
            with self.subTest(body=body):
                found = problems(page(body=body))
                self.assertTrue(any(expected in problem for problem in found), found)

    def test_a_self_closing_raw_text_element_is_rejected(self) -> None:
        source = page().replace("<script data-trackbed-runtime></script>", "<script data-trackbed-runtime />")
        self.assertEqual(
            problems(source),
            ["write <script ...></script>, not a self-closing <script />, which a browser leaves open"],
        )
        source = page().replace("<style data-trackbed-runtime></style>", "<style data-trackbed-runtime/>")
        self.assertEqual(
            problems(source),
            ["write <style ...></style>, not a self-closing <style />, which a browser leaves open"],
        )
        self.assertIn(
            "write <textarea ...></textarea>, not a self-closing <textarea />, which a browser leaves open",
            problems(page(body=ENTRY + "<textarea />")),
        )

    def test_links_and_local_or_embedded_images_are_allowed(self) -> None:
        body = (
            ENTRY
            + '<a href="https://github.com/o/r/pull/1">PR</a><a href="QA_REPORT.md">source</a>'
            + '<a href="#findings">up</a>'
            + '<img src="evidence/shot-1.png" alt="Checkout page">'
            + '<img src="data:image/png;base64,iVBORw0KGgo=" alt="Chart">'
            + '<img src="shot.png" srcset="shot-2x.png 2x, data:image/png;base64,iVBORw0KGgo= 3x" alt="Retina">'
            + '<svg width="1" role="img" aria-label="Icon"><use href="#icon"/><image href="evidence/a.png"/></svg>'
        )
        self.assertEqual(problems(page(body=body)), [])

    def test_an_authored_policy_is_rejected(self) -> None:
        head = '<meta http-equiv="Content-Security-Policy" content="default-src *">'
        self.assertIn(
            "<meta http-equiv> is not allowed; this script adds the Content-Security-Policy",
            problems(page(head=head)),
        )

    def test_entries_need_unique_ids_titles_and_a_known_severity(self) -> None:
        cases = {
            "<article data-entry><h3>T</h3></article>": "every data-entry needs a data-id",
            '<article data-entry data-id="a b"><h3>T</h3></article>': "every data-entry needs a data-id",
            ENTRY + ENTRY: 'entry id "E-01" is used more than once',
            '<article data-entry data-id="E-01"><p>No title</p></article>': "entry E-01 needs an <h3> title",
            '<article data-entry data-id="E-01" data-severity="important"><h3>T</h3></article>': (
                'entry E-01 has data-severity="important"; use one of critical, high, medium, low, suggestion'
            ),
            '<article data-entry data-id="E-01"><h3>T</h3>'
            '<article data-entry data-id="E-02"><h3>T</h3></article></article>': (
                "entry E-02 is nested inside another entry"
            ),
        }
        for body, expected in cases.items():
            with self.subTest(body=body):
                found = problems(page(body=body))
                self.assertTrue(any(expected in problem for problem in found), found)

    def test_an_entry_opens_with_prose_and_sits_in_a_section(self) -> None:
        fields_only = (
            '<article data-entry data-id="E-01"><h3>T</h3><p data-where><code data-loc>a.ts:1</code></p>'
            '<dl class="tr-fields"><dt>Evidence</dt><dd>x</dd></dl></article>'
        )
        self.assertIn(
            "entry E-01 needs a lead paragraph: one or two plain sentences, before any fields, "
            "saying what it is and why it matters",
            problems(page(body=fields_only)),
        )
        with_lead = fields_only.replace("<dl", "<p>It breaks the export.</p><dl")
        self.assertEqual(problems(page(body=with_lead)), [])
        loose = page().replace(
            "</section>", '</section><article data-entry data-id="E-02"><h3>T</h3><p>x</p></article>'
        )
        self.assertIn("entry E-02 must be inside a data-section, so the outline can list it", problems(loose))
        self.assertIn(
            "data-where belongs inside an entry, directly after its <h3>",
            problems(page(body=ENTRY + "<p data-where>a.ts:1</p>")),
        )

    def test_figures_and_images_need_a_text_alternative(self) -> None:
        svg_problem = 'an <svg> needs role="img" and an aria-label that says what it shows'
        self.assertIn(svg_problem, problems(page(body=ENTRY + '<svg width="10" viewBox="0 0 1 1"></svg>')))
        self.assertIn(svg_problem, problems(page(body=ENTRY + '<svg role="img" aria-label=" "></svg>')))
        named = ENTRY + '<svg role="img" aria-label="Findings per file"></svg><svg aria-hidden="true"></svg>'
        self.assertEqual(problems(page(body=named)), [])
        self.assertIn(
            "an <img> needs an alt attribute that says what it shows",
            problems(page(body=ENTRY + '<img src="evidence/shot.png">')),
        )

    def test_every_page_names_its_shape_and_carries_the_part_that_shape_is_for(self) -> None:
        unshaped = page().replace(' data-shape="findings"', "")
        self.assertIn(
            NEEDS_SHAPE,
            problems(unshaped),
        )
        self.assertIn(
            NEEDS_SHAPE,
            problems(page().replace('data-shape="findings"', 'data-shape="review"')),
        )
        for shape in ("plan", "inquiry"):
            with self.subTest(shape=shape):
                self.assertEqual(problems(page().replace('data-shape="findings"', f'data-shape="{shape}"')), [])
        assessment = page().replace('data-shape="findings"', 'data-shape="assessment"')
        self.assertIn("an assessment page needs its scores in an element marked data-scorecard", problems(assessment))
        scored = assessment.replace("<section data-section", "<table data-scorecard></table><section data-section", 1)
        self.assertEqual(problems(scored), [])
        qa = page().replace('data-shape="findings"', 'data-shape="qa"')
        self.assertIn("a qa page needs what was tested in an element marked data-tested", problems(qa))
        self.assertEqual(problems(qa.replace("<h2>Findings</h2>", "<h2>Findings</h2><table data-tested></table>")), [])

    def test_the_entry_noun_is_a_singular_and_a_plural(self) -> None:
        self.assertEqual(problems(page(main='data-noun="plan plans"')), [])
        self.assertIn(
            'data-noun takes the singular and plural of what an entry is, such as "plan plans"',
            problems(page(main='data-noun="plans"')),
        )
        self.assertIn('facet "shape" is a reserved name; choose another', problems(page(main='data-facets="shape"')))

    def test_an_entry_outside_the_report_is_rejected(self) -> None:
        source = page().replace("</main>", '</main><article data-entry data-id="E-02"><h3>T</h3></article>')
        self.assertIn("entry E-02 must be inside <main data-report>", problems(source))

    def test_sections_need_a_title_and_ids_stay_unique(self) -> None:
        source = page().replace("<h2>Findings</h2>", "")
        self.assertIn("a data-section needs an <h2> title", problems(source))
        duplicated = page(body=ENTRY + '<p id="findings">x</p>')
        self.assertIn('id "findings" is used more than once', problems(duplicated))

    def test_report_attributes_are_checked(self) -> None:
        self.assertEqual(problems(page(main='data-facets="severity status wave" data-root="/work/project"')), [])
        self.assertIn('facet "id" is a reserved name; choose another', problems(page(main='data-facets="id"')))
        self.assertIn(
            'facet "Wave" must be lowercase letters, digits, and hyphens',
            problems(page(main='data-facets="Wave"')),
        )
        self.assertIn(
            "data-root must be the absolute project root; omit it when unknown",
            problems(page(main='data-root="project"')),
        )
        undated = page().replace('data-generated="2026-01-15T14:02:00+0100"', 'data-generated="today"')
        self.assertIn(
            "<main data-report> needs data-generated as an ISO 8601 date or date-time",
            problems(undated),
        )
        unsourced = page().replace('data-source="QA_REPORT.md"', "")
        self.assertIn("<main data-report> needs data-source", problems(unsourced))

    def test_document_requirements_are_reported_together(self) -> None:
        found = problems("<html><head><title></title></head><body><p>hi</p></body></html>")
        for expected in (
            "the page must start with <!doctype html>",
            "<html> needs a lang attribute",
            '<head> needs <meta charset="utf-8">',
            "<title> must not be empty",
            "the page needs exactly one <main data-report>, found 0",
            "the page needs <header data-report-header> holding the <h1> title",
            "the page needs at least one data-section",
            "the page needs exactly one <style data-trackbed-runtime></style> in <head>, found 0",
            "the page needs exactly one <script data-trackbed-runtime></script>, found 0",
        ):
            self.assertIn(expected, found)

    def test_follow_up_commands_are_single_short_lines(self) -> None:
        good = '<meta name="trackbed-followup" content="/trackbed:pr:resolve-review">'
        self.assertEqual(problems(page(head=good)), [])
        for content in ("", "a\nb", "x" * 201):
            with self.subTest(content=content[:8]):
                found = problems(page(head=f'<meta name="trackbed-followup" content="{content}">'))
                self.assertTrue(any("needs one command on one line" in problem for problem in found), found)


class FinalizeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.css, self.script = visual_report.load_runtime()

    def finalize(self, source: str) -> str:
        scan = visual_report.scan_page(source)
        self.assertEqual(scan.problems, [])
        return str(visual_report.finalize(source, scan, self.css, self.script))

    def test_the_runtime_and_a_matching_policy_are_written_into_the_page(self) -> None:
        done = self.finalize(page())
        self.assertIn(f"<style data-trackbed-runtime>{self.css}</style>", done)
        self.assertIn(f"<script data-trackbed-runtime>{self.script}</script>", done)
        digest = base64.b64encode(hashlib.sha256(self.script.encode("utf-8")).digest()).decode("ascii")
        policy = re.search(r'<meta http-equiv="Content-Security-Policy" data-trackbed-runtime content="([^"]+)">', done)
        assert policy is not None
        self.assertEqual(
            policy.group(1),
            f"default-src 'none'; script-src 'sha256-{digest}'; style-src 'unsafe-inline'; "
            "img-src 'self' data: file:; base-uri 'none'; form-action 'none'",
        )
        self.assertLess(done.index("Content-Security-Policy"), done.index("<style data-trackbed-runtime>"))
        self.assertEqual(done.count(visual_report.NOTICE), 1)
        self.assertLess(done.index(visual_report.NOTICE), done.index("Content-Security-Policy"))

    def test_the_policy_allows_no_inline_script_and_no_network(self) -> None:
        policy = visual_report.policy_tag(self.script)
        self.assertNotIn("unsafe-inline'; style", policy.split("script-src")[1].split(";")[0])
        self.assertNotRegex(policy, r"https?:|\*")
        self.assertIn("default-src 'none'", policy)

    def test_finalizing_twice_changes_nothing(self) -> None:
        once = self.finalize(page())
        self.assertEqual(self.finalize(once), once)

    def test_a_stale_runtime_is_replaced(self) -> None:
        stale = self.finalize(page()).replace(self.script, "\nconsole.log('old');\n")
        self.assertEqual(self.finalize(stale), self.finalize(page()))

    def test_text_that_only_looks_like_a_placeholder_is_left_alone(self) -> None:
        decoy = "<!-- <style data-trackbed-runtime></style> --><pre>&lt;script data-trackbed-runtime&gt;</pre>"
        done = self.finalize(page(body=ENTRY + decoy))
        self.assertIn(decoy, done)
        self.assertEqual(done.count(self.script), 1)
        self.assertEqual(done.count(self.css), 1)

    def test_runtime_assets_cannot_close_their_own_element(self) -> None:
        self.assertNotIn("</style", self.css.lower())
        self.assertNotIn("</script", self.script.lower())
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp)
            (assets / "report-runtime.css").write_text("a{}", encoding="utf-8")
            (assets / "report-runtime.js").write_text("const x = '</script>';", encoding="utf-8")
            with self.assertRaises(ValueError):
                visual_report.load_runtime(assets)


class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name).resolve()

    def run_main(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = int(visual_report.main(list(args)))
        return code, out.getvalue(), err.getvalue()

    def test_a_valid_page_is_finalized_in_place(self) -> None:
        target = self.dir / "QA_REPORT.html"
        target.write_text(page(), encoding="utf-8")
        target.chmod(0o640)
        code, out, err = self.run_main(str(target))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)
        self.assertEqual(out, f"Visual report ready: {target} (1 entries, 1 sections)\n")
        self.assertIn("Content-Security-Policy", target.read_text(encoding="utf-8"))
        self.assertEqual([path.name for path in self.dir.iterdir()], ["QA_REPORT.html"])
        self.assertEqual(self.run_main("--check", str(target))[0], 0)

    def test_check_reports_an_unfinalized_page_without_writing(self) -> None:
        target = self.dir / "QA_REPORT.html"
        target.write_text(page(), encoding="utf-8")
        code, _, err = self.run_main("--check", str(target))
        self.assertEqual(code, 1)
        self.assertIn("is valid but not finalized; rerun without --check", err)
        self.assertEqual(target.read_text(encoding="utf-8"), page())

    def test_a_page_that_breaks_the_contract_is_left_untouched(self) -> None:
        target = self.dir / "QA_REPORT.html"
        broken = page(body=ENTRY + "<script>alert(1)</script>")
        target.write_text(broken, encoding="utf-8")
        code, out, err = self.run_main(str(target))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("visual-report: line 16: only <script data-trackbed-runtime></script> may appear", err)
        self.assertIn("1 problem(s)", err)
        self.assertIn("the page was not changed", err)
        self.assertEqual(target.read_text(encoding="utf-8"), broken)

    def test_only_a_regular_html_file_is_accepted(self) -> None:
        markdown = self.dir / "QA_REPORT.md"
        markdown.write_text("# QA", encoding="utf-8")
        self.assertEqual(self.run_main(str(markdown))[0], 2)
        self.assertEqual(self.run_main(str(self.dir / "missing.html"))[0], 2)
        target = self.dir / "QA_REPORT.html"
        target.write_text(page(), encoding="utf-8")
        link = self.dir / "link.html"
        link.symlink_to(target)
        code, _, err = self.run_main(str(link))
        self.assertEqual(code, 2)
        self.assertIn("must be a regular file", err)
        self.assertEqual(target.read_text(encoding="utf-8"), page())


if __name__ == "__main__":
    unittest.main()
