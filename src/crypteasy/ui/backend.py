"""Backend : la seule porte entre l'interface et core/ + keystore/.

- `Backend` (Protocol) : ce dont les écrans ont besoin. Les routes n'appellent que ça.
- `RealBackend` : adaptateur au-dessus de core/ et keystore/ (à écrire quand leurs
  contrats sont figés, SPEC_TECHNIQUE § 10).
- `FakeBackend` (fake_backend.py) : pour les tests et le développement en attendant.

Choix du backend par défaut (create_app(backend=None)) :
  CRYPTEASY_FAKE_BACKEND=1  → FakeBackend (bandeau « Mode démo »)
  sinon                     → RealBackend
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from . import errors
from .security_levels import EncryptOptions


@dataclass(frozen=True)
class KeyView:
    """Ce que l'écran affiche d'une clé (à soi ou d'un contact)."""

    name: str
    kind: str  # libellé affiché : "X25519", "RSA-3072"
    fingerprint: str  # SHA-256 du DER de la clé publique, 16 groupes de 4 hexa (§ 6.3)


class Backend(Protocol):
    demo: bool  # True → bandeau « Mode démo »
    min_password_length: int  # D5 ; affiché, la règle est appliquée par le backend
    key_protection_kdfs: dict[str, str]
    """KDF proposées pour protéger la clé privée (§ 4, D4). {} = pas de choix
    (ex. si D4 retient BestAvailableEncryption) : le menu n'est pas affiché."""

    # ----- Mes clés (F1, F2)
    def list_identities(self) -> list[KeyView]: ...
    def create_identity(
        self, name: str, key_type: str, password: bytes, kdf: str | None = None
    ) -> KeyView:
        """Lève WeakPassword, AlreadyExists, BadInput."""
        ...

    def import_private_key(self, name: str, pem: bytes, password: bytes) -> KeyView:
        """PEM chiffré : `password` l'ouvre. PEM non chiffré : `password` devient sa protection.
        Lève InvalidPrivateKey, WrongPassword, WeakPassword, AlreadyExists."""
        ...

    def export_public_key(self, fingerprint: str) -> bytes: ...
    def export_private_key(self, fingerprint: str) -> bytes:
        """PEM tel que stocké, donc chiffré. Lève NotFound."""
        ...

    def delete_identity(self, fingerprint: str) -> None: ...

    # ----- Contacts (F3)
    def list_contacts(self) -> list[KeyView]: ...
    def add_contact(self, name: str, public_pem: bytes) -> KeyView:
        """Lève InvalidKey, AlreadyExists."""
        ...

    def rename_contact(self, fingerprint: str, new_name: str) -> None:
        """Lève NotFound, AlreadyExists."""
        ...

    def remove_contact(self, fingerprint: str) -> None: ...

    # ----- Fichiers (F4, F5) : chemins, le moteur travaille par blocs
    def encrypt_file(
        self, src: Path, dst: Path, recipient_fingerprint: str, options: EncryptOptions
    ) -> None:
        """Destinataire = un contact OU une de mes clés. Écrit le paquet .zip dans dst.
        Lève NotFound, BadInput."""
        ...

    def decrypt_file(
        self,
        src: Path,
        out_dir: Path,
        *,
        key_password: bytes,
        file_password: bytes | None = None,
        identity_fingerprint: str | None = None,
        private_pem: bytes | None = None,
    ) -> Path:
        """Une de mes clés (identity_fingerprint) OU une clé importée (private_pem).
        Renvoie le fichier déchiffré, nom d'origine assaini (§ 8).
        Lève WrongPassword, WrongRecipient, FilePasswordRequired, WrongFilePassword,
        CorruptedFile, UnsupportedFormat, InvalidPrivateKey, NotFound."""
        ...


def default_backend() -> Backend:
    if os.environ.get("CRYPTEASY_FAKE_BACKEND") == "1":
        from .fake_backend import FakeBackend

        return FakeBackend()
    return RealBackend()


# --------------------------------------------------------------------------- #
# RealBackend — SQUELETTE. Les signatures de core/ (keys, package, hybrid, kdf,
# errors) et keystore/ (paths, identities, contacts) ne sont pas encore figées
# (SPEC_TECHNIQUE § 10, décisions § 12). Chaque méthode dit quel module appeler.
# --------------------------------------------------------------------------- #
class RealBackend:
    demo = False
    min_password_length = 12  # D5
    key_protection_kdfs: dict[str, str] = {}  # à remplir selon D4

    def __init__(self) -> None:
        try:
            from crypteasy.core import errors as core_errors
        except ImportError as exc:
            raise SystemExit(
                "CryptEasy : le moteur (src/crypteasy/core) n'est pas encore disponible.\n"
                "Pour essayer l'interface en attendant : CRYPTEASY_FAKE_BACKEND=1 make run"
            ) from exc
        self._core_errors = core_errors

    @contextmanager
    def _translate(self) -> Iterator[None]:
        """Exceptions de core/ → exceptions d'interface (F7). Noms à confirmer avec
        Member 1 ; les plus précises d'abord, car elles peuvent hériter des autres."""
        e = self._core_errors
        mapping = [
            ("WrongRecipientError", errors.WrongRecipient),
            ("FilePasswordRequiredError", errors.FilePasswordRequired),
            ("WrongFilePasswordError", errors.WrongFilePassword),
            ("WrongPasswordError", errors.WrongPassword),
            ("UnsupportedFormatError", errors.UnsupportedFormat),
            ("DecryptionError", errors.CorruptedFile),
            ("InvalidPrivateKeyError", errors.InvalidPrivateKey),
            ("InvalidKeyError", errors.InvalidKey),
        ]
        try:
            yield
        except Exception as exc:
            for name, ui_error in mapping:
                cls = getattr(e, name, None)
                if cls is not None and isinstance(exc, cls):
                    raise ui_error() from exc
            raise

    def _todo(self, where: str):
        raise NotImplementedError(f"RealBackend : brancher sur {where} quand le contrat est figé")

    def list_identities(self):
        return self._todo("keystore/identities.py")

    def create_identity(self, name, key_type, password, kdf=None):
        return self._todo("core/keys.py (génération) + keystore/identities.py (stockage)")

    def import_private_key(self, name, pem, password):
        return self._todo("core/keys.py (lecture PEM) + keystore/identities.py")

    def export_public_key(self, fingerprint):
        return self._todo("keystore/identities.py")

    def export_private_key(self, fingerprint):
        return self._todo("keystore/identities.py")

    def delete_identity(self, fingerprint):
        return self._todo("keystore/identities.py")

    def list_contacts(self):
        return self._todo("keystore/contacts.py")

    def add_contact(self, name, public_pem):
        return self._todo("keystore/contacts.py")

    def rename_contact(self, fingerprint, new_name):
        return self._todo("keystore/contacts.py")

    def remove_contact(self, fingerprint):
        return self._todo("keystore/contacts.py")

    def encrypt_file(self, src, dst, recipient_fingerprint, options):
        return self._todo("core/hybrid.py + core/package.py")

    def decrypt_file(
        self,
        src,
        out_dir,
        *,
        key_password,
        file_password=None,
        identity_fingerprint=None,
        private_pem=None,
    ):
        return self._todo("core/package.py + core/hybrid.py")
