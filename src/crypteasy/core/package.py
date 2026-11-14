import json
import zipfile
from pathlib import Path

from crypteasy.core.errors import DecryptionError, UnsupportedFormatError

"""
In this file I have the format of the encrypted package (spec section 5.1): the .zip with
key.enc + file.enc inside, the header at the start of file.enc, and the name given to the
decrypted file on the disk
"""

# The package is a normal .zip, only used as a bag that holds the files below together
# This is a list of the files every package must have, exactly once each
# - key.enc: the file key, locked with the recipient's public key
# - file.enc: the header + the file encrypted with the file key
required_files = ["key.enc", "file.enc"]

# This is a list of the files a package is also allowed to have
# signature.sig is for signing (F9, stretch goal), it's accepted but not used yet
optional_files = ["signature.sig"]

# file.enc always starts with these bytes, called the "magic"
# It lets the app see right away if a file is one of ours, before reading anything else
magic = b"CRYPTEZ"

# The version of the format, written right after the magic (1 byte) and in the header
# If one day the format changes, the new version gets 2, and this version of the app
# says "made by a newer version" instead of trying to read it wrong
format_version = 1

# This is a dictionary: for each cipher (the key) it gives the size of its file key in bytes
# AES-256 uses a 32 bytes key (256 bits), AES-128 a 16 bytes key (128 bits)
ciphers = {"aes-256-gcm": 32, "aes-128-gcm": 16}

# This is a dictionary: for each key type of the recipient (the key) it gives how the file
# key is locked in key.enc (the value). It's written in the header, so the app knows how to
# open key.enc. RSA keys all use RSA-OAEP, X25519 uses a key exchange + HKDF (core/hybrid.py)
key_wraps = {
    "x25519": "x25519-hkdf-sha256",
    "rsa-2048": "rsa-oaep-sha256",
    "rsa-3072": "rsa-oaep-sha256",
    "rsa-4096": "rsa-oaep-sha256",
}

# The file is encrypted in pieces ("chunks") of 64 KiB, so a 4 GB file never has to be
# loaded in the RAM at once (spec 5.2). 64 * 1024 = 65536 bytes
chunk_size = 64 * 1024

# Limits checked when reading a package, bcs the package comes from someone else and could
# have been crafted to freeze the app (e.g. a header that says "chunks of 50 GB")
min_chunk_size = 1024  # 1 KiB
max_chunk_size = 16 * 1024 * 1024  # 16 MiB (spec 5.3 step 2)
max_header_size = 64 * 1024  # the real header is around 250 bytes
max_key_enc_size = 1024  # the biggest real key.enc is 512 bytes (RSA-4096)

# The name used when the original name of the file is not usable (spec section 8)
fallback_filename = "decrypted_file"

# This is a string of the characters Windows doesn't allow in a file name
# A file made on Linux can have them (e.g. "notes: monday.txt"), so they become "_"
forbidden_characters = '<>:"|?*'

# This is a list of the names Windows keeps for old devices: a file called CON or NUL
# (even CON.txt) can't be created normally, so they get a "_" in front
windows_reserved_names = ["CON", "PRN", "AUX", "NUL"]
for number in range(1, 10):
    windows_reserved_names.append(f"COM{number}")
    windows_reserved_names.append(f"LPT{number}")

# Max length kept for a file name, most systems refuse names longer than 255 characters
max_filename_length = 200


# This func builds the start of file.enc: magic + version + header length + header JSON
# The header holds the public settings, what the decryptor needs to know HOW the file was
# encrypted (spec 5.1). It holds no secrets, and not the file name (that one is encrypted)
# It returns bytes. Those exact bytes are also checked by every AES-GCM tag (core/hybrid.py),
# so if someone changes even 1 letter of the header, decrypting fails
def make_header(key_type: str, recipient_fingerprint: str, cipher: str, is_folder: bool) -> bytes:

    # 1. The header itself, as a dictionary
    # This is a dictionary of the settings, it becomes the JSON text of the header
    header = {
        "format": "crypteasy",
        "version": format_version,
        "key_type": key_type,
        "key_wrap": key_wraps[key_type],
        "recipient_fingerprint": recipient_fingerprint,
        "cipher": cipher,
        "chunk_size": chunk_size,
        "is_folder": is_folder,
    }

    # 2. Turn it into bytes
    # json.dumps gives the JSON text (str), .encode("utf-8") turns that text into bytes
    header_json = json.dumps(header).encode("utf-8")

    # 3. Put everything together
    # bytes([format_version]) makes 1 byte with the value 1
    # .to_bytes(4, "big") writes the length of the JSON as a number on 4 bytes, e.g. 250
    # gives 00 00 00 FA. The reader needs it to know where the JSON stops
    # "big" means the biggest part of the number comes first (the usual order for files)
    version_byte = bytes([format_version])
    length_bytes = len(header_json).to_bytes(4, "big")
    return magic + version_byte + length_bytes + header_json


