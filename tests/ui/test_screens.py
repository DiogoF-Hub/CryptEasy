"""Écrans sur le FakeBackend (SPEC_TECHNIQUE § 3, § 7) : parcours, messages F7,
fichiers temporaires, noms de fichiers."""

import io
import json
import zipfile

import pytest

from crypteasy.ui.errors import BadInput
from crypteasy.ui.files import safe_filename

from .conftest import PW, html, make_identity, post, run_files

FILE_PW = "mot de passe du fichier"
WRONG_FILE_PW = "faux"
CHECKED = "1"  # valeur envoyée par une case à cocher


@pytest.mark.parametrize("path", ["/", "/cles", "/contacts", "/chiffrer", "/dechiffrer", "/info"])
def test_chaque_ecran_s_affiche_avec_bandeau_demo(client, path):
    r = client.get(path)
    assert r.status_code == 200 and "Mode démo" in html(r)


# ======================================================================== Mes clés (F1, F2)
def test_creation_x25519_par_defaut(client, backend):
    r = post(client, "/cles", {"name": "PC de Diogo", "password": PW, "password2": PW})
    assert r.status_code == 302
    assert backend.list_identities()[0].kind == "X25519"
    assert "PC de Diogo" in html(client.get("/cles"))


def test_creation_rsa_et_kdf_en_options_avancees(client, backend, monkeypatch):
    seen = {}
    original = backend.create_identity
    monkeypatch.setattr(
        backend, "create_identity", lambda *a: seen.setdefault("args", a) and original(*a)
    )
    make_identity(client, key_type="rsa-4096", kdf="pbkdf2-sha256")
    assert backend.list_identities()[0].kind == "RSA-4096"
    assert seen["args"][3] == "pbkdf2-sha256"


def test_plusieurs_paires(client, backend):
    make_identity(client, name="Alice")
    make_identity(client, name="Bob")
    assert [k.name for k in backend.list_identities()] == ["Alice", "Bob"]


@pytest.mark.parametrize(
    "data, msg",
    [
        ({"name": "A", "password": PW, "password2": PW + "x"}, "ne correspondent pas"),
        ({"name": "A", "password": "court", "password2": "court"}, "au moins 12"),
        ({"name": "", "password": PW, "password2": PW}, "obligatoire"),
        ({"name": "A" * 65, "password": PW, "password2": PW}, "64 caractères"),
        ({"name": "A", "key_type": "dsa", "password": PW, "password2": PW}, "Type de clé inconnu"),
    ],
)
def test_creation_erreurs(client, data, msg):
    r = post(client, "/cles", data)
    assert r.status_code == 400 and msg in html(r)


def test_nom_de_cle_en_double(client):
    make_identity(client)
    r = make_identity(client)
    assert r.status_code == 400 and "déjà une clé nommée" in html(r)


def test_mot_de_passe_jamais_renvoye_dans_la_page(client):
    r = post(client, "/cles", {"name": "A", "password": PW, "password2": "autre-mot-de-passe"})
    assert PW not in html(r) and "autre-mot-de-passe" not in html(r)


def test_indicateur_sur_l_ecran_des_cles(client):
    page = html(client.get("/cles"))
    assert "Niveau de sécurité" in page and "Recommandé" in page
    assert 'data-rules="{&#34;levels&#34;' in page  # JSON échappé, attribut intact
    r = post(client, "/cles", {"name": "", "key_type": "rsa-2048", "password": PW, "password2": PW})
    assert "🟡" in html(r) and "fin de vie" in html(r)


def test_export_cle_publique(client, backend):
    make_identity(client, name="Perso")
    fpr = backend.list_identities()[0].fingerprint
    r = client.get("/cles/exporter", query_string={"fpr": fpr})
    assert r.status_code == 200 and b"PUBLIC KEY" in r.data
    assert "Perso_cle_publique.pem" in r.headers["Content-Disposition"]
    assert client.get("/cles/exporter?fpr=inconnue").status_code == 404


