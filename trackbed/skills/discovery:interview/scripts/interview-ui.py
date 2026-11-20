#!/usr/bin/env python3
"""Ask one round of a discovery interview on a page in the person's own browser.

The interviewer writes a round file (`references/ui-round-format.md`): a few questions, each with the
control that fits it. This helper checks the file, builds the page, and gets the answers back.

  ask      serve the round on the loopback address, open it, and wait for the answers
  build    write the round as a page that works without this helper; answers come back by copy and paste
  answers  check answers that were pasted back against the round they answer

Exit codes: 0 done, 1 the round or the answers have problems, 2 usage or file error,
3 `ask` stopped waiting and has no answers yet.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import tempfile
import time
import webbrowser
from pathlib import Path
from typing import Any, Optional

# Running the helper must leave the installed plugin as it was: no bytecode beside these modules.
sys.dont_write_bytecode = True

from interview_ui_answers import describe_answers, read_answers  # noqa: E402
from interview_ui_page import LIVE, OFFLINE, content_policy, render_page  # noqa: E402
from interview_ui_round import read_round  # noqa: E402
from interview_ui_server import RoundServer, serve  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[1]
ASSETS = SKILL_DIR / "assets"
# The palette and fonts are shared with visual reports and decision documents.
TOKENS = SKILL_DIR.parents[1] / "shared" / "visual" / "assets" / "report-tokens.css"
DEFAULT_WAIT_SECONDS = 1500.0


class HelperError(Exception):
    """A usage or file problem: the helper could not do what was asked."""


def read_asset(path: Path, closing: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise HelperError(f"{path}: cannot read a file this helper ships with: {error}") from error
    if closing in text.lower():
        raise HelperError(f"{path}: must not contain {closing}")
    return "\n" + text.strip("\n") + "\n"


def write_private(path: Path, text: str) -> None:
    """Write a session file atomically, readable by this user only."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def load_json(path: Path, what: str) -> Any:
    try:
        text = sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise HelperError(f"{path}: cannot read {what}: {error}") from error
    # Pasted answers may arrive inside a fence or a sentence; the object itself is what counts.
    start, end = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[start : end + 1] if 0 <= start < end else text)
    except json.JSONDecodeError as error:
        raise HelperError(f"{path}: {what} is not valid JSON: {error}") from error


def load_round(path: Path) -> Optional[dict[str, Any]]:
    round_, problems = read_round(load_json(path, "the round file"), path.parent if str(path) != "-" else None)
    for problem in problems:
        print(f"interview-ui: {problem}", file=sys.stderr)
    if round_ is None:
        print(
            f"interview-ui: {len(problems)} problem(s) in {path}; nothing was shown. Fix them and rerun.",
            file=sys.stderr,
        )
    return round_


def session_dir(given: Optional[Path], session_id: str) -> Path:
    return given.expanduser() if given else Path.home() / ".trackbed" / "interviews" / session_id


def build_page(round_: dict[str, Any], mode: str, key: str = "", expires_at: int = 0) -> tuple[str, str]:
    css = read_asset(TOKENS, "</style") + read_asset(ASSETS / "interview-ui.css", "</style")
    script = read_asset(ASSETS / "interview-ui.js", "</script")
    return render_page(round_, css, script, mode=mode, key=key, expires_at=expires_at), content_policy(script, mode)


