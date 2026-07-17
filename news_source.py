"""RSS headline fetcher for the NEWS panel."""

from __future__ import annotations

import re
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

_DEFAULT_FEED = "https://feeds.bbci.co.uk/news/rss.xml"
_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class NewsHeadline:
    title: str
    when: str = ""
    summary: str = ""
    url: str = ""


@dataclass
class NewsData:
    headlines: list[NewsHeadline] = field(default_factory=list)
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


def _format_when(pub_text: str) -> str:
    try:
        dt = parsedate_to_datetime(pub_text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone()
        now = datetime.now(local.tzinfo)
        age_h = (now - local).total_seconds() / 3600
        if age_h < 1:
            return f"{max(1, int(age_h * 60))}m"
        if age_h < 48:
            return f"{int(age_h)}h"
        return local.strftime("%d %b")
    except (ValueError, TypeError, OSError):
        return ""


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

    headlines: list[NewsHeadline] = []
    for item in root.iter("item"):
        title_el = item.find("title")
        if title_el is None or not title_el.text:
            continue
        title = _strip_html(title_el.text)
        if not title:
            continue
        when = ""
        pub_el = item.find("pubDate")
        if pub_el is not None and pub_el.text:
            when = _format_when(pub_el.text)
        url = ""
        link_el = item.find("link")
        if link_el is not None and link_el.text:
            url = link_el.text.strip()
        summary = ""
        desc_el = item.find("description")
        if desc_el is not None and desc_el.text:
            summary = _strip_html(desc_el.text)
        headlines.append(NewsHeadline(title=title, when=when, summary=summary, url=url))
        if len(headlines) >= 20:
            break

    if not headlines:
        for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
            title_el = entry.find("{http://www.w3.org/2005/Atom}title")
            if title_el is None or not title_el.text:
                continue
            title = _strip_html(title_el.text)
            if not title:
                continue
            when = ""
            updated = entry.find("{http://www.w3.org/2005/Atom}updated")
            if updated is not None and updated.text:
                try:
                    dt = datetime.fromisoformat(updated.text.replace("Z", "+00:00"))
                    when = _format_when(dt.strftime("%a, %d %b %Y %H:%M:%S %z"))
                except ValueError:
                    when = ""
            url = ""
            link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            if link_el is not None:
                url = (link_el.get("href") or "").strip()
            summary = ""
            summary_el = entry.find("{http://www.w3.org/2005/Atom}summary")
            if summary_el is not None and summary_el.text:
                summary = _strip_html(summary_el.text)
            headlines.append(NewsHeadline(title=title, when=when, summary=summary, url=url))
            if len(headlines) >= 20:
                break

    if not headlines:
        data.error = "no headlines in feed"
        return data
    data.headlines = headlines[:20]
    return data