def test_export_cle_privee_post_uniquement(client, backend):
    make_identity(client, name="Perso")
    fpr = backend.list_identities()[0].fingerprint
    assert client.get("/cles/exporter-privee").status_code == 405
    r = post(client, "/cles/exporter-privee", {"fingerprint": fpr}, page="/cles")
    assert r.status_code == 200 and b"ENCRYPTED PRIVATE KEY" in r.data
    assert "Perso_cle_PRIVEE.pem" in r.headers["Content-Disposition"]


def test_suppression_puis_reimport_de_la_cle_privee(client, backend):
    make_identity(client, name="Perso")
    fpr = backend.list_identities()[0].fingerprint
    pem = post(client, "/cles/exporter-privee", {"fingerprint": fpr}, page="/cles").data
    assert post(client, "/cles/supprimer", {"fingerprint": fpr}, page="/cles").status_code == 302
    assert backend.list_identities() == []

    r = post(
        client,
        "/cles/importer",
        {"name": "Perso", "password": "mauvais"},
        {"keyfile": (pem, "cle.pem")},
        page="/cles",
    )
    assert r.status_code == 400 and "Mot de passe incorrect pour cette clé" in html(r)
    r = post(
        client,
        "/cles/importer",
        {"name": "Perso", "password": PW},
        {"keyfile": (pem, "cle.pem")},
        page="/cles",
    )
    assert r.status_code == 302 and backend.list_identities()[0].fingerprint == fpr


@pytest.mark.parametrize(
    "data, files, msg",
    [
        (
            {"name": "X", "password": PW},
            {"keyfile": (b"-----BEGIN PUBLIC KEY-----", "a.pem")},
            "pas une clé privée valide",
        ),
        ({"name": "X", "password": PW}, None, "Choisissez le fichier .pem"),
        ({"name": "X", "password": PW}, {"keyfile": (b"x" * 70_000, "gros.pem")}, "trop gros"),
    ],
)
def test_import_cle_privee_erreurs(client, data, files, msg):
    r = post(client, "/cles/importer", data, files, page="/cles")
    assert r.status_code == 400 and msg in html(r)


# ======================================================================== Contacts (F3)
def _my_public_pem(client, backend, name="Perso"):
    make_identity(client, name=name)
    me = next(k for k in backend.list_identities() if k.name == name)
    return me, backend.export_public_key(me.fingerprint)


def test_ajout_contact_par_fichier_puis_doublon(client, backend):
    _me, pem = _my_public_pem(client, backend)
    r = post(client, "/contacts", {"name": "Alice"}, {"keyfile": (pem, "alice.pem")})
    assert r.status_code == 302
    page = html(client.get("/contacts"))
    assert "Alice" in page and backend.list_contacts()[0].fingerprint in page
    r = post(client, "/contacts", {"name": "Alice bis", "keytext": pem.decode()})
    assert r.status_code == 400 and "déjà enregistrée" in html(r)


@pytest.mark.parametrize(
    "data, files, msg",
    [
        ({"name": "Bob"}, None, "Importez le fichier .pem"),
        ({"name": "Bob", "keytext": "pas une clé"}, None, "pas une clé publique valide"),
        ({"name": "Bob"}, {"keyfile": (b"x" * 70_000, "gros.pem")}, "trop gros"),
    ],
)
def test_ajout_contact_erreurs(client, data, files, msg):
    r = post(client, "/contacts", data, files)
    assert r.status_code == 400 and msg in html(r)


