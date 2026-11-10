#!/usr/bin/env python3
"""Report what the current branch's open Pull Request still needs before it is in shape.

  python3 shape-snapshot.py

Reads the Pull Request for the current branch with `gh`, fetches its target branch from `origin`, and reads
its checks and review threads. It never writes to GitHub and never changes a branch, the index, or the working
tree; the only Git state it updates is the remote-tracking ref of the target branch.

Prints one JSON document on one line. Exit 0 carries `"status": "ok"`. Exit 1 means the Pull Request could not
be read: the document carries `"status": "error"` and a `message`. Exit 2 means an invalid invocation.

The three needs:

- `rebase`: the target branch has commits the checked-out branch lacks.
- `ci`: a check that was not skipped failed, was cancelled, or has not finished.
- `ai_feedback`: an unresolved inline review thread whose reviewer comments all come from bot or app accounts,
  with no reply from the Pull Request author after the latest of them.

`local.relation` says how the checkout relates to the Pull Request head. The needs describe the Pull Request
only when it is `equal`, because the rebase count is measured from the checkout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from typing import Any

SCHEMA_VERSION = 1
LOCAL_TIMEOUT = 60
NETWORK_TIMEOUT = 120
MAX_THREAD_PAGES = 20
PR_FIELDS = "number,url,state,isDraft,baseRefName,headRefName,headRefOid,author"
CHECK_FIELDS = "name,state,bucket,link,workflow"
PASSING_BUCKETS = frozenset({"pass", "skipping"})
FAILING_BUCKETS = frozenset({"fail", "cancel"})
OID_RE = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
PR_URL_RE = re.compile(r"https://(?P<host>[^/\s]+)/(?P<owner>[^/\s]+)/(?P<name>[^/\s]+)/pull/(?P<number>\d+)")
THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          comments(first: 100) {
            pageInfo { hasNextPage }
            nodes { url createdAt isMinimized author { login __typename } }
          }
        }
      }
    }
  }
}
"""

Json = dict[str, Any]


class ShapeError(Exception):
    """The Pull Request could not be read; the message says why."""


