"""Render one interview round as a page a person answers in.

Everything the person reads is written here, escaped, from a round `interview_ui_round.read_round`
has already checked. The runtime (`assets/interview-ui.js`) draws nothing of the round: it keeps what
the person enters, sends it back, and shows the submission result.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any, Optional

from interview_ui_figures import esc, inline, render_figures

LIVE = "live"
OFFLINE = "offline"
# The value a "Something else" control carries; never an option id, which cannot start with an underscore.
OTHER = "__other"


def safe_json(value: Any) -> str:
    """JSON for a data block: no `<`, so nothing in it can close the element."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def _described(entry: dict[str, Any]) -> str:
    description = f"<span>{inline(entry['description'])}</span>" if entry["description"] else ""
    return f"<strong>{inline(entry['label'])}</strong>{description}"


def _letter(index: int) -> str:
    return chr(ord("A") + index)


def _choice(question: dict[str, Any], name: str) -> str:
    recommendation = question["recommendation"]
    recommended = recommendation["pick"] or []
    control = "checkbox" if question["multiple"] else "radio"
    options = ""
    for index, option in enumerate(question["options"]):
        ident = f"{name}-option-{option['id']}"
        badge = '<span class="ti-badge">Recommended</span>' if option["id"] in recommended else ""
        more = ""
        for key, label in (("gives", "Gives"), ("costs", "Costs")):
            if option[key]:
                more += (
                    f'<div class="ti-{key}"><h3>{label}</h3><ul>'
                    + "".join(f"<li>{inline(entry)}</li>" for entry in option[key])
                    + "</ul></div>"
                )
        more = f'<div class="ti-tradeoffs">{more}</div>' if more else ""
        more += render_figures(option)
        options += (
            f'<div class="ti-option"><input type="{control}" name="{name}" id="{ident}" value="{esc(option["id"])}" '
            f'data-option><label for="{ident}"><span class="ti-letter">{_letter(index)}</span>'
            f'<span class="ti-option-text"><strong>{inline(option["label"])}{badge}</strong>'
            + (f"<span>{inline(option['description'])}</span>" if option["description"] else "")
            + f"</span></label>{more}</div>"
        )
    if question["other"]:
        ident = f"{name}-other"
        options += (
            f'<div class="ti-option ti-option-other"><input type="{control}" name="{name}" id="{ident}" '
            f'value="{OTHER}" data-other><label for="{ident}"><span class="ti-letter">+</span>'
            '<span class="ti-option-text"><strong>Something else</strong>'
            "<span>None of these fits. Say what would.</span></span></label>"
            f'<div class="ti-own" data-own hidden><label class="ti-sr" for="{ident}-text">Your own answer</label>'
            f'<textarea id="{ident}-text" rows="2" maxlength="2000" data-other-text></textarea></div></div>'
        )
    hint = '<p class="ti-help">Choose every one that applies.</p>' if question["multiple"] else ""
    return f'<fieldset class="ti-options"><legend class="ti-sr">{inline(question["title"])}</legend>{options}</fieldset>{hint}'


def _rank(question: dict[str, Any], name: str) -> str:
    items = "".join(
        f'<li data-item="{esc(item["id"])}"><span class="ti-place" data-place>{index}</span>'
        f'<span class="ti-item-text">{_described(item)}</span><span class="ti-moves">'
        f'<button type="button" class="ti-icon" data-move="-1" aria-label="Move {esc(item["label"])} up">&uarr;</button>'
        f'<button type="button" class="ti-icon" data-move="1" aria-label="Move {esc(item["label"])} down">&darr;</button>'
        "</span></li>"
        for index, item in enumerate(question["items"], 1)
    )
    return (
        '<p class="ti-help">First is most important. Move the rows until the order is yours.</p>'
        f'<ol class="ti-rank" data-rank>{items}</ol>'
        f'<label class="ti-check" for="{name}-confirmed"><input type="checkbox" id="{name}-confirmed" data-confirmed>'
        "This order is right</label>"
    )


