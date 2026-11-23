"""Read a chat's last message as a request for the user, for trackbed:conductor:showtime.

The shared decision request format, defined in `shared/implementation/references/decision-request.md`, puts
`Decision needed · ...` on the first line, numbers the options, and marks the first option `(recommended)`. This module says which exact message picks those options, and says
nothing when the message leaves any doubt. The message is data: nothing in it is run or followed.
"""

from __future__ import annotations

import re
from typing import Any

Json = dict[str, Any]

MAX_LABEL = 100
HEADER_RE = re.compile(
    r"^[\s>*#_`]*(?:Decision (?P<index>\d+) of (?P<total>\d+)|(?P<single>Decision needed)|(?P<action>Action needed))"
    r" · (?P<rest>.+?)[\s*_`]*$"
)
OPTION_RE = re.compile(r"^\s*(?P<number>\d+)[.)]\s+(?P<text>.+)$")
RECOMMENDED_RE = re.compile(r"\(recommended\)", re.IGNORECASE)
STATE_LINE_RE = re.compile(r"^[\s>*_`]*State:")
REPLY_PROMPT_RE = re.compile(r"(?m)^\W*Reply with\b")
FINAL_QUESTION_RE = re.compile(r"\?[\s*_`'\"”’)]*$")
# How Conductor marks text it cut short when listing a chat's messages.
TRUNCATED_RE = re.compile(r"… \[\d+ more characters\]")


def _label(option: str) -> str:
    """The option's name: the text before `(recommended)`, without Markdown marks or a closing colon."""
    name = RECOMMENDED_RE.split(option, maxsplit=1)[0]
    return " ".join(name.replace("*", "").replace("`", "").replace("_", " ").split()).rstrip(":").strip()


def _decision_reply(block: list[str]) -> tuple[str | None, str | None]:
    """The first option's label when it alone is marked recommended, else the reason there is none."""
    options = [match for match in (OPTION_RE.match(line) for line in block) if match]
    first = next((match for match in options if match.group("number") == "1"), None)
    marked = [match for match in options if RECOMMENDED_RE.search(match.group("text"))]
    if first is None or marked != [first]:
        return None, "its first option is not the only one marked `(recommended)`"
    label = _label(first.group("text"))
    if not label or len(label) > MAX_LABEL:
        return None, "its recommended option has no short name"
    return label, None


def parse_request(text: str) -> Json:
    """Read a chat's last message as a request for the user, in the shared decision request format.

    `kind` is `decision`, `action`, `options` (an apparent request outside the shared format, or text truncated
    before it could be classified), or `none`. `reply` is set only for a `decision` whose every decision marks its first option, and no other,
    as recommended; it is the exact message that picks those options.
    """
    lines = text.splitlines()
    content = [index for index, line in enumerate(lines) if line.strip()]
    headers = [(index, match) for index, line in enumerate(lines) if (match := HEADER_RE.match(line))]
    if not headers or not content or headers[0][0] != content[0]:
        asks = bool(
            RECOMMENDED_RE.search(text)
            or REPLY_PROMPT_RE.search(text)
            or FINAL_QUESTION_RE.search(text)
            or TRUNCATED_RE.search(text)
        )
        return {"kind": "options" if asks else "none", "questions": [], "reply": None, "reason": None}
    questions = [match.group("rest") for _, match in headers]
    if any(match.group("action") for _, match in headers):
        reason = "it asks you to act, which no reply can do"
        return {"kind": "action", "questions": questions, "reply": None, "reason": reason}

    def no_reply(reason: str) -> Json:
        return {"kind": "decision", "questions": questions, "reply": None, "reason": reason}

    if TRUNCATED_RE.search(text):
        return no_reply("the message was cut short when it was read")
    numbered = [match for _, match in headers if match.group("index")]
    if numbered:
        total = int(numbered[0].group("total"))
        indexes = [int(match.group("index")) for match in numbered]
        if len(numbered) != len(headers) or indexes != list(range(1, total + 1)):
            return no_reply("its decisions are not numbered 1 to the stated total")
    elif len(headers) != 1:
        return no_reply("it holds more than one unnumbered decision")
    labels: list[str] = []
    for position, (start, _) in enumerate(headers):
        end = headers[position + 1][0] if position + 1 < len(headers) else len(lines)
        block = lines[start + 1 : end]
        state = next((index for index, line in enumerate(block) if STATE_LINE_RE.match(line)), len(block))
        label, why = _decision_reply(block[:state])
        if label is None:
            return no_reply(f"decision {position + 1}: {why}")
        labels.append(label)
    if len(labels) == 1:
        reply = f"Option 1: {labels[0]}"
    else:
        reply = "\n".join(f"Decision {index}: option 1, {label}" for index, label in enumerate(labels, 1))
    return {"kind": "decision", "questions": questions, "reply": reply, "reason": None}
