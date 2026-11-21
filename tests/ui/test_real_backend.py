"""RealBackend (#21) : l'interface sur le vrai core/ + keystore/.

Tous les tests de l'interface tournent déjà aussi sur le vrai moteur (conftest : backend
"real"), avec un KDF rapide. Ici, ce qui n'existe qu'avec le vrai moteur :
- le scénario « terminé quand » de l'issue, avec le VRAI KDF et sans raccourci :
  générer une clé → chiffrer un fichier et un dossier → déchiffrer → mêmes octets,
  en X25519 et en RSA ;
- les erreurs propres à keystore/ (fichiers de données abîmés, noms refusés…) ;
- les clés faites ailleurs (OpenSSL), les réglages enregistrés sur le disque.
"""

import json
import zipfile

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, x25519

from crypteasy.ui import create_app, real_backend
from crypteasy.ui.backend import default_backend
from crypteasy.ui.files import temp_root
from crypteasy.ui.real_backend import RealBackend

from .conftest import PW, TOKEN, api, html, make_identity, post, run_files
from .test_encrypt_decrypt import WRONG_PW, choose, decrypt, encrypt, status

OPENSSL_PW = "mot de passe openssl"  # phrase d'une clé .pem faite « ailleurs »


@pytest.fixture
def backend(data_home):
    """Ce fichier teste seulement le vrai backend (pas de paramètre demo / real)."""
    return RealBackend()


def _tree(folder):
    return {
        p.relative_to(folder).as_posix(): p.read_bytes() if p.is_file() else None
        for p in sorted(folder.rglob("*"))
    }


# ------------------------------------------------------------- « terminé quand » (#21)
@pytest.mark.parametrize(
    ("level", "key_type"),
    [("strong", "x25519"), ("medium", "rsa-2048")],
    ids=["x25519-argon2id", "rsa-pbkdf2"],
)
def test_cle_puis_fichier_et_dossier_aller_retour_vrai_kdf(
    client, app, dialogs, files, backend, level, key_type
):
    # 1. Générer une clé (vrai KDF : Argon2id ou PBKDF2, préréglage « normal »)
    r = make_identity(client, name="Moi", level=level)
    assert r.status_code == 302, html(r)
    (me,) = backend.list_identities()
    assert me.key_type == key_type and me.protected and me.level == level
    assert "demo-banner" not in html(client.get("/"))  # pas de bandeau « Mode démo »

    # Ma clé publique, telle qu'un correspondant l'enregistrerait en contact
    dialogs.answers.append(files / "moi.pem")
    post(client, "/cles/exporter-publique", {"fingerprint": me.fingerprint})
    pem = (files / "moi.pem").read_text()
    post(client, "/contacts", {"name": "Moi (contact)", "keytext": pem})
    (contact,) = backend.list_contacts()
    assert contact.fingerprint == me.fingerprint  # même empreinte partout (§ 6.3)

    # 2. Chiffrer un fichier (plusieurs blocs de 64 Kio) et un dossier
    content = bytes(range(256)) * 1500  # 384 000 octets, octets de 0 à 255
    (files / "rapport.bin").write_bytes(content)
    encrypt(client, app, dialogs, files / "rapport.bin", files / "p1.zip", contact.fingerprint)
    folder = files / "projet"
    (folder / "src").mkdir(parents=True)
    (folder / "vide").mkdir()
    (folder / "lisez-moi é.txt").write_text("bonjour 🔒", encoding="utf-8")
    (folder / "src" / "data.bin").write_bytes(content[::-1])
    encrypt(client, app, dialogs, folder, files / "p2.zip", contact.fingerprint, what="folder")
    assert not list(temp_root().glob("run-zip-*"))  # le zip en clair du dossier a disparu

    # 3. Déchiffrer → les originaux reviennent, octet pour octet
    sel, job = decrypt(client, app, dialogs, files / "p1.zip", passphrase=PW)
    assert sel["key"]["name"] == "Moi"  # clé trouvée toute seule grâce à l'empreinte
    assert status(client, job)["name"] == "rapport.bin"  # nom d'origine, caché dans le paquet
    dialogs.answers.append(files / "rapport (déchiffré).bin")
    api(client, f"/api/taches/{job}/enregistrer", {"mode": "file"})
    assert (files / "rapport (déchiffré).bin").read_bytes() == content

    _sel, job = decrypt(client, app, dialogs, files / "p2.zip", passphrase=PW)
    assert status(client, job) | {"percent": 100} == {
        "status": "done", "percent": 100, "name": "projet", "is_folder": True,
    }  # fmt: skip
    out_parent = files / "Bureau"
    out_parent.mkdir()
    dialogs.answers.append(out_parent)
    r = api(client, f"/api/taches/{job}/enregistrer", {"mode": "extract"})
    assert r.get_json()["saved"] == str(out_parent / "projet")
    assert _tree(out_parent / "projet") == _tree(folder)
    assert run_files(app) == []  # aucun clair temporaire ne reste

    # Mauvaise phrase secrète, avec le vrai KDF
    _sel, job = decrypt(client, app, dialogs, files / "p1.zip", passphrase=WRONG_PW)
    assert status(client, job)["error"] == "Phrase secrète incorrecte pour cette clé."


