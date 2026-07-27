#!/usr/bin/env python3
"""
ofd.py — Open Filament Database barcode lookup.

The OFD (https://openfilamentdatabase.org) publishes a complete data dump with
~2,500 real spool barcodes (GTINs) joined to brand / material / colour / weight.
We download it once, build a barcode → fields index, and refresh daily.

Each OFD ``sizes`` row can carry a ``gtin`` (retail barcode) AND/OR an
``article_number`` (manufacturer SKU — what SpoolmanDB-Community calls
``codes``) AND a ``spool_refill`` flag, independently of each other. Multiple
``sizes`` rows (one per package weight) share one ``variant_id`` (one per
colour), so this module groups all codes sharing a ``variant_id`` together —
a hit on any one of them (via `lookup`/`lookup_article`) also returns every
sibling code for that colour, letting a scan of an *unfamiliar* code still
resolve once *any* of its siblings has been seen before (see `app.py`'s
`resolve_code`).

Copyright (C) 2026 Victor Manuel (hibikipr)
SPDX-License-Identifier: AGPL-3.0-or-later
"""

import json
import os
import re
import time
from pathlib import Path

import requests

OFD_ALL_URL = "https://api.openfilamentdatabase.org/json/all.json"
OFD_CACHE = Path(os.getenv("OFD_CACHE_FILE", "ofd_index.json"))
OFD_TTL_SECONDS = 24 * 3600

# Generous cap against a malicious/broken upstream serving an oversized or
# infinite response — the real dump is a small fraction of this. Mirrors the
# same guard spoolmandb_community.py already has on its tarball download.
_MAX_ALL_JSON_BYTES = 128 * 1024 * 1024

# Bump whenever the on-disk cache shape changes, so an old cache file (e.g.
# pre-dating article_number/variant-code support) is treated as stale and
# rebuilt instead of being misread.
_CACHE_VERSION = 2

# In-process cache so we don't rebuild on every request.
_GTIN_INDEX: dict | None = None
_ARTICLE_INDEX: dict | None = None
_VARIANT_CODES: dict | None = None
_BRANDS: list | None = None
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


def _build_index(all_json: dict) -> tuple:
    """Build (gtin_index, article_index, variant_codes) from the OFD all.json dump.

    ``gtin_index`` / ``article_index`` map a canonicalized code to
    ``{"fields": {...}, "variant_id": str}`` — fields are computed per *size*
    row (e.g. `label_weight` legitimately differs across package sizes of the
    same colour), so each code keeps its own accurate fields.

    ``variant_codes`` maps ``variant_id`` -> every code (GTIN or SKU/article,
    across every package size) sharing that colour, so a hit on any one code
    can recover its siblings for cross-referencing.
    """
    brands = {b["id"]: b for b in all_json.get("brands", []) if "id" in b}
    filaments = {f["id"]: f for f in all_json.get("filaments", []) if "id" in f}
    variants = {v["id"]: v for v in all_json.get("variants", []) if "id" in v}

    gtin_index: dict = {}
    article_index: dict = {}
    variant_codes: dict = {}

    for size in all_json.get("sizes", []):
        gtin = size.get("gtin")
        article = size.get("article_number")
        if not gtin and not article:
            continue

        variant_id = size.get("variant_id")
        variant = variants.get(variant_id)
        if not variant:
            continue
        # Always key/store variant_id as a string: dict keys become strings
        # after a JSON cache round-trip regardless of the source type, so
        # storing anything else here would silently break get()-lookups the
        # moment the cache is reloaded from disk.
        variant_id = str(variant_id)
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

        is_refill = bool(size.get("spool_refill"))
        codes_for_variant = variant_codes.setdefault(variant_id, [])

        if gtin:
            canonical_gtin = _canon(gtin)
            gtin_index[canonical_gtin] = {"fields": fields, "variant_id": variant_id}
            if not any(c["code"] == canonical_gtin for c in codes_for_variant):
                codes_for_variant.append({"code": canonical_gtin, "kind": "gtin", "is_refill": is_refill})
        if article:
            normalized_article = article.strip().upper()
            article_index[normalized_article] = {"fields": fields, "variant_id": variant_id}
            if not any(c["code"] == normalized_article for c in codes_for_variant):
                codes_for_variant.append({"code": normalized_article, "kind": "sku", "is_refill": is_refill})

    return gtin_index, article_index, variant_codes


def _read_cache_file() -> dict | None:
    """Parse the cache file and check its version, ignoring TTL. Returns the
    raw dict, or None if missing/corrupt/wrong-version — those are the only
    conditions that make a cache file truly unusable; staleness alone does not."""
    if not OFD_CACHE.exists():
        return None
    try:
        data = json.loads(OFD_CACHE.read_text())
        if data.get("cache_version") != _CACHE_VERSION:
            return None
        return data
    except Exception:
        return None


def _cache_tuple(data: dict) -> tuple:
    return (
        data.get("gtin_index", {}),
        data.get("article_index", {}),
        data.get("variant_codes", {}),
        data.get("brands", []),
    )


def _load_cached() -> tuple | None:
    """Return the cache contents if present and fresh (within TTL), else None."""
    data = _read_cache_file()
    if data is None:
        return None
    if time.time() - data.get("built_at", 0) > OFD_TTL_SECONDS:
        return None
    return _cache_tuple(data)


