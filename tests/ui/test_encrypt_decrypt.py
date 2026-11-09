"""Chiffrer (F4) et déchiffrer (F5) de bout en bout, avec les boîtes de dialogue simulées :
fichiers, dossiers, détection de la clé, progression, enregistrer sous, extraction,
et les erreurs F7."""

import io
import os
import re
import zipfile

import pytest

from crypteasy.ui.fake_backend import extract_folder

from .conftest import PW, api, make_identity, post, run_files

WRONG_PW = "pas la bonne phrase"


# ------------------------------------------------------------------ outils
@pytest.fixture
def me(client, backend):
    """Ma clé « Perso » + moi-même en contact (aller-retour possible)."""
    make_identity(client)
    key = backend.list_identities()[0]
    post(client, "/contacts", {"name": "Moi", "keytext": _public_pem(backend, key).decode()})
    return key


def _public_pem(backend, key):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "k.pem"
        backend.export_public_key(key.fingerprint, path)
        return path.read_bytes()


def choose(client, dialogs, what, path):
    dialogs.answers.append(path)
    r = api(client, "/api/choisir", {"what": what})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def wait(app, job_id):
    return app.extensions["crypteasy_jobs"].wait(job_id)


def status(client, job_id):
    return api(client, f"/api/taches/{job_id}", method="GET").get_json()


def encrypt(client, app, dialogs, source, dst, recipient, what="file", cipher="aes-256-gcm"):
    sel = choose(client, dialogs, what, source)
    dialogs.answers.append(dst)
    r = api(
        client, "/api/chiffrer", {"selection": sel["id"], "recipient": recipient, "cipher": cipher}
    )
    assert r.status_code == 200, r.get_json()
    job = r.get_json()["job"]
    wait(app, job)
    return job


def decrypt(client, app, dialogs, package, passphrase=PW, key_selection=None):
    sel = choose(client, dialogs, "package", package)
    body = {"selection": sel["id"], "passphrase": passphrase, "key_selection": key_selection}
    r = api(client, "/api/dechiffrer", body)
    if r.status_code != 200:
        return sel, r.get_json()
    job = r.get_json()["job"]
    wait(app, job)
    return sel, job


# ------------------------------------------------------------------ choisir
def test_choisir_un_fichier_taille_et_estimation(client, dialogs, files):
    f = files / "rapport.pdf"
    f.write_bytes(b"x" * 2_500_000)
    data = choose(client, dialogs, "file", f)
    assert data["name"] == "rapport.pdf" and data["is_folder"] is False
    assert data["size"] == "2,5 Mo" and data["estimate"] == "moins d'une seconde"
    assert data["big"] is False and str(files) not in str(data)  # aucun chemin renvoyé


def test_choisir_un_dossier_compte_les_fichiers(client, dialogs, files):
    d = files / "vacances"
    (d / "sous").mkdir(parents=True)
    (d / "plage.jpg").write_bytes(b"a" * 1000)
    (d / "sous" / "coucher.jpg").write_bytes(b"b" * 500)
    data = choose(client, dialogs, "folder", d)
    assert data["is_folder"] is True and data["files"] == 2 and data["size"] == "1,5 Ko"


def test_choix_annule(client, dialogs):
    dialogs.answers = [None]
    assert api(client, "/api/choisir", {"what": "file"}).get_json() == {"cancelled": True}


def test_choix_inconnu(client):
    assert api(client, "/api/choisir", {"what": "/etc/passwd"}).status_code == 400


