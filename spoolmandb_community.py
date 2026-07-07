#!/usr/bin/env python3
"""
spoolmandb_community.py — SpoolmanDB-Community filament database lookup.

SpoolmanDB-Community (https://github.com/Icezaza2543/SpoolmanDB-Community, a
community-maintained continuation of Donkie/SpoolmanDB) publishes a much
broader brand/material/colour catalog than the Open Filament Database (OFD),
and a subset of its entries also carry EAN/GTIN retail barcodes and/or
manufacturer SKUs (``codes``). Real barcode coverage is far sparser than
OFD's (which is purpose-built for barcode lookups), so this is consulted as
a fallback *after* OFD in app.py, not instead of it.

The compiled `filaments.json` this project publishes on GitHub Pages does
NOT carry `color_name` as its own field (it's baked into the `name` string at
compile time, and the `{color_name}` placeholder's position isn't fixed
across manufacturers, so it can't be reliably recovered afterwards). The raw
per-manufacturer source files (`filaments/*.json` in the repo) DO have exact
`color.name` alongside `color.eans`/`color.eans_refill`/`color.codes`, so
this module downloads the whole repo as a tarball and parses those source
files directly instead of fetching the compiled JSON.

Caches the downloaded+parsed variant list and the built indexes on disk with
a 24h TTL — refreshed lazily on the next lookup once stale, the same pattern
as `ofd.py`.

Copyright (C) 2026 Victor Manuel (hibikipr)
SPDX-License-Identifier: AGPL-3.0-or-later
"""

import io
import json
import os
import re
import tarfile
import time
from pathlib import Path

import requests

SPOOLMANDB_COMMUNITY_TARBALL_URL = "https://codeload.github.com/Icezaza2543/SpoolmanDB-Community/tar.gz/refs/heads/main"
SPOOLMANDB_COMMUNITY_MATERIALS_URL = "https://icezaza2543.github.io/SpoolmanDB-Community/materials.json"
SPOOLMANDB_COMMUNITY_CACHE = Path(os.getenv("SPOOLMANDB_COMMUNITY_CACHE_FILE", "spoolmandb_community_index.json"))
SPOOLMANDB_COMMUNITY_TTL_SECONDS = 24 * 3600

# Bump whenever the on-disk cache shape changes, so an old cache file (e.g.
# pre-dating `codes`/SKU support) is treated as stale and rebuilt instead of
# being misread.
_CACHE_VERSION = 2

# In-process cache so we don't re-download/rebuild on every request.
_GTIN_INDEX: dict | None = None
_SKU_INDEX: dict | None = None
_VARIANTS: list | None = None
_BRANDS: list | None = None
_MATERIALS: list | None = None
_INDEX_LOADED_AT = 0.0


