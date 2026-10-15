"""Écran « Déchiffrer » : un .ceasy + ma clé + mot de passe → fichier d'origine."""
from flask import Blueprint, render_template, request

from ..errors import BadInput, user_message
from ..files import new_job, remove_job, save_upload
from . import attachment, backend

bp = Blueprint("decrypt", __name__, url_prefix="/dechiffrer")


def _page(error=None, status=200):
    return render_template("decrypt.html", identities=backend().list_identities(),
                           error=error), status


@bp.get("")
def index():
    return _page()


@bp.post("")
def run():
    job = new_job()
    try:
        identities = backend().list_identities()
        identity = request.form.get("identity") or (
            identities[0].fingerprint if len(identities) == 1 else "")
        if not identity:
            raise BadInput("Choisissez votre clé." if identities
                           else "Créez d'abord votre paire de clés dans « Mes clés ».")
        password = request.form.get("password", "")
        if not password:
            raise BadInput("Saisissez le mot de passe de votre clé.")
        src = save_upload(request.files.get("file"), job / "in")
        plain = backend().decrypt_file(src, job / "out", identity, password.encode("utf-8"))
        src.unlink()
        return attachment(plain, plain.name, cleanup=lambda: remove_job(job))
    except Exception as exc:   # noqa: BLE001
        remove_job(job)
        return _page(user_message(exc), 400)
