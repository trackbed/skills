"""Rules for trackbed:conductor:showtime: where a workspace stands, what may merge, and what to send.

Every function here is pure. `showtime.py` reads Conductor's records, GitHub, and Git, and hands the facts
to these rules, so the stages, the merge gate, the hold rules, and the sidebar plan can be tested without a
repository, a network, or Conductor.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import PurePosixPath
from typing import Any

Json = dict[str, Any]

GROUP_WORKING = "working"
GROUP_NEEDS_ME = "needs_me"
GROUP_NUDGE = "nudge"
GROUP_MERGE_READY = "merge_ready"
GROUP_MERGED = "merged"
# The sidebar sections showtime owns, one per group.
SECTION_NAMES = {
    GROUP_WORKING: "Working",
    GROUP_NEEDS_ME: "Needs me",
    GROUP_NUDGE: "Needs a nudge",
    GROUP_MERGE_READY: "Merge-ready",
    GROUP_MERGED: "Merged",
}
# The only messages showtime starts work with. Claude Code expands the hyphenated id; Codex reads the mention.
# `pr:create/references/showtime-handoff.md` verifies the creation command by these exact strings.
COMMANDS = {
    "create": {"claude": "/trackbed:pr-create --showtime", "codex": "$trackbed:pr:create --showtime"},
    "shape-up": {"claude": "/trackbed:pr-shape-up", "codex": "$trackbed:pr:shape-up"},
}
# How each stage reads in a report.
STAGE_LABELS = {
    "setup_failed": "Setup failed",
    "starting": "Starting",
    "unreadable": "Folder unreadable",
    "working": "Agent working",
    "waiting": "Agent needs you",
    "chat_error": "Chat stopped on an error",
    "merged": "Merged",
    "pr_closed": "Pull Request closed",
    "past_pr_elsewhere": "Branch behind a past PR",
    "uncommitted": "Idle with uncommitted changes",
    "empty": "Nothing to ship",
    "work_done_no_pr": "Work done, no PR",
    "no_chat": "No chat",
    "agent_unsupported": "Agent cannot run trackbed skills",
    "nudge_limit": "Nudged twice, still stuck",
    "out_of_sync": "Checkout differs from the PR",
    "pr_not_in_shape": "PR not in shape",
    "checks_running": "Checks running",
    "human_review": "Human review open",
    "draft": "Draft PR",
    "stacked": "Stacked PR",
    "no_checks": "No checks",
    "threads_open": "Review threads unresolved",
    "review_required": "Review required",
    "protected": "Blocked by branch protection",
    "unpublished": "Uncommitted changes beside a ready PR",
    "held": "Held",
    "merge_ready": "Merge-ready",
    "orphan_blocked": "PR with no workspace, not ready",
    "unreadable_pr": "PR could not be read",
}
NUDGE_LIMIT = 2
# What `trackbed:pr:shape-up` can clear from the workspace's own chat.
SHAPEABLE = ("conflict", "behind", "checks_failing", "stale", "ai_threads")
# Stages during which a command's count is kept. None of them shows the problem was fixed, so a problem that
# comes back after a running chat, a prompt, an error, or a failed read continues its count.
NUDGE_KEEPING_STAGES = frozenset(
    {
        "working",
        "waiting",
        "chat_error",
        "unreadable",
        "unreadable_pr",
        "out_of_sync",
        "checks_running",
        "work_done_no_pr",
        "pr_not_in_shape",
        "nudge_limit",
    }
)
CHAT_PRIORITY = {"running": 0, "waiting_for_user": 1, "error": 2, "idle": 3}
MAX_LISTED = 5

BUILD_TOOL_NAMES = frozenset(
    ".node-version .nvmrc .python-version .ruby-version .tool-versions CMakeLists.txt Dockerfile GNUmakefile "
    "Justfile Makefile Taskfile.yaml Taskfile.yml justfile lerna.json makefile nx.json pnpm-workspace.yaml "
    "rush.json turbo.json".split()
)
BREAKING_TITLE_RE = re.compile(r"^[A-Za-z]+(?:\([^)]*\))?!:")
BREAKING_FOOTER_RE = re.compile(r"(?m)^BREAKING[ -]CHANGE:")
ISSUE_KEY_RE = re.compile(r"(?:^|/)([a-z][a-z0-9]{1,9}-\d+)(?=-|$)")


def listed(items: Iterable[str]) -> str:
    """Up to five items in backticks, then how many more there are."""
    values = list(items)
    shown = ", ".join(f"`{item}`" for item in values[:MAX_LISTED])
    return shown if len(values) <= MAX_LISTED else f"{shown}, and {len(values) - MAX_LISTED} more"


def is_shared_path(
    path: str, is_ci_path: Callable[[str], bool], is_manifest: Callable[[str], bool], lockfiles: frozenset[str]
) -> bool:
    """Whether a path is CI configuration, a lockfile, or shared build tooling: a change there can break any branch."""
    name = PurePosixPath(path).name
    return is_ci_path(path) or name in lockfiles or is_manifest(name) or name in BUILD_TOOL_NAMES


def breaking_change(title: str, body: str) -> bool:
    """A Conventional Commits breaking marker: `!` before the title's colon, or a `BREAKING CHANGE:` footer."""
    return bool(BREAKING_TITLE_RE.match(title) or BREAKING_FOOTER_RE.search(body))


