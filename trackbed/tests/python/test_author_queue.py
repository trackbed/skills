"""Behavioral tests for the author view of the review queue.

Every `gh` and `git` call the helper makes is answered by an in-memory host from recorded GitHub responses, so no
test needs a network or a GitHub account. Worktree paths are real temporary directories, because the helper checks
that they exist. The host refuses any command it does not know, which keeps the helper's read-only promise under test.
"""

from __future__ import annotations

import copy
import io
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from collections.abc import Callable, Sequence
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

if __package__:
    from .script_loader import load_script
else:
    from script_loader import load_script

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "skills" / "pr:review-queue" / "scripts" / "author-queue.py"
author_queue = load_script("author_queue", SCRIPT_PATH)

ME = "ana-author"
REPO = "acme/widgets"
HEAD = "1" * 40
OTHER_HEAD = "2" * 40

Json = dict[str, Any]


def check(name: str, conclusion: str | None, run: int = 7001, status: str = "COMPLETED") -> Json:
    return {
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "checkSuite": {"workflowRun": {"databaseId": run}},
    }


def comment(login: str | None, at: str, kind: str = "User") -> Json:
    return {
        "createdAt": at,
        "isMinimized": False,
        "author": None if login is None else {"login": login, "__typename": kind},
    }


def thread(*comments: Json, resolved: bool = False) -> Json:
    return {"isResolved": resolved, "comments": {"nodes": list(comments)}}


def bot_thread(*replies: Json) -> Json:
    return thread(comment("coderabbitai", "2026-04-01T10:00:00Z", "Bot"), *replies)


def human_thread(*replies: Json) -> Json:
    return thread(comment("riley-reviewer", "2026-04-01T10:00:00Z"), *replies)


def pr_node(number: int, **fields: Any) -> Json:
    """A recorded GraphQL Pull Request: open, mergeable, approved, and green, unless fields say otherwise."""
    node: Json = {
        "number": number,
        "title": f"WID-{number}: Change {number}",
        "url": f"https://github.com/{REPO}/pull/{number}",
        "isDraft": False,
        "state": "OPEN",
        "baseRefName": "main",
        "headRefName": f"ana/wid-{number}",
        "headRefOid": HEAD,
        "isCrossRepository": False,
        "author": {"login": ME},
        "baseRef": {"associatedPullRequests": {"nodes": []}},
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "reviewDecision": "APPROVED",
        "reviewThreads": {"pageInfo": {"hasNextPage": False}, "nodes": []},
        "commits": {"nodes": [{"commit": {"statusCheckRollup": None}}]},
    }
    checks = fields.pop("checks", [check("test", "SUCCESS")])
    threads = fields.pop("threads", [])
    node.update(fields)
    set_checks(node, checks)
    node["reviewThreads"]["nodes"] = threads
    return node


def set_checks(node: Json, checks: list[Json], total: int | None = None) -> None:
    results = [c.get("conclusion") or c.get("state") for c in checks]
    if any(r in ("FAILURE", "CANCELLED", "ERROR") for r in results):
        state = "FAILURE"
    elif any(c.get("status", "COMPLETED") != "COMPLETED" for c in checks):
        state = "PENDING"
    else:
        state = "SUCCESS"
    contexts = {"totalCount": len(checks) if total is None else total, "nodes": checks}
    node["commits"]["nodes"][0]["commit"]["statusCheckRollup"] = (
        {"state": state, "contexts": contexts} if checks else None
    )


