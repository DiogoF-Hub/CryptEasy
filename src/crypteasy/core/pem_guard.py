import base64
import re

from crypteasy.core.errors import InvalidPrivateKeyError
from crypteasy.core.kdf import max_pbkdf2_iterations

"""
In this file I check a private key file BEFORE the cryptography library opens it
(spec section 6.2: refuse silly settings so a crafted key file can't freeze the app)

Why: an encrypted key file says itself how its password is hashed (which KDF, how many
iterations, how much memory). The library runs that KDF before it can know the password is
wrong. So a file of 300 bytes someone sends can ask for minutes of CPU or GBs of RAM, and
some values even crash the library (an error that "except Exception" doesn't catch)
So I read those settings here first, without any crypto, and only let through what
cryptography and OpenSSL 3 really write. This only ever refuses files, it never makes the
library accept a file it would refuse

Accepted (at most ONE encrypted block per file, a key made somewhere else has only one):
- "ENCRYPTED PRIVATE KEY" (PKCS#8) with PBES2, AES-CBC and:
    - PBKDF2 with HMAC-SHA256, at most max_pbkdf2_iterations (same limit as core/kdf.py)
    - or scrypt with p = 1, r <= 32, N a power of 2, at most 256 MiB of RAM
- the older "RSA PRIVATE KEY" with exactly "Proc-Type: 4,ENCRYPTED" and a DEK-Info line of
  AES-128/192/256-CBC (16 byte IV) or DES-EDE3-CBC (8 byte IV). Its KDF is a single MD5
Everything else that is encrypted is refused (older PBES1, PBKDF2 with SHA-1, ...)

The first version of this check was written by Sam for keystore/ (#50), I moved it to core/
so every caller of keys.load_private_keys is protected, not only keystore/ (#55)
"""

# The biggest real block is an encrypted RSA-4096 key, about 3.4 KiB
# This limit also keeps the RSA check of the library short: the biggest RSA key that fits in
# 4 KiB is around 5100 bits, checked in under a second (RSA-8192 would take 3 s or more)
max_block_size = 4 * 1024

# Limits for scrypt (only in keys made with "openssl pkcs8 -scrypt", which writes
# N = 16384, r = 8, p = 1, so 16 MiB)
max_scrypt_memory = 256 * 1024 * 1024  # 256 MiB
max_scrypt_block_size = 32  # r

# The tags of the DER elements I need to read (DER is explained above read_element)
sequence_tag = 0x30  # a list of elements
integer_tag = 0x02  # a number
octet_string_tag = 0x04  # raw bytes (a salt, an IV, the encrypted key)
oid_tag = 0x06  # an "object identifier", the ID of an algorithm

# The IDs (OIDs) of the algorithms, as the bytes written inside the DER element
# The usual dotted form is in the comment, e.g. PBES2 is 1.2.840.113549.1.5.13
pbes2_oid = bytes.fromhex("2a864886f70d01050d")  # 1.2.840.113549.1.5.13
pbkdf2_oid = bytes.fromhex("2a864886f70d01050c")  # 1.2.840.113549.1.5.12
scrypt_oid = bytes.fromhex("2b06010401da47040b")  # 1.3.6.1.4.1.11591.4.11
hmac_sha256_oid = bytes.fromhex("2a864886f70d0209")  # 1.2.840.113549.2.9

# This is a list of the OIDs of the 3 AES-CBC ciphers accepted
aes_cbc_oids = [
    bytes.fromhex("608648016503040102"),  # 2.16.840.1.101.3.4.1.2, aes128-CBC
    bytes.fromhex("608648016503040116"),  # 2.16.840.1.101.3.4.1.22, aes192-CBC
    bytes.fromhex("60864801650304012a"),  # 2.16.840.1.101.3.4.1.42, aes256-CBC
]

# This regex is the only header an older encrypted "RSA PRIVATE KEY" is allowed to have:
#   Proc-Type: 4,ENCRYPTED
#   DEK-Info: AES-256-CBC,<IV in hex>
#   (empty line, then the key in base64)
# [0-9A-Fa-f]{32} is exactly 32 hex characters = a 16 byte IV for AES, {16} = 8 bytes for
# DES-EDE3. A shorter IV is what crashed the library, so the exact size matters
# \r?\n is a line break, with or without the \r Windows adds
legacy_headers = re.compile(
    rb"Proc-Type: 4,ENCRYPTED\r?\n"
    rb"DEK-Info: (?:(?:AES-128-CBC|AES-192-CBC|AES-256-CBC),[0-9A-Fa-f]{32}"
    rb"|DES-EDE3-CBC,[0-9A-Fa-f]{16})\r?\n\r?\n"
)


