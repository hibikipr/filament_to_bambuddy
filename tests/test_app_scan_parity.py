"""App-level tests for the scan-to-add parity work (issue #28): lookup
failures vs misses, Amazon FNSKU stickers, trying every code on a label, and
following Bambuddy's Spoolman mode when adding spools."""

from unittest.mock import MagicMock, patch

import pytest

import app

HIT_FIELDS = {
    "material": "Nylon", "brand": "Polymaker", "subtype": "PolyLite Pro",
    "color_name": "PolyLite PLA Pro Blue", "rgba": "0050FFFF", "label_weight": 3000,
    "nozzle_temp_min": None, "nozzle_temp_max": None, "_title": "Polymaker PolyLite Blue",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "CACHE_FILE", tmp_path / "cache.json")
    app.app.config["TESTING"] = True
    return app.app.test_client()


def _miss(*_a, **_k):
    return None


def _boom(*_a, **_k):
    raise RuntimeError("index download failed")


class TestLookupErrors:
    def test_both_databases_unreachable_is_an_error_not_a_miss(self, client):
        with patch("ofd.lookup", _boom), patch("spoolmandb_community.lookup", _boom):
            d = client.get("/api/lookup?barcode=6938936716785").get_json()
        assert d["source"] == "error"
        assert d["lookup_error"] is True

    def test_one_database_unreachable_and_other_misses_is_not_found(self, client):
        with patch("ofd.lookup", _boom), patch("spoolmandb_community.lookup", _miss):
            d = client.get("/api/lookup?barcode=6938936716785").get_json()
        assert d["source"] == "none"

    def test_unknown_sku_is_not_found_not_amazon(self, client):
        with patch("ofd.lookup_article", _miss), patch("spoolmandb_community.lookup_sku", _miss):
            d = client.get("/api/lookup?barcode=ABC12345").get_json()
        assert d["source"] == "none"

    def test_amazon_fnsku_is_not_looked_up(self, client):
        ofd_lookup = MagicMock()
        with patch("ofd.lookup_article", ofd_lookup), patch("spoolmandb_community.lookup_sku", ofd_lookup):
            d = client.get("/api/lookup?barcode=X004AR68I3").get_json()
        assert d["source"] == "fnsku"
        ofd_lookup.assert_not_called()

    def test_hit_material_is_bambuddy_spelling(self, client):
        with patch("ofd.lookup", lambda *_a, **_k: (dict(HIT_FIELDS), [])), \
                patch("spoolmandb_community.lookup", _miss):
            d = client.get("/api/lookup?barcode=6938936716785").get_json()
        assert d["source"] == "ofd"
        assert d["fields"]["material"] == "PA"


class TestParseLabelPhoto:
    def test_skips_fnsku_and_unknown_codes_then_hits_the_sku(self, client):
        seen = []

        def sku_lookup(code, strict=False):
            seen.append(code)
            return (dict(HIT_FIELDS), [{"code": "PM70820", "kind": "sku", "is_refill": False}]) \
                if code == "PM70820" else None

        body = {"text": "PolyLite PLA Pro\nCOLOR: Blue\nSKU:\nPM70820\nNet weight 1kg",
                "barcodes": ["X004AR68I3"]}
        with patch("ofd.lookup", _miss), patch("ofd.lookup_article", _miss), \
                patch("spoolmandb_community.lookup", _miss), \
                patch("spoolmandb_community.lookup_sku", sku_lookup), \
                patch("ofd.get_brands", list):
            d = client.post("/api/parse", json=body).get_json()
        assert "X004AR68I3" not in seen
        assert d["source"] == "spoolmandb-community"
        f = d["fields"]
        # The box's printed weight beats the database's (one code, several sizes).
        assert f["label_weight"] == 1000
        # COLOR: field splits the database's product-line+colour name.
        assert f["color_name"] == "Blue"
        assert f["material"] == "PA"

    def test_decoded_barcode_from_photo_is_tried_first(self, client):
        seen = []

        def gtin_lookup(code, strict=False):
            seen.append(code)

        with patch("ofd.lookup", gtin_lookup), patch("ofd.lookup_article", _miss), \
                patch("spoolmandb_community.lookup", _miss), \
                patch("spoolmandb_community.lookup_sku", _miss), \
                patch("ofd.get_brands", list):
            d = client.post("/api/parse", json={"text": "EAN 6938936716785",
                                                "barcodes": ["012345678905"]}).get_json()
        assert seen[0] == "12345678905"
        assert d["source"] == "parsed"
        assert d["barcode"] == "12345678905"

    def test_unreachable_databases_reported(self, client):
        with patch("ofd.lookup", _boom), patch("ofd.lookup_article", _boom), \
                patch("spoolmandb_community.lookup", _boom), \
                patch("spoolmandb_community.lookup_sku", _boom), \
                patch("ofd.get_brands", list):
            d = client.post("/api/parse", json={"text": "PLA Black EAN 6938936716785"}).get_json()
        assert d["lookup_error"] is True
        assert d["fields"]["material"] == "PLA"

    def test_get_title_still_works(self, client):
        with patch("ofd.get_brands", list):
            d = client.get("/api/parse?title=Silk PLA Gold 1kg").get_json()
        assert d["fields"]["effect_type"] == "silk"


