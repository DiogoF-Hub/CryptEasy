"""File helpers and name validation shared by the keystore modules."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import unicodedata
from pathlib import Path

from .errors import InvalidNameError

MAX_NAME_LEN = 64  # same limit as the UI forms (maxlength="64")


def clean_name(name: str) -> str:
    """Strip spaces and reject empty, too long, or control / bidi-override characters."""
    name = name.strip()
    if not name or len(name) > MAX_NAME_LEN:
        raise InvalidNameError()
    # Cc: control chars, Cf: invisible formatting (e.g. right-to-left override), Zl/Zp: newlines,
    # Cs: lone surrogates (can't be encoded to UTF-8 when the JSON file is written)
    if any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp", "Cs") for c in name):
        raise InvalidNameError()
    return name


def parse_json(data: bytes) -> object:
    """json.loads for untrusted files. Every failure is a ValueError, including deeply
    nested input, which makes json.loads raise RecursionError (CWE-674)."""
    try:
        return json.loads(data)
    except RecursionError as exc:
        raise ValueError("JSON nested too deeply") from exc


def read_limited(path: Path, max_bytes: int) -> bytes:
    """Read a file, raising ValueError if it is larger than max_bytes (checked before parsing)."""
    with open(path, "rb") as f:
        data = f.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"{path.name} is larger than {max_bytes} bytes")
    return data


def atomic_write(path: Path, data: bytes) -> None:
    """Replace `path` with `data` so that a crash never leaves a half-written file.

    The temp file is created in the same folder (os.replace is only atomic on the same
    filesystem) with mode 0o600, and deleted if anything fails.
    """
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def write_new(path: Path, data: bytes) -> None:
    """Write a new file, never overwriting (raises FileExistsError). Mode 0o600 on POSIX."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(path)
        raise
