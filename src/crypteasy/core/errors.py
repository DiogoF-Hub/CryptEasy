"""
In this file I define all the errors that core/ can raise
"""

# Each error below is just a NAME for something that can go wrong. core/ never shows a
# message to the user itself, the chain is:
#   1. core/ raises one of these errors, e.g. raise WrongPassphraseError("...")
#   2. ui/backend.py catches it and finds it by its name in its _CORE_ERRORS list
#   3. it turns it into the interface's own error, which holds a translation key
#      (e.g. "error.wrong_passphrase")
#   4. the interface looks that key up in translations/fr.json or en.json, depending on
#      the language chosen by the user, and shows the sentence on screen
#
# So the text I give when raising an error (e.g. "Incorrect password...") is only for us
# developers (tests, logs), it's never shown in the app.
# The names must not change: ui/backend.py looks them up by name.
#
# In Python an error has to be written as a class that comes from Exception.
# There is nothing inside them, so "pass" just means "nothing to add".


# The base of every CryptEasy error
# Never raised directly, it only lets the code catch "any CryptEasy error" at once
class CryptEasyError(Exception):
    pass


# A public key file is not valid, or the key type is not supported
class InvalidKeyError(CryptEasyError):
    pass


# A private key file is not valid, or the key type is not supported
class InvalidPrivateKeyError(CryptEasyError):
    pass


# The passphrase does not unlock the private key (or it's missing)
class WrongPassphraseError(CryptEasyError):
    pass


# The package was not encrypted for any of the available keys
class NoMatchingKeyError(CryptEasyError):
    pass


# Not a CryptEasy package, or a package made by a newer version
class UnsupportedFormatError(CryptEasyError):
    pass


# The package is damaged or was modified, so nothing was decrypted
class DecryptionError(CryptEasyError):
    pass


# A decrypted folder is abnormally large once extracted (zip bomb guard)
class ExtractionTooLargeError(CryptEasyError):
    pass
