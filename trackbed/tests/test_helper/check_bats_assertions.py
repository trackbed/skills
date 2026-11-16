"""Reject unguarded leading ! and [[ assertions in Bats sources.

This deliberately checks line-oriented assertions, including embedded shell
snippets. It is not a general shell parser. Heredoc fixture bodies are excluded;
control-flow conditions and explicit failure guards are allowed. Guards follow
the suite convention: false, return 1, exit 1, or a block containing only echo/printf diagnostics
before an unconditional return 1 or exit 1.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HEREDOC = re.compile(r"(?<!<)<<(-?)(?!<)\s*(['\"]?)([A-Za-z_][A-Za-z_0-9]*)\2")
ASSERTION = re.compile(r"^(?:!|\[\[)(?:\s|$)")
FAILURE = re.compile(r"(?:false|(?:return|exit)\s+1)\s*;?\s*$")


def unquoted_code(text: str) -> tuple[str, bool]:
    """Mask quoted arguments so their operators cannot act as failure guards."""
    quote = ""
    escaped = False
    result = []
    for char in text:
        if escaped:
            result.append("_")
            escaped = False
        elif char == "\\" and quote != "'":
            result.append("_")
            escaped = True
        elif quote:
            if char == quote:
                quote = ""
            result.append("_")
        elif char in ("'", '"'):
            quote = char
            result.append("_")
        elif char == "#" and (not result or result[-1].isspace()):
            break
        else:
            result.append(char)
    return "".join(result), bool(quote)


def unsafe_assertions(text: str) -> list[tuple[int, int]]:
    """Return one-based start/end lines needing an explicit failure guard."""
    findings = []
    heredocs: list[tuple[str, bool]] = []
    pending = ""
    start = 0
    for number, line in enumerate(text.splitlines(), 1):
        if heredocs:
            delimiter, tabs = heredocs[0]
            if (line.lstrip("\t") if tabs else line) == delimiter:
                heredocs.pop(0)
            continue
        # Only declaration lines can introduce a heredoc. Ignore here-strings.
        if not pending:
            code, _ = unquoted_code(line)
            heredocs.extend(
                (m[3], bool(m[1])) for m in HEREDOC.finditer(line) if code[m.start() : m.start() + 2] == "<<"
            )
        stripped = line.strip()
        if not pending and not ASSERTION.match(stripped):
            continue
        if not pending:
            start = number
        pending += stripped.removesuffix("\\") + (" " if stripped.endswith("\\") else "\n")
        if stripped.endswith("\\"):
            continue
        code, incomplete = unquoted_code(pending)
        if incomplete or code.strip() == "!" or ("[[" in code and "]]" not in code):
            continue
        if code.count("{") > code.count("}"):
            continue
        code = re.sub(r"\[\[.*?\]\]", "", code, flags=re.DOTALL)
        operators = re.findall(r"&&|\|\|", code)
        if not operators:
            findings.append((start, number))
        elif "||" in operators:
            arms = code.split("||")
            guard = arms[-1].strip()
            fails = bool(FAILURE.fullmatch(guard))
            if guard.startswith("{") and guard.endswith("}"):
                commands = [command.strip() for command in re.split(r"[;\n]", guard[1:-1]) if command.strip()]
                fails = bool(
                    commands
                    and re.fullmatch(r"(?:return|exit)\s+1", commands[-1])
                    and all(
                        re.match(r"(?:echo|printf)(?:\s|$)", command) and not re.search(r"\||(?<!>)&", command)
                        for command in commands[:-1]
                    )
                )
            if not fails or any(arm.strip() for arm in arms[1:-1]) or ";" in arms[0]:
                findings.append((start, number))
        # && alone is control flow, e.g. [[ -n "$url" ]] && break.
        pending = ""
    if pending:
        findings.append((start, len(text.splitlines())))
    return findings


def main(paths: list[str]) -> int:
    files = [Path(path) for path in paths] if paths else sorted(Path(__file__).parents[1].glob("*.bats"))
    count = 0
    for path in files:
        for start, _ in unsafe_assertions(path.read_text()):
            print(f"{path}:{start}: assertion needs an explicit failure guard (|| false)")
            count += 1
    return int(bool(count))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
