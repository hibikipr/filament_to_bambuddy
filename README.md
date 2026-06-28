# filament_to_bambuddy

Scan a third-party filament box barcode with your phone and add the new spool to
your [Bambuddy](https://github.com/) filament inventory.

It's a small mobile web app:

1. **Scan** the box's barcode (phone camera) — or type the number.
2. **Look up** the product: a per-barcode cache first, then an online UPC
   database, parsing brand / material / colour / weight from the product title.
3. **Review** the auto-filled details (correct anything).
4. **Add** the spool(s) to Bambuddy via its inventory API.

The lookup is a **learning hybrid**: whatever you confirm is remembered for that
barcode, so the same product auto-fills instantly next time — and gets more
accurate the more you scan. *(Scope: new, unopened spools still in the box.)*

> **Tested with** Bambuddy v0.2.4.8. Requires **Python 3.10+**.

---

## Setup

```bash
pip install -r requirements.txt

export BAMBUDDY_URL="https://your-bambuddy.example.com"
export BAMBUDDY_API_KEY="your-bambuddy-api-key"
python app.py
```

Then open `http://<this-computer-ip>:8088/` on your phone (same network).

### ⚠️ Camera access needs a secure origin

Phone browsers only allow camera access over **HTTPS** (or `localhost`). Opening
the app at `http://192.168.x.x:8088` will **not** grant the camera — but you can
still type the barcode number in the manual field, which works anywhere.

To enable the camera, serve the app over HTTPS, e.g.:
- put it behind a reverse proxy with TLS (Caddy/nginx/Cloudflare Tunnel), the
  same way Bambuddy itself is exposed, **or**
- run a local HTTPS tunnel (e.g. `cloudflared`, `ngrok`).

### Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `BAMBUDDY_URL` | `http://localhost:8000` | Your Bambuddy base URL |
| `BAMBUDDY_API_KEY` | — | Bambuddy API key (**required**) |
| `UPC_LOOKUP_URL` | UPCItemDB trial | UPC lookup endpoint |
| `UPC_API_KEY` | — | Key for a paid UPC provider (optional) |
| `DEFAULT_LABEL_WEIGHT` | `1000` | Net grams assumed when unknown |
| `BARCODE_CACHE_FILE` | `barcode_cache.json` | Where learned lookups are stored |
| `HOST` / `PORT` | `0.0.0.0` / `8088` | Server bind address |

The default UPC provider is **UPCItemDB's keyless trial** endpoint (rate-limited,
~100 lookups/day). For heavier use, sign up for a provider and set
`UPC_LOOKUP_URL` + `UPC_API_KEY`. Filament coverage in generic UPC databases is
inconsistent — that's exactly why the per-barcode cache exists.

---

## How it maps to Bambuddy

Spools are created via `POST /api/v1/inventory/spools`. Only **`material`** is
required; the form also sends brand, subtype, colour name + RGBA, net weight,
storage location, category, nozzle temps, cost/kg and a note where available.
Each created spool is tagged `data_origin = "barcode-scan"`.

---

## License

Licensed under the **GNU Affero General Public License v3.0 or later**
(AGPL-3.0-or-later), matching Bambuddy. See [LICENSE](LICENSE).

Copyright © 2026 Victor Manuel ([hibikipr](https://github.com/hibikipr)).

---

🤖 Built with [Claude Code](https://claude.com/claude-code)
