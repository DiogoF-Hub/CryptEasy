import re

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa, x25519

from crypteasy.core.errors import InvalidKeyError, InvalidPrivateKeyError, WrongPassphraseError

"""
In this file I have everything about the keys: creating a key pair, the fingerprint,
and saving / loading the keys as PEM files
"""

# This is a list of the key types offered in the app (same names as the interface)
# x25519 is an elliptic curve key, the default one. Small, fast, about as strong as RSA-3072
# For rsa-xxxx the number is the key size in bits
key_types = ["x25519", "rsa-2048", "rsa-3072", "rsa-4096"]

# This is a dictionary: for each RSA key type (the key) it gives its size in bits (the value)
# e.g. rsa_sizes["rsa-3072"] gives 3072
# Below 2048 bits RSA is considered breakable, so smaller keys are never accepted
rsa_sizes = {"rsa-2048": 2048, "rsa-3072": 3072, "rsa-4096": 4096}

# These are 2 lists of the PEM labels accepted when loading a file,
# one for public key files and one for private key files
# A PEM file is just text, each key sits between "-----BEGIN <label>-----" and
# "-----END <label>-----", and the label says what's inside:
# - "PUBLIC KEY": standard public key (any type)
# - "RSA PUBLIC KEY": older RSA only format, still made by some tools like OpenSSL
# - "PRIVATE KEY": standard private key (PKCS#8), not encrypted
# - "ENCRYPTED PRIVATE KEY": standard private key, protected by a password
# - "RSA PRIVATE KEY": older RSA only format, can be protected by a password too
# The b before the quotes makes these bytes and not normal text (str)
# Key files are handled as raw bytes (like when you open a file with "rb"),
# and bytes can only be compared with bytes, so the labels have to be bytes too
# Example with the word KEY:
# - normal text (str): "KEY"
# - bytes: b"KEY", which Python really keeps as the numbers 75 69 89 (K=75, E=69, Y=89)
# - "KEY" == b"KEY" is False, they are not the same type
# - "KEY".encode() turns the text into bytes, so it gives b"KEY"
public_labels = [b"PUBLIC KEY", b"RSA PUBLIC KEY"]
private_labels = [b"PRIVATE KEY", b"ENCRYPTED PRIVATE KEY", b"RSA PRIVATE KEY"]

# This regex finds one PEM block: -----BEGIN <label>----- ... -----END <label>-----
# [A-Z ]+ is a label: one or more capital letters or spaces (e.g. PUBLIC KEY)
# The ( ) around it make a "capture": the regex remembers that part, so I can get it after
# - the 1st ( ) captures the BEGIN label, I get it with match.group(1)
# - the 2nd ( ) captures the END label, I get it with match.group(2)
# .+? takes the content, the ? makes it stop at the FIRST END it finds and not the last one,
# so a file with 2 keys gives 2 blocks and not 1 big block
# re.DOTALL lets "." also match line breaks, bcs a key is written on several lines
# rb"..." means raw bytes: b = bytes (like the labels), r = raw so the \ stay as they are
# re.compile prepares the regex once here, so it's not rebuilt each time a func uses it
pem_block = re.compile(rb"-----BEGIN ([A-Z ]+)-----.+?-----END ([A-Z ]+)-----", re.DOTALL)


