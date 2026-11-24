"""Render a decision document's model as one HTML page: the frame, the overview, the index, the reader's
choices, and the walkthrough of every item.

Everything the reader sees is written by this module and `decisions_item`, escaped; the runtime only
keeps the reader's record.
"""

from __future__ import annotations

import json
from typing import Any

from decisions_item import esc, inline, item_href, label_chips, paragraphs, render_item
from decisions_model import STATUSES, Document, Item, Model, squash
from inline_page import csp_meta, json_script


STATUS_OPTIONS = "".join(f'<option value="{value}">{label}</option>' for value, label in STATUSES.items())


def render_sidebar(document: Document, items: list[Item]) -> str:
    total = len(items)
    nav_items = "".join(
        f'<a class="td-nav-item" href="{item_href(item.id)}" data-route>'
        f'<span class="td-mono">{esc(item.id)}</span><span class="td-nav-title">{inline(item.title)}</span>'
        f'<span class="td-nav-state" data-nav-state="{esc(item.id)}" hidden></span></a>'
        for item in items
    )
    primary = [("overview", "Overview")]
    if document.order:
        primary.append(("order", "Suggested order"))
    primary.append(("items", f"All {document.noun_many}"))
    primary.append(("choices", "Your choices"))
    primary.append(("about", "Evidence and scope"))
    primary_nav = "".join(
        f'<a href="#{key}" data-route>{label}'
        + ('<span class="td-count" data-progress-short></span>' if key == "choices" else "")
        + "</a>"
        for key, label in primary
    )

    return (
        '<aside class="td-sidebar" data-sidebar>'
        f'<nav class="td-primary-nav" aria-label="Sections"><div class="td-primary-links">{primary_nav}</div>'
        f'<button type="button" class="td-browse" data-browse aria-controls="td-item-nav" aria-expanded="false" '
        f'aria-label="Browse {esc(document.noun_many)}">{esc(document.noun_many.capitalize())}</button></nav>'
        f'<p class="td-nav-label"><span>{esc(document.noun_many.capitalize())}</span><span>{total}</span></p>'
        f'<nav class="td-item-nav" id="td-item-nav" aria-label="{esc(document.noun_many.capitalize())}">{nav_items}</nav></aside>'
    )


def render_overview(document: Document, items: list[Item], by_id: dict[str, Item]) -> str:
    total = len(items)
    noun = document.noun_one if total == 1 else document.noun_many
    metrics = ""
    if document.metrics:
        metrics = (
            '<div class="td-metrics">'
            + "".join(
                f"<div><strong>{esc(value)}</strong><span>{esc(label)}</span></div>"
                for value, label in document.metrics
            )
            + "</div>"
        )
    start = ""
    if document.start_with:
        cards = "".join(
            f'<a class="td-card" href="{item_href(item_id)}" data-route><span class="td-mono">{esc(item_id)}</span>'
            f"<h3>{inline(by_id[item_id].title)}</h3><p>{inline(reason or by_id[item_id].summary[0])}</p>"
            '<span class="td-card-link">Evidence, options, and recommendation</span></a>'
            for item_id, reason in document.start_with
            if item_id in by_id
        )
        start = f'<section class="td-start"><h2>Start here</h2><div class="td-cards">{cards}</div></section>'
    first = items[0].id
    return (
        '<section class="td-view" id="overview" data-view="overview"><div class="td-hero">'
        + (f'<p class="td-kicker">{esc(document.kicker)}</p>' if document.kicker else "")
        + f'<h1 tabindex="-1" data-heading>{inline(document.title)}</h1>'
        + paragraphs(document.summary, "td-deck")
        + metrics
        + "</div>"
        + start
        + '<section class="td-howto"><h2>How to use this document</h2>'
        f"<p>Each of the {total} {esc(noun)} has its evidence, the options with what each gives and costs, "
        "and a recommendation with its reasoning. Record your own choice and notes on each one. "
        "The recommendation is advice; nothing is selected for you.</p>"
        "<p>The page saves your choices in this browser as you go, says when it has, and warns you when it cannot. "
        "<strong>Save a copy</strong> downloads this whole "
        "document with your choices inside it, <strong>Copy to clipboard</strong> copies that same document so you can "
        "paste it, and <strong>Export choices</strong> gives you a small file to hand "
        "back to the agent. Nothing is sent anywhere, and recording a choice changes nothing else.</p>"
        f'<p class="td-actions"><a class="td-button td-primary" href="{item_href(first)}" data-route>Start the walkthrough</a>'
        f'<a class="td-button" href="#items" data-route>Browse all {total}</a>'
        '<a class="td-button" href="#choices" data-route>Your choices <span data-progress-short></span></a></p></section></section>'
    )


