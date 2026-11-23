"""Behavioral tests for the showtime helper's `board`, `reply`, and `merge` commands.

Every `git` and `gh` call the helper makes is answered by an in-memory host, so no test needs a repository,
a network, a GitHub account, or Conductor. The host refuses any command it does not know, which keeps the
helper's promises under test: `board` writes nothing to GitHub, and `merge` runs one pinned merge and nothing else.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from collections.abc import Sequence
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest import mock

if __package__:
    from .script_loader import load_script
else:
    from script_loader import load_script

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "conductor:showtime" / "scripts"
showtime = load_script("showtime", SCRIPTS / "showtime.py")

REPO = "acme/demo"
ORIGIN = "github.com/acme/demo"
BASE_REF = "refs/remotes/origin/main"
BASE = "f" * 40
SELF_ID = "ws-self"
Json = dict[str, Any]


def oid(letter: str) -> str:
    return letter * 40


def review_page(threads: Sequence[Json] = (), decision: str | None = None, comments: Sequence[Json] = ()) -> Json:
    node = {
        "reviewDecision": decision,
        "author": {"login": "me"},
        "comments": {"nodes": list(comments)},
        "reviews": {"nodes": []},
        "reviewThreads": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": list(threads)},
    }
    return {"data": {"repository": {"pullRequest": node}}}


class FakeHost:
    """Answers the helper's commands from in-memory repository state and records each call."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.repo: Json = {
            "nameWithOwner": REPO,
            "url": f"https://{ORIGIN}",
            "defaultBranchRef": {"name": "main"},
            "squashMergeAllowed": True,
            "mergeCommitAllowed": True,
            "rebaseMergeAllowed": False,
        }
        self.fetch_exit = 0
        self.remote_base = BASE
        self.lists: dict[str, list[Json]] = {"open": [], "merged": [], "closed": []}
        # Past Pull Requests too old for the newest-first lists, found only by a lookup of their branch.
        self.older: list[Json] = []
        self.checkouts: dict[str, Json] = {}
        self.objects: set[str] = set()
        self.moved: dict[str, list[str]] = {}
        self.files: dict[str, list[str]] = {}
        self.checks: dict[str, list[Json]] = {}
        self.required: dict[str, list[Json]] = {}
        self.reviews: dict[str, Any] = {}
        self.risk: dict[str, Any] = {}
        self.rules: list[Json] = []
        self.protection: Json | None = None
        self.merge_exit = 0
        self.merge_lands = True
        self.calls: list[list[str]] = []
        self.workspaces: list[Json] = []
        self.sessions: list[Json] = []
        self.sections: list[Json] | None = []

    def workspace(self, name: str, head: str = oid("a"), **fields: Any) -> str:
        """Add a workspace with one chat; `branch`, `ahead`, `status`, `chat`, `agent`, and `idle` set its facts."""
        path = self.root / name
        path.mkdir()
        self.checkouts[str(path)] = {
            "head": head,
            "branch": fields.get("branch", f"me/{name}"),
            "status": fields.get("status", ""),
            "ahead": fields.get("ahead", 1),
            "contains": set(fields.get("contains", ())),
        }
        self.objects.add(head)
        last = datetime.now(UTC) - timedelta(minutes=fields.get("idle", 30))
        record = {
            "id": f"ws-{name}",
            "name": name,
            "branch": fields.get("branch", f"me/{name}"),
            "path": str(path),
            "state": fields.get("state", "ready"),
            "failureReason": None,
            "sectionId": fields.get("section"),
            "appUrl": f"conductor://workspace?id=ws-{name}",
        }
        self.workspaces.append(record)
        self.sessions.append(
            {
                "id": f"chat-{name}",
                "workspaceId": record["id"],
                "agent": fields.get("agent", "claude"),
                "state": fields.get("chat", "idle"),
                "archived": False,
                "lastMessageAt": last.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            }
        )
        return str(record["id"])

    def pull_request(self, number: int, branch: str, head: str = oid("a"), **fields: Any) -> None:
        """Add an open Pull Request that passes the gate unless `checks`, `title`, or another field says otherwise."""
        self.lists["open"].append(
            {
                "number": number,
                "title": fields.get("title", f"fix: change {number}"),
                "url": f"https://github.com/{REPO}/pull/{number}",
                "body": fields.get("body", ""),
                "headRefName": branch,
                "headRefOid": head,
                "headRepository": {"nameWithOwner": fields.get("head_repository", REPO)},
                "baseRefName": fields.get("base", "main"),
                "isDraft": fields.get("draft", False),
                "mergeable": fields.get("mergeable", "MERGEABLE"),
                "mergeStateStatus": fields.get("merge_state", "CLEAN"),
            }
        )
        self.objects.add(head)
        self.files[head] = fields.get("files", [f"src/file{number}.py"])
        self.moved[head] = fields.get("moved", [])
        self.checks[str(number)] = fields.get("checks", [{"name": "test", "bucket": "pass"}])
        self.required[str(number)] = fields.get("required", self.checks[str(number)])
        self.reviews[str(number)] = fields.get("reviews", review_page())
        self.risk[head] = fields.get("risk", {"floor": "low", "signals": []})

    def conductor_file(self) -> str:
        document: Json = {"self": {"workspaceId": SELF_ID}, "workspaces": self.workspaces, "sessions": self.sessions}
        if self.sections is not None:
            document["sections"] = self.sections
        path = self.root / "conductor.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return str(path)

    def __call__(
        self, argv: Sequence[str], timeout: float, input: bytes | None = None
    ) -> subprocess.CompletedProcess[bytes]:
        command = list(argv)
        self.calls.append(command)
        code, out, err = self.answer(command)
        return subprocess.CompletedProcess(command, code, out.encode(), err.encode())

    def check_answer(self, rows: list[Json]) -> tuple[int, str, str]:
        if not rows:
            return 1, "", "no checks reported on the 'x' branch"
        buckets = {row["bucket"] for row in rows}
        return (1 if "fail" in buckets else 8 if "pending" in buckets else 0), json.dumps(rows), ""

    def answer(self, argv: list[str]) -> tuple[int, str, str]:
        match argv:
            case ["git", "remote", "get-url", "origin"]:
                return 0, "git@github.com:acme/demo.git\n", ""
            case ["gh", "repo", "view", "github.com/acme/demo", "--json", _]:
                return 0, json.dumps(self.repo), ""
            case ["git", "check-ref-format", "--branch", name]:
                return 0, name + "\n", ""
            case ["git", "fetch", "--quiet", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main"]:
                return self.fetch_exit, "", "fatal: could not read from remote"
            case ["git", "rev-parse", "refs/remotes/origin/main"]:
                return 0, BASE + "\n", ""
            case ["git", "ls-remote", "--exit-code", "origin", "refs/heads/main"]:
                return 0, f"{self.remote_base}\trefs/heads/main\n", ""
            case [
                "gh",
                "pr",
                "list",
                "--repo",
                "github.com/acme/demo",
                "--author",
                "@me",
                "--state",
                state,
                "--limit",
                "100",
                "--json",
                _,
            ]:
                return 0, json.dumps(self.lists[state]), ""
            case [
                "gh",
                "pr",
                "list",
                "--repo",
                "github.com/acme/demo",
                "--author",
                "@me",
                head,
                "--state",
                "all",
                "--limit",
                "30",
                "--json",
                _,
            ] if head.startswith("--head="):
                branch = head.removeprefix("--head=")
                rows = self.lists["merged"] + self.lists["closed"] + self.older
                return 0, json.dumps([row for row in rows if row["headRefName"] == branch]), ""
            case ["gh", "api", "--hostname", "github.com", "repos/acme/demo/rules/branches/main?per_page=100"]:
                return 0, json.dumps(self.rules), ""
            case [
                "gh",
                "api",
                "--hostname",
                "github.com",
                "repos/acme/demo/branches/main/protection/required_status_checks",
            ]:
                if self.protection is None:
                    return 1, "", "gh: Required status checks not enabled (HTTP 404)"
                return 0, json.dumps(self.protection), ""
            case ["git", "-C", path, "merge-base", "--is-ancestor", commit, "HEAD"]:
                return (0 if commit in self.checkouts[path]["contains"] else 1), "", ""
            case ["git", "-C", path, "rev-parse", "HEAD"]:
                return 0, self.checkouts[path]["head"] + "\n", ""
            case ["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"]:
                return 0, self.checkouts[path]["branch"] + "\n", ""
            case ["git", "-C", path, "status", "--porcelain", "--untracked-files=normal"]:
                return 0, self.checkouts[path]["status"], ""
            case ["git", "-C", path, "rev-list", "--count", revision] if revision == f"{BASE}..HEAD":
                return 0, f"{self.checkouts[path]['ahead']}\n", ""
            case ["git", "cat-file", "-e", spec]:
                return (0 if spec.removesuffix("^{commit}") in self.objects else 1), "", ""
            case ["git", "fetch", "--quiet", "--no-tags", "origin", ref] if ref.startswith("refs/pull/"):
                number = ref.split("/")[2]
                self.objects.update(row["headRefOid"] for row in self.lists["open"] if str(row["number"]) == number)
                return 0, "", ""
            case ["git", "show", "-s", "--format=%cI", _]:
                return 0, "2026-01-01T10:00:00+00:00\n", ""
            case [
                "git",
                "log",
                "--first-parent",
                "--diff-merges=first-parent",
                "--since-as-filter=2026-01-01T10:00:00+00:00",
                "--format=",
                "--name-only",
                "--no-renames",
                span,
            ]:
                head, base = span.split("..")
                assert base == BASE
                return 0, "\n\n".join(self.moved[head]) + "\n", ""
            case ["git", "diff", "--no-renames", "--name-only", span]:
                base, head = span.split("...")
                assert base == BASE
                return 0, "\n".join(self.files[head]) + "\n", ""
            case ["gh", "pr", "checks", number, "--repo", "github.com/acme/demo", "--json", "name,bucket"]:
                return self.check_answer(self.checks[number])
            case [
                "gh",
                "pr",
                "checks",
                number,
                "--repo",
                "github.com/acme/demo",
                "--json",
                "name,bucket",
                "--required",
            ]:
                return self.check_answer(self.required[number])
            case ["gh", "api", "graphql", "--hostname", "github.com", *fields]:
                assert "owner=acme" in fields and "name=demo" in fields
                assert not any("mutation" in field for field in fields)
                number = next(field.removeprefix("number=") for field in fields if field.startswith("number="))
                page = self.reviews[number]
                return (1, "", "graphql failed") if page is None else (0, json.dumps(page), "")
            case ["git", "merge-base", base, _] if base == BASE:
                return 0, oid("0") + "\n", ""
            case [_, script, "--merge-base", _, "--head", head, "--policy-rev", base] if (
                script.endswith("risk-signals.py") and base == BASE
            ):
                report = self.risk[head]
                return (1, "", "git diff failed") if report is None else (0, json.dumps(report), "")
            case [
                "gh",
                "api",
                "--hostname",
                "github.com",
                "--method",
                "PUT",
                endpoint,
                "-f",
                head,
                "-f",
                "merge_method=squash",
            ]:
                pr = next(row for row in self.lists["open"] if endpoint == f"repos/{REPO}/pulls/{row['number']}/merge")
                assert head == f"sha={pr['headRefOid']}"
                if self.merge_exit == 0:
                    return 0, json.dumps({"merged": self.merge_lands}), ""
                return self.merge_exit, "", "HTTP 405: Required status check is expected"
        return 97, "", "unexpected command: " + " ".join(argv)


class ShowtimeCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.state = self.root / "state"
        self.host = FakeHost(self.root)
        # The shared git and gh helpers call the shared runner, so the host answers there too.
        for module in (showtime, showtime.reads, showtime.reads.review_process):
            patcher = mock.patch.object(module, "run", self.host)
            patcher.start()
            self.addCleanup(patcher.stop)

    def invoke(self, *argv: str) -> tuple[int, Json]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = showtime.main(list(argv))
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 1, "the helper prints exactly one line")
        return code, json.loads(lines[0])

    def board(self, *extra: str) -> Json:
        code, document = self.invoke(
            "board", "--conductor", self.host.conductor_file(), "--state-dir", str(self.state), *extra
        )
        self.assertEqual((code, document["status"]), (0, "ok"), document)
        return document

    def row(self, board: Json, name: str) -> Json:
        return next(row for row in board["workspaces"] if row["name"] == name)

    def merge(self, number: int, head: str, *extra: str) -> tuple[int, Json]:
        return self.invoke(
            "merge",
            "--conductor",
            self.host.conductor_file(),
            "--pr",
            str(number),
            "--head",
            head,
            "--state-dir",
            str(self.state),
            *extra,
        )

    def merges(self) -> list[list[str]]:
        return [call for call in self.host.calls if call[:2] == ["gh", "api"] and "PUT" in call]


