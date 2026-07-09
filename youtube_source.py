"""YouTube Data API v3 song search support."""

from __future__ import annotations

import html
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "youtube_config.json"
_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


@dataclass(frozen=True)
class YouTubeResult:
    video_id: str
    title: str
    channel: str = ""
    description: str = ""
    published_at: str = ""

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def embed_url(self) -> str:
        return f"https://www.youtube-nocookie.com/embed/{self.video_id}?autoplay=1&rel=0"


@dataclass
class YouTubeSearchState:
    query: str = ""
    results: list[YouTubeResult] = field(default_factory=list)
    loading: bool = False
    error: str = ""


def load_youtube_config(path: Path = CONFIG_PATH) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    api_key = str(data.get("api_key") or "").strip()
    if not api_key:
        return None
    return {"api_key": api_key}


def youtube_configured(path: Path = CONFIG_PATH) -> bool:
    return load_youtube_config(path) is not None


def save_youtube_config(api_key: str, path: Path = CONFIG_PATH) -> None:
    path.write_text(json.dumps({"api_key": api_key.strip()}, indent=2), encoding="utf-8")


def _clean_text(value: object, limit: int) -> str:
    text = html.unescape(str(value or "")).replace("\n", " ").replace("\r", " ").strip()
    return " ".join(text.split())[:limit]


def _format_youtube_api_error(message: str, status: int = 0) -> str:
    lower = message.lower()
    if "blocked" in lower or status == 403:
        return (
            "YouTube API blocked — in Google Cloud: enable YouTube Data API v3, "
            "then edit your API key restrictions to allow it"
        )
    if status == 400 and "api key" in lower:
        return "invalid YouTube API key"
    if status == 429:
        return "YouTube API quota exceeded — try again later"
    return message[:120]


class YouTubeSource:
    """On-demand YouTube song search with background fetch."""

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or load_youtube_config()
        self._lock = threading.Lock()
        self.state = YouTubeSearchState()
        self._request_id = 0

    def configured(self) -> bool:
        return bool((self.config or {}).get("api_key"))

    def reload_config(self) -> None:
        self.config = load_youtube_config()

    def snapshot(self) -> YouTubeSearchState:
        with self._lock:
            return YouTubeSearchState(
                query=self.state.query,
                results=list(self.state.results),
                loading=self.state.loading,
                error=self.state.error,
            )

    def search(self, query: str) -> bool:
        text = " ".join((query or "").split()).strip()
        if not text:
            with self._lock:
                self.state = YouTubeSearchState(query="", results=[], loading=False, error="enter a search query")
            return False
        if not self.configured():
            with self._lock:
                self.state = YouTubeSearchState(
                    query=text,
                    results=[],
                    loading=False,
                    error="add youtube api key in settings (F1)",
                )
            return False
        with self._lock:
            self._request_id += 1
            request_id = self._request_id
            self.state = YouTubeSearchState(query=text, results=[], loading=True, error="")
        thread = threading.Thread(target=self._search_worker, args=(request_id, text), daemon=True)
        thread.start()
        return True

    def _search_worker(self, request_id: int, query: str) -> None:
        result = _fetch_youtube_results((self.config or {}).get("api_key", ""), query)
        with self._lock:
            if request_id != self._request_id:
                return
            self.state = result


def _fetch_youtube_results(api_key: str, query: str) -> YouTubeSearchState:
    state = YouTubeSearchState(query=query, loading=False)
    params = urllib.parse.urlencode(
        {
            "part": "snippet",
            "type": "video",
            "videoCategoryId": "10",
            "maxResults": "10",
            "q": query,
            "key": api_key,
        }
    )
    req = urllib.request.Request(f"{_SEARCH_URL}?{params}", headers={"User-Agent": "TheMatrix/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            message = _clean_text(((data.get("error") or {}).get("message") or "youtube api error"), 160)
        except (OSError, json.JSONDecodeError):
            message = "youtube api error"
        state.error = _format_youtube_api_error(message, exc.code)
        return state
    except (urllib.error.URLError, TimeoutError, OSError):
        state.error = "youtube search unavailable"
        return state
    except Exception:
        state.error = "youtube response decode failed"
        return state

    items = payload.get("items")
    if not isinstance(items, list):
        state.error = "invalid youtube response"
        return state

    results: list[YouTubeResult] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ident = item.get("id") or {}
        snippet = item.get("snippet") or {}
        video_id = _clean_text(ident.get("videoId"), 32)
        title = _clean_text(snippet.get("title"), 120)
        if not video_id or not title:
            continue
        results.append(
            YouTubeResult(
                video_id=video_id,
                title=title,
                channel=_clean_text(snippet.get("channelTitle"), 80),
                description=_clean_text(snippet.get("description"), 180),
                published_at=_clean_text(snippet.get("publishedAt"), 32)[:10],
            )
        )
        if len(results) >= 10:
            break

    if not results:
        state.error = "no youtube matches"
        return state

    state.results = results
    return state
