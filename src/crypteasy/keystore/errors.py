"""Exceptions raised by keystore/. The UI turns them into translated messages."""


class KeystoreError(Exception):
    """Base class for every keystore error."""


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


class WrongPassphraseError(KeystoreError):
    """The passphrase does not unlock this private key."""


class InvalidPrivateKeyError(KeystoreError):
    """Not a CryptEasy private.key file, an unknown version, or unsafe parameters."""


class InvalidPublicKeyError(KeystoreError):
    """Not a valid CryptEasy public key PEM."""
