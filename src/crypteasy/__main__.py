"""Point d'entrée : `python -m crypteasy` (et l'exécutable PyInstaller).

Contrat de lancement (IMPLEMENTATION.md § 3), partagé avec Track D :
  - écoute sur 127.0.0.1, port libre choisi par le système
  - 1re ligne de stdout, exactement : CRYPTEASY_URL=http://127.0.0.1:<port>/?token=<jeton>
  - CRYPTEASY_NO_BROWSER=1 : n'ouvre pas le navigateur (tests, CI, smoke test)
  - CRYPTEASY_HOME=<dossier> : dossier de données (keystore + fichiers temporaires)
  - Quitter : fermer la console (a) OU bouton « Quitter » de l'interface (b)
Serveur : waitress (pas le serveur de développement de Flask).
"""

from __future__ import annotations

import logging
import os
import secrets
import sys
import threading
import webbrowser

from waitress import create_server

from crypteasy.ui import MAX_UPLOAD_BYTES, create_app
from crypteasy.ui.files import remove_run_dir

HOST = "127.0.0.1"  # NE JAMAIS CHANGER (§ 6) : une PR qui modifie ceci doit être refusée


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s"
    )
    token = secrets.token_urlsafe(32)
    app = None

    # Le serveur est créé AVANT l'appli : port=0 laisse le système choisir un port
    # libre sans course entre « je trouve un port » et « je l'ouvre ». L'appli,
    # qui a besoin du port pour le contrôle du Host, est branchée juste après.
    server = create_server(
        lambda environ, start_response: app(environ, start_response),
        host=HOST,
        port=0,
        threads=4,
        max_request_body_size=MAX_UPLOAD_BYTES
        + 1024**2,  # marge multipart ; Flask renvoie le 413 lisible
    )
    port = server.effective_port

    def shutdown() -> None:
        def stop() -> None:
            remove_run_dir(app)
            os._exit(0)

        threading.Timer(0.5, stop).start()  # laisse partir la page « CryptEasy est fermé »

    app = create_app(port=port, launch_token=token, shutdown=shutdown)

    url = f"http://{HOST}:{port}/?token={token}"
    print(f"CRYPTEASY_URL={url}", flush=True)
    print(
        "CryptEasy est ouvert dans votre navigateur.\n"
        "Pour quitter : bouton « Quitter » de l'interface, ou fermez cette fenêtre.",
        file=sys.stderr,
        flush=True,
    )

    if os.environ.get("CRYPTEASY_NO_BROWSER") != "1":
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()

    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        remove_run_dir(app)


if __name__ == "__main__":
    main()
