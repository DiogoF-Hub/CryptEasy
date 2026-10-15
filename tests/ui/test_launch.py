"""Bouton Quitter et contrat de lancement § 3 (python -m crypteasy dans un vrai processus)."""
import http.client
import http.cookiejar
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from crypteasy.ui import create_app
from crypteasy.ui.fake_backend import FakeBackend

from .conftest import TOKEN, csrf_of, html

SRC = Path(__file__).resolve().parents[2] / "src"


# ---------------------------------------------------------------- bouton Quitter
@pytest.fixture
def quit_calls(tmp_path):
    calls = []
    app = create_app(FakeBackend(), launch_token=TOKEN, temp_root=tmp_path,
                     shutdown=lambda: calls.append(1))
    c = app.test_client()
    c.get(f"/?token={TOKEN}")
    return c, calls


def test_quitter(quit_calls):
    c, calls = quit_calls
    r = c.post("/quitter", data={"csrf_token": csrf_of(c)})
    assert r.status_code == 200 and "CryptEasy est fermé" in html(r)
    assert calls == [1]


def test_quitter_sans_csrf_refuse(quit_calls):
    c, calls = quit_calls
    assert c.post("/quitter").status_code == 400
    assert calls == []


def test_quitter_est_un_post(quit_calls):
    c, calls = quit_calls
    assert c.get("/quitter").status_code == 405
    assert calls == []


# ---------------------------------------------------------------- processus réel
@pytest.fixture
def running(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(SRC), "CRYPTEASY_FAKE_BACKEND": "1",
           "CRYPTEASY_NO_BROWSER": "1", "CRYPTEASY_HOME": str(tmp_path)}
    proc = subprocess.Popen([sys.executable, "-m", "crypteasy"], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    first_line = proc.stdout.readline().strip()
    yield proc, first_line, tmp_path
    if proc.poll() is None:
        proc.kill()
    proc.wait(5)


def test_contrat_de_lancement(running):
    proc, first_line, home = running
    m = re.fullmatch(r"CRYPTEASY_URL=http://127\.0\.0\.1:(\d+)/\?token=([\w-]{40,})", first_line)
    assert m, first_line
    port = int(m.group(1))
    url = first_line.removeprefix("CRYPTEASY_URL=")

    # Host étranger (DNS rebinding) → 400, même avec le bon jeton
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/?" + urllib.parse.urlsplit(url).query,
                 headers={"Host": f"rebind.example:{port}"})
    assert conn.getresponse().status == 400

    # Sans jeton → 403
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5)
    assert err.value.code == 403

    # Avec le jeton : session ouverte, puis Quitter arrête le processus
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    page = opener.open(url, timeout=5).read().decode()
    assert "Chiffrez vos fichiers" in page
    token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    closed = opener.open(f"http://127.0.0.1:{port}/quitter",
                         data=urllib.parse.urlencode({"csrf_token": token}).encode(),
                         timeout=5).read().decode()
    assert "CryptEasy est fermé" in closed
    assert proc.wait(timeout=10) == 0
    # Le dossier temporaire de ce lancement a été supprimé
    assert list((home / "tmp").glob("run-*")) == []
