import io
import json
import zipfile

import pytest

from crypteasy.core import package
from crypteasy.core.errors import DecryptionError, UnsupportedFormatError

"""
In this file I test core/package.py (the zip, the header, the file names)
Run only these tests with: make test-core
"""

fingerprint = "3F2A 91C0 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000 0000"


# This func builds the start of a file.enc from a header dictionary I choose,
# so I can test headers that make_header would never make
def header_from_dict(header):
    header_json = json.dumps(header).encode("utf-8")
    return package.magic + bytes([1]) + len(header_json).to_bytes(4, "big") + header_json


# This func gives a valid header as a dictionary, the tests change one value in it
def valid_header():
    header_bytes = package.make_header("x25519", fingerprint, "aes-256-gcm", False)
    return json.loads(header_bytes[12:])


# This func writes a zip with the files I choose, to test packages that are not valid
# files is a dictionary: for each name (the key) it gives the content (the value)
def write_zip(path, files, compression=zipfile.ZIP_STORED):
    with zipfile.ZipFile(path, "w", compression=compression) as zf:
        for name, content in files.items():
            zf.writestr(name, content)


# This test checks that read_header gives back exactly what make_header wrote
def test_header_round_trip():
    header_bytes = package.make_header("rsa-3072", fingerprint, "aes-128-gcm", True)

    # io.BytesIO makes bytes look like an opened file, so read_header can .read() it
    # The extra b"chunks" after the header must not be read
    fin = io.BytesIO(header_bytes + b"chunks")
    read_bytes, header = package.read_header(fin)

    assert read_bytes == header_bytes
    assert header["key_type"] == "rsa-3072"
    assert header["key_wrap"] == "rsa-oaep-sha256"
    assert header["cipher"] == "aes-128-gcm"
    assert header["is_folder"] is True
    assert header["recipient_fingerprint"] == fingerprint
    assert fin.read() == b"chunks"


# This test checks that something that's not our format at all is refused
def test_read_header_not_ours():
    with pytest.raises(UnsupportedFormatError):
        package.read_header(io.BytesIO(b"PK\x03\x04 this is a zip, not file.enc"))
    with pytest.raises(UnsupportedFormatError):
        package.read_header(io.BytesIO(b""))


# This test checks that a package made by a newer version is refused, with the version
# byte after the magic or with the version in the header
def test_read_header_newer_version():
    header_bytes = package.make_header("x25519", fingerprint, "aes-256-gcm", False)
    # header_bytes[:7] is the magic, bytes([2]) replaces the version byte, [8:] is the rest
    newer = header_bytes[:7] + bytes([2]) + header_bytes[8:]
    with pytest.raises(UnsupportedFormatError):
        package.read_header(io.BytesIO(newer))

    header = valid_header()
    header["version"] = 2
    with pytest.raises(UnsupportedFormatError):
        package.read_header(io.BytesIO(header_from_dict(header)))


# This test gives a list of headers with one bad value each, and checks each one is refused
def test_read_header_bad_values():

    # This is a list of tuples (name of the setting, bad value, error expected)
    bad_values = [
        ("format", "gpg", UnsupportedFormatError),  # not our format
        ("key_type", "rsa-1024", UnsupportedFormatError),  # key type we don't accept
        ("key_wrap", "rsa-pkcs1", UnsupportedFormatError),  # unknown way to lock the key
        ("cipher", "aes-256-cbc", UnsupportedFormatError),  # weak mode, never used
        ("chunk_size", 50 * 1024**3, DecryptionError),  # chunks of 50 GB
        ("chunk_size", 0, DecryptionError),
        ("chunk_size", "65536", DecryptionError),  # text, not a number
        ("is_folder", "yes", DecryptionError),
        ("is_folder", 1, DecryptionError),  # a number, not True / False
        ("recipient_fingerprint", 42, DecryptionError),
    ]
    for setting, value, error in bad_values:
        header = valid_header()
        header[setting] = value
        with pytest.raises(error):
            package.read_header(io.BytesIO(header_from_dict(header)))


# This test checks headers that are broken: cut, not JSON, not a dictionary, too long
def test_read_header_broken():
    header_bytes = package.make_header("x25519", fingerprint, "aes-256-gcm", False)

    # Cut in the middle of the JSON
    with pytest.raises(DecryptionError):
        package.read_header(io.BytesIO(header_bytes[:30]))

    # This is a list of things that are not a valid JSON dictionary
    for bad_json in [b"{not json", b"[1, 2, 3]", b"\xff\xfe"]:
        fin = io.BytesIO(package.magic + bytes([1]) + len(bad_json).to_bytes(4, "big") + bad_json)
        with pytest.raises(DecryptionError):
            package.read_header(fin)

    # A length of 1 GB
    with pytest.raises(DecryptionError):
        package.read_header(io.BytesIO(package.magic + bytes([1]) + (1024**3).to_bytes(4, "big")))


