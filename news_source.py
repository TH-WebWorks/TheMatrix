"""RSS headline fetcher for the NEWS panel."""

from __future__ import annotations

import re
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

_DEFAULT_FEED = "https://feeds.bbci.co.uk/news/rss.xml"
_TAG = re.compile(r"<[^>]+>")


@dataclass
class NewsData:
    headlines: list[str] = field(default_factory=list)
    loading: bool = False
    error: str = ""


class NewsSource:
    """Background RSS fetcher; refreshes on a timer."""

    def __init__(self, feed_url: str = _DEFAULT_FEED, refresh_seconds: float = 900.0) -> None:
        self.feed_url = feed_url
        self.refresh_seconds = refresh_seconds
        self.data = NewsData()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_fetch = 0.0

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

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.refresh()
            self._stop.wait(self.refresh_seconds)

    def refresh(self) -> None:
        with self._lock:
            self.data = NewsData(loading=True)
        result = _fetch_rss(self.feed_url)
        with self._lock:
            self.data = result

    def snapshot(self) -> NewsData:
        with self._lock:
            return NewsData(
                headlines=list(self.data.headlines),
                loading=self.data.loading,
                error=self.data.error,
            )


def _strip_html(text: str) -> str:
    return _TAG.sub("", text).strip()


def _fetch_rss(url: str) -> NewsData:
    data = NewsData()
    req = urllib.request.Request(url, headers={"User-Agent": "TheMatrix/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        data.error = "feed unreachable"
        return data
    except Exception:
        data.error = "feed decode failed"
        return data

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        data.error = "invalid feed"
        return data

    headlines: list[str] = []
    for item in root.iter("item"):
        title_el = item.find("title")
        if title_el is not None and title_el.text:
            title = _strip_html(title_el.text)
            if title:
                headlines.append(title)
        if len(headlines) >= 20:
            break

    if not headlines:
        for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
            title_el = entry.find("{http://www.w3.org/2005/Atom}title")
            if title_el is not None and title_el.text:
                title = _strip_html(title_el.text)
                if title:
                    headlines.append(title)
            if len(headlines) >= 20:
                break

    if not headlines:
        data.error = "no headlines in feed"
        return data
    data.headlines = headlines[:20]
    return data
