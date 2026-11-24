"""Render one item of a decision document: its evidence, options, recommendation, and the reader's decision.

Everything written here is escaped. The runtime finds its elements by the `data-*` attributes, so
renaming one means changing `assets/decisions.js` with it.
"""

from __future__ import annotations

import html
import re

from decisions_model import CUSTOM, MAX_NOTES_CHARS, NO_CHANGE, STATUSES, Evidence, Item

CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def inline(value: str) -> str:
    """Escaped text, with `code spans` kept as code. Content is data: no other markup passes."""
    return CODE_SPAN_RE.sub(lambda match: f"<code>{match.group(1)}</code>", esc(value))


def paragraphs(lines: list[str], class_name: str = "") -> str:
    attr = f' class="{class_name}"' if class_name else ""
    return "".join(f"<p{attr}>{inline(line)}</p>" for line in lines)


def prose_or_list(lines: list[str]) -> str:
    """One entry reads as a paragraph; several read as a list."""
    if len(lines) == 1:
        return f"<p>{inline(lines[0])}</p>"
    return "<ul>" + "".join(f"<li>{inline(line)}</li>" for line in lines) + "</ul>"


def item_href(item_id: str, part: str = "") -> str:
    return "#item-" + esc(item_id) + (f"/{part}" if part else "")


def label_chips(item: Item) -> str:
    return "".join(f'<span class="td-chip" data-tone="{label.tone}">{esc(label.text)}</span>' for label in item.labels)


def choice_text(item: Item, option_id: str) -> str:
    """The same wording the runtime uses for a choice."""
    if option_id == NO_CHANGE:
        return f"No change · {item.no_change}"
    for option in item.options:
        if option.id == option_id:
            return f"Option {option.letter} · {option.name}"
    return ""


ADDED_MARK = '<span class="td-added">Made for this document</span>'


def source_line(entry: Evidence, tag: str = "p") -> str:
    """Where an entry comes from, with a visible mark on anything the source did not itself hold."""
    mark = ADDED_MARK if entry.origin == "added" else ""
    if not entry.source and not mark:
        return ""
    source = f"Source: {inline(entry.source)}" if entry.source else ""
    return f'<{tag} class="td-source">{mark}{source}</{tag}>'


def render_chart(entry: Evidence) -> str:
    """Bars as a table: every value is readable without the drawing, and the drawing needs no script."""
    top = max([value for _, value, _ in entry.bars] + [entry.limit_value])
    rows = []
    for label, value, text in entry.bars:
        muted = bool(entry.emphasis) and label not in entry.emphasis
        limit = (
            f'<span class="td-limit" style="--at:{entry.limit_value / top:.4f}" aria-hidden="true"></span>'
            if entry.limit_value
            else ""
        )
        rows.append(
            f'<tr{" data-muted" if muted else ""}><th scope="row">{inline(label)}</th>'
            f'<td><span class="td-bar-track">{limit}<span class="td-bar" style="--size:{value / top:.4f}"></span>'
            f'<span class="td-bar-value">{esc(text)}</span></span></td></tr>'
        )
    key = (
        f'<p class="td-limit-key"><span aria-hidden="true"></span>{inline(entry.limit_label)}: '
        f"{esc(entry.limit_text)}</p>"
        if entry.limit_value
        else ""
    )
    return f'<table class="td-bars"><tbody>{"".join(rows)}</tbody></table>{key}'


