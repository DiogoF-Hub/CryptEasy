"""Écrans sur le FakeBackend : parcours, messages d'erreur, fichiers temporaires."""
import pytest

from crypteasy.ui.files import safe_filename
from crypteasy.ui.errors import BadInput

from .conftest import PW, html, make_identity, post, run_files


@pytest.mark.parametrize("path", ["/", "/cles", "/contacts", "/chiffrer", "/dechiffrer"])
def test_chaque_ecran_s_affiche_avec_bandeau_demo(client, path):
    r = client.get(path)
    assert r.status_code == 200 and "Mode démo" in html(r)


# ------------------------------------------------------------------ Mes clés
def test_creation_x25519_par_defaut(client, backend):
    r = post(client, "/cles", {"name": "Perso", "password": PW, "password2": PW})
    assert r.status_code == 302
    assert backend.list_identities()[0].kind == "X25519"
    assert "Perso" in html(client.get("/cles"))


def test_creation_rsa_en_options_avancees(client, backend):
    make_identity(client, key_type="rsa-4096")
    assert backend.list_identities()[0].kind == "RSA-4096"


@pytest.mark.parametrize("data, msg", [
    ({"name": "A", "password": PW, "password2": PW + "x"}, "ne correspondent pas"),
    ({"name": "A", "password": "court", "password2": "court"}, "au moins 15"),
    ({"name": "", "password": PW, "password2": PW}, "obligatoire"),
    ({"name": "A" * 65, "password": PW, "password2": PW}, "64 caractères"),
    ({"name": "A", "key_type": "dsa", "password": PW, "password2": PW}, "Type de clé inconnu"),
])
def test_creation_erreurs(client, data, msg):
    r = post(client, "/cles", data)
    assert r.status_code == 400 and msg in html(r)


def test_mot_de_passe_jamais_renvoye_dans_la_page(client):
    r = post(client, "/cles", {"name": "A", "password": PW, "password2": "autre-mot-de-passe"})
    assert PW not in html(r) and "autre-mot-de-passe" not in html(r)


def test_export_cle_publique(client, backend):
    make_identity(client)
    fpr = backend.list_identities()[0].fingerprint
    r = client.get("/cles/exporter", query_string={"fpr": fpr})
    assert r.status_code == 200 and b"PUBLIC KEY" in r.data
    assert "Perso_cle_publique.pem" in r.headers["Content-Disposition"]
    assert client.get("/cles/exporter?fpr=inconnue").status_code == 404


# ------------------------------------------------------------------ Contacts
def test_ajout_contact_par_fichier_puis_collage(client, backend):
    make_identity(client)
    pem = backend.export_public_key(backend.list_identities()[0].fingerprint)
    r = post(client, "/contacts", {"name": "Alice"}, {"keyfile": (pem, "alice.pem")})
    assert r.status_code == 302
    page = html(client.get("/contacts"))
    assert "Alice" in page and backend.list_contacts()[0].fingerprint in page
    # même clé collée une 2e fois → refus
    r = post(client, "/contacts", {"name": "Alice bis", "keytext": pem.decode()})
    assert r.status_code == 400 and "déjà enregistrée" in html(r)


@pytest.mark.parametrize("data, files, msg", [
    ({"name": "Bob"}, None, "Importez le fichier"),
    ({"name": "Bob", "keytext": "pas une clé"}, None, "invalide ou illisible"),
    ({"name": "Bob"}, {"keyfile": (b"x" * 70_000, "gros.pem")}, "trop gros"),
])
def test_ajout_contact_erreurs(client, data, files, msg):
    r = post(client, "/contacts", data, files)
    assert r.status_code == 400 and msg in html(r)


def test_nom_de_contact_echappe(client, backend):
    make_identity(client)
    pem = backend.export_public_key(backend.list_identities()[0].fingerprint)
    post(client, "/contacts", {"name": "<script>alert(1)</script>", "keytext": pem.decode()})
    page = html(client.get("/contacts"))
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_suppression_contact_par_empreinte(client, backend):
    make_identity(client)
    pem = backend.export_public_key(backend.list_identities()[0].fingerprint)
    post(client, "/contacts", {"name": "Alice", "keytext": pem.decode()})
    fpr = backend.list_contacts()[0].fingerprint
    r = post(client, "/contacts/supprimer", {"fingerprint": fpr}, page="/contacts")
    assert r.status_code == 302 and backend.list_contacts() == []


# ------------------------------------------------------------------ Chiffrer / déchiffrer
@pytest.fixture
def moi(client, backend):
    """Ma clé + moi-même en contact : permet l'aller-retour."""
    make_identity(client)
    me = backend.list_identities()[0]
    post(client, "/contacts", {"name": "Moi", "keytext": backend.export_public_key(me.fingerprint).decode()})
    return me


def encrypt(client, contact, content=b"secret", name="rapport.pdf", out_name=""):
    return post(client, "/chiffrer", {"contact": contact, "out_name": out_name},
                {"file": (content, name)})


def decrypt(client, data, password=PW, identity=""):
    return post(client, "/dechiffrer", {"password": password, "identity": identity},
                {"file": (data, "x.ceasy")})


