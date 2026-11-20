"""Validate and render evidence beside a browser interview question or option."""

from __future__ import annotations

import base64
import html
import re
import sys
from pathlib import Path
from typing import Any, Optional
from xml.etree import ElementTree

from interview_ui_fields import Problems, _integer, _keys, _objects, text_of

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from visual_evidence_images import ImageProblem, embed_image  # noqa: E402

FIGURE_KINDS = ("steps", "sketch", "bars", "code", "table", "chart", "screenshot")
# A sketch is only ever shown through <img>, where it cannot run script or load anything.
# These are refused anyway, so a sketch saved out of the page stays inert too.
SVG_ACTIVE_RE = re.compile(
    r"<\s*(?:script|foreignObject|iframe|embed|object|image)\b|\son[a-z]+\s*=|"
    r"""(?:href|src)\s*=\s*["'](?!\s*#)|@import""",
    re.I,
)
SVG_EXTERNAL_URL_RE = re.compile(r"""url\((?!\s*["']?\s*#)""", re.I)
SVG_OPEN_RE = re.compile(r"^\s*<svg(?:\s|>)")

MAX_SVG_CHARS = 60_000
MAX_CODE_CHARS = 4_000


class RoundImages:
    """Read only screenshot files placed beside this round and bound the size of its HTML."""

    def __init__(self, directory: Optional[Path]) -> None:
        self.directory = directory
        self.encoded_bytes = 0

    def read(self, name: str, where: str, problems: Problems) -> str:
        if not self.directory or not re.fullmatch(r"[\w.-][\w. -]*\.(?:png|jpe?g|webp)", name, re.I):
            problems.add(where, "use a PNG, JPEG or WebP filename beside the round JSON")
            return ""
        path = self.directory / name
        try:
            if path.is_symlink() or not path.is_file():
                raise ImageProblem("must be a regular image file beside the round")
            if self.encoded_bytes >= 32 * 1024 * 1024:
                raise ImageProblem("screenshots exceed the 32 MB embedded limit for this round")
            data, _, _ = embed_image(path, screenshot=True)
            self.encoded_bytes += len(data)
            if self.encoded_bytes > 32 * 1024 * 1024:
                raise ImageProblem("screenshots exceed the 32 MB embedded limit for this round")
        except (OSError, ImageProblem) as error:
            problems.add(where, f"{name}: {error}")
            return ""
        return data


def read_figures(raw: dict[str, Any], where: str, problems: Problems, media: RoundImages) -> dict[str, Any]:
    if "figures" not in raw:
        return {"figure": _figure(raw.get("figure"), f"{where}.figure", problems, media)}
    if "figure" in raw:
        problems.add(where, "use either figure or figures")
    entries = _objects(raw["figures"], f"{where}.figures", problems, low=1, high=4)
    return {
        "figures": [_figure(entry, f"{where}.figures[{i}]", problems, media) for i, entry in enumerate(entries[:4])]
    }


def _chart(raw: dict[str, Any], where: str, problems: Problems) -> dict[str, Any]:
    labels = raw.get("labels")
    if not isinstance(labels, list) or not 2 <= len(labels) <= 24:
        problems.add(f"{where}.labels", "give 2 to 24 ordered x-axis labels")
        labels = []
    ticks = [text_of(label, f"{where}.labels[{i}]", problems, limit=40) for i, label in enumerate(labels)]
    series = []
    for i, entry in enumerate(_objects(raw.get("series"), f"{where}.series", problems, low=1, high=4)):
        here = f"{where}.series[{i}]"
        _keys(entry, ("label", "values"), here, problems)
        values = entry.get("values")
        if not isinstance(values, list) or len(values) != len(ticks):
            problems.add(f"{here}.values", "give one number per x-axis label")
            values = []
        elif any(type(v) not in (int, float) or not -1e100 <= v <= 1e100 for v in values):
            problems.add(f"{here}.values", "use finite numbers within ±1e100")
            values = []
        series.append({"label": text_of(entry.get("label"), f"{here}.label", problems, limit=80), "values": values})
    return {"labels": ticks, "series": series, "unit": text_of(raw.get("unit"), f"{where}.unit", problems, limit=40)}


