"""What trackbed:conductor:showtime reads: Conductor's records, GitHub, and Git.

Nothing here writes to GitHub or changes a branch, an index, or a working tree. The only Git state these
functions update is the remote-tracking ref of the default branch and `FETCH_HEAD`. Every `gh pr` call
names the repository, because `gh` searches by the remote's name and finds nothing when the repository was
renamed after the clone.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

PLUGIN_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(PLUGIN_SCRIPTS / "lib"))
sys.path.insert(0, str(PLUGIN_SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_process  # noqa: E402
import risk_classification  # noqa: E402
import risk_patterns  # noqa: E402
import showtime_rules as rules  # noqa: E402
from review_process import run as run, tail as tail  # noqa: E402  # re-exported for showtime.py

LOCAL_TIMEOUT = 60
NETWORK_TIMEOUT = 120
MAX_THREAD_PAGES = 10
MAX_PULL_REQUESTS = 100
MAX_BRANCH_PULL_REQUESTS = 30
RISK_SCRIPT = PLUGIN_SCRIPTS / "risk-signals.py"
REPO_FIELDS = "nameWithOwner,url,defaultBranchRef,squashMergeAllowed,mergeCommitAllowed,rebaseMergeAllowed"
OPEN_FIELDS = (
    "number,title,url,body,headRefName,headRefOid,headRepository,baseRefName,isDraft,mergeable,mergeStateStatus"
)
PAST_FIELDS = "number,url,state,headRefOid,headRefName,headRepository"
MERGE_METHODS = (
    ("squash", "squashMergeAllowed"),
    ("merge", "mergeCommitAllowed"),
    ("rebase", "rebaseMergeAllowed"),
)
PASSING_BUCKETS = frozenset({"pass", "skipping"})
FAILING_BUCKETS = frozenset({"fail", "cancel"})
OID_RE = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
PR_URL_RE = re.compile(r"https://(?P<host>[^/\s]+)/(?P<owner>[^/\s]+)/(?P<name>[^/\s]+)/pull/(?P<number>\d+)")
REMOTE_RE = re.compile(
    r"(?:(?:https?|ssh|git)://(?:[^/@]+@)?|[^/@]+@)(?P<host>[\w.-]+)"
    r"(?::\d+/|[:/])(?P<repo>[\w.-]+/[\w.-]+?)(?:\.git)?/?"
)
DETAILS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewDecision
      author { login }
      comments(last: 100) { nodes { createdAt isMinimized author { login __typename } } }
      reviews(last: 100) { nodes { submittedAt state body author { login __typename } } }
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isResolved
          comments(first: 100) {
            pageInfo { hasNextPage }
            nodes { createdAt isMinimized author { login __typename } }
          }
        }
      }
    }
  }
}
"""

Json = dict[str, Any]


class ShowtimeError(Exception):
    """A read failed or an input was invalid; the message says which."""


def git(*args: str) -> str:
    return review_process.git(*args, error=ShowtimeError, timeout=LOCAL_TIMEOUT)


def gh(*args: str, what: str, verb: str = "read") -> Any:
    return review_process.gh_json(*args, what=what, error=ShowtimeError, timeout=NETWORK_TIMEOUT, verb=verb)


def read_json(path: Path) -> Any:
    """The file's JSON, or None when it is missing or unreadable."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def records(document: Json, key: str, required: Sequence[str]) -> list[Json]:
    """A list of objects from the Conductor file, each holding the named non-empty strings."""
    value = document.get(key)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ShowtimeError(f"`{key}` in the Conductor file must be a list of objects")
    for item in value:
        for field in required:
            if not isinstance(item.get(field), str) or not item[field]:
                raise ShowtimeError(f"an entry of `{key}` in the Conductor file has no `{field}`")
    return value


def load_conductor(path: Path) -> Json:
    """The workspaces, chats, and sections the caller copied from Conductor's tools."""
    document = read_json(path)
    if not isinstance(document, dict):
        raise ShowtimeError(f"could not read the Conductor file `{path}` as a JSON object")
    sections = None if document.get("sections") is None else records(document, "sections", ("id", "name", "kind"))
    this = document.get("self")
    own = this.get("workspaceId") if isinstance(this, dict) else None
    return {
        "workspaces": records(document, "workspaces", ("id", "name", "state")),
        "sessions": records(document, "sessions", ("id", "workspaceId", "agent", "state")),
        "sections": sections,
        "self_workspace": own or os.environ.get("CONDUCTOR_WORKSPACE_ID"),
    }


