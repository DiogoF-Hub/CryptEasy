"""PyInstaller entry point: the same as `python -m crypteasy`.

PyInstaller runs its entry script as a top-level script, not as part of the package, so
`src/crypteasy/__main__.py` (which uses package imports) can't be the entry point itself.
"""

import sys

from crypteasy.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
