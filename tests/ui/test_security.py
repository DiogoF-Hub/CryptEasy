"""Middleware § 6 : Host, jeton de lancement, CSRF, cookies, en-têtes (porte MS1)."""
import pytest

from crypteasy.ui import create_app
from crypteasy.ui.fake_backend import FakeBackend

from .conftest import TOKEN, csrf_of, html


# ---------------------------------------------------------------- Host (DNS rebinding)
def test_mauvais_host_rejete(client):
    r = client.get("/", base_url="http://attaquant.example/")
    assert r.status_code == 400


def test_host_avec_port_reel(tmp_path):
    app = create_app(FakeBackend(), port=48123, launch_token=TOKEN, temp_root=tmp_path)
    c = app.test_client()
    for host in ("127.0.0.1:48123", "localhost:48123"):
        assert c.get(f"/?token={TOKEN}", base_url=f"http://{host}/").status_code == 302
    for host in ("127.0.0.1:9999", "127.0.0.1", "rebind.example:48123"):
        assert c.get("/", base_url=f"http://{host}/").status_code == 400


def test_cookie_nomme_par_port(tmp_path):
    app = create_app(FakeBackend(), port=48123, launch_token=TOKEN, temp_root=tmp_path)
    assert app.config["SESSION_COOKIE_NAME"] == "crypteasy_48123"


# ---------------------------------------------------------------- jeton de lancement
@pytest.mark.parametrize("path", ["/", "/cles", "/contacts", "/chiffrer", "/dechiffrer"])
def test_sans_jeton_403(anon, path):
    r = anon.get(path)
    assert r.status_code == 403 and "Accès refusé" in html(r)


def test_mauvais_jeton_403(anon):
    assert anon.get("/?token=faux").status_code == 403


def test_jeton_ouvre_la_session_et_disparait_de_l_url(anon):
    r = anon.get(f"/cles?token={TOKEN}")
    assert r.status_code == 302 and r.headers["Location"] == "/cles"
    assert anon.get("/cles").status_code == 200


def test_fichiers_statiques_publics(anon):
    assert anon.get("/static/style.css").status_code == 200


# ---------------------------------------------------------------- CSRF
@pytest.mark.parametrize("path", ["/cles", "/contacts", "/contacts/supprimer",
                                  "/chiffrer", "/dechiffrer"])
def test_post_sans_csrf_400(client, path):
    r = client.post(path, data={"name": "x"})
    assert r.status_code == 400 and "Jeton de sécurité" in html(r)


def test_post_avec_mauvais_csrf_400(client):
    csrf_of(client)  # la session a un jeton…
    assert client.post("/contacts", data={"csrf_token": "faux"}).status_code == 400


# ---------------------------------------------------------------- cookies et en-têtes
def test_cookie_de_session(anon):
    r = anon.get(f"/?token={TOKEN}")
    cookie = r.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie


def test_entetes_securite(client):
    h = client.get("/").headers
    assert "default-src 'self'" in h["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in h["Content-Security-Policy"]
    assert h["X-Frame-Options"] == "DENY"
    assert h["Cache-Control"] == "no-store"
    assert h["Referrer-Policy"] == "no-referrer"


def test_secret_different_a_chaque_lancement(tmp_path):
    a = create_app(FakeBackend(), temp_root=tmp_path)
    b = create_app(FakeBackend(), temp_root=tmp_path)
    assert a.config["SECRET_KEY"] != b.config["SECRET_KEY"]
    assert a.config["LAUNCH_TOKEN"] != b.config["LAUNCH_TOKEN"]
