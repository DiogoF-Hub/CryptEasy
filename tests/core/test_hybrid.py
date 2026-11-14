import os
import zipfile

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from crypteasy.core import hybrid, keys, package
from crypteasy.core.errors import (
    DecryptionError,
    InvalidKeyError,
    InvalidPrivateKeyError,
    NoMatchingKeyError,
    UnsupportedFormatError,
)

"""
In this file I test core/hybrid.py: encrypt → decrypt round trips, and packages that
were damaged or changed on purpose
Run only these tests with: make test-core
"""

# This is a dictionary: for each key type (the key) it keeps the encryption private key (the
# value). Generating RSA keys is slow, so each type is generated only once for all the tests
private_keys = {}


# This func gives the encryption private key of a type, and generates it only the first time
def get_key(key_type):
    if key_type not in private_keys:
        encryption_key, signing_key = keys.generate_keypair(key_type)
        private_keys[key_type] = encryption_key
    return private_keys[key_type]


# This func encrypts some bytes for a key type and gives the path of the package
# It's the setup most tests need: a file on the disk + its package
def make_package(tmp_path, data, key_type="x25519", cipher="aes-256-gcm", name="secret.txt"):
    src = tmp_path / name
    src.write_bytes(data)
    package_path = tmp_path / "package.zip"
    hybrid.encrypt_file(src, package_path, get_key(key_type).public_key(), cipher)
    return package_path


# This func reads key.enc and file.enc out of a package, to change them in a test
def read_package(package_path):
    with zipfile.ZipFile(package_path) as zf:
        return zf.read("key.enc"), zf.read("file.enc")


# This func writes a new package with the key.enc and file.enc I give
def write_package(package_path, key_enc, file_enc):
    with zipfile.ZipFile(package_path, "w") as zf:
        zf.writestr("key.enc", key_enc)
        zf.writestr("file.enc", file_enc)


# This func gives the length of the header at the start of a file.enc
# 12 bytes (magic + version + length) + the length written in those 4 bytes
def header_length(file_enc):
    return 12 + int.from_bytes(file_enc[8:12], "big")


# This is a list of sizes to test, around the chunk size (64 KiB = 65536 bytes) bcs that's
# where mistakes happen: empty, 1 byte, 1 chunk exactly, 1 chunk + 1 byte, a few chunks
sizes = [0, 1, 1000, 65536, 65537, 3 * 65536 + 123]


# This test checks the main goal of #8: encrypt → decrypt gives back the exact same bytes,
# with every key type and both ciphers
@pytest.mark.parametrize("key_type", keys.key_types)
@pytest.mark.parametrize("cipher", list(package.ciphers))
def test_round_trip(tmp_path, key_type, cipher):
    data = os.urandom(200_000)
    package_path = make_package(tmp_path, data, key_type, cipher)

    out_dir = tmp_path / "out"
    result = hybrid.decrypt_package(package_path, get_key(key_type), out_dir)

    assert result == out_dir / "secret.txt"
    assert result.read_bytes() == data


# This test checks the round trip with sizes around the chunk size
@pytest.mark.parametrize("size", sizes)
def test_round_trip_sizes(tmp_path, size):
    data = os.urandom(size)
    package_path = make_package(tmp_path, data)

    result = hybrid.decrypt_package(package_path, get_key("x25519"), tmp_path / "out")
    assert result.read_bytes() == data


# This test checks what's inside the package: exactly key.enc + file.enc, not compressed,
# the header can be read, and the file name is NOT in clear anywhere
def test_package_contents(tmp_path):
    package_path = make_package(tmp_path, b"hello", name="my_secret_plans.txt")

    with zipfile.ZipFile(package_path) as zf:
        assert sorted(zf.namelist()) == ["file.enc", "key.enc"]
        for info in zf.infolist():
            assert info.compress_type == zipfile.ZIP_STORED

    info = package.read_package_info(package_path)
    assert info["key_type"] == "x25519"
    assert info["is_folder"] is False
    assert info["recipient_fingerprint"] == keys.get_fingerprint(get_key("x25519").public_key())

    assert b"my_secret_plans" not in package_path.read_bytes()
    assert b"hello" not in package_path.read_bytes()


