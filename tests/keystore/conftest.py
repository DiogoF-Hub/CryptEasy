"""Shared fixtures for the keystore tests (Track C).

Every test runs against a temp data folder (`CRYPTEASY_HOME`), never the real one.
`fake_core` replaces all of keystore/_core.py with fast deterministic stand-ins, to test
the storage logic. `fake_kdf` replaces only the KDF (core/kdf.py, #7, not written yet),
so tests using it run the real core/keys.py. The fakes are NOT cryptography.
"""

import hashlib
import json
import os
import re

import pytest

from crypteasy.keystore import _core
from crypteasy.keystore.errors import InvalidPublicKeyError, InvalidSettingError

PW = b"a long enough key passphrase"
OTHER_PW = b"another long key passphrase"

_PEM_RE = re.compile(
    rb"-----BEGIN FAKE PUBLIC KEY-----\n(x25519|rsa-2048|rsa-3072|rsa-4096):([0-9a-f]{32})\n"
    rb"-----END FAKE PUBLIC KEY-----\n"
)
FAKE_PARAMS = {
    "argon2id": {"memory_kib": 65536, "iterations": 3, "parallelism": 4},
    "pbkdf2-sha256": {"iterations": 600_000},
}


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    path = tmp_path / "home"
    monkeypatch.setenv("CRYPTEASY_HOME", str(path))
    return path


def fake_pem(key_type: str = "x25519", key_id: bytes | None = None) -> bytes:
    key_id = key_id or os.urandom(16)
    return (
        b"-----BEGIN FAKE PUBLIC KEY-----\n"
        + key_type.encode()
        + b":"
        + key_id.hex().encode()
        + b"\n-----END FAKE PUBLIC KEY-----\n"
    )


def fake_fingerprint(pem: bytes) -> str:
    h = hashlib.sha256(pem).hexdigest().upper()
    return " ".join(h[i : i + 4] for i in range(0, 64, 4))


def _inspect_public_pem(pem: bytes) -> tuple[str, str]:
    m = _PEM_RE.fullmatch(pem)
    if not m:
        raise InvalidPublicKeyError()
    return m.group(1).decode(), fake_fingerprint(pem)


def _generate(key_type: str) -> tuple[bytes, bytes, str]:
    pem = fake_pem(key_type)
    return b"SECRET:" + os.urandom(32), pem, fake_fingerprint(pem)


def _kdf_params(kdf: str, strength: str) -> dict:
    if strength not in ("normal", "strong", "max"):
        raise InvalidSettingError()
    return dict(FAKE_PARAMS[kdf])


def _derive_lock_key(kdf: str, passphrase: bytes, salt: bytes, params: dict) -> bytes:
    material = kdf.encode() + salt + json.dumps(params, sort_keys=True).encode() + passphrase
    return hashlib.sha256(material).digest()


@pytest.fixture
def fake_kdf(monkeypatch):
    monkeypatch.setattr(_core, "kdf_params", _kdf_params)
    monkeypatch.setattr(_core, "derive_lock_key", _derive_lock_key)


@pytest.fixture
def fake_core(monkeypatch, fake_kdf):
    monkeypatch.setattr(_core, "inspect_public_pem", _inspect_public_pem)
    monkeypatch.setattr(_core, "generate", _generate)


needs_kdf = pytest.mark.skip(reason="needs core/kdf.py (#7)")