def record_answers(path: Path, answers: dict[str, Any]) -> None:
    write_private(path, json.dumps(answers, indent=2, ensure_ascii=False) + "\n")


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def cmd_ask(args: argparse.Namespace) -> int:
    round_ = load_round(args.round)
    if round_ is None:
        return 1
    directory = session_dir(args.session_dir, round_["session"]["id"])
    offline, _ = build_page(round_, OFFLINE)
    offline_path = directory / f"round-{round_['number']}.html"
    answers_path = directory / f"round-{round_['number']}.answers.json"
    write_private(offline_path, offline)
    offline_hint = f"the round's page is at {offline_path} and works without this helper"

    key = secrets.token_urlsafe(32)
    expires_at = int((time.time() + args.wait) * 1000)
    page, policy = build_page(round_, LIVE, key, expires_at)

    def check(raw: Any) -> tuple[Optional[dict[str, Any]], list[str]]:
        return read_answers(round_, raw)

    def save_answers(answers: dict[str, Any]) -> None:
        record_answers(answers_path, answers)

    try:
        server = RoundServer(key, page, policy, check, save_answers)
    except OSError as error:
        raise HelperError(f"cannot listen on the loopback address; {offline_hint}") from error

    def announce(listening: RoundServer) -> None:
        if not args.no_open:
            try:
                opened = webbrowser.open_new_tab(listening.url)
            except (OSError, webbrowser.Error):
                opened = False
            if not opened:
                raise HelperError(f"no browser could be opened here; {offline_hint}")
        minutes = max(1, round(args.wait / 60))
        print(
            f"interview-ui: round {round_['number']} is at {listening.url} (waiting up to {minutes} min for answers)",
            file=sys.stderr,
            flush=True,
        )

    answers = serve(server, expires_at, announce)
    if answers is None:
        emit({"status": "waiting", "round": round_["number"], "offlinePage": str(offline_path)})
        return 3
    emit(
        {
            "status": "answered",
            **describe_answers(round_, answers),
            "answersFile": str(answers_path),
        }
    )
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    round_ = load_round(args.round)
    if round_ is None:
        return 1
    output = args.output.expanduser()
    if output.suffix.lower() != ".html" or output.is_symlink() or output.is_dir():
        raise HelperError(f"{output}: the output must be an .html file path")
    page, _ = build_page(round_, OFFLINE)
    write_private(output, page)
    emit(
        {
            "status": "built",
            "round": round_["number"],
            "page": str(output.resolve()),
            "bytes": len(page.encode("utf-8")),
        }
    )
    return 0


def cmd_answers(args: argparse.Namespace) -> int:
    round_ = load_round(args.round)
    if round_ is None:
        return 1
    answers, problems = read_answers(round_, load_json(args.answers, "the answers"))
    if answers is None:
        for problem in problems:
            print(f"interview-ui: {problem}", file=sys.stderr)
        print("interview-ui: these answers cannot be used; ask for them again.", file=sys.stderr)
        return 1
    directory = session_dir(args.session_dir, round_["session"]["id"])
    answers_path = directory / f"round-{round_['number']}.answers.json"
    record_answers(answers_path, answers)
    emit(
        {
            "status": "answered",
            **describe_answers(round_, answers),
            "answersFile": str(answers_path),
        }
    )
    return 0


def seconds(text: str) -> float:
    value = float(text)
    if not 0 < value <= 7200:
        raise argparse.ArgumentTypeError("must be more than 0 and at most 7200 seconds")
    return value


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ask one round of a discovery interview on a page in the browser.")
    commands = parser.add_subparsers(dest="command", required=True)
    where = "where the session's files are kept (default: .trackbed/interviews/<session id> in the home folder)"

    ask = commands.add_parser("ask", help="serve a round, open it, and wait for the answers")
    ask.add_argument("--round", required=True, type=Path, help="the round file (JSON)")
    ask.add_argument("--session-dir", type=Path, help=where)
    ask.add_argument(
        "--wait", type=seconds, default=DEFAULT_WAIT_SECONDS, help="how long to wait for answers, in seconds"
    )
    ask.add_argument("--no-open", action="store_true", help="print the link and do not open a browser")
    ask.set_defaults(run=cmd_ask)

    build = commands.add_parser("build", help="write a round as a page that works without this helper")
    build.add_argument("--round", required=True, type=Path, help="the round file (JSON)")
    build.add_argument("--output", required=True, type=Path, help="the .html file to write")
    build.set_defaults(run=cmd_build)

    answers = commands.add_parser("answers", help="check answers that were pasted back")
    answers.add_argument("--round", required=True, type=Path, help="the round file the answers are for")
    answers.add_argument("--answers", required=True, type=Path, help="the pasted answers, or - to read them from stdin")
    answers.add_argument("--session-dir", type=Path, help=where)
    answers.set_defaults(run=cmd_answers)

    args = parser.parse_args(argv)
    try:
        return int(args.run(args))
    except (HelperError, OSError) as error:
        print(f"interview-ui: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
