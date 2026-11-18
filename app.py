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

if sys.version_info < (3, 10):  # noqa: UP036 - guards direct `python app.py` runs on an old system Python, independent of the Docker image's pinned version
    sys.exit(f"❌ Python 3.10+ required (this is {sys.version.split()[0]}).")

import json
import logging
import os
import re
import subprocess
from pathlib import Path

import requests
from flask import Flask, jsonify, make_response, render_template, request

import i18n
import label_reader

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


class LookupUnavailable(Exception):
    """Neither OFD nor SpoolmanDB-Community could be checked (index download
    failed with nothing cached). Distinct from a plain miss, which means both
    were checked and neither knows the code."""


def _finish_fields(fields: dict) -> dict:
    """Bring merged database fields in line with what Bambuddy stores.

    Material as Bambuddy's list spells it ("Nylon" → "PA"), an effect_type
    Bambuddy accepts, and — when the database didn't give one — the effect the
    product line or colour name implies ("Dual Matte PLA", "Galaxy Black").
    """
    if fields.get("material"):
        fields["material"] = label_reader.canonical_material(fields["material"])
    effect = label_reader.normalize_effect(fields.get("effect_type"))
    if not effect:
        effect = label_reader.effect(" ".join(
            str(fields[k]) for k in ("subtype", "color_name") if fields.get(k)))
    fields["effect_type"] = effect
    if not fields.get("extra_colors"):
        fields.pop("extra_colors", None)
    if fields.get("effect_type") is None:
        fields.pop("effect_type", None)
    return fields


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

    Returns None when both databases were checked and neither knows the code;
    raises LookupUnavailable when neither could be checked at all.
    """
    import ofd
    import spoolmandb_community

    def _ofd_lookup(c, k):
        return ofd.lookup(c, strict=True) if k == "gtin" else ofd.lookup_article(c, strict=True)

    def _smdb_lookup(c, k):
        if k == "gtin":
            return spoolmandb_community.lookup(c, strict=True)
        return spoolmandb_community.lookup_sku(c, strict=True)

    ofd_failed = smdb_failed = False
    try:
        ofd_hit = _ofd_lookup(code, kind)
    except Exception:
        log.warning("OFD lookup couldn't run for %s", code, exc_info=True)
        ofd_hit, ofd_failed = None, True
    try:
        smdb_hit = _smdb_lookup(code, kind)
    except Exception:
        log.warning("SpoolmanDB-Community lookup couldn't run for %s", code, exc_info=True)
        smdb_hit, smdb_failed = None, True

    if not ofd_hit and not smdb_hit:
        if ofd_failed and smdb_failed:
            raise LookupUnavailable(code)
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
    # list(...) is required, not redundant: _merge() below appends newly
    # cross-referenced codes to all_codes, so iterating a live view of it
    # here would pick up entries added mid-loop instead of just the
    # original siblings.
    for entry in list(all_codes):  # noqa: PERF101
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

    return _finish_fields(fields), source, all_codes, title


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
            check=False,  # returncode is checked explicitly below, not raised on
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        # Expected/benign when not running from a git checkout (e.g. inside
        # the Docker image, which doesn't copy .git) - debug, not a warning.
        log.debug("git describe unavailable", exc_info=True)
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

LANG_COOKIE_NAME = "lang"
LANG_COOKIE_MAX_AGE = 365 * 24 * 3600


def _resolve_request_locale() -> str:
    """?lang= query override > lang cookie > browser Accept-Language > default.

    See i18n.resolve_locale for the actual precedence/matching logic — this
    just pulls the three candidate values out of the current Flask request.
    """
    return i18n.resolve_locale(
        request.headers.get("Accept-Language"),
        request.args.get("lang"),
        request.cookies.get(LANG_COOKIE_NAME),
    )


@app.get("/")
def index():
    lang = _resolve_request_locale()
    translator = i18n.Translator(lang)
    resp = make_response(
        render_template(
            "index.html",
            bambuddy_url=BAMBUDDY_URL,
            version=APP_VERSION,
            lang=lang,
            supported_langs=i18n.SUPPORTED_LANGS,
            t=translator.t,
            translations=i18n.TRANSLATIONS.get(lang, i18n.TRANSLATIONS[i18n.DEFAULT_LANG]),
        )
    )
    # Remember an explicit ?lang= choice so it sticks on the next visit
    # (e.g. after adding the PWA to the home screen, where there's no address
    # bar to re-type ?lang= into).
    if request.args.get("lang") in i18n.TRANSLATIONS:
        resp.set_cookie(LANG_COOKIE_NAME, lang, max_age=LANG_COOKIE_MAX_AGE, samesite="Lax")
    return resp


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


# Dropdown option lists (mirroring Bambuddy's spool edit form). Materials are
# Bambuddy's MATERIALS, spelled its way (nylon is "PA"), plus a few common ones
# it doesn't list.
MATERIAL_OPTIONS = label_reader.BAMBUDDY_MATERIALS + ["PCTG", "TPE", "PP", "PET"]
# Subtype is the product line only. Finishes (Silk, Matte, Glow, Dual Color…)
# are the separate Effect field, Bambuddy's effect_type — this is Bambuddy's
# KNOWN_VARIANTS without them.
SUBTYPE_OPTIONS = ["Basic", "Silk+", "Plus", "Tough", "Tough+", "HF", "High Flow",
                   "High Speed", "Engineering", "CF", "GF", "Lite", "Pro", "Max",
                   "Super", "Ultra", "Flex", "Soft", "Hard", "Strong", "Impact",
                   "Heat Resistant", "UV Resistant", "ESD", "Conductive", "Magnetic"]
EFFECT_OPTIONS = [value for value, _ in label_reader.EFFECT_OPTIONS]
WEIGHT_OPTIONS = [250, 500, 750, 1000, 2000, 3000]
COLOR_OPTIONS = ["Black", "White", "Gray", "Silver", "Red", "Orange", "Yellow",
                 "Green", "Blue", "Navy", "Cyan", "Teal", "Purple", "Pink",
                 "Magenta", "Brown", "Beige", "Gold", "Bronze", "Copper",
                 "Natural", "Clear", "Transparent"]
DEFAULT_BRANDS = ["Bambu Lab", "Polymaker", "eSUN", "Overture", "SUNLU", "Inland",
                  "Hatchbox", "Prusament", "Creality", "Generic"]


# ── Bambuddy inventory backend (built-in or Spoolman) ─────────────────────────

INVENTORY_BUILTIN = "builtin"
INVENTORY_SPOOLMAN = "spoolman"
_INVENTORY_BASE = {
    INVENTORY_BUILTIN: "/api/v1/inventory",
    INVENTORY_SPOOLMAN: "/api/v1/spoolman/inventory",
}
# Spool fields Bambuddy's Spoolman proxy (SpoolmanInventoryCreate) has no
# place for. Sent anyway they'd be silently dropped, so they're left out and
# the form hides them in that mode.
SPOOLMAN_UNSUPPORTED_FIELDS = {
    "extra_colors", "effect_type", "nozzle_temp_min", "nozzle_temp_max",
    "category", "data_origin",
}
# The last mode Bambuddy answered with, kept so a network blip doesn't switch
# a Spoolman user back to the built-in inventory.
_last_inventory_backend = INVENTORY_BUILTIN


def _inventory_backend() -> str:
    """Which inventory Bambuddy is serving: its own, or Spoolman through its proxy.

    Asks /spoolman/status (needs `filaments:read`). An API key without that
    (401/403) falls back to whether the Spoolman inventory proxy answers,
    which needs only inventory access and replies 400 "not enabled" in
    built-in mode. Checked on every add, health check and form load, so
    flipping Bambuddy's Spoolman switch is followed without a restart. Same
    detection as NozzleCast's BambuddyAPIClient.inventoryBackend().
    """
    global _last_inventory_backend
    headers = {"X-API-Key": BAMBUDDY_API_KEY, "Accept": "application/json"}
    try:
        r = requests.get(f"{BAMBUDDY_URL}/api/v1/spoolman/status", headers=headers, timeout=10)
        if r.ok:
            enabled = bool((r.json() or {}).get("enabled"))
            mode = INVENTORY_SPOOLMAN if enabled else INVENTORY_BUILTIN
        elif r.status_code in (401, 403):
            probe = requests.get(f"{BAMBUDDY_URL}/api/v1/spoolman/inventory/spools",
                                 headers=headers, params={"limit": 1}, timeout=10)
            if probe.ok:
                mode = INVENTORY_SPOOLMAN
            elif probe.status_code < 500:
                mode = INVENTORY_BUILTIN
            else:
                return _last_inventory_backend
        elif r.status_code < 500:
            # Older Bambuddy without the route, or another 4xx: built-in.
            mode = INVENTORY_BUILTIN
        else:
            return _last_inventory_backend
    except Exception:
        log.debug("inventory backend detection failed; keeping %s", _last_inventory_backend, exc_info=True)
        return _last_inventory_backend
    if mode != _last_inventory_backend:
        log.info("Bambuddy inventory: %s", mode)
    _last_inventory_backend = mode
    return mode


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
        log.debug("Bambuddy location fetch failed (best-effort)", exc_info=True)
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
            set(MATERIAL_OPTIONS) | {
                label_reader.canonical_material(m["material"])
                for m in spoolmandb_community.get_materials() if m.get("material")
            },
            key=str.lower,
        )
    except Exception:
        materials = MATERIAL_OPTIONS
    # Note: SpoolmanDB-Community color names are deliberately NOT merged into
    # COLOR_OPTIONS — that list is a short generic color-family dropdown
    # (~23 entries), while SpoolmanDB's colors are thousands of specific
    # product names on a different axis (already covered by the free-text
    # color_name field, not a constrained dropdown).
    inventory = _inventory_backend() if BAMBUDDY_API_KEY else INVENTORY_BUILTIN
    return jsonify(materials=materials, subtypes=SUBTYPE_OPTIONS, effects=EFFECT_OPTIONS,
                   weights=WEIGHT_OPTIONS, colors=COLOR_OPTIONS, brands=brands,
                   locations=_bambuddy_locations(), inventory=inventory,
                   hidden_fields=sorted(SPOOLMAN_UNSUPPORTED_FIELDS - {"data_origin"})
                   if inventory == INVENTORY_SPOOLMAN else [])


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
    # Probe the endpoint we actually use (inventory — Bambuddy's own, or its
    # Spoolman proxy when it tracks filament in Spoolman, where the built-in
    # route stops answering), so the key is checked against the permission
    # this app needs.
    inventory = _inventory_backend()
    try:
        r = requests.get(f"{BAMBUDDY_URL}{_INVENTORY_BASE[inventory]}/spools",
                         headers=headers, params={"limit": 1}, timeout=10)
    except requests.exceptions.SSLError:
        log.warning("bambuddy health check: TLS error contacting %s", BAMBUDDY_URL, exc_info=True)
        return jsonify(ok=False, bambuddy=BAMBUDDY_URL, error="TLS error contacting Bambuddy — check the URL/certificate"), 200
    except requests.exceptions.ConnectionError:
        return jsonify(ok=False, bambuddy=BAMBUDDY_URL,
                       error=f"cannot connect to {BAMBUDDY_URL} (wrong URL, or not on the same network?)"), 200
    except Exception as e:
        log.exception("bambuddy health check failed unexpectedly")
        return jsonify(ok=False, bambuddy=BAMBUDDY_URL,
                       error=f"{type(e).__name__} — see server logs"), 200

    if r.ok:
        return jsonify(ok=True, bambuddy=BAMBUDDY_URL, status=r.status_code, inventory=inventory)
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

    # An Amazon FNSKU sticker ("X00…") is a stock code no filament database
    # knows; don't look it up, ask for the box's other barcode instead.
    if label_reader.is_amazon_stock_code(barcode):
        log.info("lookup %s: Amazon FNSKU, skipped", barcode)
        return jsonify(barcode=code, source="fnsku",
                       fields={"label_weight": DEFAULT_LABEL_WEIGHT}, title=None, linked_codes=[])

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
    try:
        external = _external_all_codes(code, kind)
    except LookupUnavailable:
        # Couldn't check, which is not the same as "not found": say so, so a
        # failed index download doesn't read as an unknown filament.
        log.warning("lookup %s: databases unavailable", barcode)
        return jsonify(barcode=code, source="error", lookup_error=True,
                       fields={"label_weight": DEFAULT_LABEL_WEIGHT}, title=None, linked_codes=[])
    if external:
        fields, source, all_codes, title = external
        clean_fields = {k: v for k, v in fields.items() if not k.startswith("_")}
        clean_fields.setdefault("label_weight", DEFAULT_LABEL_WEIGHT)
        linked_codes = [c for c in all_codes if c["code"] != code]
        log.info("lookup %s: %s hit — %s", barcode, source, title or "")
        return jsonify(barcode=code, source=source, title=title, fields=clean_fields, linked_codes=linked_codes)

    # 3. Not found — fill in manually (and it'll be remembered).
    log.info("lookup %s: not found", barcode)
    return jsonify(barcode=code, source="none",
                   fields={"label_weight": DEFAULT_LABEL_WEIGHT}, title=None, linked_codes=[])


def _extract_barcode(text: str) -> str | None:
    """Pull a printed barcode (UPC/EAN/GTIN) out of free text — see label_reader.extract_barcode."""
    return label_reader.extract_barcode(text)


# A label photo's OCR text is a few hundred characters; this bounds what a
# request can make the parser chew on.
_MAX_PARSE_TEXT = 20_000
_MAX_PARSE_BARCODES = 20


@app.route("/api/parse", methods=["GET", "POST"])
def parse_endpoint():
    """Parse free text (a pasted title, or a label photo) into filament fields.

    GET ?title=… takes a pasted product title. POST {"text": …, "barcodes": […]}
    takes a label photo: its OCR text, line breaks kept, and every barcode
    decoded from the image itself.

    The text is parsed heuristically, then every code on the label is looked
    up in order (decoded GTINs, the printed EAN/UPC, other barcodes, the value
    under a "SKU" heading, other SKU-shaped tokens; Amazon FNSKU stickers
    skipped) and the first database hit wins. The label still fills what the
    database leaves out — its finish, a dual-colour roll's colours — and its
    printed weight beats the database's, since one code can cover several
    sizes. Same order as NozzleCast's FilamentLookupService.analyze.
    """
    import ofd
    from filament_parse import parse_title
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
        text = str(body.get("text") or "")[:_MAX_PARSE_TEXT].strip()
        barcodes = [str(b)[:200] for b in (body.get("barcodes") or []) if isinstance(b, (str, int))]
        barcodes = barcodes[:_MAX_PARSE_BARCODES]
    else:
        text = (request.args.get("title") or "")[:_MAX_PARSE_TEXT].strip()
        barcodes = []
    if not text and not barcodes:
        return jsonify(fields={})
    try:
        brands = ofd.get_brands()
    except Exception:
        brands = []
    parsed = parse_title(text, extra_brands=brands) if text else {}
    labelled = label_reader.label_color(text)
    fields = dict(parsed)

    source, out_title = "parsed", text
    linked_codes: list = []
    resolved_code = None
    lookup_error = False
    for candidate in label_reader.code_candidates(text, barcodes, classify=_classify_code):
        code, kind = _classify_code(candidate)
        try:
            external = _external_all_codes(code, kind)
        except LookupUnavailable:
            # Neither database could be reached; every other code would fail
            # the same way.
            lookup_error = True
            break
        if not external:
            if resolved_code is None and kind == "gtin":
                resolved_code = code
            continue
        ext_fields, ext_source, all_codes, ext_title = external
        db = {k: v for k, v in ext_fields.items() if not k.startswith("_") and v is not None}
        fields = {**fields, **db}
        # The box's own printed weight wins: a database code can cover several sizes.
        if parsed.get("label_weight"):
            fields["label_weight"] = parsed["label_weight"]
        # Keep the label's split-colour swatch when the database has none.
        if "extra_colors" not in db and parsed.get("extra_colors") and \
                fields.get("effect_type") in label_reader.MULTICOLOR_EFFECTS:
            fields["extra_colors"] = parsed["extra_colors"]
        elif "extra_colors" not in db:
            fields.pop("extra_colors", None)
        if "effect_type" not in db and parsed.get("effect_type"):
            fields["effect_type"] = parsed["effect_type"]
        # A database name that's product line + colour ("PolyLite PLA Pro
        # Blue") when the label names the colour on its own ("COLOR: Blue"):
        # the label's colour, and the rest as the product line.
        if labelled["explicit"] and labelled["name"]:
            split = label_reader.split_product_and_color(
                db.get("color_name"), labelled["name"], fields.get("material"))
            if split:
                fields["color_name"] = split[0]
                if not db.get("subtype") and split[1]:
                    fields["subtype"] = split[1]
        source = ext_source
        out_title = ext_title or text
        resolved_code = code
        linked_codes = [c for c in all_codes if c["code"] != code]
        break

    if fields.get("material"):
        fields["material"] = label_reader.canonical_material(fields["material"])
    fields.setdefault("label_weight", DEFAULT_LABEL_WEIGHT)
    return jsonify(fields=fields, title=out_title, barcode=resolved_code, source=source,
                   linked_codes=linked_codes, lookup_error=lookup_error)


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
        elif key == "effect_type":
            val = label_reader.normalize_effect(val)
            if val is None:
                continue
        elif key == "material":
            val = label_reader.canonical_material(val)
        elif key == "extra_colors":
            # Bambuddy rejects the whole spool over one bad token, and takes
            # at most 8 stops: keep the valid ones.
            stops = [t.strip().lstrip("#") for t in str(val).split(",")]
            stops = [t.upper() for t in stops if re.fullmatch(r"[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?", t)][:8]
            if not stops:
                continue
            val = ",".join(stops)
        payload[key] = val
    payload.setdefault("label_weight", DEFAULT_LABEL_WEIGHT)
    payload["data_origin"] = "barcode-scan"

    # Bambuddy tracking filament in Spoolman: its built-in inventory route
    # stops answering and spools go through the Spoolman proxy, which has no
    # place for extra colours, the effect, nozzle temps or category.
    inventory = _inventory_backend()
    if inventory == INVENTORY_SPOOLMAN:
        for key in SPOOLMAN_UNSUPPORTED_FIELDS:
            payload.pop(key, None)
    spools_url = f"{BAMBUDDY_URL}{_INVENTORY_BASE[inventory]}/spools"

    headers = {"X-API-Key": BAMBUDDY_API_KEY, "Content-Type": "application/json",
               "Accept": "application/json"}
    created, errors = 0, []
    for _ in range(quantity):
        try:
            r = requests.post(spools_url, json=payload, headers=headers, timeout=30)
            if r.status_code in (200, 201):
                created += 1
            else:
                errors.append(f"{r.status_code}: {r.text[:200]}")
                break
        except Exception as e:
            log.exception("error posting spool to Bambuddy")
            errors.append(f"{type(e).__name__} — see server logs")
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
        except Exception:  # incl. LookupUnavailable: just skip the siblings
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
    return jsonify(ok=ok, created=created, requested=quantity, inventory=inventory,
                   errors=errors, bambuddy=BAMBUDDY_URL), (200 if created else 502)


if __name__ == "__main__":
    print(f"  Bambuddy: {BAMBUDDY_URL}  (API key {'set' if BAMBUDDY_API_KEY else 'NOT set'})")
    print(f"  Open on your phone:  http://<this-computer-ip>:{PORT}/")
    print("  ⚠️  Camera scanning needs https:// or localhost — see README.\n")
    app.run(host=HOST, port=PORT, debug=False)
