"""État partagé entre requêtes : fichiers choisis et opérations en cours.

Sélections (SPEC § 8 : « nos routes prennent de vrais chemins de fichiers ») :
  un chemin n'existe que côté Python, choisi par une boîte de dialogue native. La page
  ne reçoit qu'un identifiant aléatoire. Aucune route n'accepte un chemin venant de
  la page : un site malveillant ne peut donc pas désigner un fichier du disque.

Tâches (§ 5.5) : chiffrer / déchiffrer tournent dans un thread ; la page demande
  l'avancement toutes les demi-secondes.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .errors import BadInput, NotFound, UIError

MAX_ITEMS = 200  # on garde les plus récents ; l'appli n'a qu'un utilisateur


@dataclass
class Selection:
    path: Path
    kind: str  # "file" | "folder" | "package" | "public-key" | "key-file"
    size: int = 0
    count: int = 0
    info: dict = field(default_factory=dict)


class Selections:
    def __init__(self) -> None:
        self._items: dict[str, Selection] = {}
        self._lock = threading.Lock()

    def add(self, selection: Selection) -> str:
        sid = secrets.token_urlsafe(16)
        with self._lock:
            self._items[sid] = selection
            while len(self._items) > MAX_ITEMS:
                self._items.pop(next(iter(self._items)))
        return sid

    def get(self, sid: str | None, *kinds: str) -> Selection:
        with self._lock:
            sel = self._items.get(sid or "")
        if sel is None or (kinds and sel.kind not in kinds):
            raise BadInput("error.choose_again")
        return sel


@dataclass
class Job:
    id: str
    kind: str  # "encrypt" | "decrypt"
    status: str = "running"  # running | done | error
    done: int = 0
    total: int = 0
    error: UIError | Exception | None = None
    result: dict = field(default_factory=dict)  # chemins, nom d'origine… (côté Python)
    workdir: Path | None = None  # dossier temporaire à supprimer
    started: float = field(default_factory=time.monotonic)

    @property
    def percent(self) -> int:
        if self.status == "done":
            return 100
        return int(self.done * 100 / self.total) if self.total else 0


class Jobs:
    def __init__(self) -> None:
        self._items: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(
        self,
        kind: str,
        total: int,
        work: Callable[[Job], dict],
        on_error: Callable[[Job], None] | None = None,
        workdir: Path | None = None,
    ) -> Job:
        """Lance work(job) dans un thread. work met à jour job.done et renvoie le résultat."""
        job = Job(id=secrets.token_urlsafe(16), kind=kind, total=total, workdir=workdir)
        with self._lock:
            self._items[job.id] = job
            while len(self._items) > MAX_ITEMS:
                self._items.pop(next(iter(self._items)))

        def run() -> None:
            try:
                job.result = work(job)
                job.status = "done"
            except Exception as exc:  # traduit à l'affichage par user_message
                job.error = exc
                job.status = "error"
                if on_error:
                    on_error(job)

        threading.Thread(target=run, name=f"crypteasy-{kind}", daemon=True).start()
        return job

    def get(self, job_id: str, kind: str | None = None) -> Job:
        with self._lock:
            job = self._items.get(job_id)
        if job is None or (kind and job.kind != kind):
            raise NotFound()
        return job

    def wait(self, job_id: str, timeout: float = 10) -> Job:
        """Pour les tests : attend la fin d'une tâche."""
        end = time.monotonic() + timeout
        job = self.get(job_id)
        while job.status == "running" and time.monotonic() < end:
            time.sleep(0.01)
        return job