class FakeHost:
    """Answers the helper's commands from recorded GitHub responses and local worktrees, and records each call."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.repo: str | None = REPO
        self.prs: dict[tuple[str, int], list[Json]] = {}
        self.closed: list[Json] = []
        self.runs: dict[str, list[Json]] = {}
        self.worktrees: list[tuple[str, str | None, list[str]]] = []
        self.dirty: dict[str, str] = {}
        self.heads: dict[str, str] = {}
        # Paths whose index entry is hidden from git status: the ls-files tag and whether the file has changes.
        self.hidden: dict[str, tuple[str, bool]] = {}
        self.protected: list[str] | None = ["main", "master", "develop"]
        self.stacks: dict[str, str] = {}
        self.user_error = ""
        self.listing_exit = 0
        self.graphql_exit = 0
        self.read_counts: dict[int, int] = {}
        self.read_requests = 0
        self.omitted: set[int] = set()
        # Local commands that fail, each named by a fragment of its command line.
        self.failing: set[str] = set()
        self.calls: list[list[str]] = []
        self.refused: list[list[str]] = []

    def add(self, node: Json, *later: Json, repo: str = REPO) -> None:
        """Serve node for the first read of the Pull Request and each later node for one re-read."""
        node["url"] = f"https://github.com/{repo}/pull/{node['number']}"
        self.prs[(repo, node["number"])] = [node, *later]

    def checkout(self, branch: str | None, *flags: str, head: str = HEAD, name: str | None = None) -> str:
        """A worktree directory that has branch checked out at head."""
        path = self.root / (name or (branch or "detached").replace("/", "-"))
        (path / ".git-dir").mkdir(parents=True, exist_ok=True)
        self.worktrees.append((str(path), branch, list(flags)))
        self.heads[str(path)] = head
        return str(path)

    def __call__(
        self, argv: Sequence[str], timeout: float, input: bytes | None = None
    ) -> subprocess.CompletedProcess[bytes]:
        command = list(argv)
        self.calls.append(command)
        code, out, err = self.answer(command)
        if code == 0 and any(part in " ".join(command) for part in self.failing):
            code, out, err = 128, "", "fatal: cannot read the worktree"
        if code == 97:
            self.refused.append(command)
        return subprocess.CompletedProcess(command, code, out.encode(), err.encode())

    def answer(self, argv: list[str]) -> tuple[int, str, str]:
        match argv:
            case ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]:
                return (0, self.repo + "\n", "") if self.repo else (1, "", "not a git repository")
            case ["gh", "api", "user"]:
                return (1, "", self.user_error) if self.user_error else (0, json.dumps({"login": ME}), "")
            case ["gh", "api", "graphql", "-f", query, *fields]:
                assert query.startswith("query=") and "mutation" not in query
                values = dict(field.split("=", 1) for field in fields[1::2])
                if self.graphql_exit:
                    return self.graphql_exit, "", "HTTP 502"
                if "q" in values:
                    return 0, json.dumps(self.search(values["q"])), ""
                if error := self.invalid_read(query, fields):
                    return 1, "", error
                return 0, json.dumps(self.read(query, values)), ""
            case ["gh", "api", endpoint] if endpoint.startswith("repos/") and "/actions/runs?head_sha=" in endpoint:
                sha = endpoint.split("head_sha=", 1)[1].split("&", 1)[0]
                if sha not in self.runs:
                    return 1, "", "Not Found (HTTP 404)"
                return 0, json.dumps({"workflow_runs": self.runs[sha]}), ""
            case ["git", "worktree", "list", "--porcelain", "-z"]:
                return (
                    (self.listing_exit, "", "fatal: not a git repository")
                    if self.listing_exit
                    else (0, self.listing(), "")
                )
            case [script, "--branch-roles", "--protect-develop"] if script.endswith("/scripts/resolve-base.sh"):
                if self.protected is None:
                    return 1, "", "no origin remote"
                return 0, json.dumps({"protected_branches": self.protected}), ""
            case ["bash", "-c", 'cd -- "$1" && exec "$2"', "stack-membership", path, script] if script.endswith(
                "/scripts/resolve-stack-membership.sh"
            ):
                membership = self.stacks.get(path, "none")
                return (
                    (1, "", "gh stack failed") if membership == "error" else (0, f"STACK_MEMBERSHIP={membership}\n", "")
                )
            case ["git", "-C", path, "ls-files", "-v", "-z"]:
                return 0, "".join(f"{tag} {name}\0" for name, (tag, _) in self.hidden.items()), ""
            case ["git", "-C", path, "rev-parse", "--path-format=absolute", "--git-path", "index"]:
                index = Path(path) / ".git-dir" / "index"
                index.touch()
                return 0, f"{index}\n", ""
            case ["env", copy, "git", "-C", path, "update-index", _, "-z", "--stdin"] if copy.startswith(
                "GIT_INDEX_FILE="
            ):
                return 0, "", ""
            case [
                "env",
                copy,
                "git",
                "-C",
                path,
                "diff-files",
                "--quiet",
                "--no-ext-diff",
                "--ignore-submodules=none",
                "--",
                *names,
            ] if copy.startswith("GIT_INDEX_FILE="):
                return (1 if any(self.hidden[name][1] for name in names) else 0), "", ""
            case ["git", "-C", path, "rev-parse", "--path-format=absolute", "--git-dir"]:
                return 0, str(Path(path) / ".git-dir") + "\n", ""
            case ["git", "-C", path, "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none"]:
                return 0, self.dirty.get(path, ""), ""
            case ["git", "-C", path, "rev-parse", "--verify", "HEAD"]:
                return (0, self.heads[path] + "\n", "") if path in self.heads else (128, "", "fatal: bad HEAD")
        return 97, "", "unexpected command: " + " ".join(argv)

    def search(self, query: str) -> Json:
        if "is:closed" in query:
            nodes = self.closed
        else:
            assert query.startswith("is:pr is:open archived:false author:@me"), query
            nodes = [
                {
                    "number": number,
                    "title": versions[0]["title"],
                    "url": versions[0]["url"],
                    "state": "OPEN",
                    "mergedAt": None,
                    "closedAt": None,
                    "repository": {"nameWithOwner": repo},
                }
                for (repo, number), versions in self.prs.items()
                if " repo:" not in query or query.endswith(f" repo:{repo}")
            ]
        page = {"issueCount": len(nodes), "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": nodes}
        return {"data": {"search": page}}

    @staticmethod
    def invalid_read(query: str, fields: list[str]) -> str:
        """What GitHub would reject in a batched read: a missing fragment, or a variable typed or passed wrongly."""
        if "fragment PR on PullRequest" not in query:
            return "Fragment PR was used, but not defined"
        header = re.match(r"query=query\((.*?)\) \{", query)
        declared = dict(re.findall(r"\$(\w+): (\w+)!", header.group(1))) if header else {}
        for flag, field in zip(fields[::2], fields[1::2], strict=True):
            key = field.split("=", 1)[0]
            expected = ("Int", "-F") if key.startswith("k") else ("String", "-f")
            if (declared.get(key), flag) != expected:
                return f"Variable ${key} of type {declared.get(key)} passed with {flag}"
        return ""

    def read(self, query: str, values: dict[str, str]) -> Json:
        """Answer a batched read: one aliased repository per line, each with aliased Pull Requests."""
        self.read_requests += 1
        data: Json = {}
        for line in query.splitlines():
            repository = re.match(r"\s*(r\d+): repository\(owner: \$(o\d+), name: \$(n\d+)\)", line)
            if not repository:
                continue
            alias, owner, name = repository.groups()
            fields: Json = {"defaultBranchRef": {"name": "main"}}
            for pr_alias, number_key in re.findall(r"(p\d+): pullRequest\(number: \$(k\d+)\)", line):
                number = int(values[number_key])
                if number in self.omitted:
                    continue
                versions = self.prs[(f"{values[owner]}/{values[name]}", number)]
                fields[pr_alias] = copy.deepcopy(versions.pop(0) if len(versions) > 1 else versions[0])
                self.read_counts[number] = self.read_counts.get(number, 0) + 1
            data[alias] = fields
        return {"data": data}

    def listing(self) -> str:
        fields = [f"worktree {self.root / 'main'}", f"HEAD {HEAD}", "branch refs/heads/main", ""]
        for path, branch, flags in self.worktrees:
            fields += [f"worktree {path}", f"HEAD {self.heads.get(path, HEAD)}"]
            fields += [f"branch refs/heads/{branch}"] if branch else ["detached"]
            fields += [*flags, ""]
        return "\0".join(fields) + "\0"

    def reads(self, number: int) -> int:
        return self.read_counts.get(number, 0)


class QueueCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.host = host = FakeHost(Path(directory.name))
        # Every command the helper ran must be one the host knows, so an unexpected write cannot pass as a warning.
        self.addCleanup(lambda: self.assertEqual(host.refused, []))
        for module in (author_queue, author_queue.review_process):
            patcher = mock.patch.object(module, "run", self.host)
            patcher.start()
            self.addCleanup(patcher.stop)
        sleep = mock.patch.object(author_queue.time, "sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)

    def invoke(self, *argv: str) -> tuple[int, Json]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = author_queue.main(list(argv))
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 1, "the helper prints exactly one line")
        document = json.loads(lines[0])
        self.assertIsInstance(document, dict)
        return code, document

    def snapshot(self, *argv: str) -> Json:
        code, document = self.invoke(*argv)
        self.assertEqual((code, document["status"]), (0, "ok"), document)
        return document

    def only(self, node: Json, *later: Json) -> Json:
        """The report row for a single Pull Request."""
        self.host.add(node, *later)
        prs = self.snapshot()["prs"]
        self.assertEqual(len(prs), 1)
        row: Json = prs[0]
        return row


# How to make each state's condition true on a recorded Pull Request.
CONDITIONS: dict[str, Callable[[Json], None]] = {
    "draft": lambda node: node.update(isDraft=True),
    "conflicts": lambda node: node.update(mergeable="CONFLICTING"),
    "ci-failing": lambda node: add_check(node, check("lint", "FAILURE", run=7002)),
    "ai-feedback": lambda node: node["reviewThreads"]["nodes"].append(bot_thread()),
    "human-feedback": lambda node: node["reviewThreads"]["nodes"].append(human_thread()),
    "ci-running": lambda node: add_check(node, check("e2e", None, run=7003, status="IN_PROGRESS")),
    "behind": lambda node: node.update(mergeStateStatus="BEHIND"),
    "awaiting-review": lambda node: node.update(mergeStateStatus="BLOCKED", reviewDecision="REVIEW_REQUIRED"),
    "ready": lambda node: node.update(mergeStateStatus="CLEAN"),
    "unknown": lambda node: node.update(mergeStateStatus="UNKNOWN", mergeable="UNKNOWN"),
}
# These four come from the one merge state, so no Pull Request has two of them.
MERGE_STATES = {"behind", "awaiting-review", "ready", "unknown"}


def add_check(node: Json, entry: Json) -> None:
    rollup = node["commits"]["nodes"][0]["commit"]["statusCheckRollup"] or {"contexts": {"nodes": []}}
    set_checks(node, [*rollup["contexts"]["nodes"], entry])


def with_states(*states: str) -> Json:
    node = pr_node(1)
    for state in reversed(states):
        CONDITIONS[state](node)
    return node


class StateTests(QueueCase):
    def test_each_state_alone(self) -> None:
        for state in author_queue.STATES:
            with self.subTest(state=state):
                self.setUp()
                self.assertEqual(self.only(with_states(state))["state"], state)

    def test_the_earlier_state_wins(self) -> None:
        states = author_queue.STATES
        for index, first in enumerate(states):
            for later in states[index + 1 :]:
                if {first, later} <= MERGE_STATES:
                    continue
                with self.subTest(first=first, later=later):
                    self.setUp()
                    self.assertEqual(self.only(with_states(first, later))["state"], first)

    def test_the_documented_order(self) -> None:
        self.assertEqual(
            author_queue.STATES,
            (
                "draft",
                "conflicts",
                "ci-failing",
                "ai-feedback",
                "human-feedback",
                "ci-running",
                "behind",
                "awaiting-review",
                "ready",
                "unknown",
            ),
        )

    def test_a_dirty_merge_state_is_a_conflict(self) -> None:
        self.assertEqual(self.only(pr_node(1, mergeStateStatus="DIRTY"))["state"], "conflicts")

    def test_a_cancelled_check_fails_ci(self) -> None:
        row = self.only(pr_node(1, checks=[check("test", "CANCELLED")]))
        self.assertEqual((row["state"], row["ci"]["failing"]), ("ci-failing", ["test"]))

    def test_a_failure_from_a_superseded_run_does_not_count(self) -> None:
        self.host.runs[HEAD] = [
            {"id": 7001, "workflow_id": 1, "event": "pull_request", "conclusion": "cancelled"},
            {"id": 7005, "workflow_id": 1, "event": "pull_request", "conclusion": "success"},
        ]
        # GitHub's rollup still counts the cancelled check, so it reports the merge state as UNSTABLE.
        checks = [check("test", "CANCELLED", run=7001), check("test", "SUCCESS", run=7005)]
        row = self.only(pr_node(1, checks=checks, mergeStateStatus="UNSTABLE"))
        self.assertEqual((row["state"], row["ci"]["state"], row["ci"]["superseded"]), ("ready", "green", 1))

    def test_only_a_newer_run_of_the_same_workflow_and_event_supersedes(self) -> None:
        for later in ({"workflow_id": 2, "event": "pull_request"}, {"workflow_id": 1, "event": "push"}):
            with self.subTest(later=later):
                self.setUp()
                self.host.runs[HEAD] = [
                    {"id": 7001, "workflow_id": 1, "event": "pull_request", "conclusion": "failure"},
                    {"id": 7005, "conclusion": "success", **later},
                ]
                node = pr_node(1, checks=[check("lint", "FAILURE", run=7001), check("test", "SUCCESS", run=7005)])
                row = self.only(node)
                self.assertEqual((row["state"], row["ci"]["superseded"]), ("ci-failing", 0))

    def test_a_skipped_run_replaces_nothing(self) -> None:
        self.host.runs[HEAD] = [
            {"id": 7001, "workflow_id": 1, "event": "pull_request", "conclusion": "failure"},
            {"id": 7005, "workflow_id": 1, "event": "pull_request", "conclusion": "skipped"},
        ]
        self.assertEqual(self.only(pr_node(1, checks=[check("test", "FAILURE", run=7001)]))["state"], "ci-failing")

    def test_unread_checks_fail_through_the_rollup(self) -> None:
        node = pr_node(1)
        set_checks(node, [check("test", "SUCCESS")], total=150)
        node["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["state"] = "FAILURE"
        self.host.runs[HEAD] = []
        self.host.add(node)
        document = self.snapshot()
        self.assertEqual(document["prs"][0]["state"], "ci-failing")
        self.assertIn(f"only the first 1 of 150 checks read for {REPO}#1", document["warnings"])

    def test_commit_statuses_count_like_checks(self) -> None:
        for state, expected in (("FAILURE", "ci-failing"), ("ERROR", "ci-failing"), ("PENDING", "ci-running")):
            with self.subTest(state=state):
                self.setUp()
                self.host.runs[HEAD] = []
                node = pr_node(1, checks=[check("test", "SUCCESS"), {"context": "deploy", "state": state}])
                row = self.only(node)
                names = row["ci"]["failing"] if expected == "ci-failing" else row["ci"]["running"]
                self.assertEqual((row["state"], names), (expected, ["deploy"]))

    def test_no_checks_and_a_clean_merge_state_is_ready(self) -> None:
        row = self.only(pr_node(1, checks=[]))
        self.assertEqual((row["state"], row["ci"]["state"]), ("ready", "none"))

    def test_an_answered_bot_thread_does_not_count(self) -> None:
        reply = comment(ME, "2026-04-01T11:00:00Z")
        self.assertEqual(self.only(pr_node(1, threads=[bot_thread(reply)]))["state"], "ready")

    def test_an_answered_human_thread_does_not_count(self) -> None:
        reply = comment(ME, "2026-04-01T11:00:00Z")
        self.assertEqual(self.only(pr_node(1, threads=[human_thread(reply)]))["state"], "ready")

    def test_a_reply_before_the_latest_reviewer_comment_does_not_answer_it(self) -> None:
        for kind, login in (("Bot", "coderabbitai"), ("User", "riley-reviewer")):
            with self.subTest(kind=kind):
                self.setUp()
                follow_up = thread(
                    comment(login, "2026-04-01T09:00:00Z", kind),
                    comment(ME, "2026-04-01T10:00:00Z"),
                    comment(login, "2026-04-01T11:00:00Z", kind),
                )
                expected = "ai-feedback" if kind == "Bot" else "human-feedback"
                self.assertEqual(self.only(pr_node(1, threads=[follow_up]))["state"], expected)

    def test_a_resolved_thread_does_not_count(self) -> None:
        resolved = thread(comment("riley-reviewer", "2026-04-01T10:00:00Z"), resolved=True)
        self.assertEqual(self.only(pr_node(1, threads=[resolved]))["state"], "ready")

    def test_a_thread_with_a_person_in_it_is_human_feedback(self) -> None:
        mixed = bot_thread(comment("riley-reviewer", "2026-04-01T10:30:00Z"))
        row = self.only(pr_node(1, threads=[mixed]))
        self.assertEqual((row["state"], row["threads"]), ("human-feedback", {"ai": 0, "human": 1}))

    def test_changes_requested_is_human_feedback(self) -> None:
        node = pr_node(1, reviewDecision="CHANGES_REQUESTED", mergeStateStatus="BLOCKED")
        self.assertEqual(self.only(node)["state"], "human-feedback")


class BatchedReadTests(QueueCase):
    def test_pull_requests_are_read_in_batches(self) -> None:
        count = author_queue.READ_BATCH + 2
        for number in range(1, count + 1):
            self.host.add(pr_node(number))
        self.host.add(pr_node(1), repo="acme/api")
        prs = self.snapshot("--all-repos")["prs"]
        self.assertEqual(len(prs), count + 1)
        self.assertEqual(self.host.read_requests, 2)
        self.assertTrue(all(self.host.reads(number) == 1 for number in range(2, count + 1)))

    def test_only_unknown_merge_states_are_read_again(self) -> None:
        self.host.add(pr_node(1, mergeStateStatus="UNKNOWN"), pr_node(1, mergeStateStatus="BEHIND"))
        self.host.add(pr_node(2))
        states = {row["pr"]: row["state"] for row in self.snapshot()["prs"]}
        self.assertEqual(states, {f"{REPO}#1": "behind", f"{REPO}#2": "ready"})
        self.assertEqual((self.host.reads(1), self.host.reads(2), self.host.read_requests), (2, 1, 2))


class MergeStateRereadTests(QueueCase):
    def test_an_unknown_merge_state_is_read_once_more(self) -> None:
        row = self.only(pr_node(1, mergeStateStatus="UNKNOWN"), pr_node(1, mergeStateStatus="BEHIND"))
        self.assertEqual(row["state"], "behind")
        self.assertEqual(self.host.reads(1), 2)
        self.sleep.assert_called_once_with(author_queue.REREAD_DELAY)

    def test_still_unknown_after_the_reread_is_unknown(self) -> None:
        node = pr_node(1, mergeStateStatus="UNKNOWN")
        row = self.only(node, copy.deepcopy(node))
        self.assertEqual((row["state"], row["next"]["action"]), ("unknown", "recheck"))
        self.assertEqual(self.host.reads(1), 2)

    def test_a_known_merge_state_is_read_once(self) -> None:
        self.only(pr_node(1))
        self.assertEqual(self.host.reads(1), 1)
        self.sleep.assert_not_called()


class NextActionTests(QueueCase):
    def test_each_state_has_one_next_action(self) -> None:
        expected = {
            "draft": ("none", "none", None),
            "conflicts": ("run", "shape-up", "trackbed:pr:shape-up"),
            "ci-failing": ("run", "shape-up", "trackbed:pr:shape-up"),
            "ai-feedback": ("run", "shape-up", "trackbed:pr:shape-up"),
            "human-feedback": ("author", "review-reply", "trackbed:pr:github-review-reply"),
            "ci-running": ("wait", "wait", None),
            "behind": ("run", "shape-up", "trackbed:pr:shape-up"),
            "awaiting-review": ("wait", "wait", None),
            "ready": ("author", "merge", None),
            "unknown": ("wait", "recheck", None),
        }
        self.assertEqual(set(expected), set(author_queue.STATES))
        for state, (owner, action, skill) in expected.items():
            with self.subTest(state=state):
                self.setUp()
                self.host.checkout("ana/wid-1")
                row = self.only(with_states(state))
                self.assertEqual(row["next"], {"owner": owner, "action": action, "skill": skill})

    def test_behind_gets_a_rebase_only_when_nothing_else_applies(self) -> None:
        for other in ("draft", "ci-failing", "ai-feedback", "human-feedback", "ci-running"):
            with self.subTest(other=other):
                self.setUp()
                self.host.checkout("ana/wid-1")
                self.assertEqual(self.only(with_states(other, "behind"))["state"], other)

    def test_conflicts_always_get_a_rebase(self) -> None:
        for other in author_queue.STATES[2:]:
            with self.subTest(other=other):
                self.setUp()
                self.host.checkout("ana/wid-1")
                row = self.only(with_states("conflicts", other))
                self.assertEqual((row["state"], row["next"]["action"]), ("conflicts", "shape-up"))

    def test_without_an_eligible_worktree_the_next_action_says_so(self) -> None:
        row = self.only(pr_node(1, mergeStateStatus="BEHIND"))
        self.assertEqual(row["next"], {"owner": "author", "action": "no-worktree", "skill": None})
        self.assertEqual(row["worktree"], {"path": None, "reason": "not checked out in a local worktree"})

    def test_rows_for_the_author_come_first(self) -> None:
        self.host.checkout("ana/wid-2")
        self.host.add(pr_node(1, isDraft=True))
        self.host.add(pr_node(2, mergeStateStatus="BEHIND"))
        self.host.add(pr_node(3, mergeStateStatus="BLOCKED"))
        self.host.add(pr_node(4))
        self.host.add(pr_node(5, threads=[human_thread()]))
        order = [(row["pr"], row["next"]["owner"]) for row in self.snapshot()["prs"]]
        self.assertEqual(
            order,
            [
                (f"{REPO}#5", "author"),
                (f"{REPO}#4", "author"),
                (f"{REPO}#2", "run"),
                (f"{REPO}#3", "wait"),
                (f"{REPO}#1", "none"),
            ],
        )

    def test_rows_with_the_same_state_sort_by_number(self) -> None:
        for number in (10, 9, 100):
            self.host.add(pr_node(number))
        self.host.closed = [
            {
                "number": number,
                "title": f"Closed {number}",
                "url": f"https://github.com/{REPO}/pull/{number}",
                "state": "CLOSED",
                "mergedAt": None,
                "closedAt": "2026-04-02T09:00:00Z",
                "repository": {"nameWithOwner": REPO},
            }
            for number in (20, 3)
        ]
        document = self.snapshot("--since", "2026-04-01T00:00:00Z")
        self.assertEqual([row["pr"] for row in document["prs"]], [f"{REPO}#9", f"{REPO}#10", f"{REPO}#100"])
        self.assertEqual([row["pr"] for row in document["closed"]], [f"{REPO}#3", f"{REPO}#20"])


class WorktreeTests(QueueCase):
    def worktree(self, node: Json | None = None) -> Json:
        row = self.only(node or pr_node(1, mergeStateStatus="BEHIND"))
        worktree: Json = row["worktree"]
        return worktree

    def test_a_clean_worktree_at_the_published_head_is_named(self) -> None:
        path = self.host.checkout("ana/wid-1")
        self.assertEqual(self.worktree(), {"path": path, "reason": None})

    def test_a_dirty_worktree_is_not_eligible(self) -> None:
        path = self.host.checkout("ana/wid-1")
        self.host.dirty[path] = "?? notes.txt\n"
        self.assertEqual(self.worktree(), {"path": None, "reason": "dirty worktree"})

    def test_a_local_head_that_differs_from_the_remote_head_is_not_eligible(self) -> None:
        self.host.checkout("ana/wid-1", head=OTHER_HEAD)
        self.assertEqual(self.worktree(), {"path": None, "reason": "local head differs from the published head"})

    def test_a_branch_with_no_worktree_says_so(self) -> None:
        self.host.checkout("ana/something-else")
        self.assertEqual(self.worktree(), {"path": None, "reason": "not checked out in a local worktree"})

    def test_an_operation_in_progress_is_not_eligible(self) -> None:
        path = self.host.checkout("ana/wid-1")
        (Path(path) / ".git-dir" / "MERGE_HEAD").write_text(HEAD)
        self.assertEqual(self.worktree(), {"path": None, "reason": "operation in progress"})

    def test_a_rebase_stopped_in_a_detached_worktree_is_an_operation_in_progress(self) -> None:
        path = self.host.checkout(None, name="ana-wid-1")
        (Path(path) / ".git-dir" / "rebase-merge").mkdir()
        (Path(path) / ".git-dir" / "rebase-merge" / "head-name").write_text("refs/heads/ana/wid-1\n")
        self.assertEqual(self.worktree(), {"path": None, "reason": "operation in progress"})

    def test_a_hidden_edit_makes_the_worktree_dirty(self) -> None:
        self.host.checkout("ana/wid-1")
        self.host.hidden["config.local"] = ("h", True)
        self.assertEqual(self.worktree(), {"path": None, "reason": "dirty worktree"})

    def test_an_unchanged_hidden_path_is_clean(self) -> None:
        path = self.host.checkout("ana/wid-1")
        self.host.hidden["config.local"] = ("h", False)
        self.assertEqual(self.worktree(), {"path": path, "reason": None})

    def test_an_unreadable_head_is_unavailable(self) -> None:
        path = self.host.checkout("ana/wid-1")
        del self.host.heads[path]
        self.assertEqual(self.worktree(), {"path": None, "reason": "worktree unavailable"})

    def test_a_stack_member_is_not_eligible(self) -> None:
        for membership, reason in (
            ("local", "stack member"),
            ("remote", "stack member"),
            ("error", "stack membership unknown"),
        ):
            with self.subTest(membership=membership):
                self.setUp()
                self.host.stacks[self.host.checkout("ana/wid-1")] = membership
                self.assertEqual(self.worktree(), {"path": None, "reason": reason})

    def test_the_configured_protected_branches_apply(self) -> None:
        self.host.protected = ["main", "master", "develop", "staging"]
        self.host.checkout("staging")
        node = pr_node(1, mergeStateStatus="BEHIND", headRefName="staging")
        self.assertEqual(self.worktree(node), {"path": None, "reason": "protected branch"})

    def test_unknown_protected_branches_make_no_worktree_eligible(self) -> None:
        self.host.protected = None
        self.host.checkout("ana/wid-1")
        self.host.add(pr_node(1, mergeStateStatus="BEHIND"))
        document = self.snapshot()
        self.assertEqual(document["prs"][0]["worktree"], {"path": None, "reason": "protected branches unknown"})
        self.assertIn("cannot resolve the protected branches: no origin remote", document["warnings"])

    def test_a_failed_worktree_listing_is_unavailable_and_warned(self) -> None:
        self.host.listing_exit = 128
        self.host.add(pr_node(1, mergeStateStatus="BEHIND"))
        document = self.snapshot()
        self.assertEqual(document["localRepository"], REPO)
        self.assertEqual(document["prs"][0]["worktree"], {"path": None, "reason": "worktree unavailable"})
        self.assertIn("cannot list the local worktrees: fatal: not a git repository", document["warnings"])

    def test_a_worktree_that_cannot_be_inspected_is_unavailable(self) -> None:
        self.host.hidden["config.local"] = ("h", False)
        cases = ["--git-dir", "status --porcelain", "ls-files", "--git-path index", "update-index", "missing directory"]
        for number, failing in enumerate(cases, start=1):
            with self.subTest(failing=failing):
                path = self.host.checkout(f"ana/wid-{number}")
                if failing == "missing directory":
                    shutil.rmtree(path)
                self.host.failing = {failing}
                self.host.add(pr_node(number, mergeStateStatus="BEHIND"))
                rows = {row["pr"]: row for row in self.snapshot()["prs"]}
                worktree = rows[f"{REPO}#{number}"]["worktree"]
                self.assertEqual(worktree, {"path": None, "reason": "worktree unavailable"})

    def test_a_locked_worktree_is_unavailable(self) -> None:
        self.host.checkout("ana/wid-1", "locked")
        self.assertEqual(self.worktree(), {"path": None, "reason": "worktree unavailable"})

    def test_an_agent_isolation_worktree_is_not_eligible(self) -> None:
        self.host.checkout("ana/wid-1", name=".claude/worktrees/agent-1")
        self.assertEqual(self.worktree(), {"path": None, "reason": "agent isolation worktree"})

    def test_a_fork_head_is_not_eligible(self) -> None:
        self.host.checkout("ana/wid-1")
        node = pr_node(1, mergeStateStatus="BEHIND", isCrossRepository=True)
        self.assertEqual(self.worktree(node), {"path": None, "reason": "fork head"})

    def test_a_stacked_pull_request_is_classified_but_not_eligible(self) -> None:
        self.host.checkout("ana/wid-1")
        base = {"associatedPullRequests": {"nodes": [{"number": 9, "headRepository": {"nameWithOwner": REPO}}]}}
        row = self.only(pr_node(1, mergeStateStatus="BEHIND", baseRefName="ana/wid-9", baseRef=base))
        self.assertEqual((row["state"], row["basePr"]), ("behind", 9))
        self.assertEqual(row["worktree"], {"path": None, "reason": "stacked on #9"})

    def test_a_fork_pull_request_on_the_base_is_no_stack(self) -> None:
        path = self.host.checkout("ana/wid-1")
        base = {"associatedPullRequests": {"nodes": [{"number": 9, "headRepository": {"nameWithOwner": "x/widgets"}}]}}
        self.assertEqual(
            self.worktree(pr_node(1, mergeStateStatus="BEHIND", baseRef=base)), {"path": path, "reason": None}
        )

    def test_a_long_lived_base_is_no_stack(self) -> None:
        # A release Pull Request from develop is open, so develop is the head of an open Pull Request.
        release = {"nodes": [{"number": 9, "headRepository": {"nameWithOwner": REPO}}]}
        cases: dict[str, tuple[str, Json]] = {
            "default branch": ("main", {}),
            "branch protection": ("develop", {"refUpdateRule": {"pattern": "develop"}}),
            "ruleset": ("develop", {"rules": {"totalCount": 1}}),
        }
        for number, (case, (base_name, rule)) in enumerate(cases.items(), start=1):
            with self.subTest(case=case):
                path = self.host.checkout(f"ana/wid-{number}")
                base = {"associatedPullRequests": release, **rule}
                self.host.add(pr_node(number, mergeStateStatus="BEHIND", baseRefName=base_name, baseRef=base))
                rows = {row["pr"]: row for row in self.snapshot()["prs"]}
                row = rows[f"{REPO}#{number}"]
                self.assertEqual((row["basePr"], row["worktree"]), (None, {"path": path, "reason": None}))

    def test_a_protected_branch_is_not_eligible(self) -> None:
        self.host.checkout("develop")
        node = pr_node(1, mergeStateStatus="BEHIND", headRefName="develop")
        self.assertEqual(self.worktree(node), {"path": None, "reason": "protected branch"})

    def test_a_pull_request_in_another_repository_has_no_worktree_here(self) -> None:
        self.host.checkout("ana/wid-1")
        self.host.add(pr_node(1, mergeStateStatus="BEHIND"), repo="acme/api")
        row = self.snapshot("--all-repos")["prs"][0]
        self.assertEqual(row["pr"], "acme/api#1")
        self.assertEqual(row["worktree"], {"path": None, "reason": "repository not checked out here"})


class ScopeTests(QueueCase):
    def test_the_current_repository_is_the_default_scope(self) -> None:
        self.host.add(pr_node(1))
        self.host.add(pr_node(2), repo="acme/api")
        document = self.snapshot()
        self.assertEqual((document["scope"], [row["pr"] for row in document["prs"]]), (REPO, [f"{REPO}#1"]))
        self.assertEqual(document["me"], ME)
        self.assertEqual(document["schemaVersion"], 1)

    def test_all_repos_spans_every_repository(self) -> None:
        self.host.add(pr_node(1))
        self.host.add(pr_node(2), repo="acme/api")
        document = self.snapshot("--all-repos")
        self.assertEqual(document["scope"], "all")
        self.assertEqual(sorted(row["pr"] for row in document["prs"]), ["acme/api#2", f"{REPO}#1"])

    def test_since_lists_pull_requests_that_closed(self) -> None:
        self.host.closed = [
            {
                "number": 8,
                "title": "Merged one",
                "url": f"https://github.com/{REPO}/pull/8",
                "state": "MERGED",
                "mergedAt": "2026-04-02T09:00:00Z",
                "closedAt": "2026-04-02T09:00:00Z",
                "repository": {"nameWithOwner": REPO},
            },
        ]
        document = self.snapshot("--since", "2026-04-01T00:00:00Z")
        self.assertEqual(
            document["closed"],
            [
                {
                    "pr": f"{REPO}#8",
                    "url": f"https://github.com/{REPO}/pull/8",
                    "title": "Merged one",
                    "state": "MERGED",
                    "at": "2026-04-02T09:00:00Z",
                }
            ],
        )
        self.assertTrue(any("closed:>=2026-04-01T00:00:00Z" in " ".join(call) for call in self.host.calls))

    def test_no_repository_without_a_scope_is_a_usage_error(self) -> None:
        self.host.repo = None
        with redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as stop:
            author_queue.main([])
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("--all-repos", err.getvalue())
        self.assertIn("not a git repository", err.getvalue())

    def test_an_unknown_current_repository_is_warned_with_an_explicit_scope(self) -> None:
        self.host.repo = None
        self.host.checkout("ana/wid-1")
        self.host.add(pr_node(1, mergeStateStatus="BEHIND"))
        document = self.snapshot("--repo", REPO)
        self.assertEqual(document["prs"][0]["worktree"], {"path": None, "reason": "repository not checked out here"})
        self.assertIn(
            "cannot find the current directory's GitHub repository (not a git repository); "
            "no local worktree was inspected",
            document["warnings"],
        )

    def test_a_failed_sign_in_is_an_error_document_not_a_usage_error(self) -> None:
        self.host.user_error = "HTTP 401: Bad credentials"
        self.host.repo = None
        code, document = self.invoke()
        self.assertEqual((code, document["status"]), (1, "error"))
        self.assertIn("HTTP 401", document["message"])

    def test_invalid_arguments_are_usage_errors(self) -> None:
        for argv in (["--repo", "not a slug"], ["--since", "yesterday"], ["--repo", REPO, "--all-repos"]):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stop:
                author_queue.main(argv)
            self.assertEqual(stop.exception.code, 2)

    def test_a_pull_request_missing_from_a_batched_read_is_an_error_document(self) -> None:
        self.host.add(pr_node(1))
        self.host.add(pr_node(2))
        self.host.omitted.add(2)
        code, document = self.invoke()
        self.assertEqual((code, document["status"]), (1, "error"))
        self.assertIn(f"{REPO}#2", document["message"])

    def test_a_failed_read_is_an_error_document(self) -> None:
        self.host.add(pr_node(1))
        self.host.graphql_exit = 1
        code, document = self.invoke()
        self.assertEqual((code, document["status"]), (1, "error"))
        self.assertIn("HTTP 502", document["message"])


class DocumentationTests(QueueCase):
    REFERENCE = SCRIPT_PATH.parents[1] / "references" / "author-mode.md"

    def test_the_reference_lists_the_states_in_order(self) -> None:
        documented = re.findall(r"^\| \d+ \| `([a-z-]+)` \|", self.REFERENCE.read_text(), re.MULTILINE)
        self.assertEqual(tuple(documented), author_queue.STATES)

    def test_the_reference_documents_every_output_field(self) -> None:
        self.host.add(pr_node(1))
        document = self.snapshot()
        text = self.REFERENCE.read_text()
        fields = set(document) | set(document["prs"][0]) | set(document["prs"][0]["next"])
        fields |= set(document["prs"][0]["ci"]) | set(document["prs"][0]["threads"])
        for field in sorted(fields):
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", text)

    def test_the_reference_lists_every_next_action_and_owner(self) -> None:
        text = self.REFERENCE.read_text()
        for value in [*author_queue.OWNERS, "shape-up", "no-worktree", "review-reply", "merge", "wait", "recheck"]:
            with self.subTest(value=value):
                self.assertIn(f"`{value}`", text)


class ReadOnlyTests(QueueCase):
    def test_the_helper_only_reads(self) -> None:
        self.host.checkout("ana/wid-1")
        self.host.hidden["config.local"] = ("S", False)
        (Path(self.host.root) / "ana-wid-1" / "config.local").write_text("local\n")
        self.host.runs[HEAD] = []
        self.host.add(pr_node(1, checks=[check("test", "FAILURE")], mergeStateStatus="UNKNOWN"), pr_node(1))
        self.snapshot("--since", "2026-04-01")

        self.assertEqual(self.host.refused, [])
        for call in self.host.calls:
            with self.subTest(call=call[:4]):
                self.assertNotIn("-X", call)
                self.assertNotIn("--method", call)
                self.assertNotIn("-w", call)
                if call[0] == "gh":
                    self.assertTrue(
                        call[1:3] in (["repo", "view"], ["api", "user"], ["api", "graphql"])
                        or call[2].startswith("repos/")
                    )
                    if call[1:3] != ["api", "graphql"]:
                        # gh api sends a POST when it is given fields, even without -X.
                        self.assertFalse({"-f", "-F", "--field", "--raw-field", "--input"} & set(call))
                elif call[0] == "git":
                    self.assertTrue(call[1:3] == ["worktree", "list"] or call[3] in ("rev-parse", "status", "ls-files"))
                elif call[0] == "env":
                    # Only a copy of the index outside the worktree is written, never the worktree's own index.
                    copy = Path(call[1].removeprefix("GIT_INDEX_FILE="))
                    self.assertNotIn(self.host.root, copy.parents)
                    self.assertIn(call[5], ("update-index", "diff-files"))
                else:
                    self.assertTrue(
                        call[0].endswith("/resolve-base.sh") or call[-1].endswith("/resolve-stack-membership.sh")
                    )


class HiddenEditGitTests(unittest.TestCase):
    """The hidden-edit check against real git, since the fake host cannot show how git compares hidden paths."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.repo = Path(directory.name)
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"]):
            subprocess.run(["git", "-C", str(self.repo), *args], check=True)
        (self.repo / "settings.txt").write_text("one\n")
        (self.repo / "link").symlink_to("settings.txt")
        (self.repo / "sparse.txt").write_text("sparse\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "init"], check=True)

    def hide(self, flag: str, *paths: str) -> None:
        subprocess.run(["git", "-C", str(self.repo), "update-index", flag, "--", *paths], check=True)

    def test_hidden_paths_are_compared_like_the_batch_rebase(self) -> None:
        self.hide("--assume-unchanged", "settings.txt", "link")
        self.assertIs(author_queue.hidden_edits(str(self.repo)), False)
        # Change the size: git compares stat data, and a same-size edit within a second of the commit can look clean.
        (self.repo / "settings.txt").write_text("two and more\n")
        self.assertIs(author_queue.hidden_edits(str(self.repo)), True)
        (self.repo / "settings.txt").unlink()
        self.assertIs(author_queue.hidden_edits(str(self.repo)), True)

    def test_skip_worktree_paths_count_only_when_present(self) -> None:
        self.hide("--skip-worktree", "sparse.txt")
        (self.repo / "sparse.txt").unlink()
        self.assertIs(author_queue.hidden_edits(str(self.repo)), False)
        (self.repo / "sparse.txt").write_text("changed\n")
        self.assertIs(author_queue.hidden_edits(str(self.repo)), True)
        self.assertEqual(
            subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain"], capture_output=True).stdout, b""
        )


if __name__ == "__main__":
    unittest.main()
