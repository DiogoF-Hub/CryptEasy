import pytest

from crypteasy.core import kdf

"""
In this file I test core/kdf.py
Run only these tests with: make test-core
"""

# The real presets take up to 1.5 s each, so most tests use these small settings instead:
# they are valid, just much faster (and much weaker), which is fine to test the logic
# This is a dictionary: for each KDF it gives small settings that are quick to run
fast_params = {
    "argon2id": {"memory_kib": 64, "iterations": 1, "parallelism": 1},
    "pbkdf2-sha256": {"iterations": 1000},
}

passphrase = b"une phrase secrete assez longue"


# This test checks that every KDF has settings for every strength,
# and that they pass the checks (so the presets themselves are valid)
@pytest.mark.parametrize("kdf_type", kdf.kdf_types)
@pytest.mark.parametrize("strength", kdf.kdf_strengths)
def test_presets_are_valid(kdf_type, strength):
    params = kdf.get_kdf_params(kdf_type, strength)
    salt = kdf.generate_salt(kdf_type, 16)

    # check_params raises an error if something is wrong, so no error = valid
    kdf.check_params(kdf_type, salt, params)


# This test checks that the presets get stronger: normal < strong < max
@pytest.mark.parametrize("kdf_type", kdf.kdf_types)
def test_presets_get_stronger(kdf_type):
    normal = kdf.get_kdf_params(kdf_type, "normal")
    strong = kdf.get_kdf_params(kdf_type, "strong")
    maximum = kdf.get_kdf_params(kdf_type, "max")

    if kdf_type == "argon2id":
        # memory x iterations is the total work of one try
        assert (
            normal["memory_kib"] * normal["iterations"]
            < strong["memory_kib"] * strong["iterations"]
        )
        assert (
            strong["memory_kib"] * strong["iterations"]
            < maximum["memory_kib"] * maximum["iterations"]
        )
    else:
        assert normal["iterations"] < strong["iterations"] < maximum["iterations"]


# This test checks that get_kdf_params gives a copy: changing it doesn't change the presets
def test_get_kdf_params_gives_a_copy():
    params = kdf.get_kdf_params("argon2id", "normal")
    params["iterations"] = 999
    assert kdf.get_kdf_params("argon2id", "normal")["iterations"] != 999


# This test checks that a KDF or a strength that doesn't exist is refused
def test_get_kdf_params_invalid():
    with pytest.raises(ValueError):
        kdf.get_kdf_params("md5", "normal")
    # "fort" was the old French name of "strong" in the interface, it must not work anymore
    with pytest.raises(ValueError):
        kdf.get_kdf_params("argon2id", "fort")


# This test checks the salt sizes, and that each salt is random
def test_generate_salt():
    assert len(kdf.generate_salt("argon2id", 32)) == 32
    assert len(kdf.generate_salt("argon2id", 16)) == 16
    assert kdf.generate_salt("pbkdf2-sha256", 0) == b""

    # Two salts are never the same (16 random bytes)
    assert kdf.generate_salt("argon2id", 16) != kdf.generate_salt("argon2id", 16)


# This test checks the salt rules: no salt with Argon2id, and only 32 / 16 / 0 bytes
def test_generate_salt_invalid():
    with pytest.raises(ValueError):
        kdf.generate_salt("argon2id", 0)
    with pytest.raises(ValueError):
        kdf.generate_salt("pbkdf2-sha256", 8)


# This test checks that the same passphrase + salt + settings always give the same lock key,
# that's what lets keystore/ unlock the private keys later
@pytest.mark.parametrize("kdf_type", kdf.kdf_types)
def test_derive_key_is_stable(kdf_type):
    salt = kdf.generate_salt(kdf_type, 16)
    params = fast_params[kdf_type]

    key_1 = kdf.derive_key(passphrase, kdf_type, salt, params)
    key_2 = kdf.derive_key(passphrase, kdf_type, salt, params)
    assert key_1 == key_2
    assert len(key_1) == kdf.lock_key_length


