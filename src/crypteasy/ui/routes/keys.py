"""Écran « Mes clés » (F1, F2) : générer (niveau + avancé + sans phrase secrète),
importer une clé privée, changer la protection, exporter (enregistrer sous), supprimer."""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..errors import BadInput, user_message
from ..files import safe_filename
from ..i18n import t
from ..security_levels import (
    CUSTOM,
    DEFAULT_LEVEL,
    ICONS,
    KDF_STRENGTHS,
    KDFS,
    KEY_TYPES,
    ORDER,
    PRESETS,
    SALTS,
    preset_of,
    rate,
    rules_json,
)
from . import backend, clean_label, dialogs, protection_from_form, selections

bp = Blueprint("keys", __name__, url_prefix="/cles")
FORM_FIELDS = ("name", "level", "key_type", "kdf", "kdf_strength", "salt", "no_passphrase")


def _page(error=None, form=None, status=200, panel=None):
    """panel : formulaire à laisser ouvert après une erreur ("import" ou une empreinte)."""
    form = form or {}
    choices = {
        k: form.get(k) or PRESETS[DEFAULT_LEVEL][k]
        for k in ("key_type", "kdf", "kdf_strength", "salt")
    }
    no_pass = form.get("no_passphrase") == "1"
    return render_template(
        "keys.html",
        identities=backend().list_identities(),
        form=form,
        choices=choices,
        level=form.get("level") or preset_of(choices),
        rating=rate(choices, no_passphrase=no_pass),
        rules=rules_json(),
        options={"key_type": KEY_TYPES, "kdf": KDFS, "kdf_strength": KDF_STRENGTHS, "salt": SALTS},
        levels=[*[lvl for lvl in ORDER if lvl in PRESETS], CUSTOM],
        icons=ICONS,
        error=error,
        panel=panel,
    ), status


def _safe_form(form):
    """Champs renvoyés au formulaire après une erreur : jamais les phrases secrètes."""
    return {k: form.get(k, "") for k in FORM_FIELDS}


def _find(fingerprint: str):
    view = next((v for v in backend().list_identities() if v.fingerprint == fingerprint), None)
    if view is None:
        raise BadInput("error.not_found")
    return view


@bp.get("")
def index():
    return _page()


@bp.post("")
def create():
    form = request.form
    try:
        name = clean_label(form.get("name"))
        key_type = form.get("key_type") or PRESETS[DEFAULT_LEVEL]["key_type"]
        if key_type not in KEY_TYPES:
            raise BadInput("error.unknown_setting")
        view = backend().create_identity(name, key_type, protection_from_form(form, key_type))
    except Exception as exc:  # traduit en message par user_message
        return _page(user_message(exc), _safe_form(form), 400)
    flash(t("keys.created", name=view.name), "success")
    return redirect(url_for("keys.index"))


@bp.post("/importer")
def import_private():
    form = request.form
    try:
        name = clean_label(form.get("name"))
        key_file = selections().get(form.get("key_selection"), "key-file").path
        current = form.get("current_passphrase", "").encode("utf-8") or None
        view = backend().import_private_key(name, key_file, current, protection_from_form(form))
    except Exception as exc:  # traduit en message par user_message
        return _page(user_message(exc), {"import_name": form.get("name", "")}, 400, "import")
    flash(t("keys.imported", name=view.name), "success")
    return redirect(url_for("keys.index"))


@bp.post("/proteger")
def change_protection():
    form = request.form
    fingerprint = form.get("fingerprint", "")
    try:
        view = _find(fingerprint)
        current = form.get("current_passphrase", "").encode("utf-8") or None
        protection = protection_from_form(form, view.key_type)
        view = backend().change_protection(fingerprint, current, protection)
    except Exception as exc:  # traduit en message par user_message
        return _page(user_message(exc), status=400, panel=fingerprint)
    flash(t("keys.protection_changed", name=view.name), "success")
    return redirect(url_for("keys.index"))


def _export(kind: str):
    """Exporte via la boîte native « enregistrer sous » ; Python écrit directement le fichier."""
    try:
        view = _find(request.form.get("fingerprint", ""))
        if kind == "public":
            default = safe_filename(f"{view.name}_public.pem")
            types = [t("dialog.types.public_key")]
        else:
            default = safe_filename(f"{view.name}_private.key")
            types = [t("dialog.types.private_key")]
        dst = dialogs().save_file(default, types)
        if dst is None:  # boîte fermée sans choisir : rien à faire
            return redirect(url_for("keys.index"))
        if kind == "public":
            backend().export_public_key(view.fingerprint, dst)
        else:
            backend().export_private_key(view.fingerprint, dst)
    except Exception as exc:  # traduit en message par user_message
        return _page(user_message(exc), status=400)
    flash(t(f"keys.exported_{kind}", path=str(dst)), "success")
    return redirect(url_for("keys.index"))


@bp.post("/exporter-publique")
def export_public():
    return _export("public")


@bp.post("/exporter-privee")
def export_private():
    return _export("private")


@bp.post("/supprimer")
def delete():
    view = next(
        (
            v
            for v in backend().list_identities()
            if v.fingerprint == request.form.get("fingerprint")
        ),
        None,
    )
    if view is not None:
        backend().delete_identity(view.fingerprint)
        flash(t("keys.deleted", name=view.name), "success")
    return redirect(url_for("keys.index"))
