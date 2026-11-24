"""Bounded, noninteractive review subprocess helpers; callers supply deadlines and the error git and gh_json raise."""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import threading
from collections.abc import Sequence
from typing import Any


def configured_ssh_command(cwd: str | os.PathLike[str] | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", "config", "--get", "core.sshCommand"],
            cwd=cwd,
            env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def noninteractive_environment(cwd: str | os.PathLike[str] | None = None) -> dict[str, str]:
    """Return a prompt-free environment that keeps the transport git would pick in cwd.

    Git's order is GIT_SSH_COMMAND, then core.sshCommand, then GIT_SSH, then ssh.
    GIT_SSH is an executable path; the other two contain shell syntax.
    """
    ssh = os.environ.get("GIT_SSH_COMMAND") or configured_ssh_command(cwd)
    if not ssh:
        ssh = shlex.quote(os.environ.get("GIT_SSH") or "ssh")
    return dict(
        os.environ,
        GH_PROMPT_DISABLED="1",
        GIT_TERMINAL_PROMPT="0",
        GCM_INTERACTIVE="Never",
        GIT_SSH_COMMAND=f"{ssh} -oBatchMode=yes",
        GIT_OPTIONAL_LOCKS="0",
    )


def run_bounded(argv: Sequence[str], *, timeout: float, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    """Capture output, preserving native launch/timeout exceptions and cleaning descendants.

    Input defaults to EOF. Callers may supply input, text mode, cwd and environment.
    On the main thread, HUP/TERM clean the process group before the prior signal
    disposition runs; KeyboardInterrupt and other exceptions also clean the group.
    """
    if "env" not in kwargs:
        kwargs["env"] = noninteractive_environment(kwargs.get("cwd"))
    data = kwargs.pop("input", None)
    proc = subprocess.Popen(
        list(argv),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        **kwargs,
    )
    previous: dict[int, Any] = {}

    def cleanup() -> None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()

    def interrupted(signum: int, frame: Any) -> None:
        cleanup()
        handler = previous[signum]
        signal.signal(signum, handler)
        if callable(handler):
            handler(signum, frame)
        else:
            os.kill(os.getpid(), signum)

    try:
        if threading.current_thread() is threading.main_thread():
            for signum in (signal.SIGHUP, signal.SIGTERM):
                handler = signal.getsignal(signum)
                if handler != signal.SIG_IGN:
                    previous[signum] = handler
                    signal.signal(signum, interrupted)
        stdout, stderr = proc.communicate(data, timeout=timeout)
        return subprocess.CompletedProcess(list(argv), proc.returncode, stdout, stderr)
    except BaseException:
        cleanup()
        raise
    finally:
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()
        for previous_signum, handler in previous.items():
            signal.signal(previous_signum, handler)


def run(argv: Sequence[str], timeout: float, input: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    """Run without a shell, prompts, or color; a timeout or launch failure becomes exit 124 or 127.

    The failure reason goes to stderr, so callers handle every outcome through the exit status.
    """
    try:
        return run_bounded(
            list(argv), env=dict(noninteractive_environment(), NO_COLOR="1"), input=input, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(list(argv), 124, b"", f"timed out after {timeout}s".encode())
    except OSError as error:
        return subprocess.CompletedProcess(list(argv), 127, b"", str(error).encode())


def tail(data: bytes) -> str:
    """The last 300 characters of command output, on one line."""
    return " ".join(data.decode("utf-8", "replace").split())[-300:]


def git(*args: str, error: type[Exception], timeout: float, input: bytes | None = None) -> str:
    """The command's standard output; a failure raises `error` naming the git subcommand."""
    result = run(["git", *args], timeout, input)
    if result.returncode != 0:
        command = next((arg for arg in args if not arg.startswith("-") and "=" not in arg), "command")
        raise error(f"`git {command}` failed: {tail(result.stderr) or f'exit {result.returncode}'}")
    return result.stdout.decode("utf-8", "replace")


def gh_json(*args: str, what: str, error: type[Exception], timeout: float, verb: str = "read") -> Any:
    """The parsed JSON output, or None for empty output; a failed or unparsable read raises `error` naming `what`."""
    result = run(["gh", *args], timeout)
    if result.returncode != 0:
        raise error(f"could not {verb} {what}: {tail(result.stderr) or f'gh exited {result.returncode}'}")
    try:
        return json.loads(result.stdout or b"null")
    except ValueError as problem:
        raise error(f"could not parse {what}: {problem}") from problem


def is_ancestor(ancestor: str, descendant: str, *, timeout: float) -> bool:
    return run(["git", "merge-base", "--is-ancestor", ancestor, descendant], timeout).returncode == 0


def valid_branch(name: object, *, timeout: float) -> bool:
    if not isinstance(name, str) or not name:
        return False
    # `check-ref-format --branch` expands `@{-N}`, so require it to echo the name unchanged.
    checked = run(["git", "check-ref-format", "--branch", name], timeout)
    return checked.returncode == 0 and checked.stdout.decode("utf-8", "replace").strip() == name
