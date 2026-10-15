"""Écran « Mes clés » : générer une paire, exporter sa clé publique, voir l'empreinte."""
import io

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..backend import DEFAULT_KEY_TYPE, KEY_TYPES
from ..errors import BadInput, user_message
from ..files import safe_filename
from . import attachment, backend, clean_label

bp = Blueprint("keys", __name__, url_prefix="/cles")


def _page(error=None, form=None, status=200):
    b = backend()
    return render_template("keys.html", identities=b.list_identities(), key_types=KEY_TYPES,
                           default_type=DEFAULT_KEY_TYPE, min_pw=b.min_password_length,
                           error=error, form=form or {}), status


@bp.get("")
def index():
    return _page()


@bp.post("")
def create():
    form = request.form
    try:
        name = clean_label(form.get("name"), "Le nom de la clé")
        key_type = form.get("key_type", DEFAULT_KEY_TYPE)
        password = form.get("password", "")
        if password != form.get("password2", ""):
            raise BadInput("Les deux mots de passe ne correspondent pas.")
        view = backend().create_identity(name, key_type, password.encode("utf-8"))
    except Exception as exc:   # noqa: BLE001 — traduit en message par user_message
        # On ne renvoie au formulaire que les champs non sensibles (jamais les mots de passe)
        return _page(user_message(exc), {"name": form.get("name", ""),
                                         "key_type": form.get("key_type", "")}, 400)
    flash(f"Paire de clés « {view.name} » créée. N'oubliez pas son mot de passe : "
          "sans lui, impossible de déchiffrer.", "success")
    return redirect(url_for("keys.index"))


@bp.get("/exporter")
def export_public():
    fingerprint = request.args.get("fpr", "")
    b = backend()
    try:
        view = next(v for v in b.list_identities() if v.fingerprint == fingerprint)
        pem = b.export_public_key(fingerprint)
    except StopIteration:
        return _page("Clé introuvable.", status=404)
    except Exception as exc:   # noqa: BLE001
        return _page(user_message(exc), status=400)
    return attachment(io.BytesIO(pem), safe_filename(f"{view.name}_cle_publique.pem"))

