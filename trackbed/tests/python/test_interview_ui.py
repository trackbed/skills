"""Behavioral tests for the trackbed:discovery:interview page helper (`--ui`).

The helper reads a round the model wrote, builds its page, serves it on the loopback address, and
checks the answers that come back. The answer cases come from a fixture shared with
tests/node/interview-ui-runtime.test.js, so the page's runtime builds exactly the payloads the
helper accepts.
"""

from __future__ import annotations

import base64
import contextlib
import copy
import hashlib
import importlib
import io
import json
import re
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from unittest import mock

from tests.test_helper.script_loader import load_script

PLUGIN = Path(__file__).resolve().parents[2]
SKILL_DIR = PLUGIN / "skills" / "discovery:interview"
SCRIPTS = SKILL_DIR / "scripts"
ROUND_FIXTURE = PLUGIN / "tests" / "fixtures" / "interview-ui-round.json"
CASES = json.loads((PLUGIN / "tests" / "fixtures" / "interview-ui-answers-cases.json").read_text(encoding="utf-8"))
# The command imports its sibling modules, which a script-form run finds on sys.path[0].
sys.path.insert(0, str(SCRIPTS))
helper = load_script("interview_ui", SCRIPTS / "interview-ui.py")
rounds = importlib.import_module("interview_ui_round")
answers_module = importlib.import_module("interview_ui_answers")
figures = importlib.import_module("interview_ui_figures")
page = importlib.import_module("interview_ui_page")
server = importlib.import_module("interview_ui_server")

