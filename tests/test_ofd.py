"""Unit tests for ofd.py — Open Filament Database client.

Tests:
- _canon() barcode canonicalization (leading-zero stripping)
- _build_index() joins brands/filaments/variants/sizes correctly, including
  the article_number (SKU)/spool_refill fields and variant-code grouping
- get_gtin_index()/get_article_index()/lookup()/lookup_article() disk-cache
  TTL behavior (fresh cache used, stale triggers refresh, old cache-version
  shape triggers refresh)

Mirrors bambuddy's backend/tests/unit/test_ofd_client.py test data so the two
implementations can be sanity-checked against the same expected outputs.
"""

import json
import time
from unittest.mock import patch

import pytest

import ofd


class TestCanon:
    def test_strips_leading_zeros(self):
        assert ofd._canon("0012345678905") == "12345678905"

    def test_strips_non_digits(self):
        assert ofd._canon("012-345-678-905") == "12345678905"

    def test_upc_a_and_ean_13_forms_match(self):
        upc_a = "012345678905"
        ean_13 = "0012345678905"
        assert ofd._canon(upc_a) == ofd._canon(ean_13)

    def test_all_zeros_returns_zero(self):
        assert ofd._canon("0000") == "0"

    def test_empty_string(self):
        assert ofd._canon("") == "0"


SAMPLE_ALL_JSON = {
    "brands": [{"id": 1, "name": "Sunlu"}],
    "filaments": [
        {
            "id": 10,
            "brand_id": 1,
            "name": "PLA+",
            "material": "PLA",
            "min_print_temperature": 190,
            "max_print_temperature": 230,
        }
    ],
    "variants": [{"id": 100, "filament_id": 10, "name": "Black", "color_hex": "#000000"}],
    "sizes": [{"gtin": "06938936716785", "variant_id": 100, "filament_weight": 1000}],
}


class TestBuildIndex:
    def test_joins_brand_filament_variant_size(self):
        gtin_index, article_index, variant_codes = ofd._build_index(SAMPLE_ALL_JSON)
        canonical = ofd._canon("06938936716785")
        assert canonical in gtin_index
        fields = gtin_index[canonical]["fields"]
        assert fields["material"] == "PLA"
        assert fields["brand"] == "Sunlu"
        assert fields["color_name"] == "Black"
        assert fields["rgba"] == "000000FF"
        assert fields["label_weight"] == 1000
        assert fields["nozzle_temp_min"] == 190
        assert fields["nozzle_temp_max"] == 230
        assert article_index == {}
        assert variant_codes["100"] == [{"code": canonical, "kind": "gtin", "is_refill": False}]

    def test_missing_gtin_and_article_skipped(self):
        broken = {**SAMPLE_ALL_JSON, "sizes": [{"variant_id": 100, "filament_weight": 1000}]}
        gtin_index, article_index, variant_codes = ofd._build_index(broken)
        assert gtin_index == {}
        assert article_index == {}
        assert variant_codes == {}

    def test_orphaned_variant_skipped(self):
        broken = {**SAMPLE_ALL_JSON, "variants": []}
        gtin_index, article_index, variant_codes = ofd._build_index(broken)
        assert gtin_index == {}

    def test_upc_a_and_ean_13_gtin_produce_same_key(self):
        variant_a = {**SAMPLE_ALL_JSON, "sizes": [{"gtin": "6938936716785", "variant_id": 100, "filament_weight": 1000}]}
        variant_b = {**SAMPLE_ALL_JSON, "sizes": [{"gtin": "06938936716785", "variant_id": 100, "filament_weight": 1000}]}
        gtin_index_a, _, _ = ofd._build_index(variant_a)
        gtin_index_b, _, _ = ofd._build_index(variant_b)
        assert list(gtin_index_a.keys()) == list(gtin_index_b.keys())

    def test_article_number_indexed_and_normalized(self):
        data = {
            **SAMPLE_ALL_JSON,
            "sizes": [{"article_number": " alzmntabs01 ", "variant_id": 100, "filament_weight": 1000}],
        }
        gtin_index, article_index, variant_codes = ofd._build_index(data)
        assert gtin_index == {}
        assert "ALZMNTABS01" in article_index
        assert article_index["ALZMNTABS01"]["fields"]["material"] == "PLA"
        assert variant_codes["100"] == [{"code": "ALZMNTABS01", "kind": "sku", "is_refill": False}]

    def test_gtin_and_article_on_same_size_are_both_siblings(self):
        data = {
            **SAMPLE_ALL_JSON,
            "sizes": [
                {
                    "gtin": "06938936716785",
                    "article_number": "ALZMNTABS01",
                    "variant_id": 100,
                    "filament_weight": 1000,
                }
            ],
        }
        gtin_index, article_index, variant_codes = ofd._build_index(data)
        canonical = ofd._canon("06938936716785")
        assert canonical in gtin_index
        assert "ALZMNTABS01" in article_index
        codes = variant_codes["100"]
        assert {"code": canonical, "kind": "gtin", "is_refill": False} in codes
        assert {"code": "ALZMNTABS01", "kind": "sku", "is_refill": False} in codes

    def test_multiple_sizes_share_variant_codes_and_keep_per_size_fields(self):
        """Different package sizes of the same colour share a variant_id — the
        code list must include every sibling, but each code's own `fields`
        (e.g. label_weight) stays specific to the size it came from."""
        data = {
            **SAMPLE_ALL_JSON,
            "sizes": [
                {"gtin": "06938936716785", "variant_id": 100, "filament_weight": 1000},
                {
                    "gtin": "06938936716786",
                    "article_number": "ALZMNTABS01",
                    "variant_id": 100,
                    "filament_weight": 250,
                    "spool_refill": True,
                },
            ],
        }
        gtin_index, article_index, variant_codes = ofd._build_index(data)
        big = ofd._canon("06938936716785")
        small = ofd._canon("06938936716786")
        assert gtin_index[big]["fields"]["label_weight"] == 1000
        assert gtin_index[small]["fields"]["label_weight"] == 250
        codes = variant_codes["100"]
        assert {"code": big, "kind": "gtin", "is_refill": False} in codes
        assert {"code": small, "kind": "gtin", "is_refill": True} in codes
        assert {"code": "ALZMNTABS01", "kind": "sku", "is_refill": True} in codes