def environment() -> dict[str, str]:
    return dict(os.environ, GH_PROMPT_DISABLED="1", GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", NO_COLOR="1")


def run(argv: Sequence[str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    """Run without a shell; a timeout or launch failure becomes exit 124 or 127 with the reason on stderr."""
    try:
        return subprocess.run(
            list(argv), env=environment(), stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(list(argv), 124, b"", f"timed out after {timeout}s".encode())
    except OSError as error:
        return subprocess.CompletedProcess(list(argv), 127, b"", str(error).encode())


def tail(data: bytes) -> str:
    return " ".join(data.decode("utf-8", "replace").split())[-300:]


def git(*args: str) -> str:
    result = run(["git", *args], LOCAL_TIMEOUT)
    if result.returncode != 0:
        raise ShapeError(f"`git {args[0]}` failed: {tail(result.stderr) or f'exit {result.returncode}'}")
    return result.stdout.decode("utf-8", "replace").strip()


def succeeds(*argv: str) -> bool:
    return run(argv, LOCAL_TIMEOUT).returncode == 0


def valid_branch(name: Any) -> bool:
    if not isinstance(name, str) or not name:
        return False
    checked = run(["git", "check-ref-format", "--branch", name], LOCAL_TIMEOUT)
    return checked.returncode == 0 and checked.stdout.decode("utf-8", "replace").strip() == name


def pull_request() -> Json:
    """The open Pull Request for the current branch, with the repository parsed from its URL."""
    result = run(["gh", "pr", "view", "--json", PR_FIELDS], LOCAL_TIMEOUT)
    if result.returncode != 0:
        reason = tail(result.stderr) or f"gh exited {result.returncode}"
        raise ShapeError(f"could not read a Pull Request for the current branch: {reason}")
    try:
        data = json.loads(result.stdout or b"null")
    except ValueError as error:
        raise ShapeError(f"could not parse the Pull Request: {error}") from error
    url = PR_URL_RE.fullmatch(data.get("url") or "") if isinstance(data, dict) else None
    if (
        url is None
        or data.get("number") != int(url["number"])
        or not OID_RE.fullmatch(str(data.get("headRefOid")))
        or not valid_branch(data.get("headRefName"))
        or not valid_branch(data.get("baseRefName"))
    ):
        raise ShapeError("could not parse the Pull Request for the current branch")
    if data.get("state") != "OPEN":
        raise ShapeError(f"Pull Request #{data['number']} is {str(data.get('state')).lower()}, not open")
    author = data.get("author")
    return {
        "number": data["number"],
        "url": data["url"],
        "state": "OPEN",
        "draft": bool(data.get("isDraft")),
        "base": data["baseRefName"],
        "head": data["headRefName"],
        "head_oid": data["headRefOid"],
        "author": author.get("login") if isinstance(author, dict) else None,
        "host": url["host"],
        "owner": url["owner"],
        "name": url["name"],
    }


def local_state(pr_head: str) -> Json:
    """How the checkout relates to the Pull Request head: equal, ahead, behind, diverged, or unknown."""
    head = git("rev-parse", "HEAD")
    if head == pr_head:
        relation = "equal"
    elif not succeeds("git", "cat-file", "-e", f"{pr_head}^{{commit}}"):
        relation = "unknown"
    elif succeeds("git", "merge-base", "--is-ancestor", pr_head, head):
        relation = "ahead"
    elif succeeds("git", "merge-base", "--is-ancestor", head, pr_head):
        relation = "behind"
    else:
        relation = "diverged"
    return {
        "branch": git("branch", "--show-current") or None,
        "head_oid": head,
        "relation": relation,
        "dirty": bool(git("status", "--porcelain")),
    }


def base_state(base: str) -> Json:
    """Fetch the target branch and count its commits the checkout lacks."""
    ref = f"refs/remotes/origin/{base}"
    fetched = run(["git", "fetch", "--quiet", "--no-tags", "origin", f"+refs/heads/{base}:{ref}"], NETWORK_TIMEOUT)
    if fetched.returncode != 0:
        raise ShapeError(f"could not fetch `{base}` from origin: {tail(fetched.stderr) or 'git fetch failed'}")
    return {"ref": f"origin/{base}", "behind": int(git("rev-list", "--count", f"HEAD..{ref}"))}


def classify_checks(rows: list[Any]) -> Json:
    """Group check rows by bucket; a bucket this script does not know counts as pending, never as green."""
    counts = {"pass": 0, "skipping": 0, "fail": 0, "cancel": 0, "pending": 0}
    failing: list[Json] = []
    pending: list[Json] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ShapeError("could not parse the Pull Request checks")
        reported = row.get("bucket")
        bucket = reported if isinstance(reported, str) and reported in counts else "pending"
        counts[bucket] += 1
        if bucket in PASSING_BUCKETS:
            continue
        entry = {key: row.get(key) for key in ("name", "workflow", "link")} | {"bucket": bucket}
        (failing if bucket in FAILING_BUCKETS else pending).append(entry)
    if not rows:
        state = "none"
    elif failing:
        state = "failing"
    elif pending:
        state = "pending"
    else:
        state = "passing"
    return {"state": state, "counts": counts, "failing": failing, "pending": pending}


def checks_state() -> Json:
    """Read the checks by bucket. `gh pr checks` exits 1 on a failure and 8 while pending, so parse first."""
    result = run(["gh", "pr", "checks", "--json", CHECK_FIELDS], LOCAL_TIMEOUT)
    try:
        rows = json.loads(result.stdout) if result.stdout.strip() else None
    except ValueError:
        rows = None
    if rows is None and "no checks reported" in result.stderr.decode("utf-8", "replace"):
        rows = []
    if not isinstance(rows, list):
        reason = tail(result.stderr) or f"gh exited {result.returncode}"
        raise ShapeError(f"could not read the Pull Request checks: {reason}")
    return classify_checks(rows)


def login(comment: Json) -> str | None:
    author = comment.get("author")
    return author.get("login") if isinstance(author, dict) else None


def is_bot(comment: Json) -> bool:
    author = comment.get("author")
    return isinstance(author, dict) and author.get("__typename") == "Bot"


def classify_thread(thread: Json, pr_author: str | None) -> tuple[str, Json | None]:
    """Sort one unresolved thread into `ai`, `human`, `answered`, or `none`; an `ai` thread carries its entry.

    Reviewer feedback is every visible comment the Pull Request author did not write. A thread with any
    feedback from a person is `human`. A thread with more comments than one page holds is treated as open,
    so the reply pass, which reads every comment, makes the final call.
    """
    connection = thread.get("comments") or {}
    comments = [comment for comment in connection.get("nodes") or [] if isinstance(comment, dict)]
    feedback = [c for c in comments if login(c) != pr_author and not c.get("isMinimized")]
    if not feedback:
        return "none", None
    if not all(is_bot(comment) for comment in feedback):
        return "human", None
    latest = max(feedback, key=lambda comment: str(comment.get("createdAt")))
    truncated = bool((connection.get("pageInfo") or {}).get("hasNextPage"))
    answered = any(login(c) == pr_author and str(c.get("createdAt")) > str(latest.get("createdAt")) for c in comments)
    if answered and not truncated:
        return "answered", None
    return "ai", {
        "id": thread.get("id"),
        "path": thread.get("path"),
        "line": thread.get("line"),
        "outdated": bool(thread.get("isOutdated")),
        "reviewer": login(feedback[0]),
        "url": latest.get("url"),
    }


def summarize_threads(threads: list[Json], pr_author: str | None) -> Json:
    summary: Json = {"ai_threads": [], "human_threads": 0, "answered_threads": 0}
    for thread in threads:
        if thread.get("isResolved"):
            continue
        kind, entry = classify_thread(thread, pr_author)
        if entry is not None:
            summary["ai_threads"].append(entry)
        elif kind != "none":
            summary[f"{kind}_threads"] += 1
    return summary


def review_threads(pr: Json) -> list[Json]:
    """Every review thread of the Pull Request, across pages."""
    threads: list[Json] = []
    cursor: str | None = None
    for _ in range(MAX_THREAD_PAGES):
        argv = ["gh", "api", "graphql", "--hostname", pr["host"], "-f", f"owner={pr['owner']}"]
        argv += ["-f", f"name={pr['name']}", "-F", f"number={pr['number']}", "-f", f"query={THREADS_QUERY}"]
        if cursor:
            argv += ["-f", f"cursor={cursor}"]
        result = run(argv, LOCAL_TIMEOUT)
        if result.returncode != 0:
            reason = tail(result.stderr) or f"gh exited {result.returncode}"
            raise ShapeError(f"could not read the review threads: {reason}")
        try:
            page = json.loads(result.stdout)["data"]["repository"]["pullRequest"]["reviewThreads"]
            threads += [node for node in page["nodes"] if isinstance(node, dict)]
            more, cursor = bool(page["pageInfo"]["hasNextPage"]), page["pageInfo"]["endCursor"]
        except (ValueError, KeyError, TypeError) as error:
            raise ShapeError("could not parse the review threads") from error
        if not more:
            return threads
        if not cursor:
            break
    raise ShapeError("could not read every review thread: the Pull Request has too many pages of them")


def snapshot() -> Json:
    pr = pull_request()
    local = local_state(pr["head_oid"])
    base = base_state(pr["base"])
    checks = checks_state()
    review = summarize_threads(review_threads(pr), pr["author"])
    needs = {
        "rebase": base["behind"] > 0,
        "ci": checks["state"] in ("failing", "pending"),
        "ai_feedback": bool(review["ai_threads"]),
    }
    public = ("number", "url", "state", "draft", "base", "head", "head_oid", "author")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "pr": {key: pr[key] for key in public},
        "local": local,
        "base": base,
        "checks": checks,
        "review": review,
        "needs": needs,
        "in_shape": not any(needs.values()),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.parse_args(argv)
    try:
        document, code = snapshot(), 0
    except ShapeError as error:
        document, code = {"schema_version": SCHEMA_VERSION, "status": "error", "message": str(error)}, 1
    print(json.dumps(document, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