# ------------------------------------------------------------------ fichier : aller-retour
def test_aller_retour_fichier(client, app, dialogs, files, me):
    content = "Données confidentielles é€ 🔒".encode() * 30_000  # ~1 Mo, plusieurs blocs
    src = files / "Rapport final é.pdf"
    src.write_bytes(content)
    package = files / "paquet.zip"

    job = encrypt(client, app, dialogs, src, package, me.fingerprint)
    st = status(client, job)
    assert st["status"] == "done" and st["percent"] == 100 and st["saved"] == str(package)
    # nom proposé neutre (F4) : crypteasy_AAAA-MM-JJ_HHMM.zip
    assert re.fullmatch(r"crypteasy_\d{4}-\d\d-\d\d_\d{4}\.zip", dialogs.calls[-1][1])
    with zipfile.ZipFile(package) as zf:  # § 5.1 : exactement key.enc + file.enc, stocké
        assert sorted(zf.namelist()) == ["file.enc", "key.enc"]
        assert all(i.compress_type == zipfile.ZIP_STORED for i in zf.infolist())
        head = zf.read("file.enc")[:4096]
    assert head.startswith(b"CRYPTEZ\x01")
    header = head[12 : 12 + int.from_bytes(head[8:12], "big")]
    assert b"recipient_fingerprint" in header and b"Rapport" not in header  # nom hors en-tête

    renamed = files / "trucs.zip"  # un paquet renommé se déchiffre pareil
    package.rename(renamed)
    sel, job = decrypt(client, app, dialogs, renamed)
    assert sel["key"]["name"] == "Perso" and sel["key"]["protected"] is True  # clé trouvée seule
    st = status(client, job)
    assert st["status"] == "done" and st["name"] == "Rapport final é.pdf" and not st["is_folder"]

    out = files / "récupéré.pdf"
    dialogs.answers.append(out)
    r = api(client, f"/api/taches/{job}/enregistrer", {"mode": "file"})
    assert r.get_json()["saved"] == str(out)
    assert dialogs.calls[-1] == ("save_file", "Rapport final é.pdf")  # nom d'origine proposé
    assert out.read_bytes() == content
    assert run_files(app) == []  # le clair temporaire a disparu

    api(client, f"/api/taches/{job}/ouvrir-dossier", {})
    assert dialogs.revealed == [files]


def test_chiffrer_pour_une_de_mes_cles_en_aes128(client, app, dialogs, files, backend):
    make_identity(client, name="Bob")
    bob = backend.list_identities()[0]
    (files / "a.txt").write_text("salut")
    encrypt(client, app, dialogs, files / "a.txt", files / "p.zip", bob.fingerprint,
            cipher="aes-128-gcm")  # fmt: skip
    _sel, job = decrypt(client, app, dialogs, files / "p.zip")
    assert status(client, job)["status"] == "done"


def test_extension_zip_ajoutee(client, app, dialogs, files, me):
    (files / "a.txt").write_text("x")
    job = encrypt(client, app, dialogs, files / "a.txt", files / "sans_extension", me.fingerprint)
    assert status(client, job)["saved"].endswith("sans_extension.zip")


def test_chiffrer_n_ecrase_jamais(client, app, dialogs, files, me):
    (files / "a.txt").write_text("x")
    (files / "deja.zip").write_text("à moi")
    sel = choose(client, dialogs, "file", files / "a.txt")
    dialogs.answers.append(files / "deja.zip")
    r = api(client, "/api/chiffrer", {"selection": sel["id"], "recipient": me.fingerprint})
    assert r.status_code == 400 and "n'écrase jamais" in r.get_json()["error"]
    assert (files / "deja.zip").read_text() == "à moi"


def test_enregistrer_n_ecrase_jamais(client, app, dialogs, files, me):
    (files / "a.txt").write_text("contenu")
    encrypt(client, app, dialogs, files / "a.txt", files / "p.zip", me.fingerprint)
    _sel, job = decrypt(client, app, dialogs, files / "p.zip")
    dialogs.answers.append(files / "a.txt")  # existe déjà
    r = api(client, f"/api/taches/{job}/enregistrer", {"mode": "file"})
    assert r.status_code == 400 and "n'écrase jamais" in r.get_json()["error"]
    dialogs.answers.append(files / "a (copie).txt")  # on peut réessayer avec un autre nom
    assert api(client, f"/api/taches/{job}/enregistrer", {"mode": "file"}).status_code == 200


