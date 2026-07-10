"""Integration tests for i18n wiring in the `/` route (app.py's index()).

Covers the full precedence chain (query > cookie > Accept-Language >
default) end-to-end through a real Flask test client, and that the embedded
window.I18N blob served to the browser actually matches the resolved
language — the unit tests in test_i18n.py cover resolve_locale() and
get_translation() in isolation, but not that app.py actually wires them
together correctly.
"""

import pytest

import app as app_module
import i18n


@pytest.fixture
def client():
    app_module.app.testing = True
    return app_module.app.test_client()


class TestIndexRouteLanguage:
    def test_defaults_to_english_with_no_signal(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b'<html lang="en">' in resp.data
        assert "Filament details".encode() in resp.data

    def test_query_param_overrides_default(self, client):
        resp = client.get("/?lang=de")
        assert resp.status_code == 200
        assert b'<html lang="de">' in resp.data
        assert "Filament-Details".encode() in resp.data

    def test_query_param_sets_a_persistent_cookie(self, client):
        resp = client.get("/?lang=de")
        set_cookie = resp.headers.get("Set-Cookie", "")
        assert "lang=de" in set_cookie

    def test_unsupported_query_param_does_not_set_a_cookie(self, client):
        resp = client.get("/?lang=xx")
        assert "Set-Cookie" not in resp.headers

    def test_cookie_is_honored_on_a_later_request_without_query_param(self, client):
        client.set_cookie("lang", "de")
        resp = client.get("/")
        assert b'<html lang="de">' in resp.data

    def test_accept_language_header_is_honored(self, client):
        resp = client.get("/", headers={"Accept-Language": "de-DE,de;q=0.9,en;q=0.8"})
        assert b'<html lang="de">' in resp.data

    def test_query_param_wins_over_accept_language_header(self, client):
        resp = client.get("/?lang=en", headers={"Accept-Language": "de-DE,de;q=0.9"})
        assert b'<html lang="en">' in resp.data

    def test_embedded_i18n_blob_matches_resolved_language(self, client):
        resp = client.get("/?lang=de")
        body = resp.data.decode()
        assert 'const I18N_LANG = "de";' in body
        # The embedded dict must be the real German translations, not just
        # the language tag — spot-check one nested value round-trips
        # through Jinja's |tojson into the page.
        assert '"material": "Material *"' in body

    def test_unsupported_accept_language_falls_back_to_english(self, client):
        # Russian isn't one of Bambuddy's supported languages.
        resp = client.get("/", headers={"Accept-Language": "ru-RU,ru;q=0.9"})
        assert b'<html lang="en">' in resp.data

    @pytest.mark.parametrize("lang", i18n.SUPPORTED_LANGS)
    def test_every_supported_language_renders_without_error(self, client, lang):
        """Every language Bambuddy itself supports must render a full page
        with no unrendered Jinja placeholders and a matching lang attribute —
        a fast way to catch a typo'd key in any one language dict."""
        resp = client.get(f"/?lang={lang}")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert f'<html lang="{lang}">' in body
        assert "{{" not in body
        assert f'const I18N_LANG = "{lang}";' in body


class TestResolveRequestLocaleHelper:
    """Covers app._resolve_request_locale directly, isolated from the
    surrounding render_template call."""

    def test_matches_i18n_resolve_locale_given_the_same_inputs(self, client):
        with app_module.app.test_request_context("/?lang=de", headers={"Accept-Language": "en"}):
            resolved = app_module._resolve_request_locale()
        expected = i18n.resolve_locale("en", query_lang="de", cookie_lang=None)
        assert resolved == expected == "de"