def issue_key(branch: str) -> str | None:
    """A tracker key that starts a segment of the branch name, such as `SKILLS-147` from `me/skills-147-fix`."""
    match = ISSUE_KEY_RE.search(branch.lower())
    return match.group(1).upper() if match else None


def driving_chat(chats: list[Json]) -> Json | None:
    """The chat that decides the workspace's stage: running first, then waiting, then errored, then the most recent."""
    recent_first = sorted(chats, key=lambda chat: str(chat.get("last_message_at") or ""), reverse=True)
    ranked = sorted(recent_first, key=lambda chat: CHAT_PRIORITY.get(str(chat.get("state")), 3))
    return ranked[0] if ranked else None


def _login(node: Json) -> str | None:
    author = node.get("author")
    return author.get("login") if isinstance(author, dict) else None


def _is_bot(node: Json) -> bool:
    author = node.get("author")
    return isinstance(author, dict) and author.get("__typename") == "Bot"


def summarize_threads(threads: list[Json], pr_author: str | None) -> Json:
    """Count the unresolved review threads by who must act, as `trackbed:pr:shape-up` sorts them.

    `ai` threads hold only bot feedback the author has not answered, so shape-up can clear them. A thread
    with any feedback from a person is `human`. `answered` threads wait for someone to resolve them.
    `unclassified` threads hold no visible feedback but the author's, and also wait to be resolved.
    """
    counts = {"ai": 0, "human": 0, "answered": 0, "unclassified": 0}
    for thread in threads:
        if thread.get("isResolved"):
            continue
        connection = thread.get("comments") or {}
        comments = [node for node in connection.get("nodes") or [] if isinstance(node, dict)]
        feedback = [node for node in comments if _login(node) != pr_author and not node.get("isMinimized")]
        if not feedback:
            counts["unclassified"] += 1
            continue
        if not all(_is_bot(node) for node in feedback):
            counts["human"] += 1
            continue
        latest = max(str(node.get("createdAt")) for node in feedback)
        truncated = bool((connection.get("pageInfo") or {}).get("hasNextPage"))
        answered = any(_login(node) == pr_author and str(node.get("createdAt")) > latest for node in comments)
        counts["answered" if answered and not truncated else "ai"] += 1
    return counts


