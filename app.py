#!/usr/bin/env python3
"""
filament_to_bambuddy — app.py

A small mobile web app: scan a third-party filament box barcode with your phone,
look up the product (online UPC database + a learning per-barcode cache), review
the auto-filled details, and add the spool to your Bambuddy inventory.

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

# UPC lookup provider. Default is UPCItemDB's keyless trial endpoint (rate
# limited: ~100/day). Set UPC_LOOKUP_URL + UPC_API_KEY to use another provider.
UPC_LOOKUP_URL = os.getenv("UPC_LOOKUP_URL", "https://api.upcitemdb.com/prod/trial/lookup")
UPC_API_KEY = os.getenv("UPC_API_KEY", "")

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


# ── UPC lookup ────────────────────────────────────────────────────────────────

def upc_lookup(barcode: str) -> dict | None:
    """Query the configured UPC provider; return {title, brand} or None."""
    try:
        headers = {"Accept": "application/json"}
        if UPC_API_KEY:
            headers["user_key"] = UPC_API_KEY  # UPCItemDB paid; harmless otherwise
        resp = requests.get(UPC_LOOKUP_URL, params={"upc": barcode}, headers=headers, timeout=15)
        if not resp.ok:
            return {"_error": f"UPC lookup returned {resp.status_code}"}
        data = resp.json()
        items = data.get("items") or data.get("products") or []
        if not items:
            return None
        item = items[0]
        return {
            "title": item.get("title") or item.get("name") or "",
            "brand": item.get("brand") or "",
        }
    except Exception as e:
        return {"_error": str(e)}


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
    """Resolve a barcode to filament fields: cache first, then UPC API + parse."""
    from filament_parse import parse_title

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

    # 3. Non-numeric (Amazon ASIN etc.) → UPC databases reject these; go manual.
    if not barcode.isdigit():
        return jsonify(barcode=barcode, source="amazon",
                       fields={"label_weight": DEFAULT_LABEL_WEIGHT}, title=None)

    # 4. Generic UPC database (coverage for filament is patchy).
    hit = upc_lookup(barcode)
    if hit and "_error" in hit:
        # Soft-fail: still let the user fill the form manually.
        return jsonify(barcode=barcode, source="error", error=hit["_error"],
                       fields={"label_weight": DEFAULT_LABEL_WEIGHT}, title=None)
    if not hit:
        return jsonify(barcode=barcode, source="none",
                       fields={"label_weight": DEFAULT_LABEL_WEIGHT}, title=None)

    fields = parse_title(hit.get("title", ""), brand_hint=hit.get("brand") or None)
    fields.setdefault("label_weight", DEFAULT_LABEL_WEIGHT)
    return jsonify(barcode=barcode, source="upc", title=hit.get("title", ""), fields=fields)


@app.get("/api/parse")
def parse_endpoint():
    """Parse a free-text product title into filament fields (the 'paste title' helper)."""
    from filament_parse import parse_title
    title = (request.args.get("title") or "").strip()
    if not title:
        return jsonify(fields={})
    fields = parse_title(title)
    return jsonify(fields=fields, title=title)


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
