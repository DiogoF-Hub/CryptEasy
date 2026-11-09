"""Noms de fichiers, écrasement, tailles, fichiers temporaires (SPEC § 5.5, § 8)."""

import os
import time

import pytest

from crypteasy.ui.errors import BadInput, FileExists
from crypteasy.ui.files import (
    describe,
    estimate_seconds,
    init_files,
    move_no_overwrite,
    original_name,
    safe_filename,
    unique_child,
)


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


@pytest.mark.parametrize(
    "raw, expected",
    [("../../evil.exe", "evil.exe"), ("", "decrypted_file"), ("..", "decrypted_file"),
     ("a\x00b", "decrypted_file"), (None, "decrypted_file"), ("vacances.zip", "vacances.zip")],
)  # fmt: skip
def test_nom_d_origine_lu_dans_un_paquet(raw, expected):
    """§ 8 : nom de base seulement, sinon nom de repli « decrypted_file »."""
    assert original_name(raw) == expected


def test_unique_child(tmp_path):
    assert unique_child(tmp_path, "vacances") == tmp_path / "vacances"
    (tmp_path / "vacances").mkdir()
    (tmp_path / "vacances (2)").mkdir()
    assert unique_child(tmp_path, "vacances") == tmp_path / "vacances (3)"
    (tmp_path / "a.txt").write_text("x")
    assert unique_child(tmp_path, "a.txt") == tmp_path / "a (2).txt"


def test_move_no_overwrite(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.write_text("nouveau")
    dst.write_text("ancien")
    with pytest.raises(FileExists):
        move_no_overwrite(src, dst)
    assert dst.read_text() == "ancien" and src.exists()
    move_no_overwrite(src, tmp_path / "libre")
    assert (tmp_path / "libre").read_text() == "nouveau" and not src.exists()


def test_describe(tmp_path):
    (tmp_path / "d" / "e").mkdir(parents=True)
    (tmp_path / "d" / "a").write_bytes(b"x" * 10)
    (tmp_path / "d" / "e" / "b").write_bytes(b"x" * 5)
    assert describe(tmp_path / "d") == (15, 2)
    assert describe(tmp_path / "d" / "a") == (10, 1)


def test_estimation():
    assert estimate_seconds(100, None) is None
    assert estimate_seconds(100, 50) == 2
    assert estimate_seconds(100, 50, is_folder=True) == pytest.approx(2.6)


def test_nettoyage_au_demarrage(tmp_path, app):
    """Les restes d'un lancement planté sont supprimés ; ceux d'une autre instance
    encore active (fichiers récents) sont épargnés."""
    old = tmp_path / "run-ancien"
    (old / "job").mkdir(parents=True)
    (old / "job" / "clair.bin").write_text("x")
    past = time.time() - 7200
    for p in (old / "job" / "clair.bin", old / "job", old):
        os.utime(p, (past, past))
    recent = tmp_path / "run-actif"
    recent.mkdir()
    (recent / "en_cours.part").write_text("x")
    init_files(app, tmp_path)
    assert not old.exists() and recent.exists()