def test_aller_retour_octet_pour_octet(client, app, moi):
    content = "Données é€ 🔒".encode() * 50_000           # ~1 Mo, plusieurs blocs
    with encrypt(client, moi.fingerprint, content, "Rapport final é.pdf") as r:
        assert r.status_code == 200
        disposition = r.headers["Content-Disposition"]
        assert "Rapport" not in disposition                    # le nom d'origine ne fuit pas
        assert ".ceasy" in disposition and "crypteasy-" in disposition
        encrypted = r.data
    with decrypt(client, encrypted) as r:
        assert r.status_code == 200 and r.data == content
        assert "Rapport%20final%20%C3%A9.pdf" in r.headers["Content-Disposition"]
    assert run_files(app) == []                                  # rien ne reste sur le disque


def test_nom_choisi_pour_le_fichier_chiffre(client, moi):
    with encrypt(client, moi.fingerprint, out_name="dossier mars") as r:
        assert 'filename="dossier mars.ceasy"' in r.headers["Content-Disposition"]


def test_mauvais_mot_de_passe(client, app, moi):
    with encrypt(client, moi.fingerprint) as r:
        enc = r.data
    r = decrypt(client, enc, password="ce n'est pas le bon")
    assert r.status_code == 400 and "Mot de passe incorrect" in html(r)
    assert run_files(app) == []


def test_fichier_pas_pour_moi(client, app, backend, moi):
    with encrypt(client, moi.fingerprint) as r:
        enc = r.data
    make_identity(client, name="Autre")
    autre = next(k for k in backend.list_identities() if k.name == "Autre")
    r = decrypt(client, enc, identity=autre.fingerprint)
    assert r.status_code == 400 and "pas été chiffré pour vous" in html(r)


def test_fichier_modifie(client, app, moi):
    with encrypt(client, moi.fingerprint, b"A" * 10_000) as r:
        enc = bytearray(r.data)
    enc[-100] ^= 1
    r = decrypt(client, bytes(enc))
    assert r.status_code == 400 and "corrompu ou a été modifié" in html(r)
    assert run_files(app) == []                                  # pas de déchiffré partiel


def test_pas_un_fichier_crypteasy(client, moi):
    r = decrypt(client, b"%PDF-1.7 pas du tout chiffre")
    assert r.status_code == 400 and "pas un fichier CryptEasy" in html(r)


def test_erreur_imprevue_message_generique(client, app, backend, moi, monkeypatch, caplog):
    def boom(*_a):
        raise RuntimeError("détail interne secret")
    monkeypatch.setattr(backend, "encrypt_file", boom)
    r = encrypt(client, moi.fingerprint)
    assert r.status_code == 400 and "Erreur inattendue" in html(r)
    assert "détail interne secret" not in html(r)
    assert "RuntimeError" in caplog.text and "détail interne secret" not in caplog.text
    assert run_files(app) == []


@pytest.mark.parametrize("path, data, files, msg", [
    ("/chiffrer", {"contact": ""}, {"file": (b"x", "a")}, "Choisissez un destinataire"),
    ("/chiffrer", {"contact": "inconnu"}, {"file": (b"x", "a")}, "Contact introuvable"),
    ("/chiffrer", {"contact": "x"}, None, "Choisissez un fichier"),
    ("/dechiffrer", {"password": ""}, {"file": (b"x", "a")}, "Saisissez le mot de passe"),
])
def test_formulaires_incomplets(client, moi, path, data, files, msg):
    r = post(client, path, data, files)
    assert r.status_code == 400 and msg in html(r)


def test_dechiffrer_sans_cle(client):
    r = post(client, "/dechiffrer", {"password": PW}, {"file": (b"x", "a.ceasy")})
    assert r.status_code == 400 and "abord votre paire de clés" in html(r)


def test_fichier_trop_gros(client, app, moi):
    app.config["MAX_CONTENT_LENGTH"] = 2048
    r = encrypt(client, moi.fingerprint, b"x" * 10_000)
    assert r.status_code == 413 and "trop volumineux" in html(r)


def test_contact_preselectionne(client, moi):
    page = html(client.get("/chiffrer", query_string={"contact": moi.fingerprint}))
    assert f'value="{moi.fingerprint}" selected' in page


# ------------------------------------------------------------------ noms de fichiers
@pytest.mark.parametrize("raw, expected", [
    ("rapport.pdf", "rapport.pdf"),
    ("../../etc/passwd", "passwd"),
    ("C:\\Users\\x\\secret.txt", "secret.txt"),
    ('a<b>c:d"e|f?g*h.txt', "a_b_c_d_e_f_g_h.txt"),
    ("CON.txt", "_CON.txt"),
    ("été.txt", "été.txt"),
])
def test_safe_filename(raw, expected):
    assert safe_filename(raw) == expected


@pytest.mark.parametrize("raw", ["", ".", "..", "dossier/", "é" * 128 + ".bin"])
def test_safe_filename_refuse(raw):
    with pytest.raises(BadInput):
        safe_filename(raw)