# This func checks that the settings of a header are ones this version of the app knows
# It raises UnsupportedFormatError if the package was made with something we don't know
# (another format, a newer version, an unknown algorithm), and DecryptionError if a value
# makes no sense (then the file is damaged or was modified)
def check_header(header: dict):

    # 1. Format and version
    if header.get("format") != "crypteasy" or header.get("version") != format_version:
        raise UnsupportedFormatError("Not a CryptEasy package, or made by a newer version.")

    # 2. The algorithms: key type, how the file key is locked, cipher
    key_type = header.get("key_type")
    if key_type not in key_wraps:
        raise UnsupportedFormatError("Unknown key type.")
    if header.get("key_wrap") != key_wraps[key_type]:
        raise UnsupportedFormatError("Unknown key wrap.")
    if header.get("cipher") not in ciphers:
        raise UnsupportedFormatError("Unknown cipher.")

    # 3. The other values must have the right type
    # type(x) is int checks it's a whole number. I don't use isinstance here bcs in Python
    # True and False also count as numbers for isinstance (True is 1), and I don't want that
    chunk = header.get("chunk_size")
    if type(chunk) is not int or not min_chunk_size <= chunk <= max_chunk_size:
        raise DecryptionError("Invalid chunk size in the header.")
    if type(header.get("is_folder")) is not bool:
        raise DecryptionError("Invalid is_folder in the header.")
    if type(header.get("recipient_fingerprint")) is not str:
        raise DecryptionError("Invalid recipient fingerprint in the header.")


# This func reads the header at the start of file.enc (the opposite of make_header)
# fin is file.enc already opened, it reads only the header part, so after this func
# fin is right at the start of the encrypted chunks
# It returns 2 things: the header bytes exactly as they are in the file (needed to check
# the AES-GCM tags) and the header as a dictionary
def read_header(fin):

    # 1. The fixed part: magic (7 bytes) + version (1 byte) + length (4 bytes) = 12 bytes
    start_size = len(magic) + 1 + 4
    start = fin.read(start_size)
    # start[:7] takes the first 7 bytes, start[7] the 8th one (as a number),
    # start[8:12] the 4 bytes of the length
    if len(start) != start_size or start[: len(magic)] != magic:
        raise UnsupportedFormatError("Not a CryptEasy package.")
    if start[len(magic)] != format_version:
        raise UnsupportedFormatError("Made by a newer version of CryptEasy.")

    # 2. The JSON, its length is in the 4 bytes just read
    # int.from_bytes is the opposite of .to_bytes, it turns the 4 bytes back into a number
    header_length = int.from_bytes(start[len(magic) + 1 :], "big")
    if not 1 <= header_length <= max_header_size:
        raise DecryptionError("Invalid header length.")
    header_json = fin.read(header_length)
    if len(header_json) != header_length:
        raise DecryptionError("The header is cut.")

    # 3. Turn the JSON into a dictionary
    # json.loads raises a ValueError if it's not valid JSON (or not valid UTF-8 text)
    try:
        header = json.loads(header_json)
    except ValueError as error:
        raise DecryptionError("The header is not valid JSON.") from error
    # The JSON could be valid but be a list or a number instead of a dictionary
    if not isinstance(header, dict):
        raise DecryptionError("The header is not a dictionary.")

    # 4. Check the values
    check_header(header)
    return start + header_json, header


