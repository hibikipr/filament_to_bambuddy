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
import os
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request

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
    return render_template("index.html", bambuddy_url=BAMBUDDY_URL)


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
    try:
        brands = sorted(set(DEFAULT_BRANDS) | set(ofd.get_brands()), key=str.lower)
    except Exception:
        brands = DEFAULT_BRANDS
    return jsonify(materials=MATERIAL_OPTIONS, subtypes=SUBTYPE_OPTIONS,
                   weights=WEIGHT_OPTIONS, colors=COLOR_OPTIONS, brands=brands,
                   locations=_bambuddy_locations())


@app.delete("/api/cache")
def clear_cache():
    """Forget ALL remembered per-barcode lookups."""
    n = len(load_cache())
    save_cache({})
    return jsonify(ok=True, cleared=n)


@app.delete("/api/cache/<barcode>")
def forget_barcode(barcode):
    """Forget the remembered entry for one barcode."""
    cache = load_cache()
    existed = barcode in cache
    if existed:
        del cache[barcode]
        save_cache(cache)
    return jsonify(ok=True, removed=existed)


@app.post("/api/ofd/refresh")
def ofd_refresh():
    """Force a re-download/rebuild of the Open Filament Database index."""
    import ofd
    try:
        idx = ofd.get_index(force=True)
        return jsonify(ok=True, barcodes=len(idx), brands=len(ofd.get_brands()))
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 502


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
    """Resolve a barcode to filament fields: cache first, then the Open Filament Database."""
    barcode = (request.args.get("barcode") or "").strip()
    if not barcode:
        return jsonify(error="barcode required"), 400

    # 1. Personal cache — your own confirmed entries win.
    cache = load_cache()
    if barcode in cache:
        return jsonify(barcode=barcode, source="cache", fields=cache[barcode], title=None)

    # 2. Open Filament Database — filament-specific, keyed by spool barcode (GTIN).
    import ofd
    ofd_fields = ofd.lookup(barcode)
    if ofd_fields:
        fields = {k: v for k, v in ofd_fields.items() if not k.startswith("_")}
        fields.setdefault("label_weight", DEFAULT_LABEL_WEIGHT)
        return jsonify(barcode=barcode, source="ofd",
                       title=ofd_fields.get("_title"), fields=fields)

    # 3. Not found — fill in manually (and it'll be remembered).
    src = "amazon" if not barcode.isdigit() else "none"
    return jsonify(barcode=barcode, source=src,
                   fields={"label_weight": DEFAULT_LABEL_WEIGHT}, title=None)


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

    Heuristically parses the text, and if a barcode is present in it, looks that
    barcode up in the Open Filament Database — authoritative OFD data overrides
    the guesses when found.
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
    barcode = _extract_barcode(title)
    if barcode:
        ofd_fields = ofd.lookup(barcode)
        if ofd_fields:
            fields = {**fields, **{k: v for k, v in ofd_fields.items() if not k.startswith("_")}}
            source = "ofd"
            out_title = ofd_fields.get("_title") or title

    fields.setdefault("label_weight", DEFAULT_LABEL_WEIGHT)
    return jsonify(fields=fields, title=out_title, barcode=barcode, source=source)


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

    # Remember the confirmed details for this barcode (learning cache).
    if created and barcode:
        cache = load_cache()
        remembered = {k: v for k, v in fields.items()
                      if k in ALLOWED_SPOOL_FIELDS or k in ("diameter_mm",)}
        cache[barcode] = remembered
        save_cache(cache)

    ok = created == quantity
    return jsonify(ok=ok, created=created, requested=quantity,
                   errors=errors, bambuddy=BAMBUDDY_URL), (200 if created else 502)


if __name__ == "__main__":
    print(f"  Bambuddy: {BAMBUDDY_URL}  (API key {'set' if BAMBUDDY_API_KEY else 'NOT set'})")
    print(f"  Open on your phone:  http://<this-computer-ip>:{PORT}/")
    print("  ⚠️  Camera scanning needs https:// or localhost — see README.\n")
    app.run(host=HOST, port=PORT, debug=False)
