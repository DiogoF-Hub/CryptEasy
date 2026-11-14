import os
import zipfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from crypteasy.core import keys, package
from crypteasy.core.errors import (
    DecryptionError,
    InvalidKeyError,
    InvalidPrivateKeyError,
    NoMatchingKeyError,
)

"""
In this file I have the hybrid encryption itself: encrypting a file into a package
for a recipient, and decrypting a package with a private key (spec sections 5.2 and 5.3)
"""

# Hybrid = 2 kinds of encryption together:
# - the file is encrypted with AES-GCM and a random "file key" (symmetric: the same key locks
#   and unlocks). AES is very fast, so it's used for the file itself, even a 4 GB one
# - the file key is then locked with the recipient's public key (asymmetric: the public key
#   locks, only the private key unlocks). It's slow, but the file key is only 32 bytes
# So nobody has to send a password: only the recipient's private key can open key.enc,
# and only the file key inside key.enc can open file.enc
#
# file.enc after the header is a list of chunks, each one encrypted on its own:
#   [ chunk 0 = the original file name ] [ chunk 1 ] [ chunk 2 ] ... [ last chunk ]
# Each encrypted chunk ends with a 16 bytes "tag". AES-GCM computes it from the key, the data
# and the header, and checks it when decrypting: if 1 bit of the chunk or of the header was
# changed, the tag doesn't match and decrypting fails. That's how changes are detected

# Size of an AES-GCM tag in bytes
tag_size = 16

# The file name is in chunk 0, always padded to this size (in bytes, before encryption),
# so the size of file.enc doesn't tell how long the name is
# 2 bytes for the length of the name + the name (up to 1022 bytes) + zeros to fill the rest
name_chunk_size = 1024

# Text mixed into HKDF for X25519 (see lock_file_key), so the key it gives is only
# ever used for this, the key.enc of CryptEasy version 1
hkdf_info = b"crypteasy key.enc v1"

# The temporary files start with this, so they are easy to spot (and to clean up)
temp_prefix = ".crypteasy-"

# The RSA-OAEP settings, the same for locking and unlocking (spec 5.2 step 3)
# OAEP is the safe way to encrypt with RSA: it adds randomness, so the same file key never
# gives the same key.enc twice, and it uses SHA-256 inside
rsa_oaep = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)


# This func makes the nonce of a chunk
# A nonce ("number used once") is 12 bytes given to AES-GCM with each chunk. With the same
# key, 2 chunks must never use the same nonce, so I use the chunk number:
# - the first 11 bytes = the chunk number (0, 1, 2, ...)
# - the last byte = 1 if it's the last chunk, 0 otherwise
# Bcs the number is inside the nonce, swapping 2 chunks makes their tags fail. Bcs the
# "last" flag is inside too, cutting the end of the file (or adding data after) makes the
# tags fail too: the chunk that ends up last was not encrypted as the last one
# A random file key is made for every file, so these nonces are never reused with a key
def make_nonce(chunk_number: int, is_last: bool) -> bytes:
    if is_last:
        last_byte = b"\x01"  # \x01 is the byte with the value 1
    else:
        last_byte = b"\x00"
    return chunk_number.to_bytes(11, "big") + last_byte


# This func gives the key that locks the file key with X25519
# X25519 can't encrypt directly, it can only make a "shared secret": my private key + your
# public key gives the same 32 bytes as your private key + my public key. HKDF then turns
# that shared secret into a proper AES key
# The 2 public keys go in the salt, so the key is tied to this exact pair of keys
def x25519_wrap_key(shared_secret: bytes, throwaway_public: bytes, recipient_public: bytes):
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=throwaway_public + recipient_public,
        info=hkdf_info,
    )
    return hkdf.derive(shared_secret)


# This func locks the file key with the recipient's public key, it gives key.enc (spec 5.2 step 3)
# - RSA: key.enc = the file key encrypted with RSA-OAEP
# - X25519: key.enc = throwaway public key (32 bytes) + nonce (12 bytes) + locked file key
# It returns key.enc as bytes
def lock_file_key(file_key: bytes, public_key) -> bytes:

    # RSA: the public key encrypts the file key directly
    if isinstance(public_key, rsa.RSAPublicKey):
        return public_key.encrypt(file_key, rsa_oaep)

    # X25519:
    # 1. Make a throwaway key pair, used only for this file and then forgotten
    throwaway_key = x25519.X25519PrivateKey.generate()
    # Raw = just the 32 bytes of the key, without the PEM / DER structure around it
    raw = serialization.Encoding.Raw
    raw_format = serialization.PublicFormat.Raw
    throwaway_public = throwaway_key.public_key().public_bytes(raw, raw_format)
    recipient_public = public_key.public_bytes(raw, raw_format)

    # 2. Shared secret between the throwaway private key and the recipient's public key
    # The recipient gets the same secret later with their private key + the throwaway
    # public key, which is saved at the start of key.enc
    shared_secret = throwaway_key.exchange(public_key)

    # 3. HKDF → wrap key, then AES-GCM encrypts the file key with it
    wrap_key = x25519_wrap_key(shared_secret, throwaway_public, recipient_public)
    nonce = os.urandom(12)
    locked_key = AESGCM(wrap_key).encrypt(nonce, file_key, None)

    return throwaway_public + nonce + locked_key