def test_paquet_lisible_par_core_seul(client, app, dialogs, files, backend, fast_kdf):
    """Le paquet fait par l'interface est exactement le format § 5.1 de core/."""
    from crypteasy.core import package

    make_identity(client)
    (me,) = backend.list_identities()
    (files / "a.txt").write_text("x")
    encrypt(client, app, dialogs, files / "a.txt", files / "p.zip", me.fingerprint)
    header = package.read_package_info(files / "p.zip")
    assert header["recipient_fingerprint"] == me.fingerprint
    assert header["key_type"] == "x25519" and header["key_wrap"] == "x25519-hkdf-sha256"
    with zipfile.ZipFile(files / "p.zip") as zf:
        assert b"a.txt" not in zf.read("file.enc")  # le nom d'origine est chiffré


# ------------------------------------------------------------- clés faites ailleurs
def _openssl_like(kind):
    key = (
        x25519.X25519PrivateKey.generate()
        if kind == "x25519"
        else rsa.generate_private_key(public_exponent=65537, key_size=2048)
    )
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(OPENSSL_PW.encode()),
    )
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private, public


@pytest.mark.parametrize("kind", ["x25519", "rsa"])
def test_contact_et_fichier_de_cle_openssl(client, app, dialogs, files, backend, fast_kdf, kind):
    private, public = _openssl_like(kind)
    (files / "bob.key").write_bytes(private)
    post(client, "/contacts", {"name": "Bob", "keytext": public.decode()})
    (bob,) = backend.list_contacts()
    (files / "a.txt").write_text("pour Bob")
    encrypt(client, app, dialogs, files / "a.txt", files / "p.zip", bob.fingerprint)

    # Bob déchiffre avec son .pem d'OpenSSL, sans l'importer
    sel = choose(client, dialogs, "package", files / "p.zip")
    assert sel["key"] is None  # aucune de MES clés
    key_sel = choose(client, dialogs, "key-file", files / "bob.key")["id"]
    _sel, job = decrypt(
        client, app, dialogs, files / "p.zip", passphrase=WRONG_PW, key_selection=key_sel
    )
    assert status(client, job)["error"] == "Phrase secrète incorrecte pour cette clé."
    _sel, job = decrypt(
        client, app, dialogs, files / "p.zip", passphrase=OPENSSL_PW,
        key_selection=key_sel,
    )  # fmt: skip
    dialogs.answers.append(files / "b.txt")
    api(client, f"/api/taches/{job}/enregistrer", {"mode": "file"})
    assert (files / "b.txt").read_text() == "pour Bob"


