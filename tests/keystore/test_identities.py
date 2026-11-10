import base64
import json
import os

import pytest

from crypteasy.keystore import identities as ids
from crypteasy.keystore import paths
from crypteasy.keystore.errors import (
    AlreadyExistsError,
    InvalidNameError,
    InvalidPrivateKeyError,
    InvalidSettingError,
    NotFoundError,
    WrongPassphraseError,
)
from crypteasy.keystore.identities import Protection

from .conftest import OTHER_PW, PW, fake_pem

pytestmark = pytest.mark.usefixtures("fake_core")

# Every security level of section 4.2, as the UI would send it
LEVEL_PROTECTIONS = {
    "very_strong": Protection(PW, "argon2id", "max", 32, "very_strong"),
    "strong": Protection(PW, "argon2id", "normal", 16, "strong"),
    "medium": Protection(PW, "pbkdf2-sha256", "normal", 16, "medium"),
    "weak": Protection(PW, "pbkdf2-sha256", "normal", 0, "weak"),
    "none": Protection(None, level="none"),
}


def _create(name="Alice", key_type="x25519", protection=LEVEL_PROTECTIONS["strong"]):
    return ids.create_identity(name, key_type, protection)


def _folder(ident):
    (folder,) = [f for f in paths.keys_dir().iterdir() if not f.name.startswith(".")]
    return folder


# ----------------------------------------------------------------- create / unlock


@pytest.mark.parametrize("level", LEVEL_PROTECTIONS)
def test_create_then_unlock_every_level(level):
    protection = LEVEL_PROTECTIONS[level]
    ident = _create(protection=protection)
    assert ident.level == level
    assert ident.protected is (protection.passphrase is not None)
    assert ids.list_identities() == [ident]
    secret = ids.unlock(ident.fingerprint, protection.passphrase)
    assert secret.startswith(b"SECRET:")


@pytest.mark.parametrize("level", ["very_strong", "strong", "medium", "weak"])
def test_wrong_passphrase(level):
    ident = _create(protection=LEVEL_PROTECTIONS[level])
    with pytest.raises(WrongPassphraseError):
        ids.unlock(ident.fingerprint, OTHER_PW)
    with pytest.raises(WrongPassphraseError):
        ids.unlock(ident.fingerprint, None)


def test_unprotected_key_is_stored_in_clear_and_flagged():
    ident = _create(protection=LEVEL_PROTECTIONS["none"])
    doc = json.loads((_folder(ident) / "private.key").read_bytes())
    assert doc["kdf"] == "none" and "plaintext" in doc
    assert ident.protected is False


def test_protected_key_never_contains_the_secret():
    ident = _create()
    secret = ids.unlock(ident.fingerprint, PW)
    raw = (_folder(ident) / "private.key").read_bytes()
    assert secret not in raw and base64.b64encode(secret) not in raw


def test_salts_and_nonces_are_random():
    _create("A")
    _create("B")
    a, b = [json.loads((f / "private.key").read_bytes()) for f in paths.keys_dir().iterdir()]
    assert a["salt"] != b["salt"] and a["nonce"] != b["nonce"]


def test_layout_on_disk():
    ident = _create()
    folder = _folder(ident)
    assert sorted(p.name for p in folder.iterdir()) == ["info.json", "private.key", "public.pem"]
    info = json.loads((folder / "info.json").read_bytes())
    assert info["name"] == "Alice" and info["fingerprint"] == ident.fingerprint
    assert "Alice" not in folder.name  # the folder name never comes from user input


def test_several_key_pairs():
    _create("Alice")
    _create("Bob", "rsa-3072")
    assert [i.name for i in ids.list_identities()] == ["Alice", "Bob"]


def test_duplicate_name_rejected():
    _create("Alice")
    with pytest.raises(AlreadyExistsError):
        _create("Alice")


