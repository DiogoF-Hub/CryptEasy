"""Niveaux de sécurité (SPEC § 4.2) et indicateur (F6)."""

import json

import pytest

from crypteasy.ui.security_levels import (
    CIPHERS,
    KDF_STRENGTHS,
    KDFS,
    KEY_TYPES,
    PRESETS,
    RATINGS,
    SALTS,
    passphrase_level,
    preset_of,
    rate,
    rules_json,
)


@pytest.mark.parametrize("level", list(PRESETS))
def test_chaque_preset_obtient_son_niveau(level):
    """Un niveau choisi dans la liste donne bien ce niveau (avec AES-256, défaut)."""
    choices = {**PRESETS[level], "cipher": "aes-256-gcm"}
    assert rate(choices).level == level
    assert preset_of(PRESETS[level]) == level


def test_table_de_la_spec():
    """§ 4.2 : X25519 est dans les deux niveaux du haut, RSA-2048 = moyen, sans sel = faible."""
    assert rate({"key_type": "x25519"}).level == "very_strong"
    assert rate({"key_type": "rsa-3072"}).level == "strong"
    assert rate({"key_type": "rsa-2048"}).level == "medium"
    assert rate({"cipher": "aes-128-gcm"}).level == "medium"
    assert rate({"kdf": "pbkdf2-sha256"}).level == "medium"
    assert rate({"salt": "0"}).level == "weak"


def test_le_reglage_le_plus_faible_l_emporte():
    r = rate({"key_type": "x25519", "kdf": "argon2id", "kdf_strength": "max", "salt": "0"})
    assert r.level == "weak" and len(r.reasons) == 4


def test_sans_phrase_secrete():
    r = rate({"key_type": "x25519", "kdf": "argon2id", "salt": "32"}, no_passphrase=True)
    assert r.level == "none" and r.icon == "⛔"
    assert all(not key.startswith(("rating.kdf", "rating.salt")) for _lvl, key in r.reasons)


def test_personnalise():
    assert preset_of({"key_type": "rsa-4096", "kdf": "argon2id", "kdf_strength": "max",
                      "salt": "32"}) == "custom"  # fmt: skip


@pytest.mark.parametrize("n, level", [(0, "weak"), (11, "weak"), (12, "strong"),
                                      (15, "strong"), (16, "very_strong")])  # fmt: skip
def test_niveau_de_la_phrase_secrete(n, level):
    assert passphrase_level(n) == level


@pytest.mark.parametrize(
    "setting, choices",
    [("key_type", KEY_TYPES), ("cipher", CIPHERS), ("kdf", KDFS),
     ("kdf_strength", KDF_STRENGTHS), ("salt", SALTS)],
)  # fmt: skip
def test_chaque_choix_propose_a_une_note(setting, choices):
    assert set(RATINGS[setting]) == set(choices)


def test_regles_pour_la_page(app):
    with app.app_context():
        cfg = json.loads(rules_json())
    assert cfg["minPassphrase"] == 12 and cfg["veryStrongPassphrase"] == 16
    assert cfg["icons"]["very_strong"] == "🟢🟢" and cfg["labels"]["none"] == "Aucune protection"
    assert cfg["ratings"]["salt"]["0"] == "weak"
    assert set(cfg["levelHelp"]) >= {"strong", "custom"}
