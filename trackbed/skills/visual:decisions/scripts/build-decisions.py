#!/usr/bin/env python3
"""Build a self-contained decision document from a content file.

The content file (`references/content-format.md`) holds what a person has to
decide: items, their evidence, options, and a recommendation. This script checks
it, embeds the evidence images, the shared palette, the stylesheet, and the
runtime, and writes one HTML file that works offline. The reader's choices are
never part of the content: they live in the browser, in copies the reader saves,
and in exports, and `--choices` carries one of those into a rebuilt document.

Exit codes: 0 written, 1 the content or the choices file has problems and
nothing was written, 2 usage or file error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

# Running the builder must leave the installed plugin as it was: no bytecode beside these modules.
sys.dont_write_bytecode = True

from decisions_choices import Carried, carry_choices, load_choices  # noqa: E402
from decisions_content import Reader  # noqa: E402
from decisions_model import FORMAT, SCHEMA_VERSION, BuildError, fingerprint_model  # noqa: E402
from decisions_page import render_page  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[1]
ASSETS = SKILL_DIR / "assets"
# The palette and fonts are shared with the visual report runtime.
TOKENS = SKILL_DIR.parents[1] / "shared" / "visual" / "assets" / "report-tokens.css"
LARGE_PAGE_BYTES = 40 * 1024 * 1024


def read_asset(path: Path, closing: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise BuildError(f"{path}: cannot read a file this builder ships with: {error}") from error
    if closing in text.lower():
        raise BuildError(f"{path}: must not contain {closing}")
    return "\n" + text.strip("\n") + "\n"


def write_atomically(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.chmod(temp_name, 0o644)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def build(data: Path, output: Path, choices: Optional[Path], base_dir: Path) -> tuple[int, dict[str, Any]]:
    try:
        raw = json.loads(data.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        raise BuildError(f"{data}: cannot read the content file: {error}") from error
    except json.JSONDecodeError as error:
        raise BuildError(f"{data}: is not valid JSON: {error}") from error
    if output.suffix.lower() != ".html":
        raise BuildError(f"{output}: the output must be an .html file")
    if output.is_symlink() or output.is_dir():
        raise BuildError(f"{output}: the output must be a regular file path")

    reader = Reader(base_dir)
    model = reader.read(raw)
    if reader.problems or model is None:
        return 1, {"problems": reader.problems}
    fingerprint_model(model)

    carried = Carried()
    if choices is not None:
        carried, problems = carry_choices(model, load_choices(choices))
        if problems:
            return 1, {"problems": [f"choices: {problem}" for problem in problems]}

    seed = {
        "format": FORMAT,
        "schemaVersion": SCHEMA_VERSION,
        "document": {"id": model.document.id, "fingerprint": model.document.fingerprint},
        "decisions": carried.decisions,
    }
    css = read_asset(TOKENS, "</style") + read_asset(ASSETS / "decisions.css", "</style")
    script = read_asset(ASSETS / "decisions.js", "</script")
    page = render_page(model, seed, css, script)
    write_atomically(output, page)

    size = len(page.encode("utf-8"))
    report: dict[str, Any] = {
        "output": str(output.resolve()),
        "documentId": model.document.id,
        "contentVersion": model.document.fingerprint,
        "items": len(model.items),
        "options": sum(len(item.options) for item in model.items),
        "images": reader.image_count,
        "bytes": size,
    }
    if choices is not None:
        report["choices"] = {
            "carried": carried.unchanged,
            "needsReview": carried.needs_review,
            "dropped": carried.dropped,
        }
    if size > LARGE_PAGE_BYTES:
        report["warning"] = "the page is larger than 40 MB; embed fewer or smaller images"
    return 0, report


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build a self-contained decision document from a content file.")
    parser.add_argument("--data", required=True, type=Path, help="the content file (JSON)")
    parser.add_argument("--output", required=True, type=Path, help="the .html file to write")
    parser.add_argument(
        "--choices", type=Path, help="a choices export (.json) or a saved copy (.html) to carry into this build"
    )
    parser.add_argument(
        "--base-dir", type=Path, default=Path.cwd(), help="where relative evidence image paths start (default: here)"
    )
    args = parser.parse_args(argv)
    try:
        # A quoted "~/..." reaches here unexpanded; without this it becomes a "~" folder in the working directory.
        code, report = build(
            args.data.expanduser(),
            args.output.expanduser(),
            args.choices.expanduser() if args.choices else None,
            args.base_dir.expanduser().resolve(),
        )
    except BuildError as error:
        print(f"build-decisions: {error}", file=sys.stderr)
        return 2
    if code:
        for problem in report["problems"]:
            print(f"build-decisions: {problem}", file=sys.stderr)
        print(
            f"build-decisions: {len(report['problems'])} problem(s); nothing was written. Fix them and rerun.",
            file=sys.stderr,
        )
        return code
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
