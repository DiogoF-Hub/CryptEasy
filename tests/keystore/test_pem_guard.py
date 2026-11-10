"""keystore/pem_guard.py: hostile encrypted PEM files are refused before any KDF runs."""

import base64
import os
import shutil
import subprocess

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, x25519

from crypteasy.core import keys
from crypteasy.keystore import _core, pem_guard
from crypteasy.keystore.errors import InvalidPrivateKeyError

PBES2 = "1.2.840.113549.1.5.13"
PBKDF2 = "1.2.840.113549.1.5.12"
SCRYPT = "1.3.6.1.4.1.11591.4.11"
HMAC_SHA256 = "1.2.840.113549.2.9"
AES256_CBC = "2.16.840.1.101.3.4.1.42"
PKCS12_3DES = "1.2.840.113549.1.12.1.3"  # PBES1-style, refused
HMAC_SHA1 = "1.2.840.113549.2.7"
HMAC_SHA512 = "1.2.840.113549.2.11"
DES_EDE3_CBC = "1.2.840.113549.3.7"


# --------------------------------------------------------------- tiny DER builder (tests only)


def _len(n: int) -> bytes:
    if n < 128:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def _tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + _len(len(value)) + value


def _seq(*items: bytes) -> bytes:
    return _tlv(0x30, b"".join(items))