# This func splits a PEM file into its blocks, one block per key
# It returns 2 lists: the label of each block (e.g. b"PUBLIC KEY") and each whole block
# (BEGIN line + content + END line, that's what the cryptography library needs to load a key)
# If the END label of a block isn't the same as its BEGIN label, the file is broken, so for
# that block the label is None, and the func that called this one refuses the file
def split_pem_blocks(pem_data: bytes):
    # labels is a list of the label of each block, full_blocks a list of each whole block
    # Both start empty and get one element for each block found in the file
    labels = []
    full_blocks = []

    # Why a loop: a key file can have more than one key inside
    # - a CryptEasy file (public.pem or the private keys) has 2 keys:
    #   the encryption key (X25519 or RSA) + the Ed25519 signing key
    # - a key made somewhere else (e.g. with OpenSSL) has only 1 key
    # So the loop runs once per key found, and the same code works for both
    #
    # finditer searches pem_data and finds every block matching the regex, one after the other
    # Each time the loop runs, match is the result for one block, and match.group(0)
    # is the text that was found, so the whole block, from -----BEGIN to the last -----
    # e.g. with a CryptEasy public.pem:
    #   loop 1: block = "-----BEGIN PUBLIC KEY-----\n...key 1...\n-----END PUBLIC KEY-----"
    #   loop 2: block = "-----BEGIN PUBLIC KEY-----\n...key 2...\n-----END PUBLIC KEY-----"
    # If the file has no block at all (empty, garbage...) the loop runs 0 times, the lists stay
    # empty, and the func that called this one refuses the file ("must contain 1 or 2 keys")
    # Same if it finds 3 blocks or more
    for match in pem_block.finditer(pem_data):
        # group is a "capture": the regex remembers the part in parentheses, so I can get it
        # after. group(0) is the whole match (automatically captured), group(1) the first
        # part in parentheses, group(2) the second
        # e.g. with the block "-----BEGIN PUBLIC KEY-----\n...key...\n-----END PUBLIC KEY-----":
        # - match.group(0) gives the whole block, from BEGIN to END
        # - match.group(1) gives b"PUBLIC KEY", the label after BEGIN
        # - match.group(2) gives b"PUBLIC KEY", the label after END
        block = match.group(0)
        begin_label = match.group(1)
        end_label = match.group(2)

        # The END label must be the same as the BEGIN label, if not the block is broken
        # e.g. "-----BEGIN PUBLIC KEY----- ... -----END PRIVATE KEY-----" is refused
        if begin_label == end_label:
            labels.append(begin_label)
        else:
            # The block is broken, the func that called this one refuses the file
            # Even if only one of the keys is broken, the whole file is refused,
            # bcs it can't be trusted
            labels.append(None)

        full_blocks.append(block)

    # A tuple of the 2 lists
    return labels, full_blocks


# This func creates a new identity: an encryption key pair (X25519 or RSA)
# plus an Ed25519 key pair used only for signing (spec F1 and F9)
# key_type is one of the key_types list, e.g. "x25519" or "rsa-3072"
# It returns both private keys, the public keys come from them with .public_key()
# The keys are objects of the cryptography library (not bytes yet), to save them in a file
# they go through public_keys_to_pem / private_keys_to_pem
def generate_keypair(key_type: str):

    # 1. Check the key type
    # "not in" checks that key_type is not one of the elements of the list
    # e.g. "rsa-1024" is not in key_types, so it stops here
    # raise stops the func right away and sends the error to the code that called it
    # ', '.join(key_types) puts the list together with ", " between each element, so the
    # message is "Invalid key type! Use one of: x25519, rsa-2048, rsa-3072, rsa-4096"
    # It's a normal ValueError and not a CryptEasy error bcs the interface only offers valid
    # types, so this can only happen if there is a mistake in the code
    if key_type not in key_types:
        raise ValueError(f"Invalid key type! Use one of: {', '.join(key_types)}")

    # 2. Generate the encryption key
    # This is the key that protects the AES key of each file (key.enc)
    # .generate() creates a new random private key, using the secure random of the OS
    # The public key isn't generated separately, it's always computed from the private key
    # For RSA, 65537 is the public exponent everyone uses, it's safe and fast
    # and it's the one the cryptography library recommends
    # rsa_sizes[key_type] gives the size from the dictionary, e.g. rsa_sizes["rsa-3072"] = 3072
    # RSA is slower to generate: RSA-4096 can take up to a second, X25519 is instant
    if key_type == "x25519":
        encryption_key = x25519.X25519PrivateKey.generate()
    else:
        encryption_key = rsa.generate_private_key(
            public_exponent=65537, key_size=rsa_sizes[key_type]
        )

    # 3. Generate the signing key (always Ed25519, even for an RSA identity)
    # X25519 can only encrypt, it can't sign, so every identity gets a second key only to sign
    # I generate it now, from day 1, even if signing comes later
    # Like this adding signing later won't change the keys and contacts that already exist
    signing_key = ed25519.Ed25519PrivateKey.generate()

    # Returning 2 values separated by a comma gives a tuple: (encryption_key, signing_key)
    # The code that calls this func gets both at once: encryption_key, signing_key = ...
    return encryption_key, signing_key


