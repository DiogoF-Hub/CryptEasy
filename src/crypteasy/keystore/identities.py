"""My key pairs (TECHNICAL_SPEC F1, F2, sections 6.1 and 6.2).

    keys/<id>/private.key   both private keys, locked with the key passphrase (format below)
    keys/<id>/public.pem    both public keys, the file the user shares
    keys/<id>/info.json     {"version": 1, "name", "key_type", "level", "created", "fingerprint"}

<id> is random (not derived from the name or the key), so no user input ever ends up in a
path. Key pairs are looked up by fingerprint. A key pair is written into a hidden
".tmp-<id>" folder and renamed into place, so a crash never leaves half a key pair.

private.key (section 6.2):
    {"format": "crypteasy-private-key", "version": 1, "kdf": "argon2id" | "pbkdf2-sha256",
     "salt": b64, "params": {...}, "nonce": b64, "ciphertext": b64}
    or, with no passphrase:
    {"format": "crypteasy-private-key", "version": 1, "kdf": "none", "plaintext": b64}

lock_key = KDF(passphrase, salt, params); ciphertext = AES-256-GCM(lock_key, nonce, secret).
A private.key file may come from outside (import), so its parameters are bounded BEFORE
any KDF runs: a crafted file must not make the app allocate gigabytes or spin for hours.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import shutil
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import _core, paths
from .common import (
    ARGON2_MAX_ITERATIONS,
    ARGON2_MAX_MEMORY_KIB,
    ARGON2_MAX_PARALLELISM,
    PBKDF2_MAX_ITERATIONS,
    atomic_write,
    clean_name,
    parse_json,
    read_limited,
    write_new,
)
from .errors import (
    AlreadyExistsError,
    CorruptedStoreError,
    InvalidNameError,
    InvalidPrivateKeyError,
    InvalidPublicKeyError,
    InvalidSettingError,
    NotFoundError,
    WrongPassphraseError,
)

FORMAT = "crypteasy-private-key"
VERSION = 1
KEY_TYPES = ("x25519", "rsa-2048", "rsa-3072", "rsa-4096")
KDFS = ("argon2id", "pbkdf2-sha256")
SALT_LENS = (0, 16, 32)  # 0 = no salt, PBKDF2 only
LEVELS = ("very_strong", "strong", "medium", "weak", "none", "custom")
NONCE_LEN = 12


MAX_PRIVATE_KEY_BYTES = 64 * 1024  # RSA-4096 + Ed25519 PKCS#8, base64 + JSON: ~4 KiB
MAX_PUBLIC_PEM_BYTES = 16 * 1024
MAX_INFO_BYTES = 16 * 1024

_store_lock = threading.Lock()  # the Flask server is multi-threaded


@dataclass(frozen=True)
class Protection:
    """How to lock a private key on disk (sections 4.1 and 6.2)."""

    passphrase: bytes | None = field(repr=False)  # None = no passphrase (kdf "none")
    kdf: str = "argon2id"
    kdf_strength: str = "normal"
    salt_len: int = 16
    level: str = "strong"  # computed by the UI (section 4.2), kept in info.json


@dataclass(frozen=True)
class Identity:
    name: str
    key_type: str
    fingerprint: str
    level: str
    protected: bool  # False = private key saved without a passphrase
    created: str  # ISO 8601, UTC


# --------------------------------------------------------------------- private.key


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(value: object) -> bytes:
    if not isinstance(value, str):
        raise ValueError("expected a base64 string")
    return base64.b64decode(value, validate=True)  # binascii.Error is a ValueError


def _is_int(value: object, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high  # type() so that True isn't 1


def _check_params(kdf: str, salt_len: int, params: object) -> None:
    """Raise ValueError unless the KDF settings are known and within bounds."""
    if not isinstance(params, dict):
        raise ValueError("params is not an object")
    if kdf == "argon2id":
        if salt_len not in (16, 32) or set(params) != {"memory_kib", "iterations", "parallelism"}:
            raise ValueError("bad argon2id settings")
        lanes = params["parallelism"]
        if not (
            _is_int(lanes, 1, ARGON2_MAX_PARALLELISM)
            and _is_int(params["iterations"], 1, ARGON2_MAX_ITERATIONS)
            and _is_int(params["memory_kib"], 8 * lanes, ARGON2_MAX_MEMORY_KIB)
        ):
            raise ValueError("argon2id params out of bounds")
    elif kdf == "pbkdf2-sha256":
        if salt_len not in SALT_LENS or set(params) != {"iterations"}:
            raise ValueError("bad pbkdf2 settings")
        if not _is_int(params["iterations"], 1, PBKDF2_MAX_ITERATIONS):
            raise ValueError("pbkdf2 iterations out of bounds")
    else:
        raise ValueError("unknown kdf")


def _parse_private_key(data: bytes) -> dict:
    """Validate a private.key file (untrusted). Returns its fields with bytes decoded.

    Raises InvalidPrivateKeyError: not our format, unknown version, or unsafe parameters.
    """
    try:
        if len(data) > MAX_PRIVATE_KEY_BYTES:
            raise ValueError("too large")
        d = parse_json(data)
        if not isinstance(d, dict) or d.get("format") != FORMAT or d.get("version") != VERSION:
            raise ValueError("not a CryptEasy private key, or an unknown version")
        if d.get("kdf") == "none":
            if set(d) != {"format", "version", "kdf", "plaintext"}:
                raise ValueError("unexpected fields")
            return {"kdf": "none", "plaintext": _unb64(d["plaintext"])}
        if set(d) != {"format", "version", "kdf", "salt", "params", "nonce", "ciphertext"}:
            raise ValueError("unexpected fields")
        salt, nonce, ciphertext = _unb64(d["salt"]), _unb64(d["nonce"]), _unb64(d["ciphertext"])
        _check_params(d["kdf"], len(salt), d["params"])
        if len(nonce) != NONCE_LEN or len(ciphertext) <= 16:  # 16 = GCM tag
            raise ValueError("bad nonce or ciphertext")
    except (ValueError, TypeError) as exc:  # incl. JSONDecodeError, UnicodeDecodeError
        raise InvalidPrivateKeyError() from exc
    return {"kdf": d["kdf"], "salt": salt, "params": d["params"], "nonce": nonce, "ct": ciphertext}


def seal_secret(secret: bytes, protection: Protection) -> bytes:
    """Build the private.key file for `secret` (the private keys, opaque bytes)."""
    if protection.passphrase is None:
        doc = {"format": FORMAT, "version": VERSION, "kdf": "none", "plaintext": _b64(secret)}
        return json.dumps(doc, indent=2).encode()
    if protection.passphrase == b"" or protection.kdf not in KDFS:
        raise InvalidSettingError()
    params = _core.kdf_params(protection.kdf, protection.kdf_strength)
    try:
        _check_params(protection.kdf, protection.salt_len, params)
    except ValueError as exc:  # e.g. argon2id without salt
        raise InvalidSettingError() from exc
    salt = os.urandom(protection.salt_len)
    lock_key = _core.derive_lock_key(protection.kdf, protection.passphrase, salt, params)
    nonce = os.urandom(NONCE_LEN)
    doc = {
        "format": FORMAT,
        "version": VERSION,
        "kdf": protection.kdf,
        "salt": _b64(salt),
        "params": params,
        "nonce": _b64(nonce),
        "ciphertext": _b64(AESGCM(lock_key).encrypt(nonce, secret, None)),
    }
    return json.dumps(doc, indent=2).encode()


def open_secret(data: bytes, passphrase: bytes | None) -> bytes:
    """Unlock a private.key file. Raises InvalidPrivateKeyError, WrongPassphraseError.

    A key saved without a passphrase opens whatever passphrase is given.
    """
    d = _parse_private_key(data)
    if d["kdf"] == "none":
        return d["plaintext"]
    if not passphrase:
        raise WrongPassphraseError()
    lock_key = _core.derive_lock_key(d["kdf"], passphrase, d["salt"], d["params"])
    try:
        return AESGCM(lock_key).decrypt(d["nonce"], d["ct"], None)
    except InvalidTag as exc:  # wrong passphrase, or the file was modified
        raise WrongPassphraseError() from exc


# --------------------------------------------------------------------- key folders


def _check_level(protection: Protection) -> None:
    """The level must be known, and "none" exactly when there is no passphrase."""
    if protection.level not in LEVELS:
        raise InvalidSettingError()
    if (protection.passphrase is None) != (protection.level == "none"):
        raise InvalidSettingError()


def _load(folder: Path) -> Identity:
    """Read one key folder. Raises CorruptedStoreError if any of its files is damaged or
    if info.json doesn't match public.pem (e.g. edited by hand)."""
    try:
        info = parse_json(read_limited(folder / "info.json", MAX_INFO_BYTES))
        if not isinstance(info, dict) or info.get("version") != VERSION:
            raise ValueError("unknown info.json version")
        name, key_type, level, created, fpr = (
            info["name"], info["key_type"], info["level"], info["created"], info["fingerprint"],
        )  # fmt: skip
        if not all(isinstance(v, str) for v in (name, key_type, level, created, fpr)):
            raise ValueError("info.json field is not a string")
        if clean_name(name) != name or level not in LEVELS:
            raise ValueError("bad name or level")
        pem = read_limited(folder / "public.pem", MAX_PUBLIC_PEM_BYTES)
        if (key_type, fpr) != _core.inspect_public_pem(pem):
            raise ValueError("info.json doesn't match public.pem")
        private = _parse_private_key(read_limited(folder / "private.key", MAX_PRIVATE_KEY_BYTES))
    except (
        OSError,
        ValueError,
        KeyError,
        InvalidNameError,
        InvalidPublicKeyError,
        InvalidPrivateKeyError,
    ) as exc:
        raise CorruptedStoreError(f"key folder {folder.name} is damaged") from exc
    # private.key is the truth about protection; info.json's level is only what the UI
    # chose. If they disagree (hand edit, or a crash inside change_protection), never show
    # an unprotected key as protected.
    protected = private["kdf"] != "none"
    if not protected:
        level = "none"
    elif level == "none":
        level = "custom"
    return Identity(name, key_type, fpr, level, protected, created)


