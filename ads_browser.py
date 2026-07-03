"""Satellite MacRumors browser window (pywebview subprocess)."""

from __future__ import annotations

import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

_URL = "https://www.macrumors.com/"
_HELPER = Path(__file__).resolve().parent / "macrumors_browser.py"


class MacRumorsBrowser:
    """Opens macrumors.com in a native webview beside the Matrix display."""

    def __init__(self, url: str = _URL) -> None:
        self.url = url
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self.mode = "idle"  # idle | webview | fallback

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def launch(self, *, width: int = 1000, height: int = 900) -> str:
        """Return mode used: webview, fallback, or open (already running)."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return "open"

        try:
            import webview  # noqa: F401
        except ImportError:
            webbrowser.open(self.url)
            self.mode = "fallback"
            return "fallback"

        if not _HELPER.is_file():
            webbrowser.open(self.url)
            self.mode = "fallback"
            return "fallback"

        proc = subprocess.Popen(
            [
                sys.executable,
                str(_HELPER),
                "--url",
                self.url,
                "--width",
                str(width),
                "--height",
                str(height),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with self._lock:
            self._proc = proc
        self.mode = "webview"
        return "webview"

    def close(self) -> None:
        with self._lock:
            proc = self._proc
            self._proc = None
        if proc is None:
            self.mode = "idle"
            return
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)
        self.mode = "idle"

    def sync(self) -> None:
        """Drop stale state if the user closed the webview window."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is not None:
                self._proc = None
                self.mode = "idle"