@pytest.mark.parametrize(
    ("key_type", "protection", "error"),
    [
        ("dsa", LEVEL_PROTECTIONS["strong"], InvalidSettingError),
        ("x25519", Protection(PW, "scrypt"), InvalidSettingError),
        ("x25519", Protection(PW, "argon2id", salt_len=0), InvalidSettingError),
        ("x25519", Protection(PW, "pbkdf2-sha256", salt_len=8), InvalidSettingError),
        ("x25519", Protection(PW, kdf_strength="ultra"), InvalidSettingError),
        ("x25519", Protection(b""), InvalidSettingError),
        ("x25519", Protection(PW, level="excellent"), InvalidSettingError),
    ],
)
def test_bad_settings_rejected_and_nothing_written(key_type, protection, error):
    with pytest.raises(error):
        ids.create_identity("Alice", key_type, protection)
    assert list(paths.keys_dir().iterdir()) == []


def test_bad_name_rejected():
    with pytest.raises(InvalidNameError):
        _create("")


def test_crash_while_writing_leaves_nothing(monkeypatch):
    def crash(src, dst):
        raise OSError("simulated crash")

    monkeypatch.setattr(os, "rename", crash)
    with pytest.raises(OSError, match="simulated"):
        _create()
    assert list(paths.keys_dir().iterdir()) == []


def test_passphrase_not_in_repr():
    assert PW.decode() not in repr(LEVEL_PROTECTIONS["strong"])


# ----------------------------------------------------------------- change / rename / delete


def test_change_protection():
    ident = _create()
    new = Protection(OTHER_PW, "pbkdf2-sha256", "normal", 16, "medium")
    updated = ids.change_protection(ident.fingerprint, PW, new)
    assert updated.level == "medium"
    with pytest.raises(WrongPassphraseError):
        ids.unlock(ident.fingerprint, PW)
    assert ids.unlock(ident.fingerprint, OTHER_PW).startswith(b"SECRET:")


def test_change_protection_to_and_from_no_passphrase():
    ident = _create()
    secret = ids.unlock(ident.fingerprint, PW)
    ids.change_protection(ident.fingerprint, PW, LEVEL_PROTECTIONS["none"])
    assert ids.get_identity(ident.fingerprint).protected is False
    ids.change_protection(ident.fingerprint, None, LEVEL_PROTECTIONS["strong"])
    assert ids.unlock(ident.fingerprint, PW) == secret


def test_change_protection_wrong_passphrase_changes_nothing():
    ident = _create()
    before = (_folder(ident) / "private.key").read_bytes()
    with pytest.raises(WrongPassphraseError):
        ids.change_protection(ident.fingerprint, OTHER_PW, LEVEL_PROTECTIONS["medium"])
    assert (_folder(ident) / "private.key").read_bytes() == before


def test_rename():
    ident = _create("Alice")
    _create("Bob")
    assert ids.rename_identity(ident.fingerprint, "Alice laptop").name == "Alice laptop"
    assert ids.rename_identity(ident.fingerprint, "Alice laptop").name == "Alice laptop"
    with pytest.raises(AlreadyExistsError):
        ids.rename_identity(ident.fingerprint, "Bob")


def test_delete():
    a = _create("Alice")
    b = _create("Bob")
    ids.delete_identity(a.fingerprint)
    assert ids.list_identities() == [b]
    assert not any(f.name.startswith(".deleted") for f in paths.keys_dir().iterdir())


def test_unknown_fingerprint():
    for call in (
        lambda: ids.unlock("0000", PW),
        lambda: ids.get_identity("0000"),
        lambda: ids.rename_identity("0000", "x"),
        lambda: ids.delete_identity("0000"),
        lambda: ids.change_protection("0000", PW, LEVEL_PROTECTIONS["strong"]),
        lambda: ids.public_pem("0000"),
    ):
        with pytest.raises(NotFoundError):
            call()


def test_hidden_folders_ignored():
    (paths.keys_dir() / ".tmp-leftover").mkdir()
    assert ids.list_identities() == []


# ----------------------------------------------------------------- export


def test_export_public_and_private(tmp_path):
    ident = _create()
    ids.export_public_key(ident.fingerprint, tmp_path / "alice.pem")
    ids.export_private_key(ident.fingerprint, tmp_path / "alice.key")
    assert (tmp_path / "alice.pem").read_bytes() == ids.public_pem(ident.fingerprint)
    exported = (tmp_path / "alice.key").read_bytes()
    assert exported == (_folder(ident) / "private.key").read_bytes()
    assert ids.open_secret(exported, PW) == ids.unlock(ident.fingerprint, PW)