def render_order(document: Document, by_id: dict[str, Item]) -> str:
    if not document.order:
        return ""
    groups = "".join(
        '<section class="td-group"><div>'
        + (f'<p class="td-kicker">{esc(group.label)}</p>' if group.label else "")
        + f"<h2>{inline(group.title)}</h2></div><div>{paragraphs(group.summary)}"
        + (f'<p class="td-why"><strong>Why here:</strong> {inline(group.why)}</p>' if group.why else "")
        + '<ul class="td-group-items">'
        + "".join(
            f'<li><a href="{item_href(member)}" data-route><span class="td-mono">{esc(member)}</span> {inline(by_id[member].title)}</a></li>'
            for member in group.items
            if member in by_id
        )
        + "</ul></div></section>"
        for group in document.order
    )
    return (
        '<section class="td-view" id="order" data-view="order"><header class="td-page-head">'
        '<h1 tabindex="-1" data-heading>Suggested order</h1>'
        "<p>An order to decide and act in. It is a suggestion; every item can be decided on its own.</p></header>"
        f"{groups}</section>"
    )


def render_index(document: Document, items: list[Item]) -> str:
    total = len(items)
    noun = document.noun_one if total == 1 else document.noun_many
    label_names = sorted({label.text for item in items for label in item.labels})
    label_filter = ""
    if label_names:
        label_filter = (
            '<div class="td-field"><label for="td-filter-label">Label</label><select id="td-filter-label" data-filter="label">'
            '<option value="">All labels</option>'
            + "".join(f'<option value="{esc(name)}">{esc(name)}</option>' for name in label_names)
            + "</select></div>"
        )
    index_rows = "".join(
        f'<tr data-index-row="{esc(item.id)}" data-labels="{esc(json.dumps([label.text for label in item.labels]))}" '
        f'data-search="{esc(" ".join([item.id, item.title, *item.summary, item.recommendation, *[label.text for label in item.labels]]).lower())}">'
        f'<th scope="row"><a href="{item_href(item.id)}" data-route><span class="td-mono">{esc(item.id)}</span>'
        f'<strong>{inline(item.title)}</strong></a><span class="td-row-labels">{label_chips(item)}</span></th>'
        f'<td data-label="Summary">{inline(item.summary[0])}</td>'
        f'<td data-label="Recommendation">{inline(item.recommendation)}</td>'
        f'<td data-label="Your choice" data-index-choice="{esc(item.id)}"></td></tr>'
        for item in items
    )
    return (
        '<section class="td-view" id="items" data-view="items"><header class="td-page-head">'
        f'<h1 tabindex="-1" data-heading>All {total} {esc(noun)}</h1>'
        "<p>Open one for its evidence, options, and recommendation. The last column shows what you have recorded.</p></header>"
        '<div class="td-filters"><div class="td-field"><label for="td-filter-search">Search</label>'
        '<input id="td-filter-search" type="search" data-filter="search" autocomplete="off"></div>'
        f"{label_filter}"
        '<div class="td-field"><label for="td-filter-status">Your decision</label><select id="td-filter-status" data-filter="status">'
        f'<option value="">Any status</option>{STATUS_OPTIONS}</select></div></div>'
        '<p class="td-filter-status"><span data-filter-count role="status"></span>'
        '<button type="button" class="td-button" data-filter-clear>Clear filters</button></p>'
        '<div class="td-scroll" data-index-table><table class="td-index"><thead><tr>'
        f'<th scope="col">{esc(document.noun_one.capitalize())}</th><th scope="col">Summary</th>'
        '<th scope="col">Recommendation</th><th scope="col">Your choice</th></tr></thead>'
        f"<tbody>{index_rows}</tbody></table></div>"
        f'<p class="td-empty" data-filter-empty hidden>Nothing matches these filters.</p></section>'
    )


