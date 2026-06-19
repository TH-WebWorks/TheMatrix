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
    track_id: str = ""
    release_year: str = ""
    popularity: int = 0
    genres: str = ""
    error: str = ""


@dataclass(frozen=True)
class QueueTrack:
    name: str = ""
    artist: str = ""


@dataclass(frozen=True)
class SpotifyDevice:
    id: str = ""
    name: str = ""
    type: str = ""
    is_active: bool = False
    volume: int = 0


def _queue_artist(item: dict) -> str:
    artists = item.get("artists") or []
    names: list[str] = []
    for artist in artists:
        if isinstance(artist, dict):
            name = artist.get("name")
            if name:
                names.append(str(name))
    return ", ".join(names)


def _parse_queue_item(item) -> QueueTrack | None:
    if not isinstance(item, dict):
        return None
    name = str(item.get("name") or "").strip()
    if not name:
        return None
    return QueueTrack(name=name, artist=_queue_artist(item))


def _parse_device_item(item) -> SpotifyDevice | None:
    if not isinstance(item, dict):
        return None
    device_id = str(item.get("id") or "").strip()
    name = str(item.get("name") or "").strip()
    if not device_id or not name:
        return None
    return SpotifyDevice(
        id=device_id,
        name=name,
        type=str(item.get("type") or "").strip(),
        is_active=bool(item.get("is_active")),
        volume=int(item.get("volume_percent") or 0),
    )