def minutes_since(stamp: object, now: datetime) -> int:
    """Whole minutes since an ISO time; an unreadable time counts as just now, so nothing is sent on a guess."""
    try:
        then = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return 0
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return max(0, int((now - then).total_seconds() // 60))


def chats_by_workspace(sessions: list[Json], now: datetime) -> dict[str, list[Json]]:
    grouped: dict[str, list[Json]] = {}
    for session in sessions:
        if session.get("archived"):
            continue
        last = session.get("lastMessageAt") or session.get("createdAt")
        chat = {
            "id": session["id"],
            "agent": session["agent"],
            "state": session["state"],
            "last_message_at": last,
            "idle_minutes": minutes_since(last, now),
            "app_url": session.get("appUrl"),
        }
        grouped.setdefault(session["workspaceId"], []).append(chat)
    return grouped


def repository() -> Json:
    # Resolve the repository from the same remote used for base and PR ref fetches.
    origin = REMOTE_RE.fullmatch(git("remote", "get-url", "origin").strip())
    if origin is None:
        raise ShowtimeError("origin does not name a GitHub repository")
    selector = f"{origin['host']}/{origin['repo']}"
    data = gh("repo", "view", selector, "--json", REPO_FIELDS, what="the origin repository")
    name = data.get("nameWithOwner") if isinstance(data, dict) else None
    url = REMOTE_RE.fullmatch(str(data.get("url"))) if isinstance(data, dict) else None
    default = (data.get("defaultBranchRef") or {}).get("name") if isinstance(data, dict) else None
    if url is None or name != url["repo"] or not review_process.valid_branch(default, timeout=LOCAL_TIMEOUT):
        raise ShowtimeError("could not parse the repository")
    method = next((flag for flag, key in MERGE_METHODS if data.get(key)), None)
    return {
        "name_with_owner": name,
        "host": url["host"],
        "selector": f"{url['host']}/{name}",
        "default_branch": default,
        "merge_method": method,
    }


def required_check_names(repo: Json) -> list[str]:
    """The check names that branch rulesets and classic branch protection require on the default branch.

    `gh pr checks --required` lists only the required checks that have reported, so a required check that
    never started would read as no requirement at all. Every name read here gates a merge and counts as
    pending until it reports. Reading classic protection needs admin access; without it GitHub itself enforces
    that protection on the merge, so a refused read adds no names.
    """
    host, name = repo["host"], repo["name_with_owner"]
    branch = quote(repo["default_branch"], safe="")
    names: set[str] = set()
    rules_read = gh(
        "api",
        "--hostname",
        host,
        f"repos/{name}/rules/branches/{branch}?per_page=100",
        what="the default branch's rules",
    )
    for rule in rules_read if isinstance(rules_read, list) else []:
        if isinstance(rule, dict) and rule.get("type") == "required_status_checks":
            for check in (rule.get("parameters") or {}).get("required_status_checks") or []:
                if isinstance(check, dict) and isinstance(check.get("context"), str):
                    names.add(check["context"])
    classic = run(
        ["gh", "api", "--hostname", host, f"repos/{name}/branches/{branch}/protection/required_status_checks"],
        NETWORK_TIMEOUT,
    )
    if classic.returncode != 0:
        reason = tail(classic.stderr)
        if "HTTP 404" in reason or "HTTP 403" in reason:
            return sorted(names)
        raise ShowtimeError(f"could not read the default branch's protection: {reason or 'gh failed'}")
    try:
        data = json.loads(classic.stdout or b"null")
    except ValueError as error:
        raise ShowtimeError("could not parse the default branch's protection") from error
    if isinstance(data, dict):
        names.update(context for context in data.get("contexts") or [] if isinstance(context, str))
        names.update(
            check["context"]
            for check in data.get("checks") or []
            if isinstance(check, dict) and isinstance(check.get("context"), str)
        )
    return sorted(names)


def fetch_base(default_branch: str) -> str:
    """Fetch the default branch and return its remote-tracking ref."""
    ref = f"refs/remotes/origin/{default_branch}"
    refspec = f"+refs/heads/{default_branch}:{ref}"
    fetched = run(["git", "fetch", "--quiet", "--no-tags", "origin", refspec], NETWORK_TIMEOUT)
    if fetched.returncode != 0:
        raise ShowtimeError(
            f"could not fetch `{default_branch}` from origin: {tail(fetched.stderr) or 'git fetch failed'}"
        )
    return ref


def open_pull_requests(name: str) -> list[Json]:
    """The caller's open Pull Requests in the named repository."""
    rows = gh(
        *("pr", "list", "--repo", name, "--author", "@me", "--state", "open"),
        *("--limit", str(MAX_PULL_REQUESTS), "--json", OPEN_FIELDS),
        what="your open Pull Requests",
    )
    found: list[Json] = []
    for row in rows if isinstance(rows, list) else []:
        url = PR_URL_RE.fullmatch(str(row.get("url"))) if isinstance(row, dict) else None
        if url is None or not isinstance(row.get("number"), int) or not OID_RE.fullmatch(str(row.get("headRefOid"))):
            raise ShowtimeError("could not parse your open Pull Requests")
        found.append(
            {
                "number": row["number"],
                "title": str(row.get("title") or ""),
                "url": row["url"],
                "body": str(row.get("body") or ""),
                "head_branch": str(row.get("headRefName") or ""),
                "head_repository": head_repository(row),
                "head_oid": row["headRefOid"],
                "base": str(row.get("baseRefName") or ""),
                "draft": bool(row.get("isDraft")),
                "mergeable": str(row.get("mergeable") or "UNKNOWN"),
                "merge_state": str(row.get("mergeStateStatus") or "UNKNOWN"),
                "host": url["host"],
            }
        )
    return found


def head_repository(row: Json) -> str | None:
    name = (row.get("headRepository") or {}).get("nameWithOwner")
    return name.casefold() if isinstance(name, str) else None


def past_pull_requests(name: str) -> dict[tuple[str, str, str], Json]:
    """The caller's newest merged and closed Pull Requests, keyed by their full head identity."""
    found: dict[tuple[str, str, str], Json] = {}
    for state in ("merged", "closed"):
        rows = gh(
            *("pr", "list", "--repo", name, "--author", "@me", "--state", state),
            *("--limit", str(MAX_PULL_REQUESTS), "--json", PAST_FIELDS),
            what=f"your {state} Pull Requests",
        )
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            repository, branch, head = head_repository(row), row.get("headRefName"), row.get("headRefOid")
            if repository and isinstance(branch, str) and isinstance(head, str):
                past = {"number": row.get("number"), "url": row.get("url"), "state": row.get("state")}
                found.setdefault((repository, branch, head), past | {"head_oid": head})
    return found


def branch_pull_requests(name: str, branch: str, repository: str) -> list[Json]:
    """The caller's merged and closed Pull Requests from one branch of the repository, merged ones first.

    The newest-first lists in `past_pull_requests` stop at a limit, so a workspace about to be sent the
    creation command is looked up by its branch too: a Pull Request that fell out of those lists must not be
    opened a second time.
    """
    rows = gh(
        *("pr", "list", "--repo", name, "--author", "@me", f"--head={branch}", "--state", "all"),
        *("--limit", str(MAX_BRANCH_PULL_REQUESTS), "--json", PAST_FIELDS),
        what=f"your Pull Requests from `{branch}`",
    )
    found: list[Json] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or row.get("state") not in ("MERGED", "CLOSED"):
            continue
        head = row.get("headRefOid")
        if head_repository(row) == repository and row.get("headRefName") == branch and isinstance(head, str):
            found.append({"number": row.get("number"), "url": row.get("url"), "state": row["state"], "head_oid": head})
    return sorted(found, key=lambda past: past["state"] != "MERGED")


def contains(path: str, commit: str) -> bool:
    """Whether the workspace checkout's head contains the commit; an unknown commit counts as not contained."""
    if not OID_RE.fullmatch(commit):
        return False
    probe = ["git", "-C", path, "merge-base", "--is-ancestor", commit, "HEAD"]
    return run(probe, LOCAL_TIMEOUT).returncode == 0


def workspace_git(path: object, base_ref: str) -> Json:
    """The workspace checkout's head, whether it has uncommitted changes, and its commits beyond the default branch."""
    if not isinstance(path, str) or not Path(path).is_dir():
        raise ShowtimeError("the folder is missing")
    return {
        "branch": git("-C", path, "rev-parse", "--abbrev-ref", "HEAD").strip(),
        "head": git("-C", path, "rev-parse", "HEAD").strip(),
        "dirty": bool(git("-C", path, "status", "--porcelain", "--untracked-files=normal").strip()),
        "ahead": int(git("-C", path, "rev-list", "--count", f"{base_ref}..HEAD")),
    }


def ensure_commit(pr: Json) -> None:
    """Make the Pull Request's head commit readable here, fetching it when no worktree holds it."""
    probe = ["git", "cat-file", "-e", f"{pr['head_oid']}^{{commit}}"]
    if run(probe, LOCAL_TIMEOUT).returncode == 0:
        return
    ref = f"refs/pull/{pr['number']}/head"
    fetched = run(["git", "fetch", "--quiet", "--no-tags", "origin", ref], NETWORK_TIMEOUT)
    if run(probe, LOCAL_TIMEOUT).returncode != 0:
        reason = tail(fetched.stderr) or "the fetched ref did not contain it"
        raise ShowtimeError(f"the head commit of Pull Request #{pr['number']} could not be fetched: {reason}")


def check_rows(number: int, required: bool, name: str) -> list[Json]:
    """`gh pr checks` exits 1 on a failure and 8 while pending, so parse the output before the status."""
    argv = ["gh", "pr", "checks", str(number), "--repo", name, "--json", "name,bucket"] + (
        ["--required"] if required else []
    )
    result = run(argv, NETWORK_TIMEOUT)
    try:
        rows = json.loads(result.stdout) if result.stdout.strip() else None
    except ValueError:
        rows = None
    if rows is None and "checks reported" in result.stderr.decode("utf-8", "replace"):
        rows = []
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        reason = tail(result.stderr) or f"gh exited {result.returncode}"
        raise ShowtimeError(f"could not read the checks of Pull Request #{number}: {reason}")
    return rows


def checks_facts(number: int, name: str, required_names: Sequence[str] = ()) -> Json:
    """The state of the checks that gate a merge: the required ones, or all of them when none is required.

    A bucket this script does not know counts as pending, never as green, and so does a required check name
    with no reported run.
    """
    every = check_rows(number, False, name)
    required = check_rows(number, True, name) if every else []
    names = set(required_names) | {str(row.get("name")) for row in required}
    gating = [row for row in every if str(row.get("name")) in names] if names else every
    missing = names - {str(row.get("name")) for row in every}
    failing = sorted({str(row.get("name")) for row in gating if row.get("bucket") in FAILING_BUCKETS})
    pending = sorted(
        {str(row.get("name")) for row in gating if row.get("bucket") not in PASSING_BUCKETS | FAILING_BUCKETS} | missing
    )
    gating_names = {str(row.get("name")) for row in gating}
    optional = {str(row.get("name")) for row in every if row.get("bucket") in FAILING_BUCKETS} - gating_names
    state = "none" if not gating and not missing else "failing" if failing else "pending" if pending else "passing"
    return {
        "state": state,
        "required": bool(names),
        "count": len(gating),
        "failing": failing,
        "pending": pending,
        "optional_failing": sorted(optional),
    }


def review_facts(pr: Json, repo: Json) -> Json:
    """The Pull Request's open review threads and the feedback people left outside them."""
    owner, _, name = repo["name_with_owner"].partition("/")
    threads: list[Json] = []
    first: Json | None = None
    cursor: str | None = None
    for _ in range(MAX_THREAD_PAGES):
        argv = ["api", "graphql", "--hostname", pr["host"], "-f", f"owner={owner}", "-f", f"name={name}"]
        argv += ["-F", f"number={pr['number']}", "-f", f"query={DETAILS_QUERY}"]
        if cursor:
            argv += ["-f", f"cursor={cursor}"]
        data = gh(*argv, what=f"the reviews of Pull Request #{pr['number']}")
        try:
            node = data["data"]["repository"]["pullRequest"]
            page = node["reviewThreads"]
            threads += [thread for thread in page["nodes"] if isinstance(thread, dict)]
            more, cursor = bool(page["pageInfo"]["hasNextPage"]), page["pageInfo"]["endCursor"]
        except (KeyError, TypeError) as error:
            raise ShowtimeError(f"could not parse the reviews of Pull Request #{pr['number']}") from error
        first = first or node
        if not more:
            break
    else:
        raise ShowtimeError(f"Pull Request #{pr['number']} has too many pages of review threads to read")
    author = (first.get("author") or {}).get("login") if first else None

    def nodes(key: str) -> list[Json]:
        connection = (first or {}).get(key) or {}
        return [node for node in connection.get("nodes") or [] if isinstance(node, dict)]

    decision = first.get("reviewDecision") if first else None
    return {
        "threads": rules.summarize_threads(threads, author),
        "feedback": rules.feedback_facts(decision, nodes("comments"), nodes("reviews"), author),
    }


def is_shared(path: str) -> bool:
    is_ci, is_manifest = risk_classification.is_ci_path, risk_classification.is_manifest
    shared: bool = rules.is_shared_path(path, is_ci, is_manifest, risk_patterns.LOCKFILES)
    return shared


def stale_facts(pr: Json, base_ref: str) -> tuple[list[str], Json]:
    """The Pull Request's files, and whether a later merge to the base makes its checks stale.

    Checks run on a commit, so every commit that reached the base after the Pull Request's head commit was
    made counts as untested with it. The checks are stale when such a commit touches a file the Pull
    Request changes, CI configuration, a lockfile, or shared build tooling.
    """
    head = pr["head_oid"]
    made = git("show", "-s", "--format=%cI", head).strip()
    log = git(
        "log",
        "--first-parent",
        "--diff-merges=first-parent",
        f"--since-as-filter={made}",
        "--format=",
        "--name-only",
        "--no-renames",
        f"{head}..{base_ref}",
    )
    moved = sorted({line for line in log.splitlines() if line})
    files = sorted(
        {line for line in git("diff", "--no-renames", "--name-only", f"{base_ref}...{head}").splitlines() if line}
    )
    overlap = sorted(set(moved) & set(files))
    shared = [path for path in moved if is_shared(path)]
    return files, {"stale": bool(overlap or shared), "overlap": overlap, "shared": shared, "moved": len(moved)}


def risk_facts(pr: Json, base_ref: str) -> Json:
    """The deterministic risk floor of the Pull Request's diff, or the reason it could not be computed."""
    try:
        merge_base = git("merge-base", base_ref, pr["head_oid"]).strip()
    except ShowtimeError as error:
        return {"error": str(error)}
    argv = [
        sys.executable,
        str(RISK_SCRIPT),
        "--merge-base",
        merge_base,
        "--head",
        pr["head_oid"],
        "--policy-rev",
        base_ref,
    ]
    result = run(argv, LOCAL_TIMEOUT)
    if result.returncode != 0:
        return {"error": tail(result.stderr) or f"risk-signals.py exited {result.returncode}"}
    try:
        report = json.loads(result.stdout)
    except ValueError:
        return {"error": "risk-signals.py printed no JSON"}
    floor = report.get("floor") if isinstance(report, dict) else None
    if floor not in ("low", "medium", "high"):
        return {"error": "risk-signals.py printed an unexpected report"}
    signals = [signal.get("id") for signal in report.get("signals") or [] if signal.get("level") == "high"]
    return {"floor": floor, "signals": [str(signal) for signal in signals]}


def pr_facts(pr: Json, repo: Json, base_ref: str) -> Json:
    """Everything the rules need about one open Pull Request. The risk floor is read only once it has no blocker."""
    ensure_commit(pr)
    files, stale = stale_facts(pr, base_ref)
    facts = (
        pr
        | {
            "checks": checks_facts(pr["number"], repo["selector"], repo.get("required_checks") or ()),
            "stale": stale,
            "files": files,
        }
        | review_facts(pr, repo)
    )
    if not rules.pr_blockers(facts, repo["default_branch"]):
        facts["risk"] = risk_facts(pr, base_ref)
    return facts
