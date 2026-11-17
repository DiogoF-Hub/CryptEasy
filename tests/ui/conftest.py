"""Outils communs aux tests de l'interface (Track B).

Les tests n'ouvrent jamais de fenêtre (la CI n'a pas d'écran, SPEC § 10) : les boîtes
de dialogue natives sont remplacées par FakeDialogs, qui renvoie les chemins préparés
par le test.

Chaque test qui utilise la fixture `backend` tourne DEUX fois (#21) :
- "demo" : FakeBackend, rien n'est chiffré ;
- "real" : RealBackend, le vrai core/ + keystore/, dans un dossier de données
  temporaire (CRYPTEASY_HOME). Seul le KDF est remplacé par un calcul rapide (les vrais
  réglages prennent environ 1 s chacun) ; test_real_backend.py teste le vrai KDF.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

from crypteasy.keystore import _core as keystore_core
from crypteasy.ui import create_app
from crypteasy.ui.fake_backend import FakeBackend

TOKEN = "jeton-de-test"  # noqa: S105 - faux jeton de lancement, propre aux tests
PW = "une phrase secrète assez longue"  # 30 caractères : niveau « très fort » côté phrase
PW12 = "douze carac."  # exactement 12 caractères


class FakeDialogs:
    """Boîtes de dialogue simulées : chaque appel consomme la prochaine réponse prévue."""

    def __init__(self) -> None:
        self.answers: list[Path | None] = []
        self.calls: list[tuple] = []
        self.revealed: list[Path] = []

    def _next(self, *call):
        self.calls.append(call)
        assert self.answers, f"boîte de dialogue inattendue : {call}"
        return self.answers.pop(0)

    def open_file(self, file_types=()):
        return self._next("open_file", tuple(file_types))

    def open_folder(self):
        return self._next("open_folder")

    def save_file(self, default_name, file_types=()):
        return self._next("save_file", default_name)

    def reveal(self, folder):
        self.revealed.append(folder)


def _fast_kdf_params(kdf: str, strength: str) -> dict:
    """Réglages acceptés par keystore/ (mêmes bornes que les vrais), PAS de la sécurité."""
    if kdf == "argon2id":
        return {"memory_kib": 65536, "iterations": 3, "parallelism": 4}
    return {"iterations": 600_000}


def _fast_lock_key(kdf: str, passphrase: bytes, salt: bytes, params: dict) -> bytes:
    material = kdf.encode() + salt + json.dumps(params, sort_keys=True).encode() + passphrase
    return hashlib.sha256(material).digest()


@pytest.fixture
def fast_kdf(monkeypatch):
    monkeypatch.setattr(keystore_core, "kdf_params", _fast_kdf_params)
    monkeypatch.setattr(keystore_core, "derive_lock_key", _fast_lock_key)


@pytest.fixture
def data_home(tmp_path, monkeypatch):
    """Dossier de données de keystore/ propre au test, jamais celui de l'utilisateur."""
    home = tmp_path / "home"
    monkeypatch.setenv("CRYPTEASY_HOME", str(home))
    return home


@pytest.fixture(params=["demo", "real"])
def backend(request):
    if request.param == "demo":
        return FakeBackend(speed=50e6)
    request.getfixturevalue("data_home")
    request.getfixturevalue("fast_kdf")
    from crypteasy.ui.real_backend import RealBackend

    return RealBackend()


@pytest.fixture
def dialogs():
    return FakeDialogs()


@pytest.fixture
def app(backend, dialogs, tmp_path):
    app = create_app(backend, dialogs=dialogs, launch_token=TOKEN, temp_root=tmp_path / "tmp")
    app.config.update(LANGUAGE="fr", I18N_STRICT=True, SPEED=50e6)
    return app


@pytest.fixture
def anon(app):
    """Client qui n'a PAS ouvert l'URL de lancement."""
    return app.test_client()


@pytest.fixture
def client(app):
    """Client authentifié comme la fenêtre ouverte par __main__.py."""
    c = app.test_client()
    assert c.get(f"/?token={TOKEN}").status_code == 302
    return c


@pytest.fixture
def files(tmp_path):
    """Dossier « disque de l'utilisateur » où les tests créent et enregistrent des fichiers."""
    d = tmp_path / "disque"
    d.mkdir()
    return d


def csrf_of(client) -> str:
    html = client.get("/contacts").get_data(as_text=True)
    return re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)


def post(client, path, data=None):
    return client.post(path, data={**(data or {}), "csrf_token": csrf_of(client)})


def api(client, path, payload=None, *, method="POST"):
    """Appel JSON comme le fait app.js (jeton CSRF dans l'en-tête X-CSRFToken)."""
    if method == "GET":
        return client.get(path)
    return client.post(path, json=payload or {}, headers={"X-CSRFToken": csrf_of(client)})


def html(resp) -> str:
    return resp.get_data(as_text=True)


def make_identity(client, name="Perso", level="strong", pw=PW, **fields):
    from crypteasy.ui.security_levels import PRESETS

    data = {"name": name, "level": level, **PRESETS.get(level, PRESETS["strong"])}
    data.update(passphrase=pw, passphrase2=pw)
    data.update(fields)
    return post(client, "/cles", data)


def run_files(app):
    """Fichiers restant dans le dossier temporaire de ce lancement."""
    run_dir = Path(app.config["CRYPTEASY_RUN_DIR"])
    return [p for p in run_dir.rglob("*") if p.is_file()] if run_dir.exists() else []
