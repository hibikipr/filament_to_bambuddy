# filament_to_bambuddy

[![Build and publish image](https://github.com/hibikipr/filament_to_bambuddy/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/hibikipr/filament_to_bambuddy/actions/workflows/docker-publish.yml)

Scan a third-party filament box barcode with your phone and add the new spool to
your [Bambuddy](https://github.com/) filament inventory.

It's a small mobile web app:

1. **Scan** the box's barcode (phone camera) — or type the number.
2. **Look up** the product, in order:
   1. your **per-barcode cache** (anything you've confirmed before),
   2. the **[Open Filament Database](https://openfilamentdatabase.org)** — a
      filament-specific database keyed by spool barcode (GTIN), giving brand,
      material, colour (+ hex), weight and print temps,
   3. otherwise a blank form, with a **paste-the-title** auto-fill helper.
   Or skip the barcode entirely and **📷 photograph the label** — on-device OCR
   reads the text and the same parser fills the form (works even over plain
   HTTP, unlike the live barcode camera).
3. **Review** the auto-filled details (correct anything).
4. **Add** the spool(s) to Bambuddy via its inventory API.

The lookup also **learns**: whatever you confirm is remembered for that barcode,
so the same product auto-fills instantly next time. *(Scope: new, unopened
spools still in the box.)*

> **Tested with** Bambuddy v0.2.4.8. Requires **Python 3.10+**.

---

## Setup

```bash
pip install -r requirements.txt
```

Then provide your Bambuddy details. The easiest way is a local **`run.sh`**
(gitignored, so your key never gets committed):

```bash
#!/bin/bash
export BAMBUDDY_URL="https://your-bambuddy.example.com"
export BAMBUDDY_API_KEY="your-bambuddy-api-key"
cd "$(dirname "$0")" && exec python3 app.py
```

```bash
chmod +x run.sh
./run.sh
```

…or just export the variables yourself and run `python3 app.py`. Then open
`http://<this-computer-ip>:8088/` on your phone (same network). On startup the
page shows a status line: 🟢 connected, 🟡 connected-but-permission-issue, or
🔴 unreachable — with the specific reason.

### Bambuddy API key permissions (important)

Create the key in **Bambuddy → Settings → API Keys** with these enabled:

- ✅ **Manage Inventory** — *required* (this is what creates spools)
- ✅ **Read Status** — so the app's connection check passes

Without **Manage Inventory** the add will fail with `403`; without **Read
Status** the status line shows an amber permission warning.

### Install it as an app (PWA)

The app is an installable **PWA** — add it to your phone's home screen for a
full-screen, app-like experience with its own icon:

- **Android (Chrome):** menu ⋮ → *Add to Home screen* / *Install app*.
- **iOS (Safari):** Share → *Add to Home Screen*.

Like the camera, the installable PWA (service worker / offline shell) needs a
**secure origin** (HTTPS or `localhost`) — see below.

### ⚠️ Camera access needs a secure origin

Phone browsers only allow camera access over **HTTPS** (or `localhost`). Opening
the app at `http://192.168.x.x:8088` will **not** grant the camera — but you can
always type the barcode number in the manual field, which works anywhere.

To enable the camera, serve the app over HTTPS, e.g.:
- behind a reverse proxy with TLS (Caddy / nginx / Cloudflare Tunnel), the same
  way Bambuddy itself is exposed, **or**
- a local HTTPS tunnel (e.g. `cloudflared`, `ngrok`).

### Run with Docker (in a stack)

A `Dockerfile` and `docker-compose.yml` are included. It runs under **gunicorn**
and persists its caches (`barcode_cache.json`, `ofd_index.json`) to a volume.

```bash
cp .env.example .env      # then edit .env with your BAMBUDDY_URL + API key
docker compose up -d --build
```

**Prebuilt image:** a GitHub Actions workflow publishes a multi-arch image
(amd64 + arm64) to **GHCR** on every push to `main` and on `v*` tags. Pull it
instead of building:

```yaml
    image: ghcr.io/hibikipr/filament_to_bambuddy:latest
```

(After the first publish, set the package's visibility to **Public** in your
GitHub package settings if you want to pull it without authenticating.)

The app is then on port **8088**. To add it to an existing stack, drop this
service into your compose (point `env_file` or `environment` at your config):

```yaml
  filament-to-bambuddy:
    build: ./filament_to_bambuddy      # or image: <your-built-image>
    restart: unless-stopped
    ports: ["8088:8088"]
    env_file: [./filament_to_bambuddy/.env]
    volumes: ["filament_data:/data"]
# (add `filament_data:` under your top-level `volumes:`)
```

For the **camera** and **PWA install** you still need HTTPS — route this
container through the same reverse proxy (Traefik / nginx / Caddy / Cloudflare
Tunnel) you use for Bambuddy, with its own hostname.

Docker-specific env vars: `OFD_CACHE_FILE` and `BARCODE_CACHE_FILE` default to
`/data/...` in the image so the caches land on the mounted volume.

### Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `BAMBUDDY_URL` | `http://localhost:8000` | Your Bambuddy base URL |
| `BAMBUDDY_API_KEY` | — | Bambuddy API key (**required**, needs *Manage Inventory*) |
| `DEFAULT_LABEL_WEIGHT` | `1000` | Net grams assumed when unknown |
| `BARCODE_CACHE_FILE` | `barcode_cache.json` | Where learned lookups are stored |
| `OFD_CACHE_FILE` | `ofd_index.json` | Where the OFD index is cached |
| `HOST` / `PORT` | `0.0.0.0` / `8088` | Server bind address |

The Open Filament Database dump is downloaded once and cached in
`ofd_index.json`, refreshed daily (or on demand via the **Refresh DB** button).

---

## How it maps to Bambuddy

Spools are created via `POST /api/v1/inventory/spools`. Only **`material`** is
required; the form also sends brand, subtype, colour name + RGBA, net weight,
storage location, category, nozzle temps, cost/kg and a note where available.
Each created spool is tagged `data_origin = "barcode-scan"`.

## Project layout

| File | Purpose |
|---|---|
| `app.py` | Flask backend: serves the page; `/api/lookup`, `/api/parse`, `/api/spool`, `/api/health`; the learning cache; posts to Bambuddy |
| `ofd.py` | Open Filament Database client — builds the barcode → fields index, cached/refreshed daily |
| `filament_parse.py` | Heuristics turning product/label text into filament fields (paste-title + label OCR) |
| `templates/index.html` | Mobile UI (barcode scan + manual entry + editable form), Bambuddy dark/green theme |
| `static/manifest.webmanifest`, `static/sw.js`, `static/icons/` | PWA manifest, service worker, and app icons |

Not in the repo (gitignored): `run.sh` (your secrets), `barcode_cache.json`
(your learned lookups), `ofd_index.json` (downloaded database cache).

---

## License

Licensed under the **GNU Affero General Public License v3.0 or later**
(AGPL-3.0-or-later), matching Bambuddy. See [LICENSE](LICENSE).

Copyright © 2026 Victor Manuel ([hibikipr](https://github.com/hibikipr)).

---

🤖 Built with [Claude Code](https://claude.com/claude-code)
