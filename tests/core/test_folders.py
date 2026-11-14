import os
import stat
import sys
import warnings
import zipfile

import pytest

from crypteasy.core import folders
from crypteasy.core.errors import DecryptionError, ExtractionTooLargeError, UnsafeArchiveError

"""
In this file I test core/folders.py
Run only these tests with: make test-core
Every test works in tmp_path, a temp folder pytest creates and deletes for each test
"""


# This func makes a small test folder with subfolders, an empty folder, an empty file,
# a non-ASCII name and some binary data, and gives back its path
def make_folder(tmp_path):
    src = tmp_path / "holidays"
    (src / "beach").mkdir(parents=True)
    (src / "empty").mkdir()
    (src / "notes.txt").write_text("hello")
    (src / "beach" / "été.jpg").write_bytes(os.urandom(200_000))
    (src / "beach" / "empty.txt").write_bytes(b"")
    return src


# This func gives every file and folder of a tree, with the content of each file,
# so 2 trees can be compared with ==
def tree(root):
    result = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        result[rel] = path.read_bytes() if path.is_file() else "folder"
    return result


# This func builds a zip by hand with the given entries (name -> content), to make
# crafted zips like an attacker would. It gives back the zip path
def crafted_zip(tmp_path, entries, name="evil.zip"):
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as zf:
        for entry_name, content in entries.items():
            zf.writestr(entry_name, content)
    return path


# This func checks that nothing was extracted: the out folder is still empty, and
# no file escaped next to it
def assert_nothing_left(out, tmp_path, before):
    assert list(out.iterdir()) == []
    assert sorted(p.name for p in tmp_path.iterdir()) == before


# ----------------------------------------------------------------- normal folders


# A folder zipped then extracted comes back exactly the same: same files, same content,
# empty folder and empty file kept
def test_round_trip(tmp_path):
    src = make_folder(tmp_path)
    zip_path = tmp_path / "holidays.zip"
    folders.zip_folder(src, zip_path)

    out = tmp_path / "out"
    out.mkdir()
    result = folders.extract_folder(zip_path, out)

    assert result == out / "holidays"
    assert tree(result) == tree(src)


# The zip is not compressed (ZIP_STORED) and holds relative paths only
def test_zip_is_stored_with_relative_paths(tmp_path):
    src = make_folder(tmp_path)
    zip_path = tmp_path / "holidays.zip"
    folders.zip_folder(src, zip_path)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert all(info.compress_type == zipfile.ZIP_STORED for info in zf.infolist())
    assert "notes.txt" in names
    assert "beach/été.jpg" in names
    assert "empty/" in names
    assert not any(name.startswith(("/", "holidays")) for name in names)


# An empty folder gives an empty zip, and extracting it gives an empty folder
def test_empty_folder(tmp_path):
    src = tmp_path / "nothing"
    src.mkdir()
    zip_path = tmp_path / "nothing.zip"
    folders.zip_folder(src, zip_path)

    out = tmp_path / "out"
    out.mkdir()
    result = folders.extract_folder(zip_path, out)
    assert result.is_dir()
    assert list(result.iterdir()) == []


# Extracting never goes into an existing folder: the 2nd time gives "holidays (2)"
# and the 1st folder is left untouched
def test_never_overwrites_an_existing_folder(tmp_path):
    src = make_folder(tmp_path)
    zip_path = tmp_path / "holidays.zip"
    folders.zip_folder(src, zip_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "holidays").mkdir()
    (out / "holidays" / "mine.txt").write_text("keep me")

    first = folders.extract_folder(zip_path, out)
    second = folders.extract_folder(zip_path, out)

    assert first == out / "holidays (2)"
    assert second == out / "holidays (3)"
    assert tree(out / "holidays") == {"mine.txt": b"keep me"}


# Symlinks (to a file or to a folder) are not put in the zip, they could point
# anywhere on the disk. Windows needs special rights to create symlinks, so it's skipped there
@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need admin rights on Windows")
def test_symlinks_are_skipped(tmp_path):
    secret = tmp_path / "secret"
    secret.mkdir()
    (secret / "passwords.txt").write_text("hunter2")
    src = make_folder(tmp_path)
    (src / "link_to_file").symlink_to(secret / "passwords.txt")
    (src / "link_to_folder").symlink_to(secret, target_is_directory=True)

    zip_path = tmp_path / "holidays.zip"
    folders.zip_folder(src, zip_path)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert not any("link_to" in name or "passwords" in name for name in names)


# If zipping fails halfway (e.g. a file can't be read), the half-written zip is deleted:
# it would hold some of the files not encrypted. To make the 3rd file fail on every OS,
# ZipFile.write is replaced by a version that raises an error on the 3rd call
def test_zip_is_deleted_if_zipping_fails(tmp_path, monkeypatch):
    src = tmp_path / "holidays"
    src.mkdir()
    for i in range(3):
        (src / f"photo{i}.jpg").write_bytes(os.urandom(1000))
    real_write = zipfile.ZipFile.write
    calls = []

    def failing_write(self, filename, arcname=None, *args, **kwargs):
        calls.append(arcname)
        if len(calls) == 3:
            raise PermissionError("can't read this photo")
        return real_write(self, filename, arcname, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "write", failing_write)
    zip_path = tmp_path / "holidays.zip"

    with pytest.raises(PermissionError):
        folders.zip_folder(src, zip_path)
    assert len(calls) == 3
    assert not zip_path.exists()