def feedback_facts(decision: str | None, comments: list[Json], reviews: list[Json], pr_author: str | None) -> Json:
    """Feedback from people outside review threads that the author has not answered since.

    A person's comment on the Pull Request, or a review with a body, counts until the author comments, or
    submits a review with a body, after it. An author review with no body is the carrier of a thread reply,
    such as one `trackbed:pr:shape-up` posts to a bot, so it answers no person. A person whose latest review
    requests changes holds the Pull Request however the author answered, until that review is dismissed or
    followed by an approval. Bots never count here.
    """

    def is_person(node: Json) -> bool:
        author = node.get("author")
        return isinstance(author, dict) and author.get("__typename") == "User" and author.get("login") != pr_author

    answered_at = max(
        [str(node["createdAt"]) for node in comments if _login(node) == pr_author and node.get("createdAt")]
        + [
            str(node["submittedAt"])
            for node in reviews
            if _login(node) == pr_author and node.get("submittedAt") and str(node.get("body") or "").strip()
        ],
        default="",
    )
    latest: dict[str, tuple[str, str]] = {}
    for node in reviews:
        if is_person(node) and node.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            login, at = str(_login(node)), str(node.get("submittedAt"))
            if at >= latest.get(login, ("", ""))[0]:
                latest[login] = (at, str(node["state"]))
    requesting = sorted(login for login, (_, state) in latest.items() if state == "CHANGES_REQUESTED")
    people: set[str] = set()
    for node in comments:
        if is_person(node) and not node.get("isMinimized") and str(node.get("createdAt")) > answered_at:
            people.add(str(_login(node)))
    for node in reviews:
        asks = node.get("state") == "CHANGES_REQUESTED" or (
            node.get("state") in ("APPROVED", "COMMENTED") and str(node.get("body") or "").strip()
        )
        if is_person(node) and asks and str(node.get("submittedAt")) > answered_at:
            people.add(str(_login(node)))
    return {
        "changes_requested": decision == "CHANGES_REQUESTED" or bool(requesting),
        "requested_by": requesting,
        "review_required": decision == "REVIEW_REQUIRED",
        "unanswered": sorted(people),
    }


def pr_blockers(pr: Json, default_branch: str) -> list[Json]:
    """Everything that keeps an open Pull Request from the merge gate, each as a code and a sentence part."""
    found: list[Json] = []

    def add(code: str, text: str) -> None:
        found.append({"code": code, "text": text})

    checks, threads, stale = pr["checks"], pr["threads"], pr["stale"]
    if pr["mergeable"] == "CONFLICTING":
        add("conflict", f"it conflicts with `{pr['base']}`")
    if pr.get("merge_state") == "BEHIND":
        add("behind", f"it is behind `{pr['base']}`, which branch protection requires it to be up to date with")
    if checks["state"] == "failing":
        add("checks_failing", f"required checks failing: {listed(checks['failing'])}")
    if stale["stale"]:
        touched = stale["overlap"] or stale["shared"]
        add("stale", f"its checks are stale: {listed(touched)} changed on `{pr['base']}` since its head commit")
    if threads["ai"]:
        add("ai_threads", f"{threads['ai']} open thread(s) from AI reviewers")
    if threads["human"]:
        add("human_threads", f"{threads['human']} open thread(s) from people")
    if checks["state"] == "pending":
        add("checks_pending", f"required checks still running: {listed(checks['pending'])}")
    if pr["mergeable"] == "UNKNOWN":
        add("mergeable_unknown", "GitHub is still working out whether it can merge")
    if pr["draft"]:
        add("draft", "it is a draft")
    if pr["base"] != default_branch:
        add(
            "stacked",
            f"its base is `{pr['base']}`, not `{default_branch}`; showtime does not merge stacked Pull Requests",
        )
    if checks["state"] == "none":
        add("no_checks", "no checks reported on its head commit")
    unresolved = threads["answered"] + threads["unclassified"]
    if unresolved:
        add("threads_open", f"{unresolved} other review thread(s) are still unresolved")
    if pr["feedback"].get("review_required"):
        add("review_required", "it needs an approving review before it can merge")
    if pr.get("merge_state") == "BLOCKED" and not found:
        add("protected", "GitHub reports that branch protection blocks the merge")
    return found


