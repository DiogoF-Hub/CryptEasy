"""Écran « Déchiffrer » (F5). La page elle-même ; le travail passe par api.py
(choix du paquet, détection de la clé, progression, enregistrer sous / extraire)."""

from flask import Blueprint, render_template

from . import backend

bp = Blueprint("decrypt", __name__, url_prefix="/dechiffrer")


@bp.get("")
def index():
    return render_template("decrypt.html", identities=backend().list_identities())