def _scale(question: dict[str, Any], name: str) -> str:
    steps = question["steps"]
    recommendation = question["recommendation"]
    recommended = recommendation["pick"]
    stops = ""
    for value in range(1, steps + 1):
        ident = f"{name}-{value}"
        near = question["low"] if value == 1 else question["high"] if value == steps else ""
        spoken = f"{value} of {steps}" + (f", {near}" if near else "")
        mark = ' class="ti-stop ti-stop-recommended"' if value == recommended else ' class="ti-stop"'
        stops += (
            f'<span{mark}><input type="radio" name="{name}" id="{ident}" value="{value}" data-stop '
            f'aria-label="{esc(spoken)}"><label for="{ident}" aria-hidden="true">{value}</label></span>'
        )
    return (
        f'<fieldset class="ti-scale"><legend class="ti-sr">{inline(question["title"])}</legend>'
        f'<span class="ti-pole">{inline(question["low"])}</span><span class="ti-stops">{stops}</span>'
        f'<span class="ti-pole ti-pole-high">{inline(question["high"])}</span></fieldset>'
    )


def _allocate(question: dict[str, Any], name: str) -> str:
    items = ""
    for item in question["items"]:
        ident = f"{name}-item-{item['id']}"
        label = esc(item["label"])
        items += (
            f'<li data-item="{esc(item["id"])}"><label for="{ident}">{_described(item)}</label>'
            f'<span class="ti-amount"><button type="button" class="ti-icon" data-step="-1" aria-label="Less for {label}">'
            f'&minus;</button><input type="number" id="{ident}" min="0" max="{question["total"]}" '
            f'step="{question["step"]}" value="0" inputmode="numeric" data-amount>'
            f'<button type="button" class="ti-icon" data-step="1" aria-label="More for {label}">+</button></span>'
            '<span class="ti-share" aria-hidden="true"><span data-share></span></span></li>'
        )
    return (
        f'<p class="ti-left" data-left role="status"></p><ul class="ti-allocate">{items}</ul>'
        f'<p class="ti-help">Spread {question["total"]} {esc(question["unit"])} across these. More means it matters more.</p>'
    )


def _matrix(question: dict[str, Any], name: str) -> str:
    head = "".join(f'<th scope="col">{inline(column["label"])}</th>' for column in question["columns"])
    rows = ""
    for row in question["rows"]:
        cells = ""
        for column in question["columns"]:
            ident = f"{name}-{row['id']}_{column['id']}"
            cells += (
                f'<td><input type="radio" name="{name}-{esc(row["id"])}" id="{ident}" value="{esc(column["id"])}" '
                f'data-row="{esc(row["id"])}" aria-label="{esc(row["label"])}: {esc(column["label"])}">'
                f'<label for="{ident}" aria-hidden="true">{inline(column["label"])}</label></td>'
            )
        rows += f'<tr><th scope="row">{_described(row)}</th>{cells}</tr>'
    return (
        '<div class="ti-matrix-wrap"><table class="ti-matrix"><thead><tr><td></td>'
        f"{head}</tr></thead><tbody>{rows}</tbody></table></div>"
    )


def _confirm(question: dict[str, Any], name: str) -> str:
    source = f"<footer>From {inline(question['source'])}</footer>" if question["source"] else ""
    return (
        f'<blockquote class="ti-statement"><p>{inline(question["statement"])}</p>{source}</blockquote>'
        '<fieldset class="ti-verdict"><legend class="ti-sr">Is this right?</legend>'
        f'<span class="ti-pill"><input type="radio" name="{name}" id="{name}-confirm" value="confirm" data-verdict>'
        f'<label for="{name}-confirm">That is right</label></span>'
        f'<span class="ti-pill"><input type="radio" name="{name}" id="{name}-correct" value="correct" data-verdict>'
        f'<label for="{name}-correct">Not quite</label></span></fieldset>'
        f'<div class="ti-own" data-own hidden><label for="{name}-correction">What is right?</label>'
        f'<textarea id="{name}-correction" rows="2" maxlength="2000" data-correction></textarea></div>'
    )