def pr_stage(blockers: list[Json]) -> str:
    """The stage an open Pull Request's blockers put it on, or `gate_passed` when it has none."""
    codes = {blocker["code"] for blocker in blockers}
    if codes & set(SHAPEABLE):
        return "pr_not_in_shape"
    if "human_threads" in codes:
        return "human_review"
    if codes & {"checks_pending", "mergeable_unknown"}:
        return "checks_running"
    for code in ("draft", "stacked", "no_checks", "threads_open", "review_required", "protected"):
        if code in codes:
            return code
    return "gate_passed"


def pr_holds(pr: Json) -> list[Json]:
    """The hold rules a Pull Request matches after it passed the gate; a held one is never merged unattended.

    Call it only for a Pull Request with no blocker: the risk report is read only then, so a missing `risk`
    on any other Pull Request would read as a risk that could not be computed.
    """
    holds: list[Json] = []
    risk, feedback = pr.get("risk"), pr["feedback"]
    if not isinstance(risk, dict) or risk.get("error"):
        reason = risk.get("error") if isinstance(risk, dict) else "no risk report"
        holds.append({"code": "risk_unknown", "text": f"its risk tier could not be computed ({reason})"})
    elif risk.get("floor") == "high":
        holds.append(
            {"code": "risk_high", "text": f"risk signals report a high tier: {listed(risk.get('signals') or [])}"}
        )
    if breaking_change(str(pr.get("title") or ""), str(pr.get("body") or "")):
        holds.append({"code": "breaking_change", "text": "its title or description marks a breaking change"})
    if feedback["changes_requested"]:
        who = listed(feedback.get("requested_by") or []) or "a reviewer"
        holds.append({"code": "person_feedback", "text": f"{who} requested changes"})
    elif feedback["unanswered"]:
        holds.append({"code": "person_feedback", "text": f"unanswered feedback from {listed(feedback['unanswered'])}"})
    return holds


def next_nudge(signature: str, pace: Json) -> Json | None:
    """Propose the next delivery, or return None when the same problem already got two."""
    previous = pace.get("nudge")
    count = int(previous["count"]) if isinstance(previous, dict) and previous.get("signature") == signature else 0
    return None if count >= NUDGE_LIMIT else {"signature": signature, "count": count + 1}


def _result(stage: str, group: str | None, reasons: list[str], **extra: Any) -> Json:
    return {"stage": stage, "group": group, "reasons": reasons, "move": None, "read_tail": False} | extra


