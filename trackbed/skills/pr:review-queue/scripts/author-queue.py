#!/usr/bin/env python3
"""Give each of your open Pull Requests one state and one next action.

  python3 author-queue.py [--repo OWNER/NAME | --all-repos] [--since ISO-8601]

Lists the open Pull Requests you authored in the current directory's GitHub repository, in `--repo`, or in every
repository the token can read with `--all-repos`. It reads GitHub with `gh` and local worktrees with `git`, runs no
model, and never writes to GitHub, a branch, the index, a worktree, or a remote-tracking ref.

Prints one JSON document on one line. Exit 0 carries `"status": "ok"`. Exit 1 means GitHub could not be read: the
document carries `"status": "error"` and a `message`. Exit 2 means an invalid invocation: the reason goes to stderr and
no JSON is printed.

`references/author-mode.md` documents the fields, the states and their order, and the next actions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from collections.abc import Sequence
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any

PLUGIN_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(PLUGIN_SCRIPTS / "lib"))
import review_process  # noqa: E402
from review_process import run, tail  # noqa: E402

SCHEMA_VERSION = 1
LOCAL_TIMEOUT = 30
NETWORK_TIMEOUT = 120
SEARCH_PAGE = 100
SEARCH_LIMIT = 1000
# GitHub computes the merge state in the background, so wait this long before the one re-read.
REREAD_DELAY = 3
# Pull Requests read per GraphQL request. Each one can carry 100 threads of 100 comments and 100 checks, and larger
# responses time out on GitHub's side.
READ_BATCH = 10

# First match wins, in this order.
STATES = (
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
)
SHAPE_UP_STATES = frozenset({"conflicts", "ci-failing", "ai-feedback", "behind"})
OWNERS = ("author", "run", "wait", "none")
FAILED = frozenset({"FAILURE", "ERROR", "TIMED_OUT", "STARTUP_FAILURE", "ACTION_REQUIRED", "CANCELLED"})
RUNNING_STATES = frozenset({"PENDING", "EXPECTED"})
READY_MERGE_STATES = frozenset({"CLEAN", "HAS_HOOKS", "UNSTABLE"})
OPERATION_MARKERS = ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG")

SLUG_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
SINCE_RE = re.compile(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:\d{2})?)?")

SEARCH_QUERY = (
    """