# This func unlocks key.enc with the private key and gives the file key back (spec 5.3 step 5)
# The opposite of lock_file_key. It raises DecryptionError if key.enc was damaged or changed
def unlock_file_key(key_enc: bytes, private_key) -> bytes:

    # RSA: the private key decrypts it directly. A ValueError means it didn't work
    if isinstance(private_key, rsa.RSAPrivateKey):
        try:
            return private_key.decrypt(key_enc, rsa_oaep)
        except ValueError as error:
            raise DecryptionError("key.enc can't be opened with this key.") from error

    # X25519:
    # 1. Split key.enc into its 3 parts
    # key_enc[:32] = the first 32 bytes, key_enc[32:44] = the next 12, key_enc[44:] = the rest
    # The locked file key is 16 or 32 bytes + the 16 bytes tag, so at least 32 bytes
    if len(key_enc) < 32 + 12 + 16 + tag_size:
        raise DecryptionError("key.enc is too short.")
    throwaway_public = key_enc[:32]
    nonce = key_enc[32:44]
    locked_key = key_enc[44:]

    # 2. Same shared secret as when it was locked, but from the other side
    raw = serialization.Encoding.Raw
    raw_format = serialization.PublicFormat.Raw
    recipient_public = private_key.public_key().public_bytes(raw, raw_format)
    try:
        throwaway_key = x25519.X25519PublicKey.from_public_bytes(throwaway_public)
        shared_secret = private_key.exchange(throwaway_key)
    except ValueError as error:
        raise DecryptionError("Invalid throwaway key in key.enc.") from error
    # A crafted throwaway key can force a secret made only of zeros, which is never valid
    # bytes(32) is 32 bytes all set to 0
    if shared_secret == bytes(32):
        raise DecryptionError("Invalid throwaway key in key.enc.")

    # 3. HKDF → wrap key, then AES-GCM decrypts the file key (and checks its tag)
    wrap_key = x25519_wrap_key(shared_secret, throwaway_public, recipient_public)
    try:
        return AESGCM(wrap_key).decrypt(nonce, locked_key, None)
    except InvalidTag as error:
        raise DecryptionError("key.enc was changed or is not for this key.") from error


