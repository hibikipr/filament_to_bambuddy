#!/usr/bin/env python3
"""
ofd.py — Open Filament Database barcode lookup.

The OFD (https://openfilamentdatabase.org) publishes a complete data dump with
~2,500 real spool barcodes (GTINs) joined to brand / material / colour / weight.
We download it once, build a barcode → fields index, and refresh daily.

Copyright (C) 2026 Victor Manuel (hibikipr)
SPDX-License-Identifier: AGPL-3.0-or-later
"""

import json
import re
import time
from pathlib import Path

import requests

OFD_ALL_URL = "https://api.openfilamentdatabase.org/json/all.json"
OFD_CACHE = Path("ofd_index.json")
OFD_TTL_SECONDS = 24 * 3600

# In-process cache so we don't rebuild on every request.
_INDEX: dict | None = None
_INDEX_LOADED_AT = 0.0


def _canon(barcode: str) -> str:
    """Canonical GTIN form for matching: digits only, leading zeros stripped.

    Makes a UPC-A (12-digit) and its EAN-13 (leading-zero) form compare equal.
    """
    digits = re.sub(r"\D", "", barcode or "")
    return digits.lstrip("0") or "0"


def _hex_to_rgba(color_hex) -> str | None:
    if isinstance(color_hex, list):
        color_hex = color_hex[0] if color_hex else None
    if not isinstance(color_hex, str):
        return None
    h = color_hex.lstrip("#")
    if len(h) == 6 and re.fullmatch(r"[0-9A-Fa-f]{6}", h):
        return h.upper() + "FF"   # RRGGBBAA, opaque
    return None


def _subtype_from(filament_name: str, material: str) -> str | None:
    """Best-effort subtype: the filament name minus the material word."""
    if not filament_name:
        return None
    s = filament_name
    if material:
        s = re.sub(rf"\b{re.escape(material)}\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip(" -+")
    return s or None


def _build_index(all_json: dict) -> dict:
    """Build {canonical_gtin: fields} from the OFD all.json dump."""
    brands = {b["id"]: b for b in all_json.get("brands", []) if "id" in b}
    filaments = {f["id"]: f for f in all_json.get("filaments", []) if "id" in f}
    variants = {v["id"]: v for v in all_json.get("variants", []) if "id" in v}

    index: dict = {}
    for size in all_json.get("sizes", []):
        gtin = size.get("gtin")
        if not gtin:
            continue
        variant = variants.get(size.get("variant_id"))
        if not variant:
            continue
        fil = filaments.get(variant.get("filament_id"))
        if not fil:
            continue
        brand = brands.get(fil.get("brand_id"))
        material = fil.get("material") or ""

        fields: dict = {"material": material} if material else {}
        if brand and brand.get("name"):
            fields["brand"] = brand["name"]
        sub = _subtype_from(fil.get("name", ""), material)
        if sub:
            fields["subtype"] = sub
        if variant.get("name"):
            fields["color_name"] = variant["name"]
        rgba = _hex_to_rgba(variant.get("color_hex"))
        if rgba:
            fields["rgba"] = rgba
        if size.get("filament_weight"):
            try:
                fields["label_weight"] = int(round(float(size["filament_weight"])))
            except (TypeError, ValueError):
                pass
        for src, dst in (("min_print_temperature", "nozzle_temp_min"),
                         ("max_print_temperature", "nozzle_temp_max")):
            if fil.get(src) is not None:
                try:
                    fields[dst] = int(fil[src])
                except (TypeError, ValueError):
                    pass

        # A descriptive title for the UI.
        title_bits = [fields.get("brand"), fil.get("name"), fields.get("color_name")]
        fields["_title"] = " ".join(b for b in title_bits if b)

        index[_canon(gtin)] = fields
    return index


def _load_cached_index() -> dict | None:
    if not OFD_CACHE.exists():
        return None
    try:
        data = json.loads(OFD_CACHE.read_text())
        if time.time() - data.get("built_at", 0) > OFD_TTL_SECONDS:
            return None
        return data.get("index")
    except Exception:
        return None


def _refresh_index() -> dict:
    """Download all.json and rebuild the index, caching it to disk."""
    resp = requests.get(OFD_ALL_URL, timeout=60)
    resp.raise_for_status()
    index = _build_index(resp.json())
    try:
        OFD_CACHE.write_text(json.dumps({"built_at": time.time(), "index": index}))
    except Exception:
        pass
    return index


def get_index(force: bool = False) -> dict:
    """Return the barcode→fields index (memory → disk cache → download)."""
    global _INDEX, _INDEX_LOADED_AT
    if _INDEX is not None and not force and (time.time() - _INDEX_LOADED_AT) < OFD_TTL_SECONDS:
        return _INDEX
    idx = None if force else _load_cached_index()
    if idx is None:
        idx = _refresh_index()
    _INDEX = idx
    _INDEX_LOADED_AT = time.time()
    return _INDEX


def lookup(barcode: str) -> dict | None:
    """Return filament fields for a barcode from the OFD, or None if not found."""
    try:
        idx = get_index()
    except Exception:
        return None
    return idx.get(_canon(barcode))


if __name__ == "__main__":
    idx = get_index(force=True)
    print(f"OFD index: {len(idx)} barcodes")
    # show a couple of examples
    for k, v in list(idx.items())[:3]:
        print(k, "→", {kk: vv for kk, vv in v.items() if kk != "_title"})
