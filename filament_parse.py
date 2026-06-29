#!/usr/bin/env python3
"""
filament_parse.py
Heuristics that turn a UPC product title (e.g. "SUNLU PLA+ 1.75mm Black 1KG")
into best-effort filament fields for Bambuddy's inventory.

Everything here is a guess from free text — the UI always lets the user correct
it, and corrections are remembered per-barcode by the app's cache.

Copyright (C) 2026 Victor Manuel (hibikipr)
SPDX-License-Identifier: AGPL-3.0-or-later
"""

import re

# Common filament brands (longest first so multi-word names win).
KNOWN_BRANDS = [
    "Bambu Lab", "Polymaker", "Prusament", "Prusa", "Fillamentum", "MatterHackers",
    "Protopasta", "ColorFabb", "Overture", "Hatchbox", "Inland", "Creality",
    "Elegoo", "Anycubic", "Geeetech", "Eryone", "Amolen", "Duramic", "Sunlu",
    "eSUN", "Jayo", "Atomic", "Spectrum", "3DJake", "Comgrow", "Tinmorry",
    "Kingroon", "Flashforge", "Ziro", "Novamaker", "GST3D", "Iemai",
]

# Base materials → canonical Bambuddy `material`. Order matters: the most
# specific / longest token must be tried first (PETG before PET, PLA+ before PLA).
BASE_MATERIALS = [
    ("PCTG", "PCTG"), ("PETG", "PETG"), ("PET-G", "PETG"), ("PET G", "PETG"),
    ("PLA+", "PLA"), ("PLA PLUS", "PLA"), ("PLA", "PLA"),
    ("ABS+", "ABS"), ("ABS", "ABS"), ("ASA", "ASA"),
    ("TPU", "TPU"), ("TPE", "TPE"),
    ("NYLON", "Nylon"), ("PA12", "Nylon"), ("PA6", "Nylon"), ("PA", "Nylon"),
    ("HIPS", "HIPS"), ("PVA", "PVA"), ("PC", "PC"),
]

# Subtype / finish modifiers (canonical casing on the right).
SUBTYPE_HINTS = [
    ("CARBON FIBER", "Carbon Fiber"), ("CARBON FIBRE", "Carbon Fiber"),
    ("CARBON", "Carbon Fiber"), ("GLOW IN THE DARK", "Glow"), ("GLOW", "Glow"),
    ("SILK", "Silk"), ("MATTE", "Matte"), ("MARBLE", "Marble"), ("WOOD", "Wood"),
    ("METAL", "Metal"), ("RAINBOW", "Rainbow"), ("GRADIENT", "Gradient"),
    ("DUAL COLOR", "Dual Color"), ("TRI COLOR", "Tri Color"),
    ("HIGH SPEED", "High Speed"), ("HYPER", "High Speed"), ("TOUGH", "Tough"),
    ("GALAXY", "Galaxy"), ("SPARKLE", "Sparkle"), ("GLITTER", "Glitter"),
    ("LUMINOUS", "Luminous"), ("FLUORESCENT", "Fluorescent"),
    ("TRANSLUCENT", "Translucent"), ("TRANSPARENT", "Transparent"),
    ("PLUS", "Plus"),
]

# Colour name → RRGGBB (opaque; the UI lets the user tweak).
COLOR_HEX = {
    "Black": "000000", "White": "FFFFFF", "Gray": "808080", "Grey": "808080",
    "Silver": "C0C0C0", "Red": "FF0000", "Orange": "FF7F00", "Yellow": "FFFF00",
    "Green": "00A000", "Blue": "0050FF", "Navy": "001F5C", "Cyan": "00FFFF",
    "Teal": "008080", "Purple": "800080", "Violet": "7F00FF", "Pink": "FF69B4",
    "Magenta": "FF00FF", "Brown": "7B3F00", "Beige": "F5F5DC", "Gold": "D4AF37",
    "Bronze": "CD7F32", "Copper": "B87333", "Natural": "EDE6D6", "Clear": "EEEEEE",
    "Transparent": "EEEEEE", "Skin": "FFCDA0", "Olive": "808000", "Lime": "BFFF00",
    "Maroon": "800000", "Turquoise": "40E0D0", "Ivory": "FFFFF0", "Cream": "FFFDD0",
    "Tan": "D2B48C", "Khaki": "C3B091",
}
# Match longer colour names first (e.g. "Navy" before "Blue" isn't needed, but
# multi-word handling is future-proofed by sorting on length).
_COLOR_WORDS = sorted(COLOR_HEX.keys(), key=len, reverse=True)


def _find_brand(text_upper: str, extra_brands=None) -> str | None:
    """Find a brand in the text. Tries the built-in list plus any extra brands
    (e.g. the ~140 from the Open Filament Database), longest name first so a
    specific brand wins. Substring match (not word-boundary) so it still catches
    OCR text where words run together (e.g. 'OfPanchroma')."""
    brands = list(KNOWN_BRANDS) + list(extra_brands or [])
    seen, uniq = set(), []
    for b in brands:
        b = (b or "").strip()
        if b and b.upper() not in seen:
            seen.add(b.upper())
            uniq.append(b)
    uniq.sort(key=len, reverse=True)
    # Prefer specific (>=4 char) matches; fall back to shorter exact ones.
    for b in uniq:
        if len(b) >= 4 and b.upper() in text_upper:
            return b
    for b in uniq:
        if b.upper() in text_upper:
            return b
    return None


