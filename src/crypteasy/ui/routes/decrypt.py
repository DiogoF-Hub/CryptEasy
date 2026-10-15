"""Écran « Déchiffrer » (F5) : paquet .zip + une de mes clés OU une clé privée .pem
importée pour l'occasion + mot de passe de la clé (+ mot de passe du fichier si
l'expéditeur en a mis un) → fichier d'origine."""
from flask import Blueprint, render_template, request

from ..errors import BadInput, user_message
from ..files import new_job, remove_job, save_upload
from . import attachment, backend

bp = Blueprint("decrypt", __name__, url_prefix="/dechiffrer")
MAX_KEY_BYTES = 64 * 1024


def _page(error=None, status=200):
    return render_template("decrypt.html", identities=backend().list_identities(),
                           error=error, selected=request.form.get("identity", "")), status


@bp.get("")
def index():
    return _page()


@bp.post("")
def run():
    job = new_job()
    try:
        form = request.form
        key_password = form.get("password", "")
        if not key_password:
            raise BadInput("Saisissez le mot de passe de votre clé privée.")
        file_password = form.get("file_password", "").encode("utf-8") or None

        key_upload = request.files.get("privkey")
        private_pem = identity = None
        if key_upload and key_upload.filename:
            private_pem = key_upload.stream.read(MAX_KEY_BYTES + 1)
            if len(private_pem) > MAX_KEY_BYTES:
                raise BadInput("Ce fichier est trop gros pour être une clé privée.")
        else:
            identities = backend().list_identities()
            identity = form.get("identity") or (
                identities[0].fingerprint if len(identities) == 1 else "")
            if not identity:
                raise BadInput("Choisissez votre clé, ou importez votre clé privée (.pem).")

        src = save_upload(request.files.get("file"), job / "in")
        plain = backend().decrypt_file(
            src, job / "out", key_password=key_password.encode("utf-8"),
            file_password=file_password, identity_fingerprint=identity, private_pem=private_pem)
        src.unlink()
        return attachment(plain, plain.name, cleanup=lambda: remove_job(job))
    except Exception as exc:   # noqa: BLE001
        remove_job(job)
        return _page(user_message(exc), 400)
