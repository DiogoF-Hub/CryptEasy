"""Erreurs côté interface et LE seul endroit qui les traduit en messages (SPEC § F7).

Les routes n'attrapent jamais les exceptions de core/ ou keystore/ directement :
ui/backend.py les convertit en exceptions ci-dessous, les routes affichent
user_message(exc). Chaque erreur porte une CLÉ de traduction (translations/*.json),
jamais un texte en dur.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class UIError(Exception):
    """Erreur dont le message peut être montré à l'utilisateur.

    key    : clé de traduction du message
    params : valeurs insérées dans le message (ex. {"name": "Alice"})
    """

    key = "error.generic"

    def __init__(self, key: str | None = None, **params: object) -> None:
        super().__init__(key or self.key)
        self.key = key or self.key
        self.params = params


# --- F7 : messages imposés par la spec -----------------------------------------
class WrongPassphrase(UIError):
    key = "error.wrong_passphrase"


class NoMatchingKey(UIError):
    key = "error.no_matching_key"


class CorruptedFile(UIError):
    key = "error.corrupted"


class UnsupportedFormat(UIError):
    key = "error.unsupported_format"


class InvalidPublicKey(UIError):
    key = "error.invalid_public_key"


class InvalidPrivateKey(UIError):
    key = "error.invalid_private_key"


class ExtractionTooLarge(UIError):
    key = "error.extraction_too_large"


class UnsafeArchive(UIError):
    """Dossier déchiffré contenant un chemin dangereux (../, absolu, lien symbolique)."""

    key = "error.unsafe_archive"


# --- Autres erreurs de l'interface -----------------------------------------------
class FileExists(UIError):
    key = "error.file_exists"


class NotFound(UIError):
    key = "error.not_found"


class AlreadyExists(UIError):
    key = "error.already_exists"


class WeakPassphrase(UIError):
    key = "error.passphrase_too_short"


class BadInput(UIError):
    """Formulaire mal rempli (champ vide, nom invalide…)."""

    key = "error.bad_input"


def user_message(exc: BaseException) -> str:
    """Message traduit. Pour une erreur imprévue : message générique, et on ne journalise
    que le TYPE de l'exception (jamais son contenu, qui pourrait contenir des données)."""
    from .i18n import t

    if isinstance(exc, UIError):
        return t(exc.key, **exc.params)
    log.error("Erreur inattendue : %s", type(exc).__name__)
    return t("error.unexpected")
