"""Un blueprint par écran. Aucune route n'importe core/ ou keystore/ : tout passe par le Backend."""

from __future__ import annotations

import re

from flask import current_app, send_file

from ..backend import Backend
from ..errors import BadInput

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
MAX_LABEL = 64


def backend() -> Backend:
    return current_app.extensions["crypteasy_backend"]


def clean_label(raw: str | None, what: str = "Le nom") -> str:
    """Nom de clé ou de contact : 1 à 64 caractères, pas de caractère de contrôle.
    (L'échappement HTML est fait par Jinja ; on ne met jamais |safe.)"""
    label = _CONTROL.sub("", raw or "").strip()
    if not label:
        raise BadInput(f"{what} est obligatoire.")
    if len(label) > MAX_LABEL:
        raise BadInput(f"{what} ne doit pas dépasser {MAX_LABEL} caractères.")
    return label


def attachment(path_or_file, download_name: str, cleanup=None):
    """Réponse de téléchargement ; `cleanup` est appelé une fois l'envoi terminé."""
    resp = send_file(
        path_or_file,
        as_attachment=True,
        download_name=download_name,
        mimetype="application/octet-stream",
        conditional=False,
        etag=False,
    )
    if cleanup is not None:
        # PIÈGE (vérifié) : send_file active direct_passthrough, et Werkzeug renvoie alors
        # le fichier brut au serveur SANS appeler les fonctions call_on_close : le
        # fichier temporaire ne serait jamais supprimé. On désactive le passthrough
        # pour que close() ferme le fichier PUIS appelle cleanup.
        resp.direct_passthrough = False
        resp.call_on_close(cleanup)
    return resp
