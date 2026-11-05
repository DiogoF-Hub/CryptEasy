"""Outils communs aux tests de l'interface (Track B).

Les tests n'ouvrent jamais de fenêtre (la CI n'a pas d'écran, SPEC § 10) : les boîtes
de dialogue natives sont remplacées par FakeDialogs, qui renvoie les chemins préparés
par le test.
"""

import re
from pathlib import Path

import pytest

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


@pytest.fixture
def backend():
    return FakeBackend(speed=50e6)


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