def _text(question: dict[str, Any], name: str) -> str:
    placeholder = f' placeholder="{esc(question["placeholder"])}"' if question["placeholder"] else ""
    return (
        f'<textarea class="ti-text" rows="{6 if question["long"] else 3}" maxlength="5000"{placeholder} '
        f'aria-labelledby="{name}-title" data-text></textarea>'
    )


CONTROLS = {
    "choice": _choice,
    "rank": _rank,
    "scale": _scale,
    "allocate": _allocate,
    "matrix": _matrix,
    "confirm": _confirm,
    "text": _text,
}


def _pick_in_words(question: dict[str, Any], pick: Any) -> str:
    kind = question["kind"]
    if kind == "choice":
        letters = {option["id"]: _letter(index) for index, option in enumerate(question["options"])}
        labels = {option["id"]: option["label"] for option in question["options"]}
        return " and ".join(f"{letters[entry]} ({inline(labels[entry])})" for entry in pick)
    if kind == "rank":
        labels = {item["id"]: item["label"] for item in question["items"]}
        return ", then ".join(inline(labels[entry]) for entry in pick)
    if kind == "scale":
        return f"{pick} of {question['steps']}"
    if kind == "allocate":
        labels = {item["id"]: item["label"] for item in question["items"]}
        return ", ".join(f"{inline(labels[entry])} {amount}" for entry, amount in pick.items() if amount)
    rows = {row["id"]: row["label"] for row in question["rows"]}
    columns = {column["id"]: column["label"] for column in question["columns"]}
    return "; ".join(f"{inline(rows[row])}: {inline(columns[column])}" for row, column in pick.items())


def _recommendation(question: dict[str, Any]) -> str:
    recommendation = question["recommendation"]
    if recommendation is None:
        return ""
    if recommendation["pick"] is None:
        lead = "No strong preference."
    else:
        lead = f"{_pick_in_words(question, recommendation['pick'])}."
    return (
        '<aside class="ti-recommendation"><h3>Recommendation</h3>'
        f"<p><strong>{lead}</strong> {inline(recommendation['reason'])}</p></aside>"
    )


def render_question(question: dict[str, Any], number: int) -> str:
    name = f"control-{number}"
    dimension = f'<span class="ti-chip">{inline(question["dimension"])}</span>' if question["dimension"] else ""
    return (
        f'<section class="ti-question" id="q-{esc(question["id"])}" data-question="{esc(question["id"])}" '
        f'data-kind="{question["kind"]}" aria-labelledby="{name}-title">'
        f'<header class="ti-question-head"><span class="ti-number">Question {number}</span>{dimension}'
        '<span class="ti-state" data-state></span></header>'
        f'<h2 id="{name}-title">{inline(question["title"])}</h2>'
        f'<p class="ti-why"><strong>Why this matters.</strong> {inline(question["why"])}</p>'
        f"{render_figures(question)}"
        f'<div class="ti-control">{CONTROLS[question["kind"]](question, name)}</div>'
        f"{_recommendation(question)}"
        f'<footer class="ti-question-foot"><label class="ti-check" for="{name}-unsure">'
        f'<input type="checkbox" id="{name}-unsure" data-unsure>Not sure. Your call, or ask me another way</label>'
        f'<details class="ti-note"><summary>Add a note</summary><textarea rows="2" maxlength="2000" data-note '
        f'aria-label="Note on question {number}"></textarea></details></footer></section>'
    )


