import pytest
from filament_parse import parse_title, _find_nozzle_temps, _find_weight_grams, _find_diameter


# ── parse_title: the four example titles from the module's __main__ block ─────

def test_pla_plus_black():
    f = parse_title("SUNLU PLA+ Filament 1.75mm Black 1KG")
    assert f["brand"] == "Sunlu"
    assert f["material"] == "PLA"
    assert f["subtype"] == "Plus"
    assert f["color_name"] == "Black"
    assert f["label_weight"] == 1000
    assert f["diameter_mm"] == 1.75


def test_petg_matte_gray():
    f = parse_title("Overture PETG 1.75 mm Matte Gray 1kg Spool")
    assert f["material"] == "PETG"
    assert f["subtype"] == "Matte"
    assert f["color_name"] == "Gray"
    assert f["label_weight"] == 1000
    assert f["diameter_mm"] == 1.75


def test_abs_plus_red():
    f = parse_title("eSUN ABS+ 3D Printer Filament 1.75mm Red 1000g")
    assert f["material"] == "ABS"
    assert f["color_name"] == "Red"
    assert f["label_weight"] == 1000


def test_pla_carbon_fiber():
    f = parse_title("Polymaker PolyTerra PLA Carbon Fiber 1.75mm 500g")
    assert f["brand"] == "Polymaker"
    assert f["material"] == "PLA"
    assert f["subtype"] == "Carbon Fiber"
    assert f["label_weight"] == 500


# ── material detection ────────────────────────────────────────────────────────

@pytest.mark.parametrize("title,expected", [
    ("eSUN PETG+ 1.75mm", "PETG"),
    ("PCTG Filament 1kg", "PCTG"),
    ("Generic TPU 95A", "TPU"),
    ("PA-CF Carbon Nylon", "Nylon"),
    ("HIPS Support", "HIPS"),
])
def test_material_variants(title, expected):
    assert parse_title(title).get("material") == expected


# ── weight detection ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("1KG spool", 1000),
    ("2kg roll", 2000),
    ("500g", 500),
    ("0.5kg", 500),
    ("250 g", 250),
])
def test_find_weight_grams(text, expected):
    assert _find_weight_grams(text) == expected


def test_find_weight_grams_none():
    assert _find_weight_grams("no weight here") is None


# ── diameter detection ────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("1.75mm filament", 1.75),
    ("2.85 mm", 2.85),
    ("diameter 1.75", 1.75),
])
def test_find_diameter(text, expected):
    assert _find_diameter(text) == expected


# ── nozzle temperature detection ─────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("Nozzle 190-220°C", (190, 220)),
    ("printing temp 200~230C", (200, 230)),
    ("210°C nozzle", (210, 210)),
    # bed temp should not be returned
    ("Bed: 60°C", None),
])
def test_find_nozzle_temps(text, expected):
    assert _find_nozzle_temps(text) == expected


# ── colour detection ──────────────────────────────────────────────────────────

def test_color_basic():
    f = parse_title("PLA 1.75mm Blue 1kg")
    assert f["color_name"] == "Blue"
    assert f["rgba"] == "0050FFFF"


def test_dual_color():
    f = parse_title("Silk PLA 1.75mm Gold-Silver 1kg")
    assert "Gold" in f["color_name"]
    assert "Silver" in f["color_name"]


# ── hex colour override ───────────────────────────────────────────────────────

def test_hex_overrides_name_color():
    f = parse_title("PLA 1.75mm Black 1kg #FF5500")
    assert f["rgba"] == "FF5500FF"


# ── brand_hint overrides detection ───────────────────────────────────────────

def test_brand_hint():
    f = parse_title("PLA+ 1.75mm Black 1kg", brand_hint="CustomBrand")
    assert f["brand"] == "CustomBrand"


# ── empty / degenerate input ──────────────────────────────────────────────────

def test_empty_title():
    assert parse_title("") == {}


def test_no_recognisable_content():
    f = parse_title("hello world")
    assert "material" not in f
    assert "color_name" not in f
