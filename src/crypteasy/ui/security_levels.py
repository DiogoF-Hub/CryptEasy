"""Réglages de sécurité réglables (SPEC_TECHNIQUE § 4) et indicateur de niveau (F6).

Source UNIQUE des notes 🟢 / 🟡 / 🔴 : le serveur s'en sert pour l'affichage
initial et les tests, la page la reçoit en JSON (attribut data-) pour la mise à
jour en direct. Le mot de passe n'est jamais envoyé au serveur pour être noté :
seule sa longueur est évaluée, dans le navigateur.

À faire relire par Member 1 (crypto) : ce sont des jugements de sécurité.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

# ------------------------------------------------------------------ choix proposés
KEY_TYPES = {
    "x25519": "X25519 (recommandé)",
    "rsa-3072": "RSA 3072 bits",
    "rsa-4096": "RSA 4096 bits",
    "rsa-2048": "RSA 2048 bits",
}
DEFAULT_KEY_TYPE = "x25519"

CIPHERS = {"aes-256-gcm": "AES-256-GCM (recommandé)", "aes-128-gcm": "AES-128-GCM"}
DEFAULT_CIPHER = "aes-256-gcm"

KDFS = {"argon2id": "Argon2id (recommandé)", "pbkdf2-sha256": "PBKDF2-SHA256"}
DEFAULT_KDF = "argon2id"

# Préréglages : valeurs exactes à mesurer (D11), cible ~0,5 s / 1 s / 3 s
KDF_STRENGTHS = {"normal": "Normal (~0,5 s)", "fort": "Fort (~1 s)", "max": "Maximum (~3 s)"}
DEFAULT_KDF_STRENGTH = "normal"

SALT_LENGTHS = {
    "16": "16 octets (recommandé)",
    "32": "32 octets",
    "0": "Aucun sel (déconseillé, PBKDF2 uniquement)",
}
DEFAULT_SALT = "16"

MIN_PASSWORD_LENGTH = 12  # D5


@dataclass(frozen=True)
class EncryptOptions:
    cipher: str = DEFAULT_CIPHER
    password: bytes | None = None  # mot de passe supplémentaire ; None = désactivé
    kdf: str = DEFAULT_KDF
    kdf_strength: str = DEFAULT_KDF_STRENGTH
    salt_len: int = 16  # 0 = sans sel (PBKDF2 uniquement, D3)


# ------------------------------------------------------------------ niveaux
GOOD, OK, WEAK = "good", "ok", "weak"
LEVELS = {
    GOOD: {"icon": "🟢", "label": "Recommandé"},
    OK: {"icon": "🟡", "label": "Correct"},
    WEAK: {"icon": "🔴", "label": "Faible"},
}
_ORDER = [GOOD, OK, WEAK]

# réglage → valeur → (niveau, explication d'une ligne)
RULES: dict[str, dict[str, tuple[str, str]]] = {
    "key_type": {
        "x25519": (GOOD, "X25519 : courbe elliptique moderne, rapide et sûre."),
        "rsa-4096": (GOOD, "RSA 4096 bits : très solide, mais lent à générer."),
        "rsa-3072": (GOOD, "RSA 3072 bits : niveau recommandé pour RSA (128 bits de sécurité)."),
        "rsa-2048": (
            OK,
            "RSA 2048 bits : encore acceptable, mais en fin de vie (112 bits de sécurité).",
        ),
    },
    "cipher": {
        "aes-256-gcm": (GOOD, "AES-256-GCM : chiffre le fichier et détecte toute modification."),
        "aes-128-gcm": (
            OK,
            "AES-128-GCM : sûr aussi, avec une marge de sécurité plus faible qu'AES-256.",
        ),
    },
    "kdf": {
        "argon2id": (
            GOOD,
            "Argon2id : coûteux en mémoire, résiste aux attaques par carte graphique.",
        ),
        "pbkdf2-sha256": (
            OK,
            "PBKDF2 : correct, mais plus facile à attaquer sur carte graphique qu'Argon2id.",
        ),
    },
    "kdf_strength": {
        "normal": (GOOD, "Force normale : bon compromis entre rapidité et résistance."),
        "fort": (GOOD, "Force élevée : chaque essai d'un attaquant coûte deux fois plus cher."),
        "max": (GOOD, "Force maximale : le plus résistant, quelques secondes d'attente."),
    },
    "salt": {
        "16": (GOOD, "Sel de 16 octets : empêche les attaques précalculées."),
        "32": (GOOD, "Sel de 32 octets : même protection, un peu plus de marge."),
        "0": (
            WEAK,
            "Sans sel : un attaquant peut précalculer ses essais une fois pour tous les fichiers.",
        ),
    },
}
SHORT_PASSWORD = (
    WEAK,
    f"Mot de passe de moins de {MIN_PASSWORD_LENGTH} caractères : facile à deviner.",
)


@dataclass(frozen=True)
class Rating:
    level: str
    reasons: list[tuple[str, str]]  # (niveau, explication), une ligne par réglage

    @property
    def icon(self) -> str:
        return LEVELS[self.level]["icon"]

    @property
    def label(self) -> str:
        return LEVELS[self.level]["label"]


def rate(choices: dict[str, str]) -> Rating:
    """Note un ensemble de réglages : le niveau global est celui du pire réglage."""
    reasons = [RULES[k][v] for k, v in choices.items() if k in RULES and v in RULES[k]]
    level = max((lvl for lvl, _ in reasons), key=_ORDER.index, default=GOOD)
    return Rating(level, reasons)


def rules_json() -> str:
    """Règles transmises à la page pour l'indicateur en direct (static/app.js)."""
    return json.dumps(
        {
            "levels": LEVELS,
            "rules": RULES,
            "minPassword": MIN_PASSWORD_LENGTH,
            "shortPassword": SHORT_PASSWORD,
        },
        ensure_ascii=False,
    )
