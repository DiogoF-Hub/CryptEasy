"""Fichiers temporaires de l'interface (§ 6 : « plaintext left on disk »).

Chaque opération travaille dans son propre dossier « job », supprimé :
  - en cas d'erreur : tout de suite (bloc except/finally de la route) ;
  - en cas de succès : après l'envoi complet du téléchargement (response.call_on_close).
Au démarrage, les dossiers laissés par un lancement précédent (plantage) sont effacés.
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
import tempfile
import time
from pathlib import Path

from flask import Flask, current_app

from .errors import BadInput

STALE_AFTER_S = 3600  # dossiers d'un autre lancement plus vieux qu'1 h : restes d'un plantage
_FORBIDDEN = re.compile(r'[<>:"|?*\x00-\x1f\x7f]')
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
MAX_NAME_BYTES = 255


def temp_root() -> Path:
    home = os.environ.get("CRYPTEASY_HOME")
    return Path(home) / "tmp" if home else Path(tempfile.gettempdir()) / "crypteasy-tmp"


def init_files(app: Flask, root: Path | None = None) -> None:
    root = root or temp_root()
    root.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for old in root.glob("run-*"):
        try:
            if now - old.stat().st_mtime > STALE_AFTER_S:
                shutil.rmtree(old, ignore_errors=True)
        except OSError:
            pass
    run_dir = root / f"run-{secrets.token_hex(4)}"
    app.config["CRYPTEASY_RUN_DIR"] = run_dir


def new_job() -> Path:
    """Crée un dossier de travail privé pour une opération."""
    job = Path(current_app.config["CRYPTEASY_RUN_DIR"]) / secrets.token_hex(8)
    job.mkdir(parents=True, mode=0o700)
    return job


def remove_job(job: Path) -> None:
    shutil.rmtree(job, ignore_errors=True)


def remove_run_dir(app: Flask) -> None:
    shutil.rmtree(app.config["CRYPTEASY_RUN_DIR"], ignore_errors=True)


def safe_filename(raw: str | None) -> str:
    """Nom de fichier sans chemin ni caractère dangereux, utilisable sur tous les OS."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = _FORBIDDEN.sub("_", name).strip().rstrip(".")
    if name in ("", ".", ".."):
        raise BadInput("Nom de fichier invalide.")
    if len(name.encode("utf-8")) > MAX_NAME_BYTES:
        raise BadInput("Nom de fichier trop long (255 octets maximum).")
    if name.split(".")[0].upper() in _WINDOWS_RESERVED:
        name = "_" + name
    return name


def save_upload(storage, dest_dir: Path) -> Path:
    """Enregistre le fichier envoyé sous son nom assaini.

    Écriture par blocs : le fichier n'est jamais chargé entier en mémoire.
    """
    if storage is None or not storage.filename:
        raise BadInput("Choisissez un fichier.")
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / safe_filename(storage.filename)
    storage.save(path)
    return path
