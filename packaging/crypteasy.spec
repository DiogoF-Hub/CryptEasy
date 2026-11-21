# PyInstaller spec: CryptEasy as ONE file, no console window (TECHNICAL_SPEC sections 2.1, 2.2).
#
# Build with `make build` (uv run pyinstaller --noconfirm --clean packaging/crypteasy.spec),
# then `make smoke`. PyInstaller doesn't cross-compile: build on each target OS.
#
# - Our own data files (pages, CSS / JS, translations) are added below, at the same path
#   inside the bundle as in src/, so Flask and ui/i18n.py find them next to their module.
# - pywebview: pyinstaller-hooks-contrib already has hooks for `webview` (on Windows it
#   collects the WebView2 DLLs from webview/lib) and for pythonnet (`clr`).
# - console=False: on Windows no console window opens. sys.stdout / sys.stderr may then be
#   None (PyInstaller docs, "Common issues and pitfalls"); crypteasy.__main__ handles that.

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent  # SPECPATH: the folder of this file, set by PyInstaller
UI = ROOT / "src" / "crypteasy" / "ui"

datas = [
    (str(UI / "templates"), "crypteasy/ui/templates"),
    (str(UI / "static"), "crypteasy/ui/static"),
    (str(UI / "translations"), "crypteasy/ui/translations"),
]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    # pywebview's docs: PyInstaller bundles every GUI toolkit it can find, even unused
    # ones. CryptEasy uses Edge WebView2 (Windows) or GTK (Linux), never Qt or Tk.
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6", "qtpy"],
    noarchive=False,
)

if sys.platform.startswith("linux"):
    # Linux window = pywebview's GTK backend (PyGObject, `uv sync --group gtk`).
    # Only the Python side of PyGObject (`gi`) is bundled; GTK, WebKit2GTK, GLib, their
    # typelibs, themes and icons always come from the user's system (TECHNICAL_SPEC
    # section 2.2: "uses the web engine already in the OS"). Bundling them can't work:
    # - WebKitGTK starts helper programs (WebKitWebProcess...) from a path fixed when it
    #   was compiled, and they must be the exact same version as the library;
    # - a bundled GLib would be loaded first and break the system's WebKit.
    # So: keep only files from our Python, the venv and this project (incl. build/, where
    # PyInstaller writes base_library.zip), drop everything else (the system's), and the
    # gi runtime hooks, which would point GTK to bundled copies.
    import sysconfig

    ours = tuple(
        str(Path(p).resolve())
        for p in {ROOT, sys.base_prefix, sys.prefix, *sysconfig.get_paths().values()}
    )

    def _ours(src):
        return str(Path(src).resolve()).startswith(ours)

    a.binaries = [b for b in a.binaries if _ours(b[1])]
    # share/: the system's icons, themes, locales, plus a GSettings schema file compiled
    # into build/. SYMLINK entries hold a relative target, not a path, so _ours() can't
    # judge them: they are all icon-theme links under share/.
    a.datas = [
        d for d in a.datas if _ours(d[1]) and d[2] != "SYMLINK" and not d[0].startswith("share/")
    ]
    gi_rthooks = ("pyi_rth_gi", "pyi_rth_gio", "pyi_rth_glib", "pyi_rth_gtk", "pyi_rth_gdkpixbuf")
    a.scripts = [s for s in a.scripts if s[0] not in gi_rthooks]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="crypteasy",
    console=False,
    disable_windowed_traceback=False,
    upx=False,  # UPX-packed exes are flagged by antivirus software more often
    strip=False,
    runtime_tmpdir=None,
)