# This test checks is_folder and original_name, used for folders: the temp zip has another
# name on the disk, but the recipient must get "holidays.zip"
def test_folder_name(tmp_path):
    src = tmp_path / ".crypteasy-temp1234.zip"
    src.write_bytes(b"pretend this is a zipped folder")
    package_path = tmp_path / "package.zip"
    public_key = get_key("x25519").public_key()
    hybrid.encrypt_file(src, package_path, public_key, is_folder=True, original_name="holidays.zip")

    assert package.read_package_info(package_path)["is_folder"] is True
    result = hybrid.decrypt_package(package_path, get_key("x25519"), tmp_path / "out")
    assert result.name == "holidays.zip"


# This test checks that the same file encrypted twice never gives the same package
# (new random file key each time, and a new throwaway key / random OAEP padding)
@pytest.mark.parametrize("key_type", ["x25519", "rsa-2048"])
def test_never_the_same_twice(tmp_path, key_type):
    src = tmp_path / "secret.txt"
    src.write_bytes(b"same file")
    public_key = get_key(key_type).public_key()
    hybrid.encrypt_file(src, tmp_path / "a.zip", public_key)
    hybrid.encrypt_file(src, tmp_path / "b.zip", public_key)

    key_enc_a, file_enc_a = read_package(tmp_path / "a.zip")
    key_enc_b, file_enc_b = read_package(tmp_path / "b.zip")
    assert key_enc_a != key_enc_b
    assert file_enc_a != file_enc_b


# This test checks that the progress func is called, and ends at 100 %
def test_progress(tmp_path):
    # This is a list where the progress func puts each (done, total) it gets
    calls = []

    def progress(done, total):
        calls.append((done, total))

    data = os.urandom(3 * 65536)
    src = tmp_path / "secret.txt"
    src.write_bytes(data)
    package_path = tmp_path / "package.zip"
    hybrid.encrypt_file(src, package_path, get_key("x25519").public_key(), progress=progress)
    assert calls[-1] == (len(data), len(data))

    calls.clear()
    hybrid.decrypt_package(package_path, get_key("x25519"), tmp_path / "out", progress=progress)
    done, total = calls[-1]
    assert done == total


# This test checks that encrypt_file never overwrites an existing file
def test_encrypt_never_overwrites(tmp_path):
    src = tmp_path / "secret.txt"
    src.write_bytes(b"data")
    package_path = tmp_path / "package.zip"
    package_path.write_bytes(b"something important")

    with pytest.raises(FileExistsError):
        hybrid.encrypt_file(src, package_path, get_key("x25519").public_key())
    assert package_path.read_bytes() == b"something important"


# This test checks that decrypting twice in the same folder gives "secret (2).txt",
# the first decrypted file is not overwritten
def test_decrypt_never_overwrites(tmp_path):
    package_path = make_package(tmp_path, b"data")
    out_dir = tmp_path / "out"

    first = hybrid.decrypt_package(package_path, get_key("x25519"), out_dir)
    second = hybrid.decrypt_package(package_path, get_key("x25519"), out_dir)
    assert first.name == "secret.txt"
    assert second.name == "secret (2).txt"