@pytest.mark.parametrize(
    "payload, msg",
    [
        ({"recipient": ""}, "Choisissez un destinataire"),
        ({"recipient": "inconnu"}, "Choisissez un destinataire"),
        ({"cipher": "aes-256-cbc"}, "inconnu"),
    ],
)
def test_chiffrer_erreurs(client, dialogs, files, me, payload, msg):
    (files / "a.txt").write_text("x")
    sel = choose(client, dialogs, "file", files / "a.txt")
    body = {"selection": sel["id"], "recipient": me.fingerprint, **payload}
    r = api(client, "/api/chiffrer", body)
    assert r.status_code == 400 and msg in r.get_json()["error"]


def test_chiffrer_annule_a_l_enregistrement(client, dialogs, files, me):
    (files / "a.txt").write_text("x")
    sel = choose(client, dialogs, "file", files / "a.txt")
    dialogs.answers.append(None)
    r = api(client, "/api/chiffrer", {"selection": sel["id"], "recipient": me.fingerprint})
    assert r.get_json() == {"cancelled": True}


# ------------------------------------------------------------------ dossiers (§ 5.4)
@pytest.fixture
def folder(files):
    d = files / "vacances"
    (d / "sous").mkdir(parents=True)
    (d / "vide").mkdir()
    (d / "plage.jpg").write_bytes(b"photo1" * 1000)
    (d / "sous" / "coucher_soleil.jpg").write_bytes(b"photo2" * 500)
    try:
        (d / "lien").symlink_to(files)  # pourrait pointer hors du dossier : ignoré
    except OSError:
        pass  # Windows sans droits de créer des liens
    return d


def test_aller_retour_dossier_extrait(client, app, dialogs, files, me, folder):
    encrypt(client, app, dialogs, folder, files / "p.zip", me.fingerprint, what="folder")
    assert not [p for p in files.iterdir() if p.name.endswith(".part")]  # zip temporaire supprimé
    _sel, job = decrypt(client, app, dialogs, files / "p.zip")
    st = status(client, job)
    assert st["is_folder"] is True and st["name"] == "vacances"

    dest = files / "Bureau"
    dest.mkdir()
    (dest / "vacances").mkdir()  # nom déjà pris : nouveau dossier « vacances (2) »
    dialogs.answers.append(dest)
    r = api(client, f"/api/taches/{job}/enregistrer", {"mode": "extract"})
    out = dest / "vacances (2)"
    assert r.get_json()["saved"] == str(out)
    assert (out / "plage.jpg").read_bytes() == b"photo1" * 1000
    assert (out / "sous" / "coucher_soleil.jpg").read_bytes() == b"photo2" * 500
    assert (out / "vide").is_dir() and not (out / "lien").exists()
    assert list((dest / "vacances").iterdir()) == []  # rien d'existant n'est touché
    assert run_files(app) == []
    api(client, f"/api/taches/{job}/ouvrir-dossier", {})
    assert dialogs.revealed == [out]


def test_dossier_garde_en_zip(client, app, dialogs, files, me, folder):
    encrypt(client, app, dialogs, folder, files / "p.zip", me.fingerprint, what="folder")
    _sel, job = decrypt(client, app, dialogs, files / "p.zip")
    dialogs.answers.append(files / "vacances.zip")
    api(client, f"/api/taches/{job}/enregistrer", {"mode": "zip"})
    assert dialogs.calls[-1] == ("save_file", "vacances.zip")
    with zipfile.ZipFile(files / "vacances.zip") as zf:
        assert "plage.jpg" in zf.namelist() and "sous/coucher_soleil.jpg" in zf.namelist()


def test_extraire_un_fichier_seul_refuse(client, app, dialogs, files, me):
    (files / "a.txt").write_text("x")
    encrypt(client, app, dialogs, files / "a.txt", files / "p.zip", me.fingerprint)
    _sel, job = decrypt(client, app, dialogs, files / "p.zip")
    assert api(client, f"/api/taches/{job}/enregistrer", {"mode": "extract"}).status_code == 400


def _zip(members: dict, path):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


