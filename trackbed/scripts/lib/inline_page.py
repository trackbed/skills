"""Shared output helpers for self-contained HTML pages."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Mapping
from pathlib import Path


def read_inline_asset(path: Path, closing: str) -> str:
    """Read a shipped asset and reject text that could close its HTML element."""
    text = path.read_text(encoding="utf-8")
    if closing in text.lower():
        raise ValueError(f"{path}: must not contain {closing}")
    return text


def json_script(value: object, *, compact: bool = True) -> str:
    """Encode the text of an application/json script element."""
    separators = (",", ":") if compact else None
    return json.dumps(value, ensure_ascii=False, separators=separators).replace("<", "\\u003c")


def csp_meta(*scripts: str, image_sources: str = "data:", media_sources: str = "", marker: str = "") -> str:
    """Pin each executable script using its exact text, including whitespace."""
    hashes = " ".join(
        f"'sha256-{base64.b64encode(hashlib.sha256(script.encode('utf-8')).digest()).decode('ascii')}'"
        for script in scripts
    )
    media = f"media-src {media_sources}; " if media_sources else ""
    policy = (
        f"default-src 'none'; script-src {hashes}; style-src 'unsafe-inline'; "
        f"img-src {image_sources}; {media}base-uri 'none'; form-action 'none'"
    )
    attribute = f" {marker}" if marker else ""
    return f'<meta http-equiv="Content-Security-Policy"{attribute} content="{policy}">'


def fill_template(template: str, slots: Mapping[str, str]) -> str:
    """Replace slots in the original template without scanning inserted text."""
    if not slots:
        return template
    pattern = "|".join(re.escape(slot) for slot in slots)
    return re.sub(pattern, lambda match: slots[match[0]], template)


def write_page(path: Path, text: str, *, mode: int | None = None) -> None:
    """Publish a complete page with an atomic replacement in its directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = path.lstat()
    except FileNotFoundError:
        existing = None
    if existing is not None and not stat.S_ISREG(existing.st_mode):
        raise ValueError(f"{path}: the output must be a regular file path")
    if mode is None:
        mode = 0o600 if existing is None else stat.S_IMODE(existing.st_mode)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.chmod(temp_name, mode)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
