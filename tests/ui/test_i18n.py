"""Langues (SPEC § 7.1) : mêmes clés partout, chaque page s'affiche en FR et en EN,
retour à l'anglais, choix enregistré."""

import json
import re

import pytest

from crypteasy.ui.i18n import (
    TRANSLATIONS_DIR,
    catalogs,
    format_duration,
    format_size,
    t,
)

from .conftest import post

PAGES = ["/", "/cles", "/contacts", "/chiffrer", "/dechiffrer", "/info", "/page-inconnue"]


def _placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", text))


def test_chaque_langue_a_les_memes_cles_que_l_anglais():
    english = json.loads((TRANSLATIONS_DIR / "en.json").read_text(encoding="utf-8"))
    for path in TRANSLATIONS_DIR.glob("*.json"):
        other = json.loads(path.read_text(encoding="utf-8"))
        assert set(other) == set(english), f"{path.name} : clés différentes de en.json"
        for key, text in english.items():
            assert _placeholders(other[key]) == _placeholders(text), f"{path.name} : {key}"


def test_aucun_html_dans_les_traductions():
    for lang, cat in catalogs().items():
        for key, text in cat.items():
            assert "<" not in text and ">" not in text, f"{lang} : {key}"


@pytest.mark.parametrize("lang", ["fr", "en"])
@pytest.mark.parametrize("path", PAGES)
def test_chaque_page_dans_chaque_langue(app, client, lang, path):
    """I18N_STRICT : une clé manquante ferait échouer le rendu."""
    app.config["LANGUAGE"] = lang
    r = client.get(path)
    assert r.status_code in (200, 404)
    assert f'<html lang="{lang}">' in r.get_data(as_text=True)


def test_changer_de_langue_est_enregistre(app, client, backend):
    r = post(client, "/langue", {"lang": "en", "next": "/cles"})
    assert r.status_code == 302 and r.headers["Location"] == "/cles"
    assert app.config["LANGUAGE"] == "en" and backend.load_settings()["language"] == "en"
    assert "My keys" in client.get("/cles").get_data(as_text=True)


def test_langue_inconnue_ignoree(app, client):
    post(client, "/langue", {"lang": "xx"})
    assert app.config["LANGUAGE"] == "fr"


def test_redirection_seulement_locale(client):
    r = post(client, "/langue", {"lang": "en", "next": "//attaquant.example/"})
    assert r.headers["Location"] == "/"


def test_langue_enregistree_relue_au_demarrage(tmp_path):
    from crypteasy.ui import create_app
    from crypteasy.ui.fake_backend import FakeBackend

    backend = FakeBackend()
    backend.save_settings({"language": "en"})
    assert create_app(backend, temp_root=tmp_path).config["LANGUAGE"] == "en"


def test_retour_a_l_anglais_puis_a_la_cle(app, monkeypatch):
    cats = {"fr": {"a": "A fr"}, "en": {"a": "A en", "b": "B en"}}
    monkeypatch.setattr("crypteasy.ui.i18n.catalogs", lambda: cats)
    with app.app_context():
        app.config["I18N_STRICT"] = False
        assert t("a") == "A fr" and t("b") == "B en" and t("c") == "c"
        app.config["I18N_STRICT"] = True
        with pytest.raises(KeyError):
            t("c")


def test_langue_de_l_os(monkeypatch):
    from crypteasy.ui import i18n

    monkeypatch.setattr(i18n.locale, "getlocale", lambda: ("French_France", "1252"))
    assert i18n.detect_os_language() == "fr"
    monkeypatch.setattr(i18n.locale, "getlocale", lambda: ("de_DE", "UTF-8"))
    assert i18n.detect_os_language() == "en"


@pytest.mark.parametrize(
    "lang, size, expected",
    [("fr", 512, "512 o"), ("fr", 2_300_000_000, "2,3 Go"), ("en", 2_300_000_000, "2.3 GB"),
     ("fr", 150_000_000, "150 Mo")],
)  # fmt: skip
def test_tailles(app, lang, size, expected):
    with app.app_context():
        app.config["LANGUAGE"] = lang
        assert format_size(size) == expected


@pytest.mark.parametrize(
    "seconds, expected",
    [(0.3, "moins d'une seconde"), (7, "environ 7 s"), (23, "environ 25 s"),
     (190, "environ 3 min"), (5400, "environ 1,5 h")],
)  # fmt: skip
def test_durees(app, seconds, expected):
    with app.app_context():
        assert format_duration(seconds) == expected
