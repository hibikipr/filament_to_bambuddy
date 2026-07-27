"""Unit tests for spoolmandb_community.py — SpoolmanDB-Community filament database client.

Tests:
- _canon() barcode canonicalization (shared algorithm, duplicated from ofd.py)
- _subtype_from_template() literal {color_name} placeholder removal
- _parse_manufacturer_file() / _build_index() expand raw source files into
  GTIN + SKU indexes correctly (eans + eans_refill + codes, multi-color
  hexes, temp ranges, all_codes grouping)
- get_gtin_index()/get_sku_index()/lookup()/lookup_sku() disk-cache TTL
  behavior (fresh cache used, stale triggers refresh, old cache-version
  shape triggers refresh)

Mirrors bambuddy's backend/tests/unit/test_spoolmandb_community_client.py test
data so the two implementations can be sanity-checked against the same
expected outputs.
"""

import io
import json
import tarfile
import time
from unittest.mock import patch

import pytest

import spoolmandb_community as smdb


class TestCanon:
    def test_strips_leading_zeros(self):
        assert smdb._canon("0012345678905") == "12345678905"

    def test_strips_non_digits(self):
        assert smdb._canon("012-345-678-905") == "12345678905"

    def test_upc_a_and_ean_13_forms_match(self):
        assert smdb._canon("012345678905") == smdb._canon("0012345678905")

    def test_all_zeros_returns_zero(self):
        assert smdb._canon("0000") == "0"

    def test_empty_string(self):
        assert smdb._canon("") == "0"


class TestSubtypeFromTemplate:
    def test_placeholder_at_end(self):
        assert smdb._subtype_from_template("PLA Basic {color_name}") == "PLA Basic"

    def test_placeholder_at_start(self):
        assert smdb._subtype_from_template("{color_name} PLA Basic") == "PLA Basic"

    def test_placeholder_in_middle(self):
        assert smdb._subtype_from_template("Matte {color_name} PLA") == "Matte PLA"

    def test_no_placeholder_present(self):
        assert smdb._subtype_from_template("PLA Basic") == "PLA Basic"

    def test_empty_string_returns_none(self):
        assert smdb._subtype_from_template("") is None

    def test_placeholder_only_returns_none(self):
        assert smdb._subtype_from_template("{color_name}") is None


SAMPLE_MANUFACTURER_FILE = {
    "manufacturer": "Bambu Lab",
    "filaments": [
        {
            "name": "Matte {color_name} PLA",
            "material": "PLA",
            "density": 1.24,
            "weights": [{"weight": 1000, "spool_weight": 250, "spool_type": "plastic"}],
            "diameters": [1.75],
            "extruder_temp_range": [220, 240],
            "colors": [
                {"name": "Ivory White", "hex": "FFFFFF", "eans": ["6975337031345"], "codes": ["CA19001"]},
                {"name": "Desert Tan", "hex": "C19A6B", "eans_refill": ["6975337035053"]},
                {"name": "No Barcode Blue", "hex": "0000FF"},
            ],
        },
        {
            "name": "{color_name} Dual PLA",
            "material": "PLA",
            "density": 1.24,
            "weights": [{"weight": 1000}],
            "diameters": [1.75],
            "colors": [
                {
                    "name": "Black/White",
                    "hexes": ["000000", "FFFFFF"],
                    "multi_color_direction": "coaxial",
                    "eans": ["1234567890128"],
                }
            ],
        },
    ],
}


