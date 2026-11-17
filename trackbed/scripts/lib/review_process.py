"""Bounded review subprocess mechanics; callers own deadlines and error mapping."""

from __future__ import annotations

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