# This func checks every block of a private key file, before the library opens any of them
# labels and full_blocks are the 2 lists given by keys.split_pem_blocks
# keys.load_private_keys calls it after checking the labels, so every label here is a
# private key label
# If something isn't accepted, it raises InvalidPrivateKeyError
def check_private_blocks(labels, full_blocks):
    encrypted_blocks = 0  # How many encrypted blocks I found

    # range(len(full_blocks)) gives 0, 1, ... so i is the position of each block,
    # and labels[i] is the label of the same block
    for i in range(len(full_blocks)):
        label = labels[i]
        block = full_blocks[i]

        # 1. Size of the block
        if len(block) > max_block_size:
            raise InvalidPrivateKeyError("This key is too big.")

        # 2. Get the body of the block: what's between the BEGIN line and the END line
        # A block looks like "-----BEGIN X-----<body>-----END X-----", so splitting on
        # "-----" gives ["", "BEGIN X", body, "END X", ""] and the body is at position 2
        body = block.split(b"-----")[2]

        # 3. Check the encryption settings
        # ValueError and IndexError both mean "broken or not accepted" in the funcs below
        # (a cut DER element, missing settings, bad base64, ...), so they all become our error
        try:
            if b":" in body:
                # A ":" means header lines ("Proc-Type: ...") bcs base64 never has a ":"
                # Only the older RSA format has headers, and only the exact ones above
                # .lstrip() removes the line break before the first header
                if label != b"RSA PRIVATE KEY" or not legacy_headers.match(body.lstrip()):
                    raise ValueError("Headers not accepted")
                encrypted_blocks += 1
            elif label == b"ENCRYPTED PRIVATE KEY":
                # body.split() cuts on spaces and line breaks, b"".join puts the pieces back
                # together without them, so it's only the base64, which b64decode turns into
                # the DER bytes. validate=True refuses any character that isn't base64
                der = base64.b64decode(b"".join(body.split()), validate=True)
                check_encrypted_pkcs8(der)
                encrypted_blocks += 1
            # Any other block is not encrypted, so no KDF runs, nothing to check
        except (ValueError, IndexError) as e:
            raise InvalidPrivateKeyError(
                "This key file uses an encryption that is not supported or not safe."
            ) from e

    # 4. At most one encrypted block, bcs the cost of each KDF adds up
    if encrypted_blocks > 1:
        raise InvalidPrivateKeyError("This key file has more than one encrypted key.")


# This func reads one DER element that starts at position pos in data
# DER is the binary format inside a PEM block (the base64 is just DER written as text)
# A DER element is always 3 parts, one after the other ("TLV"):
# - the tag (1 byte) says what it is, e.g. 0x30 = SEQUENCE, 0x02 = INTEGER
# - the length says how many bytes the value takes
# - the value, for a SEQUENCE it's other elements one after the other
# e.g. 02 01 05 is an INTEGER (02) of 1 byte (01) with the value 5 (05)
# end is where I'm allowed to read up to (the end of the parent element)
# It returns a tuple (tag, start of the value, end of the value), positions in data
# If the element doesn't fit inside its parent it raises ValueError
def read_element(data, pos, end):

    # 1. The tag and the first byte of the length
    if pos + 2 > end:
        raise ValueError("Element cut")
    tag = data[pos]
    length = data[pos + 1]
    pos = pos + 2

    # 2. Long lengths
    # A length under 128 fits in that one byte
    # From 128, that byte is 128 + how many of the next bytes hold the length
    # e.g. 82 01 00 means "the length is the next 2 bytes": 0x0100 = 256
    # More than 4 bytes would be more than 4 GiB, a key is never that big
    if length >= 128:
        length_size = length - 128
        if length_size < 1 or length_size > 4 or pos + length_size > end:
            raise ValueError("Bad length")
        # int.from_bytes turns the bytes into a number, "big" = most important byte first
        length = int.from_bytes(data[pos : pos + length_size], "big")
        pos = pos + length_size

    # 3. The value must fit inside the parent, a crafted file can say any length
    if pos + length > end:
        raise ValueError("Element cut")

    # A tuple (tag, start of the value, end of the value)
    return tag, pos, pos + length


# This func gives the elements inside a SEQUENCE, as a list of tuples from read_element
# element is a tuple from read_element. At most 8 children, no real key needs more
def read_children(data, element):
    tag, pos, end = element
    if tag != sequence_tag:
        raise ValueError("Expected a SEQUENCE")

    # children is a list of the elements found, it starts empty
    # Each child starts where the one before ends (its 3rd value)
    children = []
    while pos < end:
        if len(children) == 8:
            raise ValueError("Too many elements")
        child = read_element(data, pos, end)
        children.append(child)
        pos = child[2]

    return children


# This func gives the bytes of an OID element, to compare with the OIDs at the top
def read_oid(data, element):
    tag, start, end = element
    if tag != oid_tag:
        raise ValueError("Expected an OID")
    return data[start:end]


# This func gives the number in an INTEGER element
# At most 8 bytes: a real iteration count or scrypt setting is way smaller,
# and a huge number is refused here without even being read
def read_small_int(data, element):
    tag, start, end = element
    if tag != integer_tag or end - start < 1 or end - start > 8:
        raise ValueError("Expected a small INTEGER")
    # signed=True bcs DER numbers can be negative (a crafted file could say -1)
    return int.from_bytes(data[start:end], "big", signed=True)


