"""Smoke test of the built executable (`make smoke`, and the CI build job).

Starts dist/crypteasy(.exe) with --no-window (Flask only, no window: CI has no screen),
reads the URL it prints as its first line (CRYPTEASY_URL=...), checks that the home page
answers on 127.0.0.1 (and refuses a request without the launch token), then stops it.

It proves the bundle is complete: Python, Flask, our pages, CSS and translations, and
core/ + keystore/ all load from the single file. It does NOT open the window: that is
checked by hand on a PC without Python (#24).

Exit code 0 = OK. Run from the repository root.
"""

from __future__ import annotations

import http.cookiejar
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "dist" / ("crypteasy.exe" if sys.platform == "win32" else "crypteasy")
START_TIMEOUT = 60  # s: a one-file exe unpacks itself to a temp folder first
URL_LINE = re.compile(r"CRYPTEASY_URL=(http://127\.0\.0\.1:\d+/\?token=[\w-]+)")


def fail(message: str) -> int:
    print(f"SMOKE TEST FAILED: {message}", file=sys.stderr)
    return 1


def read_first_line(proc: subprocess.Popen, timeout: float) -> str | None:
    """First stdout line, or None if nothing came within `timeout` seconds."""
    lines: queue.Queue[str] = queue.Queue()
    threading.Thread(target=lambda: lines.put(proc.stdout.readline()), daemon=True).start()
    try:
        return lines.get(timeout=timeout).strip()
    except queue.Empty:
        return None


def get(opener: urllib.request.OpenerDirector, url: str) -> tuple[int, str]:
    try:
        with opener.open(url, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, ""


def stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        # A one-file exe on Windows is 2 processes (the unpacker and the app):
        # /T stops the whole tree, a plain terminate() would leave the app running.
        # Full path, so a taskkill.exe earlier in PATH can't run instead.
        taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
        subprocess.run(  # noqa: S603 - fixed command, our own PID
            [str(taskkill), "/T", "/F", "/PID", str(proc.pid)], capture_output=True, check=False
        )
    else:
        proc.terminate()  # the PyInstaller bootloader forwards SIGTERM to the app
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


def main() -> int:
    if not EXE.is_file():
        return fail(f"{EXE} not found, run `make build` first")

    with tempfile.TemporaryDirectory() as home:
        env = {**os.environ, "CRYPTEASY_HOME": home}  # never touch the real data folder
        started = time.monotonic()
        proc = subprocess.Popen(  # noqa: S603 - our own freshly built executable
            [str(EXE), "--no-window"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
        try:
            first = read_first_line(proc, START_TIMEOUT)
            if not first:
                err = proc.stderr.read() if proc.poll() is not None else ""
                return fail(f"no CRYPTEASY_URL line within {START_TIMEOUT} s\n{err}")
            m = URL_LINE.fullmatch(first)
            if not m:
                return fail(f"unexpected first line: {first!r}")
            url = m.group(1)
            print(f"started in {time.monotonic() - started:.1f} s")

            base = url.split("?", 1)[0]

            no_token_status, _ = get(urllib.request.build_opener(), base)
            if no_token_status != 403:
                return fail(f"a request without the launch token answered {no_token_status}")
            print("request without token: 403")

            # The token URL opens a session (302 + cookie), then pages need that cookie
            session = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
            )
            status, body = get(session, url)
            if status != 200 or "CryptEasy" not in body:
                return fail(f"home page answered {status}")
            print("home page: 200 OK")

            status, _ = get(session, base + "static/style.css")
            if status != 200:
                return fail(f"style.css answered {status} (static files missing?)")
            print("static files: 200 OK")
        finally:
            stop(proc)

    print("SMOKE TEST OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
