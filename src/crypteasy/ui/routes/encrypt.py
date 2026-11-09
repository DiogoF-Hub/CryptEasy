"""Écran « Chiffrer » (F4). La page elle-même ; le travail passe par api.py
(choix du fichier / dossier, enregistrer sous, progression)."""

from flask import Blueprint, render_template, request

from ..security_levels import CIPHERS, DEFAULT_CIPHER, rate, rules_json
from . import backend

bp = Blueprint("encrypt", __name__, url_prefix="/chiffrer")


@bp.get("")
def index():
    b = backend()
    contacts, identities = b.list_contacts(), b.list_identities()
    selected = request.args.get("contact", "")
    kinds = {k.fingerprint: k.key_type for k in [*contacts, *identities]}
    choices = {"cipher": DEFAULT_CIPHER}
    if selected in kinds:
        choices["key_type"] = kinds[selected]
    return render_template(
        "encrypt.html",
        contacts=contacts,
        identities=identities,
        selected=selected,
        ciphers=CIPHERS,
        default_cipher=DEFAULT_CIPHER,
        rating=rate(choices),
        rules=rules_json(),
    )