def render_choices(document: Document, items: list[Item]) -> str:
    total = len(items)
    noun = document.noun_one if total == 1 else document.noun_many
    choice_rows = "".join(
        f'<tr data-choice-row="{esc(item.id)}"><th scope="row"><a href="{item_href(item.id)}" data-route>'
        f'<span class="td-mono">{esc(item.id)}</span><strong>{inline(item.title)}</strong></a></th>'
        '<td data-label="Your approach"><span data-row-approach></span><span class="td-versus" data-row-versus></span></td>'
        '<td data-label="Status"><span class="td-badge" data-row-status></span></td>'
        '<td class="td-notes-cell" data-label="Your notes"><span class="td-notes" data-row-notes></span></td>'
        f'<td class="td-row-links"><a href="{item_href(item.id, "evidence" if item.evidence else "")}" data-route>'
        f"{'Evidence' if item.evidence else 'Summary'}</a>"
        f'<a href="{item_href(item.id, "options")}" data-route>Options</a></td></tr>'
        for item in items
    )
    counters = "".join(
        f'<div><strong data-status-count="{value}">0</strong><span>{STATUSES[value].lower()}</span></div>'
        for value in ("decided", "discuss", "deferred", "open")
    )
    return (
        '<section class="td-view" id="choices" data-view="choices"><header class="td-page-head">'
        '<h1 tabindex="-1" data-heading>Your choices</h1>'
        f"<p>What you have decided so far, across all {total} {esc(noun)}. The recommendations stay on each item for reference.</p></header>"
        f'<div class="td-progress" aria-label="Decision progress">{counters}</div>'
        '<p class="td-review-count" data-review-count hidden></p>'
        '<section class="td-tools" aria-label="Keep and move your choices"><h2>Keep your choices</h2>'
        '<p class="td-save" data-save-status role="status"></p>'
        "<p>The line above says whether this browser has your choices. To keep them anywhere else, save a copy, copy the document to the clipboard, or export them. "
        "Nothing is sent anywhere.</p>"
        '<p class="td-actions"><button type="button" class="td-button td-primary" data-save-copy>Save a copy</button>'
        '<button type="button" class="td-button" data-copy-page>Copy to clipboard</button>'
        '<button type="button" class="td-button" data-export>Export choices (JSON)</button>'
        '<button type="button" class="td-button" data-import>Import choices</button>'
        '<input type="file" data-import-file accept=".json,.html,application/json,text/html" hidden></p>'
        '<dl class="td-tool-help"><div><dt>Save a copy</dt><dd>Downloads this whole document with your choices and notes inside it.</dd></div>'
        "<div><dt>Copy to clipboard</dt><dd>Copies that same document, choices and notes included, to paste to the agent.</dd></div>"
        "<div><dt>Export choices</dt><dd>Downloads a small file of your choices to hand to the agent or to import later.</dd></div>"
        "<div><dt>Import choices</dt><dd>Restores choices from an export or a saved copy of this document.</dd></div></dl>"
        '<p class="td-message" data-message role="status"></p></section>'
        '<div class="td-table-head"><h2>All your choices</h2><label>Show <select data-choice-filter>'
        f'<option value="">All {total}</option>{STATUS_OPTIONS}<option value="review">Needs review</option></select></label></div>'
        '<div class="td-scroll"><table class="td-choices"><thead><tr>'
        f'<th scope="col">{esc(document.noun_one.capitalize())}</th><th scope="col">Your approach</th><th scope="col">Status</th>'
        '<th scope="col" class="td-notes-cell">Your notes</th><th scope="col">Go to</th></tr></thead>'
        f"<tbody>{choice_rows}</tbody></table></div>"
        '<p class="td-help" data-choice-count role="status"></p>'
        f'<p class="td-print-note">Your notes are printed with each {esc(document.noun_one)}.</p>'
        '<p class="td-boundary">This is a record of what you decided. It does not change the source it was built from, '
        "and nothing here is carried out until you ask for it.</p></section>"
    )


