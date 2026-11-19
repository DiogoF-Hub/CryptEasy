import base64
import os
import shutil
import subprocess

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa, x25519

from crypteasy.core import keys, pem_guard
from crypteasy.core.errors import InvalidKeyError, InvalidPrivateKeyError

"""
In this file I test core/pem_guard.py: crafted key files must be refused before the
cryptography library opens them (#55). The first version of these tests was Sam's, for
keystore/ (#50), I moved them here with the guard
Run only these tests with: make test-core
"""

# The OIDs (algorithm IDs) used to build the test files, as the bytes inside the DER element
# The ones also in pem_guard.py are written again here on purpose, so a mistake in
# pem_guard.py doesn't hide itself in the tests
pbes2 = "2a864886f70d01050d"  # 1.2.840.113549.1.5.13
pbkdf2 = "2a864886f70d01050c"  # 1.2.840.113549.1.5.12
scrypt = "2b06010401da47040b"  # 1.3.6.1.4.1.11591.4.11
hmac_sha256 = "2a864886f70d0209"  # 1.2.840.113549.2.9
hmac_sha1 = "2a864886f70d0207"  # 1.2.840.113549.2.7, refused
hmac_sha512 = "2a864886f70d020b"  # 1.2.840.113549.2.11, refused
aes256_cbc = "60864801650304012a"  # 2.16.840.1.101.3.4.1.42
des_ede3_cbc = "2a864886f70d0307"  # 1.2.840.113549.3.7, refused in PKCS#8
pkcs12_3des = "2a864886f70d010c0103"  # 1.2.840.113549.1.12.1.3, older PBES1 style, refused


# ---------------------------------------------- a small DER builder, to craft the test files


