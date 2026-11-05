"""Écran « Contacts » (F3) : ajouter (fichier .pem choisi dans la boîte native, ou clé
collée), voir l'empreinte, renommer, supprimer. Un contact = l'empreinte de sa clé."""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..errors import BadInput, InvalidPublicKey, user_message
from ..i18n import t
from . import backend, clean_label, selections

bp = Blueprint("contacts", __name__, url_prefix="/contacts")
MAX_KEY_BYTES = 64 * 1024


def _page(error=None, form=None, status=200, editing=None):
    return render_template(
        "contacts.html",
        contacts=backend().list_contacts(),
        error=error,
        form=form or {},
        editing=editing,
    ), status


@bp.get("")
def index():
    return _page(editing=request.args.get("renommer"))


@bp.post("")
def add():
    form = request.form
    try:
        name = clean_label(form.get("name"))
        if form.get("key_selection"):
            path = selections().get(form.get("key_selection"), "public-key").path
            if path.stat().st_size > MAX_KEY_BYTES:
                raise InvalidPublicKey()
            pem = path.read_bytes()
        else:
            pem = form.get("keytext", "").strip().encode("utf-8")
        if not pem:
            raise BadInput("error.contact_key_required")
        view = backend().add_contact(name, pem)
    except Exception as exc:  # traduit en message par user_message
        return _page(user_message(exc), {k: form.get(k, "") for k in ("name", "keytext")}, 400)
    flash(t("contacts.added", name=view.name, fingerprint=view.fingerprint), "success")
    return redirect(url_for("contacts.index"))


@bp.post("/renommer")
def rename():
    fingerprint = request.form.get("fingerprint", "")
    try:
        name = clean_label(request.form.get("name"))
        backend().rename_contact(fingerprint, name)
    except Exception as exc:  # traduit en message par user_message
        return _page(user_message(exc), status=400, editing=fingerprint)
    flash(t("contacts.renamed", name=name), "success")
    return redirect(url_for("contacts.index"))


@bp.post("/supprimer")
def remove():
    fingerprint = request.form.get("fingerprint", "")
    names = [c.name for c in backend().list_contacts() if c.fingerprint == fingerprint]
    backend().remove_contact(fingerprint)
    if names:
        flash(t("contacts.deleted", name=names[0]), "success")
    return redirect(url_for("contacts.index"))
