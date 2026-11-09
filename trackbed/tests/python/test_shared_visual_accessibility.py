"""Contrast and diagram-naming checks for the shared visual palettes and examples."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

VISUAL = Path(__file__).resolve().parents[2] / "shared" / "visual"
PALETTE_FILES = [
    VISUAL / "assets" / "architecture.html",
    VISUAL / "assets" / "data-table.html",
    VISUAL / "assets" / "mermaid-flowchart.html",
    VISUAL / "references" / "css-patterns.md",
]
SURFACES = ("bg", "surface", "surface2", "surface-elevated")
TEXT_TOKENS = ("text", "text-dim")
# The status chip and before/after panel patterns in css-patterns.md read these.
STATUS_TOKENS = ("green", "red", "orange")
MIN_CONTRAST = 4.5

ROOT_BLOCK = re.compile(r":root\s*\{[^}]*\}")
HEX_TOKEN = re.compile(r"--([a-z0-9-]+):\s*#([0-9a-fA-F]{6})\s*;")
DIM_TOKEN = re.compile(r"--([a-z0-9-]+)-dim:\s*rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)")


Color = tuple[int, int, int]


def rgb(hex_value: str) -> Color:
    return (int(hex_value[0:2], 16), int(hex_value[2:4], 16), int(hex_value[4:6], 16))


def luminance(color: Color) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: Color, b: Color) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def blend(fg: Color, alpha: float, bg: Color) -> Color:
    r, g, b = (round(fg[i] * alpha + bg[i] * (1 - alpha)) for i in range(3))
    return (r, g, b)


def palette_failures(text: str, label: str) -> list[str]:
    """Return every text color below the floor on a surface or tint it can sit on.

    A color token is checked against each opaque surface and against its own
    `-dim` tint layered over each surface, which is how chips and panel headers
    use it. Body and dim text are checked against every tint. Each scheme must
    define the text and status tokens as 6-digit hex, and each status tint as
    rgba, so none escapes the check.
    """
    failures = []
    for index, block in enumerate(ROOT_BLOCK.findall(text)):
        tokens = {name: rgb(value) for name, value in HEX_TOKEN.findall(block)}
        tints = {name: ((int(r), int(g), int(b)), float(a)) for name, r, g, b, a in DIM_TOKEN.findall(block)}
        surfaces = {name: tokens[name] for name in SURFACES if name in tokens}
        if not surfaces:
            failures.append(f"{label} scheme {index}: no surface tokens found")
            continue
        for required in TEXT_TOKENS + STATUS_TOKENS:
            if required not in tokens:
                failures.append(f"{label} scheme {index}: --{required} missing or not 6-digit hex")
        for required in STATUS_TOKENS:
            if required not in tints:
                failures.append(f"{label} scheme {index}: --{required}-dim missing or not rgba")
        for name, color in tokens.items():
            if name in SURFACES:
                continue
            backgrounds = dict(surfaces)
            if name in TEXT_TOKENS:
                tint_names = list(tints)
            elif name in tints:
                tint_names = [name]
            else:
                tint_names = []
            for tint in tint_names:
                tint_rgb, alpha = tints[tint]
                for surface, surface_rgb in surfaces.items():
                    backgrounds[f"{tint}-dim over {surface}"] = blend(tint_rgb, alpha, surface_rgb)
            for background, background_rgb in backgrounds.items():
                ratio = contrast(color, background_rgb)
                if ratio < MIN_CONTRAST:
                    failures.append(f"{label} scheme {index}: --{name} on {background} is {ratio:.2f}:1")
    return failures


class PaletteContrastTests(unittest.TestCase):
    def test_every_shared_palette_has_both_schemes(self) -> None:
        for path in PALETTE_FILES:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertEqual(len(ROOT_BLOCK.findall(text)), 2)
                self.assertIn("prefers-color-scheme: dark", text)

    def test_shared_palette_text_meets_the_contrast_floor(self) -> None:
        failures = []
        for path in PALETTE_FILES:
            failures += palette_failures(path.read_text(encoding="utf-8"), path.name)
        self.assertEqual(failures, [])

    def test_checker_catches_low_contrast_dim_text_and_chips(self) -> None:
        sample = """
        :root { --bg: #ffffff; --surface: #ffffff; --text: #111111; --text-dim: #8a7e72;
                --green: #4d7c0f; --green-dim: rgba(77, 124, 15, 0.5); }
        """
        failures = palette_failures(sample, "sample")
        self.assertIn("sample scheme 0: --text-dim on bg is 3.96:1", failures)
        self.assertTrue(any(f.startswith("sample scheme 0: --green on green-dim over") for f in failures))
        self.assertFalse(any("--text on" in f for f in failures))
        self.assertIn("sample scheme 0: --red missing or not 6-digit hex", failures)
        self.assertIn("sample scheme 0: --red-dim missing or not rgba", failures)


class DiagramNameTests(unittest.TestCase):
    TAG = re.compile(r"<(pre|canvas|svg)\b([^>]*)>", re.S)
    INLINE_CODE = re.compile(r"`[^`\n]+`")

    def test_every_shared_diagram_example_has_an_accessible_name(self) -> None:
        missing = []
        found = 0
        for path in sorted(VISUAL.rglob("*")):
            if path.suffix not in {".md", ".html"}:
                continue
            for match in self.TAG.finditer(self.INLINE_CODE.sub("", path.read_text(encoding="utf-8"))):
                tag, attrs = match.group(1), match.group(2)
                if tag == "pre" and 'class="mermaid"' not in attrs:
                    continue
                found += 1
                named = 'role="img"' in attrs and re.search(r'aria-label="[^"]+"', attrs)
                decorative = tag == "svg" and 'aria-hidden="true"' in attrs
                if not (named or decorative):
                    missing.append(f"{path.relative_to(VISUAL)}: <{tag}{attrs[:60]}")
        self.assertGreater(found, 0)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