def _is_svg_document(svg: str) -> bool:
    try:
        root = ElementTree.fromstring(svg)
    except (ElementTree.ParseError, UnicodeError):
        return False
    return root.tag == "{http://www.w3.org/2000/svg}svg" and bool(root.get("viewBox", "").strip())


def _figure(raw: Any, where: str, problems: Problems, media: RoundImages) -> Optional[dict[str, Any]]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        problems.add(where, "must be an object")
        return None
    kind = raw.get("kind")
    if kind not in FIGURE_KINDS:
        problems.add(f"{where}.kind", f"must be one of {', '.join(FIGURE_KINDS)}")
        return None
    figure: dict[str, Any] = {
        "kind": kind,
        "caption": text_of(raw.get("caption"), f"{where}.caption", problems, limit=300, required=False),
    }
    if kind in ("chart", "screenshot"):
        fields = ("labels", "series", "unit") if kind == "chart" else ("file", "alt", "callouts")
        _keys(raw, ("kind", "caption", "title", "source", *fields), where, problems)
        figure["title"] = text_of(raw.get("title"), f"{where}.title", problems, limit=160)
        figure["source"] = text_of(raw.get("source"), f"{where}.source", problems, limit=300)
        if kind == "chart":
            figure.update(_chart(raw, where, problems))
        else:
            name = text_of(raw.get("file"), f"{where}.file", problems, limit=200)
            figure["image"] = media.read(name, f"{where}.file", problems)
            figure["alt"] = text_of(raw.get("alt"), f"{where}.alt", problems, limit=300)
            figure["callouts"] = []
            for i, pin in enumerate(_objects(raw.get("callouts", []), f"{where}.callouts", problems, low=0, high=6)):
                here = f"{where}.callouts[{i}]"
                _keys(pin, ("x", "y", "text"), here, problems)
                figure["callouts"].append(
                    {
                        "x": _integer(pin.get("x"), f"{here}.x", problems, low=0, high=100),
                        "y": _integer(pin.get("y"), f"{here}.y", problems, low=0, high=100),
                        "text": text_of(pin.get("text"), f"{here}.text", problems, limit=240),
                    }
                )
    elif kind == "steps":
        _keys(raw, ("kind", "caption", "steps"), where, problems)
        steps = raw.get("steps")
        if not isinstance(steps, list) or not 2 <= len(steps) <= 8:
            problems.add(f"{where}.steps", "must be a list of 2 to 8 steps")
            steps = []
        figure["steps"] = [
            text_of(step, f"{where}.steps[{index}]", problems, limit=120) for index, step in enumerate(steps)
        ]
    elif kind == "sketch":
        _keys(raw, ("kind", "caption", "svg", "alt"), where, problems)
        svg = raw.get("svg")
        # Start with the element itself, so the XML parser never receives a document type declaration.
        if not isinstance(svg, str) or not SVG_OPEN_RE.match(svg):
            problems.add(f"{where}.svg", "must be one complete <svg> element with a viewBox")
            svg = ""
        elif len(svg) > MAX_SVG_CHARS:
            problems.add(f"{where}.svg", f"is {len(svg)} characters; keep a sketch within {MAX_SVG_CHARS}")
        elif SVG_ACTIVE_RE.search(svg) or SVG_EXTERNAL_URL_RE.search(html.unescape(svg)):
            problems.add(
                f"{where}.svg",
                "must not hold script, event handlers, embedded HTML or images, or a reference outside itself",
            )
        elif not _is_svg_document(svg):
            problems.add(f"{where}.svg", "must be one complete <svg> element with a viewBox and SVG namespace")
        figure["svg"] = svg
        figure["alt"] = text_of(raw.get("alt"), f"{where}.alt", problems, limit=300)
    elif kind == "bars":
        _keys(raw, ("kind", "caption", "bars", "unit"), where, problems)
        bars: list[dict[str, Any]] = []
        for index, entry in enumerate(_objects(raw.get("bars"), f"{where}.bars", problems, low=2, high=8)):
            here = f"{where}.bars[{index}]"
            _keys(entry, ("label", "value"), here, problems)
            value = entry.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= sys.float_info.max:
                problems.add(f"{here}.value", "must be a finite number that is not negative")
                value = 0
            bars.append({"label": text_of(entry.get("label"), f"{here}.label", problems, limit=80), "value": value})
        figure["bars"] = bars
        figure["unit"] = text_of(raw.get("unit"), f"{where}.unit", problems, limit=24, required=False)
    elif kind == "code":
        _keys(raw, ("kind", "caption", "code", "language"), where, problems)
        code = raw.get("code")
        if not isinstance(code, str) or not code.strip() or len(code) > MAX_CODE_CHARS:
            problems.add(f"{where}.code", f"must be 1 to {MAX_CODE_CHARS} characters of text")
            code = ""
        figure["code"] = code.strip("\n")
        figure["language"] = text_of(raw.get("language"), f"{where}.language", problems, limit=24, required=False)
    else:
        _keys(raw, ("kind", "caption", "columns", "rows"), where, problems)
        columns = raw.get("columns")
        if not isinstance(columns, list) or not 2 <= len(columns) <= 6:
            problems.add(f"{where}.columns", "must be a list of 2 to 6 column headings")
            columns = []
        figure["columns"] = [
            text_of(column, f"{where}.columns[{index}]", problems, limit=80) for index, column in enumerate(columns)
        ]
        rows = raw.get("rows")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 10:
            problems.add(f"{where}.rows", "must be a list of 1 to 10 rows")
            rows = []
        figure["rows"] = []
        for index, row in enumerate(rows):
            if not isinstance(row, list) or len(row) != len(columns):
                problems.add(f"{where}.rows[{index}]", "must have one cell per column")
                continue
            figure["rows"].append(
                [text_of(cell, f"{where}.rows[{index}][{at}]", problems, limit=240) for at, cell in enumerate(row)]
            )
    return figure