def _resp(status, payload=None):
    r = MagicMock()
    r.status_code = status
    r.ok = 200 <= status < 300
    r.json.return_value = payload if payload is not None else {}
    r.text = ""
    return r


class TestInventoryBackend:
    @pytest.fixture(autouse=True)
    def _key(self, monkeypatch):
        monkeypatch.setattr(app, "BAMBUDDY_API_KEY", "k")
        monkeypatch.setattr(app, "_last_inventory_backend", app.INVENTORY_BUILTIN)

    def test_status_enabled_means_spoolman(self):
        with patch("requests.get", return_value=_resp(200, {"enabled": True, "connected": True})):
            assert app._inventory_backend() == app.INVENTORY_SPOOLMAN

    def test_status_disabled_means_builtin(self):
        with patch("requests.get", return_value=_resp(200, {"enabled": False, "connected": False})):
            assert app._inventory_backend() == app.INVENTORY_BUILTIN

    def test_key_without_filaments_read_probes_the_proxy(self):
        with patch("requests.get", side_effect=[_resp(403), _resp(200, [])]):
            assert app._inventory_backend() == app.INVENTORY_SPOOLMAN
        with patch("requests.get", side_effect=[_resp(403), _resp(400)]):
            assert app._inventory_backend() == app.INVENTORY_BUILTIN

    def test_blip_keeps_last_known_mode(self, monkeypatch):
        monkeypatch.setattr(app, "_last_inventory_backend", app.INVENTORY_SPOOLMAN)
        with patch("requests.get", side_effect=ConnectionError("down")):
            assert app._inventory_backend() == app.INVENTORY_SPOOLMAN
        with patch("requests.get", return_value=_resp(503)):
            assert app._inventory_backend() == app.INVENTORY_SPOOLMAN


FIELDS = {
    "material": "Nylon", "brand": "eSUN", "color_name": "Black", "rgba": "000000FF",
    "effect_type": "Dual Color", "extra_colors": "000000,FFFFFF",
    "nozzle_temp_min": "250", "nozzle_temp_max": "270", "category": "Eng",
    "label_weight": "1000",
}


class TestAddSpool:
    @pytest.fixture(autouse=True)
    def _key(self, monkeypatch):
        monkeypatch.setattr(app, "BAMBUDDY_API_KEY", "k")

    def _post(self, client, mode):
        with patch.object(app, "_inventory_backend", return_value=mode), \
                patch("requests.post", return_value=_resp(201, {})) as post, \
                patch("ofd.lookup", _miss), patch("spoolmandb_community.lookup", _miss):
            r = client.post("/api/spool", json={"barcode": "", "quantity": 1, "fields": dict(FIELDS)})
        return r, post.call_args

    def test_builtin_posts_everything_to_inventory(self, client):
        r, call = self._post(client, app.INVENTORY_BUILTIN)
        assert r.status_code == 200
        assert call.args[0].endswith("/api/v1/inventory/spools")
        payload = call.kwargs["json"]
        assert payload["material"] == "PA"
        assert payload["effect_type"] == "dual-color"
        assert payload["extra_colors"] == "000000,FFFFFF"
        assert payload["nozzle_temp_min"] == 250
        assert payload["data_origin"] == "barcode-scan"

    def test_spoolman_posts_to_proxy_without_unsupported_fields(self, client):
        r, call = self._post(client, app.INVENTORY_SPOOLMAN)
        assert r.status_code == 200
        assert call.args[0].endswith("/api/v1/spoolman/inventory/spools")
        payload = call.kwargs["json"]
        for key in ("extra_colors", "effect_type", "nozzle_temp_min", "nozzle_temp_max",
                    "category", "data_origin"):
            assert key not in payload
        assert payload["material"] == "PA"
        assert payload["color_name"] == "Black"


def test_bad_extra_colour_tokens_are_dropped(client, monkeypatch):
    monkeypatch.setattr(app, "BAMBUDDY_API_KEY", "k")
    fields = {"material": "PLA", "extra_colors": "#ff0000, nope, 00FF00,12"}
    with patch.object(app, "_inventory_backend", return_value=app.INVENTORY_BUILTIN), \
            patch("requests.post", return_value=_resp(201, {})) as post:
        client.post("/api/spool", json={"barcode": "", "fields": fields})
    assert post.call_args.kwargs["json"]["extra_colors"] == "FF0000,00FF00"
