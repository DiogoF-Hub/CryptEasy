"""Un blueprint par écran (+ api.py pour les boîtes de dialogue et les tâches).
Aucune route n'importe core/ ou keystore/ : tout passe par le Backend."""

from __future__ import annotations

import re

from flask import current_app, redirect, request, url_for

from ..backend import Backend, Protection
from ..dialogs import Dialogs
from ..errors import BadInput, WeakPassphrase
from ..security_levels import (
    KDF_STRENGTHS,
    KDFS,
    MIN_PASSPHRASE,
    NONE,
    ORDER,
    SALTS,
    passphrase_level,
    rate,
)
from ..state import Jobs, Selections

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
MAX_LABEL = 64


def backend() -> Backend:
    return current_app.extensions["crypteasy_backend"]


def dialogs() -> Dialogs:
    return current_app.extensions["crypteasy_dialogs"]


def selections() -> Selections:
    return current_app.extensions["crypteasy_selections"]


def jobs() -> Jobs:
    return current_app.extensions["crypteasy_jobs"]


def clean_label(raw: str | None, what: str = "error.name_required") -> str:
    """Nom de clé ou de contact : 1 à 64 caractères, sans caractère de contrôle.
    (L'échappement HTML est fait par Jinja ; jamais de |safe.)"""
    label = _CONTROL.sub("", raw or "").strip()
    if not label:
        raise BadInput(what)
    if len(label) > MAX_LABEL:
        raise BadInput("error.name_too_long", n=MAX_LABEL)
    return label


def protection_from_form(form, key_type: str | None = None) -> Protection:
    """Lit les champs « protection de la clé privée » (macro protection_fields) et calcule
    le niveau (§ 4.2 : le réglage le plus faible l'emporte)."""
    if form.get("no_passphrase") == "1":
        if form.get("no_passphrase_confirm") != "1":
            raise BadInput("error.confirm_no_passphrase")
        return Protection(passphrase=None, level=NONE)

    passphrase = form.get("passphrase", "")
    if passphrase != form.get("passphrase2", ""):
        raise BadInput("error.passphrases_differ")
    if len(passphrase) < MIN_PASSPHRASE:
        raise WeakPassphrase(n=MIN_PASSPHRASE)

    kdf = form.get("kdf") or "argon2id"
    strength = form.get("kdf_strength") or "normal"
    salt = form.get("salt") or "16"
    if kdf not in KDFS or strength not in KDF_STRENGTHS or salt not in SALTS:
        raise BadInput("error.unknown_setting")
    if salt == "0" and kdf == "argon2id":
        raise BadInput("error.argon2_needs_salt")

    choices = {"kdf": kdf, "kdf_strength": strength, "salt": salt}
    if key_type:
        choices["key_type"] = key_type
    level = max(rate(choices).level, passphrase_level(len(passphrase)), key=ORDER.index)
    return Protection(
        passphrase=passphrase.encode("utf-8"),
        kdf=kdf,
        kdf_strength=strength,
        salt_len=int(salt),
        level=level,
    )


def back_to(default_endpoint: str):
    """Redirige vers la page d'origine (chemin local uniquement), sinon `default_endpoint`."""
    target = request.form.get("next", "")
    if target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return redirect(target)
    return redirect(url_for(default_endpoint))
