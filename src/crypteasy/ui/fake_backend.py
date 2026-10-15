"""FakeBackend : backend factice pour les tests et le développement.

AUCUNE SÉCURITÉ : le contenu n'est PAS chiffré. Il imite le comportement attendu
du vrai moteur (SPEC_TECHNIQUE § 5) pour que l'interface et tous les cas d'erreur
F7 soient testables : paquet .zip (manifest.json, key.enc, file.enc), empreinte
du destinataire dans le manifest, mot de passe supplémentaire, détection de
modification, nom d'origine caché dans file.enc et assaini au déchiffrement.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import zipfile
from pathlib import Path

from . import errors
from .backend import KeyView
from .files import safe_filename
from .security_levels import CIPHERS, KDF_STRENGTHS, KDFS, KEY_TYPES, EncryptOptions

_PUB = ("-----BEGIN CRYPTEASY DEMO PUBLIC KEY-----\n", "\n-----END CRYPTEASY DEMO PUBLIC KEY-----\n")
_PRIV = ("-----BEGIN CRYPTEASY DEMO ENCRYPTED PRIVATE KEY-----\n",
         "\n-----END CRYPTEASY DEMO ENCRYPTED PRIVATE KEY-----\n")
_NAMES = {"manifest.json", "key.enc", "file.enc"}
_CHUNK = 64 * 1024
_MAX_SMALL = 64 * 1024          # manifest.json et key.enc
_BLOCKLIST = {"motdepasse123", "password1234", "azertyuiop12", "123456789012"}


def _kind(key_type: str) -> str:
    return key_type.upper()     # "x25519" → "X25519", "rsa-3072" → "RSA-3072"


def _fingerprint(key_id: bytes) -> str:
    h = hashlib.sha256(key_id).hexdigest().upper()
    return " ".join(h[i:i + 4] for i in range(0, 64, 4))      # 16 groupes de 4 (§ 6.3)


def _wrap(markers, obj: dict) -> bytes:
    return (markers[0] + base64.b64encode(json.dumps(obj).encode()).decode() + markers[1]).encode()


def _unwrap(markers, pem: bytes, err: type[errors.UIError]) -> dict:
    text = pem.decode("utf-8", "replace").strip() + "\n"
    if not (text.startswith(markers[0]) and text.endswith(markers[1])):
        raise err()
    try:
        return json.loads(base64.b64decode(text[len(markers[0]):-len(markers[1])], validate=True))
    except (ValueError, TypeError) as exc:
        raise err() from exc


class _Identity:
    def __init__(self, name: str, key_type: str, key_id: bytes, salt: bytes, pw_hash: bytes):
        self.name, self.key_type, self.key_id, self.salt, self.pw_hash = name, key_type, key_id, salt, pw_hash

    def check(self, password: bytes) -> None:
        if not hmac.compare_digest(hashlib.sha256(self.salt + password).digest(), self.pw_hash):
            raise errors.WrongPassword()

    def view(self) -> KeyView:
        return KeyView(self.name, _kind(self.key_type), _fingerprint(self.key_id))

    def private_pem(self) -> bytes:
        return _wrap(_PRIV, {"id": self.key_id.hex(), "type": self.key_type,
                             "salt": self.salt.hex(), "pw": self.pw_hash.hex()})

    @classmethod
    def from_private_pem(cls, name: str, pem: bytes) -> "_Identity":
        d = _unwrap(_PRIV, pem, errors.InvalidPrivateKey)
        try:
            return cls(name, d["type"], bytes.fromhex(d["id"]), bytes.fromhex(d["salt"]),
                       bytes.fromhex(d["pw"]))
        except (KeyError, ValueError) as exc:
            raise errors.InvalidPrivateKey() from exc


class FakeBackend:
    demo = True
    min_password_length = 12                        # D5
    key_protection_kdfs = dict(KDFS)                # D4 pas encore tranchée : on propose le choix

    def __init__(self) -> None:
        self._identities: dict[str, _Identity] = {}            # empreinte → identité
        self._contacts: dict[str, tuple[str, str, bytes]] = {}  # empreinte → (nom, type, pem)

    # ------------------------------------------------------------ mots de passe
    def _check_new_password(self, password: bytes) -> None:
        text = password.decode("utf-8", "replace")
        if len(text) < self.min_password_length:
            raise errors.WeakPassword(
                f"Le mot de passe doit faire au moins {self.min_password_length} caractères.")
        if text.lower() in _BLOCKLIST:
            raise errors.WeakPassword("Ce mot de passe est trop courant.")

    def _check_new_name(self, name: str) -> None:
        if any(i.name == name for i in self._identities.values()):
            raise errors.AlreadyExists(f"Vous avez déjà une clé nommée « {name} ».")

    # ------------------------------------------------------------ mes clés
    def list_identities(self) -> list[KeyView]:
        return sorted((i.view() for i in self._identities.values()), key=lambda v: v.name.lower())

    def create_identity(self, name, key_type, password, kdf=None):
        if key_type not in KEY_TYPES:
            raise errors.BadInput("Type de clé inconnu.")
        if kdf is not None and kdf not in self.key_protection_kdfs:
            raise errors.BadInput("Méthode de protection inconnue.")
        self._check_new_password(password)
        self._check_new_name(name)
        salt = os.urandom(16)
        ident = _Identity(name, key_type, os.urandom(16), salt, hashlib.sha256(salt + password).digest())
        self._identities[ident.view().fingerprint] = ident
        return ident.view()

    def import_private_key(self, name, pem, password):
        ident = _Identity.from_private_pem(name, pem)
        ident.check(password)
        self._check_new_name(name)
        fpr = ident.view().fingerprint
        if fpr in self._identities:
            raise errors.AlreadyExists(
                f"Cette clé est déjà enregistrée (« {self._identities[fpr].name} »).")
        self._identities[fpr] = ident
        return ident.view()

    def _identity(self, fingerprint: str) -> _Identity:
        try:
            return self._identities[fingerprint]
        except KeyError:
            raise errors.NotFound("Clé introuvable.") from None

    def export_public_key(self, fingerprint):
        i = self._identity(fingerprint)
        return _wrap(_PUB, {"id": i.key_id.hex(), "type": i.key_type})

    def export_private_key(self, fingerprint):
        return self._identity(fingerprint).private_pem()

    def delete_identity(self, fingerprint):
        self._identities.pop(fingerprint, None)

    # ------------------------------------------------------------ contacts
    def list_contacts(self):
        return sorted((KeyView(n, _kind(t), fpr) for fpr, (n, t, _p) in self._contacts.items()),
                      key=lambda v: v.name.lower())

    def add_contact(self, name, public_pem):
        d = _unwrap(_PUB, public_pem, errors.InvalidKey)
        if d.get("type") not in KEY_TYPES:
            raise errors.InvalidKey()
        fpr = _fingerprint(bytes.fromhex(d["id"]))
        if fpr in self._contacts:
            raise errors.AlreadyExists(
                f"Cette clé est déjà enregistrée (contact « {self._contacts[fpr][0]} »).")
        self._contacts[fpr] = (name, d["type"], public_pem)
        return KeyView(name, _kind(d["type"]), fpr)

    def rename_contact(self, fingerprint, new_name):
        if fingerprint not in self._contacts:
            raise errors.NotFound("Contact introuvable.")
        _old, key_type, pem = self._contacts[fingerprint]
        self._contacts[fingerprint] = (new_name, key_type, pem)

    def remove_contact(self, fingerprint):
        self._contacts.pop(fingerprint, None)

    # ------------------------------------------------------------ chiffrer (§ 5.2)
    def _recipient(self, fingerprint: str) -> tuple[bytes, str]:
        if fingerprint in self._contacts:
            d = _unwrap(_PUB, self._contacts[fingerprint][2], errors.InvalidKey)
            return bytes.fromhex(d["id"]), d["type"]
        if fingerprint in self._identities:
            i = self._identities[fingerprint]
            return i.key_id, i.key_type
        raise errors.NotFound("Destinataire introuvable.")

    def encrypt_file(self, src, dst, recipient_fingerprint, options: EncryptOptions):
        key_id, key_type = self._recipient(recipient_fingerprint)
        if options.cipher not in CIPHERS or options.kdf not in KDFS \
                or options.kdf_strength not in KDF_STRENGTHS or options.salt_len not in (0, 16, 32):
            raise errors.BadInput("Réglage de sécurité inconnu.")
        if options.password is not None and options.salt_len == 0 and options.kdf == "argon2id":
            raise errors.BadInput("Argon2id exige un sel.")

        pw_check = None
        password_info = None
        if options.password is not None:
            salt = os.urandom(options.salt_len)
            pw_check = hashlib.sha256(salt + options.password).hexdigest()
            password_info = {"kdf": options.kdf, "salt": base64.b64encode(salt).decode() or None,
                             "params": {"preset": options.kdf_strength}}
        manifest = json.dumps({
            "format": "crypteasy", "version": 1, "demo": True,
            "key_type": key_type,
            "key_wrap": "rsa-oaep-sha256" if key_type.startswith("rsa") else "x25519-hkdf-sha256",
            "recipient_fingerprint": _fingerprint(key_id),
            "cipher": options.cipher, "chunk_size": _CHUNK, "password": password_info,
        }, indent=2).encode()
        key_enc = json.dumps({"key_id": key_id.hex(), "pw_check": pw_check}).encode()

        name = src.name.encode("utf-8")
        mac = hashlib.sha256(manifest)
        with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_STORED) as zf:
            zf.writestr("manifest.json", manifest)
            zf.writestr("key.enc", key_enc)
            with zf.open("file.enc", "w", force_zip64=True) as out, open(src, "rb") as fin:
                head = struct.pack(">H", len(name)) + name
                mac.update(head)
                out.write(head)
                while block := fin.read(_CHUNK):
                    mac.update(block)
                    out.write(block)
                out.write(mac.digest())

    # ------------------------------------------------------------ déchiffrer (§ 5.3)
    def decrypt_file(self, src, out_dir, *, key_password, file_password=None,
                     identity_fingerprint=None, private_pem=None):
        # Quelle clé ? (enregistrée, ou importée pour cette fois)
        if private_pem is not None:
            ident = _Identity.from_private_pem("importée", private_pem)
            ident.check(key_password)        # une clé importée doit être ouverte pour connaître son empreinte
        else:
            ident = self._identity(identity_fingerprint or "")

        # 1. Ouvrir le zip SANS extraire : exactement les 3 noms attendus, tailles bornées
        with open(src, "rb") as f:
            if f.read(2) != b"PK":
                raise errors.UnsupportedFormat()
        try:
            zf = zipfile.ZipFile(src)
        except zipfile.BadZipFile as exc:
            raise errors.CorruptedFile() from exc
        with zf:
            infos = {i.filename: i for i in zf.infolist()}
            if set(infos) != _NAMES or len(zf.infolist()) != 3:
                raise errors.UnsupportedFormat()
            if infos["manifest.json"].file_size > _MAX_SMALL or infos["key.enc"].file_size > _MAX_SMALL:
                raise errors.CorruptedFile()
            # 2. Manifest : format et version connus
            manifest_raw = zf.read("manifest.json")
            try:
                manifest = json.loads(manifest_raw)
            except ValueError as exc:
                raise errors.CorruptedFile() from exc
            if manifest.get("format") != "crypteasy" or manifest.get("version") != 1:
                raise errors.UnsupportedFormat()
            # 3. Empreinte du destinataire
            if manifest.get("recipient_fingerprint") != ident.view().fingerprint:
                raise errors.WrongRecipient()
            # 4. Déverrouiller la clé privée
            ident.check(key_password)
            # 5-6. Clé du fichier et mot de passe supplémentaire
            try:
                key_enc = json.loads(zf.read("key.enc"))
            except ValueError as exc:
                raise errors.CorruptedFile() from exc
            if key_enc.get("key_id") != ident.key_id.hex():
                raise errors.CorruptedFile()
            if manifest.get("password"):
                if not file_password:
                    raise errors.FilePasswordRequired()
                salt = base64.b64decode(manifest["password"].get("salt") or "")
                if hashlib.sha256(salt + file_password).hexdigest() != key_enc.get("pw_check"):
                    raise errors.WrongFilePassword()
            # 7. Déchiffrer par blocs dans un fichier temporaire
            out_dir.mkdir(parents=True, exist_ok=True)
            tmp = out_dir / (".partial-" + os.urandom(4).hex())
            complete = False
            try:
                total = infos["file.enc"].file_size
                with zf.open("file.enc") as fin, open(tmp, "wb") as fout:
                    try:
                        head = fin.read(2)
                        (name_len,) = struct.unpack(">H", head)
                        raw_name = fin.read(name_len)
                    except struct.error as exc:
                        raise errors.CorruptedFile() from exc
                    mac = hashlib.sha256(manifest_raw + head + raw_name)
                    remaining = total - 2 - name_len - 32
                    if remaining < 0:
                        raise errors.CorruptedFile()
                    while remaining:
                        block = fin.read(min(_CHUNK, remaining))
                        if not block:
                            raise errors.CorruptedFile()
                        mac.update(block)
                        fout.write(block)
                        remaining -= len(block)
                    if not hmac.compare_digest(mac.digest(), fin.read(32)):
                        raise errors.CorruptedFile()
                complete = True
            except zipfile.BadZipFile as exc:           # CRC zip faux, etc.
                raise errors.CorruptedFile() from exc
            finally:
                if not complete:                        # jamais de déchiffré partiel sur le disque
                    tmp.unlink(missing_ok=True)
            # 8. Nom d'origine assaini (§ 8), repli « decrypted_file », jamais d'écrasement
            final = out_dir / _safe_original_name(raw_name)
            if final.exists():
                tmp.unlink(missing_ok=True)
                raise errors.CorruptedFile()
            os.replace(tmp, final)
            return final


def _safe_original_name(raw: bytes) -> str:
    if b"\x00" in raw:
        return "decrypted_file"
    try:
        return safe_filename(raw.decode("utf-8"))
    except (UnicodeDecodeError, errors.BadInput):
        return "decrypted_file"