class TestParseManufacturerFile:
    def test_expands_one_variant_per_color(self):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        assert len(variants) == 4

    def test_maps_fields_for_eans_color(self):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        v = next(v for v in variants if v["color_name"] == "Ivory White")
        assert v["brand"] == "Bambu Lab"
        assert v["material"] == "PLA"
        assert v["subtype"] == "Matte PLA"
        assert v["rgba"] == "FFFFFFFF"
        assert v["label_weight"] == 1000
        assert v["nozzle_temp_min"] == 220
        assert v["nozzle_temp_max"] == 240
        assert v["eans"] == ["6975337031345"]
        assert v["codes"] == ["CA19001"]

    def test_eans_refill_present(self):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        v = next(v for v in variants if v["color_name"] == "Desert Tan")
        assert v["eans_refill"] == ["6975337035053"]
        assert v["eans"] == []
        assert v["codes"] == []

    def test_color_without_barcode_still_expanded(self):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        v = next(v for v in variants if v["color_name"] == "No Barcode Blue")
        assert v["eans"] == []
        assert v["rgba"] == "0000FFFF"

    def test_multi_color_hexes(self):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        v = next(v for v in variants if v["color_name"] == "Black/White")
        assert v["hexes"] == ["000000", "FFFFFF"]
        assert v["rgba"] == "000000FF"


class TestAllCodesFor:
    def test_gathers_gtin_refill_and_sku(self):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        v = next(v for v in variants if v["color_name"] == "Ivory White")
        codes = smdb._all_codes_for(v)
        assert {"code": "6975337031345", "kind": "gtin", "is_refill": False} in codes
        assert {"code": "CA19001", "kind": "sku", "is_refill": False} in codes

    def test_refill_flagged(self):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        v = next(v for v in variants if v["color_name"] == "Desert Tan")
        codes = smdb._all_codes_for(v)
        assert codes == [{"code": "6975337035053", "kind": "gtin", "is_refill": True}]

    def test_no_codes_returns_empty(self):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        v = next(v for v in variants if v["color_name"] == "No Barcode Blue")
        assert smdb._all_codes_for(v) == []

    def test_non_string_ean_is_skipped_not_raised(self):
        """Covers the review finding (ported from bambuddy): a single malformed
        upstream EAN serialized as a number would otherwise raise TypeError in
        _canon() and abort the whole refresh for every manufacturer."""
        variant = {"eans": [6975337031345, "6975337031346"], "eans_refill": [None], "codes": []}
        codes = smdb._all_codes_for(variant)
        assert codes == [{"code": "6975337031346", "kind": "gtin", "is_refill": False}]

    def test_non_string_sku_is_skipped_not_raised(self):
        variant = {"eans": [], "eans_refill": [], "codes": [12345, "CA19001"]}
        codes = smdb._all_codes_for(variant)
        assert codes == [{"code": "CA19001", "kind": "sku", "is_refill": False}]


class TestBuildIndex:
    def test_indexes_eans_and_eans_refill(self):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        gtin_index, _sku_index = smdb._build_index(variants)
        assert smdb._canon("6975337031345") in gtin_index
        assert smdb._canon("6975337035053") in gtin_index
        assert smdb._canon("1234567890128") in gtin_index
        assert len(gtin_index) == 3

    def test_indexes_codes_as_sku(self):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        _gtin_index, sku_index = smdb._build_index(variants)
        assert "CA19001" in sku_index
        assert sku_index["CA19001"]["fields"]["color_name"] == "Ivory White"

    def test_gtin_and_sku_share_entry_for_cross_referencing(self):
        """A GTIN hit and a SKU hit on the same variant must share the same
        all_codes bundle, so resolving either recovers the other."""
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        gtin_index, sku_index = smdb._build_index(variants)
        gtin_entry = gtin_index[smdb._canon("6975337031345")]
        sku_entry = sku_index["CA19001"]
        assert gtin_entry is sku_entry

    def test_indexed_fields_match_barcode_field_keys(self):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        gtin_index, _ = smdb._build_index(variants)
        fields = gtin_index[smdb._canon("6975337031345")]["fields"]
        assert set(fields.keys()) == set(smdb._BARCODE_FIELD_KEYS)
        assert fields["brand"] == "Bambu Lab"
        assert fields["color_name"] == "Ivory White"
        assert fields["_title"] == "Bambu Lab Matte PLA Ivory White"


