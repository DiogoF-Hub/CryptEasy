"""Refuse hostile private key PEM files BEFORE they reach the cryptography library.

An encrypted key file declares its own KDF and cipher settings, and the library runs the
KDF before it can tell the passphrase is wrong. A 300-byte file can ask for minutes of
CPU or gigabytes of memory (CWE-400, CWE-770), and some values make cryptography 50
panic with an exception that isn't an Exception: 2**31 PBKDF2 iterations or more, or a
legacy DEK-Info IV of 8 to 15 bytes. Spec section 6.2: "refuse silly params so a crafted
key file can't freeze the app".

So the settings are read here first, with a minimal DER reader (only lengths, tags and
integers, no crypto), and only what cryptography and OpenSSL 3 actually write is let
through. Everything else is refused: this only ever rejects files, it never makes the
library accept one it wouldn't.

Accepted (at most ONE encrypted block per file; a key made elsewhere has one, and
CryptEasy's own secret is never encrypted this way):
- PKCS#8 "ENCRYPTED PRIVATE KEY": PBES2 with
    - PBKDF2, prf hmacWithSHA256, iterations <= PBKDF2_MAX_ITERATIONS
      (cryptography's BestAvailableEncryption, `openssl pkcs8 -topk8 -v2 aes-256-cbc`,
      `openssl genpkey -aes-256-cbc`), or
    - scrypt with p = 1, r <= 32, N a power of two, memory <= SCRYPT_MAX_MEMORY
      (`openssl pkcs8 -topk8 -scrypt` writes N = 16384, r = 8, p = 1)
  and AES-128/192/256-CBC.
- legacy "RSA PRIVATE KEY" with exactly `Proc-Type: 4,ENCRYPTED` and a DEK-Info of
  AES-128/192/256-CBC (16-byte IV) or DES-EDE3-CBC (8-byte IV). Its KDF is one MD5 round.
Refused: PBES1 / PKCS#12 PBE, PBKDF2 with SHA-1 (the default when no prf is written) or
any other hash, other ciphers, any other PEM header.

Size caps also bound the library's RSA key validation and core/keys.py's PEM regex:
the largest real block is an encrypted RSA-4096 key, about 3.4 KiB.
"""

from __future__ import annotations

import base64
import re

from crypteasy.core import keys

from .common import PBKDF2_MAX_ITERATIONS, SCRYPT_MAX_BLOCK_SIZE, SCRYPT_MAX_MEMORY
from .errors import InvalidPrivateKeyError

MAX_PEM_BYTES = 8 * 1024  # a whole file: up to 2 keys
MAX_BLOCK_BYTES = 4 * 1024  # one PEM block

_SEQUENCE, _INTEGER, _OCTET_STRING, _OID = 0x30, 0x02, 0x04, 0x06
# OIDs as their DER content bytes
_PBES2 = bytes.fromhex("2a864886f70d01050d")  # 1.2.840.113549.1.5.13
_PBKDF2 = bytes.fromhex("2a864886f70d01050c")  # 1.2.840.113549.1.5.12
_SCRYPT = bytes.fromhex("2b06010401da47040b")  # 1.3.6.1.4.1.11591.4.11
_HMAC_SHA256 = bytes.fromhex("2a864886f70d0209")  # 1.2.840.113549.2.9
_AES_CBC = {
    bytes.fromhex("608648016503040102"),  # 2.16.840.1.101.3.4.1.2  aes128-CBC
    bytes.fromhex("608648016503040116"),  # 2.16.840.1.101.3.4.1.22 aes192-CBC
    bytes.fromhex("60864801650304012a"),  # 2.16.840.1.101.3.4.1.42 aes256-CBC
}
_LEGACY_HEADERS = re.compile(
    rb"Proc-Type: 4,ENCRYPTED\r?\n"
    rb"DEK-Info: (?:(?:AES-128-CBC|AES-192-CBC|AES-256-CBC),[0-9A-Fa-f]{32}"
    rb"|DES-EDE3-CBC,[0-9A-Fa-f]{16})\r?\n\r?\n"
)


def check_private_pem(pem: bytes) -> None:
    """Raise InvalidPrivateKeyError if the file is too large, or if it has an encrypted
    block outside the accepted settings (module docstring), or more than one."""
    if len(pem) > MAX_PEM_BYTES:
        raise InvalidPrivateKeyError("key file too large")
    encrypted_blocks = 0
    for label, block in zip(*keys.split_pem_blocks(pem), strict=True):
        if len(block) > MAX_BLOCK_BYTES:
            raise InvalidPrivateKeyError("key too large")
        body = block.split(b"-----")[2]
        try:
            if b":" in body:  # PEM headers (base64 never contains ":")
                if label != b"RSA PRIVATE KEY" or not _LEGACY_HEADERS.match(body.lstrip()):
                    raise ValueError("unsupported PEM headers")
                encrypted_blocks += 1
            elif label == b"ENCRYPTED PRIVATE KEY":
                _check_encrypted_pkcs8(base64.b64decode(b"".join(body.split()), validate=True))
                encrypted_blocks += 1
        except (ValueError, IndexError) as exc:  # malformed DER or base64, missing fields
            raise InvalidPrivateKeyError("unsupported or unsafe key encryption") from exc
    if encrypted_blocks > 1:
        raise InvalidPrivateKeyError("more than one encrypted key in the file")


