"""Niveaux de sécurité (SPEC § 4.2) et indicateur (F6), côté interface.

- PRESETS : ce que chaque niveau remplit sur l'écran de génération de clés.
- RATINGS : la note de chaque valeur de chaque réglage. Le niveau affiché est celui
  du réglage le plus faible (« personnalisé » compris).
- Même source pour le serveur (affichage initial, tests) et pour la page (rules_json,
  recalcul en direct dans app.js). Les textes sont des clés de traduction.

Si core/levels.py (Track A) fournit ces règles, ce module devra simplement les relire.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .i18n import t

# Du plus fort au plus faible
VERY_STRONG, STRONG, MEDIUM, WEAK, NONE = "very_strong", "strong", "medium", "weak", "none"
ORDER = [VERY_STRONG, STRONG, MEDIUM, WEAK, NONE]
ICONS = {VERY_STRONG: "🟢🟢", STRONG: "🟢", MEDIUM: "🟡", WEAK: "🔴", NONE: "⛔"}
CUSTOM = "custom"
DEFAULT_LEVEL = STRONG

# ------------------------------------------------------------------ choix proposés
KEY_TYPES = ["x25519", "rsa-4096", "rsa-3072", "rsa-2048"]
CIPHERS = ["aes-256-gcm", "aes-128-gcm"]
KDFS = ["argon2id", "pbkdf2-sha256"]
KDF_STRENGTHS = ["normal", "strong", "max"]
SALTS = ["32", "16", "0"]  # octets ; "0" = aucun sel (PBKDF2 uniquement)
DEFAULT_CIPHER = "aes-256-gcm"

MIN_PASSPHRASE = 12
VERY_STRONG_PASSPHRASE = 16

# Ce que chaque niveau remplit (§ 4.2). « none » = case « sans phrase secrète ».
PRESETS: dict[str, dict[str, str]] = {
    VERY_STRONG: {"key_type": "x25519", "kdf": "argon2id", "kdf_strength": "max", "salt": "32"},
    STRONG: {"key_type": "x25519", "kdf": "argon2id", "kdf_strength": "normal", "salt": "16"},
    MEDIUM: {
        "key_type": "rsa-2048",
        "kdf": "pbkdf2-sha256",
        "kdf_strength": "normal",
        "salt": "16",
    },
    WEAK: {"key_type": "rsa-2048", "kdf": "pbkdf2-sha256", "kdf_strength": "normal", "salt": "0"},
}

# réglage → valeur → niveau (l'explication est la clé "rating.<réglage>.<valeur>")
RATINGS: dict[str, dict[str, str]] = {
    "key_type": {"x25519": VERY_STRONG, "rsa-4096": VERY_STRONG, "rsa-3072": STRONG,
                 "rsa-2048": MEDIUM},
    "cipher": {"aes-256-gcm": VERY_STRONG, "aes-128-gcm": MEDIUM},
    "kdf": {"argon2id": VERY_STRONG, "pbkdf2-sha256": MEDIUM},
    "kdf_strength": {"max": VERY_STRONG, "strong": STRONG, "normal": STRONG},
    "salt": {"32": VERY_STRONG, "16": STRONG, "0": WEAK},
}  # fmt: skip


def passphrase_level(length: int) -> str:
    if length >= VERY_STRONG_PASSPHRASE:
        return VERY_STRONG
    return STRONG if length >= MIN_PASSPHRASE else WEAK


@dataclass(frozen=True)
class Rating:
    level: str
    reasons: list[tuple[str, str]]  # (niveau, clé de traduction de l'explication)

    @property
    def icon(self) -> str:
        return ICONS[self.level]

    @property
    def label_key(self) -> str:
        return f"level.{self.level}"


def rate(choices: dict[str, str], *, no_passphrase: bool = False) -> Rating:
    """Note un ensemble de réglages : le niveau global est celui du pire réglage.

    no_passphrase : clé privée enregistrée sans phrase secrète → « aucune protection »,
    et les réglages de KDF n'ont plus de sens.
    """
    reasons = []
    for setting, value in choices.items():
        if no_passphrase and setting in ("kdf", "kdf_strength", "salt"):
            continue
        level = RATINGS.get(setting, {}).get(value)
        if level:
            reasons.append((level, f"rating.{setting}.{value}"))
    if no_passphrase:
        reasons.append((NONE, "rating.no_passphrase"))
    level = max((lvl for lvl, _ in reasons), key=ORDER.index, default=STRONG)
    return Rating(level, reasons)


def preset_of(choices: dict[str, str]) -> str:
    """Le niveau dont les réglages correspondent exactement, sinon « personnalisé »."""
    for level, preset in PRESETS.items():
        if all(choices.get(k) == v for k, v in preset.items()):
            return level
    return CUSTOM


def rules_json() -> str:
    """Tout ce dont la page a besoin pour l'indicateur en direct, déjà traduit."""
    return json.dumps(
        {
            "order": ORDER,
            "icons": ICONS,
            "labels": {lvl: t(f"level.{lvl}") for lvl in ORDER},
            "levelHelp": {lvl: t(f"level.{lvl}.help") for lvl in [*ORDER, CUSTOM]},
            "ratings": RATINGS,
            "reasons": {
                f"{s}.{v}": t(f"rating.{s}.{v}") for s, values in RATINGS.items() for v in values
            },
            "noPassphrase": t("rating.no_passphrase"),
            "presets": PRESETS,
            "minPassphrase": MIN_PASSPHRASE,
            "veryStrongPassphrase": VERY_STRONG_PASSPHRASE,
            "passphraseReasons": {
                lvl: t(f"rating.passphrase.{lvl}") for lvl in (VERY_STRONG, STRONG, WEAK)
            },
        },
        ensure_ascii=False,
    )
