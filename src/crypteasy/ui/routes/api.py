"""API JSON appelée par la page (static/app.js) : boîtes de dialogue natives, chiffrement /
déchiffrement en arrière-plan, progression, enregistrement, extraction.

Sécurité (SPEC § 8) : POST protégés par CSRF (en-tête X-CSRFToken) + jeton de lancement
+ contrôle du Host. Aucune route n'accepte de chemin : la page ne manipule que des
identifiants de sélection ou de tâche, les chemins restent côté Python (state.py).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from ..errors import BadInput, FileExists, NoMatchingKey, user_message
from ..files import (
    BIG_FILE,
    describe,
    estimate_seconds,
    move_no_overwrite,
    new_job_dir,
    remove_dir,
    safe_filename,
)
from ..i18n import format_duration, format_size, t
from ..security_levels import CIPHERS
from ..state import Job, Selection
from . import backend, dialogs, jobs, selections

bp = Blueprint("api", __name__, url_prefix="/api")


def _payload() -> dict:
    return request.get_json(silent=True) or {}


def _error(exc: Exception, status: int = 400):
    return jsonify(error=user_message(exc)), status


def _size_info(size: int, count: int, is_folder: bool) -> dict:
    """Taille, nombre de fichiers et temps estimé, déjà formatés (§ 5.5)."""
    seconds = estimate_seconds(size, current_app.config.get("SPEED"), is_folder)
    return {
        "size": format_size(size),
        "files": count if is_folder else None,
        "estimate": format_duration(seconds) if seconds is not None else None,
        "big": size > BIG_FILE,
    }


# ------------------------------------------------------------------ choisir (boîtes natives)
@bp.post("/choisir")
def choose():
    what = _payload().get("what")
    d = dialogs()
    try:
        if what == "folder":
            path = d.open_folder()
        elif what == "file":
            path = d.open_file()
        elif what == "package":
            path = d.open_file([t("dialog.types.package"), t("dialog.types.all")])
        elif what == "public-key":
            path = d.open_file([t("dialog.types.public_key"), t("dialog.types.all")])
        elif what == "key-file":
            path = d.open_file([t("dialog.types.private_key"), t("dialog.types.all")])
        else:
            raise BadInput()
        if path is None:
            return jsonify(cancelled=True)
        if what in ("file", "folder"):
            return jsonify(_choose_source(path, what))
        if what == "package":
            return jsonify(_choose_package(path))
        if not path.is_file():
            raise BadInput("error.choose_again")
        sid = selections().add(Selection(path, what))
        return jsonify(id=sid, name=path.name)
    except Exception as exc:  # traduit en message par user_message
        return _error(exc)


def _choose_source(path: Path, kind: str) -> dict:
    if (kind == "folder" and not path.is_dir()) or (kind == "file" and not path.is_file()):
        raise BadInput("error.choose_again")
    size, count = describe(path)
    sid = selections().add(Selection(path, kind, size, count))
    return {"id": sid, "name": path.name, "is_folder": kind == "folder",
            **_size_info(size, count, kind == "folder")}  # fmt: skip


def _choose_package(path: Path) -> dict:
    """Lit l'en-tête et trouve toute seule la bonne clé (§ 5.3 étape 3)."""
    info = backend().inspect_package(path)
    size = path.stat().st_size
    key = next(
        (k for k in backend().list_identities() if k.fingerprint == info.recipient_fingerprint),
        None,
    )
    sid = selections().add(
        Selection(path, "package", size, 1, {"fingerprint": info.recipient_fingerprint})
    )
    return {
        "id": sid,
        "name": path.name,
        "is_folder": info.is_folder,
        **_size_info(size, 1, False),
        "key": (
            {
                "name": key.name,
                "kind": key.kind,
                "fingerprint": key.fingerprint,
                "protected": key.protected,
            }  # fmt: skip
            if key
            else None
        ),
        "no_key_message": None if key else user_message(NoMatchingKey()),
    }


# ------------------------------------------------------------------ chiffrer
@bp.post("/chiffrer")
def encrypt():
    data = _payload()
    try:
        source = selections().get(data.get("selection"), "file", "folder")
        recipient = data.get("recipient") or ""
        known = {k.fingerprint for k in [*backend().list_contacts(), *backend().list_identities()]}
        if recipient not in known:
            raise BadInput("error.choose_recipient")
        cipher = data.get("cipher") or "aes-256-gcm"
        if cipher not in CIPHERS:
            raise BadInput("error.unknown_setting")
        # Nom neutre par défaut : ne révèle rien du contenu (F4)
        default = f"crypteasy_{datetime.now():%Y-%m-%d_%H%M}.zip"
        dst = dialogs().save_file(default, [t("dialog.types.package")])
        if dst is None:
            return jsonify(cancelled=True)
        if dst.suffix.lower() != ".zip":
            dst = dst.with_name(safe_filename(dst.name + ".zip"))
        if dst.exists():
            raise FileExists(name=dst.name)
    except Exception as exc:  # traduit en message par user_message
        return _error(exc)

    def work(job: Job) -> dict:
        def progress(done: int, total: int) -> None:
            job.done, job.total = done, total

        backend().encrypt(source.path, dst, recipient, cipher, progress)
        return {"saved": dst, "folder": dst.parent}

    job = jobs().start("encrypt", source.size, _with_backend(work))
    return jsonify(job=job.id)