def render_viewer(document: Document, items: list[Item]) -> str:
    return (
        '<section class="td-view" id="viewer" data-view="item"><div class="td-pager">'
        '<span class="td-mono" data-pager-count></span><span class="td-pager-actions">'
        f'<a class="td-button" href="#items" data-route>All {esc(document.noun_many)}</a>'
        '<button type="button" class="td-button" data-previous>Previous</button>'
        '<button type="button" class="td-button" data-next>Next</button></span></div>'
        + "".join(render_item(item, index) for index, item in enumerate(items))
        + "</section>"
    )


def render_about(document: Document) -> str:
    sections = "".join(
        f"<section><h2>{inline(section.title)}</h2>{paragraphs(section.paragraphs)}"
        + (
            "<ul>" + "".join(f"<li>{inline(bullet)}</li>" for bullet in section.bullets) + "</ul>"
            if section.bullets
            else ""
        )
        + "</section>"
        for section in document.sections
    )
    sources = ""
    if document.sources:
        sources = (
            "<section><h2>Built from</h2><ul>"
            + "".join(
                f"<li><strong>{inline(label)}</strong>{' · ' + inline(detail) if detail else ''}</li>"
                for label, detail in document.sources
            )
            + "</ul></section>"
        )
    facts = [("Document id", document.id), ("Content version", document.fingerprint), ("Built", document.generated)]
    if document.producer:
        facts.insert(0, ("Produced by", document.producer))
    return (
        '<section class="td-view" id="about" data-view="about"><header class="td-page-head">'
        '<h1 tabindex="-1" data-heading>Evidence and scope</h1>'
        "<p>What this document rests on, and what it does not establish.</p></header>"
        f'<div class="td-about">{sections}{sources}'
        "<section><h2>How your choices are kept</h2>"
        "<p>Choices and notes are saved in this browser under this document's id, when the browser allows it, "
        "and inside any copy you save or copy to the clipboard. "
        "The page has no network access. When this document is rebuilt, a choice stays attached to its item only while "
        "the item and its options are unchanged; a choice made on an earlier version comes back marked for review.</p>"
        '<dl class="td-facts">'
        + "".join(f"<div><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>" for label, value in facts)
        + "</dl></section></div></section>"
    )


