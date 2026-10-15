"""Écran « Mes clés » (F1, F2) : générer, importer une clé privée, exporter (publique /
privée), supprimer. Plusieurs paires possibles (D9)."""
import io

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..errors import BadInput, user_message
from ..files import safe_filename
from ..security_levels import DEFAULT_KDF, DEFAULT_KEY_TYPE, KEY_TYPES, rate, rules_json
from . import attachment, backend, clean_label

bp = Blueprint("keys", __name__, url_prefix="/cles")
MAX_KEY_BYTES = 64 * 1024


def _rating(form):
    b = backend()
    choices = {"key_type": form.get("key_type") or DEFAULT_KEY_TYPE}
    if b.key_protection_kdfs:
        choices["kdf"] = form.get("kdf") or DEFAULT_KDF
    return rate(choices)


def _page(error=None, form=None, status=200, open_import=False):
    b = backend()
    form = form or {}
    return render_template(
        "keys.html", identities=b.list_identities(), key_types=KEY_TYPES,
        default_type=DEFAULT_KEY_TYPE, kdfs=b.key_protection_kdfs, default_kdf=DEFAULT_KDF,
        min_pw=b.min_password_length, rating=_rating(form), rules=rules_json(),
        error=error, form=form, open_import=open_import), status


def _safe_form(form):
    """Champs renvoyés au formulaire après une erreur : jamais les mots de passe."""
    return {k: form.get(k, "") for k in ("name", "key_type", "kdf")}


@bp.get("")
def index():
    return _page()


@bp.post("")
def create():
    form = request.form
    try:
        name = clean_label(form.get("name"), "Le nom de la clé")
        password = form.get("password", "")
        if password != form.get("password2", ""):
            raise BadInput("Les deux mots de passe ne correspondent pas.")
        kdf = form.get("kdf") or None if backend().key_protection_kdfs else None
        view = backend().create_identity(name, form.get("key_type") or DEFAULT_KEY_TYPE,
                                         password.encode("utf-8"), kdf)
    except Exception as exc:   # noqa: BLE001 — traduit en message par user_message
        return _page(user_message(exc), _safe_form(form), 400)
    flash(f"Paire de clés « {view.name} » créée. N'oubliez pas son mot de passe : "
          "sans lui, impossible de déchiffrer.", "success")
    return redirect(url_for("keys.index"))


@bp.post("/importer")
def import_private():
    form = request.form
    try:
        name = clean_label(form.get("name"), "Le nom de la clé")
        upload = request.files.get("keyfile")
        if not upload or not upload.filename:
            raise BadInput("Choisissez le fichier .pem de la clé privée.")
        pem = upload.stream.read(MAX_KEY_BYTES + 1)
        if len(pem) > MAX_KEY_BYTES:
            raise BadInput("Ce fichier est trop gros pour être une clé privée.")
        view = backend().import_private_key(name, pem, form.get("password", "").encode("utf-8"))
    except Exception as exc:   # noqa: BLE001
        return _page(user_message(exc), {"import_name": form.get("name", "")}, 400,
                     open_import=True)
    flash(f"Clé « {view.name} » importée.", "success")
    return redirect(url_for("keys.index"))


def _find(fingerprint):
    return next((v for v in backend().list_identities() if v.fingerprint == fingerprint), None)


@bp.get("/exporter")
def export_public():
    view = _find(request.args.get("fpr", ""))
    if view is None:
        return _page("Clé introuvable.", status=404)
    pem = backend().export_public_key(view.fingerprint)
    return attachment(io.BytesIO(pem), safe_filename(f"{view.name}_cle_publique.pem"))


@bp.post("/exporter-privee")
def export_private():
    """POST + CSRF + confirmation : la clé privée ne sort que sur demande explicite."""
    view = _find(request.form.get("fingerprint", ""))
    if view is None:
        return _page("Clé introuvable.", status=404)
    pem = backend().export_private_key(view.fingerprint)
    return attachment(io.BytesIO(pem), safe_filename(f"{view.name}_cle_PRIVEE.pem"))


@bp.post("/supprimer")
def delete():
    view = _find(request.form.get("fingerprint", ""))
    if view is not None:
        backend().delete_identity(view.fingerprint)
        flash(f"Clé « {view.name} » supprimée.", "success")
    return redirect(url_for("keys.index"))