# This func tells me which type an encryption key is ("x25519", "rsa-3072", ...)
# It works with a private or a public key
# If it's not a key we can encrypt with, it returns None
# None is Python's way to say "nothing", the funcs that call this one check it with "is None"
def get_key_type(key):

    # (A, B) is a tuple of the 2 kinds of X25519 key, the private one and the public one
    # isinstance checks what kind of key it is, and with a tuple it checks both kinds at once
    # e.g. isinstance(key, (A, B)) is True if key is an A OR a B
    if isinstance(key, (x25519.X25519PrivateKey, x25519.X25519PublicKey)):
        return "x25519"

    # Same here, a tuple of the 2 kinds of RSA key, private and public
    if isinstance(key, (rsa.RSAPrivateKey, rsa.RSAPublicKey)):
        # key.key_size is the size of the RSA key in bits, e.g. 3072
        # f"rsa-{key.key_size}" puts it in the text, so it gives "rsa-3072"
        # "in rsa_sizes" checks if it's one of the keys of the dictionary
        # Only the sizes we accept, so an RSA-1024 key gives "rsa-1024" which is not in it
        key_type = f"rsa-{key.key_size}"
        if key_type in rsa_sizes:
            return key_type

    # Anything else: Ed25519 (can't encrypt), other curves, RSA-1024, ...
    return None


# This func gives the fingerprint of a public key
# It's the SHA-256 of the key, shown as 16 groups of 4 hex characters, e.g. "3F2A 91C0 ..."
# Same key = same fingerprint on every machine, so people can compare it by phone (spec 6.3)
# -> str after the () means this func returns a text (str)
def get_fingerprint(public_key) -> str:

    # 1. Encode the public key in the standard DER format
    # DER is the binary form of the key, it's the same thing that's inside a PEM file
    # but without the text around it. Using this standard way means the same key always
    # gives the same bytes, so always the same fingerprint
    # SubjectPublicKeyInfo is the standard structure for a public key (it says the key type
    # + the key itself), so an X25519 key and an RSA key can't give the same bytes
    # e.g. for an X25519 key, der is 44 bytes, for an RSA-3072 key around 420 bytes
    der = public_key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # 2. Hash it with SHA-256
    # A hash gives a short "summary" of the key (32 bytes = 64 hex characters)
    # Finding two different keys with the same hash is impossible in practice, so comparing
    # the fingerprints is enough to know you have the right key, without reading the whole key
    # hashes.Hash(hashes.SHA256()) prepares a SHA-256 hash, .update(der) gives it the data,
    # and .finalize() gives the result (32 bytes)
    digest = hashes.Hash(hashes.SHA256())
    digest.update(der)
    # .hex converts the binary hash into a hexadecimal string, easier to read and compare
    # .upper so it's always written the same way, in capital letters
    # e.g. hex_digest = "3F2A91C04B7E..." (64 characters, no spaces yet)
    hex_digest = digest.finalize().hex().upper()

    # 3. Split it into groups of 4 characters, easier to read out loud
    # groups is a list where I put each group of 4 characters, it starts empty
    # range(0, 64, 4) gives 0, 4, 8, ... so each time I take 4 characters
    # hex_digest[i : i + 4] takes the characters from position i to i + 4 (not included)
    # e.g. i = 0 gives "3F2A", i = 4 gives "91C0", ... so groups = ["3F2A", "91C0", ...]
    # " ".join(groups) then puts all the groups together with a space between them
    # e.g. "3F2A 91C0 4B7E ..."
    groups = []
    for i in range(0, len(hex_digest), 4):
        groups.append(hex_digest[i : i + 4])

    return " ".join(groups)


# This func gives the public.pem file people share: the public part of an identity
# The encryption public key comes first, then the signing public key (if there is one)
# signing_public_key=None means that if it's not given, it's None (no signing key)
# -> bytes means this func returns bytes, the content of the file to write
def public_keys_to_pem(encryption_public_key, signing_public_key=None) -> bytes:
    pem_data = b""  # Empty bytes, the keys get added one by one

    # [encryption_public_key, signing_public_key] is a list of the 2 public keys,
    # so the for can go through them one by one, in this order
    # Each key becomes one PEM block, and the blocks are just put one after the other
    # The order matters bcs load_public_keys expects the encryption key first
    # "is not None" skips the signing key when there isn't one
    # .public_bytes(Encoding.PEM, ...) gives the key as a PEM block, e.g.
    # b"-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VuAyEA...\n-----END PUBLIC KEY-----\n"
    # += adds it at the end of pem_data, like adding text to text
    for public_key in [encryption_public_key, signing_public_key]:
        if public_key is not None:
            pem_data += public_key.public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )

    # e.g. with 2 keys, pem_data is 2 blocks one after the other:
    # -----BEGIN PUBLIC KEY----- ... -----END PUBLIC KEY-----   (encryption key)
    # -----BEGIN PUBLIC KEY----- ... -----END PUBLIC KEY-----   (signing key)
    return pem_data


