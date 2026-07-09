#!/usr/bin/env python3
"""
filament_to_bambuddy — app.py

A small mobile web app: scan a third-party filament box barcode with your phone,
look up the product (Open Filament Database + a learning per-barcode cache),
review the auto-filled details, and add the spool to your Bambuddy inventory.

Run:
    pip install flask requests
    export BAMBUDDY_URL="https://your-bambuddy"
    export BAMBUDDY_API_KEY="..."
    python app.py        # then open the printed URL on your phone

Camera scanning needs a SECURE origin (https:// or localhost) — see the README.

Copyright (C) 2026 Victor Manuel (hibikipr)
SPDX-License-Identifier: AGPL-3.0-or-later
"""

import sys

if sys.version_info < (3, 10):
    sys.exit(f"❌ Python 3.10+ required (this is {sys.version.split()[0]}).")

import json
import logging
import os
import subprocess
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config (env vars) ─────────────────────────────────────────────────────────

BAMBUDDY_URL = os.getenv("BAMBUDDY_URL", "http://localhost:8000").rstrip("/")
BAMBUDDY_API_KEY = os.getenv("BAMBUDDY_API_KEY", "")

DEFAULT_LABEL_WEIGHT = int(os.getenv("DEFAULT_LABEL_WEIGHT", "1000"))
CACHE_FILE = Path(os.getenv("BARCODE_CACHE_FILE", "barcode_cache.json"))

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8088"))

# Fields Bambuddy's POST /inventory/spools accepts (SpoolCreate). We whitelist
# so the form can't send anything the API rejects.
ALLOWED_SPOOL_FIELDS = {
    "material", "subtype", "color_name", "rgba", "extra_colors", "effect_type",
    "brand", "label_weight", "core_weight", "nozzle_temp_min", "nozzle_temp_max",
    "note", "cost_per_kg", "category", "storage_location", "data_origin",
}

# GTIN-8/12/13/14 are the only standard checksummed lengths. The floor below
# the max (rather than an exact 8/12/13/14 match) accounts for leading zeros
# already stripped from the raw input — see _classify_code. Mirrors Bambuddy's
# `classify_code`/`_gtin_checksum_valid` in `backend/app/schemas/spool.py`.
_MIN_GTIN_LENGTH = 7
_MAX_GTIN_LENGTH = 14


def _gtin_checksum_valid(digits: str) -> bool:
    payload, check = digits[:-1], int(digits[-1])
    total = 0
    for i, ch in enumerate(reversed(payload)):
        total += int(ch) * (3 if i % 2 == 0 else 1)
    return (10 - (total % 10)) % 10 == check


def _classify_code(raw: str) -> tuple[str, str]:
    """Canonicalize `raw` and classify it as ("gtin", digits) or ("sku", stripped-upper).

    Classifies the canonicalized (zero-stripped) form rather than the raw
    input, then re-validates the checksum after re-padding to a full
    GTIN-14 — the checksum is invariant to leading-zero padding (weights are
    assigned right-to-left from the check digit, so a leading zero always
    lands in a weight-agnostic position and contributes 0 to the sum no
    matter how many precede it). Without this, a barcode already missing its
    leading zero(s) (e.g. typed from a receipt showing the short form, or a
    UPC-A with fewer digits than the exact 8/12/13/14-length gate this used
    to require) fails the length check and gets classified as a SKU instead
    of a GTIN — sending the external lookup to the wrong index.
    """
    import ofd

    canonical = ofd._canon(raw)
    if _MIN_GTIN_LENGTH <= len(canonical) <= _MAX_GTIN_LENGTH and _gtin_checksum_valid(
        canonical.zfill(_MAX_GTIN_LENGTH)
    ):
        return canonical, "gtin"
    return (raw or "").strip().upper(), "sku"


