"""Behavioral tests for the Pull Request shape-up snapshot helper.

Every `git` and `gh` call the helper makes is answered by an in-memory host, so no test needs a repository,
a network, or a GitHub account. The host refuses any command it does not know, which keeps the helper's
read-only promise under test.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import unittest
from collections.abc import Sequence
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "skills" / "pr:shape-up" / "scripts" / "shape-snapshot.py"
SPEC = importlib.util.spec_from_file_location("shape_snapshot", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
# Keep compiled bytecode out of the skill directory, which skill scanners and the converter read.
sys.dont_write_bytecode = True
shape_snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shape_snapshot)

PR_HEAD = "a" * 40
OTHER = "b" * 40
AUTHOR = "octocat"


def comment(login: str | None, at: str, *, kind: str = "User", minimized: bool = False) -> dict[str, Any]:
    author = None if login is None else {"login": login, "__typename": kind}
    return {
        "url": f"https://github.com/acme/demo/pull/7#discussion_{at}",
        "createdAt": at,
        "isMinimized": minimized,
        "author": author,
    }


def bot(at: str, login: str = "coderabbitai", **kwargs: Any) -> dict[str, Any]:
    return comment(login, at, kind="Bot", **kwargs)


def thread(*comments: dict[str, Any], resolved: bool = False, more: bool = False, **fields: Any) -> dict[str, Any]:
    return {
        "id": fields.get("id", "T_1"),
        "isResolved": resolved,
        "isOutdated": fields.get("outdated", False),
        "path": fields.get("path", "src/app.py"),
        "line": fields.get("line", 12),
        "comments": {"pageInfo": {"hasNextPage": more}, "nodes": list(comments)},
    }


def check(name: str, bucket: str) -> dict[str, Any]:
    return {"name": name, "state": bucket.upper(), "bucket": bucket, "link": f"https://ci/{name}", "workflow": "CI"}


class FakeHost:
    """Answers the helper's commands from in-memory Pull Request state and records each call."""

    def __init__(self) -> None:
        self.view: Any = {
            "number": 7,
            "url": "https://github.com/acme/demo/pull/7",
            "state": "OPEN",
            "isDraft": False,
            "baseRefName": "main",
            "headRefName": "feature",
            "headRefOid": PR_HEAD,
            "author": {"login": AUTHOR},
        }
        self.view_exit = 0
        self.head = PR_HEAD
        self.objects = {PR_HEAD}
        self.ancestors: set[tuple[str, str]] = set()
        self.branch = "feature"
        self.status = ""
        self.fetch_exit = 0
        self.behind = "0"
        self.checks: tuple[int, str, str] = (0, json.dumps([check("test", "pass")]), "")
        self.pages: list[Any] = [self.page([])]
        self.graphql_exit = 0
        self.calls: list[list[str]] = []

    @staticmethod
    def page(threads: list[dict[str, Any]], cursor: str | None = None) -> dict[str, Any]:
        info = {"hasNextPage": cursor is not None, "endCursor": cursor}
        return {"data": {"repository": {"pullRequest": {"reviewThreads": {"pageInfo": info, "nodes": threads}}}}}

    def __call__(self, argv: Sequence[str], timeout: int) -> subprocess.CompletedProcess[bytes]:
        command = list(argv)
        self.calls.append(command)
        code, out, err = self.answer(command)
        return subprocess.CompletedProcess(command, code, out.encode(), err.encode())

    def answer(self, argv: list[str]) -> tuple[int, str, str]:
        match argv:
            case ["gh", "pr", "view", "--json", _]:
                return self.view_exit, json.dumps(self.view), "no pull requests found for branch"
            case ["gh", "pr", "checks", "--json", _]:
                return self.checks
            case ["gh", "api", "graphql", "--hostname", _, *fields]:
                assert "owner=acme" in fields and "name=demo" in fields and "number=7" in fields
                assert not any("mutation" in field for field in fields)
                cursors = [field.removeprefix("cursor=") for field in fields if field.startswith("cursor=")]
                index = int(cursors[0]) if cursors else 0
                page = self.pages[index]
                return self.graphql_exit, page if isinstance(page, str) else json.dumps(page), "graphql failed"
            case ["git", "check-ref-format", "--branch", name]:
                return (1, "", "invalid") if " " in name else (0, name + "\n", "")
            case ["git", "rev-parse", "HEAD"]:
                return 0, self.head + "\n", ""
            case ["git", "cat-file", "-e", spec]:
                return (0 if spec.removesuffix("^{commit}") in self.objects else 1), "", ""
            case ["git", "merge-base", "--is-ancestor", ancestor, descendant]:
                return (0 if (ancestor, descendant) in self.ancestors else 1), "", ""
            case ["git", "branch", "--show-current"]:
                return 0, self.branch + "\n", ""
            case ["git", "status", "--porcelain"]:
                return 0, self.status, ""
            case ["git", "fetch", "--quiet", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main"]:
                return self.fetch_exit, "", "fatal: could not read from remote"
            case ["git", "rev-list", "--count", "HEAD..refs/remotes/origin/main"]:
                return 0, self.behind + "\n", ""
        return 97, "", "unexpected command: " + " ".join(argv)


class SnapshotCase(unittest.TestCase):
    def setUp(self) -> None:
        self.host = FakeHost()
        patcher = mock.patch.object(shape_snapshot, "run", self.host)
        patcher.start()
        self.addCleanup(patcher.stop)

    def snapshot(self) -> dict[str, Any]:
        code, document = self.invoke()
        self.assertEqual((code, document["status"]), (0, "ok"), document)
        return document

    def invoke(self, *argv: str) -> tuple[int, dict[str, Any]]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = shape_snapshot.main(list(argv))
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 1, "the helper prints exactly one line")
        document = json.loads(lines[0])
        self.assertIsInstance(document, dict)
        return code, document

    def error(self) -> str:
        code, document = self.invoke()
        self.assertEqual((code, document["status"]), (1, "error"), document)
        return str(document["message"])


