"""Unit tests for label_reader.py — code candidates, effect, colour and
material canonicalization, ported from NozzleCast's FilamentLabelReaderTests."""

import pytest

import app
import label_reader as lr


class TestCanonicalMaterial:
    @pytest.mark.parametrize("raw,expected", [
        ("petg", "PETG"),
        ("Nylon", "PA"),
        ("PA6", "PA"),
        ("PA12", "PA"),
        ("PA6-CF", "PA-CF"),
        ("pla cf", "PLA-CF"),
        ("PCTG", "PCTG"),           # not in Bambuddy's list: kept as is
        ("  Wood PLA ", "Wood PLA"),
    ])
    def test_canonical(self, raw, expected):
        assert lr.canonical_material(raw) == expected

    def test_blank_is_none(self):
        assert lr.canonical_material("  ") is None


class TestEffect:
    @pytest.mark.parametrize("text,expected", [
        ("Dual Matte PLA", "dual-color"),
        ("Tri Color Silk", "tri-color"),
        ("Multicolour PLA", "multicolor"),
        ("Glow in the Dark", "glow"),
        ("Galaxy Black", "galaxy"),
        ("Matt Black", "matte"),
        ("PLA Basic", None),
        ("", None),
    ])
    def test_effect(self, text, expected):
        assert lr.effect(text) == expected

    def test_normalize_matches_bambuddy_tolerance(self):
        assert lr.normalize_effect("Dual Color") == "dual-color"
        assert lr.normalize_effect("dual_color") == "dual-color"
        assert lr.normalize_effect("shiny") is None


class TestLabelColor:
    def test_explicit_field(self):
        c = lr.label_color("PolyLite PLA Pro\nCOLOR: BLUE")
        assert c == {"name": "Blue", "explicit": True, "part_hexes": []}

    def test_bracketed_pair_named_by_line_above(self):
        c = lr.label_color("DUAL\nMATTE\nFOGGY ORANGE\n(GREY-ORANGE)")
        assert c["name"] == "Foggy Orange"
        assert c["part_hexes"] == ["808080", "FF7F00"]

    def test_pair_on_its_own_line(self):
        c = lr.label_color("PLA\nBlack/Gold")
        assert c["name"] == "Black-Gold"
        assert c["part_hexes"] == ["000000", "D4AF37"]

    def test_nothing(self):
        assert lr.label_color("PLA 1.75mm")["name"] is None


class TestSplitProductAndColor:
    def test_split(self):
        assert lr.split_product_and_color("PolyLite™ PLA Pro Blue", "Blue", "PLA") == ("Blue", "PolyLite Pro")

    def test_name_not_ending_with_colour(self):
        assert lr.split_product_and_color("Blue PolyLite", "Blue", "PLA") is None

    def test_name_is_only_the_colour(self):
        assert lr.split_product_and_color("Blue", "Blue", "PLA") is None


class TestCodes:
    def test_amazon_fnsku(self):
        assert lr.is_amazon_stock_code("X004AR68I3")
        assert not lr.is_amazon_stock_code("6938936716785")
        assert not lr.is_amazon_stock_code("CA02029")

    def test_labelled_sku_on_next_line(self):
        assert lr.labelled_skus("Net weight 1kg\nSKU:\nGFA00-B08\n") == ["GFA00-B08"]

    def test_labelled_sku_same_line(self):
        assert lr.labelled_skus("Article No. CA02029") == ["CA02029"]

    def test_sku_shaped_tokens_skip_measurements(self):
        assert lr.sku_shaped_tokens("1.75mm 1000g 220C PLA CA02029") == ["CA02029"]

    def test_candidate_order(self):
        """Decoded GTINs, printed EAN, other decoded barcodes, the labelled
        SKU, then other SKU-shaped tokens; Amazon FNSKU dropped."""
        text = "EAN: 6938936716785\nSKU: PM70820\nbatch AB12345"
        barcodes = ["X004AR68I3", "PM-INVENTORY-1", "0012345678905"]
        out = lr.code_candidates(text, barcodes, classify=app._classify_code)
        assert out == ["0012345678905", "6938936716785", "PM-INVENTORY-1", "PM70820", "AB12345"]

    def test_candidates_dedupe(self):
        out = lr.code_candidates("EAN 6938936716785", ["6938936716785"], classify=app._classify_code)
        assert out == ["6938936716785"]
