"""Where CryptEasy keeps its data (TECHNICAL_SPEC section 6.1), and settings.json.

    <data dir>/keys/<id>/   my key pairs (identities.py)
    <data dir>/contacts.json
    <data dir>/settings.json

The data dir is CRYPTEASY_HOME if set (tests), else the per-user app data folder.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .common import atomic_write, parse_json, read_limited

ENV_VAR = "CRYPTEASY_HOME"
APP_NAME = "CryptEasy"
MAX_SETTINGS_BYTES = 64 * 1024


def data_dir() -> Path:
    """Return the data folder, creating it if needed.

    CRYPTEASY_HOME is read on every call, so tests can point it at a temp folder.
    """
    override = os.environ.get(ENV_VAR)
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ["APPDATA"]) / APP_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = Path.home() / ".local" / "share" / APP_NAME
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    return base


def keys_dir() -> Path:
    path = data_dir() / "keys"
    path.mkdir(mode=0o700, exist_ok=True)
    return path


def contacts_file() -> Path:
    return data_dir() / "contacts.json"


def settings_file() -> Path:
    return data_dir() / "settings.json"


def load_settings() -> dict:
    """Return the saved settings, or {} if there are none or the file is damaged.

    Settings are not critical (e.g. the language), so a damaged file must not stop the
    app. The UI checks each value it uses.
    """
    try:
        settings = parse_json(read_limited(settings_file(), MAX_SETTINGS_BYTES))
    except (OSError, ValueError):  # missing, unreadable, too large, not UTF-8, or not JSON
        return {}
    return settings if isinstance(settings, dict) else {}


def save_settings(settings: dict) -> None:
    atomic_write(settings_file(), json.dumps(settings, indent=2).encode())