def render_evidence(item: Item) -> str:
    if not item.evidence:
        return ""
    images = [entry for entry in item.evidence if entry.kind == "image"]
    blocks: list[str] = []
    gallery = ""
    if images:
        tabs = ""
        if len(images) > 1:
            buttons = "".join(
                f'<button type="button" class="td-tab" data-shot="{index}" aria-pressed="{str(index == 0).lower()}">'
                f"{esc(image.label or f'View {index + 1}')}</button>"
                for index, image in enumerate(images)
            )
            tabs = f'<div class="td-tabs" role="group" aria-label="Choose a capture">{buttons}</div>'
        figures = []
        for index, image in enumerate(images):
            size = f' width="{image.width}" height="{image.height}"' if image.width and image.height else ""
            tall = image.width and image.height and image.height > image.width * 1.15
            classes = "td-shot" + (" td-shot--tall" if tall else "") + (" td-shot--focus" if image.focus else "")
            style = f' style="object-position:{esc(image.focus)}"' if image.focus else ""
            mark = "Cropped · open the full capture" if image.focus else "Open full size"
            figures.append(
                f'<figure class="td-figure" data-figure="{index}">'
                f'<button type="button" class="td-zoom" data-zoom aria-label="Open full size: {esc(image.label or image.caption)}">'
                f'<span class="{classes}"><img src="{image.data_url}" alt="{esc(image.alt)}"{size}{style} decoding="async">'
                f'<span class="td-zoom-mark" aria-hidden="true">{mark}</span></span></button>'
                f"<figcaption>{inline(image.caption)}{source_line(image, 'span')}</figcaption></figure>"
            )
        gallery = f'<div class="td-gallery" data-gallery>{tabs}{"".join(figures)}</div>'
    # Evidence reads in the order the content gives it. The images share one gallery, at the first image's place.
    for entry in item.evidence:
        source = source_line(entry)
        if entry.kind == "image":
            blocks.append(gallery)
            gallery = ""
        elif entry.kind == "table":
            head = (
                "<thead><tr>"
                + "".join(f'<th scope="col">{esc(column)}</th>' for column in entry.columns)
                + "</tr></thead>"
                if entry.columns
                else ""
            )
            rows = "".join(
                "<tr>"
                + "".join(
                    f'<th scope="row">{inline(cell)}</th>' if position == 0 else f"<td>{inline(cell)}</td>"
                    for position, cell in enumerate(row)
                )
                + "</tr>"
                for row in entry.rows
            )
            title = f"<h3>{esc(entry.label)}</h3>" if entry.label else ""
            blocks.append(
                f'<section class="td-record">{title}<p>{inline(entry.caption)}</p>'
                f'<div class="td-scroll"><table>{head}<tbody>{rows}</tbody></table></div>{source}</section>'
            )
        elif entry.kind == "chart":
            title = f"<h3>{esc(entry.label)}</h3>" if entry.label else ""
            blocks.append(
                f'<section class="td-record td-chart">{title}<p>{inline(entry.caption)}</p>'
                f"{render_chart(entry)}{source}</section>"
            )
        elif entry.kind == "excerpt":
            title = f"<h3>{esc(entry.label)}</h3>" if entry.label else ""
            blocks.append(
                f'<section class="td-record">{title}<p>{inline(entry.caption)}</p>'
                f'<pre tabindex="0"><code>{esc(entry.text)}</code></pre>{source}</section>'
            )
    return (
        f'<section class="td-evidence" data-part="evidence" aria-labelledby="evidence-{esc(item.id)}">'
        f'<h2 id="evidence-{esc(item.id)}" tabindex="-1">Evidence</h2>{"".join(blocks)}</section>'
    )


def render_options(item: Item) -> str:
    name = f"choice-{esc(item.id)}"
    cards = []
    for option in item.options:
        input_id = f"choice-{esc(item.id)}-{option.id}"
        recommended = option.id == item.recommended
        badge = '<span class="td-rec">Recommended</span>' if recommended else ""
        benefits = (
            f'<div class="td-pro"><h4>What it gives you</h4>{prose_or_list(option.benefits)}</div>'
            if option.benefits
            else ""
        )
        tradeoffs = (
            f'<div class="td-con"><h4>What it costs</h4>{prose_or_list(option.tradeoffs)}</div>'
            if option.tradeoffs
            else ""
        )
        cards.append(
            f'<section class="td-option" data-option="{option.id}"{" data-recommended" if recommended else ""}>'
            f'<p class="td-option-top"><span class="td-mono">Option {option.letter}</span>'
            f"{badge}</p>"
            f"<h3>{inline(option.name)}</h3>{paragraphs(option.summary)}{benefits}{tradeoffs}"
            f'<p class="td-pick"><input type="radio" id="{input_id}" name="{name}" value="{option.id}" data-choice>'
            f'<label for="{input_id}">Choose option {option.letter}<span class="td-sr">: {esc(option.name)}</span></label>'
            f'<span class="td-yours" data-yours hidden>Your choice</span></p></section>'
        )
    others = [
        f'<div class="td-other" data-option="{CUSTOM}"><input type="radio" id="choice-{esc(item.id)}-{CUSTOM}" '
        f'name="{name}" value="{CUSTOM}" data-choice><label for="choice-{esc(item.id)}-{CUSTOM}">A different approach'
        "<span>Describe it in your notes.</span></label></div>"
    ]
    if item.no_change:
        recommended = item.recommended == NO_CHANGE
        badge = '<em class="td-rec">Recommended</em>' if recommended else ""
        others.append(
            f'<div class="td-other" data-option="{NO_CHANGE}"{" data-recommended" if recommended else ""}>'
            f'<input type="radio" id="choice-{esc(item.id)}-{NO_CHANGE}" name="{name}" value="{NO_CHANGE}" data-choice>'
            f'<label for="choice-{esc(item.id)}-{NO_CHANGE}">{esc(item.no_change)}'
            f"{badge}"
            f"<span>{esc(item.no_change_description)}</span></label></div>"
        )
    count = len(item.options)
    intro = (
        "No ready-made option is offered here. Describe your approach, or leave things as they are."
        if count == 0
        else "Pick one. You can change or clear it at any time."
    )
    return (
        f'<section class="td-options-block" data-part="options" aria-labelledby="options-{esc(item.id)}">'
        f'<h2 id="options-{esc(item.id)}" tabindex="-1">Options</h2>'
        f'<fieldset class="td-fieldset"><legend>{intro}</legend>'
        f'<div class="td-options">{"".join(cards)}</div>'
        f'<div class="td-others">{"".join(others)}</div></fieldset></section>'
    )


