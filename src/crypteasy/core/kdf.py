import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

"""
In this file I have the KDF: what turns the key passphrase into the "lock key"
that encrypts the private keys on the disk (spec sections 4.1 and 6.2)
"""

# A KDF (Key Derivation Function) takes a passphrase and gives a key of a fixed size.
# It's slow ON PURPOSE: someone who steals the private key file has to redo the KDF for
# every passphrase they try, so each guess costs time (and memory with Argon2id).
# For the user it's done once when unlocking the key, so it's barely noticeable.
#
# The security levels (very strong, strong, ...) are NOT here: the interface already
# computes them (ui/security_levels.py) and gives the level to keystore/, which saves it.
# Having the rules in 2 places would mean they could stop matching.

# This is a list of the KDFs offered in the app (same names as the interface)
# - argon2id: the recommended one. Memory-hard: each guess needs a lot of RAM,
#   so graphics cards (GPUs) can't try millions of passphrases at once
# - pbkdf2-sha256: older and simpler, only uses the CPU, so GPUs attack it more easily
kdf_types = ["argon2id", "pbkdf2-sha256"]

# This is a list of the strength presets the user can choose
# Stronger = slower to unlock, but also slower to brute-force
kdf_strengths = ["normal", "strong", "max"]

# This is a list of the salt sizes accepted, in bytes (0 = no salt)
# The salt is random bytes mixed with the passphrase, so the same passphrase never gives
# the same lock key twice. Without a salt, an attacker can precompute guesses once and
# reuse them against everyone (rainbow tables), so 0 is only allowed with PBKDF2, for learning
salt_sizes = [32, 16, 0]

# This is a dictionary: for each strength it gives the Argon2id settings
# - memory_kib: RAM used by each try, in KiB (262144 KiB = 256 MiB, 1048576 KiB = 1 GiB)
# - iterations: how many passes over that memory
# - parallelism: how many threads work in parallel (called "lanes" in Argon2)
# Measured on Diogo's laptop (Core Ultra X7) on Nov 10: about 0.25 s / 0.5 s / 1.3 s,
# so around 0.5 s / 1 s / 3 s on an average laptop (spec 4.1). The max memory stays at 1 GiB
# so a laptop with little RAM doesn't crash
argon2_presets = {
    "normal": {"memory_kib": 262144, "iterations": 4, "parallelism": 4},
    "strong": {"memory_kib": 524288, "iterations": 4, "parallelism": 4},
    "max": {"memory_kib": 1048576, "iterations": 6, "parallelism": 4},
}

# This is a dictionary: for each strength it gives the PBKDF2 settings
# - iterations: how many times SHA-256 is repeated
# Measured on the same laptop: about 0.25 s / 0.5 s / 1.5 s
# The _ in the numbers are only for readability, 1_200_000 is the same as 1200000
pbkdf2_presets = {
    "normal": {"iterations": 1_200_000},
    "strong": {"iterations": 2_500_000},
    "max": {"iterations": 7_500_000},
}

# Size of the lock key in bytes: 32 bytes = 256 bits, for AES-256-GCM
lock_key_length = 32

# Limits checked before running the KDF, bcs the settings come from the private.key file:
# a crafted file could ask for 100 GB of RAM or a billion iterations and freeze the app
max_argon2_memory_kib = 1048576  # 1 GiB, same as the "max" preset
max_argon2_iterations = 20
max_argon2_parallelism = 16
max_pbkdf2_iterations = 20_000_000


# This func gives the settings of a KDF for a strength, e.g. ("argon2id", "normal")
# It returns a dictionary, e.g. {"memory_kib": 262144, "iterations": 4, "parallelism": 4}
# keystore/ saves these settings in private.key, so the key can be unlocked later
# even if the presets change in a future version of the app
def get_kdf_params(kdf: str, strength: str) -> dict:

    # 1. Check the strength
    if strength not in kdf_strengths:
        raise ValueError(f"Invalid KDF strength! Use one of: {', '.join(kdf_strengths)}")

    # 2. Take the settings of the right KDF
    # dict(...) makes a copy, so if the code that called this func changes the
    # dictionary it gets, the presets at the top of this file don't change
    if kdf == "argon2id":
        return dict(argon2_presets[strength])
    if kdf == "pbkdf2-sha256":
        return dict(pbkdf2_presets[strength])

    raise ValueError(f"Invalid KDF! Use one of: {', '.join(kdf_types)}")


