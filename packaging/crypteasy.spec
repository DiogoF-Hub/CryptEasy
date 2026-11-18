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
