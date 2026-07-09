#!/usr/bin/env python3
"""
i18n.py — internationalization for filament_to_bambuddy.

Mirrors Bambuddy's own backend/app/i18n module: a flat dict of translations
per language, looked up by a dot-separated key with str.format()-style
interpolation ("{name}"), falling back to English when a language or key is
missing. Kept as a single small module (no build step, no npm i18n
framework) to match this app's plain Flask + vanilla-JS architecture — the
same dicts are used to translate both the Jinja-rendered page and the
in-browser JS (see templates/index.html, which embeds the active language's
dict as `window.I18N` and re-implements the same key-lookup + interpolation
in JS).

Copyright (C) 2026 Victor Manuel (hibikipr)
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from typing import Any

EN = {
    "app": {
        "title": "Filament → Bambuddy",
    },
    "ptr": {
        "pull": "Pull to refresh",
        "release": "Release to refresh",
        "refreshing": "Refreshing…",
    },
    "health": {
        "checking": "Checking Bambuddy…",
        "connected": "Connected to {bambuddy}",
        "permission_issue": "Permission issue",
        "not_reachable": "Bambuddy not reachable",
        "using": "using {bambuddy}",
        "server_error": "Server error",
    },
    "scan": {
        "refresh_db": "⟳ Refresh DB",
        "refreshing_db": "Refreshing database…",
        "refresh_updated": "Updated: {barcodes} OFD barcodes, {brands} brands.",
        "refresh_updated_smdb": " +{count} SpoolmanDB-Community barcodes.",
        "refresh_failed": "Refresh failed",
        "clear_cache": "🗑 Clear remembered lookups",
        "clear_confirm": "Forget all remembered barcode lookups? (The Open Filament Database is unaffected.)",
        "cleared": "Cleared {count} remembered lookup",
        "cleared_plural": "Cleared {count} remembered lookups",
        "clear_failed": "Clear failed",
        "scan_button": "📷 Scan barcode",
        "stop_camera": "Stop camera",
        "manual_label": "…or enter the barcode/SKU number",
        "manual_placeholder": "e.g. 6940082300018",
        "lookup_button": "Look up",
        "or_separator": "— or —",
        "ocr_button": "📸 Photograph the label to read its text",
        "camera_needs_https": "Camera needs https:// (or localhost). Type the barcode below instead.",
        "scanner_lib_failed": "Scanner library failed to load",
        "align_barcode": "Align the barcode within the frame…",
        "camera_error": "Camera error: {error}",
        "looking_up": "Looking up {barcode}…",
        "lookup_failed": "Lookup failed",
        "invalid_barcode": (
            "Enter a valid UPC-A/EAN-8/EAN-13 barcode, or a manufacturer "
            "SKU/article number (3+ characters)."
        ),
    },
    "form": {
        "title": "Filament details",
        "forget": "🗑 Forget",
        "paste_title_label": "Paste product title to auto-fill (optional)",
        "paste_title_placeholder": "e.g. SUNLU PLA+ 1.75mm Black 1KG",
        "fill_button": "✨ Fill",
        "fill_hint": "Find the listing, copy its name, tap Fill.",
        "search_link": "🔍 Search the web for this code",
        "material": "Material *",
        "brand": "Brand",
        "subtype": "Subtype / finish",
        "color_name": "Colour name",
        "color": "Colour",
        "net_weight": "Net weight (g)",
        "quantity": "Quantity",
        "storage_location": "Storage location",
        "category": "Category",
        "optional_placeholder": "optional",
        "nozzle_min": "Nozzle min °C",
        "nozzle_max": "Nozzle max °C",
        "cost_per_kg": "Cost /kg",
        "note": "Note",
        "submit": "＋ Add to Bambuddy inventory",
        "forgotten": "Forgotten — it won't auto-fill next time",
        "forget_failed": "Failed",
        "manual_entry": "entered manually",
        "also_matches": "Also matches: {codes}",
        "refill_suffix": " (refill)",
        "barcode_label": "Barcode:",
        "parse_failed": "Couldn't parse that title",
        "parse_request_failed": "Parse failed",
    },
    "badge": {
        "cache": "remembered",
        "ofd": "Open Filament Database",
        "smdb": "SpoolmanDB-Community",
        "label": "read from label photo — check carefully",
        "amazon": "Amazon code — enter below (I'll remember it)",
        "none": "not in database — enter below (I'll remember it)",
    },
    "ocr": {
        "loading_recognizer": "Loading text recognizer (first time only)…",
        "reading_label": "Reading label…",
        "reading_label_rotated": "Reading label (rotated {deg}°)… {percent}%",
        "no_text_found": "No text found — try a clearer, closer photo.",
        "couldnt_read": (
            "Couldn't read the label clearly. Try a closer, flatter, well-lit "
            "photo of the spec text — or fill in the details below."
        ),
        "failed": "OCR failed: {error}",
    },
    "submit": {
        "material_required": "Material is required",
        "added": "Added {count} spool",
        "added_plural": "Added {count} spools",
        "failed": "Failed",
        "request_failed": "Request failed",
    },
}

DE = {
    "app": {
        "title": "Filament → Bambuddy",
    },
    "ptr": {
        "pull": "Zum Aktualisieren ziehen",
        "release": "Loslassen zum Aktualisieren",
        "refreshing": "Wird aktualisiert…",
    },
    "health": {
        "checking": "Bambuddy wird geprüft…",
        "connected": "Verbunden mit {bambuddy}",
        "permission_issue": "Berechtigungsproblem",
        "not_reachable": "Bambuddy nicht erreichbar",
        "using": "verwendet {bambuddy}",
        "server_error": "Serverfehler",
    },
    "scan": {
        "refresh_db": "⟳ Datenbank aktualisieren",
        "refreshing_db": "Datenbank wird aktualisiert…",
        "refresh_updated": "Aktualisiert: {barcodes} OFD-Barcodes, {brands} Marken.",
        "refresh_updated_smdb": " +{count} SpoolmanDB-Community-Barcodes.",
        "refresh_failed": "Aktualisierung fehlgeschlagen",
        "clear_cache": "🗑 Gespeicherte Suchen löschen",
        "clear_confirm": "Alle gespeicherten Barcode-Suchen vergessen? (Die Open Filament Database ist nicht betroffen.)",
        "cleared": "{count} gespeicherte Suche gelöscht",
        "cleared_plural": "{count} gespeicherte Suchen gelöscht",
        "clear_failed": "Löschen fehlgeschlagen",
        "scan_button": "📷 Barcode scannen",
        "stop_camera": "Kamera stoppen",
        "manual_label": "…oder Barcode-/Artikelnummer eingeben",
        "manual_placeholder": "z. B. 6940082300018",
        "lookup_button": "Suchen",
        "or_separator": "— oder —",
        "ocr_button": "📸 Etikett fotografieren, um den Text zu lesen",
        "camera_needs_https": "Kamera benötigt https:// (oder localhost). Barcode stattdessen unten eingeben.",
        "scanner_lib_failed": "Scanner-Bibliothek konnte nicht geladen werden",
        "align_barcode": "Barcode im Rahmen ausrichten…",
        "camera_error": "Kamerafehler: {error}",
        "looking_up": "{barcode} wird gesucht…",
        "lookup_failed": "Suche fehlgeschlagen",
        "invalid_barcode": (
            "Gib einen gültigen UPC-A/EAN-8/EAN-13-Barcode oder eine "
            "Hersteller-Artikelnummer ein (mind. 3 Zeichen)."
        ),
    },
    "form": {
        "title": "Filament-Details",
        "forget": "🗑 Vergessen",
        "paste_title_label": "Produkttitel zum automatischen Ausfüllen einfügen (optional)",
        "paste_title_placeholder": "z. B. SUNLU PLA+ 1.75mm Schwarz 1KG",
        "fill_button": "✨ Ausfüllen",
        "fill_hint": "Angebot suchen, Namen kopieren, auf Ausfüllen tippen.",
        "search_link": "🔍 Im Web nach diesem Code suchen",
        "material": "Material *",
        "brand": "Marke",
        "subtype": "Subtyp / Oberfläche",
        "color_name": "Farbname",
        "color": "Farbe",
        "net_weight": "Nettogewicht (g)",
        "quantity": "Menge",
        "storage_location": "Lagerort",
        "category": "Kategorie",
        "optional_placeholder": "optional",
        "nozzle_min": "Düse min °C",
        "nozzle_max": "Düse max °C",
        "cost_per_kg": "Kosten /kg",
        "note": "Notiz",
        "submit": "＋ Zu Bambuddy-Inventar hinzufügen",
        "forgotten": "Vergessen — wird beim nächsten Mal nicht automatisch ausgefüllt",
        "forget_failed": "Fehlgeschlagen",
        "manual_entry": "manuell eingegeben",
        "also_matches": "Passt auch zu: {codes}",
        "refill_suffix": " (Nachfüllung)",
        "barcode_label": "Barcode:",
        "parse_failed": "Titel konnte nicht verarbeitet werden",
        "parse_request_failed": "Verarbeitung fehlgeschlagen",
    },
    "badge": {
        "cache": "gespeichert",
        "ofd": "Open Filament Database",
        "smdb": "SpoolmanDB-Community",
        "label": "vom Etikettfoto gelesen — bitte prüfen",
        "amazon": "Amazon-Code — unten eingeben (wird gespeichert)",
        "none": "nicht in der Datenbank — unten eingeben (wird gespeichert)",
    },
    "ocr": {
        "loading_recognizer": "Texterkennung wird geladen (nur beim ersten Mal)…",
        "reading_label": "Etikett wird gelesen…",
        "reading_label_rotated": "Etikett wird gelesen (gedreht {deg}°)… {percent}%",
        "no_text_found": "Kein Text gefunden — bitte ein schärferes, näheres Foto versuchen.",
        "couldnt_read": (
            "Etikett konnte nicht klar gelesen werden. Versuche ein näheres, "
            "flacheres, gut beleuchtetes Foto des Beschriftungstextes — oder "
            "fülle die Details unten aus."
        ),
        "failed": "OCR fehlgeschlagen: {error}",
    },
    "submit": {
        "material_required": "Material ist erforderlich",
        "added": "{count} Spule hinzugefügt",
        "added_plural": "{count} Spulen hinzugefügt",
        "failed": "Fehlgeschlagen",
        "request_failed": "Anfrage fehlgeschlagen",
    },
}

# All available translations.
TRANSLATIONS = {
    "en": EN,
    "de": DE,
}

DEFAULT_LANG = "en"
SUPPORTED_LANGS = sorted(TRANSLATIONS)


def get_translation(lang: str, key: str, **kwargs: Any) -> str:
    """Get a translation string by key with optional interpolation.

    Args:
        lang: Language code (e.g., 'en', 'de').
        key: Dot-separated key path (e.g., 'health.connected').
        **kwargs: Values to interpolate into the string via str.format().

    Returns:
        Translated string, or the key itself if not found in either the
        requested language or the English fallback.
    """
    translations = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG])

    keys = key.split(".")
    value: Any = translations
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            # Key not found in the requested language — fall back to English.
            value = TRANSLATIONS[DEFAULT_LANG]
            for k2 in keys:
                if isinstance(value, dict) and k2 in value:
                    value = value[k2]
                else:
                    return key  # Not found in the fallback either.
            break

    if isinstance(value, str):
        try:
            return value.format(**kwargs)
        except KeyError:
            return value

    return key


class Translator:
    """Helper class for translations bound to a specific language."""

    def __init__(self, lang: str = DEFAULT_LANG):
        self.lang = lang if lang in TRANSLATIONS else DEFAULT_LANG

    def t(self, key: str, **kwargs: Any) -> str:
        """Translate a key."""
        return get_translation(self.lang, key, **kwargs)


def resolve_locale(
    accept_language_header: str | None,
    query_lang: str | None = None,
    cookie_lang: str | None = None,
) -> str:
    """Resolve the active language for a request.

    Priority: an explicit ?lang= query override, then a previously-set
    language cookie, then the browser's Accept-Language header, then the
    default. Query/cookie values are matched case-insensitively against the
    supported set; Accept-Language is parsed permissively (region subtags
    like "en-US" fall back to their base "en").
    """
    for candidate in (query_lang, cookie_lang):
        if candidate and candidate.strip().lower() in TRANSLATIONS:
            return candidate.strip().lower()

    if accept_language_header:
        for part in accept_language_header.split(","):
            code = part.split(";")[0].strip().lower()
            if not code:
                continue
            if code in TRANSLATIONS:
                return code
            base = code.split("-")[0]
            if base in TRANSLATIONS:
                return base

    return DEFAULT_LANG