class BoardTests(ShowtimeCase):
    def test_each_workspace_lands_on_one_stage_with_its_move(self) -> None:
        host = self.host
        host.workspace("oslo", chat="running")
        host.workspace("cairo", oid("b"), agent="codex", ahead=3)
        host.workspace("hanoi", oid("c"))
        host.pull_request(11, "me/hanoi", oid("c"), checks=[{"name": "test", "bucket": "fail"}])
        host.workspace("perth", oid("d"))
        host.pull_request(12, "me/perth", oid("d"))
        host.workspace("dublin", oid("e"))
        host.lists["merged"].append(
            {
                "number": 9,
                "url": "u9",
                "state": "MERGED",
                "headRefOid": oid("e"),
                "headRefName": "me/dublin",
                "headRepository": {"nameWithOwner": REPO},
            }
        )
        board = self.board()

        stages = {row["name"]: (row["stage"], row["group"]) for row in board["workspaces"]}
        self.assertEqual(
            stages,
            {
                "oslo": ("working", "working"),
                "cairo": ("work_done_no_pr", "nudge"),
                "hanoi": ("pr_not_in_shape", "nudge"),
                "perth": ("merge_ready", "merge_ready"),
                "dublin": ("merged", "merged"),
            },
        )
        cairo, hanoi = self.row(board, "cairo")["move"], self.row(board, "hanoi")["move"]
        self.assertEqual((cairo["message"], cairo["session_id"]), ("$trackbed:pr:create --showtime", "chat-cairo"))
        self.assertEqual(hanoi["message"], "/trackbed:pr-shape-up")
        self.assertNotEqual(cairo["message_id"], hanoi["message_id"])
        self.assertEqual(self.row(board, "dublin")["move"], {"kind": "archive"})
        self.assertEqual([entry["number"] for entry in board["train"]], [12])
        self.assertEqual(board["train"][0]["workspace_id"], "ws-perth")
        self.assertEqual(self.row(board, "hanoi")["label"], "PR not in shape")

    def test_the_board_names_the_repository_and_its_merge_method(self) -> None:
        self.host.workspace("perth")
        self.host.pull_request(12, "me/perth")
        expected = {
            "name_with_owner": REPO,
            "host": "github.com",
            "selector": ORIGIN,
            "default_branch": "main",
            "merge_method": "squash",
            "required_checks": [],
        }
        self.assertEqual(self.board()["repository"], expected)
        self.host.repo |= {"squashMergeAllowed": False, "mergeCommitAllowed": False}
        board = self.board()
        self.assertEqual((board["repository"]["merge_method"], board["train"]), (None, []))
        self.assertIn("The repository allows no merge method, so nothing can merge.", board["notes"])

    def test_board_only_reads_and_names_the_repository_on_every_gh_pr_call(self) -> None:
        self.host.workspace("perth")
        self.host.pull_request(12, "me/perth")
        self.board()
        for call in self.host.calls:
            if call[:2] == ["gh", "pr"]:
                self.assertEqual(
                    call[3 if call[2] == "list" else 4 : 5 if call[2] == "list" else 6], ["--repo", ORIGIN], call
                )
                self.assertIn(call[2], ("list", "checks"), call)
            self.assertFalse({"push", "commit", "merge", "rebase", "reset", "checkout", "--admin"} & set(call), call)

    def test_its_own_workspace_and_pull_request_are_left_out(self) -> None:
        self.host.workspace("regina")
        self.host.workspaces[-1]["id"] = SELF_ID
        self.host.pull_request(30, "me/regina")
        board = self.board()
        self.assertFalse([call for call in self.host.calls if call[:3] == ["git", "-C", str(self.root / "regina")]])
        self.assertEqual((board["workspaces"], board["orphans"], board["train"]), ([], [], []))
        self.assertEqual(board["notes"], ["Pull Request #30 belongs to this workspace and is left out."])

    def test_a_pull_request_without_a_workspace_can_join_the_train_but_is_never_nudged(self) -> None:
        self.host.pull_request(21, "me/gone", oid("b"))
        self.host.objects.discard(oid("b"))
        self.host.pull_request(22, "me/red", oid("c"), checks=[{"name": "test", "bucket": "fail"}])
        board = self.board()
        self.assertEqual(
            [(row["pr"]["number"], row["stage"]) for row in board["orphans"]],
            [(21, "merge_ready"), (22, "orphan_blocked")],
        )
        self.assertEqual(board["train"], [board["train"][0]])
        self.assertEqual((board["train"][0]["number"], board["train"][0]["workspace_id"]), (21, None))
        self.assertIn(["git", "fetch", "--quiet", "--no-tags", "origin", "refs/pull/21/head"], self.host.calls)

    def test_hold_rules_keep_a_green_pull_request_off_the_train(self) -> None:
        host = self.host
        for name, number, letter, change in (
            ("breaking", 1, "b", {"title": "fix(codex)!: drop the old installer"}),
            ("risky", 2, "c", {"risk": {"floor": "high", "signals": [{"id": "path:ci", "level": "high"}]}}),
            ("unknown", 3, "d", {"risk": None}),
            ("asked", 4, "e", {"reviews": review_page(decision="CHANGES_REQUESTED")}),
        ):
            host.workspace(name, oid(letter))
            host.pull_request(number, f"me/{name}", oid(letter), **change)
        board = self.board()
        self.assertEqual(board["train"], [])
        self.assertEqual(sorted(entry["number"] for entry in board["held"]), [1, 2, 3, 4])
        holds = {row["name"]: row["holds"][0] for row in board["workspaces"]}
        self.assertIn("breaking change", holds["breaking"])
        self.assertIn("`path:ci`", holds["risky"])
        self.assertIn("could not be computed (git diff failed)", holds["unknown"])
        self.assertIn("requested changes", holds["asked"])

    def test_the_risk_floor_is_read_only_for_a_pull_request_with_no_blocker(self) -> None:
        self.host.workspace("hanoi")
        self.host.pull_request(11, "me/hanoi", draft=True)
        self.board()
        self.assertFalse([call for call in self.host.calls if len(call) > 1 and call[1].endswith("risk-signals.py")])

    def test_checks_go_stale_when_a_later_merge_touches_the_same_or_a_shared_file(self) -> None:
        host = self.host
        host.workspace("same", oid("b"))
        host.pull_request(1, "me/same", oid("b"), files=["src/a.py"], moved=["src/a.py", "docs/x.md"])
        host.workspace("shared", oid("c"))
        host.pull_request(2, "me/shared", oid("c"), files=["src/b.py"], moved=["trackbed/Makefile"])
        host.workspace("apart", oid("d"))
        host.pull_request(3, "me/apart", oid("d"), files=["src/c.py"], moved=["docs/x.md"])
        board = self.board()
        self.assertEqual(self.row(board, "same")["stage"], "pr_not_in_shape")
        self.assertIn("`src/a.py` changed on `main` since its head commit", self.row(board, "same")["reasons"][0])
        self.assertIn("`trackbed/Makefile`", self.row(board, "shared")["reasons"][0])
        self.assertEqual(self.row(board, "apart")["stage"], "merge_ready")

    def test_required_checks_gate_and_other_failures_are_only_noted(self) -> None:
        host = self.host
        host.workspace("perth")
        checks = [{"name": "test", "bucket": "pass"}, {"name": "scan", "bucket": "fail"}]
        host.pull_request(12, "me/perth", checks=checks, required=[checks[0]])
        host.workspace("lima", oid("b"))
        host.pull_request(13, "me/lima", oid("b"), checks=checks, required=[])
        host.workspace("quito", oid("c"))
        host.pull_request(14, "me/quito", oid("c"), checks=[], required=[])
        host.workspace("turin", oid("d"))
        host.pull_request(15, "me/turin", oid("d"), checks=[{"name": "new", "bucket": "mystery"}])
        board = self.board()
        self.assertEqual(self.row(board, "perth")["stage"], "merge_ready")
        self.assertIn("#12: checks that are not required are failing: `scan`.", board["notes"])
        self.assertEqual(self.row(board, "lima")["stage"], "pr_not_in_shape")
        self.assertEqual(self.row(board, "quito")["stage"], "no_checks")
        self.assertEqual(self.row(board, "turin")["stage"], "checks_running")

    def test_a_required_check_that_has_not_reported_is_pending(self) -> None:
        self.host.rules = [
            {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "build"}]}}
        ]
        self.host.protection = {"contexts": ["lint"], "checks": [{"context": "lint", "app_id": 1}]}
        self.host.workspace("perth")
        self.host.pull_request(12, "me/perth", required=[])
        board = self.board()
        self.assertEqual(board["repository"]["required_checks"], ["build", "lint"])
        self.assertEqual(self.row(board, "perth")["stage"], "checks_running")
        self.assertIn("`build`, `lint`", self.row(board, "perth")["reasons"][0])
        self.host.checks["12"] = [
            {"name": "test", "bucket": "fail"},
            {"name": "build", "bucket": "pass"},
            {"name": "lint", "bucket": "pass"},
        ]
        board = self.board()
        self.assertEqual(self.row(board, "perth")["stage"], "merge_ready")
        self.assertIn("#12: checks that are not required are failing: `test`.", board["notes"])

    def test_the_train_orders_by_shared_files_then_age(self) -> None:
        for name, number, letter, files in (
            ("a", 5, "b", ["x.py", "y.py"]),
            ("b", 3, "c", ["x.py"]),
            ("c", 8, "d", ["z.py"]),
        ):
            self.host.workspace(name, oid(letter))
            self.host.pull_request(number, f"me/{name}", oid(letter), files=files)
        train = self.board()["train"]
        self.assertEqual([(entry["number"], entry["shared_with"]) for entry in train], [(8, []), (3, [5]), (5, [3])])

    def test_a_pull_request_that_cannot_be_read_blocks_only_its_own_workspace(self) -> None:
        self.host.workspace("hanoi")
        self.host.pull_request(11, "me/hanoi", reviews=None)
        self.host.workspace("perth", oid("b"))
        self.host.pull_request(12, "me/perth", oid("b"))
        board = self.board()
        self.assertEqual((self.row(board, "hanoi")["stage"], self.row(board, "hanoi")["move"]), ("unreadable_pr", None))
        self.assertIn("graphql failed", self.row(board, "hanoi")["reasons"][0])
        self.assertEqual([entry["number"] for entry in board["train"]], [12])

    def test_commands_are_counted_across_passes_and_stop_after_two(self) -> None:
        self.host.workspace("cairo", ahead=2)
        passes = []
        for _ in range(3):
            row = self.row(self.board("--idle-minutes", "0"), "cairo")
            passes.append(row)
            if row["move"]:
                for _ in range(2):
                    self.assertEqual(
                        self.invoke(
                            "record-nudge", "--message-id", row["move"]["message_id"], "--state-dir", str(self.state)
                        )[0],
                        0,
                    )
        self.assertEqual([row["stage"] for row in passes], ["work_done_no_pr", "work_done_no_pr", "nudge_limit"])
        self.assertIsNone(passes[2]["move"])
        self.host.checkouts[self.host.workspaces[0]["path"]]["ahead"] = 0
        self.assertEqual(self.row(self.board("--idle-minutes", "0"), "cairo")["stage"], "empty")
        self.assertEqual(json.loads((self.state / "state.json").read_text())["nudges"], {})

    def test_the_count_survives_the_stages_a_delivered_command_leads_to(self) -> None:
        self.host.workspace("cairo", ahead=2)
        chat = self.host.sessions[0]

        def deliver() -> Json:
            move = self.row(self.board("--idle-minutes", "0"), "cairo")["move"]
            self.assertEqual(move["kind"], "send")
            self.invoke("record-nudge", "--message-id", move["message_id"], "--state-dir", str(self.state))
            return move

        self.assertEqual(deliver()["nudge"]["count"], 1)
        for state, expected in (("running", "working"), ("waiting_for_user", "waiting"), ("error", "chat_error")):
            with mock.patch.dict(chat, {"state": state}):
                self.assertEqual(self.row(self.board("--idle-minutes", "0"), "cairo")["stage"], expected)
            self.assertIn("ws-cairo", json.loads((self.state / "state.json").read_text())["nudges"])
        self.assertEqual(deliver()["nudge"]["count"], 2)
        self.assertEqual(self.row(self.board("--idle-minutes", "0"), "cairo")["stage"], "nudge_limit")

    def test_the_shape_up_count_survives_running_checks_and_a_failed_read(self) -> None:
        self.host.workspace("hanoi")
        self.host.pull_request(11, "me/hanoi", checks=[{"name": "test", "bucket": "fail"}])

        def deliver() -> Json:
            move = self.row(self.board("--idle-minutes", "0"), "hanoi")["move"]
            self.invoke("record-nudge", "--message-id", move["message_id"], "--state-dir", str(self.state))
            return move

        self.assertEqual(deliver()["nudge"]["count"], 1)
        self.host.checks["11"] = self.host.required["11"] = [{"name": "test", "bucket": "pending"}]
        self.assertEqual(self.row(self.board("--idle-minutes", "0"), "hanoi")["stage"], "checks_running")
        with mock.patch.dict(self.host.reviews, {"11": None}):
            self.assertEqual(self.row(self.board("--idle-minutes", "0"), "hanoi")["stage"], "unreadable_pr")
        self.host.checks["11"] = self.host.required["11"] = [{"name": "test", "bucket": "fail"}]
        self.assertEqual(deliver()["nudge"]["count"], 2)

    def test_a_past_pull_request_on_the_branch_stops_the_create_command(self) -> None:
        def past(number: int, branch: str, head: str, state: str = "MERGED") -> Json:
            return {
                "number": number,
                "url": f"u{number}",
                "state": state,
                "headRefOid": head,
                "headRefName": branch,
                "headRepository": {"nameWithOwner": REPO},
            }

        self.host.workspace("lagos", oid("b"), ahead=2)
        self.host.lists["merged"].append(past(9, "me/lagos", oid("c")))
        self.host.workspace("accra", oid("d"), ahead=2)
        self.host.older.append(past(4, "me/accra", oid("d")))
        self.host.workspace("tunis", oid("e"), ahead=2, contains=[oid("6")])
        self.host.older.append(past(6, "me/tunis", oid("6")))
        board = self.board("--idle-minutes", "0")
        lagos = self.row(board, "lagos")
        self.assertEqual((lagos["stage"], lagos["move"]), ("past_pr_elsewhere", None))
        self.assertIn("#9 on this branch was merged", lagos["reasons"][0])
        accra = self.row(board, "accra")
        self.assertEqual((accra["stage"], accra["move"]), ("merged", {"kind": "archive"}))
        self.assertEqual(self.row(board, "tunis")["stage"], "work_done_no_pr")

    def test_github_merge_state_decides_the_gate_too(self) -> None:
        self.host.workspace("perth")
        self.host.pull_request(12, "me/perth", merge_state="BEHIND")
        self.host.workspace("lima", oid("b"))
        self.host.pull_request(13, "me/lima", oid("b"), merge_state="BLOCKED")
        self.host.workspace("quito", oid("c"))
        self.host.pull_request(14, "me/quito", oid("c"), reviews=review_page(decision="REVIEW_REQUIRED"))
        board = self.board()
        stages = {name: self.row(board, name)["stage"] for name in ("perth", "lima", "quito")}
        self.assertEqual(stages, {"perth": "pr_not_in_shape", "lima": "protected", "quito": "review_required"})
        self.assertEqual(board["train"], [])

    def test_a_board_rebuilt_within_the_idle_window_does_not_count_twice(self) -> None:
        self.host.workspace("cairo", ahead=2)
        message_ids = set()
        for _ in range(4):
            move = self.row(self.board(), "cairo")["move"]
            self.assertEqual(move["kind"], "send")
            message_ids.add(move["message_id"])
        self.assertEqual(len(message_ids), 1)
        self.assertEqual(json.loads((self.state / "state.json").read_text())["nudges"], {})

    def test_a_second_pr_on_a_live_branch_cannot_make_the_first_an_orphan(self) -> None:
        self.host.workspace("perth", chat="running")
        self.host.pull_request(12, "me/perth")
        self.host.pull_request(13, "me/perth", base="staging")
        board = self.board()
        self.assertEqual(self.row(board, "perth")["pr"]["number"], 12)
        self.assertEqual((board["orphans"], board["train"]), ([], []))

    def test_the_archive_plan_matches_repository_branch_and_head(self) -> None:
        ws = self.host.workspace("perth")
        self.host.workspace("dublin")
        self.host.lists["merged"].append(
            {
                "number": 9,
                "url": "u9",
                "state": "MERGED",
                "headRefOid": oid("a"),
                "headRefName": "me/perth",
                "headRepository": {"nameWithOwner": REPO},
            }
        )
        board = self.board()
        self.assertEqual(self.row(board, "perth")["move"], {"kind": "archive"})
        self.assertEqual(self.row(board, "dublin")["move"]["kind"], "send")

        def check() -> tuple[int, Json]:
            return self.invoke(
                "archive-check",
                "--workspace",
                ws,
                "--conductor",
                self.host.conductor_file(),
                "--state-dir",
                str(self.state),
            )

        self.assertEqual(check()[0], 0)
        checkout = self.host.checkouts[self.host.workspaces[0]["path"]]
        for changed in ({"status": " M work.py"}, {"head": oid("b")}, {"branch": "other"}):
            with mock.patch.dict(checkout, changed):
                self.assertEqual(check()[0], 1)

        def refusal(workspace: str = ws) -> str:
            code, document = self.invoke(
                "archive-check",
                "--workspace",
                workspace,
                "--conductor",
                self.host.conductor_file(),
                "--state-dir",
                str(self.state),
            )
            self.assertEqual((code, document["status"]), (1, "error"))
            return str(document["message"])

        self.assertIn("does not clear this workspace", refusal("ws-dublin"))
        with mock.patch.dict(self.host.sessions[0], {"state": "running"}):
            self.assertIn("no longer idle", refusal())
        with mock.patch.dict(self.host.workspaces[0], {"state": "archived"}):
            self.assertIn("no longer available", refusal())
        with mock.patch.object(showtime.time, "time", return_value=showtime.time.time() + 901):
            self.assertIn("older than fifteen minutes", refusal())

    def test_changes_compare_with_the_saved_board(self) -> None:
        self.host.workspace("hanoi")
        self.host.pull_request(11, "me/hanoi", checks=[{"name": "test", "bucket": "pending"}])
        self.assertEqual(self.board()["changes"], ["First pass: there is no earlier board to compare with."])
        self.host.checks["11"] = self.host.required["11"] = [{"name": "test", "bucket": "pass"}]
        self.host.workspace("oslo", oid("b"), chat="running")
        self.assertEqual(
            self.board()["changes"], ["`hanoi`: Checks running → Merge-ready", "`oslo` is new: Agent working"]
        )
        self.host.workspaces.pop()
        self.assertEqual(self.board()["changes"], ["`oslo` is no longer listed (archived or removed)"])

    def test_a_dry_run_saves_nothing(self) -> None:
        self.host.workspace("cairo", ahead=2)
        board = self.board("--dry-run")
        self.assertTrue(board["dry_run"])
        self.assertFalse(self.state.exists())

    def test_the_sidebar_plan_needs_the_sections_list(self) -> None:
        self.host.workspace("oslo", chat="running")
        plan = self.board()["sections"]
        self.assertEqual([entry["name"] for entry in plan["create"]], ["Working"])
        self.assertEqual(plan["moves"][0]["workspace_ids"], ["ws-oslo"])
        self.host.sections = None
        self.assertIsNone(self.board()["sections"])

    def test_two_workspaces_on_one_issue_are_noted(self) -> None:
        self.host.workspace("lyon", branch="me/skills-147-first")
        self.host.workspace("dakar", oid("b"), branch="me/skills-147-again")
        self.assertIn("2 workspaces work on SKILLS-147: `dakar`, `lyon`.", self.board()["notes"])

    def test_failures_that_stop_the_board_are_reported_as_errors(self) -> None:
        self.host.fetch_exit = 1
        code, document = self.invoke("board", "--conductor", self.host.conductor_file(), "--state-dir", str(self.state))
        self.assertEqual((code, document["status"]), (1, "error"))
        self.assertIn("could not fetch `main` from origin", document["message"])
        bad = self.root / "bad.json"
        for content, expected in (
            ("[]", "as a JSON object"),
            ('{"workspaces": [{"id": "w"}], "sessions": []}', "has no `name`"),
            ('{"workspaces": [], "sessions": "none"}', "`sessions` in the Conductor file must be a list"),
        ):
            bad.write_text(content, encoding="utf-8")
            code, document = self.invoke("board", "--conductor", str(bad), "--state-dir", str(self.state))
            self.assertEqual(code, 1)
            self.assertIn(expected, document["message"])


