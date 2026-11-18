#!/usr/bin/env python3
"""
label_reader.py — what a photographed filament box says beyond the
brand/material/colour guesses in filament_parse.py: the codes worth looking
up (in the order to try them), the finish (Bambuddy's ``effect_type``), a
dual-colour roll's colours, and materials spelled the way Bambuddy spells them.

Ported from NozzleCast's ``FilamentLabelReader.swift`` (which itself started
as a port of this app), so the two read the same box the same way.

Built around real boxes. Panchroma's, for one, print no material at all
("DUAL / MATTE / FOGGY ORANGE (GREY-ORANGE)"), carry an Amazon stock barcode
(Code 128 "X004AR68I3") that no filament database knows, and give the EAN,
when they give one, as text or a QR code beside a "SKU:" line. So barcodes are
tried first and the SKU after.

Copyright (C) 2026 Victor Manuel (hibikipr)
SPDX-License-Identifier: AGPL-3.0-or-later
"""

import re

# ── Materials ────────────────────────────────────────────────────────────────

# Bambuddy's spool form `MATERIALS` (frontend/src/components/spool-form/constants.ts),
# in its order. Bambuddy stores any 1-50 character material, so these are the
# spellings to prefer, not a whitelist.
BAMBUDDY_MATERIALS = ["PLA", "PETG", "ABS", "TPU", "ASA", "PC", "PA", "PVA", "HIPS",
                      "PA-CF", "PETG-CF", "PLA-CF"]

_NYLON = ("NYLON", "PA6", "PA12", "PA66")


def canonical_material(raw: str | None) -> str | None:
    """A material as Bambuddy's list spells it when it's one of them ("petg" →
    "PETG", "Nylon" → "PA", "PA6-CF" → "PA-CF"); anything else trimmed, as is."""
    if raw is None:
        return None
    trimmed = raw.strip()
    if not trimmed:
        return None
    upper = re.sub(r"\s+", "-", trimmed.upper())
    if upper in BAMBUDDY_MATERIALS:
        return upper
    if upper in _NYLON:
        return "PA"
    if any(upper == f"{n}-CF" for n in _NYLON):
        return "PA-CF"
    return trimmed[:50]


# ── Effect (finish) ──────────────────────────────────────────────────────────

# Bambuddy's `FILAMENT_EFFECT_OPTIONS` / `ALLOWED_EFFECT_TYPES`, in the order
# its own form lists them, with the English label.
EFFECT_OPTIONS = [
    ("sparkle", "Sparkle"), ("wood", "Wood"), ("marble", "Marble"), ("glow", "Glow"),
    ("matte", "Matte"), ("silk", "Silk"), ("galaxy", "Galaxy"), ("rainbow", "Rainbow"),
    ("metal", "Metal"), ("translucent", "Translucent"), ("gradient", "Gradient"),
    ("dual-color", "Dual Color"), ("tri-color", "Tri Color"), ("multicolor", "Multicolor"),
]
EFFECT_VALUES = {value for value, _ in EFFECT_OPTIONS}
MULTICOLOR_EFFECTS = ("dual-color", "tri-color", "multicolor")

# Structure first — a dual-colour spool is drawn as a split however it's
# finished, so "Dual Matte" is Dual Color — then finishes, matte last since
# it's the plainest.
_EFFECT_RULES = [
    (("MULTICOLOR", "MULTICOLOUR", "MULTI COLOR", "MULTI COLOUR"), "multicolor"),
    (("TRI COLOR", "TRI COLOUR", "TRICOLOR", "TRICOLOUR", "TRIPLE COLOR"), "tri-color"),
    (("DUAL", "DUO", "BICOLOR", "BI COLOR", "TWO COLOR", "COEXTRUSION"), "dual-color"),
    (("GRADIENT",), "gradient"),
    (("RAINBOW",), "rainbow"),
    (("GLOW", "LUMINOUS", "PHOSPHORESCENT"), "glow"),
    (("GALAXY",), "galaxy"),
    (("SPARKLE", "GLITTER", "STARRY", "SHIMMER"), "sparkle"),
    (("SILK",), "silk"),
    (("WOOD",), "wood"),
    (("MARBLE",), "marble"),
    (("METAL", "METALLIC"), "metal"),
    (("TRANSLUCENT", "TRANSPARENT"), "translucent"),
    (("MATTE", "MATT"), "matte"),
]


