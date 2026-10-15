"""Écran « Contacts » : ajouter (fichier ou clé collée), voir l'empreinte, supprimer (par empreinte)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..errors import BadInput, user_message
from . import backend, clean_label

bp = Blueprint("contacts", __name__, url_prefix="/contacts")
MAX_KEY_BYTES = 64 * 1024


def _page(error=None, form=None, status=200):
    return render_template("contacts.html", contacts=backend().list_contacts(),
                           error=error, form=form or {}), status


@bp.get("")
def index():
    return _page()


@bp.post("")
def add():
    form = request.form
    try:
        name = clean_label(form.get("name"), "Le nom du contact")
        upload = request.files.get("keyfile")
        if upload and upload.filename:
            pem = upload.stream.read(MAX_KEY_BYTES + 1)
            if len(pem) > MAX_KEY_BYTES:
                raise BadInput("Ce fichier est trop gros pour être une clé publique.")
        else:
            pem = form.get("keytext", "").strip().encode("utf-8")
        if not pem:
            raise BadInput("Importez le fichier de sa clé publique, ou collez-la.")
        view = backend().add_contact(name, pem)
    except Exception as exc:   # noqa: BLE001
        return _page(user_message(exc), form, 400)
    flash(f"Contact « {view.name} » ajouté. Empreinte : {view.fingerprint}. "
          "Vérifiez-la avec cette personne, par téléphone ou en face à face.", "success")
    return redirect(url_for("contacts.index"))


@bp.post("/supprimer")
def remove():
    fingerprint = request.form.get("fingerprint", "")
    names = [c.name for c in backend().list_contacts() if c.fingerprint == fingerprint]
    backend().remove_contact(fingerprint)
    if names:
        flash(f"Contact « {names[0]} » supprimé.", "success")
    return redirect(url_for("contacts.index"))
