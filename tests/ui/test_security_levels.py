"""Indicateur de niveau (F6) : notation des réglages du § 4."""
import json

import pytest

from crypteasy.ui.security_levels import (
    CIPHERS, KDF_STRENGTHS, KDFS, KEY_TYPES, RULES, SALT_LENGTHS, rate, rules_json,
)


def test_reglages_par_defaut_recommandes():
    r = rate({"key_type": "x25519", "cipher": "aes-256-gcm"})
    assert r.level == "good" and r.icon == "🟢" and r.label == "Recommandé"


@pytest.mark.parametrize("choices, level", [
    ({"key_type": "rsa-2048"}, "ok"),
    ({"cipher": "aes-128-gcm"}, "ok"),
    ({"kdf": "pbkdf2-sha256"}, "ok"),
    ({"salt": "0"}, "weak"),
    ({"key_type": "x25519", "cipher": "aes-128-gcm", "salt": "0"}, "weak"),   # le pire l'emporte
])
def test_niveaux(choices, level):
    assert rate(choices).level == level


def test_une_explication_par_reglage():
    r = rate({"key_type": "rsa-3072", "cipher": "aes-256-gcm", "kdf": "argon2id", "salt": "16"})
    assert len(r.reasons) == 4 and all(text for _lvl, text in r.reasons)


def test_valeurs_inconnues_ignorees():
    assert rate({"cipher": "rot13", "inconnu": "x"}).reasons == []


@pytest.mark.parametrize("setting, choices", [
    ("key_type", KEY_TYPES), ("cipher", CIPHERS), ("kdf", KDFS),
    ("kdf_strength", KDF_STRENGTHS), ("salt", SALT_LENGTHS),
])
def test_chaque_choix_propose_a_une_regle(setting, choices):
    assert set(RULES[setting]) == set(choices)


def test_json_pour_la_page():
    cfg = json.loads(rules_json())
    assert cfg["minPassword"] == 12 and cfg["levels"]["weak"]["icon"] == "🔴"
    assert cfg["rules"]["salt"]["0"][0] == "weak"