def test_nom_de_contact_echappe(client, backend):
    _me, pem = _my_public_pem(client, backend)
    post(client, "/contacts", {"name": "<script>alert(1)</script>", "keytext": pem.decode()})
    page = html(client.get("/contacts"))
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_renommer_contact(client, backend):
    _me, pem = _my_public_pem(client, backend)
    post(client, "/contacts", {"name": "Alice", "keytext": pem.decode()})
    fpr = backend.list_contacts()[0].fingerprint
    assert 'name="name" required maxlength="64" value="Alice"' in html(
        client.get("/contacts", query_string={"renommer": fpr})
    )
    r = post(
        client, "/contacts/renommer", {"fingerprint": fpr, "name": "Alice Martin"}, page="/contacts"
    )
    assert r.status_code == 302 and backend.list_contacts()[0].name == "Alice Martin"
    r = post(client, "/contacts/renommer", {"fingerprint": fpr, "name": "  "}, page="/contacts")
    assert r.status_code == 400 and "obligatoire" in html(r)


def test_suppression_contact_par_empreinte(client, backend):
    _me, pem = _my_public_pem(client, backend)
    post(client, "/contacts", {"name": "Alice", "keytext": pem.decode()})
    fpr = backend.list_contacts()[0].fingerprint
    r = post(client, "/contacts/supprimer", {"fingerprint": fpr}, page="/contacts")
    assert r.status_code == 302 and backend.list_contacts() == []


# ======================================================================== Chiffrer / déchiffrer
@pytest.fixture
def moi(client, backend):
    """Ma clé + moi-même en contact."""
    me, pem = _my_public_pem(client, backend)
    post(client, "/contacts", {"name": "Moi", "keytext": pem.decode()})
    return me


def encrypt(client, recipient, content=b"secret", name="rapport.pdf", **options):
    return post(client, "/chiffrer", {"recipient": recipient, **options}, {"file": (content, name)})


def decrypt(client, data, password=PW, **fields):
    return post(client, "/dechiffrer", {"password": password, **fields}, {"file": (data, "x.zip")})


def encrypted(client, recipient, content=b"secret", **options):
    with encrypt(client, recipient, content, **options) as r:
        assert r.status_code == 200, html(r)
        return r.data, r.headers["Content-Disposition"]


def test_aller_retour_octet_pour_octet(client, app, moi):
    content = "Données é€ 🔒".encode() * 50_000  # ~1 Mo, plusieurs blocs
    data, disposition = encrypted(client, moi.fingerprint, content, name="Rapport final é.pdf")
    assert "encrypted_" in disposition and ".zip" in disposition  # nom neutre (D7)
    assert "Rapport" not in disposition
    with zipfile.ZipFile(io.BytesIO(data)) as zf:  # format § 5.1
        assert sorted(zf.namelist()) == ["file.enc", "key.enc", "manifest.json"]
        assert all(i.compress_type == zipfile.ZIP_STORED for i in zf.infolist())
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["cipher"] == "aes-256-gcm" and manifest["password"] is None
    assert "Rapport" not in json.dumps(manifest)  # le nom ne fuit pas
    with decrypt(client, data) as r:
        assert r.status_code == 200 and r.data == content
        assert "Rapport%20final%20%C3%A9.pdf" in r.headers["Content-Disposition"]
    assert run_files(app) == []  # rien ne reste sur le disque


def test_chiffrer_pour_une_de_mes_cles(client, backend):
    make_identity(client, name="Bob")
    bob = backend.list_identities()[0]
    data, _ = encrypted(client, bob.fingerprint, b"pour moi")
    with decrypt(client, data, identity=bob.fingerprint) as r:
        assert r.data == b"pour moi"


def test_nom_choisi_pour_le_paquet(client, moi):
    _data, disposition = encrypted(client, moi.fingerprint, out_name="dossier mars")
    assert 'filename="dossier mars.zip"' in disposition


def test_mot_de_passe_supplementaire(client, moi):
    data, _ = encrypted(
        client,
        moi.fingerprint,
        b"double protection",
        use_password=CHECKED,
        file_password=FILE_PW,
        file_password2=FILE_PW,
        kdf="pbkdf2-sha256",
        kdf_strength="fort",
        salt="32",
        cipher="aes-128-gcm",
    )
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        m = json.loads(zf.read("manifest.json"))
    assert m["cipher"] == "aes-128-gcm" and m["password"]["kdf"] == "pbkdf2-sha256"
    assert FILE_PW not in json.dumps(m)

    r = decrypt(client, data)
    assert r.status_code == 400 and "mot de passe supplémentaire" in html(r)
    r = decrypt(client, data, file_password=WRONG_FILE_PW)
    assert r.status_code == 400 and "Mot de passe du fichier incorrect" in html(r)
    with decrypt(client, data, file_password=FILE_PW) as r:
        assert r.status_code == 200 and r.data == b"double protection"