class InShapeTests(SnapshotCase):
    def test_a_synced_green_pull_request_without_ai_threads_is_in_shape(self) -> None:
        document = self.snapshot()

        self.assertTrue(document["in_shape"])
        self.assertEqual(document["needs"], {"rebase": False, "ci": False, "ai_feedback": False})
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(
            document["pr"],
            {
                "number": 7,
                "url": "https://github.com/acme/demo/pull/7",
                "state": "OPEN",
                "draft": False,
                "base": "main",
                "head": "feature",
                "head_oid": PR_HEAD,
                "author": AUTHOR,
            },
        )
        self.assertEqual(
            document["local"], {"branch": "feature", "head_oid": PR_HEAD, "relation": "equal", "dirty": False}
        )
        self.assertEqual(document["base"], {"ref": "origin/main", "behind": 0})

    def test_the_helper_only_reads(self) -> None:
        self.snapshot()

        programs = {(call[0], call[1]) for call in self.host.calls}
        self.assertEqual(
            programs,
            {
                ("gh", "pr"),
                ("gh", "api"),
                ("git", "check-ref-format"),
                ("git", "rev-parse"),
                ("git", "branch"),
                ("git", "status"),
                ("git", "fetch"),
                ("git", "rev-list"),
            },
        )
        self.assertEqual([call[2] for call in self.host.calls if call[:2] == ["gh", "pr"]], ["view", "checks"])

    def test_every_need_is_reported_together(self) -> None:
        self.host.behind = "3"
        self.host.checks = (1, json.dumps([check("test", "fail")]), "")
        self.host.pages = [FakeHost.page([thread(bot("2026-11-10T10:00:00Z"))])]
        self.host.status = " M notes.md\n"

        document = self.snapshot()

        self.assertFalse(document["in_shape"])
        self.assertEqual(document["needs"], {"rebase": True, "ci": True, "ai_feedback": True})
        self.assertEqual(document["base"]["behind"], 3)
        self.assertTrue(document["local"]["dirty"])