# This func encrypts a file into a package for a recipient (spec 5.2, steps 1 to 4)
# - src_path: the file to encrypt (for a folder, the zip made by core/folders.py)
# - package_path: where to write the package, e.g. Desktop/crypteasy_2026-11-14_1432.zip
# - public_key: the recipient's encryption public key (X25519 or RSA, from keys.py)
# - cipher: "aes-256-gcm" or "aes-128-gcm"
# - is_folder: True if src_path is a zipped folder, it's written in the header
# - original_name: the name the recipient gets back. None = the name of src_path. For a
#   folder it's e.g. "holidays.zip", bcs the temp zip on the disk has another name
# - progress: a func called after each chunk with (bytes done, bytes in total), for the
#   progress bar. None = no progress bar
# The package is written to a temp file first, and only renamed at the very end, so if
# something goes wrong there is never half a package left on the disk
def encrypt_file(
    src_path,
    package_path,
    public_key,
    cipher="aes-256-gcm",
    is_folder=False,
    original_name=None,
    progress=None,
):
    src_path = Path(src_path)
    package_path = Path(package_path)

    # 1. Check everything first
    # The recipient's key must be a PUBLIC key we can encrypt with (not Ed25519 or RSA-1024)
    key_type = keys.get_key_type(public_key)
    if key_type is None or not isinstance(public_key, (x25519.X25519PublicKey, rsa.RSAPublicKey)):
        raise InvalidKeyError("The recipient's key can't be used to encrypt.")
    if cipher not in package.ciphers:
        raise ValueError(f"Invalid cipher! Use one of: {', '.join(package.ciphers)}")
    # Never overwrite a file (spec section 8)
    if package_path.exists():
        raise FileExistsError(f"{package_path.name} already exists.")
    if original_name is None:
        original_name = src_path.name
    name_bytes = original_name.encode("utf-8")
    if len(name_bytes) > name_chunk_size - 2:
        raise ValueError("The file name is too long.")

    # 2. Make a brand new random file key (spec 5.2 step 1)
    # package.ciphers[cipher] gives its size: 32 bytes for AES-256, 16 for AES-128
    # os.urandom gives secure random bytes from the OS
    file_key = os.urandom(package.ciphers[cipher])
    aes = AESGCM(file_key)

    # 3. The header, and key.enc (spec 5.2 step 3)
    fingerprint = keys.get_fingerprint(public_key)
    header_bytes = package.make_header(key_type, fingerprint, cipher, is_folder)
    key_enc = lock_file_key(file_key, public_key)

    # 4. Write the package into a temp file next to the final one
    # os.urandom(4).hex() gives 8 random hex characters, so 2 temp files never get the same name
    temp_path = package_path.with_name(f"{temp_prefix}{os.urandom(4).hex()}.part")
    total = src_path.stat().st_size  # the size of the file in bytes
    done = 0
    finished = False

    # try / finally: the code in "finally" always runs at the end, even if there was an error,
    # so the temp file is always deleted if the package wasn't finished
    try:
        # "x" creates the file, and fails if it already exists (never overwrite)
        # ZIP_STORED = no compression, the zip is only a bag for the 2 files
        with zipfile.ZipFile(temp_path, "x", compression=zipfile.ZIP_STORED) as zf:
            zf.writestr("key.enc", key_enc)

            # zf.open(..., "w") gives a file inside the zip that I can write to bit by bit,
            # so the encrypted file never has to be fully in the RAM
            # force_zip64=True allows files over 4 GB inside the zip
            with zf.open("file.enc", "w", force_zip64=True) as out:
                with open(src_path, "rb") as fin:
                    # 4.1 The header, in clear
                    out.write(header_bytes)

                    # 4.2 Chunk 0: the original name, so it's hidden (spec 5.2 step 2)
                    # 2 bytes with the length of the name, the name, then zeros up to
                    # name_chunk_size. bytes(n) gives n bytes all set to 0
                    name_chunk = len(name_bytes).to_bytes(2, "big") + name_bytes
                    name_chunk = name_chunk + bytes(name_chunk_size - len(name_chunk))
                    # .encrypt(nonce, data, header) gives the encrypted data + the 16 bytes tag
                    # The 3rd value is checked by the tag but not encrypted (it's in clear
                    # above): that's how the header is protected in every chunk
                    out.write(aes.encrypt(make_nonce(0, False), name_chunk, header_bytes))

                    # 4.3 The file itself, 64 KiB at a time
                    # To know if a chunk is the last one, I read the NEXT chunk before
                    # encrypting the current one: if the next one is empty, the current one
                    # is the last. An empty file still gives 1 chunk (empty, but with a tag)
                    chunk_number = 1
                    chunk = fin.read(package.chunk_size)
                    while True:
                        next_chunk = fin.read(package.chunk_size)
                        is_last = next_chunk == b""

                        nonce = make_nonce(chunk_number, is_last)
                        out.write(aes.encrypt(nonce, chunk, header_bytes))

                        done += len(chunk)
                        if progress is not None:
                            progress(done, total)

                        if is_last:
                            break
                        chunk = next_chunk
                        chunk_number += 1

        # 5. Everything worked: give the temp file its real name
        # Checked again, in case a file with that name appeared in the meantime
        if package_path.exists():
            raise FileExistsError(f"{package_path.name} already exists.")
        os.rename(temp_path, package_path)
        finished = True

    finally:
        if not finished:
            # missing_ok=True: no error if the temp file was never created
            temp_path.unlink(missing_ok=True)


