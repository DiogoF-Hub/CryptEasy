"""Interface de CryptEasy (Track B) : pages Flask affichées dans la fenêtre pywebview."""

from __future__ import annotations

import secrets
import threading
from pathlib import Path

from flask import Flask, render_template, request
from flask_wtf.csrf import CSRFError, generate_csrf
from werkzeug.exceptions import HTTPException

from .backend import Backend, default_backend
from .dialogs import Dialogs, NoDialogs
from .files import init_files
from .i18n import available_languages, catalogs, current_language, detect_os_language, strings, t
from .security import init_security
from .state import Jobs, Selections

HTTP_ERRORS = {
    400: "error.bad_request",
    403: "error.forbidden",
    404: "error.page_not_found",
    405: "error.bad_request",
    413: "error.bad_request",
}


def create_app(
    backend: Backend | None = None,
    *,
    dialogs: Dialogs | None = None,
    port: int | None = None,
    launch_token: str | None = None,
    temp_root: Path | None = None,
) -> Flask:
    """Fabrique de l'application.

    backend      : None → backend par défaut (backend.default_backend) ;
                   les tests passent un FakeBackend.
    dialogs      : boîtes de dialogue natives (PywebviewDialogs dans la fenêtre,
                   NoDialogs en mode --no-window, un faux dans les tests).
    port         : port réel d'écoute, utilisé par le contrôle de l'en-tête Host.
                   None = mode test (client Flask, Host « localhost » sans port).
    launch_token : jeton attendu dans ?token= au premier accès (aléatoire si absent).
    temp_root    : dossier des fichiers temporaires (défaut : $CRYPTEASY_HOME/tmp,
                   sinon le dossier temporaire du système).
    """
    app = Flask(__name__)
    b = backend or default_backend()
    app.extensions["crypteasy_backend"] = b
    app.extensions["crypteasy_dialogs"] = dialogs or NoDialogs()
    app.extensions["crypteasy_selections"] = Selections()
    app.extensions["crypteasy_jobs"] = Jobs()
    app.config["SPEED"] = None  # octets/s, mesuré au démarrage (start_speed_measurement)
    # Aucun fichier ne transite par HTTP (Python lit et écrit directement sur le disque) :
    # les requêtes ne contiennent que de petits formulaires ou JSON.
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

    lang = b.load_settings().get("language")
    app.config["LANGUAGE"] = lang if lang in catalogs() else detect_os_language()

    init_security(app, port=port, launch_token=launch_token or secrets.token_urlsafe(32))
    init_files(app, temp_root)

    from .routes import api, contacts, decrypt, encrypt, home, keys

    for module in (home, keys, contacts, encrypt, decrypt, api):
        app.register_blueprint(module.bp)

    app.jinja_env.globals.update(t=t, languages=available_languages)

    @app.context_processor
    def inject_globals():
        return {
            "demo_mode": b.demo,
            "lang": current_language(),
            "csrf_value": generate_csrf,
            "js_strings": lambda: strings("js."),
        }

    def error_page(code: int, message: str):
        if request.path.startswith("/api/"):
            return {"error": message}, code
        return render_template("error.html", code=code, message=message, bare=code == 403), code

    @app.errorhandler(CSRFError)
    def csrf_error(_e):
        return error_page(400, t("error.csrf"))

    @app.errorhandler(HTTPException)
    def http_error(e: HTTPException):
        code = e.code or 500
        key = HTTP_ERRORS.get(code, "error.unexpected")
        if code == 400 and e.description == "bad-host":
            key = "error.bad_host"
        return error_page(code, t(key))

    return app


def start_speed_measurement(app: Flask) -> None:
    """Mesure la vitesse de chiffrement du PC en arrière-plan (§ 5.5)."""

    def run() -> None:
        try:
            app.config["SPEED"] = app.extensions["crypteasy_backend"].measure_speed()
        except Exception:  # l'estimation est un confort : sans elle, on affiche la taille seule
            app.config["SPEED"] = None

    threading.Thread(target=run, name="crypteasy-speed", daemon=True).start()
