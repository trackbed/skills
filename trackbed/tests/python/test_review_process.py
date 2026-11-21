"""Credential-free subprocess policy and descendant cleanup fixtures."""

import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

LIB = Path(__file__).resolve().parents[2] / "scripts" / "lib"
sys.path.insert(0, str(LIB))
import review_process  # noqa: E402
from review_process import noninteractive_environment, run_bounded  # noqa: E402


class ReviewProcessTests(unittest.TestCase):
    def test_environment_keeps_custom_transport_and_disables_prompts(self):
        with mock.patch.dict(os.environ, {"GIT_SSH_COMMAND": "custom-ssh -i key"}):
            env = noninteractive_environment()
        self.assertEqual(env["GIT_SSH_COMMAND"], "custom-ssh -i key -oBatchMode=yes")
        self.assertEqual(env["GCM_INTERACTIVE"], "Never")
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(env["GH_PROMPT_DISABLED"], "1")

    def test_success_input_text_and_nonzero_status(self):
        result = run_bounded(
            [sys.executable, "-c", "import sys; print(sys.stdin.read()); sys.exit(7)"],
            timeout=2,
            input="hello",
            text=True,
        )
        self.assertEqual((result.returncode, result.stdout), (7, "hello\n"))
        result = run_bounded([sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"], timeout=2)
        self.assertEqual(result.stdout, b"0\n")

    def test_shell_review_environment_is_child_only(self):
        code = (
            "import os; print(os.environ['GH_PROMPT_DISABLED'], "
            "os.environ['GCM_INTERACTIVE'], os.environ['GIT_SSH_COMMAND'])"
        )
        result = subprocess.run(
            [
                "bash",
                "-c",
                'source "$1/shell-helpers.sh"; shift; run_review_command 2 "$@"; '
                'printf "parent:%s" "${GH_PROMPT_DISABLED-unset}"',
                "fixture",
                str(LIB),
                sys.executable,
                "-c",
                code,
            ],
            env=dict(os.environ, GH_PROMPT_DISABLED="parent", GIT_SSH_COMMAND="custom-ssh"),
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "1 Never custom-ssh -oBatchMode=yes\nparent:parent")

    def test_shell_timeout_preserves_exit_124(self):
        result = subprocess.run(
            [
                "bash",
                "-c",
                'source "$1/shell-helpers.sh"; shift; run_review_command 0.1 "$@"',
                "fixture",
                str(LIB),
                sys.executable,
                "-c",
                "import time; time.sleep(60)",
            ],
            capture_output=True,
            timeout=3,
        )
        self.assertEqual(result.returncode, 124)

    def test_custom_git_ssh_executable_path_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix="transport fixture ") as directory:
            ssh = Path(directory) / "fake 'ssh"
            marker = Path(directory) / "called"
            ssh.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" >> "$TRACKBED_SSH_MARKER"\nexit 1\n')
            ssh.chmod(0o755)
            with mock.patch.dict(
                os.environ,
                {
                    "GIT_SSH": str(ssh),
                    "TRACKBED_SSH_MARKER": str(marker),
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": os.devnull,
                },
            ):
                os.environ.pop("GIT_SSH_COMMAND", None)
                command = ["git", "ls-remote", "ssh://fixture.invalid/repo"]
                for language in ("python", "shell"):
                    with self.subTest(language=language):
                        marker.unlink(missing_ok=True)
                        if language == "python":
                            result = run_bounded(command, cwd=directory, timeout=3)
                        else:
                            result = subprocess.run(
                                [
                                    "bash",
                                    "-c",
                                    'source "$1/shell-helpers.sh"; shift; run_review_command 3 "$@"',
                                    "fixture",
                                    str(LIB),
                                    *command,
                                ],
                                cwd=directory,
                                capture_output=True,
                                timeout=5,
                            )
                        self.assertTrue(marker.exists(), result.stderr)
                        self.assertIn("-oBatchMode=yes", marker.read_text())

    def test_transport_follows_git_precedence(self):
        shell = 'source "$1/shell-helpers.sh"; shift; run_review_command 3 "$@"'
        report = [sys.executable, "-c", "import os; print(os.environ['GIT_SSH_COMMAND'])"]
        cases = [
            ("environment command wins", {"GIT_SSH_COMMAND": "env-ssh", "GIT_SSH": "/bin/path-ssh"}, "env-ssh"),
            ("config beats GIT_SSH", {"GIT_SSH": "/bin/path-ssh"}, "config-ssh -i key"),
            ("config alone", {}, "config-ssh -i key"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(["git", "init", "-q", directory], check=True)
            subprocess.run(["git", "config", "core.sshCommand", "config-ssh -i key"], cwd=directory, check=True)
            for name, overrides, expected in cases:
                env = {k: v for k, v in os.environ.items() if k not in ("GIT_SSH", "GIT_SSH_COMMAND")}
                env.update(overrides, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
                with self.subTest(name), mock.patch.dict(os.environ, env, clear=True):
                    self.assertEqual(
                        noninteractive_environment(directory)["GIT_SSH_COMMAND"], f"{expected} -oBatchMode=yes"
                    )
                    result = run_bounded(report, cwd=directory, timeout=3, text=True)
                    self.assertEqual(result.stdout, f"{expected} -oBatchMode=yes\n")
                    result = subprocess.run(
                        ["bash", "-c", shell, "fixture", str(LIB), *report],
                        cwd=directory,
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    self.assertEqual(result.stdout, f"{expected} -oBatchMode=yes\n", result.stderr)

    def test_native_launch_error(self):
        with self.assertRaises(FileNotFoundError):
            run_bounded(["trackbed-no-such-program"], timeout=1)

    def assert_stopped(self, pid):
        # A killed orphan may remain a zombie until the host's reaper runs.
        for _ in range(100):
            result = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
            if result.returncode or result.stdout.strip().startswith("Z"):
                return
            time.sleep(0.02)
        self.fail(f"descendant {pid} survived")

    def test_timeout_kills_descendants(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "pid"
            command = [
                sys.executable,
                "-c",
                "import subprocess,sys,time; from pathlib import Path; "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                "Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)",
                str(marker),
            ]
            with self.assertRaises(subprocess.TimeoutExpired):
                run_bounded(command, timeout=0.5)
            self.assert_stopped(int(marker.read_text()))

    def test_interruption_restores_signal_exit_and_kills_descendants(self):
        for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
            with self.subTest(signal=signum), tempfile.TemporaryDirectory() as directory:
                marker = Path(directory) / "pid"
                child = (
                    "import subprocess,sys,time; from pathlib import Path; "
                    "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                    "Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
                )
                controller = (
                    "import sys; sys.path.insert(0,sys.argv[1]); "
                    "from review_process import run_bounded; "
                    "run_bounded([sys.executable,'-c',sys.argv[2],sys.argv[3]],timeout=10)"
                )
                proc = subprocess.Popen(
                    [sys.executable, "-c", controller, str(LIB), child, str(marker)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                try:
                    for _ in range(200):
                        if marker.exists():
                            break
                        time.sleep(0.01)
                    self.assertTrue(marker.exists())
                    proc.send_signal(signum)
                    self.assertEqual(proc.wait(timeout=3), -signum)
                    self.assert_stopped(int(marker.read_text()))
                finally:
                    if proc.poll() is None:
                        proc.kill()
                    proc.wait()


class CallerError(Exception):
    pass


def completed(code: int, stdout: bytes = b"", stderr: bytes = b"") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], code, stdout, stderr)


class CommandHelperTests(unittest.TestCase):
    def test_run_reports_launch_failure_and_timeout_as_exit_codes(self):
        self.assertEqual(review_process.run(["trackbed-no-such-program"], 5).returncode, 127)
        expired = subprocess.TimeoutExpired(["git"], 5)
        with mock.patch.object(review_process, "run_bounded", side_effect=expired):
            result = review_process.run(["git", "status"], 5)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (124, b"", b"timed out after 5s"))

    def test_run_disables_prompts_and_color_and_forwards_input(self):
        report = "import os, sys; print(os.environ['GH_PROMPT_DISABLED'], os.environ['GIT_TERMINAL_PROMPT'], "
        report += "os.environ['NO_COLOR'], sys.stdin.read())"
        result = review_process.run([sys.executable, "-c", report], 5, b"piped")
        self.assertEqual((result.returncode, result.stdout), (0, b"1 0 1 piped\n"))

    def test_tail_keeps_the_last_300_characters_on_one_line(self):
        self.assertEqual(review_process.tail(b"fatal:\n  bad\tref\n"), "fatal: bad ref")
        self.assertEqual(review_process.tail(b"x" * 400 + b"\xff"), "x" * 299 + "\ufffd")

    def test_git_returns_raw_output_and_forwards_input(self):
        oid = review_process.git("hash-object", "--stdin", error=CallerError, timeout=10, input=b"hello\n")
        self.assertEqual(oid, "ce013625030ba8dba906f756967f9e9ca394464a\n")

    def test_git_failure_raises_the_callers_error_naming_the_subcommand(self):
        cases = [
            (
                ("rev-parse", "HEAD"),
                b"fatal: not a git repository\n",
                "`git rev-parse` failed: fatal: not a git repository",
            ),
            (("-c", "log.showSignature=false", "log", "-p"), b"", "`git log` failed: exit 128"),
            (("--version",), b"", "`git command` failed: exit 128"),
        ]
        for args, stderr, message in cases:
            with self.subTest(args=args):
                with mock.patch.object(review_process, "run", return_value=completed(128, stderr=stderr)):
                    with self.assertRaises(CallerError) as raised:
                        review_process.git(*args, error=CallerError, timeout=10)
                self.assertEqual(str(raised.exception), message)

    def test_gh_json_parses_output_and_maps_failures_to_the_callers_error(self):
        with mock.patch.object(review_process, "run", return_value=completed(0, b'[{"number": 7}]')) as run:
            self.assertEqual(
                review_process.gh_json("pr", "list", what="pulls", error=CallerError, timeout=20), [{"number": 7}]
            )
        run.assert_called_once_with(["gh", "pr", "list"], 20)
        with mock.patch.object(review_process, "run", return_value=completed(0)):
            self.assertIsNone(review_process.gh_json("api", "x", what="pulls", error=CallerError, timeout=20))
        failures = [
            (completed(1, stderr=b"HTTP 404\n"), {}, "could not read pulls: HTTP 404"),
            (completed(4), {"verb": "query"}, "could not query pulls: gh exited 4"),
            (completed(0, b"{not json"), {}, "could not parse pulls: "),
        ]
        for result, options, message in failures:
            with self.subTest(message=message):
                with mock.patch.object(review_process, "run", return_value=result):
                    with self.assertRaises(CallerError) as raised:
                        review_process.gh_json("pr", "list", what="pulls", error=CallerError, timeout=20, **options)
                self.assertTrue(str(raised.exception).startswith(message), str(raised.exception))

    def test_is_ancestor_follows_the_merge_base_exit_status(self):
        for code, expected in ((0, True), (1, False), (124, False)):
            with mock.patch.object(review_process, "run", return_value=completed(code)) as run:
                self.assertIs(review_process.is_ancestor("a", "b", timeout=30), expected)
            run.assert_called_once_with(["git", "merge-base", "--is-ancestor", "a", "b"], 30)

    def test_valid_branch_requires_git_to_echo_the_name_unchanged(self):
        self.assertTrue(review_process.valid_branch("feature/stack-1", timeout=10))
        for name in ("bad name", "-leading", "", None, 42):
            with self.subTest(name=name):
                self.assertFalse(review_process.valid_branch(name, timeout=10))
        with mock.patch.object(review_process, "run", return_value=completed(0, b"main\n")):
            self.assertFalse(review_process.valid_branch("@{-1}", timeout=10))


if __name__ == "__main__":
    unittest.main()
