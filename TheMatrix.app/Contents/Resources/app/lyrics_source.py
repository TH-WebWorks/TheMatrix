"""Fetch song lyrics (LRCLIB) for the CONDUIT decode panel."""

from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

_LRC_TAG = re.compile(
    r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\](.*)",
)


@dataclass
class LyricsData:
    track: str = ""
    artist: str = ""
    duration_ms: int = 0
    synced: list[tuple[int, str]] = field(default_factory=list)
    plain: str = ""
    loading: bool = False
    error: str = ""

    @property
    def ready(self) -> bool:
        return bool(self.synced or self.plain) and not self.loading

    def key(self) -> tuple[str, str, int]:
        return (self.track, self.artist, self.duration_ms)


def parse_lrc(text: str) -> list[tuple[int, str]]:
    """Parse LRC synced lyrics into (time_ms, line) pairs."""
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        for match in _LRC_TAG.finditer(raw):
            mins = int(match.group(1))
            secs = int(match.group(2))
            frac = match.group(3) or "0"
            frac_ms = int(frac.ljust(3, "0")[:3])
            lyric = match.group(4).strip()
            if lyric:
                ms = (mins * 60 + secs) * 1000 + frac_ms
                lines.append((ms, lyric))
    lines.sort(key=lambda item: item[0])
    return lines


def _fetch_lrclib(track: str, artist: str, album: str, duration_ms: int) -> dict | None:
    duration_s = max(1, duration_ms // 1000)
    params = urllib.parse.urlencode(
        {
            "track_name": track,
            "artist_name": artist,
            "album_name": album,
            "duration": duration_s,
        }
    )
    url = f"https://lrclib.net/api/get?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "TheMatrix/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def _fetch_lrclib_search(track: str, artist: str) -> dict | None:
    query = f"{track} {artist}".strip()
    if not query:
        return None
    params = urllib.parse.urlencode({"q": query})
    url = f"https://lrclib.net/api/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "TheMatrix/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        results = json.loads(resp.read().decode("utf-8"))
    if not results:
        return None
    return results[0]


def fetch_lyrics(track: str, artist: str, album: str, duration_ms: int) -> LyricsData:
    """Blocking fetch — run off the main thread."""
    data = LyricsData(track=track, artist=artist, duration_ms=duration_ms, loading=True)
    if not track:
        data.loading = False
        data.error = "no track"
        return data
    try:
        payload = _fetch_lrclib(track, artist, album, duration_ms)
        if payload is None:
            payload = _fetch_lrclib_search(track, artist)
        if not payload:
            data.loading = False
            data.error = "no lyrics in signal"
            return data
        synced_raw = payload.get("syncedLyrics") or ""
        plain_raw = payload.get("plainLyrics") or ""
        if synced_raw:
            data.synced = parse_lrc(synced_raw)
        if plain_raw:
            data.plain = plain_raw.strip()
        if not data.synced and not data.plain:
            data.error = "no lyrics in signal"
    except Exception:
        data.error = "lyrics decode failed"
    data.loading = False
    return data


_DEMO_LYRICS: dict[str, list[tuple[int, str]]] = {
    "Clubbed to Death": [
        (0, "Oh yes"),
        (8000, "I'm afraid"),
        (16000, "Close your eyes"),
        (24000, "Count to ten"),
        (32000, "Go to sleep"),
        (40000, "Go to sleep"),
        (48000, "Go to sleep"),
    ],
    "Dragula": [
        (0, "Dead I am the one"),
        (6000, "Exterminating son"),
        (12000, "Slipping through the trees"),
        (18000, "Strangling the breeze"),
        (24000, "Dead I am the sky"),
        (30000, "Watching angels cry"),
    ],
    "Mind Heist": [
        (0, "Mind heist"),
        (5000, "Rising tension"),
        (12000, "Building pressure"),
        (20000, "The dream is real"),
        (28000, "Time is running"),
    ],
}


def demo_lyrics(track: str, artist: str, duration_ms: int) -> LyricsData:
    synced = _DEMO_LYRICS.get(track, [(0, f"{track} — {artist}")])
    return LyricsData(
        track=track,
        artist=artist,
        duration_ms=duration_ms,
        synced=synced,
        plain="\n".join(line for _, line in synced),
    )


class LyricsSource:
    """Background lyrics fetcher keyed to the current track."""

    def __init__(self, *, demo: bool = False) -> None:
        self.demo = demo
        self.data = LyricsData()
        self._lock = threading.Lock()
        self._pending_key: tuple[str, str, str, int] | None = None
        self._thread: threading.Thread | None = None

    def request(self, track: str, artist: str, album: str, duration_ms: int) -> None:
        key = (track, artist, album, duration_ms)
        with self._lock:
            if self.data.key() == (track, artist, duration_ms) and (self.data.ready or self.data.loading):
                return
            if self._pending_key == key:
                return
            self._pending_key = key
            self.data = LyricsData(track=track, artist=artist, duration_ms=duration_ms, loading=True)

        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_fetch, args=key, daemon=True)
        self._thread.start()

    def _run_fetch(self, track: str, artist: str, album: str, duration_ms: int) -> None:
        if self.demo:
            result = demo_lyrics(track, artist, duration_ms)
        else:
            result = fetch_lyrics(track, artist, album, duration_ms)
        with self._lock:
            self._pending_key = None
            if (track, artist, duration_ms) == (self.data.track, self.data.artist, self.data.duration_ms):
                self.data = result

    def snapshot(self) -> LyricsData:
        with self._lock:
            return LyricsData(
                track=self.data.track,
                artist=self.data.artist,
                duration_ms=self.data.duration_ms,
                synced=list(self.data.synced),
                plain=self.data.plain,
                loading=self.data.loading,
                error=self.data.error,
            )


def current_lyric_window(
    data: LyricsData,
    progress_ms: int,
) -> tuple[str, str, str]:
    """Return (previous, current, next) lyric lines for the given playback position."""
    if data.synced:
        idx = 0
        for i, (t, _) in enumerate(data.synced):
            if t <= progress_ms:
                idx = i
            else:
                break
        prev_line = data.synced[idx - 1][1] if idx > 0 else ""
        cur_line = data.synced[idx][1]
        next_line = data.synced[idx + 1][1] if idx + 1 < len(data.synced) else ""
        return prev_line, cur_line, next_line

    if data.plain:
        lines = [ln.strip() for ln in data.plain.splitlines() if ln.strip()]
        if not lines:
            return "", "", ""
        if data.duration_ms > 0:
            ratio = max(0.0, min(1.0, progress_ms / data.duration_ms))
            idx = min(len(lines) - 1, int(ratio * len(lines)))
        else:
            idx = 0
        prev_line = lines[idx - 1] if idx > 0 else ""
        cur_line = lines[idx]
        next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
        return prev_line, cur_line, next_line

    return "", "", ""


def wrap_lyric_line(text: str, font, max_width: int) -> list[str]:
    if not text or max_width <= 0:
        return []
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if font.size(trial)[0] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines
