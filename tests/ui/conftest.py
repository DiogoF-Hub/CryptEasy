"""Outils communs aux tests de l'interface (Track B)."""
import io
import re

import pytest

from crypteasy.ui import create_app
from crypteasy.ui.fake_backend import FakeBackend

TOKEN = "jeton-de-test"
PW = "une phrase de passe assez longue"


@pytest.fixture
def backend():
    return FakeBackend()


@pytest.fixture
def app(backend, tmp_path):
    return create_app(backend, launch_token=TOKEN, temp_root=tmp_path / "tmp")


@pytest.fixture
def anon(app):
    """Client qui n'a PAS ouvert l'URL de lancement."""
    return app.test_client()


@pytest.fixture
def client(app):
    """Client authentifié comme le navigateur ouvert par __main__.py."""
    c = app.test_client()
    assert c.get(f"/?token={TOKEN}").status_code == 302
    return c


def csrf_of(client, path="/contacts"):
    """Jeton CSRF de la session, lu dans un formulaire de la page (ou de /contacts à défaut)."""
    for page in (path, "/contacts"):
        m = re.search(r'name="csrf_token" value="([^"]+)"', client.get(page).get_data(as_text=True))
        if m:
            return m.group(1)
    raise AssertionError("aucun formulaire avec jeton CSRF")


def post(client, path, data=None, files=None, page=None):
    """POST multipart avec le jeton CSRF récupéré sur `page` (par défaut : la même URL)."""
    data = {**(data or {}), "csrf_token": csrf_of(client, page or path)}
    for field, (content, name) in (files or {}).items():
        data[field] = (io.BytesIO(content), name)
    return client.post(path, data=data, content_type="multipart/form-data")


def make_identity(client, name="Perso", key_type="x25519", pw=PW, kdf="argon2id"):
    return post(client, "/cles", {"name": name, "key_type": key_type, "kdf": kdf,
                                  "password": pw, "password2": pw})


def html(resp):
    return resp.get_data(as_text=True)


def run_files(app):
    """Fichiers restant dans le dossier temporaire de ce lancement."""
    run_dir = app.config["CRYPTEASY_RUN_DIR"]
    return [p for p in run_dir.rglob("*") if p.is_file()] if run_dir.exists() else []
