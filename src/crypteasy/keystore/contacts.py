"""Contacts book: other people's public keys (TECHNICAL_SPEC F3 and section 6.1).

contacts.json:
    {"version": 1, "contacts": [{"name": ..., "public_pem": ..., "fingerprint": ...,
                                 "added": "2026-11-10T14:32:00+00:00"}, ...]}

The file is treated as untrusted: on every load each key is parsed again and its
fingerprint recomputed. A mismatch (e.g. the file was edited by hand) raises
CorruptedStoreError instead of silently trusting the stored fingerprint.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime

from . import _core, paths
from .common import atomic_write, clean_name, parse_json, read_limited
from .errors import (
    AlreadyExistsError,
    CorruptedStoreError,
    InvalidNameError,
    InvalidPublicKeyError,
    NotFoundError,
)

VERSION = 1
MAX_PEM_BYTES = 16 * 1024  # RSA-4096 + Ed25519 public PEMs are ~1 KiB
MAX_FILE_BYTES = 8 * 1024 * 1024

_store_lock = threading.Lock()  # the Flask server is multi-threaded


@dataclass(frozen=True)
class Contact:
    name: str
    key_type: str  # "x25519", "rsa-3072", ...
    fingerprint: str
    public_pem: bytes
    added: str  # ISO 8601, UTC


def _check_pem(public_pem: bytes) -> tuple[str, str]:
    """Size and ASCII check before handing the PEM to core/. Returns (key_type, fingerprint)."""
    if len(public_pem) > MAX_PEM_BYTES or not public_pem.isascii():
        raise InvalidPublicKeyError()
    return _core.inspect_public_pem(public_pem)


def _load() -> list[Contact]:
    try:
        data = parse_json(read_limited(paths.contacts_file(), MAX_FILE_BYTES))
        if not isinstance(data, dict) or data.get("version") != VERSION:
            raise ValueError("unknown contacts.json version")
        entries = data["contacts"]
        if not isinstance(entries, list):
            raise ValueError("contacts is not a list")
        contacts = [_parse_entry(e) for e in entries]
    except FileNotFoundError:
        return []
    except (ValueError, KeyError, TypeError, InvalidNameError, InvalidPublicKeyError) as exc:
        raise CorruptedStoreError("contacts.json is damaged or was edited by hand") from exc
    if len({c.fingerprint for c in contacts}) != len(contacts):
        raise CorruptedStoreError("contacts.json has the same key twice")
    return contacts


def _parse_entry(entry: object) -> Contact:
    if not isinstance(entry, dict):
        raise ValueError("contact is not an object")
    name, pem, stored_fpr, added = (
        entry["name"], entry["public_pem"], entry["fingerprint"], entry["added"],
    )  # fmt: skip
    if not all(isinstance(v, str) for v in (name, pem, stored_fpr, added)):
        raise ValueError("contact field is not a string")
    if clean_name(name) != name:
        raise ValueError("contact name is not clean")
    pem_bytes = pem.encode("ascii")  # UnicodeEncodeError is a ValueError
    key_type, fingerprint = _check_pem(pem_bytes)
    if fingerprint != stored_fpr:
        raise ValueError("stored fingerprint doesn't match the key")
    return Contact(name, key_type, fingerprint, pem_bytes, added)


def _save(contacts: list[Contact]) -> None:
    data = {
        "version": VERSION,
        "contacts": [
            {
                "name": c.name,
                "public_pem": c.public_pem.decode("ascii"),
                "fingerprint": c.fingerprint,
                "added": c.added,
            }
            for c in contacts
        ],
    }
    atomic_write(paths.contacts_file(), json.dumps(data, indent=2).encode())


def list_contacts() -> list[Contact]:
    """All contacts, sorted by name. Raises CorruptedStoreError if contacts.json was tampered."""
    with _store_lock:
        contacts = _load()
    return sorted(contacts, key=lambda c: c.name.casefold())


def get_contact(fingerprint: str) -> Contact:
    with _store_lock:
        contacts = _load()
    for contact in contacts:
        if contact.fingerprint == fingerprint:
            return contact
    raise NotFoundError()


def add_contact(name: str, public_pem: bytes) -> Contact:
    """Validate the key, then save it. Raises InvalidNameError, InvalidPublicKeyError,
    AlreadyExistsError (same key already saved, possibly under another name)."""
    name = clean_name(name)
    key_type, fingerprint = _check_pem(public_pem)
    with _store_lock:
        contacts = _load()
        if any(c.fingerprint == fingerprint for c in contacts):
            raise AlreadyExistsError()
        added = datetime.now(UTC).isoformat(timespec="seconds")
        contact = Contact(name, key_type, fingerprint, public_pem, added)
        _save([*contacts, contact])
    return contact


def rename_contact(fingerprint: str, new_name: str) -> Contact:
    new_name = clean_name(new_name)
    with _store_lock:
        contacts = _load()
        for i, c in enumerate(contacts):
            if c.fingerprint == fingerprint:
                contacts[i] = Contact(new_name, c.key_type, c.fingerprint, c.public_pem, c.added)
                _save(contacts)
                return contacts[i]
    raise NotFoundError()


def remove_contact(fingerprint: str) -> None:
    with _store_lock:
        contacts = _load()
        kept = [c for c in contacts if c.fingerprint != fingerprint]
        if len(kept) == len(contacts):
            raise NotFoundError()
        _save(kept)
