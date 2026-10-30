#!/usr/bin/env python3
"""
generate_icons.py — generator for the web app's PWA icon set.

A filament spool inside scanner brackets with a scan line, on a dark rounded
tile in Bambu green: "scan the box, add the spool". Shares its tile and palette
with bambuddy_to_manyfold's icon so the two helpers read as a family.

Writes the SVG masters (icon.svg, maskable.svg, apple-touch-icon.svg) to
static/icons/ and renders the PNGs from them with headless Chrome (set CHROME
to point at another Chrome/Chromium binary).

    python3 scripts/generate_icons.py

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import os
import subprocess
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "static" / "icons"
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

TILE = "#1a1a1a"   # app theme background
EDGE = "#3d3d3d"   # Bambuddy border colour
INK = "#f5f5f5"
ACCENT, ACCENT_LIGHT, ACCENT_DARK = "#00AE42", "#00C64D", "#009438"  # Bambu green

GLYPH = (
    f'<circle cx="50" cy="50" r="29" fill="#2d2d2d" stroke="{EDGE}" stroke-width="1.5"/>'
    f'<circle cx="50" cy="50" r="24" fill="{ACCENT}"/>'
    f'<circle cx="50" cy="50" r="20.5" fill="none" stroke="{ACCENT_DARK}" stroke-width="1.2"/>'
    f'<circle cx="50" cy="50" r="17" fill="none" stroke="{ACCENT_DARK}" stroke-width="1.2"/>'
    f'<circle cx="50" cy="50" r="11" fill="{TILE}" stroke="{EDGE}" stroke-width="2"/>'
    f'<circle cx="50" cy="50" r="4" fill="#2d2d2d"/>'
    # scanner brackets
    f'<path d="M14 30 V20 Q14 14 20 14 H30 M70 14 H80 Q86 14 86 20 V30 M86 70 V80 Q86 86 80 86 H70 '
    f'M30 86 H20 Q14 86 14 80 V70" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>'
    # scan line with a soft glow
    f'<line x1="9" y1="50" x2="91" y2="50" stroke="{ACCENT_LIGHT}" stroke-width="5" stroke-linecap="round" opacity="0.35"/>'
    f'<line x1="9" y1="50" x2="91" y2="50" stroke="{INK}" stroke-width="2.4" stroke-linecap="round"/>'
)


def _variant(kind: str) -> str:
    """Wrap GLYPH (drawn on a 100x100 grid) for one icon variant."""
    if kind == "any":
        # Rounded dark tile, transparent outside it.
        bg = (f'<rect width="100" height="100" rx="22" fill="{TILE}"/>'
              f'<rect x="0.5" y="0.5" width="99" height="99" rx="21.5" fill="none" stroke="{EDGE}"/>')
        glyph = GLYPH
    elif kind == "maskable":
        # Full-bleed background; glyph shrunk into the ~80% maskable safe zone.
        bg = f'<rect width="100" height="100" fill="{TILE}"/>'
        glyph = f'<g transform="translate(50 50) scale(0.75) translate(-50 -50)">{GLYPH}</g>'
    else:  # apple: full-bleed square, iOS rounds the corners itself
        bg = f'<rect width="100" height="100" fill="{TILE}"/>'
        glyph = GLYPH
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
            f"{bg}{glyph}</svg>\n")


def _render(svg: Path, png: Path, size: int):
    html = svg.with_suffix(".render.html")
    html.write_text(f'<html><body style="margin:0;background:transparent">'
                    f'<img src="{svg.name}" style="display:block;width:{size}px;height:{size}px"></body></html>')
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--default-background-color=00000000", f"--window-size={size},{size}",
                        f"--screenshot={png}", html.as_uri()],
                       check=True, capture_output=True)
    finally:
        html.unlink()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sources = {
        "any": OUT_DIR / "icon.svg",
        "maskable": OUT_DIR / "maskable.svg",
        "apple": OUT_DIR / "apple-touch-icon.svg",
    }
    for kind, path in sources.items():
        path.write_text(_variant(kind))

    _render(sources["any"], OUT_DIR / "icon-192.png", 192)
    _render(sources["any"], OUT_DIR / "icon-512.png", 512)
    _render(sources["maskable"], OUT_DIR / "maskable-512.png", 512)
    _render(sources["apple"], OUT_DIR / "apple-touch-icon.png", 180)

    print(f"Wrote icons to {OUT_DIR}")


if __name__ == "__main__":
    main()
