"""Lancement (SPEC § 2.2, § 10) : `python -m crypteasy --no-window` dans un vrai processus,
comme le test de fumée de la CI (qui n'a pas d'écran)."""

import http.client
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

import pytest

from crypteasy.__main__ import parse_args

SRC = Path(__file__).resolve().parents[2] / "src"


def test_options_sans_fenetre(monkeypatch):
    monkeypatch.delenv("CRYPTEASY_NO_WINDOW", raising=False)
    monkeypatch.delenv("CRYPTEASY_NO_BROWSER", raising=False)
    assert parse_args([]).no_window is False
    assert parse_args(["--no-window"]).no_window is True
    monkeypatch.setenv("CRYPTEASY_NO_BROWSER", "1")  # variable du DEV_README / make smoke
    assert parse_args([]).no_window is True


@pytest.fixture
def running(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(SRC), "CRYPTEASY_FAKE_BACKEND": "1",
           "CRYPTEASY_HOME": str(tmp_path)}  # fmt: skip
    proc = subprocess.Popen(  # noqa: S603 - lance notre propre module, sans shell
        [sys.executable, "-m", "crypteasy", "--no-window"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    first_line = proc.stdout.readline().strip()
    yield proc, first_line
    proc.kill()
    proc.wait(10)


def _get(port, path, host=None, cookie=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Host": host or f"127.0.0.1:{port}"}
    if cookie:
        headers["Cookie"] = cookie
    conn.request("GET", path, headers=headers)
    resp = conn.getresponse()
    return resp.status, resp.getheader("Set-Cookie"), resp.read().decode()


def test_contrat_de_lancement(running):
    _proc, first_line = running
    m = re.fullmatch(r"CRYPTEASY_URL=http://127\.0\.0\.1:(\d+)/\?token=([\w-]{40,})", first_line)
    assert m, first_line
    port = int(m.group(1))
    query = "/?" + urllib.parse.urlsplit(first_line.removeprefix("CRYPTEASY_URL=")).query

    # Host étranger (DNS rebinding) → 400, même avec le bon jeton
    assert _get(port, query, host=f"rebind.example:{port}")[0] == 400
    # Sans jeton → 403
    assert _get(port, "/")[0] == 403
    # Avec le jeton : session ouverte, puis les pages répondent
    status, cookie, _ = _get(port, query)
    assert status == 302 and cookie
    status, _, page = _get(port, "/chiffrer", cookie=cookie.split(";")[0])
    assert status == 200 and ("Mode démo" in page or "Demo mode" in page)
