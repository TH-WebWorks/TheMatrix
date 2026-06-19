"""Session event log for the LOG panel; mirrored to logs/session.log."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "session.log"


@dataclass(frozen=True)
class LogEntry:
    time: str
    message: str


class SessionLog:
    def __init__(self, maxlen: int = 80) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=maxlen)
        self._log_path = LOG_FILE
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    def add(self, message: str) -> None:
        text = (message or "").strip()
        if not text:
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        self._entries.appendleft(LogEntry(time=stamp, message=text[:120]))
        self._append_file(stamp, text[:120])

    def _append_file(self, stamp: str, text: str) -> None:
        try:
            with self._log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"{stamp}  {text}\n")
        except OSError:
            pass

    def snapshot(self) -> list[LogEntry]:
        return list(self._entries)
