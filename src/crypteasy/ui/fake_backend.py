"""FakeBackend : backend factice pour les tests et le développement avant S7.

AUCUNE SÉCURITÉ : le contenu des fichiers n'est PAS chiffré. Il imite seulement le
comportement du vrai moteur (blocs, empreinte du destinataire dans l'en-tête,
détection de modification, nom d'origine stocké dans le fichier) pour que tous
les cas d'erreur de l'interface puissent être testés.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
from pathlib import Path

from . import errors
from .backend import KEY_TYPES, KeyView

_PEM_HEAD = b"-----BEGIN CRYPTEASY DEMO PUBLIC KEY-----\n"
_PEM_TAIL = b"\n-----END CRYPTEASY DEMO PUBLIC KEY-----\n"
_MAGIC = b"CEZDEMO\x00"
_VERSION = 1
_CHUNK = 64 * 1024
_KIND_LABEL = {"x25519": "X25519", "rsa-2048": "RSA-2048", "rsa-3072": "RSA-3072",
               "rsa-4096": "RSA-4096"}
_BLOCKLIST = {"motdepasse", "motdepasse123", "password", "azertyuiop", "123456789"}


def _fingerprint(key_id: bytes) -> str:
    h = hashlib.sha256(key_id).hexdigest().upper()
    return " ".join(h[i:i + 4] for i in range(0, len(h), 4))


def _public_pem(key_id: bytes, kind: str) -> bytes:
    payload = json.dumps({"id": key_id.hex(), "kind": kind}).encode()
    return _PEM_HEAD + base64.b64encode(payload) + _PEM_TAIL


def _parse_public_pem(pem: bytes) -> tuple[bytes, str]:
    pem = pem.strip() + b"\n"
    if not (pem.startswith(_PEM_HEAD) and pem.endswith(_PEM_TAIL)):
        raise errors.InvalidKey()
    try:
        data = json.loads(base64.b64decode(pem[len(_PEM_HEAD):-len(_PEM_TAIL)], validate=True))
        return bytes.fromhex(data["id"]), data["kind"]
    except (ValueError, KeyError, TypeError) as exc:
        raise errors.InvalidKey() from exc


class FakeBackend:
    demo = True
    min_password_length = 15

    def __init__(self) -> None:
        # empreinte → (nom, type, id, sel, hash du mot de passe)
        self._identities: dict[str, tuple[str, str, bytes, bytes, bytes]] = {}
        # empreinte → (nom, type, pem)
        self._contacts: dict[str, tuple[str, str, bytes]] = {}

    # ---------------------------------------------------------------- clés
    def list_identities(self) -> list[KeyView]:
        return sorted((KeyView(n, _KIND_LABEL[k], fpr)
                       for fpr, (n, k, *_r) in self._identities.items()),
                      key=lambda v: v.name.lower())

    def create_identity(self, name: str, key_type: str, password: bytes) -> KeyView:
        if key_type not in KEY_TYPES:
            raise errors.BadInput("Type de clé inconnu.")
        if len(password.decode("utf-8", "replace")) < self.min_password_length:
            raise errors.WeakPassword(
                f"Le mot de passe doit faire au moins {self.min_password_length} caractères.")
        if password.decode("utf-8", "replace").lower() in _BLOCKLIST:
            raise errors.WeakPassword("Ce mot de passe est trop courant.")
        if any(n == name for n, *_r in self._identities.values()):
            raise errors.AlreadyExists(f"Vous avez déjà une clé nommée « {name} ».")
        key_id, salt = os.urandom(16), os.urandom(16)
        fpr = _fingerprint(key_id)
        self._identities[fpr] = (name, key_type, key_id, salt,
                                 hashlib.sha256(salt + password).digest())
        return KeyView(name, _KIND_LABEL[key_type], fpr)

    def export_public_key(self, fingerprint: str) -> bytes:
        try:
            _name, kind, key_id, *_r = self._identities[fingerprint]
        except KeyError:
            raise errors.NotFound("Clé introuvable.") from None
        return _public_pem(key_id, kind)

    # ---------------------------------------------------------------- contacts
    def list_contacts(self) -> list[KeyView]:
        return sorted((KeyView(n, _KIND_LABEL[k], fpr)
                       for fpr, (n, k, _p) in self._contacts.items()),
                      key=lambda v: v.name.lower())

    def add_contact(self, name: str, public_pem: bytes) -> KeyView:
        key_id, kind = _parse_public_pem(public_pem)
        if kind not in _KIND_LABEL:
            raise errors.InvalidKey()
        fpr = _fingerprint(key_id)
        if fpr in self._contacts:
            raise errors.AlreadyExists(
                f"Cette clé est déjà enregistrée (contact « {self._contacts[fpr][0]} »).")
        self._contacts[fpr] = (name, kind, public_pem)
        return KeyView(name, _KIND_LABEL[kind], fpr)

    def remove_contact(self, fingerprint: str) -> None:
        self._contacts.pop(fingerprint, None)

    # ---------------------------------------------------------------- fichiers
    def encrypt_file(self, src: Path, dst: Path, contact_fingerprint: str) -> None:
        if contact_fingerprint not in self._contacts:
            raise errors.NotFound("Contact introuvable.")
        key_id, _kind = _parse_public_pem(self._contacts[contact_fingerprint][2])
        name = src.name.encode("utf-8")
        digest = hashlib.sha256()
        with open(src, "rb") as fin, open(dst, "wb") as fout:
            fout.write(_MAGIC + bytes([_VERSION]) + hashlib.sha256(key_id).digest()
                       + struct.pack(">H", len(name)) + name)
            while block := fin.read(_CHUNK):
                digest.update(block)
                fout.write(block)
            fout.write(digest.digest())

    def decrypt_file(self, src: Path, out_dir: Path, identity_fingerprint: str,
                     password: bytes) -> Path:
        try:
            _n, _k, key_id, salt, pw_hash = self._identities[identity_fingerprint]
        except KeyError:
            raise errors.NotFound("Clé introuvable.") from None
        if not hmac.compare_digest(hashlib.sha256(salt + password).digest(), pw_hash):
            raise errors.WrongPassword()

        size = src.stat().st_size
        with open(src, "rb") as fin:
            if fin.read(len(_MAGIC)) != _MAGIC:
                raise errors.UnsupportedFormat()
            version = fin.read(1)
            if version != bytes([_VERSION]):
                raise errors.UnsupportedFormat()
            if fin.read(32) != hashlib.sha256(key_id).digest():
                raise errors.WrongRecipient()
            try:
                (name_len,) = struct.unpack(">H", fin.read(2))
                name = fin.read(name_len).decode("utf-8")
            except (struct.error, UnicodeDecodeError) as exc:
                raise errors.CorruptedFile() from exc
            body_len = size - fin.tell() - 32
            if body_len < 0 or len(name.encode()) != name_len:
                raise errors.CorruptedFile()

            safe = Path(name).name
            if safe in ("", ".", "..") or "\x00" in safe:
                raise errors.CorruptedFile()
            out_dir.mkdir(parents=True, exist_ok=True)
            tmp = out_dir / (".partial-" + os.urandom(4).hex())
            digest = hashlib.sha256()
            try:
                with open(tmp, "wb") as fout:
                    remaining = body_len
                    while remaining:
                        block = fin.read(min(_CHUNK, remaining))
                        digest.update(block)
                        fout.write(block)
                        remaining -= len(block)
                if not hmac.compare_digest(digest.digest(), fin.read(32)):
                    raise errors.CorruptedFile()
                final = out_dir / safe
                os.replace(tmp, final)
                return final
            finally:
                tmp.unlink(missing_ok=True)
