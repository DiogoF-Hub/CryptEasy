"""Backend : la seule porte entre l'interface et core/ + keystore/ (§ 3, § 5 de la fiche Track B).

- `Backend` (Protocol) : ce dont les écrans ont besoin. Les routes n'appellent que ça.
- `RealBackend` : adaptateur au-dessus de core/ et keystore/ (S7, quand A et C ont mergé).
- `FakeBackend` (fake_backend.py) : pour les tests et le développement avant S7.

Choix du backend par défaut (create_app(backend=None)) :
  CRYPTEASY_FAKE_BACKEND=1  → FakeBackend (bandeau « Mode démo »)
  sinon                     → RealBackend
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

from . import errors


@dataclass(frozen=True)
class KeyView:
    """Ce que l'écran affiche d'une clé (à soi ou d'un contact)."""
    name: str
    kind: str          # libellé affiché : "X25519", "RSA-3072"
    fingerprint: str   # SHA-256 du SPKI DER, hex groupé (format fixé par keys.fingerprint)


# Types de clés proposés. D2 : X25519 par défaut, RSA en options avancées. D3 : RSA 3072 conseillé.
KEY_TYPES: dict[str, str] = {
    "x25519": "X25519 (recommandé)",
    "rsa-3072": "RSA 3072 bits",
    "rsa-2048": "RSA 2048 bits",
    "rsa-4096": "RSA 4096 bits",
}
DEFAULT_KEY_TYPE = "x25519"


class Backend(Protocol):
    demo: bool                 # True → bandeau « Mode démo »
    min_password_length: int   # affiché sur le formulaire ; la règle elle-même est appliquée par le backend (D4)

    # Mes clés
    def list_identities(self) -> list[KeyView]: ...
    def create_identity(self, name: str, key_type: str, password: bytes) -> KeyView:
        """Lève WeakPassword, AlreadyExists, BadInput."""
        ...
    def export_public_key(self, fingerprint: str) -> bytes:
        """PEM de MA clé publique. Lève NotFound."""
        ...

    # Contacts
    def list_contacts(self) -> list[KeyView]: ...
    def add_contact(self, name: str, public_pem: bytes) -> KeyView:
        """Lève InvalidKey, AlreadyExists."""
        ...
    def remove_contact(self, fingerprint: str) -> None: ...

    # Fichiers (chemins : le moteur travaille par blocs, jamais tout en mémoire)
    def encrypt_file(self, src: Path, dst: Path, contact_fingerprint: str) -> None:
        """Lève NotFound."""
        ...
    def decrypt_file(self, src: Path, out_dir: Path, identity_fingerprint: str,
                     password: bytes) -> Path:
        """Renvoie le fichier déchiffré (nom d'origine, assaini par core/).
        Lève WrongPassword, WrongRecipient, CorruptedFile, UnsupportedFormat, NotFound."""
        ...


def default_backend() -> Backend:
    if os.environ.get("CRYPTEASY_FAKE_BACKEND") == "1":
        from .fake_backend import FakeBackend
        return FakeBackend()
    return RealBackend()


# --------------------------------------------------------------------------- #
# RealBackend — À TERMINER EN S7, quand les stubs de Track A (core/) et Track C
# (keystore/) sont mergés. Écrit d'après les signatures du § 3 ; NON TESTÉ tant
# que ces modules n'existent pas. Les parties « identité » attendent l'API de
# keystore/identity.py, qui n'est pas encore fixée au § 3.
# --------------------------------------------------------------------------- #
class RealBackend:
    demo = False
    min_password_length = 15   # À ALIGNER sur la politique D4 de Track C

    def __init__(self) -> None:
        from crypteasy.core import errors as core_errors, hybrid, keys
        from crypteasy.keystore import contacts
        self._keys, self._hybrid, self._contacts = keys, hybrid, contacts
        self._core_errors = core_errors

    @contextmanager
    def _translate(self) -> Iterator[None]:
        """Exceptions de core/ → exceptions d'interface. Les plus précises d'abord."""
        e = self._core_errors
        try:
            yield
        except getattr(e, "WrongRecipientError", ()) as exc:
            raise errors.WrongRecipient() from exc
        except getattr(e, "UnsupportedFormatError", ()) as exc:
            raise errors.UnsupportedFormat() from exc
        except getattr(e, "DecryptionError", ()) as exc:
            raise errors.CorruptedFile() from exc
        except getattr(e, "InvalidKeyError", ()) as exc:
            raise errors.InvalidKey() from exc

    def _kind(self, public_pem: bytes) -> str:
        pub = self._keys.public_from_pem(public_pem)
        size = getattr(pub, "key_size", None)
        return f"RSA-{size}" if size else "X25519"

    def _contact(self, fingerprint: str):
        for c in self._contacts.list_contacts():
            if c.fingerprint == fingerprint:
                return c
        raise errors.NotFound("Contact introuvable.")

    # -- Contacts (§ 3 : keystore/contacts.py) --------------------------------
    def list_contacts(self) -> list[KeyView]:
        return [KeyView(c.name, self._kind(c.enc_pub_pem), c.fingerprint)
                for c in self._contacts.list_contacts()]

    def add_contact(self, name: str, public_pem: bytes) -> KeyView:
        with self._translate():
            c = self._contacts.add_contact(name, public_pem)
        return KeyView(c.name, self._kind(c.enc_pub_pem), c.fingerprint)

    def remove_contact(self, fingerprint: str) -> None:
        self._contacts.remove_contact(fingerprint)

    # -- Fichiers (§ 3 : core/hybrid.py) --------------------------------------
    def encrypt_file(self, src: Path, dst: Path, contact_fingerprint: str) -> None:
        contact = self._contact(contact_fingerprint)
        with self._translate():
            pub = self._keys.public_from_pem(contact.enc_pub_pem)
            self._hybrid.encrypt_file(src, dst, pub)

    def decrypt_file(self, src: Path, out_dir: Path, identity_fingerprint: str,
                     password: bytes) -> Path:
        pem = self._identity_private_pem(identity_fingerprint)
        try:
            key = self._keys.private_from_pem(pem, password)
        except getattr(self._core_errors, "InvalidKeyError", ()) as exc:
            # § 4 S7 de la fiche : InvalidKeyError au chargement de la clé privée = mauvais mot de passe
            raise errors.WrongPassword() from exc
        with self._translate():
            return self._hybrid.decrypt_file(src, out_dir, key)

    # -- Identités : API de keystore/identity.py à fixer avec Track C ----------
    def list_identities(self) -> list[KeyView]:
        raise NotImplementedError("keystore/identity.py : API à fixer avec Track C")

    def create_identity(self, name: str, key_type: str, password: bytes) -> KeyView:
        raise NotImplementedError("keystore/identity.py : API à fixer avec Track C")

    def export_public_key(self, fingerprint: str) -> bytes:
        raise NotImplementedError("keystore/identity.py : API à fixer avec Track C")

    def _identity_private_pem(self, fingerprint: str) -> bytes:
        raise NotImplementedError("keystore/identity.py : API à fixer avec Track C")