def effect(text: str | None) -> str | None:
    """Bambuddy's effect_type for a label or product name, or None."""
    if not text:
        return None
    upper = " " + re.sub(r"[^A-Z0-9]+", " ", text.upper()) + " "
    for words, value in _EFFECT_RULES:
        if any(f" {w} " in upper for w in words):
            return value
    return None


def normalize_effect(value: str | None) -> str | None:
    """Bambuddy's own tolerance ("Dual Color" → "dual-color"); None when it isn't one."""
    if not value:
        return None
    canonical = value.strip().lower().replace("_", "-").replace(" ", "-")
    return canonical if canonical in EFFECT_VALUES else None


# ── Colour ───────────────────────────────────────────────────────────────────

# The same palette filament_parse uses, for the parts of a multi-colour label.
COLOR_HEX = {
    "Black": "000000", "White": "FFFFFF", "Gray": "808080", "Grey": "808080",
    "Silver": "C0C0C0", "Red": "FF0000", "Orange": "FF7F00", "Yellow": "FFFF00",
    "Green": "00A000", "Blue": "0050FF", "Navy": "001F5C", "Cyan": "00FFFF",
    "Teal": "008080", "Purple": "800080", "Violet": "7F00FF", "Pink": "FF69B4",
    "Magenta": "FF00FF", "Brown": "7B3F00", "Beige": "F5F5DC", "Gold": "D4AF37",
    "Bronze": "CD7F32", "Copper": "B87333", "Natural": "EDE6D6", "Clear": "EEEEEE",
    "Olive": "808000", "Lime": "BFFF00", "Maroon": "800000", "Turquoise": "40E0D0",
    "Ivory": "FFFFF0", "Cream": "FFFDD0", "Tan": "D2B48C", "Khaki": "C3B091",
}


def _title_cased(text: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in text.lower().split())


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _color_parts(text: str) -> list[tuple[str, str]] | None:
    """"GREY-ORANGE" → [("Grey", "808080"), ("Orange", "FF7F00")] when every part is a colour word."""
    parts = [p.strip() for p in re.split(r"[-/&+]", text)]
    if not 2 <= len(parts) <= 3:
        return None
    out = []
    for part in parts:
        name = part.capitalize()
        if name not in COLOR_HEX:
            return None
        out.append((name, COLOR_HEX[name]))
    return out


def _has_color_word(text: str) -> bool:
    return any(w.capitalize() in COLOR_HEX for w in re.split(r"[^A-Za-z]+", text) if w)


def label_color(text: str) -> dict:
    """The colour as the label names it and, for a dual/tri-colour roll, its parts.

    Returns ``{"name": str | None, "explicit": bool, "part_hexes": [RRGGBB, ...]}``.
    ``explicit`` means the label names the colour in a field of its own
    ("COLOR: Blue"), not just somewhere in the product name.

    A pair or triple in brackets — "(GREY-ORANGE)", "(Black/Gold)" — names the
    parts, and the line before it, when it holds a colour word, is the colour's
    own name ("FOGGY ORANGE"). Without one, a plain "Black-Gold" pair is both.
    """
    lines = _lines(text)
    for line in lines:
        m = re.match(r"^(?:COLOU?R(?:\s+NAME)?)\s*[:：]\s*(.+)$", line, re.IGNORECASE)
        if m:
            value = m.group(1).strip()
            if value and len(value) <= 40:
                return {"name": _title_cased(value), "explicit": True, "part_hexes": []}
    for i, line in enumerate(lines):
        if not line.startswith(("(", "[")):
            continue
        parts = _color_parts(line.strip("()[] "))
        if parts and len(parts) >= 2:
            previous = lines[i - 1] if i > 0 else ""
            name = _title_cased(previous) if _has_color_word(previous) else "-".join(n for n, _ in parts)
            return {"name": name, "explicit": False, "part_hexes": [h for _, h in parts]}
    for line in lines:
        parts = _color_parts(line)
        if parts and len(parts) >= 2:
            return {"name": "-".join(n for n, _ in parts), "explicit": False, "part_hexes": [h for _, h in parts]}
    return {"name": None, "explicit": False, "part_hexes": []}


def split_product_and_color(name: str | None, color: str | None, material: str | None) -> tuple[str, str | None] | None:
    """Split a database name that's product line + colour at the colour the label names.

    ("PolyLite™ PLA Pro Blue", "Blue", "PLA") → ("Blue", "PolyLite Pro"). None when
    the name doesn't end with that colour or is nothing but it.
    """
    color = (color or "").strip()
    name = name or ""
    if not color or len(name) <= len(color) or not name.lower().endswith(color.lower()):
        return None
    product = name[: -len(color)]
    for mark in ("™", "®", "©"):
        product = product.replace(mark, "")
    if material:
        product = re.sub(rf"\b{re.escape(material)}\b", "", product, flags=re.IGNORECASE)
    product = re.sub(r"\s+", " ", product).strip(" \t\n-")
    return color, (product or None)


