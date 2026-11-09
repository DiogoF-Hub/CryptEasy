"""Boîtes de dialogue natives (SPEC § 2.2) : « choisir un fichier », « choisir un dossier »,
« enregistrer sous », et « ouvrir le dossier » dans l'Explorateur / Finder.

- PywebviewDialogs : les vraies boîtes de Windows / macOS / Linux, via la fenêtre pywebview.
- NoDialogs        : mode --no-window (CI) : aucune boîte ne peut s'ouvrir.
- Les tests utilisent leur propre faux (tests/ui/conftest.py).

Les chemins choisis restent côté Python (voir selections.py) : la page ne manipule
jamais de chemin, seulement des identifiants opaques.
"""

from __future__ import annotations

import os
import subprocess  # noqa: S404 - sert uniquement à ouvrir le gestionnaire de fichiers
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol


class Dialogs(Protocol):
    def open_file(self, file_types: Sequence[str] = ()) -> Path | None: ...
    def open_folder(self) -> Path | None: ...
    def save_file(self, default_name: str, file_types: Sequence[str] = ()) -> Path | None: ...
    def reveal(self, folder: Path) -> None: ...


def reveal_in_file_manager(folder: Path) -> None:
    """Ouvre `folder` dans l'Explorateur / le Finder / le gestionnaire de fichiers.
    `folder` vient toujours de Python (un dossier que l'appli vient d'écrire),
    jamais de la page."""
    if sys.platform == "win32":
        os.startfile(folder)  # noqa: S606 - ouvre un dossier, pas un programme
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        # outil système fixe, argument = dossier créé par l'appli, pas de shell
        subprocess.Popen([opener, str(folder)])  # noqa: S603, S607


class PywebviewDialogs:
    """Boîtes natives de la fenêtre pywebview (appelables depuis n'importe quel thread)."""

    def _window(self):
        import webview

        if not webview.windows:
            raise RuntimeError("Aucune fenêtre CryptEasy ouverte")
        return webview.windows[0]

    def _ask(self, kind, **kwargs) -> Path | None:
        result = self._window().create_file_dialog(kind, **kwargs)
        if not result:
            return None
        # Selon l'OS, pywebview renvoie une chaîne ou un tuple de chaînes
        return Path(result if isinstance(result, str) else result[0])

    def open_file(self, file_types: Sequence[str] = ()) -> Path | None:
        import webview

        return self._ask(webview.FileDialog.OPEN, file_types=tuple(file_types))

    def open_folder(self) -> Path | None:
        import webview

        return self._ask(webview.FileDialog.FOLDER)

    def save_file(self, default_name: str, file_types: Sequence[str] = ()) -> Path | None:
        import webview

        return self._ask(
            webview.FileDialog.SAVE, save_filename=default_name, file_types=tuple(file_types)
        )

    def reveal(self, folder: Path) -> None:
        reveal_in_file_manager(folder)


class NoDialogs:
    """Mode sans fenêtre : les boîtes de dialogue sont indisponibles."""

    def open_file(self, file_types: Sequence[str] = ()) -> Path | None:
        return None

    def open_folder(self) -> Path | None:
        return None

    def save_file(self, default_name: str, file_types: Sequence[str] = ()) -> Path | None:
        return None

    def reveal(self, folder: Path) -> None:
        return None
