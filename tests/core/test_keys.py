import re

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa, x25519

from crypteasy.core import keys
from crypteasy.core.errors import InvalidKeyError, InvalidPrivateKeyError, WrongPassphraseError

"""
In this file I test core/keys.py
Run only these tests with: make test-core
"""

# This is a dictionary: for each key type (the key) it keeps the key pair already made (the value)
# Generating RSA keys is slow (RSA-4096 can take a second), so I keep the keys here
# and each type is generated only once for all the tests
identities = {}


# This func gives the key pair of a type, and generates it only the first time
# It returns a tuple of the 2 private keys (encryption key, signing key)
def get_identity(key_type):
    if key_type not in identities:
        identities[key_type] = keys.generate_keypair(key_type)
    return identities[key_type]


# This func gives a public key as PEM, used to build bad files in the tests
def public_pem(public_key):
    return public_key.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )


# parametrize runs the same test once for each key type in the list keys.key_types
# This test checks that each type gives the right encryption key + an Ed25519 signing key
@pytest.mark.parametrize("key_type", keys.key_types)
def test_generate_keypair(key_type):
    # get_identity gives a tuple of 2 keys, and the 2 names on the left take one each
    encryption_key, signing_key = get_identity(key_type)

    # The encryption key has the right type, the signing key is always Ed25519
    assert keys.get_key_type(encryption_key) == key_type
    assert keys.get_key_type(encryption_key.public_key()) == key_type
    assert isinstance(signing_key, ed25519.Ed25519PrivateKey)

    if key_type == "x25519":
        assert isinstance(encryption_key, x25519.X25519PrivateKey)
    else:
        assert isinstance(encryption_key, rsa.RSAPrivateKey)
        assert encryption_key.key_size == keys.rsa_sizes[key_type]


# This test checks that a key type that doesn't exist is refused
# pytest.raises means "this line must raise this error, if not the test fails"
def test_generate_keypair_invalid_type():
    with pytest.raises(ValueError):
        keys.generate_keypair("rsa-1024")


# This test checks that keys we can't encrypt with are not recognised
def test_get_key_type_unsupported():
    # An Ed25519 key can't encrypt
    assert keys.get_key_type(ed25519.Ed25519PrivateKey.generate()) is None

    # An RSA-1024 key is too weak. noqa: weak key generated on purpose, to check it's refused
    weak_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)  # noqa: S505
    assert keys.get_key_type(weak_key) is None


# This test checks the format: 16 groups of 4 capital hex characters (SHA-256 = 64 characters)
def test_fingerprint_format():
    # _ is the usual name for a value from the tuple that I don't need (here the signing key)
    encryption_key, _ = get_identity("x25519")
    fingerprint = keys.get_fingerprint(encryption_key.public_key())

    # fullmatch means the whole string has to match the pattern, not only a part of it
    assert re.fullmatch(r"[0-9A-F]{4}( [0-9A-F]{4}){15}", fingerprint)


# This test checks that the same key always gives the same fingerprint,
# even after being saved in public.pem and loaded again
def test_fingerprint_is_stable():
    encryption_key, _ = get_identity("rsa-3072")
    public_key = encryption_key.public_key()

    pem_data = keys.public_keys_to_pem(public_key)
    loaded_key, _ = keys.load_public_keys(pem_data)
    assert keys.get_fingerprint(public_key) == keys.get_fingerprint(loaded_key)


# This test checks that two different keys don't have the same fingerprint
def test_fingerprint_differs_between_keys():
    key_a, _ = keys.generate_keypair("x25519")
    key_b, _ = keys.generate_keypair("x25519")
    assert keys.get_fingerprint(key_a.public_key()) != keys.get_fingerprint(key_b.public_key())


# This test saves both public keys in public.pem, loads them again
# and checks that we get the same keys back
@pytest.mark.parametrize("key_type", keys.key_types)
def test_public_pem_round_trip(key_type):
    encryption_key, signing_key = get_identity(key_type)
    pem_data = keys.public_keys_to_pem(encryption_key.public_key(), signing_key.public_key())

    # Both keys are in the file
    assert pem_data.count(b"-----BEGIN PUBLIC KEY-----") == 2

    loaded_encryption, loaded_signing = keys.load_public_keys(pem_data)
    assert keys.get_fingerprint(loaded_encryption) == keys.get_fingerprint(
        encryption_key.public_key()
    )
    assert keys.get_fingerprint(loaded_signing) == keys.get_fingerprint(signing_key.public_key())


