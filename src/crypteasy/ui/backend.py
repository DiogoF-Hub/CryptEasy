"""Backend : la seule porte entre l'interface et core/ + keystore/.

- `Backend` (Protocol) : ce dont les écrans ont besoin. Les routes n'appellent que ça.
- `RealBackend` : adaptateur au-dessus de core/ et keystore/ (SQUELETTE, à brancher
  quand leurs signatures sont figées, SPEC_TECHNIQUE § 10).
- `FakeBackend` (fake_backend.py) : pour les tests et pour utiliser l'interface
  en attendant (bandeau « Mode démo »).

Choix par défaut (create_app(backend=None)) :
  CRYPTEASY_FAKE_BACKEND=1  → FakeBackend
  sinon                     → RealBackend

Tous les fichiers sont désignés par des chemins sur le disque (SPEC § 2.2) : Python
lit et écrit directement, rien n'est envoyé par le navigateur.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from . import errors

# Appelé pendant les longues opérations : (octets traités, octets au total)
Progress = Callable[[int, int], None]


@dataclass(frozen=True)
class KeyView:
    """Ce que l'écran affiche d'une clé (à moi ou d'un contact)."""

    name: str
    kind: str  # libellé affiché : "X25519", "RSA-3072"
    fingerprint: str  # SHA-256 du DER de la clé publique, 16 groupes de 4 hexa (§ 6.3)
    level: str | None = None  # mes clés : niveau de protection (§ 4.2) ; contacts : None
    protected: bool = True  # False = clé privée enregistrée sans phrase secrète

    @property
    def key_type(self) -> str:
        """Identifiant utilisé par les règles de niveau : "x25519", "rsa-3072"."""
        return self.kind.lower()


@dataclass(frozen=True)
class Protection:
    """Comment verrouiller une clé privée sur le disque (§ 4.1, § 6.2)."""

    passphrase: bytes | None  # None = « sans phrase secrète »
    kdf: str = "argon2id"
    kdf_strength: str = "normal"
    salt_len: int = 16  # 0 = sans sel (PBKDF2 uniquement)
    level: str = "strong"  # niveau calculé par l'interface (§ 4.2), à garder dans info.json


@dataclass(frozen=True)
class PackageInfo:
    """En-tête public d'un paquet (§ 5.1), lu sans rien déchiffrer."""

    recipient_fingerprint: str
    is_folder: bool
    key_type: str
    cipher: str


class Backend(Protocol):
    demo: bool  # True → bandeau « Mode démo »

    # ----- Mes clés (F1, F2)
    def list_identities(self) -> list[KeyView]: ...
    def create_identity(self, name: str, key_type: str, protection: Protection) -> KeyView:
        """Lève WeakPassphrase, AlreadyExists, BadInput."""
        ...

    def import_private_key(
        self, name: str, key_file: Path, current_passphrase: bytes | None, protection: Protection
    ) -> KeyView:
        """Fichier private.key de CryptEasy ou PEM (chiffré ou non), reverrouillé avec
        `protection`. Lève InvalidPrivateKey, WrongPassphrase, AlreadyExists."""
        ...

    def change_protection(
        self, fingerprint: str, current_passphrase: bytes | None, protection: Protection
    ) -> KeyView:
        """Reverrouille la clé privée. Lève WrongPassphrase, NotFound."""
        ...

    def export_public_key(self, fingerprint: str, dst: Path) -> None:
        """Écrit public.pem dans dst (jamais d'écrasement : lève FileExists)."""
        ...

    def export_private_key(self, fingerprint: str, dst: Path) -> None:
        """Copie private.key, toujours verrouillé. Lève FileExists, NotFound."""
        ...

    def delete_identity(self, fingerprint: str) -> None: ...

    # ----- Contacts (F3)
    def list_contacts(self) -> list[KeyView]: ...
    def add_contact(self, name: str, public_pem: bytes) -> KeyView:
        """Lève InvalidPublicKey, AlreadyExists."""
        ...

    def rename_contact(self, fingerprint: str, new_name: str) -> None: ...
    def remove_contact(self, fingerprint: str) -> None: ...

    # ----- Chiffrer / déchiffrer (F4, F5, § 5)
    def measure_speed(self) -> float:
        """Vitesse de chiffrement de ce PC en octets/s (§ 5.5, core/speed.py)."""
        ...

    def encrypt(
        self, src: Path, dst: Path, recipient: str, cipher: str, progress: Progress
    ) -> None:
        """src : fichier OU dossier (zippé d'abord, § 5.4). Écrit le paquet dans dst.
        recipient : empreinte d'un contact ou d'une de mes clés."""
        ...

    def inspect_package(self, package: Path) -> PackageInfo:
        """Lève UnsupportedFormat, CorruptedFile."""
        ...

    def decrypt(
        self,
        package: Path,
        out_dir: Path,
        passphrase: bytes | None,
        progress: Progress,
        identity: str | None = None,
        key_file: Path | None = None,
    ) -> Path:
        """Déchiffre dans out_dir (fichier temporaire, § 8) et renvoie le fichier obtenu,
        sous son nom d'origine assaini. Clé : une de mes clés (identity) OU un fichier
        de clé importé pour l'occasion (key_file). Lève WrongPassphrase, NoMatchingKey,
        CorruptedFile, UnsupportedFormat, InvalidPrivateKey."""
        ...

    def extract_folder(self, zip_path: Path, parent: Path) -> Path:
        """Extrait un dossier déchiffré dans un NOUVEAU dossier créé dans `parent`
        (§ 5.4 : zip-slip, zip bomb). Renvoie ce dossier. Lève ExtractionTooLarge."""
        ...

    # ----- Réglages de l'application (settings.json, § 6.1)
    def load_settings(self) -> dict: ...
    def save_settings(self, settings: dict) -> None: ...


def default_backend() -> Backend:
    if os.environ.get("CRYPTEASY_FAKE_BACKEND") == "1":
        from .fake_backend import FakeBackend

        return FakeBackend()
    return RealBackend()


# --------------------------------------------------------------------------- #
# RealBackend — SQUELETTE. Chaque méthode indique le module à appeler.
# Les noms d'exceptions de core/errors.py sont à confirmer avec Track A.
# --------------------------------------------------------------------------- #
_CORE_ERRORS = [  # (nom dans core/errors.py, erreur d'interface) : les plus précises d'abord
    ("WrongPassphraseError", errors.WrongPassphrase),
    ("NoMatchingKeyError", errors.NoMatchingKey),
    ("UnsupportedFormatError", errors.UnsupportedFormat),
    ("ExtractionTooLargeError", errors.ExtractionTooLarge),
    ("DecryptionError", errors.CorruptedFile),
    ("InvalidPrivateKeyError", errors.InvalidPrivateKey),
    ("InvalidKeyError", errors.InvalidPublicKey),
]


class RealBackend:
    demo = False

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
        """À utiliser autour de chaque appel à core/ ou keystore/."""
        try:
            yield
        except Exception as exc:
            for name, ui_error in _CORE_ERRORS:
                cls = getattr(self._core_errors, name, None)
                if cls is not None and isinstance(exc, cls):
                    raise ui_error() from exc
            raise

    def _todo(self, where: str):
        raise NotImplementedError(f"RealBackend : brancher sur {where}")

    def list_identities(self):
        return self._todo("keystore/identities.py")

    def create_identity(self, name, key_type, protection):
        return self._todo("core/keys.py + core/kdf.py + keystore/identities.py")

    def import_private_key(self, name, key_file, current_passphrase, protection):
        return self._todo("core/keys.py + keystore/identities.py")

    def change_protection(self, fingerprint, current_passphrase, protection):
        return self._todo("keystore/identities.py")

    def export_public_key(self, fingerprint, dst):
        return self._todo("keystore/identities.py")

    def export_private_key(self, fingerprint, dst):
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

    def measure_speed(self):
        return self._todo("core/speed.py")

    def encrypt(self, src, dst, recipient, cipher, progress):
        return self._todo("core/folders.py + core/hybrid.py + core/package.py")

    def inspect_package(self, package):
        return self._todo("core/package.py")

    def decrypt(self, package, out_dir, passphrase, progress, identity=None, key_file=None):
        return self._todo("core/package.py + core/hybrid.py")

    def extract_folder(self, zip_path, parent):
        return self._todo("core/folders.py")

    def load_settings(self):
        return self._todo("keystore/paths.py (settings.json)")

    def save_settings(self, settings):
        return self._todo("keystore/paths.py (settings.json)")