class MergeTests(ShowtimeCase):
    def ready(self, **change: Any) -> Json:
        self.host.workspace("perth")
        self.host.pull_request(12, "me/perth", **change)
        return self.board()

    def test_merges_a_cleared_pull_request_pinned_to_its_head(self) -> None:
        self.ready()
        code, document = self.merge(12, oid("a"))
        self.assertEqual(
            (code, document["status"], document["outcome"], document["method"]), (0, "ok", "merged", "squash")
        )
        self.assertEqual(
            self.merges(),
            [
                [
                    "gh",
                    "api",
                    "--hostname",
                    "github.com",
                    "--method",
                    "PUT",
                    f"repos/{REPO}/pulls/12/merge",
                    "-f",
                    f"sha={oid('a')}",
                    "-f",
                    "merge_method=squash",
                ]
            ],
        )
        self.assertEqual(json.loads((self.state / "board.json").read_text())["train"], [])
        code, document = self.merge(12, oid("a"))
        self.assertEqual((code, document["status"]), (1, "refused"))

    def test_refuses_what_the_saved_board_did_not_clear(self) -> None:
        code, document = self.merge(12, oid("a"))
        self.assertEqual((code, document["status"]), (1, "refused"))
        self.assertIn("no saved board", document["message"])
        self.ready()
        for number, head, expected in ((13, oid("a"), "does not clear"), (12, oid("b"), "does not clear")):
            code, document = self.merge(number, head)
            self.assertEqual((code, document["status"]), (1, "refused"))
            self.assertIn(expected, document["message"])
        with mock.patch.object(showtime.time, "time", return_value=showtime.time.time() + 901):
            code, document = self.merge(12, oid("a"))
        self.assertIn("older than fifteen minutes", document["message"])
        self.assertFalse(self.merges())

    def test_refuses_when_the_pull_request_changed_after_the_board(self) -> None:
        self.ready()
        pr = self.host.lists["open"][0]
        for change, expected in (
            ({"isDraft": True}, "it is a draft"),
            ({"baseRefName": "staging"}, "showtime does not merge stacked"),
            ({"mergeable": "CONFLICTING"}, "conflicts"),
        ):
            with mock.patch.dict(pr, change):
                code, document = self.merge(12, oid("a"))
            self.assertEqual((code, document["status"]), (1, "refused"), change)
            self.assertIn(expected, document["message"])
        self.host.lists["open"].clear()
        self.assertIn("no longer open at the approved head", self.merge(12, oid("a"))[1]["message"])
        self.assertFalse(self.merges())

    def test_merging_rechecks_feedback_workspace_and_base(self) -> None:
        self.ready()
        with mock.patch.dict(self.host.reviews, {"12": review_page(decision="CHANGES_REQUESTED")}):
            self.assertIn("requested changes", self.merge(12, oid("a"))[1]["message"])
        with mock.patch.dict(self.host.sessions[0], {"state": "running"}):
            self.assertIn("chat is running", self.merge(12, oid("a"))[1]["message"])
        self.host.remote_base = oid("e")
        self.assertIn("default branch moved", self.merge(12, oid("a"))[1]["message"])
        self.assertFalse(self.merges())

    def test_a_local_edit_during_merge_verification_blocks_the_write(self) -> None:
        self.ready()
        checkout = self.host.checkouts[self.host.workspaces[0]["path"]]

        def edit_when_reading_base(argv: Sequence[str], timeout: float, input: bytes | None = None) -> Any:
            result = self.host(argv, timeout, input)
            if list(argv[:2]) == ["git", "ls-remote"]:
                checkout["status"] = "?? local.txt"
            return result

        with mock.patch.object(showtime.reads.review_process, "run", edit_when_reading_base):
            self.assertIn("checkout changed during verification", self.merge(12, oid("a"))[1]["message"])
        self.assertFalse(self.merges())

    def test_a_held_pull_request_merges_only_with_the_explicit_flag(self) -> None:
        board = self.ready(title="feat!: drop the v1 API")
        self.assertEqual(([entry["number"] for entry in board["held"]], board["train"]), ([12], []))
        code, document = self.merge(12, oid("a"))
        self.assertEqual((code, document["status"]), (1, "refused"))
        code, document = self.merge(12, oid("a"), "--allow-held")
        self.assertEqual((code, document["outcome"]), (0, "merged"))

    def test_a_held_pull_request_whose_holds_changed_is_refused(self) -> None:
        self.ready(title="feat!: drop the v1 API")
        with mock.patch.dict(self.host.reviews, {"12": review_page(decision="CHANGES_REQUESTED")}):
            code, document = self.merge(12, oid("a"), "--allow-held")
        self.assertEqual((code, document["status"]), (1, "refused"))
        self.assertIn("hold reasons changed", document["message"])
        self.assertFalse(self.merges())

    def test_a_dry_run_board_clears_nothing(self) -> None:
        self.host.workspace("perth")
        self.host.pull_request(12, "me/perth")
        self.board("--dry-run")
        self.assertEqual(self.merge(12, oid("a"))[1]["status"], "refused")

    def test_reports_failure_when_github_does_not_confirm_a_synchronous_merge(self) -> None:
        self.ready()
        self.host.merge_exit = 1
        code, document = self.merge(12, oid("a"))
        self.assertEqual((code, document["status"]), (1, "failed"))
        self.assertIn("Required status check is expected", document["message"])
        self.host.merge_exit, self.host.merge_lands = 0, False
        code, document = self.merge(12, oid("a"))
        self.assertEqual((code, document["status"]), (1, "failed"))