# This func checks the settings of an "ENCRYPTED PRIVATE KEY" block (PKCS#8)
# der is the decoded block. Its structure is:
#   SEQUENCE
#     SEQUENCE                    algorithm
#       OID                       must be PBES2
#       SEQUENCE                  PBES2 settings
#         SEQUENCE                KDF
#           OID                   PBKDF2 or scrypt
#           SEQUENCE              KDF settings (salt, iterations, ...)
#         SEQUENCE                cipher
#           OID                   must be AES-CBC
#           OCTET STRING          IV
#     OCTET STRING                the encrypted key (not read here)
# a, b = read_children(...) takes exactly 2 children, if there are more or fewer
# Python raises ValueError by itself, so a wrong structure is refused too
def check_encrypted_pkcs8(der):

    # 1. The outer SEQUENCE must take the whole data, nothing hidden after it
    top = read_element(der, 0, len(der))
    if top[2] != len(der):
        raise ValueError("Data after the key")
    algorithm, encrypted_key = read_children(der, top)
    if encrypted_key[0] != octet_string_tag:
        raise ValueError("Expected the encrypted key")

    # 2. The scheme must be PBES2 (the older PBES1 ones use weak KDFs and ciphers)
    scheme, pbes2_settings = read_children(der, algorithm)
    if read_oid(der, scheme) != pbes2_oid:
        raise ValueError("Only PBES2 is accepted")

    # 3. The cipher must be AES-CBC
    # read_children(...)[0] is the first child of the cipher SEQUENCE, its OID
    kdf, cipher = read_children(der, pbes2_settings)
    if read_oid(der, read_children(der, cipher)[0]) not in aes_cbc_oids:
        raise ValueError("Only AES-CBC is accepted")

    # 4. The KDF: PBKDF2 or scrypt, each one has its own settings to check
    # settings is a list of the elements of the KDF settings, the first one is always the salt
    kdf_oid, kdf_settings = read_children(der, kdf)
    settings = read_children(der, kdf_settings)
    if settings[0][0] != octet_string_tag:
        raise ValueError("Expected a salt")

    if read_oid(der, kdf_oid) == pbkdf2_oid:
        check_pbkdf2(der, settings)
    elif read_oid(der, kdf_oid) == scrypt_oid:
        check_scrypt(der, settings)
    else:
        raise ValueError("Only PBKDF2 and scrypt are accepted")


# This func checks the PBKDF2 settings: salt, iterations, key length (optional),
# then the hash used (prf)
# settings is the list of elements from check_encrypted_pkcs8
def check_pbkdf2(der, settings):

    # 1. The iterations, the slow part
    iterations = read_small_int(der, settings[1])
    if iterations < 1 or iterations > max_pbkdf2_iterations:
        raise ValueError("Too many PBKDF2 iterations")

    # 2. The optional key length, the library doesn't use it so I skip it
    # settings[2:] is the list of what's left after the salt and the iterations
    rest = settings[2:]
    if len(rest) > 0 and rest[0][0] == integer_tag:
        rest = rest[1:]

    # 3. The hash must be written and be HMAC-SHA256
    # When it's not written the default is SHA-1, which runs twice for an AES-256 key,
    # and SHA-512 is about 4x slower: with those the iteration limit wouldn't mean the same
    if len(rest) != 1:
        raise ValueError("Only PBKDF2 with HMAC-SHA256 is accepted")
    if read_oid(der, read_children(der, rest[0])[0]) != hmac_sha256_oid:
        raise ValueError("Only PBKDF2 with HMAC-SHA256 is accepted")


# This func checks the scrypt settings: salt, N (cost), r (block size), p (parallel),
# then the key length (optional)
# settings is the list of elements from check_encrypted_pkcs8
def check_scrypt(der, settings):
    n = read_small_int(der, settings[1])
    r = read_small_int(der, settings[2])
    p = read_small_int(der, settings[3])

    # 1. p must be 1 (it multiplies the time), r in its limit
    if p != 1 or r < 1 or r > max_scrypt_block_size:
        raise ValueError("scrypt r or p not accepted")

    # 2. N must be a power of 2 (2, 4, 8, ...), scrypt needs it
    # n & (n - 1) is 0 only for a power of 2, e.g. 8 = 1000 and 7 = 0111 in binary, so
    # 8 & 7 = 0. For 6 = 110 and 5 = 101, 6 & 5 = 100 which isn't 0
    if n < 2 or n & (n - 1) != 0:
        raise ValueError("scrypt N must be a power of 2")

    # 3. The RAM it would use, this is how OpenSSL computes it: 128 * r * (N + 2) + 128 * r * p
    if 128 * r * (n + 2) + 128 * r * p > max_scrypt_memory:
        raise ValueError("scrypt would use too much memory")