def load_spotify_config(path: Path = CONFIG_PATH) -> dict | None:
    """Load Spotify credentials (bundled defaults + optional user override)."""
    try:
        from spotify_connect import get_credentials

        return get_credentials()
    except ImportError:
        pass
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
        poll_interval: float = 3.5,
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
        self._last_poll_time = 0.0
        self._last_track_id = ""
        self._min_poll_playing = max(2.5, poll_interval)
        self._min_poll_idle = max(8.0, poll_interval * 2.5)
        self._min_poll_backoff = 15.0
        self.queue_tracks: list[QueueTrack] = []
        self.devices: list[SpotifyDevice] = []
        self.queue_error: str = ""
        self.devices_error: str = ""

    @property
    def art_surface(self):
        return self._art_surface

    @property
    def backoff_remaining(self) -> float:
        return max(0.0, self._backoff_until - time.time())

    @property
    def last_poll_age(self) -> float:
        if self._last_poll_time <= 0:
            return 0.0
        return max(0.0, time.time() - self._last_poll_time)

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
        needs_login = not CACHE_PATH.exists()
        auth = SpotifyOAuth(
            client_id=self.config["client_id"],
            client_secret=self.config["client_secret"],
            redirect_uri=redirect,
            scope=SCOPES,
            cache_path=str(CACHE_PATH),
            open_browser=False,
        )
        if needs_login:
            self.playback.error = "Press F1 → Connect Spotify to log in"
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
            self._last_poll_time = time.time()
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
            # Honor Spotify Retry-After as-is; capping this causes repeat 429 loops.
            self._backoff_until = time.time() + retry
            self.poll_interval = max(self._min_poll_backoff, float(retry))
            return
        self._backoff_until = 0.0
        self.poll_interval = self._min_poll_playing

        p.connected = True
        p.error = ""
        device = data.get("device") if data else None
        p.device = (device or {}).get("name", "") if device else ""

        if not data or not data.get("item"):
            p.playing = False
            p.track = ""
            p.artist = ""
            p.album = ""
            p.progress_ms = 0
            p.duration_ms = 0
            p.art_url = ""
            p.track_id = ""
            p.release_year = ""
            p.popularity = 0
            p.genres = ""
            p.device = ""
            self._last_track_id = ""
            self._art_surface = None
            self._art_cache_url = ""
            self.poll_interval = self._min_poll_idle
            return

        item = data["item"]
        p.playing = data.get("is_playing", False)
        p.track = item.get("name", "")
        p.artist = ", ".join(a["name"] for a in item.get("artists", []))
        p.album = (item.get("album") or {}).get("name", "")
        p.progress_ms = int(data.get("progress_ms") or 0)
        p.duration_ms = int(item.get("duration_ms") or 0)
        p.track_id = item.get("id", "") or ""
        album = item.get("album") or {}
        release = album.get("release_date") or ""
        p.release_year = release[:4] if release else ""
        self.poll_interval = self._min_poll_playing if p.playing else self._min_poll_idle

        if p.track_id and p.track_id != self._last_track_id:
            self._last_track_id = p.track_id
            self._fetch_track_meta(p)

        images = album.get("images") or []
        if images:
            # Prefer medium artwork
            p.art_url = images[min(1, len(images) - 1)]["url"]
            self._fetch_art(p.art_url)

    def _fetch_track_meta(self, p: SpotifyPlayback) -> None:
        if not self._sp or not p.track_id:
            return
        try:
            track = self._sp.track(p.track_id)
        except Exception:
            return
        p.popularity = int(track.get("popularity") or 0)
        album = track.get("album") or {}
        release = album.get("release_date") or ""
        p.release_year = release[:4] if release else p.release_year
        genres: list[str] = []
        for artist in track.get("artists") or []:
            genres.extend(artist.get("genres") or [])
        if not genres:
            genres = list(album.get("genres") or [])
        p.genres = ", ".join(dict.fromkeys(genres))[:120]

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

    def fetch_queue(self) -> None:
        """Load upcoming queue tracks (call when QUEUE panel opens)."""
        self.queue_tracks = []
        self.queue_error = ""
        if not self._ensure_client():
            self.queue_error = self.playback.error or "not connected"
            return
        try:
            queue_data = self._sp.queue()
        except Exception as exc:
            self.queue_error = _format_spotify_error(exc)[:72]
            return
        if not isinstance(queue_data, dict):
            self.queue_error = "invalid queue response"
            return
        upcoming: list[QueueTrack] = []
        for item in queue_data.get("queue") or []:
            parsed = _parse_queue_item(item)
            if parsed:
                upcoming.append(parsed)
            if len(upcoming) >= 10:
                break
        self.queue_tracks = upcoming

    def fetch_devices(self) -> None:
        """Load Spotify Connect devices (call when DEVICES panel opens)."""
        self.devices = []
        self.devices_error = ""
        if not self._ensure_client():
            self.devices_error = self.playback.error or "not connected"
            return
        try:
            device_data = self._sp.devices()
        except Exception as exc:
            self.devices_error = _format_spotify_error(exc)[:72]
            return
        if not isinstance(device_data, dict):
            self.devices_error = "invalid devices response"
            return
        found: list[SpotifyDevice] = []
        for item in device_data.get("devices") or []:
            parsed = _parse_device_item(item)
            if parsed:
                found.append(parsed)
        self.devices = found

    def transfer_device(self, device_id: str) -> bool:
        if not device_id or not self._ensure_client():
            return False
        try:
            self._sp.transfer_playback(device_id=device_id, force_play=False)
            return True
        except Exception:
            return False


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
            p.track_id = f"demo-{idx}"
            p.release_year = "1999"
            p.popularity = 72 + idx * 5
            p.genres = "soundtrack, electronic"
            p.error = ""
            if self.on_update:
                self.on_update(p)
            self._stop.wait(1.0)

    def _ensure_client(self) -> bool:
        return True

    def play_pause(self) -> None:
        self.playback.playing = not self.playback.playing

    def fetch_queue(self) -> None:
        self.queue_tracks = [
            QueueTrack("Dragula", "Rob Zombie"),
            QueueTrack("Mind Heist", "Zack Hemsey"),
            QueueTrack("Spybreak!", "The Propellerheads"),
        ]
        self.queue_error = ""

    def fetch_devices(self) -> None:
        self.devices = [
            SpotifyDevice("demo-mac", "MacBook Pro", "Computer", True, 72),
            SpotifyDevice("demo-tv", "Living Room TV", "TV", False, 40),
            SpotifyDevice("demo-speaker", "Matrix Speaker", "Speaker", False, 55),
        ]
        self.devices_error = ""

    def transfer_device(self, device_id: str) -> bool:
        for device in self.devices:
            if device.id == device_id:
                self.devices = [
                    SpotifyDevice(
                        d.id,
                        d.name,
                        d.type,
                        d.id == device_id,
                        d.volume,
                    )
                    for d in self.devices
                ]
                self.playback.device = device.name
                return True
        return False

    def next_track(self) -> None:
        pass

    def previous_track(self) -> None:
        pass