# This func loads a public key file (public.pem) and checks it
# pem_data is the content of the file, in bytes
# It returns the encryption public key and the signing public key
# The signing key is None when the file only has one key (e.g. a key made with OpenSSL)
# If the file isn't good, it raises InvalidKeyError
def load_public_keys(pem_data: bytes):

    # 1. Split the file into its PEM blocks
    # labels is a list of the label of each block, full_blocks a list of each whole block
    # split_pem_blocks returns a tuple of 2 lists, and the 2 names on the left take one each
    # e.g. for a CryptEasy public.pem:
    # labels = [b"PUBLIC KEY", b"PUBLIC KEY"], full_blocks = [block 1, block 2]
    labels, full_blocks = split_pem_blocks(pem_data)

    # (1, 2) is a tuple of the numbers of keys allowed in the file
    # 1 key = a key made somewhere else (encryption only), 2 keys = a CryptEasy public.pem
    # len(full_blocks) is the number of elements in the list, so the number of keys
    if len(full_blocks) not in (1, 2):
        raise InvalidKeyError("A public key file must contain 1 or 2 keys.")

    # If there is a private key in a public key file I refuse it,
    # bcs the user is about to share something secret without knowing
    # A broken block (label None) is not in the list either, so it's refused too
    for label in labels:
        if label not in public_labels:
            raise InvalidKeyError("This file contains something other than public keys.")

    # 2. Load each key
    # keys is a list where I put each loaded key, in the same order as in the file
    # load_pem_public_key reads a block and gives back the key as an object of the library,
    # already of the right kind (X25519PublicKey, RSAPublicKey, Ed25519PublicKey, ...)
    # try / except: if a line inside try raises an error, Python jumps to the except
    # instead of crashing, so I can turn the error into one of ours
    # (ValueError, UnsupportedAlgorithm) is a tuple of the 2 errors to catch at once:
    # ValueError means the content is broken
    # UnsupportedAlgorithm means a key type the cryptography library doesn't know
    # "from e" keeps the original error attached to ours, useful to know what happened
    keys = []
    try:
        for block in full_blocks:
            keys.append(serialization.load_pem_public_key(block))
    except (ValueError, UnsupportedAlgorithm) as e:
        raise InvalidKeyError("Invalid public key format.") from e

    # 3. The first key must be an encryption key (X25519 or RSA 2048 / 3072 / 4096)
    # keys[0] is the first element of the list (lists start at 0 in Python)
    # get_key_type gives None if it's not a key we can encrypt with
    encryption_key = keys[0]
    if get_key_type(encryption_key) is None:
        raise InvalidKeyError("The first key must be an X25519 or RSA (2048 / 3072 / 4096) key.")

    # 4. The second key, if there is one, must be an Ed25519 signing key
    # signing_key starts as None (no signing key), and only changes if there are 2 keys
    # keys[1] is the second element of the list
    signing_key = None
    if len(keys) == 2:
        signing_key = keys[1]
        if not isinstance(signing_key, ed25519.Ed25519PublicKey):
            raise InvalidKeyError("The second key must be an Ed25519 signing key.")

    # A tuple of the 2 public keys, same as in generate_keypair
    return encryption_key, signing_key


# This func gives both private keys of an identity as PEM (PKCS#8), NOT encrypted
# This is never written to disk like this: keystore/ locks it with the key passphrase first
# (spec section 6.2)
# -> bytes means this func returns bytes
def private_keys_to_pem(encryption_key, signing_key) -> bytes:
    pem_data = b""  # Empty bytes, the keys get added one by one

    # [encryption_key, signing_key] is a list of the 2 private keys,
    # so the for can go through them one by one, encryption key first
    # .private_bytes gives the private key as a PEM block, with 3 settings:
    # - Encoding.PEM: as text between BEGIN / END lines (not binary)
    # - PrivateFormat.PKCS8: the standard format for private keys, for any key type,
    #   so the label is "PRIVATE KEY"
    # - NoEncryption(): not protected by a password, on purpose: keystore/ encrypts
    #   everything itself with the user's settings (KDF, strength, salt), and the standard
    #   PEM encryption doesn't let us choose those
    # += adds each block at the end of pem_data
    for private_key in [encryption_key, signing_key]:
        pem_data += private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )

    # e.g. pem_data is 2 blocks one after the other:
    # -----BEGIN PRIVATE KEY----- ... -----END PRIVATE KEY-----   (encryption key)
    # -----BEGIN PRIVATE KEY----- ... -----END PRIVATE KEY-----   (signing key)
    # Anyone who has this can decrypt everything sent to this identity, so it must stay secret
    return pem_data