def _canon(barcode: str) -> str:
    """Canonical GTIN form for matching: digits only, leading zeros stripped.

    Duplicated from `ofd.py`'s `_canon()` deliberately, to keep this module
    decoupled from the OFD client (either can be swapped/removed independently).
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
        return h.upper() + "FF"  # RRGGBBAA, opaque
    return None


def _subtype_from_template(name_template: str) -> str | None:
    """Best-effort subtype: the raw (pre-substitution) name minus the {color_name} token.

    Unlike OFD's `_subtype_from`, which regex-strips a known material word out
    of an already-substituted name (a heuristic guess), SpoolmanDB-Community's
    raw source `name` field still contains the literal `{color_name}`
    placeholder before compilation — so this is a direct, reliable removal.
    """
    if not name_template:
        return None
    s = name_template.replace("{color_name}", "")
    s = re.sub(r"\s+", " ", s).strip(" -+")
    return s or None


def _extruder_temps(filament: dict) -> tuple:
    temp_range = filament.get("extruder_temp_range")
    if isinstance(temp_range, list) and len(temp_range) == 2:
        try:
            return int(temp_range[0]), int(temp_range[1])
        except (TypeError, ValueError):
            pass
    single = filament.get("extruder_temp")
    if single is not None:
        try:
            t = int(single)
            return t, t
        except (TypeError, ValueError):
            pass
    return None, None


def _parse_manufacturer_file(manufacturer: str, data: dict) -> list:
    """Expand one manufacturer source file into flat (filament, color) variant dicts."""
    variants = []
    for filament in data.get("filaments", []):
        material = filament.get("material") or ""
        name_template = filament.get("name") or ""
        subtype = _subtype_from_template(name_template)
        weights = filament.get("weights") or []
        label_weight = None
        if weights:
            try:
                label_weight = int(round(float(weights[0]["weight"])))
            except (TypeError, ValueError, KeyError):
                label_weight = None
        nozzle_temp_min, nozzle_temp_max = _extruder_temps(filament)

        for color in filament.get("colors", []):
            color_name = color.get("name")
            hexes = color.get("hexes")
            rgba = _hex_to_rgba(color.get("hex") or hexes)
            eans = color.get("eans") or []
            eans_refill = color.get("eans_refill") or []
            codes = color.get("codes") or []

            title_bits = [manufacturer, subtype, color_name]
            variants.append(
                {
                    "manufacturer": manufacturer,
                    "material": material,
                    "brand": manufacturer,
                    "subtype": subtype,
                    "color_name": color_name,
                    "rgba": rgba,
                    "hexes": hexes,
                    "label_weight": label_weight,
                    "nozzle_temp_min": nozzle_temp_min,
                    "nozzle_temp_max": nozzle_temp_max,
                    "eans": eans,
                    "eans_refill": eans_refill,
                    "codes": codes,
                    "_title": " ".join(b for b in title_bits if b),
                }
            )
    return variants


_BARCODE_FIELD_KEYS = (
    "material",
    "brand",
    "subtype",
    "color_name",
    "rgba",
    "label_weight",
    "nozzle_temp_min",
    "nozzle_temp_max",
    "_title",
)


def _all_codes_for(variant: dict) -> list:
    """Every code (GTIN or SKU) associated with one variant, tagged by kind/refill-ness."""
    codes = []
    for barcode in variant.get("eans") or []:
        codes.append({"code": _canon(barcode), "kind": "gtin", "is_refill": False})
    for barcode in variant.get("eans_refill") or []:
        codes.append({"code": _canon(barcode), "kind": "gtin", "is_refill": True})
    for code in variant.get("codes") or []:
        normalized = (code or "").strip().upper()
        if normalized:
            codes.append({"code": normalized, "kind": "sku", "is_refill": False})
    return codes


def _download_and_parse_variants() -> list:
    """Download the SpoolmanDB-Community repo tarball and parse every manufacturer source file."""
    resp = requests.get(SPOOLMANDB_COMMUNITY_TARBALL_URL, timeout=120)
    resp.raise_for_status()

    variants = []
    with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            parts = Path(member.name).parts
            if len(parts) < 2 or parts[-2] != "filaments" or not member.name.endswith(".json"):
                continue
            extracted = tar.extractfile(member)
            if not extracted:
                continue
            try:
                data = json.loads(extracted.read())
            except (json.JSONDecodeError, ValueError):
                continue
            manufacturer = data.get("manufacturer")
            if not manufacturer:
                continue
            variants.extend(_parse_manufacturer_file(manufacturer, data))
    return variants


def _build_index(variants: list) -> tuple:
    """Build (gtin_index, sku_index) from every eans/eans_refill/codes entry across all variants.

    Both indexes share the same ``entry`` dict per variant (``{"fields": ...,
    "all_codes": [...]}``), so a hit on either a GTIN or a SKU recovers every
    sibling code for that colour — mirroring OFD's variant-grouping but
    without needing a separate ID-indirection table, since this parser
    already produces one dict per (filament, colour).
    """
    gtin_index: dict = {}
    sku_index: dict = {}
    for variant in variants:
        fields = {key: variant.get(key) for key in _BARCODE_FIELD_KEYS}
        all_codes = _all_codes_for(variant)
        entry = {"fields": fields, "all_codes": all_codes}
        for barcode in (*variant.get("eans", []), *variant.get("eans_refill", [])):
            gtin_index[_canon(barcode)] = entry
        for code in variant.get("codes") or []:
            normalized = (code or "").strip().upper()
            if normalized:
                sku_index[normalized] = entry
    return gtin_index, sku_index


def _load_cached():
    if not SPOOLMANDB_COMMUNITY_CACHE.exists():
        return None
    try:
        data = json.loads(SPOOLMANDB_COMMUNITY_CACHE.read_text())
        if data.get("cache_version") != _CACHE_VERSION:
            return None
        if time.time() - data.get("built_at", 0) > SPOOLMANDB_COMMUNITY_TTL_SECONDS:
            return None
        if "variants" not in data:
            return None
        return data.get("gtin_index", {}), data.get("sku_index", {}), data.get("brands", []), data.get("variants", [])
    except Exception:
        return None


def _refresh() -> tuple:
    """Download + parse the repo tarball; build the indexes + brand list; cache all of it."""
    variants = _download_and_parse_variants()
    gtin_index, sku_index = _build_index(variants)
    brands = sorted({v["manufacturer"] for v in variants if v.get("manufacturer")})
    try:
        SPOOLMANDB_COMMUNITY_CACHE.write_text(
            json.dumps(
                {
                    "cache_version": _CACHE_VERSION,
                    "built_at": time.time(),
                    "gtin_index": gtin_index,
                    "sku_index": sku_index,
                    "brands": brands,
                    "variants": variants,
                }
            )
        )
    except Exception:
        pass
    return gtin_index, sku_index, brands, variants


def _ensure_loaded(force: bool = False):
    global _GTIN_INDEX, _SKU_INDEX, _BRANDS, _VARIANTS, _INDEX_LOADED_AT
    if _GTIN_INDEX is not None and not force and (time.time() - _INDEX_LOADED_AT) < SPOOLMANDB_COMMUNITY_TTL_SECONDS:
        return
    loaded = None if force else _load_cached()
    if loaded is None:
        loaded = _refresh()
    _GTIN_INDEX, _SKU_INDEX, _BRANDS, _VARIANTS = loaded
    _INDEX_LOADED_AT = time.time()


def get_gtin_index(force: bool = False) -> dict:
    """Return the canonical-GTIN -> {fields, all_codes} index (memory -> disk cache -> download)."""
    _ensure_loaded(force)
    return _GTIN_INDEX or {}


def get_sku_index(force: bool = False) -> dict:
    """Return the normalized-SKU -> {fields, all_codes} index."""
    _ensure_loaded(force)
    return _SKU_INDEX or {}


def get_index(force: bool = False) -> dict:
    """Back-compat alias: the GTIN index alone (most callers only care about barcodes)."""
    return get_gtin_index(force)


def get_brands() -> list:
    """Return the SpoolmanDB-Community manufacturer list."""
    try:
        _ensure_loaded()
    except Exception:
        return []
    return _BRANDS or []


def get_materials() -> list:
    """Return SpoolmanDB-Community's materials.json (material/density/temp defaults).

    This file has no per-color data, so — unlike the barcode index — it's
    fetched directly from the compiled GitHub Pages copy, no tarball needed.
    Cached in-process for the same TTL window as the barcode index.
    """
    global _MATERIALS
    if _MATERIALS is not None:
        return _MATERIALS
    try:
        resp = requests.get(SPOOLMANDB_COMMUNITY_MATERIALS_URL, timeout=30)
        resp.raise_for_status()
        _MATERIALS = resp.json()
    except Exception:
        return []
    return _MATERIALS


def lookup(barcode: str) -> tuple | None:
    """Resolve a GTIN barcode: (fields, all_codes) for its colour, or None if not found."""
    try:
        idx = get_gtin_index()
    except Exception:
        return None
    entry = idx.get(_canon(barcode))
    if not entry:
        return None
    return entry["fields"], entry["all_codes"]


def lookup_sku(code: str) -> tuple | None:
    """Resolve a manufacturer SKU the same way `lookup` resolves a GTIN."""
    try:
        idx = get_sku_index()
    except Exception:
        return None
    entry = idx.get((code or "").strip().upper())
    if not entry:
        return None
    return entry["fields"], entry["all_codes"]


if __name__ == "__main__":
    gtin_idx = get_gtin_index(force=True)
    sku_idx = get_sku_index()
    print(f"SpoolmanDB-Community index: {len(gtin_idx)} GTINs, {len(sku_idx)} SKUs, {len(get_brands())} brands")
    for k, v in list(gtin_idx.items())[:3]:
        print(k, "→", {kk: vv for kk, vv in v["fields"].items() if kk != "_title"})