# This func decrypts a package with a private key (spec 5.3, steps 1 to 7)
# - package_path: the package (its name doesn't matter, only what's inside)
# - private_key: the recipient's encryption private key, already unlocked by keystore/
# - out_dir: the folder where the decrypted file goes
# - progress: same as for encrypt_file
# It returns the path of the decrypted file, e.g. Desktop/holidays.zip
# It raises UnsupportedFormatError (not a package / newer version), NoMatchingKeyError
# (not for this key) or DecryptionError (damaged or changed: then nothing is written)
def decrypt_package(package_path, private_key, out_dir, progress=None) -> Path:
    out_dir = Path(out_dir)

    # 1. The key must be a PRIVATE key we can decrypt with
    if keys.get_key_type(private_key) is None or not isinstance(
        private_key, (x25519.X25519PrivateKey, rsa.RSAPrivateKey)
    ):
        raise InvalidPrivateKeyError("This key can't be used to decrypt.")

    out_dir.mkdir(parents=True, exist_ok=True)
    # The decrypted data goes into this temp file first, and gets its real name only once
    # every chunk was checked (spec 5.3 steps 6 and 7)
    temp_path = out_dir / f"{temp_prefix}{os.urandom(4).hex()}.part"
    finished = False

    try:
        # 2. Open the package and check what's inside (package.py)
        with package.open_package(package_path) as zf:
            key_enc = zf.read("key.enc")
            total = zf.getinfo("file.enc").file_size

            with zf.open("file.enc") as fin:
                # 3. Read and check the header
                header_bytes, header = package.read_header(fin)

                # 4. Is it for this key? (spec 5.3 step 3)
                my_fingerprint = keys.get_fingerprint(private_key.public_key())
                if header["recipient_fingerprint"] != my_fingerprint:
                    raise NoMatchingKeyError("This package was not encrypted for this key.")

                # 5. Unlock key.enc → the file key (spec 5.3 step 5)
                # It must have the size the header says (32 bytes for AES-256, 16 for AES-128)
                file_key = unlock_file_key(key_enc, private_key)
                if len(file_key) != package.ciphers[header["cipher"]]:
                    raise DecryptionError("The file key doesn't match the cipher.")
                aes = AESGCM(file_key)

                # 6. Chunk 0: the original name
                name_chunk = fin.read(name_chunk_size + tag_size)
                try:
                    name_chunk = aes.decrypt(make_nonce(0, False), name_chunk, header_bytes)
                except InvalidTag as error:
                    raise DecryptionError("The package is damaged or was changed.") from error
                name_length = int.from_bytes(name_chunk[:2], "big")
                if name_length > name_chunk_size - 2:
                    raise DecryptionError("Invalid file name length.")
                # .decode turns the bytes back into text. If it's not valid UTF-8 the name
                # is just not usable, so it's left empty and safe_filename uses the fallback
                try:
                    original_name = name_chunk[2 : 2 + name_length].decode("utf-8")
                except UnicodeDecodeError:
                    original_name = ""

                # 7. The file itself, chunk by chunk, into the temp file (spec 5.3 step 6)
                # Each encrypted chunk is the chunk size + the 16 bytes tag, the last one can
                # be shorter. Same trick as encrypt_file: read the next chunk to know if the
                # current one is the last one
                # "xb" = create the file in binary, and fail if it already exists
                encrypted_chunk_size = header["chunk_size"] + tag_size
                with open(temp_path, "xb") as fout:
                    chunk_number = 1
                    chunk = fin.read(encrypted_chunk_size)
                    # the header and chunk 0 are already read, they count in the progress too
                    done = len(header_bytes) + name_chunk_size + tag_size
                    while True:
                        # No room for a tag = the end of the file is missing
                        if len(chunk) < tag_size:
                            raise DecryptionError("The package is cut.")
                        next_chunk = fin.read(encrypted_chunk_size)
                        is_last = next_chunk == b""

                        # .decrypt checks the tag first: if anything was changed (the chunk,
                        # its position, the header, the end of the file) it raises InvalidTag
                        nonce = make_nonce(chunk_number, is_last)
                        try:
                            fout.write(aes.decrypt(nonce, chunk, header_bytes))
                        except InvalidTag as error:
                            raise DecryptionError(
                                "The package is damaged or was changed."
                            ) from error

                        done += len(chunk)
                        if progress is not None:
                            progress(done, total)

                        if is_last:
                            break
                        chunk = next_chunk
                        chunk_number += 1

        # 8. Every chunk was checked: give the file its real name (spec 5.3 step 7)
        # safe_filename cleans the name (e.g. "../../evil.exe" gives "evil.exe") and
        # free_path picks "name (2).ext" if the name is already taken, never overwrite
        final_path = package.free_path(out_dir, package.safe_filename(original_name))
        os.rename(temp_path, final_path)
        finished = True
        return final_path

    # zipfile raises BadZipFile if the zip itself is damaged while reading
    # (e.g. its own checksum of file.enc doesn't match)
    except zipfile.BadZipFile as error:
        raise DecryptionError("The zip is damaged.") from error

    finally:
        # Something went wrong: delete what was decrypted so far, nothing is given to the user
        if not finished:
            temp_path.unlink(missing_ok=True)
