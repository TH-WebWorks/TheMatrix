"""In-memory session event log for the LOG panel."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LogEntry:
    time: str
    message: str


class SessionLog:
    def __init__(self, maxlen: int = 80) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=maxlen)

    def add(self, message: str) -> None:
        text = (message or "").strip()
        if not text:
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        self._entries.appendleft(LogEntry(time=stamp, message=text[:120]))

    def snapshot(self) -> list[LogEntry]:
        return list(self._entries)
