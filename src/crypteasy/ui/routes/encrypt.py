"""Écran « Chiffrer » (F4) : fichier + destinataire (contact ou une de mes clés) +
réglages de sécurité (§ 4, défaut = recommandé) → téléchargement d'un paquet .zip.

Le paquet porte un nom neutre (D7) : le vrai nom voyage chiffré à l'intérieur.
"""

from datetime import datetime

from flask import Blueprint, render_template, request

from ..errors import BadInput, user_message
from ..files import new_job, remove_job, safe_filename, save_upload
from ..security_levels import (
    CIPHERS,
    DEFAULT_CIPHER,
    DEFAULT_KDF,
    DEFAULT_KDF_STRENGTH,
    DEFAULT_SALT,
    KDF_STRENGTHS,
    KDFS,
    SALT_LENGTHS,
    EncryptOptions,
    rate,
    rules_json,
)
from . import attachment, backend

bp = Blueprint("encrypt", __name__, url_prefix="/chiffrer")
EXT = ".zip"


def output_name(raw: str | None) -> str:
    raw = (raw or "").strip()
    if not raw:
        return f"encrypted_{datetime.now():%Y%m%d-%H%M%S}{EXT}"
    name = safe_filename(raw)
    return name if name.lower().endswith(EXT) else name + EXT


def _recipients():
    b = backend()
    return b.list_contacts(), b.list_identities()


def _rating(form, contacts, identities):
    """Note des réglages choisis (affichage initial ; la page la recalcule en direct)."""
    kinds = {k.fingerprint: k.kind for k in [*contacts, *identities]}
    recipient = form.get("recipient") or request.args.get("contact", "")
    choices = {"cipher": form.get("cipher") or DEFAULT_CIPHER}
    if recipient in kinds:
        choices["key_type"] = kinds[recipient].lower()
    if form.get("use_password"):
        choices.update(
            kdf=form.get("kdf") or DEFAULT_KDF,
            kdf_strength=form.get("kdf_strength") or DEFAULT_KDF_STRENGTH,
            salt=form.get("salt") or DEFAULT_SALT,
        )
    return rate(choices)


def _page(error=None, status=200):
    contacts, identities = _recipients()
    form = request.form
    safe = {
        k: form.get(k, "")
        for k in ("recipient", "out_name", "cipher", "use_password", "kdf", "kdf_strength", "salt")
    }
    return render_template(
        "encrypt.html",
        contacts=contacts,
        identities=identities,
        ext=EXT,
        error=error,
        selected=form.get("recipient") or request.args.get("contact", ""),
        form=safe,
        ciphers=CIPHERS,
        kdfs=KDFS,
        kdf_strengths=KDF_STRENGTHS,
        salts=SALT_LENGTHS,
        defaults={
            "cipher": DEFAULT_CIPHER,
            "kdf": DEFAULT_KDF,
            "kdf_strength": DEFAULT_KDF_STRENGTH,
            "salt": DEFAULT_SALT,
        },
        rating=_rating(form, contacts, identities),
        rules=rules_json(),
        min_pw=backend().min_password_length,
    ), status


def parse_options(form) -> EncryptOptions:
    def pick(field, choices, default):
        value = form.get(field) or default
        if value not in choices:
            raise BadInput("Réglage de sécurité inconnu.")
        return value

    cipher = pick("cipher", CIPHERS, DEFAULT_CIPHER)
    if not form.get("use_password"):
        return EncryptOptions(cipher=cipher)

    password = form.get("file_password", "")
    if not password:
        raise BadInput("Saisissez le mot de passe supplémentaire, ou désactivez l'option.")
    if password != form.get("file_password2", ""):
        raise BadInput("Les deux mots de passe du fichier ne correspondent pas.")
    kdf = pick("kdf", KDFS, DEFAULT_KDF)
    salt = pick("salt", SALT_LENGTHS, DEFAULT_SALT)
    if salt == "0" and kdf == "argon2id":
        raise BadInput("Argon2id exige un sel : choisissez 16 ou 32 octets, ou PBKDF2.")
    return EncryptOptions(
        cipher=cipher,
        password=password.encode("utf-8"),
        kdf=kdf,
        kdf_strength=pick("kdf_strength", KDF_STRENGTHS, DEFAULT_KDF_STRENGTH),
        salt_len=int(salt),
    )


@bp.get("")
def index():
    return _page()


@bp.post("")
def run():
    job = new_job()
    try:
        recipient = request.form.get("recipient", "")
        if not recipient:
            raise BadInput("Choisissez un destinataire.")
        options = parse_options(request.form)
        out_name = output_name(request.form.get("out_name"))
        src = save_upload(request.files.get("file"), job / "in")
        dst = job / "out" / out_name
        dst.parent.mkdir()
        backend().encrypt_file(src, dst, recipient, options)
        src.unlink()  # le clair n'a plus rien à faire sur le disque
        return attachment(dst, out_name, cleanup=lambda: remove_job(job))
    except Exception as exc:  # traduit en message par user_message
        remove_job(job)
        return _page(user_message(exc), 400)
