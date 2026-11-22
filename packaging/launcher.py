"""PyInstaller entry point: the same as `python -m crypteasy`.

PyInstaller runs its entry script as a top-level script, not as part of the package, so
`src/crypteasy/__main__.py` (which uses package imports) can't be the entry point itself.
"""

import os
import sys

from crypteasy.__main__ import main

if __name__ == "__main__":
    if sys.platform.startswith("linux"):
        # The executable only bundles pywebview's GTK backend (Qt is excluded in the spec).
        # On KDE pywebview tries Qt first and logs an error before falling back to GTK.
        os.environ.setdefault("PYWEBVIEW_GUI", "gtk")
    sys.exit(main())
