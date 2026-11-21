#!/usr/bin/env python3
"""Freeze stack leases before rewrites and publish explicit refs atomically."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def command(*args: str, cwd: str | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode:
        raise ValueError(f"{args[0]} {args[1]} failed (exit {result.returncode}): {result.stderr.strip()}")
    return result.stdout.strip()


def branch(value: Any) -> str:
    if not isinstance(value, str) or value.startswith("-"):
        raise ValueError("Invalid stack branch name")
    command("git", "check-ref-format", f"refs/heads/{value}")
    return value


def oid(value: Any, *, absent: bool = False) -> str:
    if absent and value == "":
        return ""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
        raise ValueError("Invalid commit ID")
    return value


def inventory() -> list[str]:
    view = json.loads(command("gh", "stack", "view", "--json"))
    rows = view["branches"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Missing stack inventory")
    for row in rows:
        if not isinstance(row, dict) or any(type(row.get(key, False)) is not bool for key in ("isMerged", "isQueued")):
            raise ValueError("Invalid stack branch state")
        branch(row["name"])
    names = [row["name"] for row in rows if not row.get("isMerged", False) and not row.get("isQueued", False)]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate stack branch")
    return names


def repository() -> str:
    return str(Path(command("git", "rev-parse", "--git-common-dir")).resolve())


def remote_heads(endpoint: str, names: list[str]) -> dict[str, str]:
    if not names:
        return {}
    output = command("git", "ls-remote", "--refs", "--", endpoint, *(f"refs/heads/{name}" for name in names))
    heads = dict.fromkeys(names, "")
    for line in output.splitlines():
        commit, ref = line.split("\t")
        name = ref.removeprefix("refs/heads/")
        if name not in heads or heads[name]:
            raise ValueError("Unexpected remote branch observation")
        heads[name] = oid(commit)
    return heads


def capture(state_file: Path, remote: str) -> None:
    names = inventory()
    if not remote or remote.startswith("-") or any(c.isspace() for c in remote):
        raise ValueError("Invalid remote name")
    endpoints = command("git", "remote", "get-url", "--push", "--all", remote).splitlines()
    if len(endpoints) != 1 or not endpoints[0] or endpoints[0].startswith("-"):
        raise ValueError("Stack publication requires exactly one push endpoint")
    endpoint = endpoints[0]
    if ":" not in endpoint:
        endpoint = str(Path(endpoint).resolve())
    local = {name: oid(command("git", "rev-parse", "--verify", f"refs/heads/{name}^{{commit}}")) for name in names}
    state = {
        "schema": 1,
        "repository": repository(),
        "endpoint": endpoint,
        "branches": names,
        "expected": remote_heads(endpoint, names),
        "local": local,
    }
    # Exclusive creation keeps retries from silently refreshing a safety snapshot.
    with os.fdopen(os.open(state_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as output:
        json.dump(state, output, indent=2)
        output.write("\n")


def load(state_file: Path) -> dict[str, Any]:
    state = json.loads(state_file.read_text())
    if state["schema"] != 1 or state["repository"] != repository():
        raise ValueError("Snapshot belongs to another repository or schema")
    names = state["branches"]
    if not isinstance(names, list) or sorted(names) != sorted(inventory()):
        raise ValueError("Active stack inventory changed; stop without publishing")
    for name in names:
        branch(name)
        oid(state["expected"][name], absent=True)
        oid(state["local"][name])
    endpoint = state["endpoint"]
    if not isinstance(endpoint, str) or not endpoint or endpoint.startswith("-") or "\n" in endpoint:
        raise ValueError("Invalid frozen endpoint")
    return dict(state)


def save(state_file: Path, state: dict[str, Any]) -> None:
    temporary = state_file.with_name(f".{state_file.name}.{os.getpid()}.tmp")
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as output:
        json.dump(state, output, indent=2)
        output.write("\n")
    os.replace(temporary, state_file)


def prepare(state_file: Path, state: dict[str, Any]) -> None:
    """Record whether preparation succeeded, so publish can refuse an unprepared stack."""
    if state.get("phase") == "prepared":
        raise ValueError("Preparation already succeeded for this snapshot; do not prepare again")
    state["phase"] = "prepare_failed"
    try:
        state["prepared"] = fast_forward(state)
        state["phase"] = "prepared"
    finally:
        save(state_file, state)


def fast_forward(state: dict[str, Any]) -> dict[str, str]:
    """Integrate behind-only remote work before local rebasing, never publish."""
    worktrees = command("git", "worktree", "list", "--porcelain", "-z").split("\0")
    locations: dict[str, str] = {}
    location = ""
    for field in worktrees:
        if field.startswith("worktree "):
            location = field[9:]
        elif field.startswith("branch refs/heads/"):
            locations[field[18:]] = location
    updates = []
    for name in state["branches"]:
        ref = f"refs/heads/{name}"
        local = oid(command("git", "rev-parse", "--verify", f"{ref}^{{commit}}"))
        if local != state["local"][name]:
            raise ValueError("Local branch changed since capture; stop before preparation")
        expected = state["expected"][name]
        if not expected:
            continue
        command("git", "fetch", "--no-tags", "--", state["endpoint"], expected)
        counts = command("git", "rev-list", "--left-right", "--count", f"{local}...{expected}").split()
        ahead, behind = map(int, counts)
        if ahead and behind:
            raise ValueError(f"{name} diverged; integrate remote work before rewriting")
        if behind:
            checkout_path = locations.get(name)
            if checkout_path and command("git", "status", "--porcelain", cwd=checkout_path):
                raise ValueError(f"{name} has local changes; stop before fast-forward")
            updates.append((ref, local, expected, checkout_path))
    for ref, local, expected, target_worktree in updates:
        if target_worktree:
            command("git", "merge", "--ff-only", "--no-overwrite-ignore", expected, cwd=target_worktree)
        else:
            command("git", "update-ref", ref, expected, local)
    return {
        name: oid(command("git", "rev-parse", "--verify", f"refs/heads/{name}^{{commit}}"))
        for name in state["branches"]
    }


def require_prepared(state: dict[str, Any]) -> None:
    """A lease taken while local and remote differed may still match after a skipped or failed prepare."""
    names = state["branches"]
    differing = [name for name in names if state["expected"][name] not in ("", state["local"][name])]
    if differing and state.get("phase") != "prepared":
        raise ValueError(
            f"{', '.join(differing)} differed from the remote at capture and preparation has not succeeded "
            f"(phase: {state.get('phase', 'none')}); publishing could drop remote-only commits"
        )


def publish(state: dict[str, Any]) -> None:
    names = state["branches"]
    if not names:
        print("No active branches to publish")
        return
    require_prepared(state)
    tips = {name: oid(command("git", "rev-parse", "--verify", f"refs/heads/{name}^{{commit}}")) for name in names}
    leases = [f"--force-with-lease=refs/heads/{name}:{state['expected'][name]}" for name in names]
    refs = [f"{tips[name]}:refs/heads/{name}" for name in names]
    command(
        "git",
        "-c",
        "push.followTags=false",
        "push",
        "--atomic",
        "--no-follow-tags",
        *leases,
        "--",
        state["endpoint"],
        *refs,
    )
    if remote_heads(state["endpoint"], names) != tips:
        raise ValueError("Publication returned success but remote heads moved; snapshot retained")
    print("STACK_PUBLISHED=true")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["capture", "prepare", "publish"])
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--remote")
    args = parser.parse_args()
    try:
        if args.operation == "capture":
            if not args.remote:
                raise ValueError("capture requires --remote")
            capture(args.state, args.remote)
        elif args.operation == "prepare":
            prepare(args.state, load(args.state))
        else:
            publish(load(args.state))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"Stack publication stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