class LocalRelationTests(SnapshotCase):
    def relation(self) -> str:
        return str(self.snapshot()["local"]["relation"])

    def test_unpushed_commits_are_ahead(self) -> None:
        self.host.head = OTHER
        self.host.ancestors = {(PR_HEAD, OTHER)}
        self.assertEqual(self.relation(), "ahead")

    def test_a_stale_checkout_is_behind(self) -> None:
        self.host.head = OTHER
        self.host.ancestors = {(OTHER, PR_HEAD)}
        self.assertEqual(self.relation(), "behind")

    def test_unrelated_tips_are_diverged(self) -> None:
        self.host.head = OTHER
        self.assertEqual(self.relation(), "diverged")

    def test_a_pull_request_head_that_was_never_fetched_is_unknown(self) -> None:
        self.host.head = OTHER
        self.host.objects = set()
        self.assertEqual(self.relation(), "unknown")

    def test_a_detached_head_has_no_branch(self) -> None:
        self.host.branch = ""
        self.assertIsNone(self.snapshot()["local"]["branch"])


class CheckTests(SnapshotCase):
    def checks(self, rows: list[dict[str, Any]], code: int = 0) -> dict[str, Any]:
        self.host.checks = (code, json.dumps(rows), "")
        document = self.snapshot()
        self.assertEqual(document["needs"]["ci"], document["checks"]["state"] in ("failing", "pending"))
        return dict(document["checks"])

    def test_passing_and_skipped_checks_are_green(self) -> None:
        checks = self.checks([check("test", "pass"), check("docs", "skipping")])

        self.assertEqual(checks["state"], "passing")
        self.assertEqual(checks["counts"], {"pass": 1, "skipping": 1, "fail": 0, "cancel": 0, "pending": 0})
        self.assertEqual((checks["failing"], checks["pending"]), ([], []))

    def test_a_failed_or_cancelled_check_is_failing_even_while_others_run(self) -> None:
        checks = self.checks([check("test", "fail"), check("build", "cancel"), check("lint", "pending")], code=1)

        self.assertEqual(checks["state"], "failing")
        self.assertEqual([entry["name"] for entry in checks["failing"]], ["test", "build"])
        self.assertEqual(
            checks["failing"][0], {"name": "test", "workflow": "CI", "link": "https://ci/test", "bucket": "fail"}
        )
        self.assertEqual([entry["name"] for entry in checks["pending"]], ["lint"])

    def test_a_running_check_is_pending(self) -> None:
        checks = self.checks([check("test", "pass"), check("lint", "pending")], code=8)
        self.assertEqual(checks["state"], "pending")

    def test_an_unknown_bucket_is_never_green(self) -> None:
        checks = self.checks([check("test", "mystery")])

        self.assertEqual(checks["state"], "pending")
        self.assertEqual(checks["pending"][0]["bucket"], "pending")

    def test_a_pull_request_without_checks_needs_no_ci_work(self) -> None:
        self.host.checks = (1, "", "no checks reported on the 'feature' branch")
        document = self.snapshot()

        self.assertEqual(document["checks"]["state"], "none")
        self.assertFalse(document["needs"]["ci"])

    def test_unreadable_checks_stop_the_snapshot(self) -> None:
        self.host.checks = (1, "", "HTTP 502")
        self.assertIn("could not read the Pull Request checks: HTTP 502", self.error())

        self.host.checks = (0, "not json", "")
        self.assertIn("could not read the Pull Request checks", self.error())

        self.host.checks = (0, json.dumps(["test"]), "")
        self.assertIn("could not parse the Pull Request checks", self.error())