def test_export_never_overwrites(tmp_path):
    ident = _create()
    dst = tmp_path / "taken.pem"
    dst.write_bytes(b"mine")
    with pytest.raises(FileExistsError):
        ids.export_public_key(ident.fingerprint, dst)
    with pytest.raises(FileExistsError):
        ids.export_private_key(ident.fingerprint, dst)
    assert dst.read_bytes() == b"mine"


# ----------------------------------------------------------------- damaged / hostile files


def _assert_damaged():
    assert ids.list_identities() == []
    assert len(ids.damaged_identities()) == 1


def _edit_json(path, change):
    doc = json.loads(path.read_bytes())
    change(doc)
    path.write_text(json.dumps(doc))


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(version=2),
        lambda d: d.update(name="Bob\n"),
        lambda d: d.update(level="ultra"),
        lambda d: d.update(fingerprint="AAAA " * 15 + "AAAA"),
        lambda d: d.update(key_type="rsa-4096"),
        lambda d: d.pop("created"),
    ],
)
def test_hand_edited_info_detected(change):
    ident = _create()
    _edit_json(_folder(ident) / "info.json", change)
    _assert_damaged()


def test_swapped_public_key_detected():
    ident = _create()
    (_folder(ident) / "public.pem").write_bytes(fake_pem())
    _assert_damaged()


@pytest.mark.parametrize("missing", ["info.json", "public.pem", "private.key"])
def test_missing_file_detected(missing):
    ident = _create()
    (_folder(ident) / missing).unlink()
    _assert_damaged()


def _sealed(protection=None):
    return ids.seal_secret(b"SECRET:x", protection or LEVEL_PROTECTIONS["strong"])


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(format="pem"),
        lambda d: d.update(version=2),
        lambda d: d.update(kdf="scrypt"),
        lambda d: d.update(extra=1),
        lambda d: d.pop("nonce"),
        lambda d: d.update(nonce=base64.b64encode(b"short").decode()),
        lambda d: d.update(salt="not base64!"),
        lambda d: d.update(salt=""),  # argon2id needs a salt
        lambda d: d.update(ciphertext=base64.b64encode(b"tiny").decode()),
        lambda d: d["params"].update(memory_kib=4 * 1024 * 1024),  # 4 GiB: refused
        lambda d: d["params"].update(memory_kib=2**64),
        lambda d: d["params"].update(iterations=10**9),
        lambda d: d["params"].update(parallelism=0),
        lambda d: d["params"].update(parallelism=True),
        lambda d: d["params"].update(iterations="3"),
        lambda d: d["params"].update(extra=1),
        lambda d: d.update(params=[]),
    ],
)
def test_hostile_private_key_rejected_before_kdf(change, monkeypatch):
    doc = json.loads(_sealed())
    change(doc)

    def kdf_must_not_run(*args):
        raise AssertionError("KDF ran on unchecked parameters")

    monkeypatch.setattr(ids._core, "derive_lock_key", kdf_must_not_run)
    with pytest.raises(InvalidPrivateKeyError):
        ids.open_secret(json.dumps(doc).encode(), PW)


def test_pbkdf2_iterations_bounded():
    doc = json.loads(_sealed(LEVEL_PROTECTIONS["medium"]))
    doc["params"]["iterations"] = 50_000_000
    with pytest.raises(InvalidPrivateKeyError):
        ids.open_secret(json.dumps(doc).encode(), PW)


@pytest.mark.parametrize("data", [b"", b"{", b"[]", b"\xff", b"{}" + b" " * 70_000])
def test_garbage_private_key_rejected(data):
    with pytest.raises(InvalidPrivateKeyError):
        ids.open_secret(data, PW)


