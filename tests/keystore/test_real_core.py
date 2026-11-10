"""keystore/ on top of the real core/keys.py (#6). Only the KDF is faked until #7.

Keys saved without a passphrase don't use the KDF at all, so those tests are fully real.
"""

import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa, x25519

from crypteasy.core import keys
from crypteasy.keystore import contacts, paths
from crypteasy.keystore import identities as ids
from crypteasy.keystore.errors import (
    AlreadyExistsError,
    InvalidPrivateKeyError,
    InvalidPublicKeyError,
    WrongPassphraseError,
)
from crypteasy.keystore.identities import Protection

from .conftest import OTHER_PW, PW, needs_kdf

pytestmark = pytest.mark.usefixtures("fake_kdf")

NONE = Protection(None, level="none")
STRONG = Protection(PW, "argon2id", "normal", 16, "strong")
MEDIUM = Protection(PW, "pbkdf2-sha256", "normal", 16, "medium")


def _pkcs8(key, password: bytes | None = None) -> bytes:
    enc = (
        serialization.BestAvailableEncryption(password)
        if password
        else serialization.NoEncryption()
    )
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, enc)


# ----------------------------------------------------------------- create / unlock


@pytest.mark.parametrize("key_type", ids.KEY_TYPES)
def test_create_every_key_type(key_type):
    ident = ids.create_identity("Alice", key_type, NONE)
    assert ident.key_type == key_type
    pem = ids.public_pem(ident.fingerprint)
    enc_pub, sig_pub = keys.load_public_keys(pem)
    assert isinstance(sig_pub, ed25519.Ed25519PublicKey)  # signing key from day 1
    assert ident.fingerprint == keys.get_fingerprint(enc_pub)  # fingerprint = encryption key
    enc, sig = keys.load_private_keys(ids.unlock(ident.fingerprint, None))
    assert keys.get_fingerprint(enc.public_key()) == ident.fingerprint
    assert sig.public_key() == sig_pub


@pytest.mark.parametrize("protection", [STRONG, MEDIUM])
def test_protected_roundtrip_and_wrong_passphrase(protection):
    ident = ids.create_identity("Alice", "x25519", protection)
    enc, _sig = keys.load_private_keys(ids.unlock(ident.fingerprint, PW))
    assert keys.get_fingerprint(enc.public_key()) == ident.fingerprint
    with pytest.raises(WrongPassphraseError):
        ids.unlock(ident.fingerprint, OTHER_PW)


def test_secret_never_written_in_clear_when_protected():
    ident = ids.create_identity("Alice", "x25519", STRONG)
    secret = ids.unlock(ident.fingerprint, PW)
    for f in paths.keys_dir().rglob("*"):
        if f.is_file():
            assert b"PRIVATE KEY" not in f.read_bytes()
    assert b"PRIVATE KEY" in secret


@needs_kdf
def test_real_kdf_every_level():
    """With core/kdf.py: every level of section 4.2 round-trips with the real KDF presets,
    and the presets pass identities._check_params."""
    raise NotImplementedError


# ----------------------------------------------------------------- contacts


def test_contact_from_crypteasy_public_pem():
    alice = ids.create_identity("Alice", "rsa-2048", NONE)
    contact = contacts.add_contact("Alice", ids.public_pem(alice.fingerprint))
    assert (contact.key_type, contact.fingerprint) == ("rsa-2048", alice.fingerprint)
    assert contacts.list_contacts() == [contact]  # reload re-parses with core/


def test_contact_from_single_openssl_key():
    pub = x25519.X25519PrivateKey.generate().public_key()
    contact = contacts.add_contact("Bob", keys.public_keys_to_pem(pub))
    assert contact.fingerprint == keys.get_fingerprint(pub)


@pytest.mark.parametrize(
    "make_pem",
    [
        lambda: _pkcs8(x25519.X25519PrivateKey.generate()),  # a private key, not public
        lambda: keys.public_keys_to_pem(ed25519.Ed25519PrivateKey.generate().public_key()),
        lambda: keys.public_keys_to_pem(x25519.X25519PrivateKey.generate().public_key())[:60],
        lambda: b"-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PUBLIC KEY-----\n",
    ],
)
def test_invalid_contact_keys(make_pem):
    with pytest.raises(InvalidPublicKeyError):
        contacts.add_contact("Eve", make_pem())