class ThreadTests(SnapshotCase):
    def review(self, *threads: dict[str, Any]) -> dict[str, Any]:
        self.host.pages = [FakeHost.page(list(threads))]
        document = self.snapshot()
        self.assertEqual(document["needs"]["ai_feedback"], bool(document["review"]["ai_threads"]))
        return dict(document["review"])

    def test_an_unresolved_bot_thread_is_ai_feedback(self) -> None:
        first, second = bot("2026-11-10T10:00:00Z"), bot("2026-11-10T11:00:00Z", login="copilot")
        review = self.review(thread(first, second, id="T_9", path="src/a.py", line=4, outdated=True))

        self.assertEqual(
            review["ai_threads"],
            [
                {
                    "id": "T_9",
                    "path": "src/a.py",
                    "line": 4,
                    "outdated": True,
                    "reviewer": "coderabbitai",
                    "url": second["url"],
                }
            ],
        )
        self.assertEqual((review["human_threads"], review["answered_threads"]), (0, 0))

    def test_a_resolved_thread_is_ignored(self) -> None:
        review = self.review(thread(bot("2026-11-10T10:00:00Z"), resolved=True))
        self.assertEqual(review, {"ai_threads": [], "human_threads": 0, "answered_threads": 0})

    def test_any_feedback_from_a_person_makes_the_thread_human(self) -> None:
        review = self.review(
            thread(comment("reviewer", "2026-11-10T10:00:00Z")),
            thread(bot("2026-11-10T10:00:00Z"), comment("reviewer", "2026-11-10T11:00:00Z")),
            thread(comment(None, "2026-11-10T10:00:00Z")),
        )

        self.assertEqual(review["ai_threads"], [])
        self.assertEqual(review["human_threads"], 3)

    def test_a_thread_the_author_answered_is_not_open(self) -> None:
        review = self.review(thread(bot("2026-11-10T10:00:00Z"), comment(AUTHOR, "2026-11-10T11:00:00Z")))

        self.assertEqual(review["ai_threads"], [])
        self.assertEqual(review["answered_threads"], 1)

    def test_a_bot_comment_after_the_authors_reply_reopens_the_thread(self) -> None:
        review = self.review(
            thread(
                bot("2026-11-10T10:00:00Z"),
                comment(AUTHOR, "2026-11-10T11:00:00Z"),
                bot("2026-11-10T12:00:00Z"),
            )
        )

        self.assertEqual(len(review["ai_threads"]), 1)
        self.assertEqual(review["answered_threads"], 0)

    def test_hidden_comments_and_author_only_threads_carry_no_feedback(self) -> None:
        review = self.review(
            thread(bot("2026-11-10T10:00:00Z", minimized=True)),
            thread(comment(AUTHOR, "2026-11-10T10:00:00Z")),
        )
        self.assertEqual(review, {"ai_threads": [], "human_threads": 0, "answered_threads": 0})

    def test_a_thread_longer_than_one_page_stays_open_for_the_reply_pass(self) -> None:
        review = self.review(thread(bot("2026-11-10T10:00:00Z"), comment(AUTHOR, "2026-11-10T11:00:00Z"), more=True))

        self.assertEqual(len(review["ai_threads"]), 1)
        self.assertEqual(review["answered_threads"], 0)

    def test_a_bot_authored_pull_request_keeps_other_bots_feedback(self) -> None:
        self.host.view["author"] = {"login": "coderabbitai"}
        review = self.review(
            thread(bot("2026-11-10T10:00:00Z")),
            thread(bot("2026-11-10T10:00:00Z", login="copilot"), id="T_2"),
        )
        self.assertEqual([entry["id"] for entry in review["ai_threads"]], ["T_2"])

    def test_threads_are_read_across_pages(self) -> None:
        self.host.pages = [
            FakeHost.page([thread(bot("2026-11-10T10:00:00Z"), id="T_1")], cursor="1"),
            FakeHost.page([thread(bot("2026-11-10T10:00:00Z"), id="T_2")]),
        ]

        review = self.snapshot()["review"]

        self.assertEqual([entry["id"] for entry in review["ai_threads"]], ["T_1", "T_2"])
        graphql = [call for call in self.host.calls if call[:3] == ["gh", "api", "graphql"]]
        self.assertEqual(["cursor=1" in call for call in graphql], [False, True])

    def test_pages_that_never_end_stop_the_snapshot(self) -> None:
        self.host.pages = [FakeHost.page([], cursor="0")]
        with mock.patch.object(shape_snapshot, "MAX_THREAD_PAGES", 3):
            self.assertIn("too many pages", self.error())
        self.assertEqual(len([call for call in self.host.calls if call[:3] == ["gh", "api", "graphql"]]), 3)

    def test_a_page_without_a_cursor_stops_the_snapshot(self) -> None:
        page = FakeHost.page([])
        page["data"]["repository"]["pullRequest"]["reviewThreads"]["pageInfo"] = {
            "hasNextPage": True,
            "endCursor": None,
        }
        self.host.pages = [page]
        self.assertIn("could not read every review thread", self.error())

    def test_unreadable_threads_stop_the_snapshot(self) -> None:
        self.host.graphql_exit = 1
        self.assertIn("could not read the review threads: graphql failed", self.error())

        self.host.graphql_exit = 0
        for page in ("not json", {"data": {"repository": None}}, {"errors": [{"message": "nope"}]}):
            self.host.pages = [page]
            self.assertIn("could not parse the review threads", self.error())