# ── Codes ────────────────────────────────────────────────────────────────────

_AMAZON_FNSKU = re.compile(r"^X0[0-9A-Z]{8}$", re.IGNORECASE)


def is_amazon_stock_code(code: str | None) -> bool:
    """Amazon's FNSKU: "X0" and eight letters or digits. In no filament database."""
    return bool(_AMAZON_FNSKU.match((code or "").strip()))


def extract_barcode(text: str) -> str | None:
    """Pull a printed barcode (UPC/EAN/GTIN) out of free text, e.g. label OCR.

    Prefers a labelled number ("EAN: 6938936716785"); falls back to any bare
    12–14 digit run. Returns digits only, or None.
    """
    # The separator between the label and the digits is wrapped in an atomic
    # group: without it, its optional \s* overlaps with the [\d\s] class right
    # after it, and a long run of spaces with no trailing digit makes the
    # regex engine try every possible split between the two — O(n^2) blowup.
    m = re.search(r"(?:EAN|UPC|GTIN|BARCODE)(?>\s*[:#]?\s*)(\d[\d \t]{6,16}\d)", text or "", re.IGNORECASE)
    cand = re.sub(r"\D", "", m.group(1)) if m else None
    if not cand:
        m = re.search(r"(?<!\d)(\d{12,14})(?!\d)", text or "")
        cand = m.group(1) if m else None
    return cand if cand and 8 <= len(cand) <= 14 else None


def _is_sku_shaped(token: str) -> bool:
    """Letters and digits together, 5–16 characters, at least three digits:
    "CA02029", "GFA00-B08". Not a weight, diameter or temperature."""
    if not 5 <= len(token) <= 16:
        return False
    if not re.fullmatch(r"[A-Za-z0-9-]+", token):
        return False
    if sum(c.isdigit() for c in token) < 3 or not any(c.isalpha() for c in token):
        return False
    return not re.fullmatch(r"\d+(?:MM|G|KG|C|F)", token, re.IGNORECASE)


_SKU_LABEL = re.compile(
    r"^(?:SKU|ARTICLE(?:\s*(?:NO|NUMBER))?|ART\.?\s*NO|ITEM(?:\s*(?:NO|NUMBER))?|MPN|MODEL)\b\.?\s*[:#]?\s*",
    re.IGNORECASE,
)


def labelled_skus(text: str) -> list[str]:
    """Values after "SKU", "Article", "Art. No." or "Item", on the same line or
    the next (label layouts put the value under the heading)."""
    lines = [ln.strip() for ln in (text or "").splitlines()]
    out = []
    for i, line in enumerate(lines):
        m = _SKU_LABEL.match(line)
        if not m:
            continue
        rest = line[m.end():].strip()
        value = lines[i + 1] if not rest and i + 1 < len(lines) else rest
        token = value.split(" ")[0] if value else ""
        if token and _is_sku_shaped(token):
            out.append(token.upper())
    return out


def sku_shaped_tokens(text: str) -> list[str]:
    tokens = re.split(r"[\s,;()]+", text or "")
    return [t.strip(".:").upper() for t in tokens if _is_sku_shaped(t.strip(".:"))]


def code_candidates(text: str, barcodes: list[str] | None = None, classify=None) -> list[str]:
    """Codes to look up, best first.

    Decoded barcodes that are GTINs, the EAN/UPC printed on the label, any
    other decoded barcode, the SKU printed after a "SKU" heading, then any
    other SKU-shaped token. Amazon FNSKU stickers are dropped. ``classify``
    is app._classify_code (injected to avoid a circular import).
    """
    out: list[str] = []

    def add(code: str):
        code = (code or "").strip()
        if code and not any(o.upper() == code.upper() for o in out):
            out.append(code)

    decoded = [b.strip() for b in (barcodes or []) if isinstance(b, str) and b.strip()]
    decoded = [b for b in decoded if not is_amazon_stock_code(b)]
    if classify:
        for code in decoded:
            if classify(code)[1] == "gtin":
                add(code)
    printed = extract_barcode(text)
    if printed:
        add(printed)
    for code in decoded:
        add(code)
    for sku in labelled_skus(text):
        add(sku)
    for token in sku_shaped_tokens(text):
        if not is_amazon_stock_code(token):
            add(token)
    return out