# ----------------------------------------------------------------- import (F2)


def test_import_openssl_pem_gets_a_signing_key(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (tmp_path / "k.pem").write_bytes(_pkcs8(key))
    ident = ids.import_private_key("Imported", tmp_path / "k.pem", None, STRONG)
    assert ident.key_type == "rsa-2048"
    assert ident.fingerprint == keys.get_fingerprint(key.public_key())
    enc, sig = keys.load_private_keys(ids.unlock(ident.fingerprint, PW))
    assert isinstance(sig, ed25519.Ed25519PrivateKey)
    assert enc.private_numbers() == key.private_numbers()


def test_import_encrypted_openssl_pem(tmp_path):
    key = x25519.X25519PrivateKey.generate()
    (tmp_path / "k.pem").write_bytes(_pkcs8(key, b"openssl pw"))
    with pytest.raises(WrongPassphraseError):
        ids.import_private_key("Imported", tmp_path / "k.pem", b"wrong", NONE)
    ident = ids.import_private_key("Imported", tmp_path / "k.pem", b"openssl pw", NONE)
    assert ident.fingerprint == keys.get_fingerprint(key.public_key())


@pytest.mark.parametrize("protection", [NONE, MEDIUM])
def test_export_then_import_crypteasy_private_key(tmp_path, monkeypatch, protection):
    alice = ids.create_identity("Alice", "x25519", protection)
    ids.export_private_key(alice.fingerprint, tmp_path / "alice.key")
    original_public = ids.public_pem(alice.fingerprint)
    # move to "another PC": a fresh data folder
    monkeypatch.setenv("CRYPTEASY_HOME", str(tmp_path / "other-pc"))
    ident = ids.import_private_key("Alice", tmp_path / "alice.key", protection.passphrase, STRONG)
    assert ident.fingerprint == alice.fingerprint
    assert ids.public_pem(ident.fingerprint) == original_public  # same signing key too
    assert ident.level == "strong"


def test_import_same_key_twice_rejected(tmp_path):
    alice = ids.create_identity("Alice", "x25519", NONE)
    ids.export_private_key(alice.fingerprint, tmp_path / "alice.key")
    with pytest.raises(AlreadyExistsError):
        ids.import_private_key("Alice 2", tmp_path / "alice.key", None, NONE)


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"garbage",
        b"{}",
        b"x" * 70_000,
        keys.public_keys_to_pem(x25519.X25519PrivateKey.generate().public_key()),
    ],
)
def test_import_garbage_rejected_and_nothing_saved(tmp_path, content):
    (tmp_path / "k.pem").write_bytes(content)
    with pytest.raises(InvalidPrivateKeyError):
        ids.import_private_key("X", tmp_path / "k.pem", None, NONE)
    assert list(paths.keys_dir().iterdir()) == []


def test_import_crafted_encrypted_header_rejected(tmp_path):
    """An unencrypted key with the word ENCRYPTED in a PEM header makes core/keys.py pass a
    password to cryptography, which raises TypeError. keystore turns it into
    InvalidPrivateKeyError instead of crashing the request."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    begin = b"-----BEGIN RSA PRIVATE KEY-----\n"
    (tmp_path / "k.pem").write_bytes(pem.replace(begin, begin + b"X-Note: ENCRYPTED\n\n"))
    with pytest.raises(InvalidPrivateKeyError):
        ids.import_private_key("X", tmp_path / "k.pem", b"pw", NONE)


def test_imported_unprotected_file_is_relocked(tmp_path):
    key = x25519.X25519PrivateKey.generate()
    (tmp_path / "k.pem").write_bytes(_pkcs8(key))
    ident = ids.import_private_key("X", tmp_path / "k.pem", None, MEDIUM)
    (folder,) = paths.keys_dir().iterdir()
    assert json.loads((folder / "private.key").read_bytes())["kdf"] == "pbkdf2-sha256"
    assert ident.protected