def _external_all_codes(code: str, kind: str) -> tuple | None:
    """Cross-reference OFD and SpoolmanDB-Community for `code`, merging both hits.

    Returns (fields, source, all_codes, title) where `source` is whichever
    database resolved first, `fields` prefers that source's values but fills
    any gaps (e.g. missing nozzle temps) from the other, and `all_codes` is
    the union of every sibling code (other package-size GTINs, the refill
    GTIN, the SKU/article number) discovered across both databases. If only
    one database resolves `code` directly, its sibling codes are also probed
    against the *other* database to recover cross-referenced fields/codes.
    Mirrors Bambuddy's `_external_all_codes` in `backend/app/api/routes/inventory.py`.
    """
    import ofd
    import spoolmandb_community

    def _ofd_lookup(c, k):
        return ofd.lookup(c) if k == "gtin" else ofd.lookup_article(c)

    def _smdb_lookup(c, k):
        return spoolmandb_community.lookup(c) if k == "gtin" else spoolmandb_community.lookup_sku(c)

    try:
        ofd_hit = _ofd_lookup(code, kind)
    except Exception:
        ofd_hit = None
    try:
        smdb_hit = _smdb_lookup(code, kind)
    except Exception:
        smdb_hit = None

    if not ofd_hit and not smdb_hit:
        return None

    fields: dict = {}
    all_codes: list = []
    source = None
    title = None

    def _merge(hit, src_name):
        nonlocal source, title
        hit_fields, hit_codes = hit
        for key, value in hit_fields.items():
            if key == "_title":
                continue
            if value is not None and fields.get(key) is None:
                fields[key] = value
        if title is None and hit_fields.get("_title"):
            title = hit_fields["_title"]
        for entry in hit_codes:
            if not any(existing["code"] == entry["code"] for existing in all_codes):
                all_codes.append(entry)
        if source is None:
            source = src_name

    if ofd_hit:
        _merge(ofd_hit, "ofd")
    if smdb_hit:
        _merge(smdb_hit, "spoolmandb-community")

    tried = {code}
    for entry in list(all_codes):
        if ofd_hit and smdb_hit:
            break
        sibling_code = entry["code"]
        if sibling_code in tried:
            continue
        tried.add(sibling_code)
        if not ofd_hit:
            try:
                probe = _ofd_lookup(sibling_code, entry["kind"])
            except Exception:
                probe = None
            if probe:
                _merge(probe, "ofd")
                ofd_hit = probe
        if not smdb_hit:
            try:
                probe = _smdb_lookup(sibling_code, entry["kind"])
            except Exception:
                probe = None
            if probe:
                _merge(probe, "spoolmandb-community")
                smdb_hit = probe

    return fields, source, all_codes, title


def _get_version() -> str:
    """Resolve the running app's version for display in the GUI footer.

    Priority: APP_VERSION env var (baked in at Docker build time from the
    release git tag, see Dockerfile + docker-publish.yml) > local `git
    describe` (useful when running straight from a git checkout) > "dev".
    """
    env_version = os.getenv("APP_VERSION")
    if env_version:
        return env_version
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "dev"


APP_VERSION = _get_version()

app = Flask(__name__)


# ── Barcode cache (learns from your confirmed entries) ────────────────────────

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_cache(cache: dict):
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return render_template("index.html", bambuddy_url=BAMBUDDY_URL, version=APP_VERSION)


@app.get("/sw.js")
def service_worker():
    # Served from the root so its scope covers the whole site (a SW under
    # /static would only control /static/*).
    resp = app.send_static_file("sw.js")
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/manifest.webmanifest")
def manifest():
    resp = app.send_static_file("manifest.webmanifest")
    resp.headers["Content-Type"] = "application/manifest+json"
    return resp


# Dropdown option lists (mirroring Bambuddy's spool edit form).
MATERIAL_OPTIONS = ["PLA", "PETG", "PCTG", "ABS", "ASA", "TPU", "TPE", "PC", "PA",
                    "Nylon", "PVA", "HIPS", "PP", "PET", "PLA-CF", "PETG-CF", "PA-CF"]
SUBTYPE_OPTIONS = ["Basic", "Matte", "Silk", "Silk+", "Plus", "Tough", "HF",
                   "High Speed", "CF", "GF", "Galaxy", "Glow", "Marble", "Metal",
                   "Rainbow", "Sparkle", "Wood", "Translucent", "Transparent",
                   "Clear", "Gradient", "Dual Color", "Tri Color", "Carbon Fiber"]
WEIGHT_OPTIONS = [250, 500, 750, 1000, 2000, 3000]
COLOR_OPTIONS = ["Black", "White", "Gray", "Silver", "Red", "Orange", "Yellow",
                 "Green", "Blue", "Navy", "Cyan", "Teal", "Purple", "Pink",
                 "Magenta", "Brown", "Beige", "Gold", "Bronze", "Copper",
                 "Natural", "Clear", "Transparent"]
DEFAULT_BRANDS = ["Bambu Lab", "Polymaker", "eSUN", "Overture", "SUNLU", "Inland",
                  "Hatchbox", "Prusament", "Creality", "Generic"]


def _bambuddy_locations() -> list[str]:
    """Storage-location names from Bambuddy (best-effort; empty on failure)."""
    if not BAMBUDDY_API_KEY:
        return []
    try:
        r = requests.get(f"{BAMBUDDY_URL}/api/v1/inventory/locations",
                         headers={"X-API-Key": BAMBUDDY_API_KEY, "Accept": "application/json"},
                         timeout=10)
        if r.ok:
            return [loc.get("name") for loc in r.json() if loc.get("name")]
    except Exception:
        pass
    return []