# ----------------------------------------------------------------- zip-slip

# Each of these names tries to write outside the new folder
unsafe_names = [
    "../evil.txt",
    "../../evil.txt",
    "sub/../../evil.txt",
    "..\\evil.txt",
    "sub\\..\\..\\evil.txt",
    "/home/evil.txt",
    "\\evil.txt",
    "C:/evil.txt",
    "C:evil.txt",
    "notes.txt:hidden",
]


# A zip with a dangerous path is refused, the new folder is deleted
# and nothing is written, not even the good file put before the bad one
@pytest.mark.parametrize("bad_name", unsafe_names)
def test_zip_slip_is_refused(tmp_path, bad_name):
    zip_path = crafted_zip(tmp_path, {"good.txt": b"ok", bad_name: b"pwned"})
    out = tmp_path / "out"
    out.mkdir()
    before = sorted(p.name for p in tmp_path.iterdir())

    with pytest.raises(UnsafeArchiveError):
        folders.extract_folder(zip_path, out)
    assert_nothing_left(out, tmp_path, before)
    assert not (tmp_path / "evil.txt").exists()


# A symlink entry in the zip is refused: once on the disk it could send the next files
# anywhere (e.g. "link" -> /etc, then "link/passwd")
def test_symlink_entry_is_refused(tmp_path):
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        info = zipfile.ZipInfo("link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, "/etc")
    out = tmp_path / "out"
    out.mkdir()

    with pytest.raises(UnsafeArchiveError):
        folders.extract_folder(zip_path, out)
    assert list(out.iterdir()) == []


# The same name twice, or a path going "through" a file: refused, nothing overwritten
@pytest.mark.parametrize(
    "entries",
    [
        [("a.txt", b"first"), ("a.txt", b"second")],
        [("a", b"a file"), ("a/b.txt", b"inside a file?")],
    ],
)
def test_duplicate_paths_are_refused(tmp_path, entries):
    zip_path = tmp_path / "evil.zip"
    # zipfile warns when a name is written twice, that's exactly what we want here
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for name, content in entries:
                zf.writestr(name, content)
    out = tmp_path / "out"
    out.mkdir()

    with pytest.raises(UnsafeArchiveError):
        folders.extract_folder(zip_path, out)
    assert list(out.iterdir()) == []


# Windows device names (CON, NUL, COM1, ...) get a "_" in front, files AND folders,
# with or without an extension and whatever the case. Other names are left alone
def test_windows_device_names_are_renamed(tmp_path):
    zip_path = crafted_zip(
        tmp_path,
        {
            "nul.txt": b"1",
            "aux/notes.txt": b"2",
            "Com1.log": b"3",
            "LPT9": b"4",
            "con.tar.gz": b"5",
            "console.txt": b"6",
            "null.txt": b"7",
            "notes/prn": b"8",
        },
    )
    out = tmp_path / "out"
    out.mkdir()

    result = folders.extract_folder(zip_path, out)

    assert tree(result) == {
        "_nul.txt": b"1",
        "_aux": "folder",
        "_aux/notes.txt": b"2",
        "_Com1.log": b"3",
        "_LPT9": b"4",
        "_con.tar.gz": b"5",
        "console.txt": b"6",
        "null.txt": b"7",
        "notes": "folder",
        "notes/_prn": b"8",
    }


# ----------------------------------------------------------------- zip bomb


# A small zip that becomes huge once extracted (here 20 MiB of zeros, compressed to a few
# KiB) is stopped, and the part already extracted is deleted
def test_zip_bomb_is_stopped(tmp_path):
    zip_path = tmp_path / "bomb.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("zeros.bin", b"\0" * (20 * 1024 * 1024))
    assert zip_path.stat().st_size < 1024 * 1024
    out = tmp_path / "out"
    out.mkdir()

    with pytest.raises(ExtractionTooLargeError):
        folders.extract_folder(zip_path, out)
    assert list(out.iterdir()) == []


# Too many files in the zip: refused before writing anything
def test_too_many_files(tmp_path, monkeypatch):
    monkeypatch.setattr(folders, "max_files", 5)
    zip_path = crafted_zip(tmp_path, {f"f{i}.txt": b"x" for i in range(6)})
    out = tmp_path / "out"
    out.mkdir()

    with pytest.raises(ExtractionTooLargeError):
        folders.extract_folder(zip_path, out)
    assert list(out.iterdir()) == []


# The limit is 10 times the zip size, at least 1 MiB, at most 20 GiB
def test_size_limit():
    assert folders.size_limit(0) == 1024 * 1024
    assert folders.size_limit(10 * 1024 * 1024) == 100 * 1024 * 1024
    assert folders.size_limit(10 * 1024**4) == 20 * 1024**3


# ----------------------------------------------------------------- broken zip


# Something that is not a zip at all: DecryptionError, the new folder is deleted
def test_not_a_zip(tmp_path):
    zip_path = tmp_path / "broken.zip"
    zip_path.write_bytes(os.urandom(1000))
    out = tmp_path / "out"
    out.mkdir()

    with pytest.raises(DecryptionError):
        folders.extract_folder(zip_path, out)
    assert list(out.iterdir()) == []