# This func opens a package and checks what's inside before anything is read (spec 5.3 step 1)
# It returns the opened zip, the caller uses it with "with" so it gets closed at the end
# The files are always read directly from the zip, never extracted on the disk with
# extractall: a crafted zip can hold names like "../../evil.exe" (zip-slip)
def open_package(package_path) -> zipfile.ZipFile:

    # 1. Open it as a zip
    # BadZipFile = it's not a zip at all (or the end of the zip is missing)
    try:
        zf = zipfile.ZipFile(package_path)
    except zipfile.BadZipFile as error:
        raise UnsupportedFormatError("Not a zip file.") from error

    # 2. Check the files inside
    # infolist() gives one "info" per file in the zip: its name, size, compression...
    # names is a list where I put the name of each file, it starts empty
    names = []
    for info in zf.infolist():
        names.append(info.filename)

    is_valid = True

    # Every required file must be there exactly once (a zip can hold the same name twice)
    for name in required_files:
        if names.count(name) != 1:
            is_valid = False

    # Nothing else than the expected files
    for name in names:
        if name not in required_files and name not in optional_files:
            is_valid = False
    if len(names) != len(set(names)):  # set() removes the duplicates
        is_valid = False

    # The app always makes "stored" zips (not compressed, compressing encrypted data is
    # useless). Refusing the other ones means a small zip can't unpack into a huge file
    # flag_bits & 1 is a bit that says the zip itself is password protected, never ours
    for info in zf.infolist():
        if info.compress_type != zipfile.ZIP_STORED or info.flag_bits & 1:
            is_valid = False

    # key.enc must have a sane size
    if is_valid and zf.getinfo("key.enc").file_size > max_key_enc_size:
        is_valid = False

    if not is_valid:
        zf.close()
        raise UnsupportedFormatError("This zip is not a CryptEasy package.")
    return zf


# This func reads the public header of a package, without decrypting anything
# Used by the Decrypt page to show who it's for, and if it's a folder (spec 5.3 steps 1 to 3)
# It returns the header as a dictionary, e.g. {"key_type": "x25519", "is_folder": False, ...}
def read_package_info(package_path) -> dict:
    try:
        with open_package(package_path) as zf:
            with zf.open("file.enc") as fin:
                header_bytes, header = read_header(fin)
    except zipfile.BadZipFile as error:
        raise DecryptionError("The zip is damaged.") from error
    return header


# This func cleans the original name of a decrypted file before it's used on the disk
# (spec section 8). The name comes from inside the package, so from someone else:
# a crafted package could ask for "../../Windows/evil.exe" to write outside the folder
# It returns a safe name, e.g. "../../evil.exe" gives "evil.exe"
def safe_filename(name: str) -> str:

    # 1. Keep only the last part of a path (the base name)
    # Windows uses \ between folders and Linux / macOS use /, so I turn every \ into /
    # and keep what's after the last /
    # "\\" is how a single \ is written in Python text, bcs \ alone is used for things
    # like \n (a new line)
    name = name.replace("\\", "/")
    name = name.split("/")[-1]

    # 2. Go through every character
    # A control character (code under 32, e.g. NUL or a new line) has no reason to be in a
    # real file name, so the name is not trusted at all and the fallback is used
    # ord(character) gives the code of a character, e.g. ord("A") = 65
    # clean is a list where I put each character I keep, it starts empty
    clean = []
    for character in name:
        if ord(character) < 32:
            return fallback_filename
        if character in forbidden_characters:
            clean.append("_")
        else:
            clean.append(character)
    # "".join(clean) puts the characters back together into one text
    name = "".join(clean)

    # 3. Windows doesn't allow a name ending with a space or a dot
    # .rstrip(" .") removes the spaces and dots at the end, so ".." also becomes ""
    name = name.rstrip(" .")
    if name == "":
        return fallback_filename

    # 4. Names Windows keeps for devices (CON, NUL, ...), with or without an extension
    # e.g. "con.txt": .split(".")[0] gives "con", .upper() gives "CON"
    if name.split(".")[0].upper() in windows_reserved_names:
        name = "_" + name

    # 5. Too long: cut the name but keep the extension (e.g. ".pdf")
    if len(name) > max_filename_length:
        suffix = Path(name).suffix[:20]
        name = name[: max_filename_length - len(suffix)] + suffix

    return name


# This func gives a path in a folder that doesn't exist yet, so nothing is ever overwritten
# (spec section 8). If "holidays.zip" is taken, it tries "holidays (2).zip", "holidays (3).zip"...
# It returns the path (Path), e.g. Desktop/holidays (2).zip
def free_path(folder, filename: str) -> Path:

    # Path(...) / "name" joins a folder and a name the right way for the OS (\ or /)
    path = Path(folder) / filename
    if not path.exists():
        return path

    # .stem is the name without the extension, .suffix the extension
    # e.g. for "holidays.zip": stem = "holidays", suffix = ".zip"
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    number = 2
    while True:
        path = Path(folder) / f"{stem} ({number}){suffix}"
        if not path.exists():
            return path
        number += 1
