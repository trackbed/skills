#!/usr/bin/env python3
"""Finalize a hand-written visual report page.

A skill run with `--visual` writes one HTML page beside its Markdown report. This
script checks that page against the contract in
`shared/visual/references/visual-report.md`, then copies the shared interactive
runtime into the page's two placeholders and adds a Content-Security-Policy that
allows only that runtime script and no network requests.

Exit codes: 0 finalized (or, with `--check`, already finalized), 1 the page breaks
the contract and was left untouched, 2 usage or file error.
"""

from __future__ import annotations

import argparse
import re
import stat
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from inline_page import csp_meta, read_inline_asset, write_page  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "shared" / "visual" / "assets"
RUNTIME_ATTR = "data-trackbed-runtime"
# Written once near the top of a finalized page, for a person or agent that opens it as a file.
NOTICE = (
    "<!-- Visual report page finalized by scripts/visual-report.py: a snapshot of a Markdown report. "
    "Working artifact, not project source. Do not review it as code, edit it by hand, or commit it. -->"
)
SEVERITIES = ("critical", "high", "medium", "low", "suggestion")
# What a page is for decides how it is laid out. Each shape has its own template and its own required part.
SHAPES = ("findings", "plan", "qa", "inquiry", "assessment", "fixes", "changes")
SHAPE_PARTS = {
    "assessment": ("data-scorecard", "an assessment page needs its scores in an element marked data-scorecard"),
    "qa": ("data-tested", "a qa page needs what was tested in an element marked data-tested"),
    "changes": (
        "data-compare",
        "a changes page needs a before and after for each change, in an element marked data-compare",
    ),
}
# The two sides of a before and after comparison on a changes page, in the order they are written.
COMPARE_SIDES = ("before", "after")
VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
)
# Browsers ignore the slash on these, so a self-closing one swallows the rest of the page as its text.
RAW_TEXT_TAGS = frozenset({"script", "style", "textarea", "title"})
FORBIDDEN_TAGS = frozenset({"applet", "base", "embed", "form", "frame", "frameset", "iframe", "link", "object"})
URL_ATTRS = frozenset({"action", "formaction", "href", "imagesrcset", "poster", "src", "srcset", "xlink:href"})
SRCSET_ATTRS = frozenset({"imagesrcset", "srcset"})
# SVG elements that load the file their href names, so it is held to the <img src> rule. The parser lowercases tags.
SVG_RESOURCE_TAGS = frozenset({"feimage", "image", "use"})
LINK_SCHEMES = frozenset({"http", "https", "mailto"})
# Browsers drop these from anywhere in a URL, so `java&#9;script:` still reads as `javascript:`.
URL_IGNORED_RE = re.compile(r"[\t\n\r]")
# ...and trim C0 controls and spaces from both ends before reading the scheme.
URL_TRIMMED = "".join(chr(code) for code in range(0x21))
# Facet names become `data-<name>` attributes, so they cannot reuse a name the contract already gives a meaning.
RESERVED_FACETS = frozenset(
    {
        "accept-label",
        "collapsed",
        "commit",
        "compare",
        "controls",
        "copy",
        "noun",
        "scorecard",
        "shape",
        "tested",
        "where",
        "dismiss-label",
        "entry",
        "facets",
        "generated",
        "id",
        "loc",
        "producer",
        "removes",
        "report",
        "report-header",
        "root",
        "run-id",
        "section",
        "severity-label",
        "side",
        "sortable",
        "source",
        "triage",
        "trackbed-ready",
        "trackbed-runtime",
    }
)
SCHEME_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9+.\-]*):")
IMAGE_DATA_RE = re.compile(r"^data:image/(?:avif|gif|jpe?g|png|webp);base64,[A-Za-z0-9+/=\s]+$")
FACET_RE = re.compile(r"^[a-z][a-z0-9-]*$")
ENTRY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
GENERATED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?$")
MAX_FOLLOWUP_CHARS = 200

Attrs = dict[str, str]


@dataclass
class Span:
    """A half-open character range in the page source."""

    start: int
    end: int