def _tlv(data: bytes, pos: int, end: int) -> tuple[int, int, int]:
    """(tag, value start, value end) of the DER element at `pos`. ValueError if malformed."""
    if pos + 2 > end:
        raise ValueError("truncated")
    tag, length = data[pos], data[pos + 1]
    pos += 2
    if length & 0x80:
        n = length & 0x7F
        if not 1 <= n <= 4 or pos + n > end:
            raise ValueError("bad length")
        length = int.from_bytes(data[pos : pos + n], "big")
        pos += n
    if pos + length > end:
        raise ValueError("truncated")
    return tag, pos, pos + length


def _children(data: bytes, element: tuple[int, int, int]) -> list:
    """The elements inside a SEQUENCE (at most 8 of them)."""
    if element[0] != _SEQUENCE:
        raise ValueError("expected a SEQUENCE")
    items, pos, end = [], element[1], element[2]
    while pos < end:
        if len(items) == 8:
            raise ValueError("too many elements")
        items.append(_tlv(data, pos, end))
        pos = items[-1][2]
    return items


def _oid(data: bytes, element: tuple[int, int, int]) -> bytes:
    if element[0] != _OID:
        raise ValueError("expected an OID")
    return data[element[1] : element[2]]


def _int(data: bytes, element: tuple[int, int, int]) -> int:
    tag, start, end = element
    if tag != _INTEGER or not 1 <= end - start <= 8:
        raise ValueError("expected a small INTEGER")
    return int.from_bytes(data[start:end], "big", signed=True)


def _check_encrypted_pkcs8(der: bytes) -> None:
    # EncryptedPrivateKeyInfo ::= SEQUENCE { AlgorithmIdentifier, OCTET STRING }
    top = _tlv(der, 0, len(der))
    if top[2] != len(der):
        raise ValueError("trailing data")
    algorithm, encrypted = _children(der, top)
    if encrypted[0] != _OCTET_STRING:
        raise ValueError("expected the encrypted key")
    scheme, pbes2_params = _children(der, algorithm)
    if _oid(der, scheme) != _PBES2:
        raise ValueError("only PBES2 is accepted")
    # PBES2-params ::= SEQUENCE { keyDerivationFunc, encryptionScheme }
    kdf, cipher = _children(der, pbes2_params)
    if _oid(der, _children(der, cipher)[0]) not in _AES_CBC:
        raise ValueError("only AES-CBC is accepted")
    kdf_oid, kdf_params = _children(der, kdf)
    fields = _children(der, kdf_params)
    if fields[0][0] != _OCTET_STRING:  # salt
        raise ValueError("expected a salt")
    if _oid(der, kdf_oid) == _PBKDF2:
        _check_pbkdf2(der, fields)
    elif _oid(der, kdf_oid) == _SCRYPT:
        _check_scrypt(der, fields)
    else:
        raise ValueError("only PBKDF2 and scrypt are accepted")


def _check_pbkdf2(der: bytes, fields: list) -> None:
    # PBKDF2-params ::= SEQUENCE { salt, iterationCount, keyLength INTEGER OPTIONAL,
    #                              prf AlgorithmIdentifier DEFAULT hmacWithSHA1 }
    if not 1 <= _int(der, fields[1]) <= PBKDF2_MAX_ITERATIONS:
        raise ValueError("PBKDF2 iterations out of bounds")
    rest = fields[2:]
    if rest and rest[0][0] == _INTEGER:  # keyLength: cryptography ignores it
        rest = rest[1:]
    # The prf must be written and be HMAC-SHA256: SHA-1 (the default) runs twice for an
    # AES-256 key, SHA-384/512 are ~4x slower on most CPUs, so the iteration bound
    # wouldn't hold.
    if len(rest) != 1 or _oid(der, _children(der, rest[0])[0]) != _HMAC_SHA256:
        raise ValueError("only PBKDF2 with HMAC-SHA256 is accepted")


def _check_scrypt(der: bytes, fields: list) -> None:
    # scrypt-params ::= SEQUENCE { salt, costParameter N, blockSize r,
    #                              parallelizationParameter p, keyLength OPTIONAL }
    n, r, p = (_int(der, f) for f in fields[1:4])
    if p != 1 or not 1 <= r <= SCRYPT_MAX_BLOCK_SIZE:
        raise ValueError("scrypt r or p out of bounds")
    if n < 2 or n & (n - 1):
        raise ValueError("scrypt N must be a power of two")
    # OpenSSL allocates 128 * r * (N + 2) for V plus 128 * r * p for B
    if 128 * r * (n + 2) + 128 * r * p > SCRYPT_MAX_MEMORY:
        raise ValueError("scrypt memory out of bounds")
