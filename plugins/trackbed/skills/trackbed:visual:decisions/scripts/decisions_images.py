"""Read an evidence image and embed it in the page.

An image is recognized by its leading bytes, never by its file name, and reaches the page only as a
`data:` URL inside an `<img>`, where it cannot run script or load anything else.
"""

from __future__ import annotations

import base64
import re
import struct
from pathlib import Path
from typing import Optional

MAX_IMAGE_BYTES = 10 * 1024 * 1024
SVG_VIEWBOX_RE = re.compile(
    r"""<svg\b[^>]*\bviewBox\s*=\s*["']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+(\d+(?:\.\d+)?)[\s,]+(\d+(?:\.\d+)?)"""
)
# An evidence SVG is only ever shown through <img>, where it cannot run script or load
# anything. These are refused anyway, so a file saved out of the page stays inert too.
SVG_ACTIVE_RE = re.compile(
    r"<\s*(?:script|foreignObject|iframe|embed|object)\b|\son[a-z]+\s*=|"
    r"""(?:href|src)\s*=\s*["']\s*(?:https?:|//|javascript:|data:text/html)""",
    re.I,
)


class ImageProblem(Exception):
    """Why a file cannot be used as evidence. `missing` marks a file that could not be read at all."""

    def __init__(self, message: str, *, missing: bool = False) -> None:
        super().__init__(message)
        self.missing = missing


def embed_image(path: Path) -> tuple[str, int, int]:
    """The image as a data URL, with its pixel size when the header gives one (0 otherwise)."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ImageProblem(f"cannot be read ({error.strerror or error})", missing=True) from error
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageProblem(f"is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB")
    sniffed = sniff_image(data)
    if sniffed is None:
        raise ImageProblem("is not a PNG, JPEG, GIF, WebP, AVIF, or SVG image")
    mime, width, height = sniffed
    if mime == "image/svg+xml" and SVG_ACTIVE_RE.search(data.decode("utf-8", "replace")):
        raise ImageProblem("is an SVG with script, event handlers, embedded HTML, or remote references")
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}", width, height


def sniff_image(data: bytes) -> Optional[tuple[str, int, int]]:
    """The image type by its leading bytes, with its pixel size when the header gives one cheaply."""
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return "image/png", int(width), int(height)
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        width, height = struct.unpack("<HH", data[6:10])
        return "image/gif", int(width), int(height)
    if data.startswith(b"\xff\xd8\xff"):
        width, height = jpeg_size(data)
        return "image/jpeg", width, height
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", 0, 0
    if data[4:8] == b"ftyp" and data[8:12] in (b"avif", b"avis"):
        return "image/avif", 0, 0
    head = data[:2048].decode("utf-8", "replace").lstrip("\ufeff").lstrip()
    if head.startswith("<svg") or (head.startswith("<?xml") and "<svg" in head):
        box = SVG_VIEWBOX_RE.search(head)
        if box:
            return "image/svg+xml", round(float(box.group(1))), round(float(box.group(2)))
        return "image/svg+xml", 0, 0
    return None


def jpeg_size(data: bytes) -> tuple[int, int]:
    position = 2
    while position + 9 < len(data):
        if data[position] != 0xFF:
            break
        marker = data[position + 1]
        length = int(struct.unpack(">H", data[position + 2 : position + 4])[0])
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[position + 5 : position + 9])
            return int(width), int(height)
        position += 2 + length
    return 0, 0