def _progress(progress: Optional[dict[str, Any]]) -> str:
    if progress is None:
        return ""
    target = progress["target"]
    rows = ""
    for entry in progress["entries"]:
        note = f'<span class="ti-entry-note">{inline(entry["note"])}</span>' if entry["note"] else ""
        if entry["value"] is not None:
            met = ' data-met="true"' if target is not None and entry["value"] >= target else ""
            marker = f'<span class="ti-target" style="left:{target}%"></span>' if target is not None else ""
            rows += (
                f'<li class="ti-meter"{met}><span class="ti-entry-label">{inline(entry["label"])}</span>'
                f'<span class="ti-entry-value">{entry["value"]}%</span><span class="ti-track" aria-hidden="true">'
                f'<span class="ti-fill" style="width:{entry["value"]}%"></span>{marker}</span>{note}</li>'
            )
        else:
            rows += (
                f'<li class="ti-node" data-state="{entry["state"]}" style="--depth:{entry["depth"]}">'
                f'<span class="ti-entry-label">{inline(entry["label"])}</span>'
                f'<span class="ti-entry-value">{entry["state"]}</span>{note}</li>'
            )
    goal = f'<p class="ti-help">The interview aims for {target}% on each.</p>' if target is not None else ""
    return (
        f'<section class="ti-panel" aria-labelledby="ti-progress"><h2 id="ti-progress">{inline(progress["label"])}</h2>'
        f'<ul class="ti-progress">{rows}</ul>{goal}</section>'
    )


def catalog_of(round_: dict[str, Any]) -> dict[str, Any]:
    """What the runtime needs to know about the round: its identity and each question's shape."""
    questions: list[dict[str, Any]] = []
    for question in round_["questions"]:
        shape: dict[str, Any] = {"id": question["id"], "kind": question["kind"]}
        if question["kind"] == "choice":
            shape.update(
                options=[option["id"] for option in question["options"]],
                multiple=question["multiple"],
                other=question["other"],
            )
        elif question["kind"] in ("rank", "allocate"):
            shape["items"] = [item["id"] for item in question["items"]]
            if question["kind"] == "allocate":
                shape.update(total=question["total"], step=question["step"], unit=question["unit"])
        elif question["kind"] == "scale":
            shape["steps"] = question["steps"]
        elif question["kind"] == "matrix":
            shape.update(
                rows=[row["id"] for row in question["rows"]], columns=[column["id"] for column in question["columns"]]
            )
        questions.append(shape)
    return {
        "session": round_["session"]["id"],
        "round": round_["number"],
        "fingerprint": round_["fingerprint"],
        "questions": questions,
    }


def content_policy(script: str, mode: str) -> str:
    """Only the runtime may run, and it may reach only the helper that served the page."""
    script_hash = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
    connect = " connect-src 'self';" if mode == LIVE else ""
    return (
        f"default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; img-src data:;"
        f"{connect} base-uri 'none'; form-action 'none'"
    )