def render_recommendation(item: Item) -> str:
    target = choice_text(item, item.recommended)
    # With no recommended option, the summary line says so; a second line would only repeat it.
    which = f'<p class="td-rec-target">{esc(target)}</p>' if target else ""
    uncertainty = (
        f'<div class="td-uncertain"><h3>What is uncertain</h3>{prose_or_list(item.uncertainty)}</div>'
        if item.uncertainty
        else ""
    )
    return (
        f'<section class="td-recommendation" aria-labelledby="rec-{esc(item.id)}">'
        f'<p class="td-kicker" id="rec-{esc(item.id)}">Recommendation</p>{which}'
        f"<h2>{inline(item.recommendation)}</h2>{paragraphs(item.reasoning)}{uncertainty}</section>"
    )


def render_decision(item: Item) -> str:
    key = esc(item.id)
    options = "".join(
        f'<option value="{value}"{" disabled" if value == "decided" else ""}>{label}</option>'
        for value, label in STATUSES.items()
    )
    return (
        f'<section class="td-decision" data-part="choice" aria-labelledby="decision-{key}">'
        f'<div class="td-decision-head"><h2 id="decision-{key}" tabindex="-1">Your decision</h2>'
        '<p class="td-save" data-save-status role="status"></p></div>'
        '<div class="td-review" data-review hidden><p data-review-text></p>'
        '<button type="button" class="td-button" data-confirm>Keep my earlier choice</button></div>'
        '<p class="td-summary-line" data-choice-summary>Not decided · No approach selected</p>'
        '<div class="td-editor">'
        f'<div><label for="status-{key}">Decision status</label>'
        f'<select id="status-{key}" data-decision-status aria-describedby="status-help-{key}">{options}</select>'
        f'<p class="td-help" id="status-help-{key}" data-status-help>Choose an approach above to mark this decided.</p>'
        '<button type="button" class="td-button" data-clear disabled>Clear my choice</button></div>'
        f'<div><label for="notes-{key}">Your notes and reasoning</label>'
        f'<textarea id="notes-{key}" data-notes rows="5" maxlength="{MAX_NOTES_CHARS}" '
        'placeholder="Why this choice, what to change, or what needs discussion"></textarea></div></div>'
        '<p class="td-help">Recording a choice changes nothing else. '
        '<a href="#choices" data-route>See all your choices</a></p>'
        '<div class="td-print-decision"><p><strong>Your decision:</strong> <span data-print-choice>Not decided</span></p>'
        "<p data-print-notes></p></div></section>"
    )


def render_item(item: Item, index: int) -> str:
    key = esc(item.id)
    status = f'<p class="td-status-line">{inline(item.status)}</p>' if item.status else ""
    impact = f'<div class="td-impact"><h3>Why it matters</h3>{paragraphs(item.impact)}</div>' if item.impact else ""
    steps = (
        '<ol class="td-steps" aria-label="Sequence">'
        + "".join(f"<li>{inline(step)}</li>" for step in item.steps)
        + "</ol>"
        if item.steps
        else ""
    )
    closing = ""
    if item.success_criteria or item.evidence_limits:
        success = (
            f"<section><h3>How to tell it worked</h3>{prose_or_list(item.success_criteria)}</section>"
            if item.success_criteria
            else ""
        )
        limits = (
            f"<section><h3>Limits of the evidence</h3>{prose_or_list(item.evidence_limits)}</section>"
            if item.evidence_limits
            else ""
        )
        closing = f'<div class="td-closing">{success}{limits}</div>'
    facts = [("Id in the source", item.id)]
    if item.source_title:
        facts.append(("Title in the source", item.source_title))
    if item.source_location:
        facts.append(("Where", item.source_location))
    facts.extend(item.details)
    facts.append(("Item version", item.fingerprint))
    details = "".join(f"<div><dt>{esc(label)}</dt><dd>{inline(value)}</dd></div>" for label, value in facts)
    return (
        f'<article class="td-item" id="item-{key}" data-item="{key}" data-index="{index}">'
        f'<header class="td-item-head"><p class="td-eyebrow"><span class="td-mono">{key}</span>{label_chips(item)}</p>'
        f'<h1 tabindex="-1" data-heading>{inline(item.title)}</h1>{status}</header>'
        f'<section class="td-lead"><h2>Summary</h2>{paragraphs(item.summary)}{impact}</section>'
        f"{steps}{render_evidence(item)}{render_options(item)}{render_recommendation(item)}{render_decision(item)}{closing}"
        f'<details class="td-trace"><summary>Source and details</summary><dl>{details}</dl></details></article>'
    )
