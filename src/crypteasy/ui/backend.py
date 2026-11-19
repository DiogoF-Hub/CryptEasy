"""Backend : la seule porte entre l'interface et core/ + keystore/.

- `Backend` (Protocol) : ce dont les écrans ont besoin. Les routes n'appellent que ça.
- `RealBackend` (real_backend.py) : branché sur core/ et keystore/, convertit leurs
  erreurs en messages traduits.
- `FakeBackend` (fake_backend.py) : rien n'est chiffré, pour les tests de l'interface
  et les démos (bandeau « Mode démo »).

Choix par défaut (create_app(backend=None)) :
  CRYPTEASY_FAKE_BACKEND=1  → FakeBackend
  sinon                     → RealBackend

Tous les fichiers sont désignés par des chemins sur le disque (SPEC § 2.2) : Python
lit et écrit directement, rien n'est envoyé par le navigateur.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

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
        """Vitesse de chiffrement de ce PC en octets/s (§ 5.5)."""
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
    from .real_backend import RealBackend

    return RealBackend()