def _send(command: str, signature: str, chat: Json | None, pace: Json, reasons: list[str], stage: str) -> Json:
    """Plan one command for an idle chat, or say why it does not go out."""
    if chat is None:
        return _result("no_chat", GROUP_NEEDS_ME, [*reasons, "the workspace has no chat to send a command to"])
    if chat.get("agent") not in COMMANDS[command]:
        text = f"its chat runs `{chat.get('agent')}`, which cannot run trackbed skills"
        return _result("agent_unsupported", GROUP_NEEDS_ME, [*reasons, text])
    counted = next_nudge(signature, pace)
    if counted is None:
        text = f"`trackbed:pr:{command}` was sent {NUDGE_LIMIT} times for the same problem"
        return _result("nudge_limit", GROUP_NEEDS_ME, [*reasons, text], read_tail=True)
    waited, needed = int(chat.get("idle_minutes") or 0), int(pace["idle_minutes"])
    previous = pace.get("nudge")
    if isinstance(previous, dict) and previous.get("signature") == signature:
        waited = min(waited, max(0, (int(pace["now"]) - int(previous["at"])) // 60))
    if waited < needed:
        move = {"kind": "wait", "command": command, "minutes_left": needed - waited}
        return _result(stage, GROUP_NUDGE, reasons, move=move)
    move = {"kind": "send", "command": command, "session_id": chat["id"], "message": COMMANDS[command][chat["agent"]]}
    return _result(stage, GROUP_NUDGE, reasons, move=move, nudge=counted, read_tail=True)


def workspace_stage(ws: Json, pr: Json | None, past_pr: Json | None, default_branch: str, pace: Json) -> Json:
    """Place one workspace on exactly one stage and name its next move.

    `pr` is the open Pull Request on the workspace's branch. `past_pr` is the merged or closed Pull Request whose
    head repository, branch, and head match the checkout; a merged one wins over a closed one. `ws` may carry
    `past_elsewhere`, a merged or closed Pull Request on the branch whose head the checkout does not contain.
    `pace` holds `idle_minutes`, the time as `now`, and the workspace's saved command count as `nudge`.
    The result holds `stage`, `group`, `reasons`, `move`, and `read_tail`, plus `nudge` when a command is
    planned, and `blockers` and `holds` when the Pull Request reached the gate.
    """
    state, git, chats = ws.get("state"), ws.get("git"), ws.get("chats") or []
    if state == "failed":
        return _result(
            "setup_failed", GROUP_NEEDS_ME, [f"setup failed: {ws.get('failure_reason') or 'no reason given'}"]
        )
    if state in ("initializing", "setting_up"):
        return _result("starting", GROUP_WORKING, ["Conductor is still setting the workspace up"])
    if not isinstance(git, dict):
        return _result(
            "unreadable", GROUP_NEEDS_ME, [f"its folder could not be read: {ws.get('git_error') or 'unknown error'}"]
        )
    chat = driving_chat(chats)
    if chat is not None and chat.get("state") == "running":
        return _result("working", GROUP_WORKING, ["its chat is running"])
    if chat is not None and chat.get("state") == "waiting_for_user":
        return _result("waiting", GROUP_NEEDS_ME, ["its chat waits on a dialog or a permission prompt in Conductor"])
    if chat is not None and chat.get("state") == "error":
        return _result("chat_error", GROUP_NEEDS_ME, ["its chat stopped on an error"])

    head, dirty, ahead = git["head"], bool(git["dirty"]), int(git["ahead"])
    if pr is None and past_pr is not None and past_pr["head_oid"] == head:
        if past_pr["state"] != "MERGED":
            return _result(
                "pr_closed", GROUP_NEEDS_ME, [f"Pull Request #{past_pr['number']} was closed without merging"]
            )
        if dirty:
            reasons = [f"Pull Request #{past_pr['number']} is merged, but the workspace has uncommitted changes"]
            return _result("merged", GROUP_MERGED, reasons)
        return _result(
            "merged", GROUP_MERGED, [f"Pull Request #{past_pr['number']} is merged"], move={"kind": "archive"}
        )

    if pr is None:
        if dirty:
            return _result(
                "uncommitted", GROUP_NEEDS_ME, ["idle with uncommitted changes and no Pull Request"], read_tail=True
            )
        if ahead == 0:
            return _result("empty", None, ["nothing to ship: no commits beyond the default branch"], read_tail=True)
        elsewhere = ws.get("past_elsewhere")
        if isinstance(elsewhere, dict):
            verb = "merged" if elsewhere.get("state") == "MERGED" else "closed"
            text = (
                f"Pull Request #{elsewhere['number']} on this branch was {verb} at a commit this checkout does not"
                " contain; pull the branch, or start new work on a new branch"
            )
            return _result("past_pr_elsewhere", GROUP_NEEDS_ME, [text], read_tail=True)
        reasons = [f"{ahead} commit(s) ahead of `{default_branch}` and no Pull Request"]
        return _send("create", "create", chat, pace, reasons, "work_done_no_pr")

    if pr["head_oid"] != head:
        text = f"its checkout is not at the head of Pull Request #{pr['number']}; push or pull the branch first"
        return _result("out_of_sync", GROUP_NEEDS_ME, [text], read_tail=True)
    blockers = pr_blockers(pr, default_branch)
    reasons = [blocker["text"] for blocker in blockers]
    stage = pr_stage(blockers)
    if stage == "pr_not_in_shape":
        codes = sorted(blocker["code"] for blocker in blockers if blocker["code"] in SHAPEABLE)
        planned = _send("shape-up", "shape-up:" + ",".join(codes), chat, pace, reasons, stage)
        return planned | {"blockers": blockers}
    if stage == "checks_running":
        return _result(stage, GROUP_WORKING, reasons, blockers=blockers)
    if stage != "gate_passed":
        return _result(stage, GROUP_NEEDS_ME, reasons, blockers=blockers, read_tail=True)
    if dirty:
        text = "the workspace has uncommitted changes, so its Pull Request may not be the whole work"
        return _result("unpublished", GROUP_NEEDS_ME, [text], blockers=[], read_tail=True)
    holds = pr_holds(pr)
    if holds:
        return _result("held", GROUP_NEEDS_ME, [hold["text"] for hold in holds], blockers=[], holds=holds)
    return _result("merge_ready", GROUP_MERGE_READY, ["it passes the merge gate"], blockers=[], holds=[])


def unreadable_pr(number: int, reason: str) -> Json:
    """The stage of a Pull Request whose checks or reviews could not be read: nothing is sent and nothing merges."""
    return _result("unreadable_pr", GROUP_NEEDS_ME, [f"Pull Request #{number} could not be read: {reason}"])


def unreadable_history(reason: str) -> Json:
    """The stage of a workspace whose branch history could not be read, so the creation command is not planned."""
    return _result("unreadable_pr", GROUP_NEEDS_ME, [f"the Pull Requests from its branch could not be read: {reason}"])


def orphan_stage(pr: Json, default_branch: str) -> Json:
    """Place an open Pull Request that has no live workspace: it can join the merge train but cannot be nudged."""
    blockers = pr_blockers(pr, default_branch)
    if blockers:
        reasons = [blocker["text"] for blocker in blockers]
        return _result(
            "orphan_blocked", None, [*reasons, "it has no workspace, so no command can be sent"], blockers=blockers
        )
    holds = pr_holds(pr)
    if holds:
        return _result("held", None, [hold["text"] for hold in holds], blockers=[], holds=holds)
    return _result("merge_ready", None, ["it passes the merge gate"], blockers=[], holds=[])


def shared_with(files_by_pr: dict[int, set[str]]) -> dict[int, list[int]]:
    """For each open Pull Request, the other open ones that change at least one of its files."""
    return {
        number: sorted(other for other, theirs in files_by_pr.items() if other != number and files & theirs)
        for number, files in files_by_pr.items()
    }


def order_train(numbers: Iterable[int], overlaps: dict[int, list[int]]) -> list[int]:
    """Merge order: the fewest overlapping open Pull Requests first, then the lowest number."""
    return sorted(numbers, key=lambda number: (len(overlaps.get(number, [])), number))


def plan_sections(rows: list[Json], sections: list[Json] | None, new_id: Callable[[], str]) -> Json | None:
    """Which sidebar sections to create and which workspaces to move into them.

    A workspace moves only when it is in no section or already in one of showtime's five. One the user
    placed in a section of their own stays where it is. A pinned workspace may still be planned; Conductor
    refuses that move with `forbidden`.
    """
    if sections is None:
        return None
    by_name = {section["name"]: section["id"] for section in sections if section.get("kind") == "custom"}
    ours = {by_name[name] for name in SECTION_NAMES.values() if name in by_name}
    create: list[Json] = []
    moves: dict[str, Json] = {}
    left: list[str] = []
    for row in rows:
        group, current = row.get("group"), row.get("section_id")
        if group is None:
            continue
        if current is not None and current not in ours:
            left.append(str(row["name"]))
            continue
        name = SECTION_NAMES[group]
        if name not in by_name:
            by_name[name] = new_id()
            create.append({"name": name, "section_id": by_name[name]})
        target = by_name[name]
        if current != target:
            moves.setdefault(target, {"section_id": target, "name": name, "workspace_ids": []})["workspace_ids"].append(
                row["id"]
            )
    return {"create": create, "moves": list(moves.values()), "left_in_place": left}
