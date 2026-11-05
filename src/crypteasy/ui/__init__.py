"""Interface web locale de CryptEasy (Track B)."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from pathlib import Path

from flask import Flask, render_template
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import RequestEntityTooLarge

from .backend import Backend, default_backend
from .files import init_files
from .security import init_security

# Taille maximale d'un envoi. Choix délibéré (fiche Track B, S7 point 2) : le moteur
# travaille par blocs, la limite sert surtout à éviter de remplir le disque par erreur.
# À valider à MS0 ; le serveur waitress reçoit la même valeur (voir __main__.py).
MAX_UPLOAD_BYTES = 4 * 1024**3  # 4 Gio


def create_app(
    backend: Backend | None = None,
    *,
    port: int | None = None,
    launch_token: str | None = None,
    temp_root: Path | None = None,
    shutdown: Callable[[], None] | None = None,
) -> Flask:
    """Fabrique de l'application.

    backend=None → backend par défaut (voir backend.default_backend) ;
                   les tests passent un FakeBackend.
    port         → port réel d'écoute, utilisé par le contrôle de l'en-tête Host.
                   None = mode test (client Flask, Host « localhost » sans port).
    launch_token → jeton attendu dans ?token= au premier accès (aléatoire si absent,
                   lisible dans app.config["LAUNCH_TOKEN"]).
    temp_root    → dossier des fichiers temporaires (défaut : $CRYPTEASY_HOME/tmp,
                   sinon le dossier temporaire du système).
    shutdown     → appelé par le bouton « Quitter » (fourni par __main__.py ; rien en test).
    """
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.extensions["crypteasy_backend"] = backend or default_backend()
    app.extensions["crypteasy_shutdown"] = shutdown or (lambda: None)
    init_security(app, port=port, launch_token=launch_token or secrets.token_urlsafe(32))
    init_files(app, temp_root)

    from .routes import app_control, contacts, decrypt, encrypt, home, keys

    for module in (home, keys, contacts, encrypt, decrypt, app_control):
        app.register_blueprint(module.bp)

    @app.context_processor
    def inject_globals():
        return {"demo_mode": app.extensions["crypteasy_backend"].demo}

    @app.errorhandler(CSRFError)
    def csrf_error(_e):
        return render_template(
            "error.html",
            code=400,
            message="Jeton de sécurité expiré ou absent : rechargez la page.",
        ), 400

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("error.html", code=400, message=e.description), 400

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template(
            "error.html",
            code=403,
            bare=True,
            message="Ouvrez CryptEasy depuis son application, pas en tapant l'adresse à la main.",
        ), 403

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_e):
        return render_template(
            "error.html", code=413, message="Fichier trop volumineux (4 Gio maximum)."
        ), 413

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", code=404, message="Page introuvable."), 404

    return app