def render_page(round_: dict[str, Any], css: str, script: str, *, mode: str, key: str = "", expires_at: int = 0) -> str:
    session = round_["session"]
    number = round_["number"]
    questions = "".join(render_question(question, index) for index, question in enumerate(round_["questions"], 1))
    outline = "".join(
        f'<li><a href="#q-{esc(question["id"])}"><span class="ti-outline-title">{inline(question["title"])}</span>'
        f'<span class="ti-outline-state" data-outline="{esc(question["id"])}"></span></a></li>'
        for question in round_["questions"]
    )
    # Round 1 has no answers yet: what it shows is the interviewer's starting hypothesis.
    heading = "Where I am starting from" if number == 1 else "What I took from your answers so far"
    synthesis = (
        f'<section class="ti-synthesis"><h2>{heading}</h2>'
        + "".join(f"<p>{inline(paragraph)}</p>" for paragraph in round_["synthesis"])
        + "</section>"
    )
    topic = f" · {esc(session['topic'])}" if session["topic"] else ""
    send = "Send answers" if mode == LIVE else "Copy answers"
    how = (
        "Answers go straight to the agent in your terminal, on this computer only."
        if mode == LIVE
        else "This page is not connected to the agent. Copy your answers and paste them into the chat."
    )
    copy = '<button type="button" class="ti-button" data-copy>Copy answers</button>' if mode == LIVE else ""
    config = {"mode": mode, "key": key, "expiresAt": expires_at}
    title = f"Round {number} · {session['title']}"
    return (
        "<!doctype html>\n"
        f'<html lang="en" class="no-js" data-session="{esc(session["id"])}">\n<head>\n<meta charset="utf-8">\n'
        "<!-- Interview round built by trackbed:discovery:interview (scripts/interview-ui.py). A working artifact, "
        "not project source: do not review it as code, edit it by hand, or commit it. -->\n"
        f'<meta http-equiv="Content-Security-Policy" content="{content_policy(script, mode)}">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light dark">\n'
        '<meta name="referrer" content="no-referrer">\n'
        f"<title>{esc(title)}</title>\n<style>{css}</style>\n</head>\n<body>\n"
        '<a class="ti-skip" href="#main">Skip to the questions</a>\n'
        f'<header class="ti-masthead"><p class="ti-brand"><strong>{inline(session["title"])}</strong>'
        f"<span>Interview · round {number}{topic}</span></p>"
        "</header>\n"
        '<div class="ti-layout"><aside class="ti-side">'
        f"{_progress(round_['progress'])}"
        '<nav class="ti-panel" aria-labelledby="ti-outline" data-view="ask"><h2 id="ti-outline">This round</h2>'
        f'<ol class="ti-outline">{outline}</ol><p class="ti-help" data-count></p></nav></aside>\n'
        '<main class="ti-main" id="main" tabindex="-1">\n'
        '<div data-view="ask">'
        f'<header class="ti-head"><p class="ti-kicker">Round {number}</p><h1>{inline(round_["title"])}</h1>'
        f"{synthesis}</header>\n"
        '<div class="ti-notice" data-notice role="alert" hidden><p data-notice-text></p>'
        "</div>\n"
        f"<form data-form novalidate>\n{questions}\n"
        '<section class="ti-send" aria-labelledby="ti-send"><h2 id="ti-send">Send this round</h2>'
        '<label for="ti-round-note">Anything else worth knowing? <span class="ti-optional">Optional</span></label>'
        '<textarea id="ti-round-note" rows="3" maxlength="5000" data-round-note></textarea>'
        '<label class="ti-check" for="ti-wrap-up"><input type="checkbox" id="ti-wrap-up" data-wrap-up>'
        "That is enough questions. Write it up after this round</label>"
        '<p class="ti-count" data-count></p>'
        f'<p class="ti-actions"><button type="submit" class="ti-button ti-primary" data-send>{send}</button>{copy}</p>'
        f'<p class="ti-help" data-send-help>{how}</p>'
        '<div class="ti-own" data-copy-box hidden><label for="ti-copy-text">Copy this and paste it into the chat</label>'
        '<textarea id="ti-copy-text" rows="6" readonly data-copy-text></textarea></div>'
        "</section></form></div>\n"
        '<div class="ti-after" data-view="sent" hidden><h1 tabindex="-1">Answers sent</h1>'
        "<p>You can close this tab. If there’s another round, it will open in a new tab.</p></div>\n"
        '<noscript><p class="ti-notice">This page needs JavaScript to record and send your answers. '
        "Answer in the chat instead.</p></noscript>\n"
        "</main></div>\n"
        '<dialog id="ti-inspect" aria-labelledby="ti-inspect-title"><header>'
        '<h2 id="ti-inspect-title">Screenshot</h2>'
        '<button type="button" class="ti-button ti-dismiss" autofocus>Close</button></header>'
        '<div class="ti-inspect-scroll" tabindex="0"></div></dialog>\n'
        '<p class="ti-toast" data-toast role="status" hidden></p>\n'
        f'<script type="application/json" id="trackbed-interview-round">{safe_json(catalog_of(round_))}</script>\n'
        f'<script type="application/json" id="trackbed-interview-config">{safe_json(config)}</script>\n'
        f"<script>{script}</script>\n</body>\n</html>\n"
    )