# This test checks the keys that can't be used: a signing key (Ed25519), a private key given
# instead of a public one, a weak RSA-1024 key, a bad cipher
def test_encrypt_bad_inputs(tmp_path):
    src = tmp_path / "secret.txt"
    src.write_bytes(b"data")
    encryption_key, signing_key = keys.generate_keypair("x25519")

    with pytest.raises(InvalidKeyError):
        hybrid.encrypt_file(src, tmp_path / "a.zip", signing_key.public_key())
    with pytest.raises(InvalidKeyError):
        hybrid.encrypt_file(src, tmp_path / "b.zip", encryption_key)
    weak_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)  # noqa: S505
    with pytest.raises(InvalidKeyError):
        hybrid.encrypt_file(src, tmp_path / "c.zip", weak_key.public_key())
    with pytest.raises(ValueError):
        hybrid.encrypt_file(src, tmp_path / "d.zip", encryption_key.public_key(), "aes-256-cbc")

    # Nothing was left on the disk, not even a temp file
    # os.listdir gives the list of the names in a folder
    assert os.listdir(tmp_path) == ["secret.txt"]


# This test checks that decrypt_package refuses a public key or a signing key
def test_decrypt_bad_key(tmp_path):
    package_path = make_package(tmp_path, b"data")
    encryption_key, signing_key = keys.generate_keypair("x25519")

    with pytest.raises(InvalidPrivateKeyError):
        hybrid.decrypt_package(package_path, encryption_key.public_key(), tmp_path / "out")
    with pytest.raises(InvalidPrivateKeyError):
        hybrid.decrypt_package(package_path, signing_key, tmp_path / "out")


# This test checks that a package for someone else is refused right away ("not for you")
@pytest.mark.parametrize("key_type", ["x25519", "rsa-2048"])
def test_wrong_recipient(tmp_path, key_type):
    package_path = make_package(tmp_path, b"data", key_type)
    other_key, other_signing_key = keys.generate_keypair(key_type)

    out_dir = tmp_path / "out"
    with pytest.raises(NoMatchingKeyError):
        hybrid.decrypt_package(package_path, other_key, out_dir)
    assert list(out_dir.iterdir()) == []