@app.get("/api/options")
def options():
    """Dropdown data for the form (materials, subtypes, weights, colours, brands, locations)."""
    import ofd
    import spoolmandb_community
    try:
        brands = sorted(
            set(DEFAULT_BRANDS) | set(ofd.get_brands()) | set(spoolmandb_community.get_brands()),
            key=str.lower,
        )
    except Exception:
        brands = DEFAULT_BRANDS
    try:
        materials = sorted(
            set(MATERIAL_OPTIONS) | {m["material"] for m in spoolmandb_community.get_materials() if m.get("material")},
            key=str.lower,
        )
    except Exception:
        materials = MATERIAL_OPTIONS
    # Note: SpoolmanDB-Community color names are deliberately NOT merged into
    # COLOR_OPTIONS — that list is a short generic color-family dropdown
    # (~23 entries), while SpoolmanDB's colors are thousands of specific
    # product names on a different axis (already covered by the free-text
    # color_name field, not a constrained dropdown).
    return jsonify(materials=materials, subtypes=SUBTYPE_OPTIONS,
                   weights=WEIGHT_OPTIONS, colors=COLOR_OPTIONS, brands=brands,
                   locations=_bambuddy_locations())


@app.delete("/api/cache")
def clear_cache():
    """Forget ALL remembered per-barcode lookups."""
    n = len(load_cache())
    save_cache({})
    log.info("cache cleared: %d entries removed", n)
    return jsonify(ok=True, cleared=n)


@app.delete("/api/cache/<barcode>")
def forget_barcode(barcode):
    """Forget the remembered entry for one barcode."""
    cache = load_cache()
    existed = barcode in cache
    if existed:
        del cache[barcode]
        save_cache(cache)
        log.info("cache forget: %s", barcode)
    return jsonify(ok=True, removed=existed)


@app.post("/api/ofd/refresh")
def ofd_refresh():
    """Force a re-download/rebuild of the OFD + SpoolmanDB-Community indexes.

    Kept at this URL (not renamed) so the existing "Refresh DB" button in
    templates/index.html doesn't need a second endpoint/button — one refresh
    action updates both community databases.
    """
    import ofd
    import spoolmandb_community
    log.info("OFD + SpoolmanDB-Community refresh started")

    # Each refresh is independently guarded — an OFD network blip must not
    # take down the whole endpoint (previously it returned 502 immediately
    # and never even attempted the SpoolmanDB-Community refresh) or discard
    # a SpoolmanDB-Community refresh that already succeeded.
    try:
        gtin_idx = ofd.get_gtin_index(force=True)
        article_idx = ofd.get_article_index()
        brands = len(ofd.get_brands())
        ofd_codes = len(gtin_idx) + len(article_idx)
        log.info(
            "OFD refresh done: %d GTINs, %d article numbers, %d brands",
            len(gtin_idx), len(article_idx), brands,
        )
    except Exception as e:
        log.error("OFD refresh failed: %s", e)
        ofd_codes = 0
        brands = 0

    try:
        smdb_gtin_idx = spoolmandb_community.get_gtin_index(force=True)
        smdb_sku_idx = spoolmandb_community.get_sku_index()
        smdb_codes = len(smdb_gtin_idx) + len(smdb_sku_idx)
        log.info("SpoolmanDB-Community refresh done: %d codes", smdb_codes)
    except Exception as e:
        log.error("SpoolmanDB-Community refresh failed: %s", e)
        smdb_codes = 0

    return jsonify(
        ok=True,
        barcodes=ofd_codes,
        brands=brands,
        spoolmandb_community_barcodes=smdb_codes,
    )