def test_sans_sel_autorise_avec_pbkdf2_seulement(client, moi):
    opts = dict(use_password=CHECKED, file_password=FILE_PW, file_password2=FILE_PW, salt="0")
    r = encrypt(client, moi.fingerprint, kdf="argon2id", **opts)
    assert r.status_code == 400 and "Argon2id exige un sel" in html(r)
    assert "🔴" in html(r)  # l'indicateur affiche Faible
    data, _ = encrypted(client, moi.fingerprint, kdf="pbkdf2-sha256", **opts)
    with decrypt(client, data, file_password=FILE_PW) as r:
        assert r.status_code == 200


@pytest.mark.parametrize(
    "options, msg",
    [
        ({"use_password": "1"}, "Saisissez le mot de passe supplémentaire"),
        (
            {"use_password": "1", "file_password": "a", "file_password2": "b"},
            "ne correspondent pas",
        ),
        ({"cipher": "aes-256-cbc"}, "Réglage de sécurité inconnu"),
        (
            {"use_password": "1", "file_password": "a", "file_password2": "a", "kdf": "md5"},
            "Réglage de sécurité inconnu",
        ),
    ],
)
def test_reglages_invalides(client, moi, options, msg):
    r = encrypt(client, moi.fingerprint, **options)
    assert r.status_code == 400 and msg in html(r)


def test_mot_de_passe_du_fichier_jamais_renvoye(client, moi):
    r = encrypt(
        client, moi.fingerprint, use_password=CHECKED, file_password=FILE_PW, file_password2="x"
    )
    assert FILE_PW not in html(r)


def test_dechiffrer_avec_cle_pem_importee(client, backend, moi):
    data, _ = encrypted(client, moi.fingerprint, b"via pem")
    pem = backend.export_private_key(moi.fingerprint)
    r = post(
        client,
        "/dechiffrer",
        {"password": PW},
        {"file": (data, "x.zip"), "privkey": (pem, "cle.pem")},
    )
    assert r.status_code == 200 and r.data == b"via pem"


@pytest.mark.parametrize(
    "password, msg",
    [
        ("ce n'est pas le bon", "Mot de passe incorrect pour cette clé"),
    ],
)
def test_mauvais_mot_de_passe_de_cle(client, app, moi, password, msg):
    data, _ = encrypted(client, moi.fingerprint)
    r = decrypt(client, data, password=password)
    assert r.status_code == 400 and msg in html(r)
    assert run_files(app) == []


def test_paquet_pas_pour_cette_cle(client, backend, moi):
    data, _ = encrypted(client, moi.fingerprint)
    make_identity(client, name="Autre")
    autre = next(k for k in backend.list_identities() if k.name == "Autre")
    r = decrypt(client, data, identity=autre.fingerprint)
    assert r.status_code == 400 and "pas été chiffré pour cette clé" in html(r)


def _tamper(data: bytes, member: str, edit) -> bytes:
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as dst:
        for name in src.namelist():
            content = src.read(name)
            dst.writestr(name, edit(content) if name == member else content)
    return out.getvalue()


@pytest.mark.parametrize(
    "member, edit",
    [
        ("file.enc", lambda b: b[:-40] + bytes([b[-40] ^ 1]) + b[-39:]),  # 1 bit du contenu
        ("file.enc", lambda b: b[:-100]),  # tronqué
        ("manifest.json", lambda b: b.replace(b"aes-256-gcm", b"aes-128-gcm")),  # réglage modifié
    ],
)
def test_paquet_modifie(client, app, moi, member, edit):
    data, _ = encrypted(client, moi.fingerprint, b"A" * 10_000)
    r = decrypt(client, _tamper(data, member, edit))
    assert r.status_code == 400 and "endommagé ou a été modifié" in html(r)
    assert run_files(app) == []  # pas de déchiffré partiel