class TestCachingAndLookup:
    @pytest.fixture(autouse=True)
    def _reset_module_cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr(smdb, "_GTIN_INDEX", None)
        monkeypatch.setattr(smdb, "_SKU_INDEX", None)
        monkeypatch.setattr(smdb, "_BRANDS", None)
        monkeypatch.setattr(smdb, "_VARIANTS", None)
        monkeypatch.setattr(smdb, "_INDEX_LOADED_AT", 0.0)
        monkeypatch.setattr(smdb, "SPOOLMANDB_COMMUNITY_CACHE", tmp_path / "spoolmandb_community_index.json")
        yield

    def _write_cache(self, tmp_path, gtin_index, sku_index, brands, variants, built_at=None, version=None):
        cache_file = tmp_path / "spoolmandb_community_index.json"
        cache_file.write_text(
            json.dumps(
                {
                    "cache_version": smdb._CACHE_VERSION if version is None else version,
                    "built_at": time.time() if built_at is None else built_at,
                    "gtin_index": gtin_index,
                    "sku_index": sku_index,
                    "brands": brands,
                    "variants": variants,
                }
            )
        )

    def test_fresh_disk_cache_used_without_network_call(self, tmp_path):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        gtin_index, sku_index = smdb._build_index(variants)
        self._write_cache(tmp_path, gtin_index, sku_index, ["Bambu Lab"], variants)

        with patch("spoolmandb_community._refresh") as mock_refresh:
            result = smdb.get_gtin_index()
            mock_refresh.assert_not_called()
        assert smdb._canon("6975337031345") in result

    def test_stale_disk_cache_triggers_refresh(self, tmp_path):
        stale_time = time.time() - smdb.SPOOLMANDB_COMMUNITY_TTL_SECONDS - 10
        self._write_cache(tmp_path, {}, {}, [], [], built_at=stale_time)

        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        gtin_index, sku_index = smdb._build_index(variants)
        with patch(
            "spoolmandb_community._refresh",
            return_value=(gtin_index, sku_index, ["Bambu Lab"], variants),
        ) as mock_refresh:
            result = smdb.get_gtin_index()
            mock_refresh.assert_called_once()
        assert smdb._canon("6975337031345") in result

    def test_old_cache_version_triggers_refresh(self, tmp_path):
        """A cache file predating codes/SKU support must not be misread."""
        self._write_cache(tmp_path, {}, {}, [], [], version=1)

        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        gtin_index, sku_index = smdb._build_index(variants)
        with patch(
            "spoolmandb_community._refresh",
            return_value=(gtin_index, sku_index, ["Bambu Lab"], variants),
        ) as mock_refresh:
            result = smdb.get_gtin_index()
            mock_refresh.assert_called_once()
        assert smdb._canon("6975337031345") in result

    def test_missing_variants_key_treated_as_stale(self, tmp_path):
        cache_file = tmp_path / "spoolmandb_community_index.json"
        cache_file.write_text(
            json.dumps({"cache_version": smdb._CACHE_VERSION, "built_at": time.time(), "gtin_index": {}, "sku_index": {}, "brands": []})
        )

        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        gtin_index, sku_index = smdb._build_index(variants)
        with patch(
            "spoolmandb_community._refresh",
            return_value=(gtin_index, sku_index, ["Bambu Lab"], variants),
        ) as mock_refresh:
            result = smdb.get_gtin_index()
            mock_refresh.assert_called_once()
        assert smdb._canon("6975337031345") in result

    def test_refresh_failure_falls_back_to_stale_disk_cache(self, tmp_path):
        """Offline/upstream-down must not discard an otherwise-usable, if old,
        index — a stale hit beats reporting no match for every barcode."""
        stale_time = time.time() - smdb.SPOOLMANDB_COMMUNITY_TTL_SECONDS - 10
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        gtin_index, sku_index = smdb._build_index(variants)
        self._write_cache(tmp_path, gtin_index, sku_index, ["Bambu Lab"], variants, built_at=stale_time)

        with patch("spoolmandb_community._refresh", side_effect=RuntimeError("offline")):
            result = smdb.get_gtin_index()
        assert smdb._canon("6975337031345") in result

    def test_refresh_failure_with_no_cache_at_all_raises(self, tmp_path):
        """No stale fallback exists (first-ever startup, no network) — the
        caller must still learn the lookup couldn't be attempted."""
        with (
            patch("spoolmandb_community._refresh", side_effect=RuntimeError("offline")),
            pytest.raises(RuntimeError),
        ):
            smdb.get_gtin_index()

    def test_empty_refresh_result_with_no_cache_raises(self, tmp_path):
        """A refresh that parses to zero manufacturer files (e.g. the repo
        layout changes and the path filter matches nothing) must not be
        treated as a successful, cacheable refresh - with nothing to fall
        back to, the caller must learn the refresh effectively failed."""
        with (
            patch("spoolmandb_community._download_and_parse_variants", return_value=[]),
            pytest.raises(RuntimeError, match="zero manufacturer files"),
        ):
            smdb._refresh()
        assert not (tmp_path / "spoolmandb_community_index.json").exists()

    def test_empty_refresh_result_falls_back_to_stale_cache_untouched(self, tmp_path):
        """An empty refresh must not clobber a good stale cache - the stale
        entries keep serving lookups instead of "no match" for a full TTL."""
        stale_time = time.time() - smdb.SPOOLMANDB_COMMUNITY_TTL_SECONDS - 10
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        gtin_index, sku_index = smdb._build_index(variants)
        self._write_cache(tmp_path, gtin_index, sku_index, ["Bambu Lab"], variants, built_at=stale_time)
        cache_path = tmp_path / "spoolmandb_community_index.json"
        before = cache_path.read_text()

        with patch("spoolmandb_community._download_and_parse_variants", return_value=[]):
            result = smdb.get_gtin_index()

        assert smdb._canon("6975337031345") in result
        assert cache_path.read_text() == before

    def test_refresh_writes_cache_atomically(self, tmp_path):
        """Cache writes go through a temp file + rename, never a partial file
        at the real path — even if a write is interrupted mid-way."""
        cache_path = tmp_path / "spoolmandb_community_index.json"
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)

        with patch("spoolmandb_community._download_and_parse_variants", return_value=variants):
            smdb._refresh()

        assert cache_path.exists()
        assert not cache_path.with_suffix(".json.tmp").exists()
        data = json.loads(cache_path.read_text())
        assert data["cache_version"] == smdb._CACHE_VERSION

    def test_lookup_returns_none_for_unknown_barcode(self, tmp_path):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        gtin_index, sku_index = smdb._build_index(variants)
        self._write_cache(tmp_path, gtin_index, sku_index, ["Bambu Lab"], variants)
        assert smdb.lookup("0000000000000") is None

    def test_lookup_returns_fields_and_codes_for_known_barcode(self, tmp_path):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        gtin_index, sku_index = smdb._build_index(variants)
        self._write_cache(tmp_path, gtin_index, sku_index, ["Bambu Lab"], variants)

        result = smdb.lookup("6975337031345")
        assert result is not None
        fields, codes = result
        assert fields["brand"] == "Bambu Lab"
        assert any(c["kind"] == "sku" for c in codes)

    def test_lookup_sku_returns_fields_and_codes(self, tmp_path):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        gtin_index, sku_index = smdb._build_index(variants)
        self._write_cache(tmp_path, gtin_index, sku_index, ["Bambu Lab"], variants)

        result = smdb.lookup_sku("ca19001")
        assert result is not None
        fields, codes = result
        assert fields["color_name"] == "Ivory White"
        assert any(c["kind"] == "gtin" for c in codes)

    def test_lookup_sku_returns_none_for_unknown_code(self, tmp_path):
        variants = smdb._parse_manufacturer_file("Bambu Lab", SAMPLE_MANUFACTURER_FILE)
        gtin_index, sku_index = smdb._build_index(variants)
        self._write_cache(tmp_path, gtin_index, sku_index, ["Bambu Lab"], variants)
        assert smdb.lookup_sku("NOPE") is None