@app.get("/api/health")
def health():
    """Confirm Bambuddy is reachable + config present, with a specific reason."""
    if not BAMBUDDY_API_KEY:
        return jsonify(ok=False, bambuddy=BAMBUDDY_URL,
                       error="BAMBUDDY_API_KEY not set — start with ./run.sh"), 200
    headers = {"X-API-Key": BAMBUDDY_API_KEY, "Accept": "application/json"}
    # Probe the endpoint we actually use (inventory), so the key is checked
    # against the permission this app needs.
    try:
        r = requests.get(f"{BAMBUDDY_URL}/api/v1/inventory/spools",
                         headers=headers, params={"limit": 1}, timeout=10)
    except requests.exceptions.SSLError as e:
        return jsonify(ok=False, bambuddy=BAMBUDDY_URL, error=f"TLS error: {e}"), 200
    except requests.exceptions.ConnectionError:
        return jsonify(ok=False, bambuddy=BAMBUDDY_URL,
                       error=f"cannot connect to {BAMBUDDY_URL} (wrong URL, or not on the same network?)"), 200
    except Exception as e:
        return jsonify(ok=False, bambuddy=BAMBUDDY_URL, error=str(e)), 200

    if r.ok:
        return jsonify(ok=True, bambuddy=BAMBUDDY_URL, status=r.status_code)
    if r.status_code == 401:
        return jsonify(ok=False, level="error", bambuddy=BAMBUDDY_URL,
                       error="API key rejected (HTTP 401) — wrong or revoked key"), 200
    if r.status_code == 403:
        # Reachable + key valid, but the key lacks inventory permission. Not a
        # connectivity failure — surface as a fixable warning.
        return jsonify(ok=False, level="warn", bambuddy=BAMBUDDY_URL,
                       error=("connected, but this API key lacks inventory access. "
                              "In Bambuddy → Settings → API Keys, enable 'Manage Inventory' "
                              "(required to add spools) and 'Read Status', then update run.sh.")), 200
    return jsonify(ok=False, level="error", bambuddy=BAMBUDDY_URL,
                   error=f"HTTP {r.status_code}: {r.text[:160]}"), 200


@app.get("/api/lookup")
def lookup():
    """Resolve a barcode or SKU to filament fields: cache first, then a
    cross-referenced OFD/SpoolmanDB-Community lookup.

    A scanned/typed code is classified server-side as a GTIN (checksummed,
    standard length) or a manufacturer SKU/article number (e.g. a Code 128
    "inventory barcode" with no UPC/EAN counterpart) via `_classify_code`,
    then resolved through the matching path in each database. Whichever
    database hits first, its sibling codes (other package-size GTINs, the
    refill GTIN, the SKU) are cross-referenced against the *other* database
    to fill in any missing fields — see `_external_all_codes`.
    """
    barcode = (request.args.get("barcode") or "").strip()
    if not barcode:
        return jsonify(error="barcode required"), 400

    code, kind = _classify_code(barcode)

    # 1. Personal cache — your own confirmed entries win. Checked under both
    # the canonicalized code and the raw scanned/typed string, so cache
    # entries written before this rework (keyed by the un-canonicalized
    # value) still hit.
    cache = load_cache()
    cache_hit = cache.get(code)
    if cache_hit is None and code != barcode:
        cache_hit = cache.get(barcode)
    if cache_hit is not None:
        log.info("lookup %s: cache hit", barcode)
        return jsonify(barcode=code, source="cache", fields=cache_hit, title=None, linked_codes=[])

    # 2. Cross-referenced OFD + SpoolmanDB-Community lookup.
    external = _external_all_codes(code, kind)
    if external:
        fields, source, all_codes, title = external
        clean_fields = {k: v for k, v in fields.items() if not k.startswith("_")}
        clean_fields.setdefault("label_weight", DEFAULT_LABEL_WEIGHT)
        linked_codes = [c for c in all_codes if c["code"] != code]
        log.info("lookup %s: %s hit — %s", barcode, source, title or "")
        return jsonify(barcode=code, source=source, title=title, fields=clean_fields, linked_codes=linked_codes)

    # 3. Not found — fill in manually (and it'll be remembered).
    src = "amazon" if kind == "sku" else "none"
    log.info("lookup %s: not found (source=%s)", barcode, src)
    return jsonify(barcode=code, source=src,
                   fields={"label_weight": DEFAULT_LABEL_WEIGHT}, title=None, linked_codes=[])


def _extract_barcode(text: str) -> str | None:
    """Pull a barcode (UPC/EAN/GTIN) out of free text, e.g. label OCR.

    Prefers a labelled number ("EAN: 6938936716785"); falls back to any bare
    12–14 digit run. Returns digits only, or None.
    """
    import re
    m = re.search(r"(?:EAN|UPC|GTIN|BARCODE)\s*[:#]?\s*(\d[\d\s]{6,16}\d)", text, re.I)
    cand = re.sub(r"\D", "", m.group(1)) if m else None
    if not cand:
        m = re.search(r"(?<!\d)(\d{12,14})(?!\d)", text)
        cand = m.group(1) if m else None
    return cand if cand and 8 <= len(cand) <= 14 else None


