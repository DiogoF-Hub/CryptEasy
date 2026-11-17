"""RealBackend : l'interface branchée sur le vrai moteur (#21).

- core/      : chiffrement hybride (hybrid.py), paquet .zip (package.py), dossiers (folders.py)
- keystore/  : mes clés (identities.py), contacts (contacts.py), réglages (paths.py)

Les routes ne voient jamais ces modules : elles appellent l'interface `Backend`
(backend.py), et chaque erreur de core/ ou keystore/ est convertie ici en erreur
d'interface (errors.py), qui porte une clé de traduction (SPEC § F7).
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from crypteasy.core import errors as core_errors
from crypteasy.core import folders, hybrid, keys, package
from crypteasy.keystore import _core as keystore_core
from crypteasy.keystore import contacts, identities, paths
from crypteasy.keystore import errors as keystore_errors
from crypteasy.keystore.common import read_limited

from . import errors
from .backend import KeyView, PackageInfo, Progress, Protection
from .files import temp_root

# (erreur de core/ ou keystore/, erreur d'interface) : la première qui correspond gagne,
# donc les plus précises d'abord. Les classes de keystore/errors.py pour les clés et la
# phrase secrète SONT celles de core/errors.py : une seule ligne suffit pour les deux.
_ERRORS: list[tuple[type[Exception], type[errors.UIError] | errors.UIError]] = [
    (core_errors.WrongPassphraseError, errors.WrongPassphrase),
    (core_errors.NoMatchingKeyError, errors.NoMatchingKey),
    (core_errors.UnsupportedFormatError, errors.UnsupportedFormat),
    (core_errors.ExtractionTooLargeError, errors.ExtractionTooLarge),
    (core_errors.UnsafeArchiveError, errors.UnsafeArchive),
    (core_errors.DecryptionError, errors.CorruptedFile),
    (core_errors.InvalidPrivateKeyError, errors.InvalidPrivateKey),
    (core_errors.InvalidKeyError, errors.InvalidPublicKey),
    (keystore_errors.NotFoundError, errors.NotFound),
    (keystore_errors.AlreadyExistsError, errors.AlreadyExists),
    (keystore_errors.InvalidNameError, errors.BadInput("error.bad_name")),
    (keystore_errors.InvalidSettingError, errors.BadInput("error.unknown_setting")),
    (keystore_errors.CorruptedStoreError, errors.StoreDamaged),
]

SPEED_SAMPLE = 32 * 1024 * 1024  # § 5.5 : on chiffre ~30 Mo une fois au démarrage


@contextmanager
def translate() -> Iterator[None]:
    """À mettre autour de chaque appel à core/ ou keystore/."""
    try:
        yield
    except errors.UIError:
        raise
    except FileExistsError as exc:  # § 8 : jamais d'écrasement
        name = Path(exc.filename).name if exc.filename else ""
        raise errors.FileExists(name=name) from exc
    except Exception as exc:
        for engine_error, ui_error in _ERRORS:
            if isinstance(exc, engine_error):
                if isinstance(ui_error, errors.UIError):  # instance : on en fait une copie
                    raise type(ui_error)(ui_error.key, **ui_error.params) from exc
                raise ui_error() from exc
        raise  # imprévu : user_message() affichera le message générique


def _view(item: identities.Identity | contacts.Contact) -> KeyView:
    """Identity / Contact de keystore → ce que l'écran affiche ("rsa-3072" → "RSA-3072")."""
    if isinstance(item, identities.Identity):
        return KeyView(item.name, item.key_type.upper(), item.fingerprint, item.level,
                       item.protected)  # fmt: skip
    return KeyView(item.name, item.key_type.upper(), item.fingerprint)


def _protection(p: Protection) -> identities.Protection:
    return identities.Protection(p.passphrase, p.kdf, p.kdf_strength, p.salt_len, p.level)