# This test checks that changing anything (passphrase, salt, settings) gives another lock key
@pytest.mark.parametrize("kdf_type", kdf.kdf_types)
def test_derive_key_changes(kdf_type):
    salt = kdf.generate_salt(kdf_type, 16)
    params = fast_params[kdf_type]
    key = kdf.derive_key(passphrase, kdf_type, salt, params)

    # Another passphrase
    assert kdf.derive_key(b"une autre phrase secrete", kdf_type, salt, params) != key

    # Another salt
    other_salt = kdf.generate_salt(kdf_type, 16)
    assert kdf.derive_key(passphrase, kdf_type, other_salt, params) != key

    # Other settings: one more iteration
    other_params = dict(params)
    other_params["iterations"] += 1
    assert kdf.derive_key(passphrase, kdf_type, salt, other_params) != key


# This test shows why "no salt" is weak: without a salt, two different users who chose
# the same passphrase get exactly the same lock key
def test_no_salt_gives_the_same_key_for_everyone():
    params = fast_params["pbkdf2-sha256"]
    key_user_1 = kdf.derive_key(passphrase, "pbkdf2-sha256", b"", params)
    key_user_2 = kdf.derive_key(passphrase, "pbkdf2-sha256", b"", params)
    assert key_user_1 == key_user_2

    # With a salt each, the same passphrase gives 2 different lock keys
    salt_1 = kdf.generate_salt("pbkdf2-sha256", 16)
    salt_2 = kdf.generate_salt("pbkdf2-sha256", 16)
    key_salted_1 = kdf.derive_key(passphrase, "pbkdf2-sha256", salt_1, params)
    key_salted_2 = kdf.derive_key(passphrase, "pbkdf2-sha256", salt_2, params)
    assert key_salted_1 != key_salted_2


# This test checks that an empty passphrase is refused (the no passphrase mode doesn't use the KDF)
def test_derive_key_empty_passphrase():
    salt = kdf.generate_salt("argon2id", 16)
    with pytest.raises(ValueError):
        kdf.derive_key(b"", "argon2id", salt, fast_params["argon2id"])


# This test gives a list of bad settings, like a crafted private.key file could have,
# and checks that each one is refused BEFORE running the KDF
def test_check_params_rejects_bad_settings():
    salt = b"0123456789abcdef"  # 16 bytes

    # This is a list of tuples (kdf, salt, settings), each one with a comment saying why it's bad
    bad_settings = [
        ("md5", salt, {"iterations": 1000}),  # unknown KDF
        ("argon2id", b"", fast_params["argon2id"]),  # Argon2id without a salt
        ("argon2id", b"12345678", fast_params["argon2id"]),  # salt of 8 bytes, not 32 / 16 / 0
        ("argon2id", salt, {"memory_kib": 64, "iterations": 1}),  # parallelism missing
        (
            "argon2id",
            salt,
            {"memory_kib": "64", "iterations": 1, "parallelism": 1},
        ),  # text, not a number
        (
            "argon2id",
            salt,
            {"memory_kib": 4096, "iterations": 1.5, "parallelism": 1},
        ),  # not a whole number
        (
            "argon2id",
            salt,
            {"memory_kib": 100_000_000, "iterations": 1, "parallelism": 1},
        ),  # ~100 GB RAM
        ("argon2id", salt, {"memory_kib": 4096, "iterations": 0, "parallelism": 1}),  # 0 iterations
        ("argon2id", salt, {"memory_kib": 4096, "iterations": 1000, "parallelism": 1}),  # too many
        (
            "argon2id",
            salt,
            {"memory_kib": 8, "iterations": 1, "parallelism": 4},
        ),  # < 8 KiB per parallel thread
        ("pbkdf2-sha256", salt, {}),  # iterations missing
        ("pbkdf2-sha256", salt, {"iterations": 0}),  # 0 iterations
        ("pbkdf2-sha256", salt, {"iterations": 1_000_000_000}),  # a billion iterations
    ]
    for kdf_type, bad_salt, params in bad_settings:
        with pytest.raises(ValueError):
            kdf.check_params(kdf_type, bad_salt, params)