def _scan() -> tuple[list[tuple[Path, Identity]], list[str]]:
    """(healthy key folders, names of damaged ones). Hidden folders (.tmp-, .deleted-)
    are skipped. A damaged folder never hides or blocks the healthy ones."""
    healthy, damaged = [], []
    for folder in sorted(paths.keys_dir().iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        try:
            healthy.append((folder, _load(folder)))
        except CorruptedStoreError:
            damaged.append(folder.name)
    return healthy, damaged


def _find(fingerprint: str) -> tuple[Path, Identity]:
    for folder, ident in _scan()[0]:
        if ident.fingerprint == fingerprint:
            return folder, ident
    raise NotFoundError()


def _info_json(ident: Identity) -> bytes:
    info = {
        "version": VERSION,
        "name": ident.name,
        "key_type": ident.key_type,
        "level": ident.level,
        "created": ident.created,
        "fingerprint": ident.fingerprint,
    }
    return json.dumps(info, indent=2).encode()


def _check_name_free(name: str, except_fingerprint: str | None = None) -> None:
    for _folder, ident in _scan()[0]:
        if ident.name == name and ident.fingerprint != except_fingerprint:
            raise AlreadyExistsError()


def _remove(folder: Path) -> None:
    """Hide the folder first (atomic), then delete it. If the delete fails (e.g. a file
    held open by an antivirus on Windows), _sweep_leftovers retries on the next write."""
    trash = folder.with_name(f".deleted-{folder.name}")
    os.rename(folder, trash)
    shutil.rmtree(trash, ignore_errors=True)


def _sweep_leftovers() -> None:
    """Delete .tmp- / .deleted- folders left by a crash or a failed delete: they may hold a
    private.key (in clear for a "no passphrase" key). Called under _store_lock, so no
    create is in progress."""
    for folder in paths.keys_dir().iterdir():
        if folder.name.startswith((".tmp-", ".deleted-")):
            shutil.rmtree(folder, ignore_errors=True)


# --------------------------------------------------------------------- public API


def list_identities() -> list[Identity]:
    """My key pairs, sorted by name. Damaged ones are listed by damaged_identities()."""
    with _store_lock:
        healthy, _damaged = _scan()
    return sorted((ident for _f, ident in healthy), key=lambda i: i.name.casefold())


def damaged_identities() -> list[str]:
    """Ids of key folders that can't be read (damaged or edited by hand), so the UI can
    tell the user and offer to delete them with delete_damaged_identity()."""
    with _store_lock:
        return _scan()[1]


def get_identity(fingerprint: str) -> Identity:
    with _store_lock:
        return _find(fingerprint)[1]


def create_identity(name: str, key_type: str, protection: Protection) -> Identity:
    """Generate a key pair and save it. Raises InvalidNameError, InvalidSettingError,
    AlreadyExistsError (name taken). The passphrase policy (length, blocklist) is checked
    by the caller."""
    name = clean_name(name)
    if key_type not in KEY_TYPES:
        raise InvalidSettingError()
    _check_level(protection)
    with _store_lock:
        _sweep_leftovers()
        _check_name_free(name)
        secret, public_pem, fingerprint = _core.generate(key_type)
        return _save_new(name, key_type, fingerprint, public_pem, secret, protection)


def import_private_key(
    name: str, key_file: Path, current_passphrase: bytes | None, protection: Protection
) -> Identity:
    """Import a private key and re-lock it with `protection` (spec F2).

    `key_file` is a private.key exported by CryptEasy, or a PEM private key made elsewhere
    (e.g. OpenSSL), encrypted or not; `current_passphrase` unlocks it. A PEM without an
    Ed25519 signing key gets a new one. Raises InvalidPrivateKeyError, WrongPassphraseError,
    InvalidNameError, InvalidSettingError, AlreadyExistsError (name taken, or this key is
    already one of mine).
    """
    name = clean_name(name)
    _check_level(protection)
    try:
        data = read_limited(key_file, MAX_PRIVATE_KEY_BYTES)
    except ValueError as exc:  # too large to be a key
        raise InvalidPrivateKeyError() from exc
    if data.lstrip().startswith(b"{"):  # CryptEasy private.key (JSON); a PEM starts with "-----"
        pem, password = open_secret(data, current_passphrase), None
    else:
        pem, password = data, current_passphrase
    secret, public_pem, key_type, fingerprint = _core.load_private_pem(pem, password)
    with _store_lock:
        _sweep_leftovers()
        _check_name_free(name)
        if any(ident.fingerprint == fingerprint for _f, ident in _scan()[0]):
            raise AlreadyExistsError()
        return _save_new(name, key_type, fingerprint, public_pem, secret, protection)


def _save_new(
    name: str, key_type: str, fingerprint: str, public_pem: bytes, secret: bytes,
    protection: Protection,
) -> Identity:  # fmt: skip
    """Lock `secret` and write a new key folder. Called under _store_lock."""
    private_key = seal_secret(secret, protection)
    created = datetime.now(UTC).isoformat(timespec="seconds")
    ident = Identity(
        name, key_type, fingerprint, protection.level, protection.passphrase is not None,
        created,
    )  # fmt: skip
    keys = paths.keys_dir()
    key_id = secrets.token_hex(8)
    tmp = keys / f".tmp-{key_id}"
    tmp.mkdir(mode=0o700)
    try:
        write_new(tmp / "private.key", private_key)
        write_new(tmp / "public.pem", public_pem)
        write_new(tmp / "info.json", _info_json(ident))
        os.rename(tmp, keys / key_id)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return ident


def unlock(fingerprint: str, passphrase: bytes | None) -> bytes:
    """Return the private keys (opaque bytes for core/). Raises NotFoundError,
    WrongPassphraseError, CorruptedStoreError."""
    with _store_lock:
        folder, _ident = _find(fingerprint)
        private_key = read_limited(folder / "private.key", MAX_PRIVATE_KEY_BYTES)
    # The KDF (up to a few seconds) runs outside the lock
    return open_secret(private_key, passphrase)


def change_protection(
    fingerprint: str, current_passphrase: bytes | None, protection: Protection
) -> Identity:
    """Re-lock the private key with new settings. Raises NotFoundError, WrongPassphraseError,
    InvalidSettingError."""
    _check_level(protection)
    with _store_lock:
        folder, ident = _find(fingerprint)
        private_key = read_limited(folder / "private.key", MAX_PRIVATE_KEY_BYTES)
        secret = open_secret(private_key, current_passphrase)
        new_private_key = seal_secret(secret, protection)
        updated = Identity(
            ident.name, ident.key_type, ident.fingerprint, protection.level,
            protection.passphrase is not None, ident.created,
        )  # fmt: skip
        # Two separate atomic writes: a crash in between is handled by _load, which takes
        # the protection from private.key, never from info.json.
        atomic_write(folder / "private.key", new_private_key)
        atomic_write(folder / "info.json", _info_json(updated))
    return updated


def rename_identity(fingerprint: str, new_name: str) -> Identity:
    new_name = clean_name(new_name)
    with _store_lock:
        folder, ident = _find(fingerprint)
        _check_name_free(new_name, except_fingerprint=fingerprint)
        updated = Identity(
            new_name, ident.key_type, ident.fingerprint, ident.level, ident.protected,
            ident.created,
        )  # fmt: skip
        atomic_write(folder / "info.json", _info_json(updated))
    return updated


def delete_identity(fingerprint: str) -> None:
    with _store_lock:
        _sweep_leftovers()
        _remove(_find(fingerprint)[0])


def delete_damaged_identity(key_id: str) -> None:
    """Delete a folder listed by damaged_identities(). `key_id` must be one of those names,
    so it can't point anywhere else."""
    with _store_lock:
        _sweep_leftovers()
        if key_id not in _scan()[1]:
            raise NotFoundError()
        _remove(paths.keys_dir() / key_id)


def public_pem(fingerprint: str) -> bytes:
    with _store_lock:
        folder, _ident = _find(fingerprint)
        return read_limited(folder / "public.pem", MAX_PUBLIC_PEM_BYTES)


def export_public_key(fingerprint: str, dst: Path) -> None:
    """Write public.pem to dst. Never overwrites (FileExistsError)."""
    write_new(dst, public_pem(fingerprint))


def export_private_key(fingerprint: str, dst: Path) -> None:
    """Copy private.key to dst, still locked. Never overwrites (FileExistsError)."""
    with _store_lock:
        folder, _ident = _find(fingerprint)
        private_key = read_limited(folder / "private.key", MAX_PRIVATE_KEY_BYTES)
    write_new(dst, private_key)
