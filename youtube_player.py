"""Satellite YouTube embed player (pywebview subprocess)."""

from __future__ import annotations

import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

_HELPER = Path(__file__).resolve().parent / "youtube_embed_browser.py"


def youtube_embed_url(video_id: str, *, autoplay: bool = True) -> str:
    vid = "".join(ch for ch in (video_id or "") if ch.isalnum() or ch in "-_")[:32]
    if not vid:
        return ""
    params = "autoplay=1" if autoplay else "autoplay=0"
    return f"https://www.youtube-nocookie.com/embed/{vid}?{params}&rel=0&modestbranding=1"


class YouTubePlayer:
    """Opens a YouTube embed in a native webview beside the Matrix display."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self.mode = "idle"  # idle | webview | fallback
        self.video_id = ""
        self.title = ""

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def play(
        self,
        video_id: str,
        *,
        title: str = "",
        width: int = 720,
        height: int = 405,
    ) -> str:
        """Return mode used: webview, fallback, or open (already playing same video)."""
        url = youtube_embed_url(video_id)
        if not url:
            self.mode = "idle"
            return "idle"

        with self._lock:
            if (
                self._proc is not None
                and self._proc.poll() is None
                and self.video_id == video_id
            ):
                self.title = title or self.title
                return "open"

        self.close()

        try:
            import webview  # noqa: F401
        except ImportError:
            webbrowser.open(f"https://www.youtube.com/watch?v={video_id}")
            self.video_id = video_id
            self.title = title
            self.mode = "fallback"
            return "fallback"

        if not _HELPER.is_file():
            webbrowser.open(f"https://www.youtube.com/watch?v={video_id}")
            self.video_id = video_id
            self.title = title
            self.mode = "fallback"
            return "fallback"

        proc = subprocess.Popen(
            [
                sys.executable,
                str(_HELPER),
                "--video-id",
                video_id,
                "--title",
                title[:96],
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
        self.video_id = video_id
        self.title = title
        self.mode = "webview"
        return "webview"

    def close(self) -> None:
        with self._lock:
            proc = self._proc
            self._proc = None
        if proc is None:
            self.mode = "idle"
            self.video_id = ""
            self.title = ""
            return
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)
        self.mode = "idle"
        self.video_id = ""
        self.title = ""

    def sync(self) -> None:
        """Drop stale state if the user closed the webview window."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is not None:
                self._proc = None
                self.mode = "idle"
                self.video_id = ""
                self.title = ""