@pytest.mark.parametrize("name", ["../evil.txt", "/abs.txt", "C:/x.txt", "a/../../b.txt"])
def test_extraction_zip_slip(files, name):
    z = _zip({"ok.txt": b"ok", name: b"pirate"}, files / "slip.zip")
    from crypteasy.ui.errors import UnsafeArchive

    with pytest.raises(UnsafeArchive):
        extract_folder(z, files)
    assert not (files / "slip").exists()  # le dossier à moitié extrait est supprimé
    assert not (files.parent / "evil.txt").exists()


def test_extraction_zip_bomb(files):
    path = files / "bombe.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("zeros.bin", b"\0" * (30 * 1024 * 1024))  # ~30 Ko compressé
    from crypteasy.ui.errors import ExtractionTooLarge

    with pytest.raises(ExtractionTooLarge):
        extract_folder(path, files)
    assert not (files / "bombe").exists()


def test_extraction_lien_symbolique_refuse(files):
    path = files / "lien.zip"
    with zipfile.ZipFile(path, "w") as zf:
        info = zipfile.ZipInfo("lien")
        info.external_attr = 0o120777 << 16  # S_IFLNK
        zf.writestr(info, "/etc/passwd")
    from crypteasy.ui.errors import UnsafeArchive

    with pytest.raises(UnsafeArchive):
        extract_folder(path, files)


# ------------------------------------------------------------------ erreurs F7
def test_mauvaise_phrase_secrete(client, app, dialogs, files, me):
    (files / "a.txt").write_text("x")
    encrypt(client, app, dialogs, files / "a.txt", files / "p.zip", me.fingerprint)
    _sel, job = decrypt(client, app, dialogs, files / "p.zip", passphrase=WRONG_PW)
    st = status(client, job)
    assert st == {"status": "error", "percent": 0,
                  "error": "Phrase secrète incorrecte pour cette clé."}  # fmt: skip
    assert run_files(app) == []


def test_aucune_de_mes_cles(client, app, dialogs, files, backend, me):
    (files / "a.txt").write_text("x")
    encrypt(client, app, dialogs, files / "a.txt", files / "p.zip", me.fingerprint)
    backend.delete_identity(me.fingerprint)
    sel, err = decrypt(client, app, dialogs, files / "p.zip")
    assert sel["key"] is None
    assert sel["no_key_message"] == "Ce fichier n'a été chiffré pour aucune de vos clés."
    assert err["error"] == sel["no_key_message"]


def test_dechiffrer_avec_un_fichier_de_cle(client, app, dialogs, files, backend, me):
    (files / "a.txt").write_text("via fichier de clé")
    encrypt(client, app, dialogs, files / "a.txt", files / "p.zip", me.fingerprint)
    backend.export_private_key(me.fingerprint, files / "perso.key")
    backend.delete_identity(me.fingerprint)
    key_sel = choose(client, dialogs, "key-file", files / "perso.key")["id"]
    _sel, job = decrypt(client, app, dialogs, files / "p.zip", key_selection=key_sel)
    dialogs.answers.append(files / "b.txt")
    api(client, f"/api/taches/{job}/enregistrer", {"mode": "file"})
    assert (files / "b.txt").read_text() == "via fichier de clé"


def test_cle_sans_phrase_secrete(client, app, dialogs, files, backend):
    post(client, "/cles", {"name": "Libre", "no_passphrase": "1", "no_passphrase_confirm": "1"})
    key = backend.list_identities()[0]
    (files / "a.txt").write_text("x")
    encrypt(client, app, dialogs, files / "a.txt", files / "p.zip", key.fingerprint)
    sel, job = decrypt(client, app, dialogs, files / "p.zip", passphrase="")
    assert sel["key"]["protected"] is False and status(client, job)["status"] == "done"


def _rewrite(package, member, edit):
    src = zipfile.ZipFile(package)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as dst:
        for name in src.namelist():
            data = src.read(name)
            dst.writestr(name, edit(data) if name == member else data)
    package.write_bytes(out.getvalue())