def _find_material(text_upper: str) -> tuple[str | None, str | None]:
    """Return (material, subtype_from_plus). Detects PLA+ → material PLA, subtype Plus.

    Uses letter boundaries so short tokens (PA, PC, PET…) don't false-match inside
    brand names — e.g. 'PA' must not fire on 'PAnchroma'.
    """
    for token, canonical in BASE_MATERIALS:
        if re.search(r"(?<![A-Z])" + re.escape(token) + r"(?![A-Z])", text_upper):
            sub = "Plus" if token.endswith("+") or token.endswith("PLUS") else None
            return canonical, sub
    return None, None


def _find_subtypes(text_upper: str) -> list[str]:
    found = []
    for token, canonical in SUBTYPE_HINTS:
        if token in text_upper and canonical not in found:
            found.append(canonical)
    return found


def _find_color(text: str) -> tuple[str | None, str | None]:
    for word in _COLOR_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE):
            return word, COLOR_HEX[word] + "FF"   # RRGGBBAA, opaque
    return None, None


def _find_diameter(text: str) -> float | None:
    m = re.search(r"\b(1\.75|2\.85|3\.00|3\.0|3)\s*mm\b", text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"\b(1\.75|2\.85)\b", text)
    return float(m.group(1)) if m else None


def _find_nozzle_temps(text: str) -> tuple[int, int] | None:
    """Pull the nozzle/printing temperature (°C) out of label text.

    Distinguishes nozzle from bed by VALUE, not by adjacent label — OCR often
    scrambles multi-column spec blocks (so "Printing Temp" can sit next to the
    bed value). Nozzle/hotend temps are >=140°C; bed temps are well below that.
    Returns (min, max), or None.
    """
    # All "NN-NN°C" ranges; pick the one in the nozzle band.
    for lo, hi in re.findall(r"(\d{2,3})\s*[-–~]\s*(\d{2,3})\s*°?\s*[cC]\b", text):
        lo, hi = int(lo), int(hi)
        if 140 <= lo and hi <= 360 and lo <= hi:
            return lo, hi
    # Single value fallback (e.g. "Nozzle 210°C").
    for m in re.finditer(r"(\d{2,3})\s*°?\s*[cC]\b", text):
        t = int(m.group(1))
        if 140 <= t <= 360:
            return t, t
    return None


def _find_hex(text: str) -> str | None:
    """First #RRGGBB in the text → RRGGBBAA (opaque). Labels often print it."""
    m = re.search(r"#([0-9A-Fa-f]{6})\b", text)
    return m.group(1).upper() + "FF" if m else None


def _find_weight_grams(text: str) -> int | None:
    """Net filament weight in grams from tokens like '1KG', '1000g', '0.5kg', '500 g'."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|kgs|kilograms?)\b", text, re.IGNORECASE)
    if m:
        return int(round(float(m.group(1)) * 1000))
    m = re.search(r"(\d{3,5})\s*(g|grams?)\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def parse_title(title: str, brand_hint: str | None = None, extra_brands=None) -> dict:
    """Best-effort parse of a product title into Bambuddy spool fields.

    ``extra_brands`` augments the built-in brand list (e.g. the Open Filament
    Database's brands). Returns a dict with any of: brand, material, subtype,
    color_name, rgba, diameter_mm, label_weight. Missing fields are absent.
    """
    if not title:
        return {}
    text = title.strip()
    upper = text.upper()
    out: dict = {}

    brand = brand_hint or _find_brand(upper, extra_brands)
    if brand:
        out["brand"] = brand

    material, plus_sub = _find_material(upper)
    if material:
        out["material"] = material

    subtypes = _find_subtypes(upper)
    if plus_sub and plus_sub not in subtypes:
        subtypes.insert(0, plus_sub)
    if subtypes:
        out["subtype"] = " ".join(subtypes)

    color_name, rgba = _find_color(text)
    if color_name:
        out["color_name"] = color_name
        out["rgba"] = rgba
    # An explicit hex on the label is authoritative for the colour swatch.
    hex_rgba = _find_hex(text)
    if hex_rgba:
        out["rgba"] = hex_rgba

    temps = _find_nozzle_temps(text)
    if temps:
        out["nozzle_temp_min"], out["nozzle_temp_max"] = temps

    diameter = _find_diameter(text)
    if diameter:
        out["diameter_mm"] = diameter

    weight = _find_weight_grams(text)
    if weight:
        out["label_weight"] = weight

    return out


if __name__ == "__main__":
    # Quick manual check.
    for t in [
        "SUNLU PLA+ Filament 1.75mm Black 1KG",
        "Overture PETG 1.75 mm Matte Gray 1kg Spool",
        "eSUN ABS+ 3D Printer Filament 1.75mm Red 1000g",
        "Polymaker PolyTerra PLA Carbon Fiber 1.75mm 500g",
    ]:
        print(t, "→", parse_title(t))
