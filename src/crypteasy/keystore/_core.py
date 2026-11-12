"""The only place where keystore/ calls the crypto engine (crypteasy.core).

Keys come from core/keys.py (#6), the KDF from core/kdf.py (#7). Most tests replace the
KDF pair with fast fakes (tests/keystore/conftest.py); test_real_core.py runs the real one.

Callers use `_core.<name>(...)`, never `from ._core import <name>`, so the fakes apply.

The fingerprint of a key pair is the fingerprint of its ENCRYPTION public key (the one
a package is encrypted for), not of the Ed25519 signing key.
"""

from __future__ import annotations

from cryptography.exceptions import InternalError
from cryptography.hazmat.primitives.asymmetric import ed25519

from crypteasy.core import kdf as core_kdf
from crypteasy.core import keys

from . import pem_guard
from .errors import InvalidPrivateKeyError, InvalidSettingError


def inspect_public_pem(pem: bytes) -> tuple[str, str]:
    """Parse a public.pem (encryption key, optionally followed by the Ed25519 key).

    Returns (key_type, fingerprint). Raises InvalidPublicKeyError (core's InvalidKeyError).
    """
    encryption_key, _signing_key = keys.load_public_keys(pem)
    return keys.get_key_type(encryption_key), keys.get_fingerprint(encryption_key)


def _identity_from(encryption_key, signing_key) -> tuple[bytes, bytes, str, str]:
    """(secret, public_pem, key_type, fingerprint) for a pair of private keys."""
    public = encryption_key.public_key()
    secret = keys.private_keys_to_pem(encryption_key, signing_key)
    public_pem = keys.public_keys_to_pem(public, signing_key.public_key())
    return secret, public_pem, keys.get_key_type(encryption_key), keys.get_fingerprint(public)


def generate(key_type: str) -> tuple[bytes, bytes, str]:
    """New key pair. Returns (secret, public_pem, fingerprint); `secret` is both private
    keys as unencrypted PKCS#8 PEM, which keystore locks before writing it anywhere."""
    secret, public_pem, _key_type, fingerprint = _identity_from(*keys.generate_keypair(key_type))
    return secret, public_pem, fingerprint


def load_private_pem(pem: bytes, password: bytes | None) -> tuple[bytes, bytes, str, str]:
    """Private keys from a PEM file: an unlocked CryptEasy secret, or a key made elsewhere
    (e.g. OpenSSL), encrypted or not. A key made elsewhere has no Ed25519 signing key, so
    one is generated (spec F9: every key pair has one from day 1).

    Returns (secret, public_pem, key_type, fingerprint).
    Raises InvalidPrivateKeyError, WrongPassphraseError.
    """
    pem_guard.check_private_pem(pem)  # size and KDF cost, before the library runs any KDF
    try:
        encryption_key, signing_key = keys.load_private_keys(pem, password)
    except TypeError as exc:
        # cryptography raises TypeError when a password is given for a block that isn't
        # encrypted, or none for one that is. core/keys.py decides that by looking for the
        # word ENCRYPTED in the block, which a crafted header line can fake.
        raise InvalidPrivateKeyError("encrypted and unencrypted blocks mixed up") from exc
    except InternalError as exc:  # e.g. OpenSSL running out of memory in a KDF
        raise InvalidPrivateKeyError("the key could not be decrypted") from exc
    if signing_key is None:
        signing_key = ed25519.Ed25519PrivateKey.generate()
    return _identity_from(encryption_key, signing_key)


def kdf_params(kdf: str, strength: str) -> dict:
    """Preset parameters for a KDF ("argon2id" / "pbkdf2-sha256") and a strength
    ("normal" / "strong" / "max"), in the private.key "params" format (spec section 6.2).
    Raises InvalidSettingError for an unknown KDF or strength."""
    try:
        return core_kdf.get_kdf_params(kdf, strength)
    except ValueError as exc:
        raise InvalidSettingError() from exc


def derive_lock_key(kdf: str, passphrase: bytes, salt: bytes, params: dict) -> bytes:
    """Turn the key passphrase into the 32-byte AES-256-GCM key that locks private.key.

    keystore has already checked the settings against its own bounds; core checks them
    again. A refusal there means the file is unusable: InvalidPrivateKeyError."""
    try:
        return core_kdf.derive_key(passphrase, kdf, salt, params)
    except ValueError as exc:
        raise InvalidPrivateKeyError("KDF settings refused by core") from exc