# This test changes 1 byte at different places of file.enc and checks that each time
# decrypting fails AND nothing is left in the output folder (spec 5.3 step 6)
def test_tampered_file_enc(tmp_path):
    data = os.urandom(3 * 65536)
    package_path = make_package(tmp_path, data)
    key_enc, file_enc = read_package(package_path)
    start = header_length(file_enc)

    # This is a list of positions in file.enc: in chunk 0 (the name), in the first chunk,
    # in the middle, and the very last byte (the tag of the last chunk)
    positions = [start + 5, start + 1040 + 10, len(file_enc) // 2, len(file_enc) - 1]
    for position in positions:
        # bytearray is like bytes but can be changed. ^ 1 flips the lowest bit of the byte
        changed = bytearray(file_enc)
        changed[position] = changed[position] ^ 1
        write_package(package_path, key_enc, bytes(changed))

        out_dir = tmp_path / f"out_{position}"
        with pytest.raises(DecryptionError):
            hybrid.decrypt_package(package_path, get_key("x25519"), out_dir)
        assert list(out_dir.iterdir()) == []


# This test changes the header without touching the chunks: since the header is checked by
# every tag, even a change that looks harmless (is_folder false → true) is detected
def test_tampered_header(tmp_path):
    package_path = make_package(tmp_path, b"data")
    key_enc, file_enc = read_package(package_path)

    # "false" and "true " have the same length, so the header length stays right
    changed = file_enc.replace(b'"is_folder": false', b'"is_folder": true ', 1)
    assert changed != file_enc
    write_package(package_path, key_enc, changed)

    with pytest.raises(DecryptionError):
        hybrid.decrypt_package(package_path, get_key("x25519"), tmp_path / "out")


# This test swaps the cipher in the header (aes-256 → aes-128): the file key in key.enc is
# 32 bytes, so it doesn't match and it's refused
def test_tampered_cipher(tmp_path):
    package_path = make_package(tmp_path, b"data")
    key_enc, file_enc = read_package(package_path)
    write_package(package_path, key_enc, file_enc.replace(b"aes-256-gcm", b"aes-128-gcm", 1))

    with pytest.raises(DecryptionError):
        hybrid.decrypt_package(package_path, get_key("x25519"), tmp_path / "out")


# This test checks the chunks themselves: the last one removed, data added at the end,
# 2 chunks swapped. Each chunk alone is valid, only their order / number is wrong
def test_cut_or_reordered_chunks(tmp_path):
    data = os.urandom(3 * 65536 + 100)  # 4 chunks: 3 full + 1 small
    package_path = make_package(tmp_path, data)
    key_enc, file_enc = read_package(package_path)

    # Split file.enc into: the header + chunk 0 (the name), then the encrypted data chunks
    start = header_length(file_enc) + 1024 + 16
    full = 65536 + 16
    head = file_enc[:start]
    chunk_1 = file_enc[start : start + full]
    chunk_2 = file_enc[start + full : start + 2 * full]
    rest = file_enc[start + 2 * full :]

    # This is a list of broken versions of file.enc
    broken = [
        file_enc[: start + 3 * full],  # the last chunk removed (cut exactly between 2 chunks)
        file_enc[:-50],  # cut in the middle of the last chunk
        file_enc + b"extra data at the end",
        head + chunk_2 + chunk_1 + rest,  # chunks 1 and 2 swapped
        head,  # only the name, no data at all
    ]
    for number, file_enc_broken in enumerate(broken):
        write_package(package_path, key_enc, file_enc_broken)
        out_dir = tmp_path / f"out_{number}"
        with pytest.raises(DecryptionError):
            hybrid.decrypt_package(package_path, get_key("x25519"), out_dir)
        assert list(out_dir.iterdir()) == []


# This test changes key.enc: for both key types it must be refused
@pytest.mark.parametrize("key_type", ["x25519", "rsa-2048"])
def test_tampered_key_enc(tmp_path, key_type):
    package_path = make_package(tmp_path, b"data", key_type)
    key_enc, file_enc = read_package(package_path)

    # This is a list of broken versions of key.enc
    changed = bytearray(key_enc)
    changed[-1] = changed[-1] ^ 1
    broken = [bytes(changed), key_enc[:20], bytes(len(key_enc))]
    for key_enc_broken in broken:
        write_package(package_path, key_enc_broken, file_enc)
        with pytest.raises(DecryptionError):
            hybrid.decrypt_package(package_path, get_key(key_type), tmp_path / "out")


# This test checks that key.enc from another package can't be mixed with this file.enc:
# both are for the same key, but the file key is not the same, so the tags fail
def test_key_enc_from_another_package(tmp_path):
    package_path = make_package(tmp_path, b"first file")
    key_enc, file_enc = read_package(package_path)

    other = tmp_path / "other"
    other.mkdir()
    other_key_enc, other_file_enc = read_package(make_package(other, b"second file"))

    write_package(package_path, other_key_enc, file_enc)
    with pytest.raises(DecryptionError):
        hybrid.decrypt_package(package_path, get_key("x25519"), tmp_path / "out")


# This test checks that something that's not a package gives UnsupportedFormatError
def test_not_a_package(tmp_path):
    fake = tmp_path / "holidays.zip"
    fake.write_bytes(b"just some text, not a zip")
    with pytest.raises(UnsupportedFormatError):
        hybrid.decrypt_package(fake, get_key("x25519"), tmp_path / "out")


# This test checks that a dangerous name inside the package is cleaned on decrypt
def test_dangerous_name(tmp_path):
    src = tmp_path / "secret.txt"
    src.write_bytes(b"data")
    package_path = tmp_path / "package.zip"
    public_key = get_key("x25519").public_key()
    hybrid.encrypt_file(src, package_path, public_key, original_name="../../evil.exe")

    out_dir = tmp_path / "out"
    result = hybrid.decrypt_package(package_path, get_key("x25519"), out_dir)
    assert result == out_dir / "evil.exe"