class PullRequestTests(SnapshotCase):
    def test_a_branch_without_a_pull_request_is_an_error(self) -> None:
        self.host.view_exit = 1
        message = self.error()

        self.assertIn("could not read a Pull Request for the current branch", message)
        self.assertIn("no pull requests found", message)

    def test_a_merged_or_closed_pull_request_is_an_error(self) -> None:
        for state in ("MERGED", "CLOSED"):
            self.host.view["state"] = state
            self.assertEqual(self.error(), f"Pull Request #7 is {state.lower()}, not open")

    def test_a_malformed_pull_request_is_an_error(self) -> None:
        broken: list[tuple[str, Any]] = [
            ("url", "https://github.com/acme/demo/issues/7"),
            ("number", 8),
            ("headRefOid", "abc"),
            ("headRefName", "bad name"),
            ("baseRefName", ""),
        ]
        for field, value in broken:
            host = FakeHost()
            host.view[field] = value
            with mock.patch.object(shape_snapshot, "run", host):
                self.assertIn("could not parse the Pull Request", self.error(), field)

        self.host.view = ["not", "an", "object"]
        self.assertIn("could not parse the Pull Request", self.error())

    def test_a_draft_from_a_deleted_account_is_still_read(self) -> None:
        self.host.view["isDraft"] = True
        self.host.view["author"] = None

        document = self.snapshot()

        self.assertTrue(document["pr"]["draft"])
        self.assertIsNone(document["pr"]["author"])

    def test_an_enterprise_host_is_passed_to_the_api(self) -> None:
        self.host.view["url"] = "https://ghe.example.com/acme/demo/pull/7"
        self.snapshot()

        graphql = [call for call in self.host.calls if call[:3] == ["gh", "api", "graphql"]]
        self.assertEqual([call[3:5] for call in graphql], [["--hostname", "ghe.example.com"]])

    def test_a_failed_fetch_of_the_target_branch_is_an_error(self) -> None:
        self.host.fetch_exit = 128
        self.assertIn("could not fetch `main` from origin: fatal: could not read from remote", self.error())

    def test_a_failed_git_command_names_the_command(self) -> None:
        self.host.behind = "many"
        with self.assertRaises(ValueError):
            shape_snapshot.snapshot()

        failing = mock.Mock(return_value=subprocess.CompletedProcess([], 128, b"", b"fatal: not a git repository"))
        with mock.patch.object(shape_snapshot, "run", failing):
            with self.assertRaisesRegex(shape_snapshot.ShapeError, "`git rev-parse` failed: fatal: not a git"):
                shape_snapshot.git("rev-parse", "HEAD")


class InvocationTests(unittest.TestCase):
    def test_an_argument_is_an_invalid_invocation(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            shape_snapshot.main(["--fix"])
        self.assertEqual(raised.exception.code, 2)

    def test_a_command_that_cannot_start_reports_exit_127(self) -> None:
        result = shape_snapshot.run(["trackbed-no-such-program"], 5)
        self.assertEqual(result.returncode, 127)

    def test_a_command_that_hangs_reports_exit_124(self) -> None:
        expired = subprocess.TimeoutExpired(["git"], 5)
        with mock.patch.object(shape_snapshot.subprocess, "run", side_effect=expired):
            result = shape_snapshot.run(["git", "status"], 5)
        self.assertEqual((result.returncode, result.stderr), (124, b"timed out after 5s"))

    def test_commands_run_without_prompts(self) -> None:
        environment = shape_snapshot.environment()
        self.assertEqual((environment["GH_PROMPT_DISABLED"], environment["GIT_TERMINAL_PROMPT"]), ("1", "0"))


if __name__ == "__main__":
    unittest.main()
