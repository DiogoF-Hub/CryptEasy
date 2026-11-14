"""keystore/ with no fakes at all: real keys (core/keys.py) and the real KDF (core/kdf.py).

Every security level of spec section 4.2, as the UI sends it. The "max" presets (1 GiB of
Argon2 memory) are @slow: `make test-slow`, not CI.
"""

import json

import pytest

from crypteasy.core import kdf as core_kdf
from crypteasy.core import keys
from crypteasy.keystore import identities as ids
from crypteasy.keystore import paths
from crypteasy.keystore.errors import WrongPassphraseError
from crypteasy.keystore.identities import Protection

from .conftest import OTHER_PW, PW

LEVELS = [
    pytest.param(Protection(PW, "argon2id", "max", 32, "very_strong"), marks=pytest.mark.slow),
    Protection(PW, "argon2id", "normal", 16, "strong"),
    Protection(PW, "pbkdf2-sha256", "normal", 16, "medium"),
    Protection(PW, "pbkdf2-sha256", "normal", 0, "weak"),
    Protection(None, level="none"),
]


@pytest.mark.parametrize("protection", LEVELS)
def test_every_level_roundtrip(protection):
    ident = ids.create_identity("Alice", "x25519", protection)
    enc, _sig = keys.load_private_keys(ids.unlock(ident.fingerprint, protection.passphrase))
    assert keys.get_fingerprint(enc.public_key()) == ident.fingerprint
    if protection.passphrase is not None:
        with pytest.raises(WrongPassphraseError):
            ids.unlock(ident.fingerprint, OTHER_PW)


def test_stored_params_are_core_presets():
    ident = ids.create_identity("Alice", "x25519", Protection(PW, "pbkdf2-sha256", "strong"))
    (folder,) = paths.keys_dir().iterdir()
    doc = json.loads((folder / "private.key").read_bytes())
    assert doc["params"] == core_kdf.get_kdf_params("pbkdf2-sha256", "strong")
    assert ident.fingerprint


@pytest.mark.parametrize("kdf", ["argon2id", "pbkdf2-sha256"])
@pytest.mark.parametrize("strength", ["normal", "strong", "max"])
@pytest.mark.parametrize("salt_len", [16, 32])
def test_every_core_preset_passes_keystore_bounds(kdf, strength, salt_len):
    """A key locked with any core/kdf.py preset must load again (keystore bounds are
    checked before the KDF runs)."""
    ids._check_params(kdf, salt_len, core_kdf.get_kdf_params(kdf, strength))


def test_change_protection_with_real_kdf():
    ident = ids.create_identity("Alice", "x25519", Protection(None, level="none"))
    secret = ids.unlock(ident.fingerprint, None)
    ids.change_protection(ident.fingerprint, None, Protection(PW, "argon2id", "normal", 16))
    assert ids.unlock(ident.fingerprint, PW) == secret
