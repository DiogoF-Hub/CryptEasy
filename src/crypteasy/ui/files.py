"""Fichiers et dossiers côté interface (SPEC § 5.5, § 8).

- Fichiers temporaires : un dossier par lancement (run-xxxx), un sous-dossier par
  opération, supprimés après chaque action (y compris en cas d'erreur) et au démarrage.
- Noms de fichiers assainis, jamais d'écrasement.
- Taille d'un fichier ou d'un dossier, estimation du temps.
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

from .errors import BadInput, FileExists

# Au démarrage, on supprime les dossiers temporaires dont aucun fichier n'a bougé depuis
# ce délai : restes d'un lancement précédent (plantage). Les dossiers d'une autre
# instance encore ouverte (double-clic sur l'exe) sont épargnés.
STALE_AFTER_S = 3600
_FORBIDDEN = re.compile(r'[<>:"|?*\x00-\x1f\x7f]')
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}  # fmt: skip
MAX_NAME_BYTES = 255
FALLBACK_NAME = "decrypted_file"
BIG_FILE = 4 * 1000**3  # au-delà : « fichier volumineux, cela peut prendre quelques minutes »
FOLDER_MARGIN = 1.3  # le zip d'un dossier prend aussi du temps (§ 5.5)


# ----------------------------------------------------------------- temporaires
def temp_root() -> Path:
    home = os.environ.get("CRYPTEASY_HOME")
    return Path(home) / "tmp" if home else Path(tempfile.gettempdir()) / "crypteasy-tmp"


def _last_activity(folder: Path) -> float:
    times = [folder.stat().st_mtime]
    for path in folder.rglob("*"):
        try:
            times.append(path.stat().st_mtime)
        except OSError:
            pass
    return max(times)


def init_files(app: Flask, root: Path | None = None) -> None:
    root = root or temp_root()
    root.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for old in root.glob("run-*"):
        try:
            if now - _last_activity(old) > STALE_AFTER_S:
                shutil.rmtree(old, ignore_errors=True)
        except OSError:
            pass
    app.config["CRYPTEASY_RUN_DIR"] = root / f"run-{secrets.token_hex(4)}"


def new_job_dir() -> Path:
    """Dossier de travail privé pour une opération."""
    job = Path(current_app.config["CRYPTEASY_RUN_DIR"]) / secrets.token_hex(8)
    job.mkdir(parents=True, mode=0o700)
    return job


def remove_dir(path: Path | None) -> None:
    if path is not None:
        shutil.rmtree(path, ignore_errors=True)


def remove_run_dir(app: Flask) -> None:
    remove_dir(Path(app.config["CRYPTEASY_RUN_DIR"]))


# ----------------------------------------------------------------- noms
def safe_filename(raw: str | None) -> str:
    """Nom de fichier sans chemin ni caractère dangereux, valable sur tous les OS (§ 8)."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = _FORBIDDEN.sub("_", name).strip().rstrip(".")
    if name in ("", ".", ".."):
        raise BadInput("error.bad_filename")
    if len(name.encode("utf-8")) > MAX_NAME_BYTES:
        raise BadInput("error.filename_too_long")
    if name.split(".")[0].upper() in _WINDOWS_RESERVED:
        name = "_" + name
    return name


def original_name(raw: str | None) -> str:
    """Nom d'origine lu dans un paquet : nettoyé, ou « decrypted_file » (§ 8)."""
    if raw is None or "\x00" in raw:
        return FALLBACK_NAME
    try:
        return safe_filename(raw)
    except BadInput:
        return FALLBACK_NAME


def unique_child(parent: Path, name: str) -> Path:
    """parent/name, ou « name (2) », « name (3) »… si le nom est pris (§ 5.4)."""
    candidate = parent / name
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 2
    while candidate.exists():
        candidate = parent / f"{stem} ({n}){suffix}"
        n += 1
    return candidate


def move_no_overwrite(src: Path, dst: Path) -> None:
    """Déplace src vers dst, jamais par-dessus un fichier existant (§ 8)."""
    if dst.exists():
        raise FileExists(name=dst.name)
    try:
        os.link(src, dst)  # échoue si dst existe : pas de fenêtre de course
        src.unlink()
    except FileExistsError as exc:
        raise FileExists(name=dst.name) from exc
    except OSError:
        # autre disque ou système sans liens durs : copie puis suppression
        with open(src, "rb") as fin, open(dst, "xb") as fout:
            shutil.copyfileobj(fin, fout, 1024 * 1024)
        src.unlink()


# ----------------------------------------------------------------- tailles
def describe(path: Path) -> tuple[int, int]:
    """(taille totale en octets, nombre de fichiers). Les liens symboliques sont ignorés,
    comme au moment de zipper le dossier (§ 5.4)."""
    if path.is_symlink():
        return 0, 0
    if path.is_file():
        return path.stat().st_size, 1
    size = count = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
        for name in files:
            f = Path(root) / name
            if not f.is_symlink():
                try:
                    size += f.stat().st_size
                    count += 1
                except OSError:
                    pass
    return size, count


def estimate_seconds(size: int, speed: float | None, is_folder: bool = False) -> float | None:
    """Temps estimé (§ 5.5) ; None tant que la vitesse du PC n'est pas mesurée."""
    if not speed:
        return None
    return size / speed * (FOLDER_MARGIN if is_folder else 1.0)