def _int(i: int) -> bytes:
    return _tlv(0x02, i.to_bytes((i.bit_length() + 8) // 8 or 1, "big", signed=True))


def _oid(dotted: str) -> bytes:
    parts = [int(p) for p in dotted.split(".")]
    out = bytes([40 * parts[0] + parts[1]])
    for p in parts[2:]:
        enc = [p & 0x7F]
        p >>= 7
        while p:
            enc.insert(0, 0x80 | (p & 0x7F))
            p >>= 7
        out += bytes(enc)
    return _tlv(0x06, out)


def _octet(b: bytes) -> bytes:
    return _tlv(0x04, b)


def _pem(der: bytes) -> bytes:
    body = base64.encodebytes(der)
    return (
        b"-----BEGIN ENCRYPTED PRIVATE KEY-----\n" + body + b"-----END ENCRYPTED PRIVATE KEY-----\n"
    )


def _encrypted(kdf: bytes, scheme: str = PBES2, cipher_oid: str = AES256_CBC) -> bytes:
    """An EncryptedPrivateKeyInfo with the given KDF. The ciphertext is random: the guard
    must decide from the header alone, without decrypting anything."""
    cipher = _seq(_oid(cipher_oid), _octet(os.urandom(16)))
    algorithm = _seq(_oid(scheme), _seq(kdf, cipher))
    return _pem(_seq(algorithm, _octet(os.urandom(64))))


def pbkdf2(iterations: int, prf: str | None = HMAC_SHA256, key_length: int | None = None,
           cipher_oid: str = AES256_CBC) -> bytes:  # fmt: skip
    fields = _octet(os.urandom(16)) + _int(iterations)
    if key_length is not None:
        fields += _int(key_length)
    if prf is not None:
        fields += _seq(_oid(prf), b"\x05\x00")
    return _encrypted(_seq(_oid(PBKDF2), _seq(fields)), cipher_oid=cipher_oid)


def legacy(dek_info: bytes, label: bytes = b"RSA PRIVATE KEY") -> bytes:
    body = base64.encodebytes(os.urandom(64))
    headers = b"Proc-Type: 4,ENCRYPTED\nDEK-Info: " + dek_info + b"\n\n"
    return b"-----BEGIN " + label + b"-----\n" + headers + body + b"-----END " + label + b"-----\n"


def scrypt(n: int, r: int, p: int) -> bytes:
    params = _seq(_octet(os.urandom(16)), _int(n), _int(r), _int(p), _int(32))
    return _encrypted(_seq(_oid(SCRYPT), params))


# --------------------------------------------------------------- tests


@pytest.fixture
def library_must_not_run(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("the file reached the library before being checked")

    monkeypatch.setattr(keys, "load_private_keys", fail)


@pytest.mark.parametrize(
    "pem",
    [
        pbkdf2(2048),  # OpenSSL default
        pbkdf2(10_000_000),
        pbkdf2(2048, key_length=32),
        scrypt(16384, 8, 1),  # openssl pkcs8 -scrypt
        scrypt(2**17, 8, 1),  # 128 MiB
        legacy(b"AES-256-CBC," + b"AB" * 16),
        legacy(b"DES-EDE3-CBC," + b"AB" * 8),
    ],
)
def test_reasonable_settings_pass(pem):
    pem_guard.check_private_pem(pem)


@pytest.mark.parametrize(
    "pem",
    [
        pbkdf2(10_000_001),
        pbkdf2(2**31),  # made cryptography 50 panic (BaseException)
        pbkdf2(2**40),
        pbkdf2(2**64 - 1),
        pbkdf2(0),
        pbkdf2(-1),
        pbkdf2(10_000_000, prf=None),  # SHA-1 default: twice the work for AES-256
        pbkdf2(10_000_000, prf=HMAC_SHA512),  # ~4x the work
        pbkdf2(2048, prf=HMAC_SHA1),
        pbkdf2(2048, cipher_oid=DES_EDE3_CBC),
        scrypt(2**20, 8, 1),  # 1 GiB, ~7 s
        scrypt(2**22, 8, 1),  # 4 GiB
        scrypt(2**20, 1024, 1),  # 128 GiB: OpenSSL malloc failure (InternalError)
        scrypt(2**20, 8, 4),  # p multiplies the time
        scrypt(2, 4_194_304, 3),  # N=2, huge r: 5 GiB, 53 s
        scrypt(1024, 64, 1),
        scrypt(1000, 8, 1),  # N not a power of two
        scrypt(1024, 8, 100_000),  # huge p
        scrypt(1, 8, 1),
        legacy(b"AES-128-CBC," + b"00" * 8),  # 8-byte IV: made cryptography 50 panic
        legacy(b"AES-256-CBC," + b"00" * 15),
        legacy(b"AES-256-CBC," + b"00" * 16, label=b"PRIVATE KEY"),
        legacy(b"DES-CBC," + b"00" * 8),
        legacy(b"AES-256-CBC,00").replace(b"Proc-Type: 4,", b"Proc-Type:4,"),
        pbkdf2(2048) + pbkdf2(2048),  # two encrypted blocks: costs add up
        _encrypted(_seq(_oid(PBKDF2), _seq(_octet(b"salt"))), scheme=PKCS12_3DES),
        _encrypted(_seq(_oid(AES256_CBC), _seq(_octet(b"salt"), _int(1)))),  # unknown KDF
        _encrypted(_seq(_oid(PBKDF2), _seq(_octet(b"salt")))),  # no iteration count
    ],
)
def test_hostile_settings_refused_before_library(pem, library_must_not_run):
    with pytest.raises(InvalidPrivateKeyError):
        _core.load_private_pem(pem, b"any passphrase")


@pytest.mark.parametrize(
    "pem",
    [
        _pem(b"\x30\x84\xff\xff\xff\xff"),  # length larger than the data
        _pem(b"\x30\x00trailing"),
        _pem(b"\x30\x89" + b"\x01" * 9),  # 9-byte length
        b"-----BEGIN ENCRYPTED PRIVATE KEY-----\n!!!\n-----END ENCRYPTED PRIVATE KEY-----\n",
        b"-----BEGIN ENCRYPTED PRIVATE KEY-----\n\n-----END ENCRYPTED PRIVATE KEY-----\n",
    ],
)
def test_malformed_der_refused(pem, library_must_not_run):
    with pytest.raises(InvalidPrivateKeyError):
        _core.load_private_pem(pem, b"pw")


def test_size_caps(library_must_not_run):
    with pytest.raises(InvalidPrivateKeyError):
        _core.load_private_pem(b"x" * (pem_guard.MAX_PEM_BYTES + 1), None)
    big_block = b"-----BEGIN PRIVATE KEY-----\n" + b"A" * 5000 + b"\n-----END PRIVATE KEY-----\n"
    with pytest.raises(InvalidPrivateKeyError):
        _core.load_private_pem(big_block, None)


def test_largest_real_key_fits():
    """An encrypted RSA-4096 PKCS#8 (~3.4 KiB) is the largest block a user can bring."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(b"pw"),
    )
    secret, _public, key_type, _fpr = _core.load_private_pem(pem, b"pw")
    assert key_type == "rsa-4096"
    pem_guard.check_private_pem(secret)  # our own two-key secret fits too


@pytest.mark.skipif(shutil.which("openssl") is None, reason="needs the openssl command")
@pytest.mark.parametrize("args", [["-v2", "aes-256-cbc"], ["-scrypt"]])
def test_openssl_encrypted_keys_import(tmp_path, args):
    key = x25519.X25519PrivateKey.generate()
    plain = tmp_path / "k.pem"
    plain.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    out = tmp_path / "enc.pem"
    cmd = ["openssl", "pkcs8", "-topk8", *args, "-in", plain, "-passout", "pass:pw", "-out", out]
    subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603 - fixed args, test only
    _secret, _public, key_type, fingerprint = _core.load_private_pem(out.read_bytes(), b"pw")
    assert (key_type, fingerprint) == ("x25519", keys.get_fingerprint(key.public_key()))


def test_real_legacy_encrypted_rsa_imports():
    """`openssl rsa -aes256 -traditional` style (Proc-Type / DEK-Info) still imports."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.BestAvailableEncryption(b"pw"),
    )
    assert b"DEK-Info" in pem
    _secret, _public, key_type, _fpr = _core.load_private_pem(pem, b"pw")
    assert key_type == "rsa-2048"