class TestCachingAndLookup:
    @pytest.fixture(autouse=True)
    def _reset_module_cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ofd, "_GTIN_INDEX", None)
        monkeypatch.setattr(ofd, "_ARTICLE_INDEX", None)
        monkeypatch.setattr(ofd, "_VARIANT_CODES", None)
        monkeypatch.setattr(ofd, "_BRANDS", None)
        monkeypatch.setattr(ofd, "_INDEX_LOADED_AT", 0.0)
        monkeypatch.setattr(ofd, "OFD_CACHE", tmp_path / "ofd_cache.json")
        yield

    def _write_cache(self, tmp_path, gtin_index, article_index, variant_codes, brands, built_at=None, version=None):
        cache_file = tmp_path / "ofd_cache.json"
        cache_file.write_text(
            json.dumps(
                {
                    "cache_version": ofd._CACHE_VERSION if version is None else version,
                    "built_at": time.time() if built_at is None else built_at,
                    "gtin_index": gtin_index,
                    "article_index": article_index,
                    "variant_codes": variant_codes,
                    "brands": brands,
                }
            )
        )

    def test_fresh_disk_cache_used_without_network_call(self, tmp_path):
        gtin_index, article_index, variant_codes = ofd._build_index(SAMPLE_ALL_JSON)
        self._write_cache(tmp_path, gtin_index, article_index, variant_codes, ["Sunlu"])

        with patch("ofd._refresh") as mock_refresh:
            result = ofd.get_gtin_index()
            mock_refresh.assert_not_called()
        assert ofd._canon("06938936716785") in result

    def test_stale_disk_cache_triggers_refresh(self, tmp_path):
        stale_time = time.time() - ofd.OFD_TTL_SECONDS - 10
        self._write_cache(tmp_path, {}, {}, {}, [], built_at=stale_time)

        gtin_index, article_index, variant_codes = ofd._build_index(SAMPLE_ALL_JSON)
        with patch(
            "ofd._refresh",
            return_value=(gtin_index, article_index, variant_codes, ["Sunlu"]),
        ) as mock_refresh:
            result = ofd.get_gtin_index()
            mock_refresh.assert_called_once()
        assert ofd._canon("06938936716785") in result

    def test_old_cache_version_triggers_refresh(self, tmp_path):
        """A cache file predating article_number/variant-code support must not be misread."""
        self._write_cache(tmp_path, {}, {}, {}, [], version=1)

        gtin_index, article_index, variant_codes = ofd._build_index(SAMPLE_ALL_JSON)
        with patch(
            "ofd._refresh",
            return_value=(gtin_index, article_index, variant_codes, ["Sunlu"]),
        ) as mock_refresh:
            result = ofd.get_gtin_index()
            mock_refresh.assert_called_once()
        assert ofd._canon("06938936716785") in result

    def test_lookup_returns_none_for_unknown_barcode(self, tmp_path):
        gtin_index, article_index, variant_codes = ofd._build_index(SAMPLE_ALL_JSON)
        self._write_cache(tmp_path, gtin_index, article_index, variant_codes, ["Sunlu"])
        assert ofd.lookup("0000000000000") is None

    def test_lookup_returns_fields_and_codes_for_known_barcode(self, tmp_path):
        gtin_index, article_index, variant_codes = ofd._build_index(SAMPLE_ALL_JSON)
        self._write_cache(tmp_path, gtin_index, article_index, variant_codes, ["Sunlu"])

        result = ofd.lookup("6938936716785")
        assert result is not None
        fields, codes = result
        assert fields["brand"] == "Sunlu"
        assert codes == [{"code": ofd._canon("6938936716785"), "kind": "gtin", "is_refill": False}]

    def test_lookup_article_returns_fields_and_codes(self, tmp_path):
        data = {
            **SAMPLE_ALL_JSON,
            "sizes": [
                {"gtin": "06938936716785", "article_number": "ALZMNTABS01", "variant_id": 100, "filament_weight": 1000}
            ],
        }
        gtin_index, article_index, variant_codes = ofd._build_index(data)
        self._write_cache(tmp_path, gtin_index, article_index, variant_codes, ["Sunlu"])

        result = ofd.lookup_article("alzmntabs01")
        assert result is not None
        fields, codes = result
        assert fields["brand"] == "Sunlu"
        assert any(c["kind"] == "gtin" for c in codes)
        assert any(c["kind"] == "sku" for c in codes)

    def test_lookup_article_returns_none_for_unknown_code(self, tmp_path):
        gtin_index, article_index, variant_codes = ofd._build_index(SAMPLE_ALL_JSON)
        self._write_cache(tmp_path, gtin_index, article_index, variant_codes, ["Sunlu"])
        assert ofd.lookup_article("NOPE") is None