def _manufacturer_json(name: str, ean: str) -> bytes:
    return json.dumps(
        {
            "manufacturer": name,
            "filaments": [{"name": "Test {color_name}", "material": "PLA", "colors": [{"name": "Red", "eans": [ean]}]}],
        }
    ).encode()


def _build_tarball(files: dict) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


class _MockStreamResponse:
    """Minimal stand-in for requests.Response as used by
    `with requests.get(..., stream=True) as resp: ... resp.iter_content(...)`."""

    def __init__(self, content: bytes):
        self._content = content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i : i + chunk_size]


class TestDownloadAndParseVariantsSizeCaps:
    """Covers the review finding (ported from bambuddy): the tarball download
    and per-member reads were both unbounded, so a malformed or huge upstream
    response could exhaust memory on the 24h auto-refresh."""

    def test_successful_download_parses_all_members(self, monkeypatch):
        tarball = _build_tarball(
            {
                "SpoolmanDB-Community-main/filaments/a.json": _manufacturer_json("A Co", "1111111111111"),
                "SpoolmanDB-Community-main/filaments/b.json": _manufacturer_json("B Co", "2222222222222"),
            }
        )
        monkeypatch.setattr(smdb.requests, "get", lambda *a, **k: _MockStreamResponse(tarball))

        variants = smdb._download_and_parse_variants()

        assert {v["manufacturer"] for v in variants} == {"A Co", "B Co"}

    def test_oversized_member_is_skipped_others_still_parsed(self, monkeypatch):
        small_file = _manufacturer_json("Small Co", "1111111111111")
        huge_file = _manufacturer_json("Huge Co", "2222222222222") + b" " * 1000
        monkeypatch.setattr(smdb, "_MAX_MEMBER_BYTES", len(small_file) + 10)
        assert len(huge_file) > smdb._MAX_MEMBER_BYTES

        tarball = _build_tarball(
            {
                "SpoolmanDB-Community-main/filaments/small.json": small_file,
                "SpoolmanDB-Community-main/filaments/huge.json": huge_file,
            }
        )
        monkeypatch.setattr(smdb.requests, "get", lambda *a, **k: _MockStreamResponse(tarball))

        variants = smdb._download_and_parse_variants()

        assert {v["manufacturer"] for v in variants} == {"Small Co"}

    def test_total_download_size_over_cap_raises(self, monkeypatch):
        monkeypatch.setattr(smdb, "_MAX_TARBALL_BYTES", 50)
        tarball = _build_tarball(
            {"SpoolmanDB-Community-main/filaments/a.json": _manufacturer_json("A Co", "1111111111111")}
        )
        assert len(tarball) > 50
        monkeypatch.setattr(smdb.requests, "get", lambda *a, **k: _MockStreamResponse(tarball))

        with pytest.raises(ValueError, match="exceeded"):
            smdb._download_and_parse_variants()

    def test_total_decompressed_size_over_cap_raises(self, monkeypatch):
        """The per-member cap alone doesn't bound the sum across many members -
        several files each individually under _MAX_MEMBER_BYTES could still
        decompress to a large total. This is the residual decompression-bomb
        guard on top of the per-member cap."""
        files = {
            f"SpoolmanDB-Community-main/filaments/co{i}.json": _manufacturer_json(f"Co {i}", "1111111111111")
            for i in range(5)
        }
        member_size = len(next(iter(files.values())))
        monkeypatch.setattr(smdb, "_MAX_MEMBER_BYTES", member_size + 10)
        monkeypatch.setattr(smdb, "_MAX_TOTAL_DECOMPRESSED_BYTES", member_size * 3)
        tarball = _build_tarball(files)
        monkeypatch.setattr(smdb.requests, "get", lambda *a, **k: _MockStreamResponse(tarball))

        with pytest.raises(ValueError, match="decompressed contents exceeded"):
            smdb._download_and_parse_variants()