SCRIPT_RE = re.compile(r"<script>(.*?)</script>", re.S)
POLICY_RE = re.compile(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">')
CATALOG_RE = re.compile(r'<script type="application/json" id="trackbed-interview-round">(.*?)</script>', re.S)
FORM_RE = re.compile(r"<form data-form novalidate>(.*?)</form>", re.S)
CONFIG_RE = re.compile(r'<script type="application/json" id="trackbed-interview-config">(.*?)</script>', re.S)


def fixture_round() -> dict[str, Any]:
    raw = json.loads(ROUND_FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def minimal_round(**question: Any) -> dict[str, Any]:
    base = {"id": "q", "kind": "text", "title": "A question?", "why": "Because it decides the plan."}
    return {
        "format": rounds.ROUND_FORMAT,
        "schemaVersion": 1,
        "session": {"id": "demo", "title": "Demo"},
        "number": 1,
        "title": "First round",
        "synthesis": ["The starting hypothesis."],
        "questions": [{**base, **question}],
    }


def problems_of(raw: Any) -> list[str]:
    round_, problems = rounds.read_round(raw)
    assert round_ is None, "the round was accepted"
    return list(problems)


def run(*argv: str, stdin: str = "") -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), mock.patch("sys.stdin", io.StringIO(stdin)):
        code = helper.main(list(argv))
    return int(code), out.getvalue(), err.getvalue()


def request(
    url: str, *, headers: dict[str, str] | None = None, body: bytes | None = None
) -> tuple[int, dict[str, str], bytes]:
    call = urllib.request.Request(url, data=body, headers=headers or {}, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(call, timeout=5) as response:
            return int(response.status), dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as error:
        with error:
            return int(error.code), dict(error.headers.items()), error.read()


class RoundReading(unittest.TestCase):
    def test_the_fixture_round_reads_clean_and_keeps_every_kind(self) -> None:
        round_, problems = rounds.read_round(fixture_round())
        self.assertEqual(problems, [])
        assert round_ is not None
        kinds = [question["kind"] for question in round_["questions"]]
        self.assertEqual(kinds, ["choice", "scale", "rank", "matrix", "allocate", "confirm", "text"])
        self.assertEqual(sorted(kinds), sorted(rounds.KINDS))
        self.assertRegex(round_["fingerprint"], r"^[0-9a-f]{16}$")
        # A recommendation is stored as the answer it recommends, in the answer's own shape.
        picks = {question["id"]: (question["recommendation"] or {}).get("pick") for question in round_["questions"]}
        self.assertEqual(picks["code-step"], ["second-screen"])
        self.assertEqual(picks["friction"], 3)
        self.assertIsNone(picks["edge-order"])
        self.assertEqual(picks["scope"]["sms"], "never")
        self.assertEqual(sum(picks["effort"].values()), 100)

    def test_synthesis_requires_at_least_one_paragraph(self) -> None:
        raw = minimal_round()
        del raw["synthesis"]
        for changes in ({}, {"synthesis": None}, {"synthesis": []}):
            with self.subTest(changes=changes):
                self.assertIn("synthesis: provide at least one paragraph", problems_of({**raw, **changes}))

    def test_the_fingerprint_follows_the_content(self) -> None:
        first, _ = rounds.read_round(fixture_round())
        changed = fixture_round()
        changed["questions"][0]["title"] = "Where is the code typed?"
        second, _ = rounds.read_round(changed)
        again, _ = rounds.read_round(fixture_round())
        assert first is not None and second is not None and again is not None
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(first["fingerprint"], again["fingerprint"])

    def test_a_round_that_is_not_one_is_refused_with_the_reason(self) -> None:
        self.assertEqual(problems_of([1, 2]), ["round: must be a JSON object"])
        wrong_format = minimal_round()
        wrong_format["format"] = "trackbed-decisions"
        self.assertIn(
            'round: must have "format": "trackbed-interview-round" and "schemaVersion": 1', problems_of(wrong_format)
        )
        typo = minimal_round()
        typo["sinthesis"] = "x"
        self.assertTrue(any("unknown field `sinthesis`" in problem for problem in problems_of(typo)))
        no_session = minimal_round()
        no_session["session"] = "demo"
        self.assertTrue(any(problem.startswith("session: must be an object") for problem in problems_of(no_session)))

    def test_every_question_needs_an_id_a_title_and_why_it_matters(self) -> None:
        found = problems_of(minimal_round(id="Not An Id", title="", why=None))
        self.assertIn("questions[0].id: must be a short id of lowercase letters, digits, and hyphens", found)
        self.assertIn("questions[0].title: must not be empty", found)
        self.assertIn("questions[0].why: must be text", found)
        twice = minimal_round()
        twice["questions"].append(copy.deepcopy(twice["questions"][0]))
        self.assertIn("questions[1].id: `q` is used twice", problems_of(twice))
        none = minimal_round()
        none["questions"] = []
        self.assertIn("questions: has 0 entries; it takes 1 to 8", problems_of(none))
        self.assertIn(
            "questions[0].kind: must be one of " + ", ".join(rounds.KINDS), problems_of(minimal_round(kind="slider"))
        )

    def test_a_question_with_a_control_says_what_the_interviewer_recommends(self) -> None:
        options = [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]
        missing = problems_of(minimal_round(kind="choice", options=options))
        self.assertTrue(any("recommendation: is required" in problem for problem in missing))
        unknown = minimal_round(kind="choice", options=options, recommendation={"pick": "c", "reason": "Because."})
        self.assertTrue(any("recommendation.pick.selected" in problem for problem in problems_of(unknown)))
        neutral, problems = rounds.read_round(
            minimal_round(kind="choice", options=options, recommendation={"pick": None, "reason": "Your call."})
        )
        self.assertEqual(problems, [])
        assert neutral is not None
        self.assertEqual(neutral["questions"][0]["recommendation"], {"pick": None, "reason": "Your call."})
        on_text = minimal_round(recommendation={"pick": None, "reason": "x"})
        self.assertTrue(any("takes no recommendation" in problem for problem in problems_of(on_text)))

    def test_rank_recommendation_ids_must_be_strings(self) -> None:
        raw = minimal_round(
            kind="rank",
            items=[{"id": "1", "label": "One"}, {"id": "2", "label": "Two"}],
            recommendation={"pick": [1, 2], "reason": "Why this order."},
        )
        self.assertIn(
            "questions[0].recommendation.pick.order: must list every item of this question once", problems_of(raw)
        )

    def test_allocation_recommendation_amounts_must_match_the_step(self) -> None:
        raw = minimal_round(
            kind="allocate",
            items=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            recommendation={"pick": {"a": 41, "b": 59}, "reason": "Why this split."},
        )
        self.assertIn("questions[0].recommendation.pick.amounts: must be multiples of 5", problems_of(raw))

    def test_each_kind_checks_its_own_shape(self) -> None:
        neutral = {"pick": None, "reason": "Your call."}
        cases: list[tuple[dict[str, Any], str]] = [
            ({"kind": "choice", "options": [{"id": "a", "label": "A"}], "recommendation": neutral}, "it takes 2 to 6"),
            (
                {
                    "kind": "choice",
                    "options": [{"id": "a", "label": "A"}, {"id": "a", "label": "B"}],
                    "recommendation": neutral,
                },
                "`a` is used twice",
            ),
            ({"kind": "rank", "items": "x", "recommendation": neutral}, "must be a list of objects"),
            ({"kind": "scale", "low": "Low", "high": "", "recommendation": neutral}, "high: must not be empty"),
            (
                {"kind": "scale", "low": "Low", "high": "High", "steps": 9, "recommendation": neutral},
                "steps: must be a whole number from 3 to 7",
            ),
            (
                {
                    "kind": "allocate",
                    "items": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                    "total": 10,
                    "step": 3,
                    "recommendation": neutral,
                },
                "step: must divide the total of 10 evenly",
            ),
            (
                {
                    "kind": "matrix",
                    "rows": [{"id": "r", "label": "R"}],
                    "columns": [{"id": "c", "label": "C"}],
                    "recommendation": neutral,
                },
                "columns: has 1 entries; it takes 2 to 5",
            ),
            ({"kind": "confirm"}, "statement: must be text"),
            ({"kind": "text", "long": "yes"}, "long: must be true or false"),
            ({"kind": "text", "options": []}, "unknown field `options`"),
        ]
        for question, expected in cases:
            with self.subTest(expected=expected):
                found = problems_of(minimal_round(**question))
                self.assertTrue(any(expected in problem for problem in found), found)

    def test_figures_are_checked_and_a_sketch_must_be_inert(self) -> None:
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'
        accepted, problems = rounds.read_round(
            minimal_round(
                figure={"kind": "sketch", "svg": svg, "alt": "A square", "caption": "Made for this question."}
            )
        )
        self.assertEqual(problems, [])
        assert accepted is not None
        for hostile in (
            svg.replace("<rect", "<script>alert(1)</script><rect"),
            svg.replace("<rect", '<rect onclick="x()"'),
            svg.replace("<rect", '<image href="https://example.com/x.png"/><rect'),
            svg.replace("<rect", '<a href="https://example.com"><rect'),
            svg.replace("<rect", "<style>@import url(x.css)</style><rect"),
            svg.replace("<rect", '<rect fill="url(&quot;https://example.com/paint&quot;)"'),
            svg.replace("<rect", "<foreignObject><p>hi</p></foreignObject><rect"),
        ):
            with self.subTest(svg=hostile[60:110]):
                found = problems_of(minimal_round(figure={"kind": "sketch", "svg": hostile, "alt": "A square"}))
                self.assertTrue(any("must not hold script" in problem for problem in found), found)
        for reference in ("url(#m)", "url( '#m' )", "url(&quot;#m&quot;)"):
            local = svg.replace(
                "<rect", f'<defs><marker id="m"/></defs><path marker-end="{reference}"/><use href="#m"/><rect'
            )
            with self.subTest(reference=reference):
                checked, problems = rounds.read_round(
                    minimal_round(figure={"kind": "sketch", "svg": local, "alt": "x"})
                )
                self.assertEqual(problems, [])
                self.assertIsNotNone(checked)
        cases: list[tuple[dict[str, Any], str]] = [
            ({"kind": "sketch", "svg": "<div>no</div>", "alt": "x"}, "one complete <svg> element with a viewBox"),
            (
                {"kind": "sketch", "svg": svg.replace("/></svg>", "></svg>"), "alt": "x"},
                "one complete <svg> element with a viewBox",
            ),
            (
                {"kind": "sketch", "svg": svg.replace(' xmlns="http://www.w3.org/2000/svg"', ""), "alt": "x"},
                "SVG namespace",
            ),
            ({"kind": "sketch", "svg": svg}, "figure.alt: must be text"),
            ({"kind": "steps", "steps": ["only one"]}, "must be a list of 2 to 8 steps"),
            ({"kind": "bars", "bars": [{"label": "a", "value": -1}, {"label": "b", "value": 2}]}, "not negative"),
            ({"kind": "code", "code": ""}, "must be 1 to 4000 characters of text"),
            ({"kind": "table", "columns": ["a", "b"], "rows": [["only one"]]}, "must have one cell per column"),
            ({"kind": "unknown"}, "figure.kind: must be one of"),
            ("a picture", "figure: must be an object"),
        ]
        for figure, expected in cases:
            with self.subTest(expected=expected):
                found = problems_of(minimal_round(figure=figure))
                self.assertTrue(any(expected in problem for problem in found), found)

    def test_evidence_bars_require_finite_values_and_scale_before_multiplying(self) -> None:
        def with_values(*values: float) -> dict[str, Any]:
            return minimal_round(
                figure={
                    "kind": "bars",
                    "bars": [{"label": str(index), "value": value} for index, value in enumerate(values)],
                }
            )

        for value in (float("nan"), float("inf"), 10**400):
            with self.subTest(value=value):
                self.assertIn(
                    "questions[0].figure.bars[0].value: must be a finite number that is not negative",
                    problems_of(with_values(value, 1)),
                )
        checked, problems = rounds.read_round(with_values(1e308, 5e307, 0))
        self.assertEqual(problems, [])
        assert checked is not None
        html = figures.render_figure(checked["questions"][0]["figure"])
        self.assertEqual(re.findall(r"width:([\d.]+)%", html), ["100", "50", "0"])

    def test_evidence_chart_checks_series_alignment_and_finite_values(self) -> None:
        chart = {
            "kind": "chart",
            "title": "Cost",
            "source": "Scenario",
            "unit": "USD",
            "labels": ["Jan", "Feb"],
            "series": [{"label": "A", "values": [-2, 0]}],
        }
        for values in ([], [1], [True, 2], [float("nan"), 1], [1, float("inf")]):
            with self.subTest(values=values):
                bad = {**chart, "series": [{"label": "A", "values": values}]}
                self.assertTrue(any("series[0].values" in p for p in problems_of(minimal_round(figures=[bad]))))
        self.assertTrue(
            any("either figure or figures" in p for p in problems_of(minimal_round(figure=chart, figures=[chart])))
        )
        for values in ([-2, 0], [-3, -3], [0, 0]):
            chart["series"][0]["values"] = values
            checked, problems = rounds.read_round(minimal_round(figures=[chart]))
            self.assertEqual(problems, [])
            assert checked is not None
            body = helper.build_page(checked, page.OFFLINE)[0]
            self.assertIn("<polyline", body)
            self.assertIn("View chart data", body)
            self.assertIn(f"<td>{values[0]}</td>", body)

    def test_screenshot_requires_a_local_raster_file_and_valid_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            capture = SKILL_DIR / "assets" / "ui-verification-prototype.png"
            (folder / "linked.png").symlink_to(capture)
            (folder / "document.png").write_text("<html>wrong format</html>")
            screen = {"kind": "screenshot", "title": "Login", "source": "Local prototype", "alt": "Login form"}
            for name in (
                "missing.png",
                "../outside.png",
                str(capture),
                "https://example.com/a.png",
                "linked.png",
                "document.png",
            ):
                with self.subTest(name=name):
                    checked, problems = rounds.read_round(minimal_round(figure={**screen, "file": name}), folder)
                    self.assertIsNone(checked)
                    self.assertTrue(any(".figure.file" in p for p in problems))
            (folder / "capture.png").write_bytes(capture.read_bytes())
            screen.update(file="capture.png", callouts=[{"x": 101, "y": 20, "text": "Help"}])
            checked, problems = rounds.read_round(minimal_round(figure=screen), folder)
            self.assertIsNone(checked)
            self.assertTrue(any("callouts[0].x" in p for p in problems))

    def test_progress_is_a_meter_or_a_tree_never_both_in_one_entry(self) -> None:
        tree = minimal_round()
        tree["progress"] = {
            "label": "Decision tree",
            "entries": [
                {"label": "Root", "state": "resolved", "note": "Decided"},
                {"label": "Branch", "state": "active", "depth": 1},
            ],
        }
        round_, problems = rounds.read_round(tree)
        self.assertEqual(problems, [])
        assert round_ is not None
        self.assertEqual([entry["state"] for entry in round_["progress"]["entries"]], ["resolved", "active"])
        for entry, expected in (
            ({"label": "x", "value": 50, "state": "open"}, "takes either `value`"),
            ({"label": "x"}, "takes either `value`"),
            ({"label": "x", "value": 140}, "must be a whole number from 0 to 100"),
            ({"label": "x", "state": "done"}, "state: must be one of resolved, active, open"),
        ):
            with self.subTest(expected=expected):
                broken = minimal_round()
                broken["progress"] = {"entries": [entry]}
                self.assertTrue(any(expected in problem for problem in problems_of(broken)))
        not_an_object = minimal_round()
        not_an_object["progress"] = "80%"
        self.assertIn("progress: must be an object", problems_of(not_an_object))


class Answers(unittest.TestCase):
    def setUp(self) -> None:
        round_, problems = rounds.read_round(fixture_round())
        self.assertEqual(problems, [])
        assert round_ is not None
        self.round = round_

    def test_the_runtime_catalog_in_the_fixture_is_the_one_the_builder_writes(self) -> None:
        self.assertEqual(page.catalog_of(self.round), CASES["catalog"])

    def test_single_choice_rejects_a_selected_option_plus_a_write_in(self) -> None:
        payload = copy.deepcopy(CASES["cases"][0]["payload"])
        payload["answers"][0]["value"]["other"] = "Another option"
        checked, problems = answers_module.read_answers(self.round, payload)
        self.assertIsNone(checked)
        self.assertIn("a single choice takes either a selected option or a write-in", problems[0])

    def test_every_payload_the_runtime_builds_is_accepted(self) -> None:
        for case in CASES["cases"]:
            with self.subTest(case=case["name"]):
                answers, problems = answers_module.read_answers(self.round, case["payload"])
                self.assertEqual(problems, [])
                assert answers is not None
                self.assertEqual(
                    [(entry["id"], entry["status"]) for entry in answers["answers"]],
                    [(entry["id"], entry["status"]) for entry in case["payload"]["answers"]],
                )
                # Only a complete answer carries a value.
                for entry in answers["answers"]:
                    self.assertEqual(entry["value"] is not None, entry["status"] == "answered")

    def test_answers_that_do_not_fit_the_round_are_refused(self) -> None:
        for case in CASES["refused"]:
            with self.subTest(case=case["name"]):
                payload = copy.deepcopy(CASES["cases"][0]["payload"])
                target = payload
                for key in case["path"][:-1]:
                    target = target[key]
                target[case["path"][-1]] = case["value"]
                answers, problems = answers_module.read_answers(self.round, payload)
                self.assertIsNone(answers)
                self.assertTrue(any(case["problem"] in problem for problem in problems), problems)

    def test_answers_must_cover_the_round_exactly(self) -> None:
        payload = copy.deepcopy(CASES["cases"][0]["payload"])
        payload["answers"].pop()
        self.assertEqual(
            answers_module.read_answers(self.round, payload)[1],
            ["answers.answers: must hold exactly one entry for every question of the round"],
        )
        payload = copy.deepcopy(CASES["cases"][0]["payload"])
        payload["answers"] = "all good"
        self.assertEqual(
            answers_module.read_answers(self.round, payload)[1], ["answers.answers: must be a list of objects"]
        )
        self.assertEqual(answers_module.read_answers(self.round, "yes")[1], ["answers: must be a JSON object"])

    def test_pasted_answer_ids_must_be_strings(self) -> None:
        round_, problems = rounds.read_round(minimal_round(id="1"))
        self.assertEqual(problems, [])
        assert round_ is not None
        payload = {
            **CASES["cases"][0]["payload"],
            "session": round_["session"]["id"],
            "round": round_["number"],
            "fingerprint": round_["fingerprint"],
        }
        for invalid in (1, [], {}):
            with self.subTest(invalid=invalid):
                payload["answers"] = [{"id": invalid, "status": "open"}]
                self.assertEqual(
                    answers_module.read_answers(round_, payload),
                    (None, ["answers.answers: each entry must have a string id"]),
                )

    def test_answers_are_described_in_the_words_the_person_saw(self) -> None:
        answers, _ = answers_module.read_answers(self.round, CASES["cases"][0]["payload"])
        assert answers is not None
        described = answers_module.describe_answers(self.round, answers)
        by_id = {entry["id"]: entry for entry in described["answers"]}
        self.assertEqual(described["counts"], {"answered": 7, "unsure": 0, "open": 0})
        self.assertEqual(described["next"], "continue")
        self.assertEqual(described["note"], "Legal wants a say on SMS.")
        self.assertEqual(by_id["code-step"]["answer"], "On its own screen")
        self.assertIs(by_id["code-step"]["matchesRecommendation"], True)
        self.assertEqual(by_id["friction"]["answer"], "4 of 5 (1 = Every sign-in, 5 = Once per device, then never)")
        self.assertIs(by_id["friction"]["matchesRecommendation"], False)
        self.assertTrue(by_id["edge-order"]["answer"].startswith("1. The person lost access to the inbox > 2. "))
        # No pick was recommended, so there is nothing to match.
        self.assertNotIn("matchesRecommendation", by_id["edge-order"])
        self.assertIn("SMS as a second channel: Never", by_id["scope"]["answer"])
        self.assertTrue(by_id["effort"]["answer"].startswith("The sign-in flow itself: 40 points; "))
        self.assertEqual(by_id["session-column"]["answer"], "corrected: The mobile API writes to it already.")
        self.assertEqual(by_id["worry"]["answer"], "That recovery becomes the easy way in.")

    def test_an_own_answer_never_counts_as_taking_the_recommendation(self) -> None:
        answers, _ = answers_module.read_answers(self.round, CASES["cases"][3]["payload"])
        assert answers is not None
        first = answers_module.describe_answers(self.round, answers)["answers"][0]
        self.assertEqual(first["answer"], "their own answer: A magic link instead of a code")
        self.assertIs(first["matchesRecommendation"], False)
        unsure, _ = answers_module.read_answers(self.round, CASES["cases"][2]["payload"])
        assert unsure is not None
        described = answers_module.describe_answers(self.round, unsure)
        self.assertEqual(described["next"], "wrap-up")
        self.assertEqual(described["counts"], {"answered": 6, "unsure": 1, "open": 0})
        self.assertEqual(described["answers"][1]["note"], "Depends on what legal says.")
        self.assertIsNone(described["answers"][1]["answer"])


class Page(unittest.TestCase):
    def setUp(self) -> None:
        round_, _ = rounds.read_round(fixture_round())
        assert round_ is not None
        self.round = round_

    def test_rendered_controls_have_the_attributes_the_runtime_selects(self) -> None:
        class Attributes(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.names: set[str] = set()

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                self.names.update(name for name, _ in attrs)

        runtime = (helper.ASSETS / "interview-ui.js").read_text(encoding="utf-8")
        selectors = set(re.findall(r"\[(data-[a-z-]+)\]", runtime))
        self.assertIn("data-send", selectors)
        for mode in (page.LIVE, page.OFFLINE):
            with self.subTest(mode=mode):
                attributes = Attributes()
                attributes.feed(helper.build_page(self.round, mode)[0])
                required = selectors if mode == page.LIVE else selectors - {"data-copy"}
                self.assertEqual(required - attributes.names, set())

    def test_the_page_runs_only_the_runtime_and_reaches_only_its_helper(self) -> None:
        live, policy = helper.build_page(self.round, page.LIVE, "k" * 43, 12345)
        offline, offline_policy = helper.build_page(self.round, page.OFFLINE)
        for html, expected in ((live, policy), (offline, offline_policy)):
            scripts = SCRIPT_RE.findall(html)
            self.assertEqual(len(scripts), 1)
            digest = base64.b64encode(hashlib.sha256(scripts[0].encode("utf-8")).digest()).decode("ascii")
            found = POLICY_RE.search(html)
            assert found is not None
            self.assertEqual(found.group(1), expected)
            self.assertIn(f"script-src 'sha256-{digest}'", expected)
            self.assertIn("default-src 'none'", expected)
            self.assertNotIn("http://", html.replace("http://www.w3.org/2000/svg", ""))
            self.assertNotIn("https://", html)
        self.assertIn("connect-src 'self'", policy)
        self.assertNotIn("connect-src", offline_policy)
        self.assertEqual(json.loads(CONFIG_RE.findall(live)[0]), {"mode": "live", "key": "k" * 43, "expiresAt": 12345})
        self.assertEqual(json.loads(CONFIG_RE.findall(offline)[0]), {"mode": "offline", "key": "", "expiresAt": 0})
        self.assertIn(">Send answers</button>", live)
        self.assertIn(">Copy answers</button>", offline)
        self.assertIn("This page is not connected to the agent.", offline)

    def test_the_page_holds_every_question_with_its_control_and_selects_nothing(self) -> None:
        html, _ = helper.build_page(self.round, page.OFFLINE)
        self.assertEqual(json.loads(CATALOG_RE.findall(html)[0]), page.catalog_of(self.round))
        for question in self.round["questions"]:
            self.assertIn(f'data-question="{question["id"]}" data-kind="{question["kind"]}"', html)
        found = FORM_RE.search(html)
        assert found is not None
        form = found.group(1)
        self.assertEqual(form.count("<strong>Why this matters.</strong>"), 7)
        self.assertEqual(form.count('<aside class="ti-recommendation">'), 5)
        self.assertEqual(form.count("data-unsure"), 7)
        # The page recommends and never chooses for the person.
        self.assertNotIn(" checked", form)
        self.assertNotIn(" selected", form)
        self.assertIn('<span class="ti-badge">Recommended</span>', html)
        self.assertIn("<strong>B (On its own screen).</strong>", html)
        self.assertIn("<strong>No strong preference.</strong>", html)
        self.assertRegex(
            form, r'class="ti-stop ti-stop-recommended"><input type="radio" name="(control-\d+)" id="\1-3"'
        )
        self.assertIn('value="__other" data-other', html)
        self.assertIn('data-move="-1" aria-label="Move The email arrives late up"', html)
        self.assertIn('min="0" max="100" step="5" value="0"', html)
        self.assertIn('aria-label="Backup codes: Later"', html)
        self.assertIn("<footer>From <code>db/schema.sql</code> line 212</footer>", html)
        self.assertIn('<li class="ti-meter" data-met="true"><span class="ti-entry-label">User and why now</span>', html)
        self.assertIn("The interview aims for 80% on each.", html)

    def test_form_control_ids_and_radio_groups_do_not_collide(self) -> None:
        neutral = {"pick": None, "reason": "Your call."}
        raw = minimal_round(
            id="scope-a",
            kind="choice",
            options=[{"id": "other", "label": "Other proposal"}, {"id": "unsure", "label": "Defer"}],
            recommendation=neutral,
        )
        raw["questions"].append(
            {
                **raw["questions"][0],
                "id": "scope",
                "kind": "matrix",
                "rows": [{"id": "a", "label": "A"}, {"id": "a-b", "label": "A B"}],
                "columns": [{"id": "b-c", "label": "B C"}, {"id": "c", "label": "C"}],
            }
        )
        del raw["questions"][1]["options"]
        round_, problems = rounds.read_round(raw)
        self.assertEqual(problems, [])
        assert round_ is not None
        html, _ = helper.build_page(round_, page.OFFLINE)
        ids = re.findall(r'\sid="([^"]+)"', html)
        self.assertEqual(len(ids), len(set(ids)))
        groups = re.findall(r'<input type="radio" name="([^"]+)"', html)
        self.assertEqual(sorted(groups.count(group) for group in set(groups)), [2, 2, 3])

    def test_the_first_round_shows_the_starting_hypothesis_and_later_rounds_the_synthesis(self) -> None:
        later, _ = helper.build_page(self.round, page.OFFLINE)
        self.assertIn('<section class="ti-synthesis"><h2>What I took from your answers so far</h2>', later)
        raw = minimal_round()
        raw["synthesis"] = "You want old sessions gone without losing the plan."
        first_round, problems = rounds.read_round(raw)
        self.assertEqual(problems, [])
        assert first_round is not None
        first, _ = helper.build_page(first_round, page.OFFLINE)
        self.assertIn(
            '<section class="ti-synthesis"><h2>Where I am starting from</h2>'
            "<p>You want old sessions gone without losing the plan.</p></section>",
            first,
        )

    def test_text_from_the_round_reaches_the_page_escaped(self) -> None:
        raw = minimal_round(
            kind="choice",
            title='Is <script>alert("x")</script> & **bold** `code` safe?',
            options=[{"id": "a", "label": "<img src=x onerror=1>"}, {"id": "b", "label": "B", "gives": "</script>"}],
            recommendation={"pick": None, "reason": "</style><b>no</b>"},
        )
        raw["session"]["title"] = '"><svg onload=1>'
        round_, problems = rounds.read_round(raw)
        self.assertEqual(problems, [])
        assert round_ is not None
        html, _ = helper.build_page(round_, page.OFFLINE)
        self.assertEqual(len(SCRIPT_RE.findall(html)), 1)
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("<svg onload", html)
        self.assertIn(
            "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; <strong>bold</strong> <code>code</code>", html
        )
        # The data block cannot be closed from inside either.
        self.assertNotIn("</script>", CATALOG_RE.findall(html)[0])

    def test_figures_render_and_a_sketch_is_only_ever_an_image(self) -> None:
        html, _ = helper.build_page(self.round, page.OFFLINE)
        self.assertEqual(html.count('<img class="ti-sketch" src="data:image/svg+xml;base64,'), 2)
        self.assertNotIn("<svg", html)
        self.assertIn('<figure class="ti-figure ti-figure-bars">', html)
        self.assertIn("<span>20 codes a month</span>", html)
        self.assertIn("<span>0.2 codes a month</span>", html)
        self.assertIn('<pre class="ti-code" data-language="sql" tabindex="0"><code>CREATE TABLE sessions (', html)
        steps = figures.render_figure({"kind": "steps", "caption": "", "steps": ["Ask", "Answer"]})
        self.assertEqual(
            steps,
            '<figure class="ti-figure ti-figure-steps"><ol class="ti-steps"><li>Ask</li><li>Answer</li></ol></figure>',
        )
        table = figures.render_figure(
            {"kind": "table", "caption": "Compared", "columns": ["Option", "Cost"], "rows": [["A", "Low"]]}
        )
        self.assertIn('<th scope="col">Option</th><th scope="col">Cost</th>', table)
        self.assertIn('<tr><th scope="row">A</th><td>Low</td></tr>', table)
        self.assertIn("<figcaption>Compared</figcaption>", table)
        self.assertEqual(figures.render_figure(None), "")


class Serving(unittest.TestCase):
    """The loopback listener, driven the way the page drives it."""

    KEY = "k" * 43

    def setUp(self) -> None:
        round_, _ = rounds.read_round(fixture_round())
        assert round_ is not None
        self.round = round_
        self.payload = json.dumps(CASES["cases"][0]["payload"]).encode("utf-8")
        self.listener = server.RoundServer(
            self.KEY,
            "<p>the page</p>",
            "default-src 'none'",
            lambda raw: answers_module.read_answers(round_, raw),
            mock.Mock(),
        )
        self.thread = threading.Thread(target=self.listener.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.listener.port}"
        self.keyed = {server.KEY_HEADER: self.KEY}
        self.addCleanup(self.stop)

    def stop(self) -> None:
        self.listener.shutdown()
        self.listener.server_close()
        self.thread.join(5)

    def test_the_page_is_served_only_with_the_key(self) -> None:
        status, headers, body = request(f"{self.base}/?k={self.KEY}")
        self.assertEqual((status, body), (200, b"<p>the page</p>"))
        self.assertEqual(headers["Content-Security-Policy"], "default-src 'none'; frame-ancestors 'none'")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(request(f"{self.base}/")[0], 403)
        self.assertEqual(request(f"{self.base}/?k=wrong")[0], 403)
        self.assertEqual(request(f"{self.base}/elsewhere")[0], 404)
        self.assertEqual(self.listener.url, f"{self.base}/?k={self.KEY}")

    def test_no_state_endpoint_remains_for_between_round_polling(self) -> None:
        self.assertEqual(request(f"{self.base}/state", headers=self.keyed)[0], 404)

    def test_a_request_under_another_host_name_is_refused(self) -> None:
        for headers in ({"Host": "evil.example"}, {"Host": f"evil.example:{self.listener.port}"}):
            self.assertEqual(request(f"{self.base}/?k={self.KEY}", headers=headers)[0], 403)
        post = {**self.keyed, "Content-Type": "application/json", "Host": "evil.example"}
        self.assertEqual(request(f"{self.base}/answers", headers=post, body=self.payload)[0], 403)
        local = {"Host": f"localhost:{self.listener.port}"}
        self.assertEqual(request(f"{self.base}/?k={self.KEY}", headers=local)[0], 200)

    def test_answers_are_accepted_once_and_only_from_the_page(self) -> None:
        post = {**self.keyed, "Content-Type": "application/json"}
        refusals: list[tuple[dict[str, str], bytes, int]] = [
            ({**post, "Origin": "https://evil.example"}, self.payload, 403),
            ({"Content-Type": "application/json"}, self.payload, 403),
            ({**self.keyed, "Content-Type": "text/plain"}, self.payload, 415),
            # Refused on the size it announces, before any of it is read.
            ({**post, "Content-Length": str(server.MAX_BODY_BYTES + 1)}, b"", 413),
            (post, b"", 413),
        ]
        for headers, body, expected in refusals:
            with self.subTest(expected=expected):
                self.assertEqual(request(f"{self.base}/answers", headers=headers, body=body)[0], expected)
        self.assertEqual(request(f"{self.base}/elsewhere", headers=post, body=self.payload)[0], 404)
        status, _, body = request(f"{self.base}/answers", headers=post, body=b"{not json")
        self.assertEqual((status, json.loads(body)["problems"]), (422, ["answers: are not valid JSON"]))
        stale = json.loads(self.payload)
        stale["fingerprint"] = "0" * 16
        status, _, body = request(f"{self.base}/answers", headers=post, body=json.dumps(stale).encode("utf-8"))
        self.assertEqual(status, 422)
        self.assertIn("earlier version of this round", json.loads(body)["problems"][0])
        self.assertIsNone(self.listener.answers)
        self.assertFalse(self.listener.done.is_set())

        origin = {**post, "Origin": self.base}
        status, _, body = request(f"{self.base}/answers", headers=origin, body=self.payload)
        self.assertEqual((status, json.loads(body)), (200, {"ok": True}))
        self.assertTrue(self.listener.done.wait(timeout=2))
        assert self.listener.answers is not None
        self.assertEqual(self.listener.answers["answers"][0]["value"], {"selected": ["second-screen"], "other": ""})
        self.assertEqual(request(f"{self.base}/answers", headers=origin, body=self.payload)[0], 409)

    def test_concurrent_submissions_save_only_one_answer(self) -> None:
        validated = threading.Barrier(2)
        check = self.listener.check
        assert check is not None

        def check_together(raw: Any) -> Any:
            result = check(raw)
            validated.wait(timeout=3)
            return result

        self.listener.check = check_together
        self.listener.save_answers = save = mock.Mock()
        post = {**self.keyed, "Content-Type": "application/json"}

        def submit(note: str) -> int:
            payload = {**json.loads(self.payload), "note": note}
            return request(f"{self.base}/answers", headers=post, body=json.dumps(payload).encode())[0]

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(pool.map(submit, ("First tab", "Second tab")), [200, 409])
        save.assert_called_once_with(self.listener.answers)


class Command(unittest.TestCase):
    def setUp(self) -> None:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.directory = Path(holder.name)
        self.session = self.directory / "session"

    def ask(self, *extra: str) -> tuple[int, str, str, list[str]]:
        """Run `ask` to its end while a stand-in for the page answers it."""
        opened: list[str] = []

        def answer(url: str) -> bool:
            opened.append(url)
            base, key = url.split("/?k=")
            headers = {server.KEY_HEADER: key, "Content-Type": "application/json", "Origin": base}
            body = json.dumps(CASES["cases"][0]["payload"]).encode("utf-8")
            threading.Thread(
                target=request, args=(f"{base}/answers",), kwargs={"headers": headers, "body": body}
            ).start()
            return True

        with mock.patch.object(helper.webbrowser, "open_new_tab", side_effect=answer):
            code, out, err = run("ask", "--round", str(ROUND_FIXTURE), "--session-dir", str(self.session), *extra)
        return code, out, err, opened

    def test_capture_and_chart_survive_offline_export_and_pin_the_answers_to_the_evidence(self) -> None:
        example = SKILL_DIR / "assets" / "ui-round-example.json"
        raw = json.loads(example.read_text())
        evidence = raw["questions"][1]["figures"]
        # The same evidence formats work on individual options.
        raw["questions"][0]["options"][0].pop("figure")
        raw["questions"][0]["options"][0]["figures"] = evidence
        path = self.directory / "round.json"
        path.write_text(json.dumps(raw))
        name = evidence[1]["file"]
        image = self.directory / name
        image.write_bytes((example.parent / name).read_bytes())
        output = self.directory / "page.html"
        code, _, err = run("build", "--round", str(path), "--output", str(output))
        self.assertEqual(code, 0, err)
        html = output.read_text()
        self.assertIn("data:image/png;base64," + base64.b64encode(image.read_bytes()).decode(), html)
        self.assertEqual(html.count('class="ti-enlarge"'), 2)
        self.assertIn("Trust requires an explicit choice", html)
        self.assertNotIn("connect-src", POLICY_RE.search(html).group(1))
        catalog = json.loads(CATALOG_RE.findall(html)[0])
        payload = {
            "format": rounds.ANSWERS_FORMAT,
            "schemaVersion": 1,
            "round": catalog["round"],
            "session": catalog["session"],
            "fingerprint": catalog["fingerprint"],
            "answers": [{"id": q["id"], "status": "open"} for q in catalog["questions"]],
        }
        args = ("answers", "--round", str(path), "--answers", "-", "--session-dir", str(self.session))
        self.assertEqual(run(*args, stdin=json.dumps(payload))[0], 0)
        # A different capture at the same filename changes the round fingerprint.
        image.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jQ0kAAAAASUVORK5CYII="
            )
        )
        self.assertEqual(run(*args, stdin=json.dumps(payload))[0], 1)

    def test_build_reports_an_output_filesystem_error_as_exit_two(self) -> None:
        parent = self.directory / "regular-file"
        parent.touch()
        code, _, error = run("build", "--round", str(ROUND_FIXTURE), "--output", str(parent / "round.html"))
        self.assertEqual(code, 2)
        self.assertIn(str(parent), error)

    def test_ask_serves_the_round_opens_it_and_returns_the_answers(self) -> None:
        code, out, err, opened = self.ask("--wait", "20")
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["counts"], {"answered": 7, "unsure": 0, "open": 0})
        self.assertEqual(result["answers"][0]["answer"], "On its own screen")
        self.assertEqual(len(opened), 1)
        self.assertRegex(opened[0], r"^http://127\.0\.0\.1:\d+/\?k=[\w-]{43}$")
        self.assertIn(f"interview-ui: round 2 is at {opened[0]} (waiting up to 1 min for answers)", err)

        saved = json.loads(Path(result["answersFile"]).read_text(encoding="utf-8"))
        self.assertEqual(saved["format"], rounds.ANSWERS_FORMAT)
        self.assertFalse((self.session / "session.json").exists())
        key = opened[0].split("/?k=")[1]
        for name in ("round-2.html", "round-2.answers.json"):
            path = self.session / name
            self.assertEqual(path.stat().st_mode & 0o777, 0o600, name)
            self.assertNotIn(key, path.read_text(encoding="utf-8"))

    def test_ask_stops_waiting_and_says_where_the_page_is(self) -> None:
        code, out, err = run(
            "ask", "--round", str(ROUND_FIXTURE), "--session-dir", str(self.session), "--wait", "0.2", "--no-open"
        )
        self.assertEqual(code, 3)
        result = json.loads(out)
        self.assertEqual(result["status"], "waiting")
        self.assertEqual(result["offlinePage"], str(self.session / "round-2.html"))
        self.assertNotIn("url", result)
        self.assertFalse((self.session / "round-2.answers.json").exists())

    def test_ask_reports_failed_save_and_accepts_retry(self) -> None:
        answers_path = self.session / "round-2.answers.json"
        answers_path.mkdir(parents=True)

        def answer(url: str) -> bool:
            base, key = url.split("/?k=")
            headers = {server.KEY_HEADER: key, "Content-Type": "application/json"}
            payload = json.dumps(CASES["cases"][0]["payload"]).encode()
            status, _, body = request(f"{base}/answers", headers=headers, body=payload)
            self.assertEqual(status, 500)
            self.assertIn("Could not save your answers", json.loads(body)["problems"][0])
            answers_path.rmdir()
            self.assertEqual(request(f"{base}/answers", headers=headers, body=payload)[0], 200)
            self.assertTrue(answers_path.is_file())
            return True

        with mock.patch.object(helper.webbrowser, "open_new_tab", side_effect=answer):
            code, out, err = run(
                "ask", "--round", str(ROUND_FIXTURE), "--session-dir", str(self.session), "--wait", "5"
            )
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["answersFile"], str(answers_path))

    def test_ask_returns_the_offline_page_when_no_browser_opens(self) -> None:
        for outcome in (False, helper.webbrowser.Error("no browser")):
            with self.subTest(outcome=outcome):
                with mock.patch.object(helper.webbrowser, "open_new_tab", side_effect=[outcome]):
                    code, out, err = run(
                        "ask", "--round", str(ROUND_FIXTURE), "--session-dir", str(self.session), "--wait", "0.2"
                    )
                self.assertEqual((code, out), (2, ""))
                offline = self.session / "round-2.html"
                self.assertIn(f"no browser could be opened here; the round's page is at {offline}", err)
                self.assertNotIn("http://127.0.0.1", err)
                self.assertTrue(offline.is_file())

    def test_ask_returns_the_offline_page_when_it_cannot_listen(self) -> None:
        with mock.patch.object(helper, "RoundServer", side_effect=OSError("no sockets here")):
            code, out, err = run("ask", "--round", str(ROUND_FIXTURE), "--session-dir", str(self.session), "--no-open")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("cannot listen on the loopback address; the round's page is at", err)
        self.assertIn("round-2.html and works without this helper", err)

    def test_followups_and_retries_each_open_a_tab_with_an_independent_key(self) -> None:
        payload = copy.deepcopy(CASES["cases"][0]["payload"])
        keys: list[str] = []

        def submit(url: str) -> bool:
            base, key = url.split("/?k=")
            self.assertNotIn(key, keys)
            body = json.dumps(payload).encode()
            headers = {"Content-Type": "application/json"}
            for old in keys:
                self.assertEqual(request(base + "/?k=" + old)[0], 403)
                self.assertEqual(
                    request(base + "/answers", headers={**headers, server.KEY_HEADER: old}, body=body)[0], 403
                )
            self.assertEqual(request(base + "/answers", headers={**headers, server.KEY_HEADER: key}, body=body)[0], 200)
            keys.append(key)
            return True

        with mock.patch.object(helper.webbrowser, "open_new_tab", side_effect=submit) as opener:
            for number in (2, 3, 3):
                raw = fixture_round()
                raw["number"] = number
                round_, problems = rounds.read_round(raw)
                self.assertEqual(problems, [])
                assert round_ is not None
                payload.update(round=number, fingerprint=round_["fingerprint"])
                path = self.directory / f"round-{number}.json"
                path.write_text(json.dumps(raw), encoding="utf-8")
                code, out, err = run("ask", "--round", str(path), "--session-dir", str(self.session), "--wait", "5")
                self.assertEqual(code, 0, err)
                self.assertEqual(json.loads(out)["round"], number)
        self.assertEqual(opener.call_count, 3)

    def test_a_round_with_problems_is_not_shown(self) -> None:
        broken = self.directory / "round.json"
        raw = fixture_round()
        raw["questions"][0]["options"][0]["id"] = "second-screen"
        del raw["questions"][1]["why"]
        broken.write_text(json.dumps(raw), encoding="utf-8")
        for command in (
            ("ask", "--round", str(broken), "--session-dir", str(self.session), "--no-open"),
            ("build", "--round", str(broken), "--output", str(self.directory / "page.html")),
            ("answers", "--round", str(broken), "--answers", str(broken)),
        ):
            with self.subTest(command=command[0]):
                code, out, err = run(*command)
                self.assertEqual((code, out), (1, ""))
                self.assertIn("interview-ui: questions[0].options[1].id: `second-screen` is used twice", err)
                self.assertIn("interview-ui: questions[1].why: must be text", err)
                self.assertIn("nothing was shown. Fix them and rerun.", err)
        self.assertFalse(self.session.exists())

    def test_build_writes_a_page_that_needs_no_helper(self) -> None:
        output = self.directory / "pages" / "round.html"
        code, out, err = run("build", "--round", str(ROUND_FIXTURE), "--output", str(output))
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual((result["status"], result["round"], result["page"]), ("built", 2, str(output.resolve())))
        html = output.read_text(encoding="utf-8")
        self.assertEqual(result["bytes"], len(html.encode("utf-8")))
        self.assertEqual(json.loads(CONFIG_RE.findall(html)[0])["mode"], "offline")
        code, _, err = run("build", "--round", str(ROUND_FIXTURE), "--output", str(self.directory / "round.txt"))
        self.assertEqual(code, 2)
        self.assertIn("the output must be an .html file path", err)

    def test_pasted_answers_are_checked_against_their_round(self) -> None:
        payload = CASES["cases"][0]["payload"]
        pasted = "Here are my answers:\n```json\n" + json.dumps(payload, indent=2) + "\n```\n"
        code, out, err = run(
            "answers", "--round", str(ROUND_FIXTURE), "--answers", "-", "--session-dir", str(self.session), stdin=pasted
        )
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual((result["status"], result["round"]), ("answered", 2))
        self.assertTrue((self.session / "round-2.answers.json").is_file())

        stale = self.directory / "stale.json"
        stale.write_text(json.dumps({**payload, "fingerprint": "0" * 16}), encoding="utf-8")
        code, out, err = run("answers", "--round", str(ROUND_FIXTURE), "--answers", str(stale))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("were given to an earlier version of this round", err)
        self.assertIn("these answers cannot be used; ask for them again.", err)

        code, _, err = run("answers", "--round", str(ROUND_FIXTURE), "--answers", "-", stdin="no answers here")
        self.assertEqual(code, 2)
        self.assertIn("the answers is not valid JSON", err)
        code, _, err = run("answers", "--round", str(self.directory / "missing.json"), "--answers", str(stale))
        self.assertEqual(code, 2)
        self.assertIn("cannot read the round file", err)

    def test_sessions_live_under_the_home_folder_by_default_and_waits_are_bounded(self) -> None:
        with mock.patch.object(helper.Path, "home", return_value=self.directory):
            self.assertEqual(helper.session_dir(None, "demo"), self.directory / ".trackbed" / "interviews" / "demo")
        self.assertEqual(helper.session_dir(Path("/tmp/x"), "demo"), Path("/tmp/x"))
        self.assertEqual(helper.seconds("90"), 90.0)
        for value in ("0", "7201"):
            with self.assertRaises(helper.argparse.ArgumentTypeError):
                helper.seconds(value)

    def test_a_shipped_asset_that_could_close_its_element_is_refused(self) -> None:
        hostile = self.directory / "runtime.js"
        hostile.write_text("var x = '</SCRIPT>';", encoding="utf-8")
        with self.assertRaises(helper.HelperError):
            helper.read_asset(hostile, "</script")
        with self.assertRaises(helper.HelperError):
            helper.read_asset(self.directory / "missing.css", "</style")


if __name__ == "__main__":
    unittest.main()