# This func loads private keys from PEM and checks them
# It works with the keys from private_keys_to_pem, or with a standard private key file
# (e.g. made with OpenSSL), protected by a password or not
# pem_data is the content of the file, in bytes
# password: bytes | None = None means the password is bytes or None (no password),
# and if it's not given it's None
# It returns the encryption private key and the signing private key
# The signing key is None when the file only has one key
# If the file isn't good it raises InvalidPrivateKeyError, if the password is wrong
# or missing it raises WrongPassphraseError
def load_private_keys(pem_data: bytes, password: bytes | None = None):

    # 1. Split the file into its PEM blocks (same as in load_public_keys)
    # labels is a list of the label of each block, full_blocks a list of each whole block
    # e.g. for the keys from private_keys_to_pem:
    # labels = [b"PRIVATE KEY", b"PRIVATE KEY"], full_blocks = [block 1, block 2]
    labels, full_blocks = split_pem_blocks(pem_data)

    # (1, 2) is a tuple of the numbers of keys allowed in the file
    # len(full_blocks) is the number of keys found
    if len(full_blocks) not in (1, 2):
        raise InvalidPrivateKeyError("A private key file must contain 1 or 2 keys.")

    # Every label must be a private key label, e.g. a public key here is refused
    # A broken block (label None) is not in the list either, so it's refused too
    for label in labels:
        if label not in private_labels:
            raise InvalidPrivateKeyError("This file is not a private key file.")

    # 2. Load each key, with the password only if that block is encrypted
    # keys is a list where I put each loaded key, in the same order as in the file
    # An encrypted block has the label "ENCRYPTED PRIVATE KEY" (PKCS#8), or a line
    # "Proc-Type: 4,ENCRYPTED" (older RSA format), both have the word ENCRYPTED in them
    # The library refuses a password for a key that isn't encrypted,
    # so I only give the password when it's needed
    keys = []
    for block in full_blocks:
        # b"ENCRYPTED" in block checks if the word is somewhere in the block,
        # so is_encrypted is True or False
        is_encrypted = b"ENCRYPTED" in block

        # "not password" is True when there is no password (None) or an empty one (b"")
        # An encrypted key with no password can't be opened, so I stop here
        if is_encrypted and not password:
            raise WrongPassphraseError("This private key is protected by a password.")

        # block_password is the password to give to the library for this block:
        # the real password if the block is encrypted, None if it isn't
        if is_encrypted:
            block_password = password
        else:
            block_password = None

        # load_pem_private_key reads the block (and decrypts it with the password if needed)
        # and gives back the key as an object of the library, already of the right kind
        # try / except: if the line inside try raises an error, Python jumps to the except
        # that matches it instead of crashing, so I can turn it into one of our errors
        # "from e" keeps the original error attached to ours, useful to know what happened
        try:
            key = serialization.load_pem_private_key(block, password=block_password)
        except ValueError as e:
            # For an encrypted key, ValueError means the password is wrong
            # For a key that isn't encrypted, it means the content is broken
            if is_encrypted:
                raise WrongPassphraseError("Incorrect password for this private key.") from e
            raise InvalidPrivateKeyError("Invalid private key format.") from e
        except UnsupportedAlgorithm as e:
            # A key type the cryptography library doesn't know
            raise InvalidPrivateKeyError("Unsupported key algorithm.") from e

        keys.append(key)

    # 3. The first key must be an encryption key (X25519 or RSA 2048 / 3072 / 4096)
    # keys[0] is the first element of the list (lists start at 0 in Python)
    encryption_key = keys[0]
    if get_key_type(encryption_key) is None:
        raise InvalidPrivateKeyError(
            "The first key must be an X25519 or RSA (2048 / 3072 / 4096) key."
        )

    # 4. The second key, if there is one, must be an Ed25519 signing key
    # signing_key starts as None (no signing key), and only changes if there are 2 keys
    # A key imported from somewhere else has no signing key, keystore/ will have to create one
    signing_key = None
    if len(keys) == 2:
        signing_key = keys[1]
        if not isinstance(signing_key, ed25519.Ed25519PrivateKey):
            raise InvalidPrivateKeyError("The second key must be an Ed25519 signing key.")

    # A tuple of the 2 private keys, same as in generate_keypair
    return encryption_key, signing_key