CODE_RE = re.compile(r"`([^`\n]+)`")
BOLD_RE = re.compile(r"\*\*([^*\n]+)\*\*")


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def inline(value: str) -> str:
    """Escaped text, with `code` and **bold** as the only markup."""
    return BOLD_RE.sub(r"<strong>\1</strong>", CODE_RE.sub(r"<code>\1</code>", esc(value)))


def _render_chart(figure: dict[str, Any]) -> str:
    series, ticks = figure["series"], figure["labels"]
    values = [v for line in series for v in line["values"]]
    bottom, top = min(values), max(values)

    def y(v: float) -> float:
        return 95 if top == bottom else 16 + 158 * ((top - v) / (top - bottom))

    bounds = [top] if bottom == top else [top, bottom]
    plot = "".join(
        f'<line x1="86" x2="590" y1="{y(v):.2f}" y2="{y(v):.2f}" class="ti-gridline"/>'
        f'<text x="79" y="{y(v):.2f}" text-anchor="end" dominant-baseline="middle">{v:g}</text>'
        for v in bounds
    )
    legend = []
    for i, line in enumerate(series):
        points = [(86 + 504 * j / (len(ticks) - 1), y(v)) for j, v in enumerate(line["values"])]
        coords = " ".join(f"{px:.2f},{py:.2f}" for px, py in points)
        plot += f'<g class="ti-series ti-series-{i}"><polyline points="{coords}"/>'
        plot += "".join(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="3"/>' for px, py in points) + "</g>"
        legend.append(
            f'<li class="ti-series-{i}"><svg viewBox="0 0 24 8" aria-hidden="true">'
            f'<path d="M0 4h24"/></svg>{inline(line["label"])}</li>'
        )
    table = render_figure(
        {
            "kind": "table",
            "caption": "",
            "columns": ["Observation", *(line["label"] for line in series)],
            "rows": [[label, *(str(line["values"][j]) for line in series)] for j, label in enumerate(ticks)],
        }
    )
    return (
        f'<ul class="ti-chart-legend">{"".join(legend)}</ul><p class="ti-chart-unit">{inline(figure["unit"])}</p>'
        f'<svg class="ti-chart" viewBox="0 0 608 190" role="img" aria-label="{esc(figure["title"])}">{plot}</svg>'
        f'<div class="ti-chart-ticks"><span>{inline(ticks[0])}</span><span>{inline(ticks[-1])}</span></div>'
        f'<div class="ti-inspect-point"><label>Inspect an observation'
        f'<input type="range" min="0" max="{len(ticks) - 1}" value="{len(ticks) - 1}"></label>'
        "<output></output></div>"
        f"<details><summary>View chart data</summary>{table}</details>"
    )


def _render_screenshot(figure: dict[str, Any]) -> str:
    pins = "".join(
        f'<span class="ti-pin" aria-hidden="true" style="left:{pin["x"]}%;top:{pin["y"]}%">{i}</span>'
        for i, pin in enumerate(figure["callouts"], 1)
    )
    notes = "".join(f"<li>{inline(pin['text'])}</li>" for pin in figure["callouts"])
    return (
        f'<button type="button" class="ti-enlarge" aria-label="Enlarge screenshot: {esc(figure["title"])}">'
        f'<span class="ti-capture"><img src="{figure["image"]}" alt="{esc(figure["alt"])}">{pins}</span>'
        '<span class="ti-enlarge-label">Enlarge screenshot</span></button>'
        + (f'<ol class="ti-callouts">{notes}</ol>' if notes else "")
    )


def render_figures(owner: dict[str, Any]) -> str:
    return "".join(render_figure(figure) for figure in owner.get("figures", [owner.get("figure")]))


def render_figure(figure: Optional[dict[str, Any]]) -> str:
    if figure is None:
        return ""
    kind = figure["kind"]
    if kind == "chart":
        body = _render_chart(figure)
    elif kind == "screenshot":
        body = _render_screenshot(figure)
    elif kind == "steps":
        body = '<ol class="ti-steps">' + "".join(f"<li>{inline(step)}</li>" for step in figure["steps"]) + "</ol>"
    elif kind == "sketch":
        data = base64.b64encode(figure["svg"].encode("utf-8")).decode("ascii")
        body = f'<img class="ti-sketch" src="data:image/svg+xml;base64,{data}" alt="{esc(figure["alt"])}">'
    elif kind == "bars":
        highest = max(bar["value"] for bar in figure["bars"]) or 1
        unit = f" {esc(figure['unit'])}" if figure["unit"] else ""
        body = (
            '<dl class="ti-bars">'
            + "".join(
                f"<div><dt>{inline(bar['label'])}</dt><dd>"
                f'<span><span class="ti-bar" style="width:{100 * (bar["value"] / highest):g}%"></span></span>'
                f"<span>{format(bar['value'], 'g')}{unit}</span></dd></div>"
                for bar in figure["bars"]
            )
            + "</dl>"
        )
    elif kind == "code":
        language = f' data-language="{esc(figure["language"])}"' if figure["language"] else ""
        body = f'<pre class="ti-code"{language} tabindex="0"><code>{esc(figure["code"])}</code></pre>'
    else:
        head = "".join(f'<th scope="col">{inline(column)}</th>' for column in figure["columns"])
        rows = "".join(
            "<tr>"
            + "".join(
                f'<th scope="row">{inline(cell)}</th>' if at == 0 else f"<td>{inline(cell)}</td>"
                for at, cell in enumerate(row)
            )
            + "</tr>"
            for row in figure["rows"]
        )
        body = (
            '<div class="ti-table-wrap" tabindex="0"><table class="ti-table">'
            f"<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>"
        )
    caption = f"<figcaption>{inline(figure['caption'])}</figcaption>" if figure["caption"] else ""
    title = f'<h3 class="ti-evidence-title">{inline(figure["title"])}</h3>' if "title" in figure else ""
    source = f'<p class="ti-source">Source · {inline(figure["source"])}</p>' if "source" in figure else ""
    return f'<figure class="ti-figure ti-figure-{kind}">{title}{body}{caption}{source}</figure>'