# This func builds one DER element: tag, length, value (see read_element in pem_guard.py)
def element(tag, value):
    # Under 128 the length is one byte, from 128 it's 0x80 + how many bytes, then the bytes
    # (n.bit_length() + 7) // 8 is how many bytes the number needs
    n = len(value)
    if n < 128:
        length = bytes([n])
    else:
        length_bytes = n.to_bytes((n.bit_length() + 7) // 8, "big")
        length = bytes([0x80 + len(length_bytes)]) + length_bytes
    return bytes([tag]) + length + value


# This func builds a SEQUENCE from a list of elements already built
def sequence(items):
    return element(0x30, b"".join(items))


# This func builds an INTEGER. DER numbers are signed, so 1 byte more than needed
# when the first bit would be set (e.g. 128 is written 00 80, not 80 which would be -128)
def integer(n):
    return element(0x02, n.to_bytes((n.bit_length() + 8) // 8, "big", signed=True))


# This func builds an OID element from the hex of its bytes
def oid(hex_bytes):
    return element(0x06, bytes.fromhex(hex_bytes))


# This func builds an OCTET STRING (raw bytes)
def octets(data):
    return element(0x04, data)


# This func puts DER bytes in an "ENCRYPTED PRIVATE KEY" PEM block
def to_pem(der):
    return (
        b"-----BEGIN ENCRYPTED PRIVATE KEY-----\n"
        + base64.encodebytes(der)
        + b"-----END ENCRYPTED PRIVATE KEY-----\n"
    )


# This func builds a whole encrypted PKCS#8 file around KDF settings I choose
# The encrypted key itself is random: the guard must decide from the settings alone
def encrypted_pem(kdf, scheme=pbes2, cipher=aes256_cbc):
    cipher_element = sequence([oid(cipher), octets(os.urandom(16))])
    algorithm = sequence([oid(scheme), sequence([kdf, cipher_element])])
    return to_pem(sequence([algorithm, octets(os.urandom(64))]))


# This func builds a PBKDF2 file. prf is the hash (None = not written, so SHA-1 by default)
def pbkdf2_pem(iterations, prf=hmac_sha256, key_length=None, cipher=aes256_cbc):
    # settings is a list of the PBKDF2 settings: salt, iterations, then the optional ones
    settings = [octets(os.urandom(16)), integer(iterations)]
    if key_length is not None:
        settings.append(integer(key_length))
    if prf is not None:
        settings.append(sequence([oid(prf), b"\x05\x00"]))  # 05 00 is a NULL element
    return encrypted_pem(sequence([oid(pbkdf2), sequence(settings)]), cipher=cipher)


# This func builds a scrypt file with N, r and p
def scrypt_pem(n, r, p):
    settings = sequence([octets(os.urandom(16)), integer(n), integer(r), integer(p), integer(32)])
    return encrypted_pem(sequence([oid(scrypt), settings]))


# This func builds an older "RSA PRIVATE KEY" with Proc-Type / DEK-Info header lines
def legacy_pem(dek_info, label=b"RSA PRIVATE KEY"):
    headers = b"Proc-Type: 4,ENCRYPTED\nDEK-Info: " + dek_info + b"\n\n"
    body = base64.encodebytes(os.urandom(64))
    return b"-----BEGIN " + label + b"-----\n" + headers + body + b"-----END " + label + b"-----\n"


# This func makes the library fail the test if a file ever reaches it
# monkeypatch (from pytest) swaps load_pem_private_key for the time of one test only
def library_must_not_run(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("The file reached the library before being checked")

    monkeypatch.setattr(keys.serialization, "load_pem_private_key", fail)


# ---------------------------------------------------------------------------------- tests


# This test checks that the settings real tools write are accepted
def test_normal_settings_pass():

    # This is a list of files with settings that cryptography or OpenSSL really write
    good_files = [
        pbkdf2_pem(2048),  # OpenSSL default
        pbkdf2_pem(10_000_000),  # the limit itself
        pbkdf2_pem(2048, key_length=32),
        scrypt_pem(16384, 8, 1),  # openssl pkcs8 -scrypt
        scrypt_pem(2**17, 8, 1),  # 128 MiB
        legacy_pem(b"AES-256-CBC," + b"AB" * 16),
        legacy_pem(b"DES-EDE3-CBC," + b"AB" * 8),
    ]
    for pem_data in good_files:
        labels, full_blocks = keys.split_pem_blocks(pem_data)
        pem_guard.check_private_blocks(labels, full_blocks)


# This test gives a list of crafted files and checks each one is refused
# before the library sees it
def test_dangerous_settings_refused(monkeypatch):
    library_must_not_run(monkeypatch)

    # This is a list of crafted files, each one with a comment saying what it does
    bad_files = [
        pbkdf2_pem(10_000_001),  # just over the limit
        pbkdf2_pem(2**31),  # made cryptography 50 crash
        pbkdf2_pem(2**40),
        pbkdf2_pem(2**64 - 1),  # 9 bytes, too big to even read
        pbkdf2_pem(0),
        pbkdf2_pem(-1),
        pbkdf2_pem(10_000_000, prf=None),  # SHA-1 by default: twice the work for AES-256
        pbkdf2_pem(10_000_000, prf=hmac_sha512),  # about 4x the work
        pbkdf2_pem(2048, prf=hmac_sha1),
        pbkdf2_pem(2048, cipher=des_ede3_cbc),
        scrypt_pem(2**20, 8, 1),  # 1 GiB, about 7 s
        scrypt_pem(2**22, 8, 1),  # 4 GiB
        scrypt_pem(2**20, 1024, 1),  # 128 GiB: OpenSSL runs out of memory
        scrypt_pem(2**20, 8, 4),  # p multiplies the time
        scrypt_pem(2, 4_194_304, 3),  # tiny N, huge r: 5 GiB, 53 s
        scrypt_pem(1024, 64, 1),  # r over the limit
        scrypt_pem(1000, 8, 1),  # N not a power of 2
        scrypt_pem(1024, 8, 100_000),  # huge p
        scrypt_pem(1, 8, 1),
        legacy_pem(b"AES-128-CBC," + b"00" * 8),  # 8 byte IV: made cryptography 50 crash
        legacy_pem(b"AES-256-CBC," + b"00" * 15),
        legacy_pem(b"AES-256-CBC," + b"00" * 16, label=b"PRIVATE KEY"),  # headers, wrong label
        legacy_pem(b"DES-CBC," + b"00" * 8),
        legacy_pem(b"AES-256-CBC," + b"00" * 16).replace(b"Proc-Type: 4,", b"Proc-Type:4,"),
        pbkdf2_pem(2048) + pbkdf2_pem(2048),  # 2 encrypted blocks: the costs add up
        encrypted_pem(sequence([oid(pbkdf2), sequence([octets(b"salt")])]), scheme=pkcs12_3des),
        encrypted_pem(sequence([oid(aes256_cbc), sequence([octets(b"salt"), integer(1)])])),
        encrypted_pem(sequence([oid(pbkdf2), sequence([octets(b"salt")])])),  # no iterations
    ]
    for pem_data in bad_files:
        with pytest.raises(InvalidPrivateKeyError):
            keys.load_private_keys(pem_data, b"any password")


# This test checks that broken DER or base64 is refused, not a crash
def test_broken_files_refused(monkeypatch):
    library_must_not_run(monkeypatch)

    # This is a list of broken files
    bad_files = [
        to_pem(b"\x30\x84\xff\xff\xff\xff"),  # says 4 GiB, has nothing
        to_pem(b"\x30\x00trailing"),  # data after the end
        to_pem(b"\x30\x89" + b"\x01" * 9),  # a length written on 9 bytes
        b"-----BEGIN ENCRYPTED PRIVATE KEY-----\n!!!\n-----END ENCRYPTED PRIVATE KEY-----\n",
        b"-----BEGIN ENCRYPTED PRIVATE KEY-----\n\n-----END ENCRYPTED PRIVATE KEY-----\n",
    ]
    for pem_data in bad_files:
        with pytest.raises(InvalidPrivateKeyError):
            keys.load_private_keys(pem_data, b"any password")


# This test checks the files from #55 that made core/keys.py crash, with the real library:
# they must now give our error
def test_files_that_crashed_core():

    # A normal RSA key, not encrypted, with a fake header line that has the word ENCRYPTED
    # (keys.py gave it the password, so the library raised TypeError)
    plain = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    fake_header = plain.replace(b"KEY-----\n", b"KEY-----\nX-Note: ENCRYPTED\n\n", 1)

    # This is a list of the 3 files that crashed
    crashing_files = [
        pbkdf2_pem(2**31),  # PanicException, not even an Exception
        legacy_pem(b"AES-128-CBC," + b"00" * 8),  # PanicException too
        fake_header,  # TypeError
    ]
    for pem_data in crashing_files:
        with pytest.raises(InvalidPrivateKeyError):
            keys.load_private_keys(pem_data, b"any password")


# This test checks the size limits: the whole file (before the regex) and each block
def test_size_limits(monkeypatch):
    library_must_not_run(monkeypatch)
    too_big = b"x" * (keys.max_key_file_size + 1)

    with pytest.raises(InvalidPrivateKeyError):
        keys.load_private_keys(too_big)
    with pytest.raises(InvalidKeyError):
        keys.load_public_keys(too_big)

    # Lots of BEGIN lines and no END: the regex was slow on this (0.55 s for 64 KiB)
    with pytest.raises(InvalidPrivateKeyError):
        keys.load_private_keys(b"-----BEGIN X-----\n" * 3640)

    # One block over 4 KiB, e.g. an RSA-8192 key (3 s of checks in the library)
    big_block = b"-----BEGIN PRIVATE KEY-----\n" + b"A" * 5000 + b"\n-----END PRIVATE KEY-----\n"
    with pytest.raises(InvalidPrivateKeyError):
        keys.load_private_keys(big_block)


# This test checks that the biggest real key a user can bring still loads:
# an encrypted RSA-4096 key (about 3.4 KiB), and our own 2 key file too
def test_biggest_real_key_fits():
    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    pem_data = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(b"pw"),
    )
    encryption_key, signing_key = keys.load_private_keys(pem_data, b"pw")
    assert keys.get_key_type(encryption_key) == "rsa-4096"
    assert signing_key is None

    # Our own file: the RSA-4096 key + an Ed25519 key, not encrypted
    ed_key = ed25519.Ed25519PrivateKey.generate()
    own_file = keys.private_keys_to_pem(encryption_key, ed_key)
    loaded_encryption, _loaded_signing = keys.load_private_keys(own_file)
    assert keys.get_key_type(loaded_encryption) == "rsa-4096"


# This test checks that the older encrypted RSA format (Proc-Type / DEK-Info) still loads
def test_old_encrypted_rsa_still_loads():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_data = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.BestAvailableEncryption(b"pw"),
    )
    assert b"DEK-Info" in pem_data
    encryption_key, _signing_key = keys.load_private_keys(pem_data, b"pw")
    assert keys.get_key_type(encryption_key) == "rsa-2048"


# This test checks that keys encrypted by the openssl command still load
# (skipped if openssl isn't installed on the machine)
@pytest.mark.skipif(shutil.which("openssl") is None, reason="needs the openssl command")
def test_openssl_encrypted_keys_load(tmp_path):
    key = x25519.X25519PrivateKey.generate()
    plain = tmp_path / "key.pem"
    plain.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

    # This is a list of the 2 ways openssl encrypts a key: PBKDF2 + AES, or scrypt
    for options in [["-v2", "aes-256-cbc"], ["-scrypt"]]:
        out = tmp_path / "encrypted.pem"
        # + puts the lists together into one list, the full command
        command = ["openssl", "pkcs8", "-topk8"] + options
        command = command + ["-in", str(plain), "-passout", "pass:pw", "-out", str(out)]
        subprocess.run(command, check=True, capture_output=True)  # noqa: S603 - fixed args
        encryption_key, _signing_key = keys.load_private_keys(out.read_bytes(), b"pw")
        assert keys.get_fingerprint(encryption_key.public_key()) == keys.get_fingerprint(
            key.public_key()
        )
