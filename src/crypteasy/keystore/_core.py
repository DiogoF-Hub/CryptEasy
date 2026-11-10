"""The only place where keystore/ calls the crypto engine (crypteasy.core).

These four functions wait for core/keys.py (#6) and core/kdf.py (#7). The signatures
below are a PROPOSAL to confirm with Track A; once core/ lands, each body becomes a
call into core/ (and core's exceptions are turned into the keystore ones listed here).
Tests replace them with fakes (tests/keystore/conftest.py, `fake_core`).

Callers use `_core.<name>(...)`, never `from ._core import <name>`, so the fakes apply.
"""

from __future__ import annotations

_PENDING_KEYS = "needs core/keys.py (#6)"
_PENDING_KDF = "needs core/kdf.py (#7)"


def inspect_public_pem(pem: bytes) -> tuple[str, str]:
    """Parse a CryptEasy public.pem (encryption key + Ed25519 signing key).

    Returns (key_type, fingerprint), e.g. ("x25519", "AB12 CD34 ...").
    Raises InvalidPublicKeyError if it isn't a valid CryptEasy public key.
    """
    raise NotImplementedError(_PENDING_KEYS)


def generate(key_type: str) -> tuple[bytes, bytes, str]:
    """Generate a key pair of `key_type` ("x25519", "rsa-2048", ...) plus its Ed25519 key.

    Returns (secret, public_pem, fingerprint). `secret` is the private keys as opaque
    bytes (how the two PKCS#8 DER keys are packed is up to core/); keystore only locks it.
    """
    raise NotImplementedError(_PENDING_KEYS)


def kdf_params(kdf: str, strength: str) -> dict:
    """Preset parameters for a KDF ("argon2id" / "pbkdf2-sha256") and a strength.

    argon2id → {"memory_kib": int, "iterations": int, "parallelism": int}
    pbkdf2-sha256 → {"iterations": int}
    Raises InvalidSettingError for an unknown strength.
    """
    raise NotImplementedError(_PENDING_KDF)


def derive_lock_key(kdf: str, passphrase: bytes, salt: bytes, params: dict) -> bytes:
    """Turn the key passphrase into the 32-byte AES-256-GCM key that locks private.key."""
    raise NotImplementedError(_PENDING_KDF)
