"""Mes clés (F1, F2) et Contacts (F3)."""

import pytest

from crypteasy.ui.security_levels import PRESETS

from .conftest import PW, PW12, api, html, make_identity, post

OTHER_PW = "une autre phrase secrète"
WRONG_PW = "pas la bonne phrase"
CHECKED = "1"  # valeur envoyée par une case cochée


# ======================================================================== créer (F1)
def test_creation_par_defaut_x25519_fort(client, backend):
    r = post(client, "/cles", {"name": "PC de Diogo", "passphrase": PW12, "passphrase2": PW12})
    assert r.status_code == 302
    key = backend.list_identities()[0]
    assert (key.kind, key.level, key.protected) == ("X25519", "strong", True)
    page = html(client.get("/cles"))
    assert "PC de Diogo" in page and "créée" in page and key.fingerprint in page


@pytest.mark.parametrize(
    "level, pw, expected_kind, expected_level",
    [
        ("very_strong", PW, "X25519", "very_strong"),
        ("very_strong", PW12, "X25519", "strong"),  # « très fort » exige 16+ caractères
        ("strong", PW, "X25519", "strong"),
        ("medium", PW, "RSA-2048", "medium"),
        ("weak", PW, "RSA-2048", "weak"),
    ],
)
def test_niveaux(client, backend, level, pw, expected_kind, expected_level):
    assert make_identity(client, level=level, pw=pw).status_code == 302
    key = backend.list_identities()[0]
    assert (key.kind, key.level) == (expected_kind, expected_level)


def test_personnalise_note_selon_le_reglage_le_plus_faible(client, backend):
    make_identity(client, level="custom", key_type="rsa-4096", kdf="argon2id",
                  kdf_strength="max", salt="0")  # fmt: skip
    assert html(client.get("/cles"))  # la page s'affiche
    # Argon2id sans sel est refusé…
    assert backend.list_identities() == []
    make_identity(client, level="custom", key_type="rsa-4096", kdf="pbkdf2-sha256",
                  kdf_strength="max", salt="32")  # fmt: skip
    assert backend.list_identities()[0].level == "medium"  # PBKDF2 = moyen


def test_sans_phrase_secrete_exige_confirmation(client, backend):
    r = post(client, "/cles", {"name": "A", "no_passphrase": CHECKED})
    assert r.status_code == 400 and "Cochez la case de confirmation" in html(r)
    r = post(client, "/cles", {"name": "A", "no_passphrase": CHECKED,
                               "no_passphrase_confirm": CHECKED})  # fmt: skip
    assert r.status_code == 302
    key = backend.list_identities()[0]
    assert (key.level, key.protected) == ("none", False)
    assert "sans phrase secrète" in html(client.get("/cles"))


@pytest.mark.parametrize(
    "data, msg",
    [
        ({"name": "A", "passphrase": PW, "passphrase2": PW + "x"}, "ne correspondent pas"),
        ({"name": "A", "passphrase": "court", "passphrase2": "court"}, "au moins 12"),
        ({"name": "", "passphrase": PW, "passphrase2": PW}, "obligatoire"),
        ({"name": "A" * 65, "passphrase": PW, "passphrase2": PW}, "64 caractères"),
        ({"name": "A", "key_type": "dsa", "passphrase": PW, "passphrase2": PW}, "inconnu"),
        ({"name": "A", "kdf": "md5", "passphrase": PW, "passphrase2": PW}, "inconnu"),
        ({"name": "A", "kdf": "argon2id", "salt": "0", "passphrase": PW, "passphrase2": PW},
         "Argon2id exige un sel"),
    ],
)  # fmt: skip
def test_creation_erreurs(client, data, msg):
    r = post(client, "/cles", data)
    assert r.status_code == 400 and msg in html(r)


def test_phrase_secrete_jamais_renvoyee(client):
    r = post(client, "/cles", {"name": "A", "passphrase": PW, "passphrase2": OTHER_PW})
    assert PW not in html(r) and OTHER_PW not in html(r)


def test_nom_en_double(client):
    make_identity(client)
    r = make_identity(client)
    assert r.status_code == 400 and "déjà une clé nommée" in html(r)


def test_indicateur_de_niveau(client):
    page = html(client.get("/cles"))
    assert "Niveau de sécurité" in page and 'data-rules="{' in page
    r = post(client, "/cles", {"name": "", "level": "custom", "key_type": "rsa-2048",
                               "passphrase": PW, "passphrase2": PW})  # fmt: skip
    assert "🟡" in html(r)


# ======================================================================== exporter / importer (F2)
def _fpr(backend, name="Perso"):
    return next(k.fingerprint for k in backend.list_identities() if k.name == name)


def test_export_publique_via_enregistrer_sous(client, backend, dialogs, files):
    make_identity(client)
    dialogs.answers = [files / "ma_cle.pem"]
    r = post(client, "/cles/exporter-publique", {"fingerprint": _fpr(backend)})
    assert r.status_code == 302
    assert dialogs.calls[-1] == ("save_file", "Perso_public.pem")
    assert b"PUBLIC KEY" in (files / "ma_cle.pem").read_bytes()


def test_export_annule(client, backend, dialogs, files):
    make_identity(client)
    dialogs.answers = [None]
    assert (
        post(client, "/cles/exporter-publique", {"fingerprint": _fpr(backend)}).status_code == 302
    )
    assert list(files.iterdir()) == []


def test_export_n_ecrase_jamais(client, backend, dialogs, files):
    make_identity(client)
    (files / "existe.pem").write_text("à moi")
    dialogs.answers = [files / "existe.pem"]
    r = post(client, "/cles/exporter-publique", {"fingerprint": _fpr(backend)})
    assert r.status_code == 400 and "écrase jamais" in html(r)
    assert (files / "existe.pem").read_text() == "à moi"


