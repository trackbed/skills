"""Check failure guards in Bats sources and cap raw pins in guidance suites.

This deliberately checks line-oriented assertions, including embedded shell
snippets. It is not a general shell parser. Heredoc fixture bodies are excluded;
control-flow conditions and explicit failure guards are allowed. Guards follow
the suite convention: false, return 1, exit 1, or a block containing only echo/printf diagnostics
before an unconditional return 1 or exit 1.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path

HEREDOC = re.compile(r"(?<!<)<<(-?)(?!<)\s*(['\"]?)([A-Za-z_][A-Za-z_0-9]*)\2")
BASH_SNIPPET = re.compile(r"^\s*(?:run\s+)?bash\s+-[a-zA-Z]*c\s+['\"]\s*$")
ASSERTION = re.compile(r"^(?:!|\[\[)(?:\s|$)")
FAILURE = re.compile(r"(?:false|(?:return|exit)\s+1)\s*;?\s*$")
RAW_PIN = re.compile(r"(?:^|[;|&])[ \t]*(?:(?:if|elif|then|run|!)[ \t]+)*grep[ \t]+-qF?(?=\s|$)", re.MULTILINE)
GUIDANCE_BASELINE = Path(__file__).with_name("guidance-grep-baseline.json")


def unquoted_code(text: str, quote: str = "") -> tuple[str, str]:
    """Mask quoted arguments so their operators cannot act as failure guards."""
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
    if escaped:
        result[-1] = "\\"
    return "".join(result), quote


def source_lines(text: str) -> Iterator[tuple[int, str, str]]:
    """Yield shell source lines with their original numbers, skipping heredoc bodies."""
    heredocs: list[tuple[str, bool]] = []
    quote = ""
    embedded_shell = False
    for number, line in enumerate(text.splitlines(), 1):
        if heredocs:
            delimiter, tabs = heredocs[0]
            if (line.lstrip("\t") if tabs else line) == delimiter:
                heredocs.pop(0)
            continue
        # Inspect assertions in embedded shell snippets as well as top-level code.
        # A quoted continuation cannot open a heredoc in the surrounding shell.
        if not quote:
            embedded_shell = bool(BASH_SNIPPET.match(line))
        code, line_quote = unquoted_code(line)
        heredoc_code, quote = unquoted_code(line, quote) if quote else (code, line_quote)
        if embedded_shell:
            heredoc_code = code
        heredocs.extend(
            (m[3], bool(m[1])) for m in HEREDOC.finditer(line) if heredoc_code[m.start() : m.start() + 2] == "<<"
        )
        yield number, line, code


def count_raw_pins(text: str) -> int:
    """Count quiet grep commands in guidance source, including piped checks."""
    code = "\n".join(code for _, _, code in source_lines(text))
    return len(RAW_PIN.findall(code.replace("\\\n", "")))


def unsafe_assertions(text: str) -> list[tuple[int, int]]:
    """Return one-based start/end lines needing an explicit failure guard."""
    findings = []
    pending = ""
    start = 0
    for number, line, _ in source_lines(text):
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
    baseline = json.loads(GUIDANCE_BASELINE.read_text())
    failed = False
    for path in files:
        text = path.read_text()
        for start, _ in unsafe_assertions(text):
            print(f"{path}:{start}: assertion needs an explicit failure guard (|| false)")
            failed = True
        if path.name.endswith("-guidance.bats"):
            actual = count_raw_pins(text)
            limit = baseline.get(path.name, 0)
            if actual > limit:
                print(f"{path}: {actual} raw grep pins exceed baseline {limit}. Use guidance assertion helpers.")
                failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