# This test checks that a valid package opens, also with the optional signature.sig
def test_open_package_valid(tmp_path):
    # tmp_path is a temp folder made by pytest for this test, deleted after
    path = tmp_path / "package.zip"
    write_zip(path, {"key.enc": b"k", "file.enc": b"f"})
    with package.open_package(path) as zf:
        assert zf.read("key.enc") == b"k"

    signed = tmp_path / "signed.zip"
    write_zip(signed, {"key.enc": b"k", "file.enc": b"f", "signature.sig": b"s"})
    with package.open_package(signed) as zf:
        assert zf.read("file.enc") == b"f"


# This test gives a list of zips that are not packages, and checks each one is refused
def test_open_package_invalid(tmp_path):

    # This is a list of dictionaries, each one is the content of a bad zip
    bad_zips = [
        {"file.enc": b"f"},  # key.enc missing
        {"key.enc": b"k"},  # file.enc missing
        {"key.enc": b"k", "file.enc": b"f", "evil.exe": b"x"},  # an extra file
        {"key.enc": b"k", "file.enc": b"f", "../key.enc": b"x"},  # zip-slip name
        {"key.enc": b"k" * 5000, "file.enc": b"f"},  # key.enc way too big
    ]
    # enumerate gives the position of each item too: 0, 1, 2...
    for number, files in enumerate(bad_zips):
        path = tmp_path / f"bad_{number}.zip"
        write_zip(path, files)
        with pytest.raises(UnsupportedFormatError):
            package.open_package(path)

    # A compressed zip (the app only makes stored ones)
    compressed = tmp_path / "compressed.zip"
    write_zip(compressed, {"key.enc": b"k", "file.enc": b"f"}, zipfile.ZIP_DEFLATED)
    with pytest.raises(UnsupportedFormatError):
        package.open_package(compressed)

    # Not a zip at all
    not_zip = tmp_path / "photo.jpg"
    not_zip.write_bytes(b"\xff\xd8\xff this is not a zip")
    with pytest.raises(UnsupportedFormatError):
        package.open_package(not_zip)


# This test checks that the same name twice in a zip is refused
def test_open_package_duplicate_name(tmp_path):
    path = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("key.enc", b"k")
        zf.writestr("file.enc", b"f")
        # Python warns when writing the same name twice, that's exactly what I want to test
        with pytest.warns(UserWarning):
            zf.writestr("key.enc", b"other")
    with pytest.raises(UnsupportedFormatError):
        package.open_package(path)


# This test checks that read_package_info gives the header of a package
def test_read_package_info(tmp_path):
    path = tmp_path / "anything.zip"
    header_bytes = package.make_header("x25519", fingerprint, "aes-256-gcm", True)
    write_zip(path, {"key.enc": b"k", "file.enc": header_bytes + b"chunks"})

    info = package.read_package_info(path)
    assert info["recipient_fingerprint"] == fingerprint
    assert info["is_folder"] is True


# This test gives a list of file names from a package and the safe name each one must give
def test_safe_filename():

    # This is a list of tuples (name in the package, name expected on the disk)
    names = [
        ("holidays.zip", "holidays.zip"),
        ("rapport final.pdf", "rapport final.pdf"),
        ("vacances_été.jpg", "vacances_été.jpg"),  # accents are fine
        ("../../evil.exe", "evil.exe"),  # zip-slip with /
        ("..\\..\\Windows\\evil.exe", "evil.exe"),  # zip-slip with \
        ("/etc/passwd", "passwd"),  # absolute path
        ("C:\\Users\\bob\\notes.txt", "notes.txt"),
        ("notes: monday?.txt", "notes_ monday_.txt"),  # characters Windows refuses
        ("CON", "_CON"),
        ("nul.txt", "_nul.txt"),
        ("report.pdf. . ", "report.pdf"),  # Windows drops dots and spaces at the end
        ("", package.fallback_filename),
        (".", package.fallback_filename),
        ("..", package.fallback_filename),
        ("folder/", package.fallback_filename),
        ("evil\x00.exe", package.fallback_filename),  # NUL character
        ("two\nlines.txt", package.fallback_filename),
    ]
    for name, expected in names:
        assert package.safe_filename(name) == expected


# This test checks that a very long name is cut but keeps its extension
def test_safe_filename_too_long():
    name = package.safe_filename("a" * 1000 + ".pdf")
    assert len(name) == package.max_filename_length
    assert name.endswith(".pdf")


# This test checks that free_path never gives the path of a file that already exists
def test_free_path(tmp_path):
    assert package.free_path(tmp_path, "holidays.zip") == tmp_path / "holidays.zip"

    (tmp_path / "holidays.zip").write_bytes(b"already here")
    assert package.free_path(tmp_path, "holidays.zip") == tmp_path / "holidays (2).zip"

    (tmp_path / "holidays (2).zip").write_bytes(b"also here")
    assert package.free_path(tmp_path, "holidays.zip") == tmp_path / "holidays (3).zip"