@pytest.mark.parametrize(
    "payload",
    [
        b"%PDF-1.7 pas du tout un zip",
        lambda: _zip({"autre.txt": b"x"}),
        lambda: _zip(
            {
                "manifest.json": b'{"format":"crypteasy","version":99}',
                "key.enc": b"",
                "file.enc": b"",
            }
        ),
    ],
)
def test_pas_un_paquet_crypteasy(client, moi, payload):
    data = payload() if callable(payload) else payload
    r = decrypt(client, data)
    assert r.status_code == 400 and "pas un fichier CryptEasy" in html(r)


def _zip(members: dict) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return out.getvalue()


def test_erreur_imprevue_message_generique(client, app, backend, moi, monkeypatch, caplog):
    def boom(*_a, **_k):
        raise RuntimeError("détail interne secret")

    monkeypatch.setattr(backend, "encrypt_file", boom)
    r = encrypt(client, moi.fingerprint)
    assert r.status_code == 400 and "Erreur inattendue" in html(r)
    assert "détail interne secret" not in html(r)
    assert "RuntimeError" in caplog.text and "détail interne secret" not in caplog.text
    assert run_files(app) == []


@pytest.mark.parametrize(
    "path, data, files, msg",
    [
        ("/chiffrer", {"recipient": ""}, {"file": (b"x", "a")}, "Choisissez un destinataire"),
        ("/chiffrer", {"recipient": "inconnu"}, {"file": (b"x", "a")}, "Destinataire introuvable"),
        ("/chiffrer", {"recipient": "x"}, None, "Choisissez un fichier"),
        ("/dechiffrer", {"password": ""}, {"file": (b"x", "a")}, "Saisissez le mot de passe"),
    ],
)
def test_formulaires_incomplets(client, moi, path, data, files, msg):
    r = post(client, path, data, files)
    assert r.status_code == 400 and msg in html(r)


def test_dechiffrer_sans_cle(client):
    r = post(client, "/dechiffrer", {"password": PW}, {"file": (b"x", "a.zip")})
    assert r.status_code == 400 and "importez votre clé privée" in html(r)


def test_fichier_trop_gros(client, app, moi):
    app.config["MAX_CONTENT_LENGTH"] = 2048
    r = encrypt(client, moi.fingerprint, b"x" * 10_000)
    assert r.status_code == 413 and "trop volumineux" in html(r)


def test_contact_preselectionne_et_note(client, moi):
    page = html(client.get("/chiffrer", query_string={"contact": moi.fingerprint}))
    assert f'value="{moi.fingerprint}" data-rate-value="x25519" selected' in page
    assert "X25519 : courbe elliptique moderne" in page


def test_page_info(client):
    page = html(client.get("/info"))
    for text in (
        "Chiffrement hybride",
        "Pourquoi le sel compte",
        "manifest.json",
        "Les réglages de sécurité",
        "Sauvegardez votre clé privée",
    ):
        assert text in page


# ======================================================================== noms de fichiers
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("rapport.pdf", "rapport.pdf"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\x\\secret.txt", "secret.txt"),
        ('a<b>c:d"e|f?g*h.txt', "a_b_c_d_e_f_g_h.txt"),
        ("CON.txt", "_CON.txt"),
        ("été.txt", "été.txt"),
    ],
)
def test_safe_filename(raw, expected):
    assert safe_filename(raw) == expected


@pytest.mark.parametrize("raw", ["", ".", "..", "dossier/", "é" * 128 + ".bin"])
def test_safe_filename_refuse(raw):
    with pytest.raises(BadInput):
        safe_filename(raw)
