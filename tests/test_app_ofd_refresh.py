"""Tests for POST /api/ofd/refresh — the combined OFD + SpoolmanDB-Community
force-refresh endpoint.

Each refresh must be independently guarded: an OFD network blip must not
take the whole endpoint down (previously it returned 502 immediately and
never even attempted the SpoolmanDB-Community refresh) or discard a
SpoolmanDB-Community refresh that already succeeded.
"""

from unittest.mock import MagicMock, patch

import pytest

import app as app_module


@pytest.fixture
def client():
    app_module.app.testing = True
    return app_module.app.test_client()


class TestOfdRefreshEndpoint:
    def test_both_succeed_sums_entries(self, client):
        with (
            patch("ofd.get_gtin_index", return_value={"a": 1}),
            patch("ofd.get_article_index", return_value={"b": 1}),
            patch("ofd.get_brands", return_value=["Sunlu"]),
            patch("spoolmandb_community.get_gtin_index", return_value={"c": 1}),
            patch("spoolmandb_community.get_sku_index", return_value={"d": 1}),
        ):
            resp = client.post("/api/ofd/refresh")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"ok": True, "barcodes": 2, "brands": 1, "spoolmandb_community_barcodes": 2}

    def test_ofd_failure_degrades_and_still_refreshes_spoolmandb(self, client):
        with (
            patch("ofd.get_gtin_index", side_effect=RuntimeError("network blip")),
            patch("spoolmandb_community.get_gtin_index", return_value={"c": 1}),
            patch("spoolmandb_community.get_sku_index", return_value={"d": 1}),
        ):
            resp = client.post("/api/ofd/refresh")

        # Must still succeed (not 502) and must have attempted the
        # SpoolmanDB-Community refresh despite the OFD failure.
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["barcodes"] == 0
        assert data["brands"] == 0
        assert data["spoolmandb_community_barcodes"] == 2

    def test_spoolmandb_failure_degrades_and_keeps_ofd_count(self, client):
        with (
            patch("ofd.get_gtin_index", return_value={"a": 1}),
            patch("ofd.get_article_index", return_value={"b": 1}),
            patch("ofd.get_brands", return_value=["Sunlu"]),
            patch("spoolmandb_community.get_gtin_index", side_effect=RuntimeError("network blip")),
        ):
            resp = client.post("/api/ofd/refresh")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["barcodes"] == 2
        assert data["brands"] == 1
        assert data["spoolmandb_community_barcodes"] == 0