def test_tampered_ciphertext_fails_closed():
    doc = json.loads(_sealed())
    ct = bytearray(base64.b64decode(doc["ciphertext"]))
    ct[0] ^= 1
    doc["ciphertext"] = base64.b64encode(bytes(ct)).decode()
    with pytest.raises(WrongPassphraseError):
        ids.open_secret(json.dumps(doc).encode(), PW)


# ----------------------------------------------------------------- review fixes


def test_damaged_folder_does_not_block_healthy_keys():
    bad = _create("Alice")
    _edit_json(_folder(bad) / "info.json", lambda d: d.update(version=99))
    good = _create("Bob")
    assert ids.list_identities() == [good]
    assert ids.unlock(good.fingerprint, PW).startswith(b"SECRET:")
    ids.rename_identity(good.fingerprint, "Robert")
    (damaged,) = ids.damaged_identities()
    ids.delete_damaged_identity(damaged)
    assert ids.damaged_identities() == []
    ids.delete_identity(good.fingerprint)
    assert list(paths.keys_dir().iterdir()) == []


@pytest.mark.parametrize("key_id", ["../..", "nope", ".tmp-x", ""])
def test_delete_damaged_only_accepts_listed_ids(key_id):
    with pytest.raises(NotFoundError):
        ids.delete_damaged_identity(key_id)


def test_failed_delete_is_swept_on_next_write(monkeypatch):
    a = _create("Alice", protection=LEVEL_PROTECTIONS["none"])
    real_rmtree = ids.shutil.rmtree
    monkeypatch.setattr(ids.shutil, "rmtree", lambda *a, **k: None)  # delete "fails"
    ids.delete_identity(a.fingerprint)
    assert [f.name.startswith(".deleted-") for f in paths.keys_dir().iterdir()] == [True]
    monkeypatch.setattr(ids.shutil, "rmtree", real_rmtree)
    _create("Bob")
    assert not any(f.name.startswith(".") for f in paths.keys_dir().iterdir())


def test_leftover_tmp_folder_is_swept():
    leftover = paths.keys_dir() / ".tmp-crashed"
    leftover.mkdir()
    (leftover / "private.key").write_bytes(b"{}")
    _create()
    assert not leftover.exists()


@pytest.mark.parametrize(
    "protection",
    [Protection(None, level="very_strong"), Protection(PW, level="none")],
)
def test_level_must_match_passphrase(protection):
    with pytest.raises(InvalidSettingError):
        _create(protection=protection)
    ident = _create()
    with pytest.raises(InvalidSettingError):
        ids.change_protection(ident.fingerprint, PW, protection)


def test_unprotected_key_never_shown_as_protected():
    """info.json says very_strong, private.key is in clear: private.key wins."""
    ident = _create(protection=LEVEL_PROTECTIONS["none"])
    _edit_json(_folder(ident) / "info.json", lambda d: d.update(level="very_strong"))
    shown = ids.get_identity(ident.fingerprint)
    assert (shown.level, shown.protected) == ("none", False)


def test_protected_key_with_level_none_shown_as_custom():
    ident = _create()
    _edit_json(_folder(ident) / "info.json", lambda d: d.update(level="none"))
    shown = ids.get_identity(ident.fingerprint)
    assert (shown.level, shown.protected) == ("custom", True)


@pytest.mark.parametrize("name", ["info.json", "private.key"])
def test_deeply_nested_json_is_damage_not_crash(name):
    ident = _create()
    (_folder(ident) / name).write_bytes(b"[" * 16_000)
    _assert_damaged()


def test_deeply_nested_private_key_rejected():
    with pytest.raises(InvalidPrivateKeyError):
        ids.open_secret(b"[" * 60_000, PW)


@pytest.mark.parametrize(
    ("kdf", "salt_len", "params"),
    [  # the "max" presets of TECHNICAL_SPEC section 4.1 must load
        ("argon2id", 32, {"memory_kib": 1024 * 1024, "iterations": 4, "parallelism": 4}),
        ("pbkdf2-sha256", 32, {"iterations": 3_000_000}),
        ("pbkdf2-sha256", 0, {"iterations": 600_000}),
    ],
)
def test_spec_presets_within_bounds(kdf, salt_len, params):
    ids._check_params(kdf, salt_len, params)
