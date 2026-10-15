"""Erreurs côté interface et LE seul endroit qui les traduit en messages.

Textes repris de SPEC_TECHNIQUE.md, F7.

Les routes n'attrapent jamais les exceptions de core/ ou keystore/ directement :
ui/backend.py les convertit en exceptions ci-dessous, les routes affichent
user_message(exc).
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

UNEXPECTED = "Erreur inattendue. Réessayez ; si le problème persiste, signalez-le."


class UIError(Exception):
    """Erreur dont le message peut être montré tel quel à l'utilisateur."""
    default = "Opération impossible."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default)


class WrongPassword(UIError):
    default = "Mot de passe incorrect pour cette clé."


class WrongRecipient(UIError):
    default = "Ce fichier n'a pas été chiffré pour cette clé."


class WrongFilePassword(UIError):
    default = "Mot de passe du fichier incorrect."


class FilePasswordRequired(UIError):
    default = ("Ce fichier est protégé par un mot de passe supplémentaire : "
               "saisissez-le dans « Mot de passe du fichier ».")


class CorruptedFile(UIError):
    default = "Ce fichier est endommagé ou a été modifié. Rien n'a été déchiffré."


class UnsupportedFormat(UIError):
    default = ("Ce n'est pas un fichier CryptEasy, "
               "ou il a été créé par une version plus récente.")


class InvalidKey(UIError):
    default = "Ce n'est pas une clé publique valide."


class InvalidPrivateKey(UIError):
    default = "Ce n'est pas une clé privée valide."


class NotFound(UIError):
    default = "Élément introuvable."


class AlreadyExists(UIError):
    default = "Cet élément existe déjà."


class WeakPassword(UIError):
    default = "Mot de passe trop faible."


class BadInput(UIError):
    """Formulaire mal rempli (champ vide, nom invalide…)."""
    default = "Formulaire incomplet."


def user_message(exc: BaseException) -> str:
    """Message à afficher. Pour une erreur imprévue : message générique, et on ne
    journalise que le TYPE (jamais le contenu, qui pourrait contenir des données)."""
    if isinstance(exc, UIError):
        return str(exc)
    log.error("Erreur inattendue : %s", type(exc).__name__)
    return UNEXPECTED
