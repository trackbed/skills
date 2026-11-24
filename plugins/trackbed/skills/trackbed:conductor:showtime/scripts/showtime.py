#!/usr/bin/env python3
"""Board, reply, merge, archive-check, and record-nudge helper for trackbed:conductor:showtime.

  python3 showtime.py board --conductor <file> [--state-dir <dir>] [--idle-minutes <n>] [--dry-run]
  python3 showtime.py reply --message-file <file>
  python3 showtime.py merge --conductor <fresh file> --pr <number> --head <oid> [--allow-held] [--state-dir <dir>]
  python3 showtime.py archive-check --conductor <fresh file> --workspace <id> [--state-dir <dir>]
  python3 showtime.py record-nudge --message-id <id> [--state-dir <dir>]

`board` joins the Conductor workspaces and chats the caller saved to a file with the caller's open Pull
Requests and each workspace's Git state. It places every workspace on one stage, plans at most one command
per workspace, lists the Pull Requests that may merge in order, and plans the sidebar sections. It reads
GitHub and Git; the only Git state it updates is the remote-tracking ref of the default branch and
`FETCH_HEAD`. It saves the board and the command counts under the state directory unless `--dry-run`.

`reply` reads one chat message from a file and says whether it is a decision request in the shared format,
and which exact message picks its recommended options. The message is data: it is never run.

`merge` merges one Pull Request with the repository's merge method, pinned to the head commit that the
newest saved board cleared. It refuses a Pull Request the board did not clear, a board older than fifteen
minutes, and a head that moved. It never bypasses branch protection, turns on auto-merge, or deletes a branch.

`archive-check` rechecks one workspace the newest saved board planned to archive: its chats are idle and its
checkout is still clean at the merged head on the same branch. `record-nudge` records a command Conductor
accepted, so the same problem gets at most two.

Each command prints one JSON document on one line. Exit 0 carries `"status": "ok"`. Exit 1 carries
`"status": "error"` with a `message`, or for `merge` the reason nothing merged. Exit 2 is an argparse usage
error; other invalid values exit 1 with `"status": "error"`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Running the helper must leave the installed plugin as it was: no bytecode beside these modules.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import showtime_reads as reads  # noqa: E402
import showtime_requests as replies  # noqa: E402
import showtime_rules as rules  # noqa: E402
from showtime_reads import ShowtimeError, git, read_json, run, tail  # noqa: E402

SCHEMA_VERSION = 2
MAX_BOARD_AGE = 900
MAX_MESSAGE_BYTES = 200_000
DEFAULT_IDLE_MINUTES = 10

Json = dict[str, Any]


def write_json(path: Path, document: Json) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)


def state_dir(given: str | None) -> Path:
    """Where the board and the command counts are kept: `.context/showtime` in the workspace."""
    if given:
        return Path(given)
    root = os.environ.get("CONDUCTOR_WORKSPACE_PATH") or git("rev-parse", "--show-toplevel").strip()
    return Path(root) / ".context" / "showtime"


def pr_summary(pr: Json) -> Json:
    return {key: pr.get(key) for key in ("number", "url", "title", "head_oid")}


def diff_boards(previous: object, rows: list[Json], orphans: list[Json]) -> list[str]:
    """What changed since the saved board, one line per workspace or Pull Request that moved."""
    if not isinstance(previous, dict):
        return ["First pass: there is no earlier board to compare with."]
    changes: list[str] = []
    old = {row["id"]: row for row in previous.get("workspaces") or [] if isinstance(row, dict) and "id" in row}
    for row in rows:
        before = old.pop(row["id"], None)
        if before is None:
            changes.append(f"`{row['name']}` is new: {row['label']}")
        elif before.get("stage") != row["stage"]:
            changes.append(f"`{row['name']}`: {before.get('label')} → {row['label']}")
    changes += [f"`{row.get('name')}` is no longer listed (archived or removed)" for row in old.values()]
    was = {row.get("pr", {}).get("number"): row for row in previous.get("orphans") or [] if isinstance(row, dict)}
    for row in orphans:
        before = was.pop(row["pr"]["number"], None)
        if before is None:
            changes.append(f"#{row['pr']['number']} has no workspace: {row['label']}")
        elif before.get("stage") != row["stage"]:
            changes.append(f"#{row['pr']['number']}: {before.get('label')} → {row['label']}")
    changes += [f"#{number} no longer waits without a workspace" for number in was]
    return changes


def read_nudges(where: Path) -> Json:
    saved = read_json(where / "state.json")
    stored = saved.get("nudges") if isinstance(saved, dict) and saved.get("schema_version") == SCHEMA_VERSION else None
    return stored if isinstance(stored, dict) else {}


def build_board(args: argparse.Namespace, target: int | None = None) -> Json:
    conductor = reads.load_conductor(Path(args.conductor))
    now = datetime.now(timezone.utc)
    repo = reads.repository()
    repo["required_checks"] = reads.required_check_names(repo)
    default = repo["default_branch"]
    base_ref = git("rev-parse", reads.fetch_base(default)).strip()
    open_prs = reads.open_pull_requests(repo["selector"])
    if target is not None:
        open_prs = [pr for pr in open_prs if pr["number"] == target]
    by_branch: dict[str, list[Json]] = {}
    for opened in open_prs:
        by_branch.setdefault(opened["head_branch"], []).append(opened)
    past = reads.past_pull_requests(repo["selector"]) if target is None else {}
    where = state_dir(args.state_dir)
    nudges = read_nudges(where)
    repository_key = repo["name_with_owner"].casefold()
    chats = reads.chats_by_workspace(conductor["sessions"], now)
    notes: list[str] = []
    facts_by_number: dict[int, Json] = {}
    claimed: set[int] = set()
    kept_nudges: Json = {}
    rows: list[Json] = []

    def facts_for(pr: Json) -> Json:
        if pr["number"] not in facts_by_number:
            facts_by_number[pr["number"]] = reads.pr_facts(pr, repo, base_ref)
        return facts_by_number[pr["number"]]

    for ws in sorted(conductor["workspaces"], key=lambda item: str(item["name"])):
        branch = str(ws.get("branch") or "")
        matches = by_branch.get(branch, [])
        if target is not None and not matches:
            continue
        claimed.update(pr["number"] for pr in matches)
        local_matches = [pr for pr in matches if pr["head_repository"] == repository_key]
        matched = min(local_matches, key=lambda pr: (pr["base"] != default, pr["number"]), default=None)
        if ws["id"] == conductor["self_workspace"]:
            notes.extend(f"Pull Request #{pr['number']} belongs to this workspace and is left out." for pr in matches)
            continue
        for extra in matches:
            if extra is not matched:
                notes.append(f"Pull Request #{extra['number']} shares branch {branch!r} and is left out.")
        facts: Json = {
            "state": ws["state"],
            "failure_reason": ws.get("failureReason"),
            "chats": chats.get(ws["id"], []),
        }
        pr: Json | None = None
        result: Json | None = None
        if ws["state"] == "ready":
            try:
                facts["git"] = reads.workspace_git(ws.get("path"), base_ref)
                if facts["git"]["branch"] != branch:
                    del facts["git"]
                    raise ShowtimeError("the checked-out branch differs from the Conductor workspace branch")
            except ShowtimeError as error:
                facts["git_error"] = str(error)
            if matched is not None and "git" in facts:
                try:
                    pr = facts_for(matched)
                except ShowtimeError as error:
                    result = rules.unreadable_pr(matched["number"], str(error))
        if matched is None and matches:
            result = rules.unreadable_pr(matches[0]["number"], "its head repository differs from the workspace origin")
        past_pr = past.get((repository_key, branch, facts["git"]["head"])) if "git" in facts else None
        checkout = facts.get("git")
        if (
            result is None
            and pr is None
            and past_pr is None
            and checkout
            and not checkout["dirty"]
            and checkout["ahead"]
        ):
            # About to plan the creation command: read the branch's own history, which the lists above may miss.
            try:
                history = reads.branch_pull_requests(repo["selector"], branch, repository_key)
            except ShowtimeError as error:
                result = rules.unreadable_history(str(error))
            else:
                past_pr = next((past for past in history if past["head_oid"] == checkout["head"]), None)
                facts["past_elsewhere"] = next(
                    (past for past in history if not reads.contains(str(ws.get("path")), past["head_oid"])), None
                )
        if result is None:
            pace = {"idle_minutes": args.idle_minutes, "now": int(now.timestamp()), "nudge": nudges.get(ws["id"])}
            result = rules.workspace_stage(facts, pr, past_pr, default, pace)
        move = result["move"]
        chat = rules.driving_chat(facts["chats"])
        if move and move["kind"] == "send":
            nudge = result["nudge"]
            identity = json.dumps([ws["id"], move["session_id"], chat and chat["last_message_at"], nudge])
            move.update(message_id=str(uuid.uuid5(uuid.NAMESPACE_OID, identity)), nudge=nudge)
        if result["stage"] in rules.NUDGE_KEEPING_STAGES and ws["id"] in nudges:
            kept_nudges[ws["id"]] = nudges[ws["id"]]
        shown = pr or matched or (past_pr if result["stage"] in ("merged", "pr_closed") else None)
        rows.append(
            {
                "id": ws["id"],
                "name": ws["name"],
                "branch": branch,
                "app_url": ws.get("appUrl"),
                "section_id": ws.get("sectionId"),
                "stage": result["stage"],
                "label": rules.STAGE_LABELS[result["stage"]],
                "group": result["group"],
                "reasons": result["reasons"],
                "move": move,
                "read_tail": bool(result["read_tail"] and chat is not None and chat["state"] == "idle"),
                "chat": chat,
                "pr": pr_summary(shown or matches[0]) if shown or matches else None,
                "holds": [hold["text"] for hold in result.get("holds") or []],
            }
        )
        if pr is not None and pr["checks"]["optional_failing"]:
            failing = rules.listed(pr["checks"]["optional_failing"])
            notes.append(f"#{pr['number']}: checks that are not required are failing: {failing}.")

    orphans: list[Json] = []
    for pr in open_prs:
        if pr["number"] in claimed:
            continue
        try:
            result = rules.orphan_stage(facts_for(pr), default)
        except ShowtimeError as error:
            result = rules.unreadable_pr(pr["number"], str(error))
        orphans.append(
            {
                "pr": pr_summary(pr),
                "stage": result["stage"],
                "label": rules.STAGE_LABELS[result["stage"]],
                "reasons": result["reasons"],
                "holds": [hold["text"] for hold in result.get("holds") or []],
            }
        )

    overlaps = rules.shared_with({number: set(facts["files"]) for number, facts in facts_by_number.items()})
    entries = [(row, row["id"]) for row in rows] + [(row, None) for row in orphans]
    ready = {row["pr"]["number"]: (row, owner) for row, owner in entries if row["stage"] == "merge_ready"}
    train = [
        ready[number][0]["pr"] | {"workspace_id": ready[number][1], "shared_with": overlaps.get(number, [])}
        for number in rules.order_train(ready, overlaps)
    ]
    held = [
        row["pr"] | {"workspace_id": owner, "holds": row["holds"]} for row, owner in entries if row["stage"] == "held"
    ]

    by_key: dict[str, list[str]] = {}
    for row in rows:
        key = rules.issue_key(row["branch"])
        if key:
            by_key.setdefault(key, []).append(row["name"])
    notes += [
        f"{len(names)} workspaces work on {key}: {rules.listed(names)}."
        for key, names in by_key.items()
        if len(names) > 1
    ]
    if len(open_prs) == reads.MAX_PULL_REQUESTS:
        notes.append(f"Only your first {reads.MAX_PULL_REQUESTS} open Pull Requests were read.")
    if repo["merge_method"] is None:
        notes.append("The repository allows no merge method, so nothing can merge.")

    board = {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checked_at_epoch": int(now.timestamp()),
        "dry_run": bool(args.dry_run),
        "idle_minutes": args.idle_minutes,
        "repository": repo,
        "base_oid": base_ref,
        "workspaces": rows,
        "orphans": orphans,
        "train": train if repo["merge_method"] else [],
        "held": held if repo["merge_method"] else [],
        "sections": rules.plan_sections(rows, conductor["sections"], lambda: str(uuid.uuid4())),
        "changes": diff_boards(read_json(where / "board.json"), rows, orphans),
        "notes": notes,
    }
    if not args.dry_run:
        write_json(where / "board.json", board)
        write_json(where / "state.json", {"schema_version": SCHEMA_VERSION, "nudges": kept_nudges})
    return board


def read_reply(args: argparse.Namespace) -> Json:
    path = Path(args.message_file)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ShowtimeError(f"could not read `{path}`: {error}") from error
    if len(data) > MAX_MESSAGE_BYTES:
        raise ShowtimeError(f"`{path}` is larger than {MAX_MESSAGE_BYTES} bytes")
    return {"schema_version": SCHEMA_VERSION, "status": "ok"} | replies.parse_request(data.decode("utf-8", "replace"))


def available_board(board: object) -> str | None:
    if not isinstance(board, dict) or board.get("status") != "ok" or board.get("schema_version") != SCHEMA_VERSION:
        return "there is no saved board; run `board` first"
    if int(time.time()) - int(board.get("checked_at_epoch") or 0) > MAX_BOARD_AGE:
        return "the saved board is older than fifteen minutes; run `board` again"
    return None


def cleared_entry(board: Json, number: int, head: str, allow_held: bool) -> Json | None:
    lists = ["train", "held"] if allow_held else ["train"]
    return next(
        (entry for key in lists for entry in board[key] if entry["number"] == number and entry["head_oid"] == head),
        None,
    )


def record_nudge(args: argparse.Namespace) -> Json:
    where = state_dir(args.state_dir)
    board = read_json(where / "board.json")
    if not isinstance(board, dict) or board.get("schema_version") != SCHEMA_VERSION:
        raise ShowtimeError("there is no saved board for this delivery")
    for row in board["workspaces"]:
        move = row["move"] or {}
        if move.get("message_id") != args.message_id:
            continue
        nudges = read_nudges(where)
        previous = nudges.get(row["id"]) or {}
        if previous.get("message_id") != args.message_id:
            nudges[row["id"]] = move["nudge"] | {"message_id": args.message_id, "at": int(time.time())}
            write_json(where / "state.json", {"schema_version": SCHEMA_VERSION, "nudges": nudges})
        return {"schema_version": SCHEMA_VERSION, "status": "ok", "message_id": args.message_id}
    raise ShowtimeError("the saved board does not contain this delivery")


def archive_check(args: argparse.Namespace) -> Json:
    board = read_json(state_dir(args.state_dir) / "board.json")
    if problem := available_board(board):
        raise ShowtimeError(problem)
    planned = next((row for row in board["workspaces"] if row["id"] == args.workspace), None)
    if not planned or (planned["move"] or {}).get("kind") != "archive":
        raise ShowtimeError("the saved board does not clear this workspace for archiving")
    current = reads.load_conductor(Path(args.conductor))
    workspace = next((row for row in current["workspaces"] if row["id"] == args.workspace), None)
    if not workspace or workspace["state"] != "ready" or workspace["id"] == current["self_workspace"]:
        raise ShowtimeError("the workspace is no longer available for archiving")
    if any(
        session["workspaceId"] == args.workspace and not session.get("archived") and session["state"] != "idle"
        for session in current["sessions"]
    ):
        raise ShowtimeError("the workspace has a chat that is no longer idle")
    checkout = reads.workspace_git(workspace.get("path"), board["base_oid"])
    if checkout["dirty"] or checkout["head"] != planned["pr"]["head_oid"] or checkout["branch"] != planned["branch"]:
        raise ShowtimeError("the workspace checkout changed since the archive plan")
    return {"schema_version": SCHEMA_VERSION, "status": "ok", "workspace": args.workspace}


def merge(args: argparse.Namespace) -> tuple[Json, int]:
    """Recheck one cleared Pull Request and merge it synchronously with its head pinned."""
    where = state_dir(args.state_dir)
    board = read_json(where / "board.json")

    def refused(message: str) -> tuple[Json, int]:
        return {"schema_version": SCHEMA_VERSION, "status": "refused", "pr": args.pr, "message": message}, 1

    if problem := available_board(board):
        return refused(problem)
    approved = cleared_entry(board, args.pr, args.head, args.allow_held)
    if approved is None:
        return refused(f"the saved board does not clear Pull Request #{args.pr} at `{args.head}` for merging")
    fresh = build_board(
        argparse.Namespace(
            conductor=args.conductor, state_dir=args.state_dir, dry_run=True, idle_minutes=board["idle_minutes"]
        ),
        target=args.pr,
    )
    repo = fresh["repository"]
    if repo != board["repository"]:
        return refused("the repository, default branch, or merge method changed")
    current = cleared_entry(fresh, args.pr, args.head, args.allow_held)
    if current is None:
        reasons = next(
            (
                row["reasons"]
                for row in fresh["workspaces"] + fresh["orphans"]
                if row["pr"] and row["pr"]["number"] == args.pr and row["pr"]["head_oid"] == args.head
            ),
            ["it is no longer open at the approved head"],
        )
        return refused(f"Pull Request #{args.pr} no longer passes the merge gate: {'; '.join(reasons)}")
    if current["workspace_id"] != approved["workspace_id"] or current.get("holds") != approved.get("holds"):
        return refused("the workspace or hold reasons changed")
    base = git("ls-remote", "--exit-code", "origin", f"refs/heads/{repo['default_branch']}").split()
    if not base or base[0] != fresh["base_oid"]:
        return refused("the default branch moved during verification")
    if current["workspace_id"] is not None:
        workspaces = reads.load_conductor(Path(args.conductor))["workspaces"]
        workspace = next((row for row in workspaces if row["id"] == current["workspace_id"]), None)
        if workspace is None:
            return refused("the workspace disappeared during verification")
        checkout = reads.workspace_git(workspace.get("path"), fresh["base_oid"])
        if checkout["dirty"] or checkout["head"] != args.head or checkout["branch"] != workspace.get("branch"):
            return refused("the workspace checkout changed during verification")
    if problem := available_board(board):
        return refused(problem)
    method, name, host = repo["merge_method"], repo["name_with_owner"], repo["host"]
    # The synchronous endpoint cannot queue a merge or enable auto-merge.
    command = [
        "gh",
        "api",
        "--hostname",
        host,
        "--method",
        "PUT",
        f"repos/{name}/pulls/{args.pr}/merge",
        "-f",
        f"sha={args.head}",
        "-f",
        f"merge_method={method}",
    ]
    merged = run(command, reads.NETWORK_TIMEOUT)
    document = {"schema_version": SCHEMA_VERSION, "pr": args.pr, "url": current["url"], "method": method}
    try:
        response = json.loads(merged.stdout)
    except ValueError:
        response = None
    if merged.returncode == 0 and isinstance(response, dict) and response.get("merged") is True:
        for key in ("train", "held"):
            board[key] = [entry for entry in board.get(key) or [] if entry.get("number") != args.pr]
        write_json(where / "board.json", board)
        return document | {"status": "ok", "outcome": "merged"}, 0
    message = tail(merged.stderr) or (response.get("message") if isinstance(response, dict) else None)
    if not message:
        message = "GitHub did not confirm a synchronous merge"
    return document | {"status": "failed", "message": message}, 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="showtime.py", description=(__doc__ or "").split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    board = commands.add_parser("board", help="place every workspace on a stage and plan the next moves")
    board.add_argument(
        "--conductor", required=True, help="JSON file with Conductor's workspaces, sessions, and sections"
    )
    board.add_argument("--state-dir", help="where the board and command counts are kept")
    board.add_argument("--idle-minutes", type=int, default=DEFAULT_IDLE_MINUTES, help="how long a chat must be idle")
    board.add_argument("--dry-run", action="store_true", help="save nothing, so nothing can merge from this board")
    reply = commands.add_parser("reply", help="read one chat message as a decision request")
    reply.add_argument("--message-file", required=True, help="file holding the chat's last message")
    merging = commands.add_parser("merge", help="merge one Pull Request the saved board cleared")
    merging.add_argument("--conductor", required=True, help="fresh Conductor records for the merge gate")
    merging.add_argument("--pr", type=int, required=True, help="Pull Request number")
    merging.add_argument("--head", required=True, help="head commit the board saw")
    merging.add_argument("--allow-held", action="store_true", help="also accept a Pull Request the board held")
    merging.add_argument("--state-dir", help="where the board is kept")
    recording = commands.add_parser("record-nudge", help="record a command Conductor accepted")
    recording.add_argument("--message-id", required=True)
    recording.add_argument("--state-dir")
    archiving = commands.add_parser("archive-check", help="recheck one workspace approved for archiving")
    archiving.add_argument("--conductor", required=True)
    archiving.add_argument("--workspace", required=True)
    archiving.add_argument("--state-dir")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "board":
            if args.idle_minutes < 0:
                raise ShowtimeError("`--idle-minutes` must not be negative")
            document, code = build_board(args), 0
        elif args.command == "reply":
            document, code = read_reply(args), 0
        elif args.command == "record-nudge":
            document, code = record_nudge(args), 0
        elif args.command == "archive-check":
            document, code = archive_check(args), 0
        else:
            if not reads.OID_RE.fullmatch(args.head):
                raise ShowtimeError("`--head` must be a full commit id")
            document, code = merge(args)
    except ShowtimeError as error:
        document, code = {"schema_version": SCHEMA_VERSION, "status": "error", "message": str(error)}, 1
    print(json.dumps(document, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
