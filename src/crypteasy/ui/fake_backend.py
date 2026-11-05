"""FakeBackend : backend factice pour les tests et pour utiliser l'interface en attendant
core/ et keystore/.

AUCUNE SÉCURITÉ : le contenu des fichiers n'est PAS chiffré. Il imite le comportement
attendu du vrai moteur (SPEC § 5) pour que tous les écrans et tous les cas d'erreur F7
soient utilisables et testables : paquet .zip avec key.enc + file.enc, en-tête
« CRYPTEZ » lisible sans clé, empreinte du destinataire, détection de modification,
nom d'origine caché et assaini, dossiers zippés puis extraits.

Le zip / l'extraction des dossiers (zip_folder, extract_folder) sont, eux, de vraies
implémentations sûres (§ 5.4) : Track A peut s'en inspirer pour core/folders.py.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import stat
import struct
import time
import zipfile
from pathlib import Path, PurePosixPath

from . import errors
from .backend import KeyView, PackageInfo, Protection
from .files import original_name, remove_dir, unique_child
from .security_levels import KDF_STRENGTHS, KDFS, KEY_TYPES

_PUB = (
    "-----BEGIN CRYPTEASY DEMO PUBLIC KEY-----\n",
    "\n-----END CRYPTEASY DEMO PUBLIC KEY-----\n",
)
_MAGIC = b"CRYPTEZ"
_VERSION = 1
_CHUNK = 64 * 1024
_MAX_HEADER = 64 * 1024
_MAX_KEY_ENC = 64 * 1024
_BLOCKLIST = {"motdepasse123", "password1234", "azertyuiop12", "123456789012"}

# Limites d'extraction d'un dossier (§ 5.4, « chiffres à ajuster »)
MAX_FILES = 100_000
MAX_RATIO = 10  # taille extraite ≤ 10 × taille du zip
MIN_LIMIT = 1024 * 1024


def _fingerprint(key_id: bytes) -> str:
    h = hashlib.sha256(key_id).hexdigest().upper()
    return " ".join(h[i : i + 4] for i in range(0, 64, 4))  # 16 groupes de 4 (§ 6.3)


def _kind(key_type: str) -> str:
    return key_type.upper()  # "x25519" → "X25519", "rsa-3072" → "RSA-3072"


class _Identity:
    def __init__(self, name: str, key_type: str, key_id: bytes, lock: dict, level: str) -> None:
        self.name, self.key_type, self.key_id, self.lock, self.level = (
            name, key_type, key_id, lock, level,
        )  # fmt: skip

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.key_id)

    @property
    def protected(self) -> bool:
        return self.lock["kdf"] != "none"

    def view(self) -> KeyView:
        return KeyView(
            self.name, _kind(self.key_type), self.fingerprint, self.level, self.protected
        )

    def unlock(self, passphrase: bytes | None) -> None:
        if not self.protected:
            return
        salt = base64.b64decode(self.lock["salt"])
        digest = hashlib.sha256(salt + (passphrase or b"")).hexdigest()
        if not hmac.compare_digest(digest, self.lock["check"]):
            raise errors.WrongPassphrase()

    def private_file(self) -> bytes:
        """Imite le format private.key de la spec (§ 6.2)."""
        return json.dumps(
            {"format": "crypteasy-private-key", "version": 1, "demo": True,
             "key_type": self.key_type, "key_id": self.key_id.hex(), **self.lock},
            indent=2,
        ).encode()  # fmt: skip

    @classmethod
    def from_private_file(cls, name: str, data: bytes) -> _Identity:
        try:
            d = json.loads(data)
            if d.get("format") != "crypteasy-private-key" or d.get("key_type") not in KEY_TYPES:
                raise ValueError
            lock = {k: d[k] for k in ("kdf", "kdf_strength", "salt", "check") if k in d}
            if lock.get("kdf") is None:
                raise ValueError
            return cls(name, d["key_type"], bytes.fromhex(d["key_id"]), lock, "strong")
        except (ValueError, KeyError, TypeError) as exc:
            raise errors.InvalidPrivateKey() from exc


def _make_lock(protection: Protection) -> dict:
    if protection.passphrase is None:
        return {"kdf": "none"}
    salt = os.urandom(protection.salt_len)
    return {
        "kdf": protection.kdf,
        "kdf_strength": protection.kdf_strength,
        "salt": base64.b64encode(salt).decode(),
        "check": hashlib.sha256(salt + protection.passphrase).hexdigest(),
    }


# --------------------------------------------------------------------- dossiers (§ 5.4)
def zip_folder(folder: Path, dst_zip: Path) -> None:
    """Zippe un dossier (stocké, sans compression), chemins relatifs, liens symboliques
    ignorés. Écrit au fil de l'eau sur le disque."""
    with zipfile.ZipFile(dst_zip, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
        for root, dirs, files in os.walk(folder):
            here = Path(root)
            dirs[:] = sorted(d for d in dirs if not (here / d).is_symlink())
            rel = here.relative_to(folder)
            if rel != Path(".") and not files and not dirs:
                zf.writestr(rel.as_posix() + "/", b"")  # dossier vide conservé
            for name in sorted(files):
                path = here / name
                if not path.is_symlink():
                    zf.write(path, (rel / name).as_posix())


def extract_folder(zip_path: Path, parent: Path) -> Path:
    """Extrait dans un NOUVEAU dossier (jamais dans un dossier existant), chaque chemin
    vérifié (zip-slip), taille et nombre de fichiers plafonnés (zip bomb). En cas de
    problème, le nouveau dossier est supprimé."""
    folder = unique_child(parent, Path(zip_path.name).stem or "dossier")
    folder.mkdir()
    root = folder.resolve()
    limit = max(MAX_RATIO * zip_path.stat().st_size, MIN_LIMIT)
    written = 0
    try:
        with zipfile.ZipFile(zip_path) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_FILES:
                raise errors.ExtractionTooLarge()
            for info in infos:
                raw = info.filename.replace("\\", "/")
                parts = PurePosixPath(raw).parts
                if (
                    raw.startswith("/")
                    or ".." in parts
                    or (parts and ":" in parts[0])
                    or stat.S_ISLNK(info.external_attr >> 16)
                ):
                    raise errors.UnsafeArchive()
                if not parts:
                    continue
                target = folder.joinpath(*parts).resolve()
                if not target.is_relative_to(root) or target == root:
                    raise errors.UnsafeArchive()
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "xb") as dst:
                    while chunk := src.read(1024 * 1024):
                        written += len(chunk)  # on compte ce qui sort, pas ce qu'annonce le zip
                        if written > limit:
                            raise errors.ExtractionTooLarge()
                        dst.write(chunk)
    except zipfile.BadZipFile as exc:
        remove_dir(folder)
        raise errors.CorruptedFile() from exc
    except BaseException:
        remove_dir(folder)
        raise
    return folder