query($q: String!, $after: String) {
  search(query: $q, type: ISSUE, first: %d, after: $after) {
    issueCount pageInfo { hasNextPage endCursor }
    nodes { ... on PullRequest {
      number title url state mergedAt closedAt repository { nameWithOwner }
    } }
  }
}
"""
    % SEARCH_PAGE
)
# One request reads up to READ_BATCH Pull Requests, one aliased `repository` field per line; see `read_prs`.
PR_FRAGMENT = """
fragment PR on PullRequest {
  number title url isDraft state
  baseRefName headRefName headRefOid isCrossRepository
  author { login }
  baseRef {
    associatedPullRequests(states: OPEN, first: 10) { nodes { number headRepository { nameWithOwner } } }
    refUpdateRule { pattern } rules(first: 1) { totalCount }
  }
  mergeable mergeStateStatus reviewDecision
  reviewThreads(first: 100) {
    pageInfo { hasNextPage }
    nodes { isResolved comments(first: 100) {
      nodes { createdAt isMinimized author { login __typename } }
    } }
  }
  commits(last: 1) { nodes { commit { statusCheckRollup { state contexts(first: 100) { totalCount nodes {
    ... on CheckRun { name status conclusion checkSuite { workflowRun { databaseId } } }
    ... on StatusContext { context state }
  } } } } } }
}
"""

Json = dict[str, Any]


class QueueError(Exception):
    """GitHub could not be read; the message says why."""


class UsageError(Exception):
    """The invocation cannot run; exit 2."""


gh_json = partial(review_process.gh_json, error=QueueError, timeout=NETWORK_TIMEOUT)


def graphql(query: str, what: str, **fields: str | int) -> Json:
    argv = ["api", "graphql", "-f", f"query={query}"]
    for key, value in fields.items():
        argv += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
    data = gh_json(*argv, what=what)
    if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
        raise QueueError(f"could not parse {what}")
    result: Json = data["data"]
    return result


def search(query: str, warnings: list[str]) -> list[Json]:
    """Every Pull Request the search finds, up to SEARCH_LIMIT."""
    nodes: list[Json] = []
    after: str | None = None
    while True:
        fields = {"q": query} | ({"after": after} if after else {})
        try:
            result = graphql(SEARCH_QUERY, f"the search `{query}`", **fields)["search"]
            page = [node for node in result["nodes"] if isinstance(node, dict) and node.get("url")]
            more, after, count = (
                result["pageInfo"]["hasNextPage"],
                result["pageInfo"]["endCursor"],
                result["issueCount"],
            )
        except (KeyError, TypeError) as error:
            raise QueueError(f"could not parse the search `{query}`") from error
        nodes += page
        if not more or not after or len(nodes) >= SEARCH_LIMIT:
            if count > len(nodes):
                warnings.append(f"only the first {len(nodes)} of {count} results read for: {query}")
            return nodes


def read_prs(refs: Sequence[tuple[str, int]]) -> dict[tuple[str, int], tuple[Json, str | None]]:
    """Each Pull Request's fields and its repository's default branch, READ_BATCH to a request."""
    nodes: dict[tuple[str, int], tuple[Json, str | None]] = {}
    for start in range(0, len(refs), READ_BATCH):
        batch = refs[start : start + READ_BATCH]
        by_repo: dict[str, list[tuple[int, int]]] = {}
        for index, (slug, number) in enumerate(batch):
            by_repo.setdefault(slug, []).append((index, number))
        variables: dict[str, str | int] = {}
        lines = []
        for r, (slug, prs) in enumerate(by_repo.items()):
            variables[f"o{r}"], variables[f"n{r}"] = slug.split("/", 1)
            fields = " ".join(f"p{i}: pullRequest(number: $k{i}) {{ ...PR }}" for i, _ in prs)
            lines.append(f"  r{r}: repository(owner: $o{r}, name: $n{r}) {{ defaultBranchRef {{ name }} {fields} }}")
            variables.update({f"k{i}": number for i, number in prs})
        declared = ", ".join(f"${key}: {'Int' if key[0] == 'k' else 'String'}!" for key in variables)
        query = f"query({declared}) {{\n" + "\n".join(lines) + "\n}\n" + PR_FRAGMENT
        what = "Pull Requests " + ", ".join(f"{slug}#{number}" for slug, number in batch)
        data = graphql(query, what, **variables)
        for r, (slug, prs) in enumerate(by_repo.items()):
            repository = data.get(f"r{r}") or {}
            for i, number in prs:
                node = repository.get(f"p{i}")
                if not isinstance(node, dict):
                    raise QueueError(f"could not parse {slug}#{number}")
                nodes[(slug, number)] = (node, (repository.get("defaultBranchRef") or {}).get("name"))
    return nodes


def superseded_runs(slug: str, sha: str, warnings: list[str]) -> set[int]:
    """Runs that a newer run of the same workflow and event on the same head replaced; a skipped run replaces none."""
    try:
        data = gh_json("api", f"repos/{slug}/actions/runs?head_sha={sha}&per_page=100", what="workflow runs")
        runs = [entry for entry in data["workflow_runs"] if isinstance(entry, dict)]
    except (QueueError, KeyError, TypeError) as error:
        warnings.append(f"cannot list workflow runs for {slug}@{sha} ({error}); superseded checks still count")
        return set()
    groups: dict[tuple[Any, Any], list[Json]] = {}
    for workflow_run in runs:
        groups.setdefault((workflow_run.get("workflow_id"), workflow_run.get("event")), []).append(workflow_run)
    replaced: set[int] = set()
    for group in groups.values():
        latest = max((r["id"] for r in group if r.get("conclusion") != "skipped"), default=None)
        if latest is not None:
            replaced |= {r["id"] for r in group if r["id"] < latest}
    return replaced


def ci_state(node: Json, slug: str, warnings: list[str]) -> Json:
    """CI after dropping checks from superseded runs: failing, running, green, or none, with the check names."""
    commits = (node.get("commits") or {}).get("nodes") or [{}]
    rollup = ((commits[0] or {}).get("commit") or {}).get("statusCheckRollup") or {}
    contexts = rollup.get("contexts") or {}
    every = [check for check in contexts.get("nodes") or [] if isinstance(check, dict)]
    unread = (contexts.get("totalCount") or len(every)) - len(every)
    if unread > 0:
        warnings.append(f"only the first {len(every)} of {len(every) + unread} checks read for {slug}#{node['number']}")
    replaced = (
        superseded_runs(slug, node["headRefOid"], warnings) if rollup.get("state", "SUCCESS") != "SUCCESS" else set()
    )
    checks = [
        c for c in every if ((c.get("checkSuite") or {}).get("workflowRun") or {}).get("databaseId") not in replaced
    ]

    def name(check: Json) -> str:
        return str(check.get("name") or check.get("context"))

    failing = sorted({name(c) for c in checks if (c.get("conclusion") or c.get("state")) in FAILED})
    running = sorted(
        {name(c) for c in checks if c.get("status", "COMPLETED") != "COMPLETED" or c.get("state") in RUNNING_STATES}
    )
    # Checks past the first 100 are unread, so only the rollup state can name a failure among them.
    if failing or (unread > 0 and rollup.get("state") in ("FAILURE", "ERROR")):
        state = "failing"
    elif running or (unread > 0 and rollup.get("state") in RUNNING_STATES):
        state = "running"
    else:
        state = "green" if checks else "none"
    return {"state": state, "failing": failing, "running": running, "superseded": len(every) - len(checks)}


def open_threads(node: Json, author: str | None, slug: str, warnings: list[str]) -> Json:
    """Unresolved threads the author has not answered since the latest reviewer comment, by who left the feedback.

    Feedback is every visible comment the author did not write. A thread with feedback from a person counts as
    human.
    """
    connection = node.get("reviewThreads") or {}
    if (connection.get("pageInfo") or {}).get("hasNextPage"):
        warnings.append(f"only the first 100 review threads read for {slug}#{node['number']}")
    counts = {"ai": 0, "human": 0}
    for thread in connection.get("nodes") or []:
        if not isinstance(thread, dict) or thread.get("isResolved"):
            continue
        comments = [c for c in (thread.get("comments") or {}).get("nodes") or [] if isinstance(c, dict)]
        feedback = [c for c in comments if login(c) != author and not c.get("isMinimized")]
        if not feedback:
            continue
        latest = max(str(c.get("createdAt")) for c in feedback)
        if any(login(c) == author and str(c.get("createdAt")) > latest for c in comments):
            continue
        bots = all(((c.get("author") or {}).get("__typename")) == "Bot" for c in feedback)
        counts["ai" if bots else "human"] += 1
    return counts


def login(comment: Json) -> str | None:
    author = comment.get("author")
    return author.get("login") if isinstance(author, dict) else None


def stacked_on(node: Json, slug: str, default_branch: str | None) -> int | None:
    """The open Pull Request in the same repository whose head branch is this one's base.

    As in the reviewer view, a base that is the default branch or that branch protection or a ruleset covers is a
    long-lived branch, such as develop under a release Pull Request, not a stack.
    """
    base = node.get("baseRef") or {}
    if (
        node.get("baseRefName") == default_branch
        or base.get("refUpdateRule")
        or (base.get("rules") or {}).get("totalCount")
    ):
        return None
    nodes = (base.get("associatedPullRequests") or {}).get("nodes") or []
    for other in nodes:
        if isinstance(other, dict) and (other.get("headRepository") or {}).get("nameWithOwner") == slug:
            number: int = other["number"]
            return number
    return None


def classify(node: Json, ci: Json, threads: Json) -> str:
    """The first state in STATES that applies."""
    merge_state = node.get("mergeStateStatus")
    if node.get("isDraft"):
        return "draft"
    if node.get("mergeable") == "CONFLICTING" or merge_state == "DIRTY":
        return "conflicts"
    if ci["state"] == "failing":
        return "ci-failing"
    if threads["ai"]:
        return "ai-feedback"
    if threads["human"] or node.get("reviewDecision") == "CHANGES_REQUESTED":
        return "human-feedback"
    if ci["state"] == "running":
        return "ci-running"
    if merge_state == "BEHIND":
        return "behind"
    if merge_state == "BLOCKED":
        return "awaiting-review"
    if merge_state in READY_MERGE_STATES:
        return "ready"
    return "unknown"


class Worktrees:
    """The worktrees of the repository in the current directory and its protected branches, read once.

    The rules follow `worktree_reason` and `location_reason` in pr:rebase's batch-rebase.sh, except that the local head
    is compared with GitHub's published head instead of `git ls-remote`, before the stack check.
    """

    def __init__(self, repository: str | None, warnings: list[str]) -> None:
        self.repository = repository
        self.by_branch: dict[str, tuple[str, str | None]] = {}
        self.protected: frozenset[str] | None = None
        self.listed = False
        if repository is None:
            return
        listing = run(["git", "worktree", "list", "--porcelain", "-z"], LOCAL_TIMEOUT)
        if listing.returncode != 0:
            warnings.append(f"cannot list the local worktrees: {tail(listing.stderr)}")
            return
        self.listed = True
        roles = run([str(PLUGIN_SCRIPTS / "resolve-base.sh"), "--branch-roles", "--protect-develop"], LOCAL_TIMEOUT)
        try:
            names = json.loads(roles.stdout)["protected_branches"] if roles.returncode == 0 else None
        except (ValueError, KeyError, TypeError):
            names = None
        if isinstance(names, list) and names and all(isinstance(name, str) for name in names):
            self.protected = frozenset(names)
        else:
            why = tail(roles.stderr) or f"resolve-base.sh exited {roles.returncode} without a protected-branch list"
            warnings.append(f"cannot resolve the protected branches: {why}")
        path, branch, unavailable = "", "", False
        for field in listing.stdout.decode("utf-8", "replace").split("\0") + [""]:
            if field.startswith("worktree "):
                path, branch, unavailable = field[len("worktree ") :], "", False
            elif field.startswith("branch refs/heads/"):
                branch = field[len("branch refs/heads/") :]
            elif field.split(" ", 1)[0] in ("bare", "detached", "locked", "prunable"):
                unavailable = True
            elif field == "" and path:
                self.add(path, branch, unavailable)
                path = ""

    def add(self, path: str, branch: str, unavailable: bool) -> None:
        """Record the worktree; a rebase in progress detaches it from the branch its head-name file records."""
        flag = "worktree unavailable" if unavailable or any(ord(ch) < 32 for ch in path) else None
        if not branch and Path(path).is_dir():
            directory = git_dir(path)
            for marker in ("rebase-merge", "rebase-apply"):
                try:
                    head_name = (directory / marker / "head-name").read_text().strip() if directory else ""
                except OSError:
                    continue
                if head_name.startswith("refs/heads/"):
                    branch, flag = head_name[len("refs/heads/") :], "operation in progress"
        if branch:
            self.by_branch[branch] = (path, flag)

    def eligibility(self, slug: str, node: Json, base_pr: int | None) -> Json:
        """The clean worktree that has the branch checked out at the published head, or why there is none."""
        branch, head = str(node.get("headRefName")), str(node.get("headRefOid"))
        found = self.by_branch.get(branch)
        if slug != self.repository:
            reason: str | None = "repository not checked out here"
        elif node.get("isCrossRepository"):
            reason = "fork head"
        elif base_pr is not None:
            reason = f"stacked on #{base_pr}"
        elif not self.listed:
            reason = "worktree unavailable"
        elif found is None:
            reason = "not checked out in a local worktree"
        elif found[1] == "worktree unavailable" or not Path(found[0]).is_dir():
            reason = "worktree unavailable"
        elif "/.claude/worktrees/" in found[0]:
            reason = "agent isolation worktree"
        elif self.protected is None:
            reason = "protected branches unknown"
        elif branch in self.protected:
            reason = "protected branch"
        else:
            reason = found[1] or worktree_reason(found[0], head)
        if reason is not None or found is None:
            return {"path": None, "reason": reason}
        return {"path": found[0], "reason": None}


def git_dir(path: str) -> Path | None:
    result = run(["git", "-C", path, "rev-parse", "--path-format=absolute", "--git-dir"], LOCAL_TIMEOUT)
    return Path(result.stdout.decode("utf-8", "replace").strip()) if result.returncode == 0 else None


def worktree_reason(path: str, head: str) -> str | None:
    directory = git_dir(path)
    if directory is None:
        return "worktree unavailable"
    if any((directory / marker).exists() for marker in OPERATION_MARKERS):
        return "operation in progress"
    status = run(
        ["git", "-C", path, "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none"],
        LOCAL_TIMEOUT,
    )
    if status.returncode != 0:
        return "worktree unavailable"
    hidden = hidden_edits(path)
    if hidden is None:
        return "worktree unavailable"
    if status.stdout.strip() or hidden:
        return "dirty worktree"
    local = run(["git", "-C", path, "rev-parse", "--verify", "HEAD"], LOCAL_TIMEOUT)
    if local.returncode != 0:
        return "worktree unavailable"
    if local.stdout.decode().strip() != head:
        return "local head differs from the published head"
    return stack_reason(path)


def hidden_edits(path: str) -> bool | None:
    """Whether a path marked assume-unchanged or skip-worktree, which git status hides, has changes.

    As the batch rebase does, compare those paths through a copy of the index with the hiding flags cleared. The copy
    lives in a temporary directory outside the repository. None when the paths cannot be inspected.
    """
    listing = run(["git", "-C", path, "ls-files", "-v", "-z"], LOCAL_TIMEOUT)
    if listing.returncode != 0:
        return None
    hidden = [
        entry[2:]
        for entry in listing.stdout.decode("utf-8", "surrogateescape").split("\0")
        if entry[:1] == "h" or (entry[:1] in ("S", "s") and os.path.lexists(os.path.join(path, entry[2:])))
    ]
    if not hidden:
        return False
    index = run(["git", "-C", path, "rev-parse", "--path-format=absolute", "--git-path", "index"], LOCAL_TIMEOUT)
    if index.returncode != 0:
        return None
    names = b"".join(name.encode("utf-8", "surrogateescape") + b"\0" for name in hidden)
    with tempfile.TemporaryDirectory() as scratch:
        copy = Path(scratch, "index")
        try:
            shutil.copyfile(index.stdout.decode("utf-8", "surrogateescape").strip(), copy)
        except OSError:
            return None
        git = ["env", f"GIT_INDEX_FILE={copy}", "git", "-C", path]
        for flag in ("--no-assume-unchanged", "--no-skip-worktree"):
            if run([*git, "update-index", flag, "-z", "--stdin"], LOCAL_TIMEOUT, input=names).returncode != 0:
                return None
        diff = run(
            [*git, "diff-files", "--quiet", "--no-ext-diff", "--ignore-submodules=none", "--", *hidden], LOCAL_TIMEOUT
        )
    return {0: False, 1: True}.get(diff.returncode)


def stack_reason(path: str) -> str | None:
    """Skip a branch gh-stack or GitHub tracks as part of a stack, as the batch rebase does."""
    resolver = str(PLUGIN_SCRIPTS / "resolve-stack-membership.sh")
    result = run(["bash", "-c", 'cd -- "$1" && exec "$2"', "stack-membership", path, resolver], NETWORK_TIMEOUT)
    membership = re.search(r"^STACK_MEMBERSHIP=(\S+)$", result.stdout.decode("utf-8", "replace"), re.MULTILINE)
    if result.returncode != 0 or membership is None or membership.group(1) not in ("none", "local", "remote"):
        return "stack membership unknown"
    return None if membership.group(1) == "none" else "stack member"


def next_action(state: str, worktree: Json) -> Json:
    """Who moves next and how."""
    if state in SHAPE_UP_STATES:
        if worktree["path"]:
            return {"owner": "run", "action": "shape-up", "skill": "trackbed:pr:shape-up"}
        return {"owner": "author", "action": "no-worktree", "skill": None}
    actions: dict[str, Json] = {
        "human-feedback": {"owner": "author", "action": "review-reply", "skill": "trackbed:pr:github-review-reply"},
        "ready": {"owner": "author", "action": "merge", "skill": None},
        "ci-running": {"owner": "wait", "action": "wait", "skill": None},
        "awaiting-review": {"owner": "wait", "action": "wait", "skill": None},
        "unknown": {"owner": "wait", "action": "recheck", "skill": None},
        "draft": {"owner": "none", "action": "none", "skill": None},
    }
    return actions[state]


def current_repository() -> tuple[str | None, str]:
    """The current directory's GitHub repository, or None and gh's reason."""
    result = run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"], NETWORK_TIMEOUT)
    slug = result.stdout.decode("utf-8", "replace").strip()
    if result.returncode == 0 and slug:
        return slug, ""
    return None, tail(result.stderr) or f"gh exited {result.returncode}"


def report(node: Json, slug: str, default_branch: str | None, worktrees: Worktrees, warnings: list[str]) -> Json:
    author = login(node)
    ci = ci_state(node, slug, warnings)
    threads = open_threads(node, author, slug, warnings)
    state = classify(node, ci, threads)
    base_pr = stacked_on(node, slug, default_branch)
    worktree = worktrees.eligibility(slug, node, base_pr)
    return {
        "pr": f"{slug}#{node['number']}",
        "url": node.get("url"),
        "title": node.get("title"),
        "state": state,
        "next": next_action(state, worktree),
        "worktree": worktree,
        "base": node.get("baseRefName"),
        "basePr": base_pr,
        "headBranch": node.get("headRefName"),
        "head": node.get("headRefOid"),
        "mergeable": node.get("mergeable"),
        "mergeStateStatus": node.get("mergeStateStatus"),
        "reviewDecision": node.get("reviewDecision"),
        "ci": ci,
        "threads": threads,
    }


def pr_key(ref: str) -> tuple[str, int]:
    """Sort `OWNER/NAME#N` by repository, then by number, so #9 comes before #10."""
    slug, number = ref.rsplit("#", 1)
    return slug, int(number)