def test_export_privee_puis_reimport(client, backend, dialogs, files):
    make_identity(client)
    fpr = _fpr(backend)
    dialogs.answers = [files / "perso.key"]
    post(client, "/cles/exporter-privee", {"fingerprint": fpr})
    assert dialogs.calls[-1] == ("save_file", "Perso_private.key")
    assert b"crypteasy-private-key" in (files / "perso.key").read_bytes()
    post(client, "/cles/supprimer", {"fingerprint": fpr})
    assert backend.list_identities() == []

    dialogs.answers = [files / "perso.key"]
    sel = api(client, "/api/choisir", {"what": "key-file"}).get_json()["id"]
    base = {"name": "Perso", "key_selection": sel, "passphrase": OTHER_PW, "passphrase2": OTHER_PW}
    r = post(client, "/cles/importer", {**base, "current_passphrase": WRONG_PW})
    assert r.status_code == 400 and "Phrase secrète incorrecte pour cette clé" in html(r)
    r = post(client, "/cles/importer", {**base, "current_passphrase": PW})
    assert r.status_code == 302 and _fpr(backend) == fpr


def test_import_fichier_invalide(client, dialogs, files):
    (files / "faux.key").write_text("-----BEGIN PUBLIC KEY-----")
    dialogs.answers = [files / "faux.key"]
    sel = api(client, "/api/choisir", {"what": "key-file"}).get_json()["id"]
    r = post(client, "/cles/importer", {"name": "X", "key_selection": sel,
                                        "passphrase": PW, "passphrase2": PW})  # fmt: skip
    assert r.status_code == 400 and "pas une clé privée valide" in html(r)


def test_import_sans_fichier(client):
    r = post(client, "/cles/importer", {"name": "X", "passphrase": PW, "passphrase2": PW})
    assert r.status_code == 400 and "choisissez à nouveau" in html(r)


def test_changer_la_protection(client, backend):
    make_identity(client, level="medium")
    fpr = _fpr(backend)
    new = {"fingerprint": fpr, "passphrase": OTHER_PW, "passphrase2": OTHER_PW,
           **{k: v for k, v in PRESETS["very_strong"].items() if k != "key_type"}}  # fmt: skip
    r = post(client, "/cles/proteger", {**new, "current_passphrase": WRONG_PW})
    assert r.status_code == 400 and "Phrase secrète incorrecte" in html(r)
    r = post(client, "/cles/proteger", {**new, "current_passphrase": PW})
    assert r.status_code == 302
    # le type de clé (RSA-2048) reste « moyen », même avec la meilleure protection
    assert backend.list_identities()[0].level == "medium"


def test_suppression(client, backend):
    make_identity(client)
    assert post(client, "/cles/supprimer", {"fingerprint": _fpr(backend)}).status_code == 302
    assert backend.list_identities() == []


# ======================================================================== contacts (F3)
@pytest.fixture
def pem_file(client, backend, files):
    make_identity(client)
    path = files / "alice.pem"
    backend.export_public_key(_fpr(backend), path)
    return path


def test_ajout_contact_par_fichier(client, backend, dialogs, pem_file):
    dialogs.answers = [pem_file]
    data = api(client, "/api/choisir", {"what": "public-key"}).get_json()
    assert data["name"] == "alice.pem" and "/" not in data["id"]
    assert dialogs.calls[-1][1][0] == "Clé publique (*.pem)"
    r = post(client, "/contacts", {"name": "Alice", "key_selection": data["id"]})
    assert r.status_code == 302
    page = html(client.get("/contacts"))
    assert "Alice" in page and backend.list_contacts()[0].fingerprint in page


def test_ajout_contact_par_collage_et_doublon(client, backend, pem_file):
    text = pem_file.read_text()
    assert post(client, "/contacts", {"name": "Alice", "keytext": text}).status_code == 302
    r = post(client, "/contacts", {"name": "Alice bis", "keytext": text})
    assert r.status_code == 400 and "déjà enregistrée" in html(r)


@pytest.mark.parametrize(
    "data, msg",
    [
        ({"name": "Bob"}, "Choisissez le fichier .pem"),
        ({"name": "Bob", "keytext": "pas une clé"}, "pas une clé publique valide"),
        ({"name": "Bob", "key_selection": "inventé"}, "choisissez à nouveau"),
    ],
)
def test_ajout_contact_erreurs(client, data, msg):
    r = post(client, "/contacts", data)
    assert r.status_code == 400 and msg in html(r)


def test_nom_de_contact_echappe(client, pem_file):
    post(
        client, "/contacts", {"name": "<script>alert(1)</script>", "keytext": pem_file.read_text()}
    )
    page = html(client.get("/contacts"))
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_renommer_et_supprimer_contact(client, backend, pem_file):
    post(client, "/contacts", {"name": "Alice", "keytext": pem_file.read_text()})
    fpr = backend.list_contacts()[0].fingerprint
    assert 'value="Alice" autofocus' in html(
        client.get("/contacts", query_string={"renommer": fpr})
    )
    r = post(client, "/contacts/renommer", {"fingerprint": fpr, "name": "Alice Martin"})
    assert r.status_code == 302 and backend.list_contacts()[0].name == "Alice Martin"
    r = post(client, "/contacts/renommer", {"fingerprint": fpr, "name": "  "})
    assert r.status_code == 400 and "obligatoire" in html(r)
    assert post(client, "/contacts/supprimer", {"fingerprint": fpr}).status_code == 302
    assert backend.list_contacts() == []