class FakeBackend:
    demo = True

    def __init__(self, speed: float | None = None) -> None:
        self._identities: dict[str, _Identity] = {}
        self._contacts: dict[str, tuple[str, str, bytes]] = {}  # empreinte → (nom, type, pem)
        self._settings: dict = {}
        self._speed = speed

    # ----------------------------------------------------------------- mes clés
    def _check_protection(self, protection: Protection) -> None:
        if protection.passphrase is None:
            return
        text = protection.passphrase.decode("utf-8", "replace")
        if len(text) < 12:
            raise errors.WeakPassphrase(n=12)
        if text.lower() in _BLOCKLIST:
            raise errors.WeakPassphrase("error.passphrase_common")
        if protection.kdf not in KDFS or protection.kdf_strength not in KDF_STRENGTHS:
            raise errors.BadInput("error.unknown_setting")
        if protection.salt_len not in (0, 16, 32):
            raise errors.BadInput("error.unknown_setting")
        if protection.salt_len == 0 and protection.kdf == "argon2id":
            raise errors.BadInput("error.argon2_needs_salt")

    def _check_name(self, name: str) -> None:
        if any(i.name == name for i in self._identities.values()):
            raise errors.AlreadyExists("error.key_name_taken", name=name)

    def list_identities(self) -> list[KeyView]:
        return sorted((i.view() for i in self._identities.values()), key=lambda v: v.name.lower())

    def create_identity(self, name, key_type, protection):
        if key_type not in KEY_TYPES:
            raise errors.BadInput("error.unknown_setting")
        self._check_protection(protection)
        self._check_name(name)
        ident = _Identity(name, key_type, os.urandom(16), _make_lock(protection), protection.level)
        self._identities[ident.fingerprint] = ident
        return ident.view()

    def import_private_key(self, name, key_file, current_passphrase, protection):
        if key_file.stat().st_size > _MAX_KEY_ENC:
            raise errors.InvalidPrivateKey()
        ident = _Identity.from_private_file(name, key_file.read_bytes())
        ident.unlock(current_passphrase)
        self._check_protection(protection)
        self._check_name(name)
        if ident.fingerprint in self._identities:
            raise errors.AlreadyExists(
                "error.key_already_imported", name=self._identities[ident.fingerprint].name
            )
        ident.lock, ident.level = _make_lock(protection), protection.level
        self._identities[ident.fingerprint] = ident
        return ident.view()

    def _identity(self, fingerprint: str) -> _Identity:
        try:
            return self._identities[fingerprint]
        except KeyError:
            raise errors.NotFound() from None

    def change_protection(self, fingerprint, current_passphrase, protection):
        ident = self._identity(fingerprint)
        ident.unlock(current_passphrase)
        self._check_protection(protection)
        ident.lock, ident.level = _make_lock(protection), protection.level
        return ident.view()

    @staticmethod
    def _write_new(dst: Path, data: bytes) -> None:
        try:
            with open(dst, "xb") as f:  # « x » : jamais d'écrasement (§ 8)
                f.write(data)
        except FileExistsError as exc:
            raise errors.FileExists(name=dst.name) from exc

    def _public_pem(self, ident: _Identity) -> bytes:
        payload = json.dumps({"id": ident.key_id.hex(), "type": ident.key_type}).encode()
        return (_PUB[0] + base64.b64encode(payload).decode() + _PUB[1]).encode()

    def export_public_key(self, fingerprint, dst):
        self._write_new(dst, self._public_pem(self._identity(fingerprint)))

    def export_private_key(self, fingerprint, dst):
        self._write_new(dst, self._identity(fingerprint).private_file())

    def delete_identity(self, fingerprint):
        self._identities.pop(fingerprint, None)

    # ----------------------------------------------------------------- contacts
    def list_contacts(self):
        return sorted(
            (KeyView(n, _kind(t), fpr) for fpr, (n, t, _p) in self._contacts.items()),
            key=lambda v: v.name.lower(),
        )

    def add_contact(self, name, public_pem):
        text = public_pem.decode("utf-8", "replace").strip() + "\n"
        try:
            if not (text.startswith(_PUB[0]) and text.endswith(_PUB[1])):
                raise ValueError
            d = json.loads(base64.b64decode(text[len(_PUB[0]) : -len(_PUB[1])], validate=True))
            key_id, key_type = bytes.fromhex(d["id"]), d["type"]
            if key_type not in KEY_TYPES:
                raise ValueError
        except (ValueError, KeyError, TypeError) as exc:
            raise errors.InvalidPublicKey() from exc
        fpr = _fingerprint(key_id)
        if fpr in self._contacts:
            raise errors.AlreadyExists("error.contact_key_taken", name=self._contacts[fpr][0])
        self._contacts[fpr] = (name, key_type, public_pem)
        return KeyView(name, _kind(key_type), fpr)

    def rename_contact(self, fingerprint, new_name):
        if fingerprint not in self._contacts:
            raise errors.NotFound()
        _old, key_type, pem = self._contacts[fingerprint]
        self._contacts[fingerprint] = (new_name, key_type, pem)

    def remove_contact(self, fingerprint):
        self._contacts.pop(fingerprint, None)

    # ----------------------------------------------------------------- chiffrer
    def measure_speed(self) -> float:
        if self._speed:
            return self._speed
        data = bytes(16 * 1024 * 1024)
        start = time.perf_counter()
        hashlib.sha256(data).digest()
        self._speed = len(data) / max(time.perf_counter() - start, 1e-6)
        return self._speed

    def _recipient(self, fingerprint: str) -> tuple[bytes, str]:
        if fingerprint in self._contacts:
            _n, key_type, pem = self._contacts[fingerprint]
            text = pem.decode().strip() + "\n"
            d = json.loads(base64.b64decode(text[len(_PUB[0]) : -len(_PUB[1])]))
            return bytes.fromhex(d["id"]), key_type
        if fingerprint in self._identities:
            ident = self._identities[fingerprint]
            return ident.key_id, ident.key_type
        raise errors.NotFound("error.recipient_not_found")

    def encrypt(self, src, dst, recipient, cipher, progress):
        key_id, key_type = self._recipient(recipient)
        if cipher not in ("aes-256-gcm", "aes-128-gcm"):
            raise errors.BadInput("error.unknown_setting")
        tmp_zip = None
        is_folder = src.is_dir()
        try:
            if is_folder:  # § 5.4 : zip temporaire, supprimé juste après
                tmp_zip = dst.with_name(f".{dst.name}.dossier.part")
                zip_folder(src, tmp_zip)
                source, name = tmp_zip, src.name + ".zip"
            else:
                source, name = src, src.name
            wrap = "rsa-oaep-sha256" if key_type.startswith("rsa") else "x25519-hkdf-sha256"
            header = json.dumps({
                "format": "crypteasy", "version": _VERSION, "demo": True,
                "key_type": key_type, "key_wrap": wrap,
                "recipient_fingerprint": _fingerprint(key_id),
                "cipher": cipher, "chunk_size": _CHUNK, "is_folder": is_folder,
            }).encode()  # fmt: skip
            raw_name = name.encode("utf-8")
            total = source.stat().st_size
            mac = hashlib.sha256(header + raw_name)
            part = dst.with_name(f".{dst.name}.part")
            try:
                with zipfile.ZipFile(part, "w", compression=zipfile.ZIP_STORED) as zf:
                    zf.writestr("key.enc", json.dumps({"demo": True, "key_id": key_id.hex()}))
                    with (
                        zf.open("file.enc", "w", force_zip64=True) as out,
                        open(source, "rb") as fin,
                    ):
                        out.write(
                            _MAGIC + bytes([_VERSION]) + struct.pack(">I", len(header)) + header
                        )
                        out.write(struct.pack(">H", len(raw_name)) + raw_name)
                        done = 0
                        progress(0, total)
                        while block := fin.read(_CHUNK):
                            mac.update(block)
                            out.write(block)
                            done += len(block)
                            progress(done, total)
                        out.write(mac.digest())
                if dst.exists():
                    raise errors.FileExists(name=dst.name)
                os.replace(part, dst)
            finally:
                part.unlink(missing_ok=True)
        finally:
            if tmp_zip is not None:
                tmp_zip.unlink(missing_ok=True)

    # ----------------------------------------------------------------- déchiffrer
    @staticmethod
    def _open_package(package: Path) -> zipfile.ZipFile:
        with open(package, "rb") as f:
            if f.read(2) != b"PK":
                raise errors.UnsupportedFormat()
        try:
            zf = zipfile.ZipFile(package)
        except zipfile.BadZipFile as exc:
            raise errors.CorruptedFile() from exc
        names = {i.filename for i in zf.infolist()}
        if not {"key.enc", "file.enc"} <= names or not names <= {
            "key.enc",
            "file.enc",
            "signature.sig",
        }:
            zf.close()
            raise errors.UnsupportedFormat()
        return zf

    @staticmethod
    def _read_header(fin) -> tuple[bytes, dict]:
        if fin.read(len(_MAGIC)) != _MAGIC:
            raise errors.UnsupportedFormat()
        if fin.read(1) != bytes([_VERSION]):
            raise errors.UnsupportedFormat()
        try:
            (length,) = struct.unpack(">I", fin.read(4))
            if length > _MAX_HEADER:
                raise errors.CorruptedFile()
            raw = fin.read(length)
            header = json.loads(raw)
        except (struct.error, ValueError) as exc:
            raise errors.CorruptedFile() from exc
        if header.get("format") != "crypteasy" or header.get("version") != _VERSION:
            raise errors.UnsupportedFormat()
        return raw, header

    def inspect_package(self, package):
        with self._open_package(package) as zf, zf.open("file.enc") as fin:
            _raw, h = self._read_header(fin)
        try:
            return PackageInfo(
                h["recipient_fingerprint"], bool(h["is_folder"]), h["key_type"], h["cipher"]
            )
        except KeyError as exc:
            raise errors.CorruptedFile() from exc

    def decrypt(self, package, out_dir, passphrase, progress, identity=None, key_file=None):
        info = self.inspect_package(package)
        if key_file is not None:
            ident = _Identity.from_private_file("importée", key_file.read_bytes())
        else:
            ident = self._identities.get(identity or info.recipient_fingerprint)
            if ident is None:
                raise errors.NoMatchingKey()
        if ident.fingerprint != info.recipient_fingerprint:
            raise errors.NoMatchingKey()
        ident.unlock(passphrase)

        out_dir.mkdir(parents=True, exist_ok=True)
        tmp = out_dir / f".partial-{os.urandom(4).hex()}"
        complete = False
        try:
            with self._open_package(package) as zf:
                if zf.getinfo("key.enc").file_size > _MAX_KEY_ENC:
                    raise errors.CorruptedFile()
                try:
                    if json.loads(zf.read("key.enc")).get("key_id") != ident.key_id.hex():
                        raise errors.CorruptedFile()
                except ValueError as exc:
                    raise errors.CorruptedFile() from exc
                total = zf.getinfo("file.enc").file_size
                with zf.open("file.enc") as fin, open(tmp, "wb") as fout:
                    raw_header, _h = self._read_header(fin)
                    try:
                        (name_len,) = struct.unpack(">H", fin.read(2))
                    except struct.error as exc:
                        raise errors.CorruptedFile() from exc
                    raw_name = fin.read(name_len)
                    mac = hashlib.sha256(raw_header + raw_name)
                    offset = len(_MAGIC) + 1 + 4 + len(raw_header) + 2 + name_len
                    remaining = total - offset - 32
                    if remaining < 0:
                        raise errors.CorruptedFile()
                    done = 0
                    while remaining:
                        block = fin.read(min(_CHUNK, remaining))
                        if not block:
                            raise errors.CorruptedFile()
                        mac.update(block)
                        fout.write(block)
                        remaining -= len(block)
                        done += len(block)
                        progress(done, total)
                    if not hmac.compare_digest(mac.digest(), fin.read(32)):
                        raise errors.CorruptedFile()
            complete = True
        except zipfile.BadZipFile as exc:  # CRC du zip faux, etc.
            raise errors.CorruptedFile() from exc
        finally:
            if not complete:  # jamais de déchiffré partiel sur le disque
                tmp.unlink(missing_ok=True)
        try:
            name = original_name(raw_name.decode("utf-8"))
        except UnicodeDecodeError:
            name = original_name(None)
        final = out_dir / name
        os.replace(tmp, final)
        return final

    def extract_folder(self, zip_path, parent):
        return extract_folder(zip_path, parent)

    # ----------------------------------------------------------------- réglages
    def load_settings(self):
        return dict(self._settings)

    def save_settings(self, settings):
        self._settings = dict(settings)
