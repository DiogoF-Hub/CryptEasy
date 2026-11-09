"""Point d'entrée : `python -m crypteasy` (et l'exécutable PyInstaller).

SPEC_TECHNIQUE § 2.2 : double-clic → une fenêtre CryptEasy (pywebview), pas de
navigateur ni de console. Fermer la fenêtre quitte l'application.

- Flask (servi par waitress) écoute uniquement sur 127.0.0.1, sur un port choisi par
  le système ; la fenêtre ouvre http://127.0.0.1:<port>/?token=<jeton>.
- 1re ligne de stdout : CRYPTEASY_URL=<adresse>, pour le test de fumée.
- --no-window (ou CRYPTEASY_NO_WINDOW=1 / CRYPTEASY_NO_BROWSER=1) : démarre seulement
  Flask, pour la CI qui n'a pas d'écran (§ 10). Ctrl+C pour arrêter.
- CRYPTEASY_HOME=<dossier> : dossier de données (tests, démo).
"""

from __future__ import annotations

import argparse
import logging
import os
import secrets
import sys
import threading
import webbrowser

from waitress import create_server

from crypteasy.ui import create_app, start_speed_measurement
from crypteasy.ui.dialogs import NoDialogs, PywebviewDialogs
from crypteasy.ui.files import remove_run_dir
from crypteasy.ui.i18n import t

HOST = "127.0.0.1"  # NE JAMAIS CHANGER (§ 8) : une PR qui modifie ceci doit être refusée
WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"
MAX_REQUEST_BYTES = 1024 * 1024  # l'API n'échange que de petits JSON : aucun fichier ne transite


def _say(text: str, *, stdout: bool = False) -> None:
    """Exe sans console : sys.stdout / sys.stderr peuvent ne pas exister."""
    stream = sys.stdout if stdout else sys.stderr
    if stream is not None:
        print(text, file=stream, flush=True)


def _message_box(title: str, text: str) -> None:
    """Message d'erreur natif sous Windows (quand la fenêtre ne peut pas s'ouvrir)."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)  # icône « erreur »
    else:
        _say(f"{title}\n{text}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="crypteasy", description="CryptEasy")
    parser.add_argument(
        "--no-window", action="store_true", help="démarre seulement Flask (CI, test de fumée)"
    )
    args = parser.parse_args(argv)
    if (
        os.environ.get("CRYPTEASY_NO_WINDOW") == "1"
        or os.environ.get("CRYPTEASY_NO_BROWSER") == "1"
    ):
        args.no_window = True
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    token = secrets.token_urlsafe(32)
    app = None

    # Serveur créé AVANT l'appli : port=0 laisse le système choisir un port libre, sans
    # course entre « trouver un port » et « l'ouvrir ». L'appli (qui a besoin du port pour
    # le contrôle du Host) est branchée juste après.
    server = create_server(
        lambda environ, start_response: app(environ, start_response),
        host=HOST,
        port=0,
        threads=6,
        max_request_body_size=MAX_REQUEST_BYTES,
    )
    port = server.effective_port
    dialogs = NoDialogs() if args.no_window else PywebviewDialogs()
    app = create_app(port=port, launch_token=token, dialogs=dialogs)
    start_speed_measurement(app)

    url = f"http://{HOST}:{port}/?token={token}"
    _say(f"CRYPTEASY_URL={url}", stdout=True)

    try:
        if args.no_window:
            _say("CryptEasy (sans fenêtre) : Ctrl+C pour arrêter.")
            try:
                server.run()
            except KeyboardInterrupt:
                pass
            return 0
        return _run_window(server, url, app.config["LANGUAGE"])
    finally:
        remove_run_dir(app)


def _run_window(server, url: str, lang: str) -> int:
    try:
        import webview
    except ImportError:
        _message_box("CryptEasy", t("app.window_error", lang))
        return 1

    threading.Thread(target=server.run, name="crypteasy-server", daemon=True).start()
    window = webview.create_window(
        "CryptEasy", url, width=1120, height=800, min_size=(480, 560), text_select=True
    )
    renderer = {}

    def on_initialized(engine: str) -> bool:
        # Windows sans WebView2 : pywebview se rabattrait sur l'ancien moteur d'Internet
        # Explorer, incapable d'afficher nos pages. On refuse d'ouvrir la fenêtre (F7).
        renderer["engine"] = engine
        return engine != "mshtml"

    window.events.initialized += on_initialized
    try:
        webview.start(private_mode=True)  # bloque jusqu'à la fermeture de la fenêtre
    except Exception:  # pas de moteur web utilisable (Linux sans WebKit2GTK…)
        logging.getLogger(__name__).exception("Impossible d'ouvrir la fenêtre")
        _message_box("CryptEasy", t("app.window_error", lang))
        return 1
    if renderer.get("engine") == "mshtml":
        _message_box(t("app.webview2_title", lang), t("app.webview2_text", lang))
        webbrowser.open(WEBVIEW2_URL)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