def _load_stale_cached() -> tuple | None:
    """Return the cache contents regardless of TTL — a last-resort fallback
    for when a refresh attempt fails (e.g. offline), so a working-but-old
    index is still served instead of dropping to "no match" for everything."""
    data = _read_cache_file()
    return None if data is None else _cache_tuple(data)


def _refresh() -> tuple:
    """Download all.json; build the indexes + brand-name list; cache all of it."""
    chunks = bytearray()
    # Streamed with a running size cap rather than requests.get(...).json() —
    # the latter buffers the whole response with no ceiling, so a large or
    # slow upstream response (malicious or just broken) could OOM the app on
    # the 24h auto-refresh.
    with requests.get(OFD_ALL_URL, timeout=60, stream=True) as resp:
        resp.raise_for_status()
        for chunk in resp.iter_content(chunk_size=65536):
            chunks.extend(chunk)
            if len(chunks) > _MAX_ALL_JSON_BYTES:
                raise ValueError(f"OFD all.json exceeded {_MAX_ALL_JSON_BYTES} byte cap - aborting download")
    all_json = json.loads(bytes(chunks))
    gtin_index, article_index, variant_codes = _build_index(all_json)
    brands = sorted({b["name"] for b in all_json.get("brands", []) if b.get("name")})
    if not gtin_index and not article_index:
        # A 200 that parses to zero entries (e.g. upstream's dump shape
        # changes) must not overwrite a good cache with an empty one and
        # silently return "no match" for everyone for a full TTL.
        # _ensure_loaded's except-path already falls back to the stale cache
        # on any refresh failure, so raising here reuses that fallback.
        raise RuntimeError("OFD refresh parsed zero entries - keeping previous cache")
    try:
        # Write to a temp file and rename over the real path — Path.replace()
        # is atomic (POSIX rename(2) semantics, and Windows-safe since it
        # replaces an existing destination too), so a reader never observes a
        # half-written cache file even if the process is killed mid-write.
        tmp_path = OFD_CACHE.with_suffix(OFD_CACHE.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(
                {
                    "cache_version": _CACHE_VERSION,
                    "built_at": time.time(),
                    "gtin_index": gtin_index,
                    "article_index": article_index,
                    "variant_codes": variant_codes,
                    "brands": brands,
                }
            )
        )
        tmp_path.replace(OFD_CACHE)
    except Exception:
        pass
    return gtin_index, article_index, variant_codes, brands


def _ensure_loaded(force: bool = False):
    global _GTIN_INDEX, _ARTICLE_INDEX, _VARIANT_CODES, _BRANDS, _INDEX_LOADED_AT
    if _GTIN_INDEX is not None and not force and (time.time() - _INDEX_LOADED_AT) < OFD_TTL_SECONDS:
        return
    loaded = None if force else _load_cached()
    if loaded is None:
        try:
            loaded = _refresh()
        except Exception:
            # Offline/upstream-down: a stale-but-working index beats no index
            # at all. Only re-raise if there's truly nothing on disk to fall
            # back to (e.g. first-ever startup with no network) — that's the
            # one case where the caller must know the lookup couldn't be
            # attempted at all.
            loaded = _load_stale_cached()
            if loaded is None:
                raise
    _GTIN_INDEX, _ARTICLE_INDEX, _VARIANT_CODES, _BRANDS = loaded
    _INDEX_LOADED_AT = time.time()


def get_gtin_index(force: bool = False) -> dict:
    """Return the canonical-GTIN -> {fields, variant_id} index (memory -> disk cache -> download)."""
    _ensure_loaded(force)
    return _GTIN_INDEX or {}


def get_article_index(force: bool = False) -> dict:
    """Return the normalized-article-number -> {fields, variant_id} index."""
    _ensure_loaded(force)
    return _ARTICLE_INDEX or {}


def get_index(force: bool = False) -> dict:
    """Back-compat alias: the GTIN index alone (most callers only care about barcodes)."""
    return get_gtin_index(force)


def get_brands() -> list:
    """Return the OFD brand-name list (for data-driven brand detection)."""
    try:
        _ensure_loaded()
    except Exception:
        return []
    return _BRANDS or []


def _codes_for_variant(variant_id: str) -> list:
    return list(_VARIANT_CODES.get(variant_id, [])) if _VARIANT_CODES else []


def lookup(barcode: str) -> tuple | None:
    """Resolve a GTIN barcode: (fields, all_codes) for its colour, or None if not found.

    ``all_codes`` includes every GTIN/SKU sibling (other package sizes, the
    refill code, the manufacturer article number) sharing the same colour.
    """
    try:
        idx = get_gtin_index()
    except Exception:
        return None
    entry = idx.get(_canon(barcode))
    if not entry:
        return None
    return entry["fields"], _codes_for_variant(entry["variant_id"])


def lookup_article(code: str) -> tuple | None:
    """Resolve a manufacturer SKU/article number the same way `lookup` resolves a GTIN."""
    try:
        idx = get_article_index()
    except Exception:
        return None
    entry = idx.get((code or "").strip().upper())
    if not entry:
        return None
    return entry["fields"], _codes_for_variant(entry["variant_id"])


if __name__ == "__main__":
    gtin_idx = get_gtin_index(force=True)
    article_idx = get_article_index()
    print(f"OFD index: {len(gtin_idx)} GTINs, {len(article_idx)} article numbers")
    # show a couple of examples
    for k, v in list(gtin_idx.items())[:3]:
        print(k, "→", {kk: vv for kk, vv in v["fields"].items() if kk != "_title"})