# This test checks that a public key made somewhere else (e.g. with OpenSSL),
# so with only the encryption key, is accepted
def test_public_pem_single_key():
    encryption_key = x25519.X25519PrivateKey.generate()
    pem_data = keys.public_keys_to_pem(encryption_key.public_key())

    loaded_encryption, loaded_signing = keys.load_public_keys(pem_data)
    assert keys.get_key_type(loaded_encryption) == "x25519"
    assert loaded_signing is None


# This test checks that a public.pem saved on Windows still loads
# Windows ends each line with \r\n instead of \n, and split_pem_blocks has to handle that
def test_public_pem_windows_line_endings():
    encryption_key, signing_key = get_identity("x25519")
    pem_data = keys.public_keys_to_pem(encryption_key.public_key(), signing_key.public_key())
    windows_pem = pem_data.replace(b"\n", b"\r\n")

    loaded_encryption, loaded_signing = keys.load_public_keys(windows_pem)
    assert keys.get_fingerprint(loaded_encryption) == keys.get_fingerprint(
        encryption_key.public_key()
    )
    assert loaded_signing is not None


# This test gives a list of bad public key files and checks that each one is refused
def test_public_pem_rejects_bad_files():
    ed_key = ed25519.Ed25519PrivateKey.generate().public_key()
    ec_key = ec.generate_private_key(ec.SECP256R1()).public_key()
    x_key = x25519.X25519PrivateKey.generate().public_key()
    encryption_key, signing_key = get_identity("x25519")

    # This is a list of bad public key files, each one with a comment saying why it's bad
    bad_files = [
        b"",  # empty
        b"not a key at all",  # garbage
        public_pem(ed_key),  # a signing key can't be the encryption key
        public_pem(ec_key),  # unsupported curve
        public_pem(x_key) + public_pem(x_key),  # second key isn't a signing key
        public_pem(x_key) + public_pem(ed_key) + public_pem(ed_key),  # 3 keys
        keys.private_keys_to_pem(encryption_key, signing_key),  # a private key!
        b"-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PUBLIC KEY-----",  # broken content
        b"-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PRIVATE KEY-----",  # BEGIN and END differ
    ]
    for pem_data in bad_files:
        with pytest.raises(InvalidKeyError):
            keys.load_public_keys(pem_data)


# This test saves both private keys as PEM, loads them again
# and checks that we get the same keys back
@pytest.mark.parametrize("key_type", keys.key_types)
def test_private_pem_round_trip(key_type):
    encryption_key, signing_key = get_identity(key_type)
    pem_data = keys.private_keys_to_pem(encryption_key, signing_key)

    loaded_encryption, loaded_signing = keys.load_private_keys(pem_data)
    assert keys.get_fingerprint(loaded_encryption.public_key()) == keys.get_fingerprint(
        encryption_key.public_key()
    )
    assert keys.get_fingerprint(loaded_signing.public_key()) == keys.get_fingerprint(
        signing_key.public_key()
    )


# This test uses a standard private key file protected by a password (like OpenSSL makes)
# and checks the right password, a wrong one and a missing one
def test_private_pem_standard_encrypted_file():
    encryption_key, _ = get_identity("rsa-2048")
    secret = b"correct horse battery staple"
    pem_data = encryption_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(secret),
    )

    # Right password: the key is loaded, and there is no signing key in this kind of file
    loaded_encryption, loaded_signing = keys.load_private_keys(pem_data, secret)
    assert keys.get_key_type(loaded_encryption) == "rsa-2048"
    assert loaded_signing is None

    # Wrong password
    with pytest.raises(WrongPassphraseError):
        keys.load_private_keys(pem_data, b"wrong password")

    # No password at all
    with pytest.raises(WrongPassphraseError):
        keys.load_private_keys(pem_data)


# This test gives a list of bad private key files and checks that each one is refused
def test_private_pem_rejects_bad_files():
    encryption_key, signing_key = get_identity("x25519")
    ed_only = ed25519.Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    # This is a list of bad private key files, each one with a comment saying why it's bad
    bad_files = [
        b"",  # empty
        b"not a key at all",  # garbage
        ed_only,  # a signing key can't be the encryption key
        keys.public_keys_to_pem(encryption_key.public_key()),  # a public key
        b"-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----",  # broken content
        b"-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PUBLIC KEY-----",  # BEGIN and END differ
    ]
    for pem_data in bad_files:
        with pytest.raises(InvalidPrivateKeyError):
            keys.load_private_keys(pem_data)
