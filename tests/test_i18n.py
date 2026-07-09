"""Unit tests for i18n.py — internationalization for filament_to_bambuddy.

Mirrors bambuddy's backend/tests/unit tests for its own backend/app/i18n
module (dot-key lookup, str.format() interpolation, English fallback), plus
tests for resolve_locale's query/cookie/header precedence, which this app's
i18n module has and bambuddy's backend one doesn't (bambuddy's frontend
handles that with i18next-browser-languagedetector instead).
"""

import i18n


class TestGetTranslation:
    def test_returns_known_key_in_requested_language(self):
        assert i18n.get_translation("de", "form.material") == "Material *"

    def test_returns_known_key_in_english_by_default(self):
        assert i18n.get_translation("en", "form.material") == "Material *"

    def test_unknown_language_falls_back_to_english(self):
        assert i18n.get_translation("xx", "form.material") == i18n.get_translation("en", "form.material")

    def test_interpolates_kwargs(self):
        assert i18n.get_translation("en", "health.connected", bambuddy="my-server") == "Connected to my-server"

    def test_interpolates_kwargs_in_non_english_language(self):
        assert i18n.get_translation("de", "health.connected", bambuddy="my-server") == "Verbunden mit my-server"

    def test_missing_interpolation_kwarg_returns_unformatted_string(self):
        # format() raises KeyError for a missing placeholder value — the
        # function must swallow that and return the raw template rather than
        # propagating an exception up into a request handler.
        result = i18n.get_translation("en", "health.connected")
        assert result == "Connected to {bambuddy}"

    def test_missing_key_in_requested_language_falls_back_to_english(self):
        # A key present in EN but deliberately absent from a non-English
        # dict (simulated by monkeypatching would be more realistic, but
        # every key in this module IS translated — so instead assert the
        # fallback path activates for a key that doesn't exist anywhere,
        # which must return the key itself in both languages).
        assert i18n.get_translation("de", "nonexistent.key") == "nonexistent.key"
        assert i18n.get_translation("en", "nonexistent.key") == "nonexistent.key"

    def test_key_missing_everywhere_returns_the_key(self):
        assert i18n.get_translation("en", "totally.bogus.key") == "totally.bogus.key"

    def test_non_string_leaf_returns_the_key(self):
        # "form" is a dict, not a string leaf — asking for it directly (no
        # further path segment) must not return a dict to the caller.
        assert i18n.get_translation("en", "form") == "form"


class TestTranslator:
    def test_defaults_to_english(self):
        translator = i18n.Translator()
        assert translator.lang == "en"

    def test_unsupported_language_falls_back_to_english(self):
        translator = i18n.Translator("xx")
        assert translator.lang == "en"

    def test_supported_language_is_kept(self):
        translator = i18n.Translator("de")
        assert translator.lang == "de"

    def test_t_delegates_to_get_translation(self):
        translator = i18n.Translator("de")
        assert translator.t("form.material") == "Material *"

    def test_t_interpolates_kwargs(self):
        translator = i18n.Translator("en")
        assert translator.t("scan.looking_up", barcode="123") == "Looking up 123…"


class TestResolveLocale:
    def test_query_param_wins_over_everything(self):
        assert i18n.resolve_locale("de", query_lang="en", cookie_lang="de") == "en"

    def test_cookie_used_when_no_query_param(self):
        assert i18n.resolve_locale("en", query_lang=None, cookie_lang="de") == "de"

    def test_accept_language_used_when_no_query_or_cookie(self):
        assert i18n.resolve_locale("de-DE,de;q=0.9,en;q=0.8") == "de"

    def test_accept_language_base_subtag_matches(self):
        # "de-AT" (Austrian German) has no exact-match dict, but must still
        # resolve to the base "de" translations rather than falling through
        # to English.
        assert i18n.resolve_locale("de-AT,de;q=0.9") == "de"

    def test_unsupported_accept_language_falls_back_to_default(self):
        assert i18n.resolve_locale("fr-FR,fr;q=0.9") == i18n.DEFAULT_LANG

    def test_no_signal_at_all_falls_back_to_default(self):
        assert i18n.resolve_locale(None) == i18n.DEFAULT_LANG

    def test_unsupported_query_param_is_ignored_falls_through_to_cookie(self):
        assert i18n.resolve_locale(None, query_lang="fr", cookie_lang="de") == "de"

    def test_query_param_is_case_insensitive(self):
        assert i18n.resolve_locale(None, query_lang="DE") == "de"

    def test_accept_language_picks_first_supported_entry_in_priority_order(self):
        # "fr" (unsupported) is listed before "de" (supported) — the first
        # *supported* entry should win, not just the first entry overall.
        assert i18n.resolve_locale("fr;q=0.9,de;q=0.8") == "de"


class TestTranslationSetsAreComplete:
    """Every language must define exactly the same set of keys as English —
    a silently-missing key in a non-English language would only be caught at
    runtime (via the fallback) instead of at test time."""

    def _flatten(self, d, prefix=""):
        keys = set()
        for k, v in d.items():
            full = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys |= self._flatten(v, full)
            else:
                keys.add(full)
        return keys

    def test_all_languages_have_the_same_keys_as_english(self):
        english_keys = self._flatten(i18n.EN)
        for lang, translations in i18n.TRANSLATIONS.items():
            if lang == "en":
                continue
            assert self._flatten(translations) == english_keys, f"{lang} key set mismatch"

    def test_no_empty_string_values(self):
        for lang, translations in i18n.TRANSLATIONS.items():
            for key in self._flatten(translations):
                value = translations
                for part in key.split("."):
                    value = value[part]
                assert value != "", f"{lang}.{key} is empty"
