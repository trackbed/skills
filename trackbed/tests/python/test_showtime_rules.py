"""Behavioral tests for the showtime rules and the decision request reader.

Both modules are pure, so every test builds its facts in memory: no repository, network, or Conductor.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

if __package__:
    from .script_loader import load_script
else:
    from script_loader import load_script

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "conductor:showtime" / "scripts"
rules = load_script("showtime_rules", SCRIPTS / "showtime_rules.py")
requests = load_script("showtime_requests", SCRIPTS / "showtime_requests.py")

HEAD = "a" * 40
NOW = 1_800_000_000
Json = dict[str, Any]


def chat(state: str = "idle", agent: str = "claude", idle: int = 30, **fields: Any) -> Json:
    return {
        "id": "chat-1",
        "agent": agent,
        "state": state,
        "idle_minutes": idle,
        "last_message_at": "2026-01-01",
    } | fields


def workspace(*chats: Json, dirty: bool = False, ahead: int = 0, head: str = HEAD, **fields: Any) -> Json:
    return {"state": "ready", "git": {"head": head, "dirty": dirty, "ahead": ahead}, "chats": list(chats)} | fields


def pull_request(**fields: Any) -> Json:
    pr: Json = {
        "number": 7,
        "title": "fix: tidy the parser",
        "body": "",
        "head_oid": HEAD,
        "base": "main",
        "draft": False,
        "mergeable": "MERGEABLE",
        "checks": {"state": "passing", "failing": [], "pending": [], "optional_failing": []},
        "threads": {"ai": 0, "human": 0, "answered": 0, "unclassified": 0},
        "feedback": {"changes_requested": False, "requested_by": [], "review_required": False, "unanswered": []},
        "stale": {"stale": False, "overlap": [], "shared": [], "moved": 0},
        "risk": {"floor": "low", "signals": []},
    }
    return pr | fields


def pace(idle_minutes: int = 10, nudge: Json | None = None, now: int = NOW) -> Json:
    return {"idle_minutes": idle_minutes, "now": now, "nudge": nudge}


def stage(ws: Json, pr: Json | None = None, past: Json | None = None, **pacing: Any) -> Json:
    return rules.workspace_stage(ws, pr, past, "main", pace(**pacing))


def comment(login: str, at: str, kind: str = "User", **fields: Any) -> Json:
    return {"author": {"login": login, "__typename": kind}, "createdAt": at, "isMinimized": False} | fields


def thread(*comments: Json, resolved: bool = False, more: bool = False) -> Json:
    return {"isResolved": resolved, "comments": {"pageInfo": {"hasNextPage": more}, "nodes": list(comments)}}


class WorkspaceStageTests(unittest.TestCase):
    def test_a_workspace_that_is_not_ready_is_never_sent_a_command(self) -> None:
        failed = stage({"state": "failed", "failure_reason": "setup script exited 1", "chats": []})
        self.assertEqual((failed["stage"], failed["group"], failed["move"]), ("setup_failed", "needs_me", None))
        self.assertIn("setup script exited 1", failed["reasons"][0])
        self.assertEqual(stage({"state": "initializing", "chats": []})["stage"], "starting")
        unreadable = stage({"state": "ready", "git_error": "the folder is missing", "chats": []})
        self.assertEqual((unreadable["stage"], unreadable["move"]), ("unreadable", None))

    def test_a_running_or_waiting_chat_decides_the_stage_before_anything_else(self) -> None:
        idle_and_running = workspace(chat(), chat("running", id="chat-2"), ahead=3)
        self.assertEqual(stage(idle_and_running)["stage"], "working")
        waiting = stage(workspace(chat("waiting_for_user"), ahead=3), pull_request())
        self.assertEqual((waiting["stage"], waiting["move"], waiting["read_tail"]), ("waiting", None, False))
        self.assertEqual(stage(workspace(chat("error")))["stage"], "chat_error")

    def test_committed_work_without_a_pull_request_gets_the_create_command(self) -> None:
        for agent, message in (
            ("claude", "/trackbed:pr-create --showtime"),
            ("codex", "$trackbed:pr:create --showtime"),
        ):
            with self.subTest(agent=agent):
                result = stage(workspace(chat(agent=agent), ahead=2))
                self.assertEqual((result["stage"], result["group"]), ("work_done_no_pr", "nudge"))
                self.assertEqual(
                    result["move"], {"kind": "send", "command": "create", "session_id": "chat-1", "message": message}
                )
                self.assertTrue(result["read_tail"])
                self.assertEqual(result["nudge"], {"signature": "create", "count": 1})

    def test_uncommitted_or_absent_work_is_never_published_for_the_user(self) -> None:
        dirty = stage(workspace(chat(), dirty=True, ahead=2))
        self.assertEqual((dirty["stage"], dirty["move"]), ("uncommitted", None))
        empty = stage(workspace(chat()))
        self.assertEqual((empty["stage"], empty["group"], empty["move"]), ("empty", None, None))

    def test_a_command_waits_until_the_chat_has_been_idle_long_enough(self) -> None:
        result = stage(workspace(chat(idle=4), ahead=1))
        self.assertEqual(result["move"], {"kind": "wait", "command": "create", "minutes_left": 6})
        self.assertNotIn("nudge", result)
        self.assertEqual(stage(workspace(chat(idle=4), ahead=1), idle_minutes=0)["move"]["kind"], "send")

    def test_a_chat_that_cannot_run_the_command_is_reported(self) -> None:
        self.assertEqual(stage(workspace(ahead=1))["stage"], "no_chat")
        other = stage(workspace(chat(agent="cursor"), ahead=1))
        self.assertEqual((other["stage"], other["move"]), ("agent_unsupported", None))

    def test_the_same_problem_gets_two_commands_and_no_third(self) -> None:
        ws, later = workspace(chat(), ahead=1), NOW + 3600
        second = stage(ws, nudge={"signature": "create", "count": 1, "at": NOW}, now=later)
        self.assertEqual(second["nudge"], {"signature": "create", "count": 2})
        third = stage(ws, nudge={"signature": "create", "count": 2, "at": NOW}, now=later)
        self.assertEqual((third["stage"], third["group"], third["move"]), ("nudge_limit", "needs_me", None))
        self.assertIn("was sent 2 times for the same problem", third["reasons"][-1])

    def test_a_recent_successful_delivery_waits_for_the_idle_window(self) -> None:
        saved = {"signature": "create", "count": 1, "at": NOW}
        again = stage(workspace(chat(), ahead=1), nudge=saved, now=NOW + 120)
        self.assertEqual(again["move"], {"kind": "wait", "command": "create", "minutes_left": 8})
        other = stage(workspace(chat(), ahead=1), nudge={"signature": "shape-up:stale", "count": 2, "at": NOW})
        self.assertEqual(other["nudge"]["count"], 1)

    def test_a_merged_pull_request_is_archived_only_from_a_clean_checkout(self) -> None:
        merged = {"number": 9, "state": "MERGED", "head_oid": HEAD}
        clean = stage(workspace(chat(), ahead=2), past=merged)
        self.assertEqual((clean["stage"], clean["move"]), ("merged", {"kind": "archive"}))
        self.assertIsNone(stage(workspace(chat(), ahead=2, dirty=True), past=merged)["move"])
        closed = stage(workspace(chat(), ahead=2), past=merged | {"state": "CLOSED"})
        self.assertEqual((closed["stage"], closed["move"]), ("pr_closed", None))
        moved_on = stage(workspace(chat(), ahead=2, head="b" * 40), past=merged)
        self.assertEqual(moved_on["stage"], "work_done_no_pr")

    def test_a_branch_behind_its_merged_pull_request_is_never_sent_the_create_command(self) -> None:
        behind = workspace(chat(), ahead=2, head="b" * 40, past_elsewhere={"number": 9, "state": "MERGED"})
        result = stage(behind)
        self.assertEqual((result["stage"], result["group"], result["move"]), ("past_pr_elsewhere", "needs_me", None))
        self.assertIn("#9 on this branch was merged", result["reasons"][0])
        closed = stage(workspace(chat(), ahead=2, past_elsewhere={"number": 9, "state": "CLOSED"}))
        self.assertIn("was closed", closed["reasons"][0])

    def test_a_checkout_away_from_the_pull_request_head_is_only_reported(self) -> None:
        result = stage(workspace(chat(), ahead=1, head="b" * 40), pull_request())
        self.assertEqual((result["stage"], result["move"]), ("out_of_sync", None))

    def test_what_shape_up_can_clear_gets_the_shape_up_command(self) -> None:
        cases: dict[str, Json] = {
            "conflict": {"mergeable": "CONFLICTING"},
            "checks_failing": {"checks": {"state": "failing", "failing": ["test"], "pending": []}},
            "stale": {"stale": {"stale": True, "overlap": ["src/a.py"], "shared": [], "moved": 2}},
            "ai_threads": {"threads": {"ai": 2, "human": 0, "answered": 0, "unclassified": 0}},
            "behind": {"merge_state": "BEHIND"},
        }
        for code, change in cases.items():
            with self.subTest(code=code):
                result = stage(workspace(chat(agent="codex"), ahead=1), pull_request(**change))
                self.assertEqual(
                    (result["stage"], result["move"]["message"]), ("pr_not_in_shape", "$trackbed:pr:shape-up")
                )
                self.assertEqual(result["nudge"]["signature"], f"shape-up:{code}")

    def test_stages_that_no_command_can_clear_send_nothing(self) -> None:
        cases: dict[str, Json] = {
            "human_review": {"threads": {"ai": 0, "human": 1, "answered": 0, "unclassified": 0}},
            "checks_running": {"checks": {"state": "pending", "failing": [], "pending": ["test"]}},
            "draft": {"draft": True},
            "stacked": {"base": "feature"},
            "no_checks": {"checks": {"state": "none", "failing": [], "pending": []}},
            "threads_open": {"threads": {"ai": 0, "human": 0, "answered": 1, "unclassified": 0}},
            "review_required": {"feedback": {"changes_requested": False, "review_required": True, "unanswered": []}},
            "protected": {"merge_state": "BLOCKED"},
        }
        for name, change in cases.items():
            with self.subTest(stage=name):
                result = stage(workspace(chat(), ahead=1), pull_request(**change))
                self.assertEqual((result["stage"], result["move"]), (name, None))
        pending_and_blocked = pull_request(
            merge_state="BLOCKED", checks={"state": "pending", "failing": [], "pending": ["test"]}
        )
        self.assertEqual(stage(workspace(chat(), ahead=1), pending_and_blocked)["stage"], "checks_running")
        unknown = stage(workspace(chat(), ahead=1), pull_request(mergeable="UNKNOWN"))
        self.assertEqual((unknown["stage"], unknown["group"]), ("checks_running", "working"))

    def test_shape_up_goes_first_when_a_person_also_left_a_thread(self) -> None:
        both = pull_request(mergeable="CONFLICTING", threads={"ai": 0, "human": 1, "answered": 0, "unclassified": 0})
        self.assertEqual(stage(workspace(chat(), ahead=1), both)["stage"], "pr_not_in_shape")

    def test_only_a_clean_checkout_with_no_hold_reaches_the_merge_train(self) -> None:
        ready = stage(workspace(chat(), ahead=1), pull_request())
        self.assertEqual((ready["stage"], ready["group"], ready["holds"]), ("merge_ready", "merge_ready", []))
        dirty = stage(workspace(chat(), ahead=1, dirty=True), pull_request())
        self.assertEqual(dirty["stage"], "unpublished")

    def test_an_orphan_joins_the_train_or_is_reported_and_is_never_sent_anything(self) -> None:
        self.assertEqual(rules.orphan_stage(pull_request(), "main")["stage"], "merge_ready")
        self.assertEqual(rules.orphan_stage(pull_request(title="feat!: drop v1"), "main")["stage"], "held")
        blocked = rules.orphan_stage(pull_request(mergeable="CONFLICTING"), "main")
        self.assertEqual((blocked["stage"], blocked["move"]), ("orphan_blocked", None))
        self.assertIn("no workspace", blocked["reasons"][-1])

    def test_every_stage_has_a_label(self) -> None:
        results = [
            stage(workspace(chat(), ahead=1), pull_request()),
            rules.unreadable_pr(7, "gh exited 1"),
            rules.unreadable_history("gh exited 1"),
            stage(workspace(chat(), ahead=2, past_elsewhere={"number": 9, "state": "MERGED"})),
            rules.orphan_stage(pull_request(draft=True), "main"),
        ]
        for result in results:
            self.assertIn(result["stage"], rules.STAGE_LABELS)


class HoldTests(unittest.TestCase):
    def codes(self, **change: Any) -> list[str]:
        return [hold["code"] for hold in rules.pr_holds(pull_request(**change))]

    def test_a_high_or_unknown_risk_tier_holds(self) -> None:
        self.assertEqual(self.codes(), [])
        self.assertEqual(self.codes(risk={"floor": "medium", "signals": []}), [])
        self.assertEqual(self.codes(risk={"floor": "high", "signals": ["path:ci"]}), ["risk_high"])
        self.assertEqual(self.codes(risk={"error": "git diff failed"}), ["risk_unknown"])
        self.assertEqual(self.codes(risk=None), ["risk_unknown"])

    def test_a_breaking_change_marker_holds(self) -> None:
        self.assertEqual(self.codes(title="fix(codex)!: simplify legacy install cleanup"), ["breaking_change"])
        self.assertEqual(self.codes(body="Details.\n\nBREAKING CHANGE: the flag is gone"), ["breaking_change"])
        self.assertEqual(self.codes(title="fix: handle the ! character", body="not a BREAKING CHANGE: footer"), [])

    def test_feedback_from_a_person_holds(self) -> None:
        self.assertEqual(self.codes(feedback={"changes_requested": True, "unanswered": []}), ["person_feedback"])
        named = rules.pr_holds(
            pull_request(feedback={"changes_requested": True, "requested_by": ["ana"], "unanswered": []})
        )
        self.assertEqual(named[0]["text"], "`ana` requested changes")
        self.assertEqual(self.codes(feedback={"changes_requested": False, "unanswered": ["ana"]}), ["person_feedback"])


class ReviewFactTests(unittest.TestCase):
    def test_threads_are_counted_by_who_must_act(self) -> None:
        threads = [
            thread(comment("coderabbitai", "2026-01-01T10:00:00Z", "Bot")),
            thread(comment("coderabbitai", "2026-01-01T10:00:00Z", "Bot"), comment("me", "2026-01-01T11:00:00Z")),
            thread(comment("ana", "2026-01-01T10:00:00Z"), comment("coderabbitai", "2026-01-01T10:05:00Z", "Bot")),
            thread(comment("ana", "2026-01-01T10:00:00Z"), resolved=True),
            thread(comment("me", "2026-01-01T10:00:00Z")),
            thread(comment("copilot", "2026-01-01T10:00:00Z", "Bot"), comment("me", "2026-01-01T11:00:00Z"), more=True),
        ]
        self.assertEqual(
            rules.summarize_threads(threads, "me"), {"ai": 2, "human": 1, "answered": 1, "unclassified": 1}
        )

    def test_feedback_counts_until_the_author_answers(self) -> None:
        comments = [comment("ana", "2026-01-02T10:00:00Z"), comment("github-actions", "2026-01-03T10:00:00Z", "Bot")]
        reviews = [
            {
                "author": {"login": "bo", "__typename": "User"},
                "state": "COMMENTED",
                "body": "why?",
                "submittedAt": "2026-01-02T12:00:00Z",
            },
            {
                "author": {"login": "cy", "__typename": "User"},
                "state": "COMMENTED",
                "body": " ",
                "submittedAt": "2026-01-02T12:00:00Z",
            },
            {
                "author": {"login": "di", "__typename": "User"},
                "state": "APPROVED",
                "body": "Could you update the migration guide before merging?",
                "submittedAt": "2026-01-02T12:00:00Z",
            },
        ]
        open_feedback = rules.feedback_facts("CHANGES_REQUESTED", comments, reviews, "me")
        self.assertEqual(
            open_feedback,
            {
                "changes_requested": True,
                "requested_by": [],
                "review_required": False,
                "unanswered": ["ana", "bo", "di"],
            },
        )
        answered = rules.feedback_facts(None, [*comments, comment("me", "2026-01-04T10:00:00Z")], reviews, "me")
        self.assertEqual(
            answered, {"changes_requested": False, "requested_by": [], "review_required": False, "unanswered": []}
        )
        self.assertTrue(rules.feedback_facts("REVIEW_REQUIRED", [], [], "me")["review_required"])

    def test_a_reply_to_a_bot_thread_answers_no_person(self) -> None:
        def review(login: str, state: str, at: str, body: str = "") -> Json:
            return {"author": {"login": login, "__typename": "User"}, "state": state, "body": body, "submittedAt": at}

        asked = [
            review("ana", "CHANGES_REQUESTED", "2026-01-02T10:00:00Z", "Please hold this."),
            review("bo", "COMMENTED", "2026-01-02T11:00:00Z", "Why this approach?"),
        ]
        bot_reply = review("me", "COMMENTED", "2026-01-03T10:00:00Z")
        held = rules.feedback_facts(None, [], [*asked, bot_reply], "me")
        self.assertEqual((held["changes_requested"], held["requested_by"]), (True, ["ana"]))
        self.assertEqual(held["unanswered"], ["ana", "bo"])
        answered = rules.feedback_facts(None, [comment("me", "2026-01-04T10:00:00Z")], [*asked, bot_reply], "me")
        self.assertEqual((answered["requested_by"], answered["unanswered"]), (["ana"], []))
        approved = review("ana", "APPROVED", "2026-01-05T10:00:00Z")
        cleared = rules.feedback_facts(None, [comment("me", "2026-01-04T10:00:00Z")], [*asked, approved], "me")
        self.assertEqual((cleared["changes_requested"], cleared["unanswered"]), (False, []))


class PlanningTests(unittest.TestCase):
    def test_shared_paths_are_ci_lockfiles_manifests_and_build_tools(self) -> None:
        def shared(path: str) -> bool:
            return rules.is_shared_path(
                path,
                lambda p: p.startswith(".github/workflows/"),
                lambda n: n == "package.json",
                frozenset({"uv.lock"}),
            )

        for path in (".github/workflows/ci.yml", "uv.lock", "web/package.json", "trackbed/Makefile", ".nvmrc"):
            self.assertTrue(shared(path), path)
        for path in ("src/app.py", "docs/Makefile.md", "README.md"):
            self.assertFalse(shared(path), path)

    def test_the_train_takes_pull_requests_that_share_no_files_first(self) -> None:
        overlaps = rules.shared_with({3: {"a.py"}, 5: {"a.py", "b.py"}, 8: {"c.py"}, 9: {"b.py"}})
        self.assertEqual(overlaps, {3: [5], 5: [3, 9], 8: [], 9: [5]})
        self.assertEqual(rules.order_train([9, 5, 3, 8], overlaps), [8, 3, 9, 5])

    def test_issue_keys_come_from_the_start_of_a_branch_segment(self) -> None:
        self.assertEqual(rules.issue_key("abildtoft/skills-147-ship-it"), "SKILLS-147")
        self.assertEqual(rules.issue_key("SKILLS-9"), "SKILLS-9")
        self.assertIsNone(rules.issue_key("fix/names-in-utf-8"))
        self.assertIsNone(rules.issue_key("Abildtoft/kmfd7"))

    def test_the_most_urgent_chat_drives_the_workspace(self) -> None:
        old = chat(last_message_at="2026-01-01", id="old")
        new = chat(last_message_at="2026-01-02", id="new")
        self.assertEqual(rules.driving_chat([old, new])["id"], "new")
        self.assertEqual(
            rules.driving_chat([new, chat("running", last_message_at="2025-01-01", id="busy")])["id"], "busy"
        )
        self.assertIsNone(rules.driving_chat([]))

    def test_sections_move_only_workspaces_the_user_has_not_placed(self) -> None:
        ids = iter(["new-1", "new-2"])
        sections = [
            {"id": "s-needs", "name": "Needs me", "kind": "custom"},
            {"id": "s-mine", "name": "Client work", "kind": "custom"},
            {"id": "s-pin", "name": "Pinned", "kind": "pinned"},
        ]
        rows = [
            {"id": "w1", "name": "oslo", "group": "working", "section_id": None},
            {"id": "w2", "name": "lima", "group": "needs_me", "section_id": "s-needs"},
            {"id": "w3", "name": "cairo", "group": "merge_ready", "section_id": "s-needs"},
            {"id": "w4", "name": "hanoi", "group": "nudge", "section_id": "s-mine"},
            {"id": "w5", "name": "perth", "group": "merged", "section_id": "s-pin"},
            {"id": "w6", "name": "turin", "group": None, "section_id": None},
            {"id": "w7", "name": "quito", "group": "working", "section_id": None},
        ]
        plan = rules.plan_sections(rows, sections, lambda: next(ids))
        self.assertEqual(
            plan["create"], [{"name": "Working", "section_id": "new-1"}, {"name": "Merge-ready", "section_id": "new-2"}]
        )
        self.assertEqual(
            plan["moves"],
            [
                {"section_id": "new-1", "name": "Working", "workspace_ids": ["w1", "w7"]},
                {"section_id": "new-2", "name": "Merge-ready", "workspace_ids": ["w3"]},
            ],
        )
        self.assertEqual(plan["left_in_place"], ["hanoi", "perth"])
        self.assertIsNone(rules.plan_sections(rows, None, lambda: "unused"))


SINGLE = """Decision needed · SKILLS-22: resume review for the open finding, or stop here?

