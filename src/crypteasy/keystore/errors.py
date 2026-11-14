"""Exceptions raised by keystore/. The UI turns them into translated messages.

The three key errors are core/'s own classes (core/errors.py), so a wrong passphrase or
a bad key file is the same error whether core/ or keystore/ spotted it, and
ui/backend.py's _CORE_ERRORS already maps them.
"""

from crypteasy.core.errors import InvalidKeyError as InvalidPublicKeyError
from crypteasy.core.errors import InvalidPrivateKeyError, WrongPassphraseError

__all__ = [
    "AlreadyExistsError",
    "CorruptedStoreError",
    "InvalidNameError",
    "InvalidPrivateKeyError",
    "InvalidPublicKeyError",
    "InvalidSettingError",
    "KeystoreError",
    "NotFoundError",
    "WrongPassphraseError",
]


class KeystoreError(Exception):
    """Base class for the keystore-only errors below."""


class NotFoundError(KeystoreError):
    """No key pair or contact with this fingerprint."""


class AlreadyExistsError(KeystoreError):
    """The name or the key is already in the store."""


class InvalidNameError(KeystoreError):
    """Empty, too long, or contains control characters."""


class InvalidSettingError(KeystoreError):
    """Unknown key type, KDF, salt length or level."""


class CorruptedStoreError(KeystoreError):
    """A stored file (contacts.json, info.json, public.pem) is damaged or was edited by hand."""
