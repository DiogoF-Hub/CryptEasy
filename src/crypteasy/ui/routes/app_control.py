"""Bouton « Quitter » (option (b) du contrat de lancement, § 3) : POST protégé par CSRF."""

from flask import Blueprint, current_app, render_template

bp = Blueprint("app_control", __name__)


@bp.post("/quitter")
def quit_app():
    current_app.extensions["crypteasy_shutdown"]()  # __main__.py arrête le serveur juste après
    return render_template("closed.html")
