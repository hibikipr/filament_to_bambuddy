"""Unit tests for app.py's _classify_code().

Mirrors bambuddy's backend/tests/unit/test_spool_schemas_barcode.py
TestClassifyCode so the two implementations can be sanity-checked against the
same expected outputs.
"""

import app


class TestClassifyCode:
    def test_valid_upc_a_is_gtin(self):
        assert app._classify_code("012345678905") == ("12345678905", "gtin")

    def test_valid_ean_13_is_gtin(self):
        assert app._classify_code("06938936716785") == ("6938936716785", "gtin")

    def test_bad_checksum_falls_back_to_sku(self):
        # Right length (12 digits) but an invalid check digit.
        code, kind = app._classify_code("099999999999")
        assert kind == "sku"

    def test_alphanumeric_code_is_sku(self):
        """A Code 128 manufacturer SKU/article number — e.g. a Polymaker
        inventory barcode with no UPC/EAN counterpart."""
        assert app._classify_code("ALZMNTABS01") == ("ALZMNTABS01", "sku")

    def test_short_digit_string_below_floor_is_sku(self):
        code, kind = app._classify_code("12345")
        assert kind == "sku"

    def test_leading_zero_upc_a_still_classifies_gtin_after_stripping(self):
        """Regression: a UPC-A with a leading zero must classify as gtin
        whether fed the raw scanned value or the already-stripped short form
        (e.g. typed from a receipt/product page showing 11 digits) — the
        GTIN checksum is invariant to leading-zero padding, so re-padding the
        stripped canonical form and checking there gives the same verdict the
        raw value would have. Before this fix, _classify_code required an
        exact 8/12/13/14-digit match, so the stripped 11-digit form fell
        through to "sku" and the external lookup queried the wrong index."""
        raw = "036000291452"  # 12-digit UPC-A, one leading zero
        stripped = "36000291452"
        assert app._classify_code(raw) == ("36000291452", "gtin")
        assert app._classify_code(stripped) == ("36000291452", "gtin")

    def test_classification_is_stable_across_canon(self):
        """_classify_code(x) and _classify_code(ofd._canon(x)) must always
        agree — this is what guarantees a scan (raw input) and a later typed
        lookup of the same barcode's short form can never disagree on kind."""
        import ofd

        for raw in (
            "0012345678905",
            "012345678905",
            "06938936716785",
            "0000000000123456",  # heavily zero-padded, still within GTIN-14
            "ALZMNTABS01",
            "099999999999",
        ):
            canonical = ofd._canon(raw)
            _, raw_kind = app._classify_code(raw)
            _, canonical_kind = app._classify_code(canonical)
            assert raw_kind == canonical_kind, raw