class RealBackend:
    demo = False

    # ----------------------------------------------------------------- mes clés (F1, F2)
    def list_identities(self) -> list[KeyView]:
        with translate():
            return [_view(i) for i in identities.list_identities()]

    def _name_taken(self, name: str) -> None:
        name = name.strip()
        if any(i.name == name for i in identities.list_identities()):
            raise errors.AlreadyExists("error.key_name_taken", name=name)

    def create_identity(self, name, key_type, protection):
        with translate():
            self._name_taken(name)
            return _view(identities.create_identity(name, key_type, _protection(protection)))

    def import_private_key(self, name, key_file, current_passphrase, protection):
        with translate():
            self._name_taken(name)
            try:
                ident = identities.import_private_key(
                    name, Path(key_file), current_passphrase, _protection(protection)
                )
            except keystore_errors.AlreadyExistsError:
                # Le nom est libre (vérifié juste avant) : c'est donc la CLÉ qui est déjà
                # enregistrée. On la recharge pour dire sous quel nom (erreur rare).
                fpr = self._fingerprint_of_key_file(Path(key_file), current_passphrase)
                same = [i.name for i in identities.list_identities() if i.fingerprint == fpr]
                if not same:
                    raise
                raise errors.AlreadyExists("error.key_already_imported", name=same[0]) from None
            return _view(ident)

    def change_protection(self, fingerprint, current_passphrase, protection):
        with translate():
            return _view(
                identities.change_protection(fingerprint, current_passphrase,
                                             _protection(protection))
            )  # fmt: skip

    def export_public_key(self, fingerprint, dst):
        with translate():
            identities.export_public_key(fingerprint, Path(dst))

    def export_private_key(self, fingerprint, dst):
        with translate():
            identities.export_private_key(fingerprint, Path(dst))

    def delete_identity(self, fingerprint):
        with translate(), suppress(keystore_errors.NotFoundError):  # déjà supprimée
            identities.delete_identity(fingerprint)

    # ----------------------------------------------------------------- contacts (F3)
    def list_contacts(self) -> list[KeyView]:
        with translate():
            return [_view(c) for c in contacts.list_contacts()]

    def add_contact(self, name, public_pem):
        with translate():
            try:
                return _view(contacts.add_contact(name, public_pem))
            except keystore_errors.AlreadyExistsError:
                # Même clé déjà enregistrée, peut-être sous un autre nom : on dit lequel
                _type, fpr = keystore_core.inspect_public_pem(public_pem)
                same = [c.name for c in contacts.list_contacts() if c.fingerprint == fpr]
                if not same:
                    raise
                raise errors.AlreadyExists("error.contact_key_taken", name=same[0]) from None

    def rename_contact(self, fingerprint, new_name):
        with translate():
            contacts.rename_contact(fingerprint, new_name)

    def remove_contact(self, fingerprint):
        with translate(), suppress(keystore_errors.NotFoundError):  # déjà supprimé
            contacts.remove_contact(fingerprint)

    # ----------------------------------------------------------------- chiffrer (F4, § 5.2)
    def measure_speed(self) -> float:
        """§ 5.5 : chiffre une fois ~30 Mo, comme le vrai chiffrement (AES-GCM, blocs
        de 64 Kio), et renvoie la vitesse en octets/s."""
        aes = AESGCM(AESGCM.generate_key(bit_length=256))
        block = os.urandom(package.chunk_size)
        nonce = os.urandom(12)  # données jetables : réutiliser le nonce ne protège rien ici
        start = time.perf_counter()
        for _ in range(SPEED_SAMPLE // len(block)):
            aes.encrypt(nonce, block, b"")
        return SPEED_SAMPLE / max(time.perf_counter() - start, 1e-6)

    def _public_key(self, fingerprint: str):
        """Clé publique du destinataire : un contact, ou une de mes clés (s'envoyer un
        fichier à soi-même)."""
        try:
            pem = contacts.get_contact(fingerprint).public_pem
        except keystore_errors.NotFoundError:
            try:
                pem = identities.public_pem(fingerprint)
            except keystore_errors.NotFoundError:
                raise errors.NotFound("error.recipient_not_found") from None
        return keys.load_public_keys(pem)[0]

    def encrypt(self, src, dst, recipient, cipher, progress: Progress):
        src, dst = Path(src), Path(dst)
        with translate():
            public_key = self._public_key(recipient)
            if not src.is_dir():
                hybrid.encrypt_file(src, dst, public_key, cipher, progress=progress)
                return
            # § 5.4 : un dossier est d'abord zippé. Le zip (en clair) va dans le dossier
            # temporaire de l'appli, jamais à côté du paquet (dossier synchronisé, clé USB…),
            # et il est supprimé juste après, même en cas d'erreur.
            root = temp_root()
            root.mkdir(parents=True, exist_ok=True)
            workdir = Path(tempfile.mkdtemp(prefix="run-zip-", dir=root))
            try:
                tmp_zip = workdir / "folder.zip"
                folders.zip_folder(src, tmp_zip)
                hybrid.encrypt_file(
                    tmp_zip, dst, public_key, cipher, is_folder=True,
                    original_name=f"{src.name}.zip", progress=progress,
                )  # fmt: skip
            finally:
                shutil.rmtree(workdir, ignore_errors=True)

    # ----------------------------------------------------------------- déchiffrer (F5, § 5.3)
    def inspect_package(self, package_path):
        with translate():
            h = package.read_package_info(Path(package_path))
        return PackageInfo(h["recipient_fingerprint"], h["is_folder"], h["key_type"], h["cipher"])

    @staticmethod
    def _key_from_file(key_file: Path, passphrase: bytes | None):
        """Clé privée prise dans un fichier pour l'occasion (sans l'enregistrer) : un
        private.key exporté par CryptEasy, ou un .pem fait ailleurs (OpenSSL), chiffré ou
        non. Mêmes contrôles qu'à l'import (taille, coût du KDF borné avant de le lancer)."""
        try:
            data = read_limited(key_file, identities.MAX_PRIVATE_KEY_BYTES)
        except ValueError as exc:  # trop gros pour être une clé
            raise errors.InvalidPrivateKey() from exc
        if data.lstrip().startswith(b"{"):  # private.key de CryptEasy (JSON)
            pem, password = identities.open_secret(data, passphrase), None
        else:
            pem, password = data, passphrase
        secret, _public_pem, _key_type, _fpr = keystore_core.load_private_pem(pem, password)
        return keys.load_private_keys(secret)[0]

    def _fingerprint_of_key_file(self, key_file: Path, passphrase: bytes | None) -> str:
        return keys.get_fingerprint(self._key_from_file(key_file, passphrase).public_key())

    def decrypt(self, package_path, out_dir, passphrase, progress, identity=None, key_file=None):
        package_path, out_dir = Path(package_path), Path(out_dir)
        with translate():
            info = self.inspect_package(package_path)
            if key_file is not None:
                private_key = self._key_from_file(Path(key_file), passphrase)
            else:
                # § 5.3 étape 3 : la clé est choisie grâce à l'empreinte de l'en-tête
                fingerprint = identity or info.recipient_fingerprint
                if fingerprint != info.recipient_fingerprint:
                    raise errors.NoMatchingKey()
                try:
                    secret = identities.unlock(fingerprint, passphrase)
                except keystore_errors.NotFoundError:
                    raise errors.NoMatchingKey() from None
                private_key = keys.load_private_keys(secret)[0]
            # Vérifie l'empreinte, déchiffre dans un fichier temporaire et ne lui donne son
            # nom d'origine (assaini) qu'une fois TOUS les blocs vérifiés (§ 5.3, § 8)
            return hybrid.decrypt_package(package_path, private_key, out_dir, progress)

    def extract_folder(self, zip_path, parent):
        with translate():
            return folders.extract_folder(Path(zip_path), Path(parent))

    # ----------------------------------------------------------------- réglages (§ 6.1)
    def load_settings(self) -> dict:
        return paths.load_settings()  # fichier abîmé → {} : jamais bloquant

    def save_settings(self, settings: dict) -> None:
        paths.save_settings(settings)
