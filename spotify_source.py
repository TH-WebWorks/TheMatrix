"""Spotify playback via Web API (spotipy)."""

from __future__ import annotations

import io
import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

CONFIG_PATH = Path(__file__).resolve().parent / "spotify_config.json"
CACHE_PATH = Path(__file__).resolve().parent / ".spotify_cache"

SCOPES = (
    "user-read-currently-playing "
    "user-read-playback-state "
    "user-modify-playback-state"
)


@dataclass
class SpotifyPlayback:
    connected: bool = False
    playing: bool = False
    track: str = ""
    artist: str = ""
    album: str = ""
    progress_ms: int = 0
    duration_ms: int = 0
    art_url: str = ""
    device: str = ""
    error: str = ""


def load_spotify_config(path: Path = CONFIG_PATH) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("client_id") and data.get("client_secret"):
        return data
    return None


def clear_spotify_cache() -> bool:
    """Remove cached OAuth token (use after network reset or auth errors)."""
    if CACHE_PATH.exists():
        CACHE_PATH.unlink()
        return True
    return False


def save_spotify_config(client_id: str, client_secret: str, redirect_uri: str) -> None:
    CONFIG_PATH.write_text(
        json.dumps(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _format_spotify_error(exc: Exception) -> str:
    try:
        from spotipy.exceptions import SpotifyException
    except ImportError:
        return str(exc)[:80]

    if isinstance(exc, SpotifyException):
        status = getattr(exc, "http_status", None)
        if status == 429:
            retry = 60
            headers = getattr(exc, "headers", None) or {}
            if headers.get("Retry-After"):
                try:
                    retry = int(headers["Retry-After"])
                except ValueError:
                    pass
            if retry >= 3600:
                hours = retry // 3600
                return f"Spotify rate limit — wait ~{hours}h (stop other Matrix instances)"
            return f"Spotify rate limit — retry in {retry}s"
        if status == 401:
            return "Spotify login expired — run: python spotify_setup.py --reauth"
        if status == 403:
            return "Spotify Premium required on this account"
        msg = str(exc).split(":", 1)[-1].strip()
        return (msg or "Spotify API error")[:80]

    if isinstance(exc, (urllib.error.URLError, TimeoutError, OSError)):
        return "No network — check connection to Spotify"
    return str(exc)[:80]


class SpotifySource:
    def __init__(
        self,
        config: dict | None = None,
        poll_interval: float = 2.5,
        on_update: Callable[[SpotifyPlayback], None] | None = None,
    ) -> None:
        self.config = config or load_spotify_config()
        self.poll_interval = poll_interval
        self._base_poll_interval = poll_interval
        self.on_update = on_update
        self.playback = SpotifyPlayback()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sp = None
        self._art_cache_url = ""
        self._art_surface = None
        self._backoff_until = 0.0

    @property
    def art_surface(self):
        return self._art_surface

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _ensure_client(self) -> bool:
        if self._sp is not None:
            return True
        if not self.config:
            self.playback.error = "Missing spotify_config.json"
            return False
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth
        except ImportError:
            self.playback.error = "Install spotipy: pip install spotipy"
            return False

        redirect = self.config.get("redirect_uri", "http://127.0.0.1:8888/callback")
        auth = SpotifyOAuth(
            client_id=self.config["client_id"],
            client_secret=self.config["client_secret"],
            redirect_uri=redirect,
            scope=SCOPES,
            cache_path=str(CACHE_PATH),
            open_browser=False,
        )
        # retries=0: do not block the display thread for hours on 429 responses
        self._sp = spotipy.Spotify(auth_manager=auth, retries=0, requests_timeout=10)
        self.playback.connected = True
        self.playback.error = ""
        return True

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._poll()
            if self.on_update:
                self.on_update(self.playback)
            self._stop.wait(self.poll_interval)

    def _poll(self) -> None:
        if time.time() < self._backoff_until:
            return
        if not self._ensure_client():
            return
        p = self.playback
        try:
            data = self._sp.current_user_playing_track()
        except Exception as exc:
            p.connected = False
            p.error = _format_spotify_error(exc)
            retry = 30
            try:
                from spotipy.exceptions import SpotifyException

                if isinstance(exc, SpotifyException) and exc.http_status == 429:
                    headers = getattr(exc, "headers", None) or {}
                    if headers.get("Retry-After"):
                        retry = max(30, int(headers["Retry-After"]))
            except (ImportError, ValueError):
                pass
            self._backoff_until = time.time() + min(retry, 300)
            return
        self._backoff_until = 0.0
        self.poll_interval = self._base_poll_interval

        p.connected = True
        p.error = ""
        if not data or not data.get("item"):
            p.playing = False
            p.track = ""
            p.artist = ""
            p.album = ""
            p.progress_ms = 0
            p.duration_ms = 0
            p.art_url = ""
            self._art_surface = None
            self._art_cache_url = ""
            return

        item = data["item"]
        p.playing = data.get("is_playing", False)
        p.track = item.get("name", "")
        p.artist = ", ".join(a["name"] for a in item.get("artists", []))
        p.album = (item.get("album") or {}).get("name", "")
        p.progress_ms = int(data.get("progress_ms") or 0)
        p.duration_ms = int(item.get("duration_ms") or 0)

        images = (item.get("album") or {}).get("images") or []
        if images:
            # Prefer medium artwork
            p.art_url = images[min(1, len(images) - 1)]["url"]
            self._fetch_art(p.art_url)

    def _fetch_art(self, url: str) -> None:
        if not url or url == self._art_cache_url:
            return
        try:
            import pygame

            with urllib.request.urlopen(url, timeout=4) as resp:
                raw = resp.read()
            art = pygame.image.load(io.BytesIO(raw)).convert_alpha()
            self._art_cache_url = url
            self._art_surface = art
        except Exception:
            pass

    def play_pause(self) -> None:
        if not self._ensure_client():
            return
        try:
            if self.playback.playing:
                self._sp.pause_playback()
            else:
                self._sp.start_playback()
        except Exception:
            pass

    def next_track(self) -> None:
        if self._ensure_client():
            try:
                self._sp.next_track()
            except Exception:
                pass

    def previous_track(self) -> None:
        if self._ensure_client():
            try:
                self._sp.previous_track()
            except Exception:
                pass


class DemoSpotifySource(SpotifySource):
    """Fake now-playing for --demo."""

    def __init__(self, on_update: Callable[[SpotifyPlayback], None] | None = None) -> None:
        super().__init__(config={"client_id": "demo", "client_secret": "demo"}, on_update=on_update)
        self._t = 0

    def _loop(self) -> None:
        tracks = [
            ("Clubbed to Death", "Rob Dougan", "The Matrix: Music from the Motion Picture"),
            ("Dragula", "Rob Zombie", "Hellbilly Deluxe"),
            ("Mind Heist", "Zack Hemsey", "Inception: Music from the Motion Picture"),
        ]
        while not self._stop.is_set():
            self._t += 1
            idx = (self._t // 20) % len(tracks)
            track, artist, album = tracks[idx]
            p = self.playback
            p.connected = True
            p.playing = True
            p.track = track
            p.artist = artist
            p.album = album
            p.duration_ms = 240_000
            p.progress_ms = (self._t * 1500) % p.duration_ms
            p.device = "DESKTOP"
            p.error = ""
            if self.on_update:
                self.on_update(p)
            self._stop.wait(1.0)

    def _ensure_client(self) -> bool:
        return True

    def play_pause(self) -> None:
        self.playback.playing = not self.playback.playing

    def next_track(self) -> None:
        pass

    def previous_track(self) -> None:
        pass