def snapshot(scope: str | None, all_repos: bool, since: str | None) -> Json:
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Read the login first, so a failed sign-in or network is an error document rather than "no repository here".
    me = gh_json("api", "user", what="the GitHub login")
    if not isinstance(me, dict) or not me.get("login"):
        raise QueueError("could not parse the GitHub login")
    here, why = current_repository()
    if scope is None and not all_repos:
        if here is None:
            raise UsageError(
                f"cannot find the current directory's GitHub repository ({why}); run it inside one, "
                "or pass --repo OWNER/NAME or --all-repos"
            )
        scope = here
    warnings: list[str] = []
    if here is None:
        warnings.append(
            f"cannot find the current directory's GitHub repository ({why}); no local worktree was inspected"
        )
    qualifier = f" repo:{scope}" if scope else ""
    found = search(f"is:pr is:open archived:false author:@me{qualifier}", warnings)
    refs = sorted({(n["repository"]["nameWithOwner"], n["number"]) for n in found if n.get("state") == "OPEN"})
    nodes = read_prs(refs)
    unknown = [ref for ref, (node, _) in nodes.items() if node.get("mergeStateStatus") == "UNKNOWN"]
    if unknown:
        time.sleep(REREAD_DELAY)
        nodes |= read_prs(unknown)
    worktrees = Worktrees(here, warnings)
    prs = [report(node, slug, default, worktrees, warnings) for (slug, _), (node, default) in nodes.items()]
    prs.sort(key=lambda pr: (OWNERS.index(pr["next"]["owner"]), STATES.index(pr["state"]), pr_key(pr["pr"])))
    closed: list[Json] = []
    if since:
        for node in search(f"is:pr is:closed author:@me closed:>={since}{qualifier}", warnings):
            slug = node["repository"]["nameWithOwner"]
            closed.append(
                {
                    "pr": f"{slug}#{node['number']}",
                    "url": node.get("url"),
                    "title": node.get("title"),
                    "state": node.get("state"),
                    "at": node.get("mergedAt") or node.get("closedAt"),
                }
            )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "ok",
        "checkedAt": checked_at,
        "me": me["login"],
        "scope": scope or "all",
        "localRepository": here,
        "prs": prs,
        "closed": sorted(closed, key=lambda pr: pr_key(pr["pr"])),
        "warnings": warnings,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--repo", help="search this repository instead of the current one")
    where.add_argument("--all-repos", action="store_true", help="search every repository the token can read")
    parser.add_argument("--since", help="also list your Pull Requests that closed since this ISO-8601 time")
    args = parser.parse_args(argv)
    if args.repo is not None and not SLUG_RE.fullmatch(args.repo):
        parser.error(f"--repo must be OWNER/NAME, got: {args.repo}")
    if args.since is not None and not SINCE_RE.fullmatch(args.since):
        parser.error(f"--since must be an ISO-8601 date or time, got: {args.since}")
    try:
        document, code = snapshot(args.repo, args.all_repos, args.since), 0
    except UsageError as error:
        parser.error(str(error))
    except QueueError as error:
        document, code = {"schemaVersion": SCHEMA_VERSION, "status": "error", "message": str(error)}, 1
    print(json.dumps(document, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