def render_dialogs() -> str:
    return (
        '<dialog class="td-dialog td-zoom-dialog" data-zoom-dialog aria-labelledby="td-zoom-title">'
        '<div class="td-dialog-head"><h2 id="td-zoom-title">Evidence</h2>'
        '<button type="button" class="td-button" data-close autofocus>Close</button></div>'
        '<p class="td-dialog-tools"><button type="button" class="td-button" data-fit aria-pressed="true">Fit to width</button>'
        '<button type="button" class="td-button" data-actual aria-pressed="false">Original size</button></p>'
        '<div class="td-zoom-scroll" tabindex="0"><img alt="" data-zoom-image></div>'
        '<p class="td-dialog-caption" data-zoom-caption></p></dialog>\n'
        '<dialog class="td-dialog td-import-dialog" data-import-dialog aria-labelledby="td-import-title">'
        '<div class="td-dialog-head"><h2 id="td-import-title">Import choices</h2>'
        '<button type="button" class="td-button" data-close>Cancel</button></div>'
        '<div class="td-dialog-body"><p data-import-description></p>'
        '<fieldset class="td-fieldset"><legend>What should happen to choices you already have here?</legend>'
        '<div class="td-other"><input type="radio" id="td-import-keep" name="td-import-mode" value="keep" checked>'
        '<label for="td-import-keep">Keep mine<span>Import only into items where you have recorded nothing.</span></label></div>'
        '<div class="td-other"><input type="radio" id="td-import-replace" name="td-import-mode" value="replace">'
        '<label for="td-import-replace">Replace mine<span>Use the imported choice and notes wherever the file has one.</span></label></div>'
        '</fieldset><p class="td-help" data-import-preview></p>'
        '<button type="button" class="td-button td-primary" data-import-confirm>Import</button></div></dialog>\n'
    )


def render_page(model: Model, seed: dict[str, Any], css: str, script: str) -> str:
    document = model.document
    by_id = {item.id: item for item in model.items}
    catalog = {
        "documentId": document.id,
        "title": document.title,
        "fingerprint": document.fingerprint,
        "generated": document.generated,
        "nounOne": document.noun_one,
        "nounMany": document.noun_many,
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "fingerprint": item.fingerprint,
                "options": [{"id": option.id, "name": option.name, "letter": option.letter} for option in item.options],
                "noChange": item.no_change,
                "recommended": item.recommended,
            }
            for item in model.items
        ],
    }
    description = squash(document.summary[0])[:300] if document.summary else document.title
    return (
        "<!doctype html>\n"
        f'<html lang="en" class="no-js" data-document="{esc(document.id)}">\n<head>\n<meta charset="utf-8">\n'
        "<!-- Decision document built by trackbed:visual:decisions (scripts/build-decisions.py). A working artifact, "
        "not project source: do not review it as code, edit it by hand, or commit it. -->\n"
        f"{csp_meta(script)}\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light dark">\n'
        f'<meta name="description" content="{esc(description)}">\n'
        f"<title>{esc(document.title)}</title>\n<style>{css}</style>\n</head>\n<body>\n"
        '<a class="td-skip" href="#main" data-skip>Skip to content</a>\n'
        '<header class="td-masthead"><a class="td-brand" href="#overview" data-route>'
        f"<strong>{inline(document.title)}</strong><span>Decision document</span></a>"
        '<p class="td-actions"><a class="td-button" href="#choices" data-route>Your choices <span data-progress-short></span></a>'
        '<button type="button" class="td-button td-primary" data-save-copy>Save a copy</button>'
        '<button type="button" class="td-button" data-copy-page>Copy to clipboard</button>'
        '<button type="button" class="td-button" data-print>Print</button></p></header>\n'
        f'<div class="td-layout">{render_sidebar(document, model.items)}\n'
        f'<main class="td-main" id="main" tabindex="-1">\n'
        f"{render_overview(document, model.items, by_id)}\n{render_order(document, by_id)}\n"
        f"{render_index(document, model.items)}\n{render_choices(document, model.items)}\n"
        f"{render_viewer(document, model.items)}\n{render_about(document)}\n"
        f'<footer class="td-footer"><span>{inline(document.title)} · built {esc(document.generated)}</span>'
        "<span>One file · works offline · sends nothing</span></footer></main></div>\n"
        f"{render_dialogs()}"
        '<p class="td-toast" data-toast role="status" hidden></p>\n'
        f'<script type="application/json" id="trackbed-decisions-catalog">{json_script(catalog)}</script>\n'
        f'<script type="application/json" id="trackbed-decisions-state">{json_script(seed)}</script>\n'
        f"<script>{script}</script>\n</body>\n</html>\n"
    )
