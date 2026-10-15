"""Écran « Chiffrer » : un contact + un fichier → téléchargement d'un .ceasy.

Le fichier chiffré ne reprend PAS le nom d'origine (§ 4 « Output naming ») :
nom choisi par l'utilisateur, sinon aléatoire. Le vrai nom voyage chiffré à l'intérieur.
"""
import secrets

from flask import Blueprint, render_template, request

from ..errors import BadInput, user_message
from ..files import new_job, remove_job, safe_filename, save_upload
from . import attachment, backend

bp = Blueprint("encrypt", __name__, url_prefix="/chiffrer")
EXT = ".ceasy"


def _page(error=None, status=200):
    return render_template("encrypt.html", contacts=backend().list_contacts(), ext=EXT,
                           error=error, selected=request.values.get("contact", "")), status


@bp.get("")
def index():
    return _page()


def output_name(raw: str | None) -> str:
    raw = (raw or "").strip()
    if not raw:
        return f"crypteasy-{secrets.token_hex(4)}{EXT}"
    name = safe_filename(raw)
    return name if name.lower().endswith(EXT) else name + EXT


@bp.post("")
def run():
    job = new_job()
    try:
        contact = request.form.get("contact", "")
        if not contact:
            raise BadInput("Choisissez un destinataire.")
        out_name = output_name(request.form.get("out_name"))
        src = save_upload(request.files.get("file"), job / "in")
        dst = job / "out" / out_name
        dst.parent.mkdir()
        backend().encrypt_file(src, dst, contact)
        src.unlink()   # le clair n'a plus rien à faire sur le disque
        return attachment(dst, out_name, cleanup=lambda: remove_job(job))
    except Exception as exc:   # noqa: BLE001
        remove_job(job)
        return _page(user_message(exc), 400)