@dataclass
class Open:
    tag: str
    attrs: Attrs
    has_heading: bool = False
    has_lead: bool = False
    # On a changes page: the comparisons a decided change holds, and the sides a comparison holds.
    needs_compare: bool = False
    compares: int = 0
    sides: list[str] = field(default_factory=list)


@dataclass
class Scan:
    problems: list[str] = field(default_factory=list)
    entries: int = 0
    sections: int = 0
    style_slots: list[Span] = field(default_factory=list)
    script_slots: list[Span] = field(default_factory=list)
    policy_tags: list[Span] = field(default_factory=list)
    charset_end: int | None = None


class PageParser(HTMLParser):
    """Collects contract problems and the source ranges the runtime is written into."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.scan = Scan()
        self._line_starts = [0]
        for match in re.finditer("\n", source):
            self._line_starts.append(match.end())
        self._stack: list[Open] = []
        self._slot_start: int | None = None
        self._has_doctype = False
        self._html_lang = ""
        self._has_viewport = False
        self._title = ""
        self._in_title = False
        self._mains = 0
        self._has_title_heading = False
        self._shape = ""
        self._parts: set[str] = set()
        self._ids: set[str] = set()
        self._entry_ids: set[str] = set()
        # On a fixes page: which fix entry already names each finding it removes.
        self._removed_by: dict[str, str] = {}

    # ---------- source positions ----------

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_starts[line - 1] + column

    def _problem(self, message: str) -> None:
        line, _ = self.getpos()
        self.scan.problems.append(f"line {line}: {message}")

    def _inside(self, tag: str, attr: str | None = None) -> bool:
        return any(node.tag == tag and (attr is None or attr in node.attrs) for node in self._stack)

    def _inside_attr(self, attr: str) -> bool:
        return any(attr in node.attrs for node in self._stack)

    # ---------- parser callbacks ----------

    def handle_decl(self, decl: str) -> None:
        if decl.lower().startswith("doctype html"):
            self._has_doctype = True

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag in RAW_TEXT_TAGS:
            self._problem(f"write <{tag} ...></{tag}>, not a self-closing <{tag} />, which a browser leaves open")
            start = self._offset()
            self._close_slot(tag, start + len(self.get_starttag_text() or ""))
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map: Attrs = {name: value or "" for name, value in attrs}
        start = self._offset()
        end = start + len(self.get_starttag_text() or "")
        self._check_attrs(tag, attr_map)

        if tag == "html":
            self._html_lang = attr_map.get("lang", "").strip()
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            self._check_meta(attr_map, Span(start, end))
        elif tag == "style" and RUNTIME_ATTR in attr_map:
            if not self._inside("head"):
                self._problem(f"<style {RUNTIME_ATTR}> must be inside <head>")
            self._slot_start = end
        elif tag == "script":
            if RUNTIME_ATTR not in attr_map:
                self._problem(f"only <script {RUNTIME_ATTR}></script> may appear; remove this <script>")
            elif "src" in attr_map or "type" in attr_map:
                self._problem(f"<script {RUNTIME_ATTR}> takes no other attributes")
            else:
                self._slot_start = end
        elif tag in FORBIDDEN_TAGS:
            self._problem(f"<{tag}> is not allowed in a visual report")
        elif tag == "main" and "data-report" in attr_map:
            self._mains += 1
            self._check_report(attr_map)

        for part, _ in SHAPE_PARTS.values():
            if part in attr_map:
                self._parts.add(part)
        if "data-section" in attr_map:
            self.scan.sections += 1
            if not self._inside("main", "data-report"):
                self._problem("data-section must be inside <main data-report>")
        if "data-entry" in attr_map:
            self._check_entry(attr_map)
        if "data-compare" in attr_map:
            self._check_compare(tag)
        if "data-side" in attr_map:
            self._check_side(tag, attr_map["data-side"].strip())
        if tag == "h1" and self._inside_attr("data-report-header"):
            self._has_title_heading = True
        if tag in {"h2", "h3"}:
            marker = "data-section" if tag == "h2" else "data-entry"
            for node in reversed(self._stack):
                if marker in node.attrs:
                    node.has_heading = True
                    break
        if tag == "p" and "data-where" not in attr_map:
            for node in reversed(self._stack):
                if "data-entry" in node.attrs:
                    node.has_lead = True
                    break
        if "data-where" in attr_map and not self._inside_attr("data-entry"):
            self._problem("data-where belongs inside an entry, directly after its <h3>")
        if tag == "svg" and attr_map.get("aria-hidden") != "true":
            if attr_map.get("role") != "img" or not attr_map.get("aria-label", "").strip():
                self._problem('an <svg> needs role="img" and an aria-label that says what it shows')
        if tag == "img" and "alt" not in attr_map:
            self._problem("an <img> needs an alt attribute that says what it shows")
        if tag not in VOID_TAGS:
            node = Open(tag, attr_map)
            node.needs_compare = "data-entry" in attr_map and self._shape == "changes" and self._decided(attr_map)
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        self._close_slot(tag, self._offset())
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index].tag != tag:
                continue
            for node in self._stack[index:]:
                self._check_closed(node)
            del self._stack[index:]
            break

    def _close_slot(self, tag: str, end: int) -> None:
        if tag not in {"style", "script"} or self._slot_start is None:
            return
        slots = self.scan.style_slots if tag == "style" else self.scan.script_slots
        slots.append(Span(self._slot_start, end))
        self._slot_start = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title += data

    # ---------- checks ----------

    def _check_closed(self, node: Open) -> None:
        if "data-section" in node.attrs and not node.has_heading:
            self._problem("a data-section needs an <h2> title")
        if "data-entry" in node.attrs:
            entry_id = node.attrs.get("data-id", "?")
            if not node.has_heading:
                self._problem(f"entry {entry_id} needs an <h3> title")
            if not node.has_lead:
                self._problem(
                    f"entry {entry_id} needs a lead paragraph: one or two plain sentences, before any fields, "
                    "saying what it is and why it matters"
                )
            if node.needs_compare and node.compares == 0:
                self._problem(
                    f"change {entry_id} needs a before and after: an element marked data-compare holding "
                    '<figure data-side="before"> and <figure data-side="after">'
                )
        if "data-compare" in node.attrs and node.sides != list(COMPARE_SIDES):
            self._problem(
                'a data-compare holds one <figure data-side="before"> and then one <figure data-side="after">, '
                f"found {', '.join(node.sides) or 'neither'}"
            )

    def _check_attrs(self, tag: str, attrs: Attrs) -> None:
        for name, value in attrs.items():
            if name.startswith("on"):
                self._problem(f"<{tag}> has the event handler attribute {name}; the page carries no script of its own")
            elif name == "srcdoc":
                self._problem(f"<{tag}> has srcdoc, which is not allowed")
            elif name in URL_ATTRS:
                self._check_url(tag, name, value)
        element_id = attrs.get("id", "").strip()
        if element_id:
            if element_id in self._ids:
                self._problem(f'id "{element_id}" is used more than once')
            self._ids.add(element_id)

    def _check_url(self, tag: str, name: str, value: str) -> None:
        if name in SRCSET_ATTRS:
            if tag not in {"img", "source"}:
                self._problem(f"<{tag} {name}> is not allowed; only <img> may load a file")
                return
            for candidate in srcset_urls(value):
                self._check_image_url(tag, name, candidate)
            return
        if name == "src":
            if tag != "img":
                self._problem(f"<{tag} src> is not allowed; only <img> may load a file")
            else:
                self._check_image_url(tag, name, value)
            return
        if tag in SVG_RESOURCE_TAGS and name in {"href", "xlink:href"}:
            self._check_image_url(tag, name, value)
            return
        scheme = url_scheme(value)
        if scheme and scheme not in LINK_SCHEMES:
            self._problem(f'<{tag} {name}> uses the "{scheme}:" scheme; use http, https, mailto, or a relative link')

    def _check_image_url(self, tag: str, name: str, value: str) -> None:
        """Hold a URL that loads a file to the <img src> rule: a relative path or an embedded image."""
        cleaned = URL_IGNORED_RE.sub("", value).strip(URL_TRIMMED)
        scheme = url_scheme(cleaned)
        if scheme == "data":
            if not IMAGE_DATA_RE.match(cleaned):
                self._problem(f"<{tag} {name}> data URL must be a base64 AVIF, GIF, JPEG, PNG, or WebP image")
        elif scheme or cleaned.startswith("//"):
            self._problem(f"<{tag} {name}> must use a relative path or a data URL, never a remote address")

    def _check_meta(self, attrs: Attrs, span: Span) -> None:
        if "charset" in attrs:
            self.scan.charset_end = span.end
        if attrs.get("name", "").lower() == "viewport":
            self._has_viewport = True
        if attrs.get("name") == "trackbed-followup":
            content = attrs.get("content", "")
            if not content.strip() or "\n" in content or len(content) > MAX_FOLLOWUP_CHARS:
                self._problem(
                    '<meta name="trackbed-followup"> needs one command on one line, '
                    f"at most {MAX_FOLLOWUP_CHARS} characters"
                )
        if "http-equiv" in attrs:
            if RUNTIME_ATTR in attrs:
                self.scan.policy_tags.append(span)
            else:
                self._problem("<meta http-equiv> is not allowed; this script adds the Content-Security-Policy")

    def _check_report(self, attrs: Attrs) -> None:
        for name in ("data-producer", "data-source"):
            if not attrs.get(name, "").strip():
                self._problem(f"<main data-report> needs {name}")
        self._shape = attrs.get("data-shape", "").strip()
        if self._shape not in SHAPES:
            self._problem(f"<main data-report> needs data-shape, one of {', '.join(SHAPES)}, as the skill names it")
        if "data-noun" in attrs and len(attrs["data-noun"].split()) != 2:
            self._problem('data-noun takes the singular and plural of what an entry is, such as "plan plans"')
        if not GENERATED_RE.match(attrs.get("data-generated", "").strip()):
            self._problem("<main data-report> needs data-generated as an ISO 8601 date or date-time")
        root = attrs.get("data-root", "")
        if root and not (root.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", root)):
            self._problem("data-root must be the absolute project root; omit it when unknown")
        for facet in attrs.get("data-facets", "").split():
            if not FACET_RE.match(facet):
                self._problem(f'facet "{facet}" must be lowercase letters, digits, and hyphens')
            elif facet in RESERVED_FACETS:
                self._problem(f'facet "{facet}" is a reserved name; choose another')

    def _check_entry(self, attrs: Attrs) -> None:
        self.scan.entries += 1
        entry_id = attrs.get("data-id", "").strip()
        if not self._inside("main", "data-report"):
            self._problem(f"entry {entry_id or '?'} must be inside <main data-report>")
        elif not self._inside_attr("data-section"):
            self._problem(f"entry {entry_id or '?'} must be inside a data-section, so the outline can list it")
        if self._inside_attr("data-entry"):
            self._problem(f"entry {entry_id or '?'} is nested inside another entry")
        if not ENTRY_ID_RE.match(entry_id):
            self._problem("every data-entry needs a data-id of letters, digits, dots, hyphens, or underscores")
        elif entry_id in self._entry_ids:
            self._problem(f'entry id "{entry_id}" is used more than once')
        self._entry_ids.add(entry_id)
        if self._shape == "fixes":
            self._check_removes(entry_id or "?", attrs)
        severity = attrs.get("data-severity")
        if severity is not None and severity not in SEVERITIES:
            self._problem(
                f'entry {entry_id or "?"} has data-severity="{severity}"; use one of {", ".join(SEVERITIES)} '
                "and put the report's own label in data-severity-label"
            )

    def _decided(self, attrs: Attrs) -> bool:
        """Whether the reader accepts or dismisses this entry, which neither it nor anything around it turns off."""
        return attrs.get("data-triage") != "off" and all(node.attrs.get("data-triage") != "off" for node in self._stack)

    def _check_compare(self, tag: str) -> None:
        """A comparison holds its two figures, belongs to one entry, and is never nested in another comparison."""
        if tag in VOID_TAGS:
            self._problem(f"data-compare belongs on an element that holds the two figures, not on <{tag}>")
            return
        if self._inside_attr("data-compare"):
            self._problem("a data-compare is nested inside another; give each comparison its own element")
        for node in reversed(self._stack):
            if "data-entry" in node.attrs:
                node.compares += 1
                return
        self._problem("data-compare belongs inside an entry, under its Before and after heading")

    def _check_side(self, tag: str, side: str) -> None:
        """Each side of a comparison is a named figure, directly in the comparison it belongs to."""
        if side not in COMPARE_SIDES:
            self._problem(f'data-side="{side}" is not a side; use before or after')
            return
        if tag != "figure" or not self._stack or "data-compare" not in self._stack[-1].attrs:
            self._problem(f'data-side="{side}" belongs on a <figure> directly inside a data-compare')
            return
        self._stack[-1].sides.append(side)

    def _check_removes(self, entry_id: str, attrs: Attrs) -> None:
        """A fix the reader decides on names the findings it removes, and each finding belongs to one fix."""
        if not self._decided(attrs):
            return
        findings = attrs.get("data-removes", "").split()
        if not findings:
            self._problem(
                f"fix {entry_id} needs data-removes with the IDs of the findings it removes, such as "
                'data-removes="RO-001 RO-002"'
            )
            return
        for finding in findings:
            if not ENTRY_ID_RE.match(finding):
                self._problem(
                    f'fix {entry_id} has "{finding}" in data-removes; separate finding IDs with spaces, such as '
                    'data-removes="RO-001 RO-002"'
                )
            elif self._removed_by.get(finding) == entry_id:
                self._problem(f"fix {entry_id} lists {finding} twice in data-removes")
            elif finding in self._removed_by:
                self._problem(
                    f"fix {entry_id} removes {finding}, which fix {self._removed_by[finding]} already removes; "
                    "a finding belongs to one fix"
                )
            else:
                self._removed_by[finding] = entry_id

    def finish(self) -> Scan:
        self.close()
        for node in self._stack:
            self._check_closed(node)
        document = self.scan.problems
        if not self._has_doctype:
            document.append("the page must start with <!doctype html>")
        if not self._html_lang:
            document.append("<html> needs a lang attribute")
        if self.scan.charset_end is None:
            document.append('<head> needs <meta charset="utf-8">')
        if not self._has_viewport:
            document.append('<head> needs <meta name="viewport" content="width=device-width, initial-scale=1">')
        if not self._title.strip():
            document.append("<title> must not be empty")
        if self._mains != 1:
            document.append(f"the page needs exactly one <main data-report>, found {self._mains}")
        if not self._has_title_heading:
            document.append("the page needs <header data-report-header> holding the <h1> title")
        part = SHAPE_PARTS.get(self._shape)
        if part and part[0] not in self._parts:
            document.append(part[1])
        if self.scan.sections == 0:
            document.append("the page needs at least one data-section")
        if len(self.scan.style_slots) != 1:
            document.append(
                f"the page needs exactly one <style {RUNTIME_ATTR}></style> in <head>, "
                f"found {len(self.scan.style_slots)}"
            )
        if len(self.scan.script_slots) != 1:
            document.append(
                f"the page needs exactly one <script {RUNTIME_ATTR}></script>, found {len(self.scan.script_slots)}"
            )
        if len(self.scan.policy_tags) > 1:
            document.append("the page carries more than one injected Content-Security-Policy; remove them and rerun")
        return self.scan


def url_scheme(value: str) -> str:
    """The lowercase scheme a browser reads from a URL attribute, or an empty string for a relative URL."""
    match = SCHEME_RE.match(URL_IGNORED_RE.sub("", value).strip(URL_TRIMMED))
    return match.group(1).lower() if match else ""


def srcset_urls(value: str) -> list[str]:
    """The URL of each image candidate in a srcset value, read the way the HTML standard reads them."""
    urls: list[str] = []
    position = 0
    while position < len(value):
        while position < len(value) and (value[position].isspace() or value[position] == ","):
            position += 1
        start = position
        while position < len(value) and not value[position].isspace():
            position += 1
        url = value[start:position]
        if url.endswith(","):
            urls.append(url.rstrip(","))
            continue
        if url:
            urls.append(url)
        # Skip the width or density descriptor, up to the comma that ends this candidate.
        depth = 0
        while position < len(value) and (depth or value[position] != ","):
            depth += {"(": 1, ")": -1}.get(value[position], 0)
            depth = max(depth, 0)
            position += 1
    return urls


def scan_page(source: str) -> Scan:
    parser = PageParser(source)
    parser.feed(source)
    return parser.finish()


def load_runtime(assets: Path = ASSETS) -> tuple[str, str]:
    """Return the runtime stylesheet and script as they are written into a page."""
    # The palette and fonts are a separate file because the decision document shares them.
    css = "".join(
        "\n" + read_inline_asset(assets / name, "</style").strip("\n") + "\n"
        for name in ("report-tokens.css", "report-runtime.css")
    )
    script = "\n" + read_inline_asset(assets / "report-runtime.js", "</script").strip("\n") + "\n"
    return css, script


def policy_tag(script: str) -> str:
    return csp_meta(script, image_sources="'self' data: file:", marker=RUNTIME_ATTR)


def finalize(source: str, scan: Scan, css: str, script: str) -> str:
    """Write the runtime into a page that passed `scan_page` with no problems."""
    if scan.charset_end is None:
        raise ValueError("page was not validated")
    edits: list[tuple[Span, str]] = [(scan.style_slots[0], css), (scan.script_slots[0], script)]
    if scan.policy_tags:
        edits.append((scan.policy_tags[0], policy_tag(script)))
    else:
        edits.append((Span(scan.charset_end, scan.charset_end), f"\n    {NOTICE}\n    {policy_tag(script)}"))
    parts: list[str] = []
    cursor = 0
    for span, text in sorted(edits, key=lambda edit: edit[0].start):
        parts.extend((source[cursor : span.start], text))
        cursor = span.end
    parts.append(source[cursor:])
    return "".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a visual report page and write the shared runtime into it.")
    parser.add_argument("page", type=Path, help="the hand-written .html page beside the Markdown report")
    parser.add_argument(
        "--check", action="store_true", help="validate and confirm the page is finalized; write nothing"
    )
    args = parser.parse_args(argv)
    page: Path = args.page

    if page.suffix.lower() != ".html":
        print(f"visual-report: {page} must be an .html file", file=sys.stderr)
        return 2
    if page.is_symlink() or not page.is_file():
        print(f"visual-report: {page} must be a regular file, not a symlink or a missing path", file=sys.stderr)
        return 2
    try:
        source = page.read_text(encoding="utf-8")
        css, script = load_runtime()
    except (OSError, UnicodeDecodeError, ValueError) as error:
        print(f"visual-report: {error}", file=sys.stderr)
        return 2

    scan = scan_page(source)
    if scan.problems:
        for problem in scan.problems:
            print(f"visual-report: {problem}", file=sys.stderr)
        print(
            f"visual-report: {len(scan.problems)} problem(s) in {page}; the page was not changed. Fix them and rerun.",
            file=sys.stderr,
        )
        return 1

    finalized = finalize(source, scan, css, script)
    if args.check:
        if finalized != source:
            print(f"visual-report: {page} is valid but not finalized; rerun without --check", file=sys.stderr)
            return 1
    elif finalized != source:
        try:
            write_page(page, finalized, mode=stat.S_IMODE(page.stat().st_mode))
        except OSError as error:
            print(f"visual-report: {error}", file=sys.stderr)
            return 2
    print(f"Visual report ready: {page.resolve()} ({scan.entries} entries, {scan.sections} sections)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