def test_fichier_de_cle_d_un_autre(client, app, dialogs, files, backend, fast_kdf):
    make_identity(client)
    (me,) = backend.list_identities()
    (files / "a.txt").write_text("x")
    encrypt(client, app, dialogs, files / "a.txt", files / "p.zip", me.fingerprint)
    private, _public = _openssl_like("x25519")
    (files / "autre.key").write_bytes(private)
    key_sel = choose(client, dialogs, "key-file", files / "autre.key")["id"]
    _sel, job = decrypt(
        client, app, dialogs, files / "p.zip", passphrase=OPENSSL_PW,
        key_selection=key_sel,
    )  # fmt: skip
    assert status(client, job)["error"] == "Ce fichier n'a été chiffré pour aucune de vos clés."


def test_import_cle_openssl_puis_deja_importee(client, dialogs, files, backend, fast_kdf):
    private, _public = _openssl_like("rsa")
    (files / "cle.pem").write_bytes(private)
    form = {"name": "Importée", "current_passphrase": OPENSSL_PW,
            "passphrase": PW, "passphrase2": PW}  # fmt: skip
    dialogs.answers.append(files / "cle.pem")
    sel = api(client, "/api/choisir", {"what": "key-file"}).get_json()["id"]
    assert post(client, "/cles/importer", {**form, "key_selection": sel}).status_code == 302
    (imported,) = backend.list_identities()
    assert imported.key_type == "rsa-2048" and imported.protected

    dialogs.answers.append(files / "cle.pem")
    sel = api(client, "/api/choisir", {"what": "key-file"}).get_json()["id"]
    r = post(client, "/cles/importer", {**form, "name": "Encore", "key_selection": sel})
    assert "Cette clé est déjà enregistrée (« Importée »)." in html(r)


# ------------------------------------------------------------- erreurs propres à keystore/
def test_nom_avec_caractere_invisible_refuse(client, backend, fast_kdf):
    r = make_identity(client, name="Alice‮gpj.exe")  # inversion droite-gauche
    assert "Nom invalide" in html(r) and backend.list_identities() == []


def test_carnet_de_contacts_abime(client, data_home, backend):
    backend.list_contacts()  # crée le dossier de données
    (data_home / "contacts.json").write_text('{"version": 1, "contacts": [{"name": 1}]}')
    r = client.get("/contacts")
    assert r.status_code == 409
    assert "Vos clés ou vos contacts enregistrés sont illisibles" in html(r)


def test_dossier_de_cle_abime_n_empeche_pas_les_autres(client, data_home, backend, fast_kdf):
    make_identity(client, name="Bonne")
    make_identity(client, name="Abîmée")
    damaged = next(
        p for p in (data_home / "keys").iterdir()
        if json.loads((p / "info.json").read_text())["name"] == "Abîmée"
    )  # fmt: skip
    (damaged / "public.pem").write_text("modifié à la main")
    assert [k.name for k in backend.list_identities()] == ["Bonne"]
    assert client.get("/cles").status_code == 200


# ------------------------------------------------------------- réglages, démarrage, vitesse
def test_langue_enregistree_sur_le_disque(client, data_home, backend, tmp_path):
    post(client, "/langue", {"lang": "en"})
    assert json.loads((data_home / "settings.json").read_text())["language"] == "en"
    again = create_app(RealBackend(), launch_token=TOKEN, temp_root=tmp_path / "tmp2")
    assert again.config["LANGUAGE"] == "en"


def test_backend_par_defaut(monkeypatch, data_home):
    monkeypatch.delenv("CRYPTEASY_FAKE_BACKEND", raising=False)
    assert type(default_backend()) is RealBackend
    monkeypatch.setenv("CRYPTEASY_FAKE_BACKEND", "1")
    assert default_backend().demo is True


def test_mesure_de_vitesse(monkeypatch, backend):
    monkeypatch.setattr(real_backend, "SPEED_SAMPLE", 1024 * 1024)
    assert backend.measure_speed() > 1e6  # plus d'1 Mo/s sur n'importe quel PC
