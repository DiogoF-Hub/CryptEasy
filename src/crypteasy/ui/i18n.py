"""Traductions (SPEC § 7.1).

- Un fichier par langue dans translations/ : {"clé": "texte"}. Les pages et le code
  n'utilisent que la clé : t("encrypt.button").
- Texte manquant dans une langue → anglais ; manquant partout → la clé elle-même
  (et une exception en mode test, pour qu'aucune clé oubliée ne passe).
- Ajouter une langue = copier en.json en xx.json et traduire : elle apparaît
  toute seule dans le sélecteur (le nom affiché vient de "_meta.language_name").
- Les textes ne contiennent pas de HTML : Jinja les échappe comme toute donnée.
"""

from __future__ import annotations

import json
import locale
from functools import cache
from pathlib import Path

from flask import current_app, has_app_context

TRANSLATIONS_DIR = Path(__file__).parent / "translations"
FALLBACK = "en"


@cache
def catalogs() -> dict[str, dict[str, str]]:
    """Toutes les langues disponibles : {"fr": {...}, "en": {...}}."""
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(TRANSLATIONS_DIR.glob("*.json"))
    }


def available_languages() -> list[tuple[str, str]]:
    """[(code, nom affiché)] pour le sélecteur de langue."""
    return [(code, cat.get("_meta.language_name", code)) for code, cat in catalogs().items()]


def detect_os_language() -> str:
    """Premier lancement : français si l'OS est en français, anglais sinon."""
    try:
        name = (locale.getlocale()[0] or "").lower()
    except ValueError:
        name = ""
    # Linux/macOS : « fr_FR » ; Windows : « French_France »
    return "fr" if name.startswith(("fr", "french")) and "fr" in catalogs() else FALLBACK


def current_language() -> str:
    if has_app_context():
        return current_app.config.get("LANGUAGE", FALLBACK)
    return FALLBACK


def t(key: str, lang: str | None = None, **params: object) -> str:
    lang = lang or current_language()
    cats = catalogs()
    text = cats.get(lang, {}).get(key)
    if text is None:
        text = cats[FALLBACK].get(key)
    if text is None:
        if has_app_context() and current_app.config.get("I18N_STRICT"):
            raise KeyError(f"Traduction manquante : {key}")
        return key
    return text.format(**params) if params else text


def strings(prefix: str) -> dict[str, str]:
    """Tous les textes dont la clé commence par `prefix` (pour le JavaScript)."""
    keys = {k for cat in catalogs().values() for k in cat if k.startswith(prefix)}
    return {k: t(k) for k in sorted(keys)}


def format_size(size: int) -> str:
    """Taille lisible dans la langue courante : « 2,3 Go » / « 2.3 GB »."""
    units = ["size.b", "size.kb", "size.mb", "size.gb", "size.tb"]
    value, unit = float(size), 0
    while value >= 1000 and unit < len(units) - 1:
        value /= 1000
        unit += 1
    number = f"{value:.0f}" if unit == 0 or value >= 100 else f"{value:.1f}"
    number = number.replace(".", t("_meta.decimal_separator"))
    return f"{number} {t(units[unit])}"


def format_duration(seconds: float) -> str:
    """Estimation arrondie : « moins d'une seconde », « environ 25 s », « environ 3 min »."""
    if seconds < 1:
        return t("duration.under_second")
    if seconds < 60:
        return t(
            "duration.seconds", n=max(1, round(seconds / 5) * 5 if seconds > 10 else round(seconds))
        )
    minutes = seconds / 60
    if minutes < 60:
        return t("duration.minutes", n=round(minutes))
    return t("duration.hours", n=f"{minutes / 60:.1f}".replace(".", t("_meta.decimal_separator")))