class GitHistoryTests(unittest.TestCase):
    def test_later_merge_counts_earlier_topic_commits_that_changed_shared_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)

            def git(*args: str, day: int = 1) -> str:
                date = f"2026-01-0{day}T12:00:00Z"
                env = os.environ | {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
                return subprocess.run(
                    ["git", "-c", "core.hooksPath=/dev/null", "-C", temporary, *args],
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout

            git("init", "-b", "main")
            git("config", "user.email", "fixture@example.com")
            git("config", "user.name", "Fixture")
            git("commit", "--allow-empty", "-m", "Base")
            git("switch", "-c", "older-topic")
            (path / "Makefile").write_text("older topic\n", encoding="utf-8")
            git("add", "Makefile")
            git("commit", "-m", "Shared build change", day=2)
            git("switch", "-c", "candidate", "main")
            git("commit", "--allow-empty", "-m", "Candidate", day=3)
            git("switch", "main")
            git("merge", "--no-ff", "-m", "Land older topic", "older-topic", day=4)
            with mock.patch.object(showtime.reads, "git", git):
                _, stale = showtime.reads.stale_facts({"head_oid": "candidate"}, "main")
            self.assertEqual((stale["stale"], stale["shared"]), (True, ["Makefile"]))


class MergeArgumentsTests(ShowtimeCase):
    def test_rejects_a_head_that_is_not_a_full_commit_id(self) -> None:
        code, document = self.merge(12, "abc123")
        self.assertEqual((code, document["status"]), (1, "error"))


class ReplyTests(ShowtimeCase):
    def reply(self, text: str) -> tuple[int, Json]:
        path = self.root / "tail.txt"
        path.write_text(text, encoding="utf-8")
        return self.invoke("reply", "--message-file", str(path))

    def test_reads_the_message_from_a_file_and_runs_nothing(self) -> None:
        text = "Decision needed · PR #4: rebase now?\n\n1. Rebase (recommended): rebases $(touch /tmp/x).\n2. Skip.\n"
        code, document = self.reply(text)
        self.assertEqual((code, document["kind"], document["reply"]), (0, "decision", "Option 1: Rebase"))
        self.assertEqual(self.host.calls, [])
        self.assertEqual(self.reply("All done.")[1]["kind"], "none")

    def test_a_missing_or_huge_file_is_an_error(self) -> None:
        code, document = self.invoke("reply", "--message-file", str(self.root / "absent.txt"))
        self.assertEqual((code, document["status"]), (1, "error"))
        code, document = self.reply("x" * (showtime.MAX_MESSAGE_BYTES + 1))
        self.assertIn("larger than", document["message"])


if __name__ == "__main__":
    unittest.main()