# This func creates a new random salt of the size the user chose (32, 16 or 0 bytes)
# It returns bytes, e.g. 16 random bytes, or b"" (empty bytes) for "no salt"
def generate_salt(kdf: str, salt_size: int) -> bytes:

    # 1. Check the size
    if salt_size not in salt_sizes:
        raise ValueError("Invalid salt size! Use 32, 16 or 0 bytes.")

    # 2. Argon2id always needs a salt (the library refuses less than 8 bytes)
    if kdf == "argon2id" and salt_size == 0:
        raise ValueError("Argon2id always needs a salt.")

    # 3. os.urandom gives secure random bytes from the OS, never use random for this
    # os.urandom(0) gives b"", so the "no salt" case works too
    return os.urandom(salt_size)


# This func checks the KDF settings before using them
# Used by derive_key, and by keystore/ when it reads a private.key file (the settings come
# from the file, so they could have been changed by someone)
# It raises ValueError if something is wrong, and returns nothing if everything is fine
def check_params(kdf: str, salt: bytes, params: dict):

    # 1. The salt: one of the accepted sizes, and never empty with Argon2id
    if len(salt) not in salt_sizes:
        raise ValueError("Invalid salt size.")
    if kdf == "argon2id" and len(salt) == 0:
        raise ValueError("Argon2id always needs a salt.")

    # 2. The settings of each KDF must be whole numbers within the limits
    # isinstance(x, int) checks it's a whole number (and not text like "4" or 4.5)
    if kdf == "argon2id":
        memory_kib = params.get("memory_kib")
        iterations = params.get("iterations")
        parallelism = params.get("parallelism")

        # This is a list of the 3 settings, to check they are all whole numbers at once
        for value in [memory_kib, iterations, parallelism]:
            if not isinstance(value, int):
                raise ValueError("Invalid Argon2id settings.")

        if not 1 <= parallelism <= max_argon2_parallelism:
            raise ValueError("Invalid Argon2id parallelism.")
        if not 1 <= iterations <= max_argon2_iterations:
            raise ValueError("Invalid number of Argon2id iterations.")
        # Argon2 needs at least 8 KiB of memory per parallel thread, that's a rule of the algorithm
        if not 8 * parallelism <= memory_kib <= max_argon2_memory_kib:
            raise ValueError("Invalid Argon2id memory size.")

    elif kdf == "pbkdf2-sha256":
        iterations = params.get("iterations")
        if not isinstance(iterations, int):
            raise ValueError("Invalid PBKDF2 settings.")
        if not 1 <= iterations <= max_pbkdf2_iterations:
            raise ValueError("Invalid number of PBKDF2 iterations.")

    else:
        raise ValueError(f"Invalid KDF! Use one of: {', '.join(kdf_types)}")


# This func turns the key passphrase into the lock key (32 bytes)
# Same passphrase + same salt + same settings = always the same lock key, that's how
# keystore/ can unlock the private keys later (it saves the salt and the settings)
# A different passphrase gives a completely different lock key, and then AES-GCM refuses
# to decrypt the private keys, that's how a wrong passphrase is detected
def derive_key(passphrase: bytes, kdf: str, salt: bytes, params: dict) -> bytes:

    # 1. Check everything first
    # An empty passphrase makes no sense here: "no passphrase" is a separate mode where
    # the private keys are not locked at all (spec 6.2), so the KDF is never called
    if not passphrase:
        raise ValueError("The passphrase is empty, use the no passphrase mode instead.")
    check_params(kdf, salt, params)

    # 2. Run the KDF
    # .derive(passphrase) does the slow work and gives the lock key
    if kdf == "argon2id":
        argon2 = Argon2id(
            salt=salt,
            length=lock_key_length,
            iterations=params["iterations"],
            lanes=params["parallelism"],  # the library calls it lanes
            memory_cost=params["memory_kib"],
        )
        return argon2.derive(passphrase)

    pbkdf2 = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=lock_key_length,
        salt=salt,
        iterations=params["iterations"],
    )
    return pbkdf2.derive(passphrase)