Review used its whole fix budget and one required finding is open.

1. Resume review (recommended): starts a new fix budget of up to 2 cycles.
2. Stop here: leaves the finding open.

State: branch pushed, Pull Request #12 open.
"""


class RequestTests(unittest.TestCase):
    def test_the_example_in_the_shared_format_gets_a_reply(self) -> None:
        reference = SCRIPTS.parents[2] / "shared" / "implementation" / "references" / "decision-request.md"
        example = reference.read_text(encoding="utf-8").split("## Example", 1)[1].split("```text\n", 1)[1]
        result = requests.parse_request(example.split("```", 1)[0])
        self.assertEqual((result["kind"], result["reply"]), ("decision", "Option 1: Resume review"))

    def test_a_decision_with_a_recommended_first_option_gets_a_reply(self) -> None:
        result = requests.parse_request(SINGLE)
        self.assertEqual((result["kind"], result["reply"]), ("decision", "Option 1: Resume review"))
        self.assertEqual(result["questions"], ["SKILLS-22: resume review for the open finding, or stop here?"])
        bold = requests.parse_request(
            SINGLE.replace("Decision needed · SKILLS-22: resume", "**Decision needed · SKILLS-22: resume")
        )
        self.assertEqual(bold["reply"], "Option 1: Resume review")

    def test_several_decisions_are_answered_together_or_not_at_all(self) -> None:
        both = (
            "Decision 1 of 2 · PR #4: rebase now?\n\n1. **Rebase** (recommended): rebases.\n2. Skip.\n\n"
            "Decision 2 of 2 · PR #4: keep the draft?\n\n1. Keep it (recommended)\n2. Drop it\n\nState: nothing pushed."
        )
        self.assertEqual(
            requests.parse_request(both)["reply"], "Decision 1: option 1, Rebase\nDecision 2: option 1, Keep it"
        )
        missing = requests.parse_request(both.replace("1. Keep it (recommended)", "1. Keep it"))
        self.assertEqual((missing["kind"], missing["reply"]), ("decision", None))
        self.assertIn("decision 2", missing["reason"])
        cut_off = requests.parse_request(both.split("Decision 2 of 2")[0])
        self.assertIsNone(cut_off["reply"])
        self.assertIn("not numbered 1 to the stated total", cut_off["reason"])

    def test_no_reply_when_the_recommendation_leaves_any_doubt(self) -> None:
        cases = {
            "second option recommended": SINGLE.replace("Resume review (recommended)", "Resume review").replace(
                "2. Stop here", "2. Stop here (recommended)"
            ),
            "two options recommended": SINGLE.replace("2. Stop here", "2. Stop here (recommended)"),
            "no options": SINGLE.split("1. Resume")[0],
            "cut short": SINGLE + "… [221 more characters]",
            "option after the state line": SINGLE.replace("1. Resume review (recommended)", "1. Resume review")
            + "1. Other (recommended)",
            "two unnumbered decisions": SINGLE + "\n" + SINGLE,
            "numbered and unnumbered decisions": SINGLE.replace("Decision needed ·", "Decision 1 of 1 ·")
            + "\n"
            + SINGLE,
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                result = requests.parse_request(text)
                self.assertEqual((result["kind"], result["reply"]), ("decision", None))
                self.assertTrue(result["reason"])

    def test_an_action_request_is_never_answered(self) -> None:
        result = requests.parse_request(
            "Action needed · SKILLS-3: grant access to the registry\n\n1. Do it (recommended)\n"
        )
        self.assertEqual((result["kind"], result["reply"]), ("action", None))

    def test_other_questions_are_reported_without_an_automatic_reply(self) -> None:
        prose = "**D1: Which colour?**\n\n**A) Red (recommended)**\n\n**B) Blue**\n\nReply with a letter (A or B)."
        self.assertEqual(requests.parse_request(prose)["kind"], "options")
        late = "All done.\n\n" + SINGLE
        self.assertEqual(
            (requests.parse_request(late)["kind"], requests.parse_request(late)["reply"]), ("options", None)
        )
        for text in (
            "Opened Pull Request #12. Want me to watch CI?",
            "Which approach should I use?**",
            "Unfinished sentence… [21 more characters]",
        ):
            result = requests.parse_request(text)
            self.assertEqual((result["kind"], result["reply"]), ("options", None))
        for text in ("", "Rebased onto main and pushed."):
            self.assertEqual(
                requests.parse_request(text), {"kind": "none", "questions": [], "reply": None, "reason": None}
            )

    def test_the_reply_carries_only_a_short_plain_label(self) -> None:
        marked = SINGLE.replace("1. Resume review (recommended)", "1. **`Resume` _review_** (Recommended)")
        self.assertEqual(requests.parse_request(marked)["reply"], "Option 1: Resume review")
        long_label = SINGLE.replace("Resume review", "Resume " + "x" * 120)
        self.assertIsNone(requests.parse_request(long_label)["reply"])


if __name__ == "__main__":
    unittest.main()