@app.get("/api/parse")
def parse_endpoint():
    """Parse free text (pasted title or label OCR) into filament fields.

    Heuristically parses the text, and if a barcode is present in it, looks
    that barcode up (OFD, then SpoolmanDB-Community) — authoritative data
    overrides the guesses when found.
    """
    from filament_parse import parse_title
    import ofd
    title = (request.args.get("title") or "").strip()
    if not title:
        return jsonify(fields={})
    try:
        brands = ofd.get_brands()
    except Exception:
        brands = []
    fields = parse_title(title, extra_brands=brands)

    source, out_title = "parsed", title
    linked_codes: list = []
    barcode = _extract_barcode(title)
    resolved_code = barcode
    if barcode:
        code, kind = _classify_code(barcode)
        external = _external_all_codes(code, kind)
        if external:
            ext_fields, ext_source, all_codes, ext_title = external
            fields = {**fields, **{k: v for k, v in ext_fields.items() if not k.startswith("_") and v is not None}}
            source = ext_source
            out_title = ext_title or title
            resolved_code = code
            linked_codes = [c for c in all_codes if c["code"] != code]

    fields.setdefault("label_weight", DEFAULT_LABEL_WEIGHT)
    return jsonify(fields=fields, title=out_title, barcode=resolved_code, source=source, linked_codes=linked_codes)


@app.post("/api/spool")
def add_spool():
    """Create one or more spools in Bambuddy, then remember the details by barcode."""
    if not BAMBUDDY_API_KEY:
        return jsonify(ok=False, error="BAMBUDDY_API_KEY not set on the server"), 400

    body = request.get_json(force=True, silent=True) or {}
    barcode = (body.get("barcode") or "").strip()
    quantity = max(1, min(int(body.get("quantity") or 1), 50))
    fields = body.get("fields") or {}

    if not (fields.get("material") or "").strip():
        return jsonify(ok=False, error="Material is required"), 400

    # Build a clean Bambuddy payload from whitelisted, typed fields.
    payload: dict = {}
    for key in ALLOWED_SPOOL_FIELDS:
        if key not in fields or fields[key] in (None, ""):
            continue
        val = fields[key]
        if key in ("label_weight", "core_weight", "nozzle_temp_min", "nozzle_temp_max"):
            try:
                val = int(val)
            except (TypeError, ValueError):
                continue
        elif key == "cost_per_kg":
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
        payload[key] = val
    payload.setdefault("label_weight", DEFAULT_LABEL_WEIGHT)
    payload["data_origin"] = "barcode-scan"

    headers = {"X-API-Key": BAMBUDDY_API_KEY, "Content-Type": "application/json",
               "Accept": "application/json"}
    created, errors = 0, []
    for _ in range(quantity):
        try:
            r = requests.post(f"{BAMBUDDY_URL}/api/v1/inventory/spools",
                              json=payload, headers=headers, timeout=30)
            if r.status_code in (200, 201):
                created += 1
            else:
                errors.append(f"{r.status_code}: {r.text[:200]}")
                break
        except Exception as e:
            errors.append(str(e))
            break

    # Remember the confirmed details for this barcode (learning cache), plus
    # every cross-referenced sibling code — so a later scan of ANY of them
    # (another package-size GTIN, the refill GTIN, the manufacturer SKU)
    # resolves instantly as "remembered" instead of re-querying OFD/SpoolmanDB.
    if created and barcode:
        cache = load_cache()
        remembered = {k: v for k, v in fields.items()
                      if k in ALLOWED_SPOOL_FIELDS or k in ("diameter_mm",)}
        code, kind = _classify_code(barcode)
        cache[code] = remembered
        try:
            external = _external_all_codes(code, kind)
        except Exception:
            external = None
        if external:
            _, _, all_codes, _ = external
            for entry in all_codes:
                if entry["code"] != code:
                    cache[entry["code"]] = remembered
        save_cache(cache)

    ok = created == quantity
    material = payload.get("material", "?")
    brand = payload.get("brand", "")
    label = f"{brand} {material}".strip() if brand else material
    if ok:
        log.info("spool added: %dx %s (barcode=%s)", created, label, barcode or "none")
    else:
        log.warning("spool add partial: %d/%d %s (barcode=%s) errors=%s",
                    created, quantity, label, barcode or "none", errors)
    return jsonify(ok=ok, created=created, requested=quantity,
                   errors=errors, bambuddy=BAMBUDDY_URL), (200 if created else 502)


if __name__ == "__main__":
    print(f"  Bambuddy: {BAMBUDDY_URL}  (API key {'set' if BAMBUDDY_API_KEY else 'NOT set'})")
    print(f"  Open on your phone:  http://<this-computer-ip>:{PORT}/")
    print("  ⚠️  Camera scanning needs https:// or localhost — see README.\n")
    app.run(host=HOST, port=PORT, debug=False)
