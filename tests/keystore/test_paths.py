import os
import sys

import pytest

from crypteasy.keystore import paths
from crypteasy.keystore.common import atomic_write, clean_name, read_limited, write_new
from crypteasy.keystore.errors import InvalidNameError


def test_data_dir_uses_env_override_and_creates_it(home):
    assert not home.exists()
    assert paths.data_dir() == home
    assert home.is_dir()


def test_data_dir_follows_env_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("CRYPTEASY_HOME", str(tmp_path / "a"))
    first = paths.data_dir()
    monkeypatch.setenv("CRYPTEASY_HOME", str(tmp_path / "b"))
    assert paths.data_dir() != first


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX default only")
def test_data_dir_default_is_per_user(monkeypatch, tmp_path):
    monkeypatch.delenv("CRYPTEASY_HOME")
    monkeypatch.setenv("HOME", str(tmp_path))
    expected = (
        tmp_path / "Library" / "Application Support" / "CryptEasy"
        if sys.platform == "darwin"
        else tmp_path / ".local" / "share" / "CryptEasy"
    )
    assert paths.data_dir() == expected


def test_settings_roundtrip():
    assert paths.load_settings() == {}
    paths.save_settings({"language": "fr"})
    assert paths.load_settings() == {"language": "fr"}


@pytest.mark.parametrize(
    "content", [b"{not json", b"[1, 2]", b"\xff\xfe", b"[" * 16_000, b"x" * 70_000]
)
def test_damaged_settings_fall_back_to_empty(content):
    paths.settings_file().write_bytes(content)
    assert paths.load_settings() == {}


def test_atomic_write_replaces_and_leaves_no_temp(tmp_path):
    target = tmp_path / "f.json"
    target.write_bytes(b"old")
    atomic_write(target, b"new")
    assert target.read_bytes() == b"new"
    assert os.listdir(tmp_path) == ["f.json"]


def test_atomic_write_keeps_old_file_on_crash(tmp_path, monkeypatch):
    target = tmp_path / "f.json"
    target.write_bytes(b"old")

    def crash(src, dst):
        raise OSError("simulated crash")

    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises(OSError, match="simulated"):
        atomic_write(target, b"new")
    assert target.read_bytes() == b"old"
    assert os.listdir(tmp_path) == ["f.json"]


def test_write_new_never_overwrites(tmp_path):
    target = tmp_path / "out.pem"
    write_new(target, b"one")
    with pytest.raises(FileExistsError):
        write_new(target, b"two")
    assert target.read_bytes() == b"one"


@pytest.mark.skipif(sys.platform == "win32", reason="Windows ignores POSIX modes")
def test_written_files_are_private(tmp_path):
    atomic_write(tmp_path / "a", b"x")
    write_new(tmp_path / "b", b"x")
    assert (tmp_path / "a").stat().st_mode & 0o077 == 0
    assert (tmp_path / "b").stat().st_mode & 0o077 == 0


def test_read_limited(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"12345")
    assert read_limited(f, 5) == b"12345"
    with pytest.raises(ValueError):
        read_limited(f, 4)


def test_clean_name():
    assert clean_name("  Alice laptop ") == "Alice laptop"
    assert clean_name("Zoé 🔑") == "Zoé 🔑"
    assert clean_name("a" * 64) == "a" * 64


@pytest.mark.parametrize("name", ["", "   ", "a" * 65, "Al\nice", "Al\x00ice", "Bob‮exe"])
def test_clean_name_rejects(name):
    with pytest.raises(InvalidNameError):
        clean_name(name)