# ------------------------------------------------------------------ déchiffrer
@bp.post("/dechiffrer")
def decrypt():
    data = _payload()
    try:
        package = selections().get(data.get("selection"), "package")
        key_file = None
        identity = None
        if data.get("key_selection"):
            key_file = selections().get(data["key_selection"], "key-file").path
        else:
            identity = package.info["fingerprint"]
            if identity not in {k.fingerprint for k in backend().list_identities()}:
                raise NoMatchingKey()
        passphrase = (data.get("passphrase") or "").encode("utf-8") or None
        workdir = new_job_dir()  # fichier à moitié déchiffré : temporaire (§ 8)
    except Exception as exc:  # traduit en message par user_message
        return _error(exc)

    def work(job: Job) -> dict:
        def progress(done: int, total: int) -> None:
            job.done, job.total = done, total

        out = backend().decrypt(
            package.path,
            workdir / "out",
            passphrase,
            progress,
            identity=identity,
            key_file=key_file,
        )
        is_folder = backend().inspect_package(package.path).is_folder
        return {"plain": out, "name": out.name, "is_folder": is_folder}

    job = jobs().start(
        "decrypt",
        package.size,
        _with_backend(work),
        on_error=lambda j: remove_dir(j.workdir),
        workdir=workdir,
    )
    return jsonify(job=job.id)


def _with_backend(work):
    """Les threads n'ont pas de contexte Flask : on capture le backend avant."""
    app = current_app._get_current_object()

    def run(job: Job) -> dict:
        with app.app_context():
            return work(job)

    return run


# ------------------------------------------------------------------ suivi des tâches
@bp.get("/taches/<job_id>")
def status(job_id: str):
    try:
        job = jobs().get(job_id)
    except Exception as exc:  # traduit en message par user_message
        return _error(exc, 404)
    body = {"status": job.status, "percent": job.percent}
    if job.status == "error":
        body["error"] = user_message(job.error)
    elif job.status == "done":
        r = job.result
        is_folder = r.get("is_folder", False)
        name = r.get("name") or ""
        # un dossier déchiffré arrive sous forme de zip : on affiche le nom du dossier
        body["name"] = name.removesuffix(".zip") if is_folder else name
        body["is_folder"] = is_folder
        if "saved" in r:
            body["saved"] = str(r["saved"])
    return jsonify(body)


@bp.post("/taches/<job_id>/enregistrer")
def save(job_id: str):
    """Fin du déchiffrement : « enregistrer sous » (fichier, ou dossier gardé en .zip)
    ou extraction dans un nouveau dossier (§ 5.3 étape 8)."""
    mode = _payload().get("mode")
    try:
        job = jobs().get(job_id, "decrypt")
        if job.status != "done" or "plain" not in job.result:
            raise BadInput("error.nothing_to_save")
        plain: Path = job.result["plain"]
        if mode == "extract":
            if not job.result["is_folder"]:
                raise BadInput()
            parent = dialogs().open_folder()
            if parent is None:
                return jsonify(cancelled=True)
            folder = backend().extract_folder(plain, parent)
            saved, reveal = folder, folder
        elif mode in ("file", "zip"):
            dst = dialogs().save_file(plain.name)
            if dst is None:
                return jsonify(cancelled=True)
            move_no_overwrite(plain, dst)
            saved, reveal = dst, dst.parent
        else:
            raise BadInput()
    except Exception as exc:  # traduit en message par user_message
        return _error(exc)
    remove_dir(job.workdir)  # le clair temporaire disparaît dès qu'il est enregistré
    job.result = {"saved": saved, "folder": reveal, "name": job.result["name"],
                  "is_folder": job.result["is_folder"]}  # fmt: skip
    return jsonify(saved=str(saved))


@bp.post("/taches/<job_id>/abandonner")
def discard(job_id: str):
    try:
        job = jobs().get(job_id)
    except Exception as exc:  # traduit en message par user_message
        return _error(exc, 404)
    remove_dir(job.workdir)
    job.result = {}
    return jsonify(ok=True)


@bp.post("/taches/<job_id>/ouvrir-dossier")
def reveal(job_id: str):
    """Ouvre le dossier du résultat dans l'Explorateur / le Finder. Le dossier vient
    du résultat de la tâche (côté Python), jamais de la page."""
    try:
        job = jobs().get(job_id)
        folder = job.result.get("folder")
        if folder is None or not Path(folder).is_dir():
            raise BadInput("error.nothing_to_save")
        dialogs().reveal(Path(folder))
    except Exception as exc:  # traduit en message par user_message
        return _error(exc)
    return jsonify(ok=True)