@pytest.mark.parametrize(
    "edit",
    [
        lambda b: b[:-40] + bytes([b[-40] ^ 1]) + b[-39:],  # 1 bit du contenu
        lambda b: b[:-100],  # tronqué
        lambda b: b.replace(b"aes-256-gcm", b"aes-128-gcm"),  # réglage de l'en-tête modifié
    ],
)
def test_paquet_modifie(client, app, dialogs, files, me, edit):
    (files / "a.txt").write_bytes(b"A" * 10_000)
    encrypt(client, app, dialogs, files / "a.txt", files / "p.zip", me.fingerprint)
    _rewrite(files / "p.zip", "file.enc", edit)
    _sel, job = decrypt(client, app, dialogs, files / "p.zip")
    st = status(client, job)
    assert st["error"] == "Ce fichier est endommagé ou a été modifié. Rien n'a été déchiffré."
    assert run_files(app) == []  # pas de déchiffré partiel


@pytest.mark.parametrize(
    "content",
    [
        b"%PDF-1.7 pas du tout un zip",
        None,  # zip sans key.enc
    ],
)
def test_pas_un_paquet_crypteasy(client, dialogs, files, content):
    path = files / "x.zip"
    if content is None:
        _zip({"autre.txt": b"x"}, path)
    else:
        path.write_bytes(content)
    dialogs.answers.append(path)
    r = api(client, "/api/choisir", {"what": "package"})
    assert r.status_code == 400
    assert "pas un fichier CryptEasy" in r.get_json()["error"]


def test_erreur_imprevue_message_generique(client, app, dialogs, files, backend, me,
                                           monkeypatch, caplog):  # fmt: skip
    def boom(*_a, **_k):
        raise RuntimeError("détail interne secret")

    monkeypatch.setattr(backend, "encrypt", boom)
    (files / "a.txt").write_text("x")
    job = encrypt(client, app, dialogs, files / "a.txt", files / "p.zip", me.fingerprint)
    st = status(client, job)
    assert st["status"] == "error" and "Erreur inattendue" in st["error"]
    assert "détail interne secret" not in str(st) and "détail interne secret" not in caplog.text


def test_tache_inconnue(client):
    assert api(client, "/api/taches/inconnue", method="GET").status_code == 404


def test_enregistrer_avant_la_fin_ou_deux_fois(client, app, dialogs, files, me):
    (files / "a.txt").write_text("x")
    encrypt(client, app, dialogs, files / "a.txt", files / "p.zip", me.fingerprint)
    _sel, job = decrypt(client, app, dialogs, files / "p.zip")
    dialogs.answers.append(files / "b.txt")
    api(client, f"/api/taches/{job}/enregistrer", {"mode": "file"})
    r = api(client, f"/api/taches/{job}/enregistrer", {"mode": "file"})
    assert r.status_code == 400 and "plus rien à enregistrer" in r.get_json()["error"]


def test_abandonner_supprime_le_clair(client, app, dialogs, files, me):
    (files / "a.txt").write_text("x")
    encrypt(client, app, dialogs, files / "a.txt", files / "p.zip", me.fingerprint)
    _sel, job = decrypt(client, app, dialogs, files / "p.zip")
    assert run_files(app)  # le fichier déchiffré attend d'être enregistré
    api(client, f"/api/taches/{job}/abandonner", {})
    assert run_files(app) == []


def test_contact_preselectionne_et_note(client, me):
    page = client.get("/chiffrer", query_string={"contact": me.fingerprint}).get_data(as_text=True)
    assert f'value="{me.fingerprint}" data-rate-value="x25519" selected' in page
    assert "X25519 : courbe elliptique moderne" in page


def test_gros_fichier_signale(client, dialogs, files, monkeypatch):
    from crypteasy.ui.routes import api as api_module

    monkeypatch.setattr(api_module, "BIG_FILE", 10)
    (files / "a.bin").write_bytes(b"x" * 100)
    assert choose(client, dialogs, "file", files / "a.bin")["big"] is True


@pytest.mark.skipif(os.name == "nt", reason="liens symboliques")
def test_taille_ignore_les_liens(client, dialogs, files):
    d = files / "d"
    d.mkdir()
    (d / "a").write_bytes(b"x" * 10)
    (d / "lien").symlink_to(d / "a")
    assert choose(client, dialogs, "folder", d)["files"] == 1
