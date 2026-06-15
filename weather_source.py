"""Weather fetcher for the WEATHER panel (wttr.in, no API key)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field

_WTTR_URL = "https://wttr.in/?format=j1"


@dataclass
class WeatherData:
    lines: list[str] = field(default_factory=list)
    location: str = ""
    loading: bool = False
    error: str = ""


class WeatherSource:
    """Background weather fetcher; refreshes on a timer."""

    def __init__(self, refresh_seconds: float = 1800.0) -> None:
        self.refresh_seconds = refresh_seconds
        self.data = WeatherData()
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
            self.data = WeatherData(loading=True)
        result = _fetch_weather()
        with self._lock:
            self.data = result

    def snapshot(self) -> WeatherData:
        with self._lock:
            return WeatherData(
                lines=list(self.data.lines),
                location=self.data.location,
                loading=self.data.loading,
                error=self.data.error,
            )


def _fetch_weather() -> WeatherData:
    data = WeatherData()
    req = urllib.request.Request(_WTTR_URL, headers={"User-Agent": "curl/7.64"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        data.error = "weather signal unreachable"
        return data
    except Exception:
        data.error = "weather decode failed"
        return data

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        data.error = "invalid weather signal"
        return data

    if not isinstance(payload, dict):
        data.error = "invalid weather signal"
        return data

    location = ""
    areas = payload.get("nearest_area")
    if isinstance(areas, list) and areas:
        area = areas[0]
        if isinstance(area, dict):
            names = area.get("areaName")
            if isinstance(names, list) and names:
                first = names[0]
                if isinstance(first, dict) and first.get("value"):
                    location = str(first["value"])

    lines: list[str] = []
    current = payload.get("current_condition")
    if isinstance(current, list) and current:
        row = current[0]
        if isinstance(row, dict):
            temp = row.get("temp_C") or row.get("temp_F") or "?"
            desc = ""
            weather_desc = row.get("weatherDesc")
            if isinstance(weather_desc, list) and weather_desc:
                item = weather_desc[0]
                if isinstance(item, dict) and item.get("value"):
                    desc = str(item["value"])
            humidity = row.get("humidity")
            wind = row.get("windspeedKmph")
            line = f"NOW {temp}C {desc}".strip()
            if humidity:
                line += f" · {humidity}% humidity"
            if wind:
                line += f" · wind {wind} km/h"
            lines.append(line)

    weather_days = payload.get("weather")
    if isinstance(weather_days, list):
        for day in weather_days[:2]:
            if not isinstance(day, dict):
                continue
            date = str(day.get("date") or "")
            hourly = day.get("hourly")
            if not isinstance(hourly, list):
                continue
            for hour in hourly[::4]:
                if not isinstance(hour, dict):
                    continue
                time_val = str(hour.get("time") or "")
                if len(time_val) == 4 and time_val.isdigit():
                    time_val = f"{time_val[:2]}:{time_val[2:]}"
                temp = hour.get("tempC") or hour.get("tempF") or "?"
                desc = ""
                weather_desc = hour.get("weatherDesc")
                if isinstance(weather_desc, list) and weather_desc:
                    item = weather_desc[0]
                    if isinstance(item, dict) and item.get("value"):
                        desc = str(item["value"])
                label = f"{date} {time_val}".strip()
                lines.append(f"{label} · {temp}C {desc}".strip())
                if len(lines) >= 12:
                    break
            if len(lines) >= 12:
                break

    if not lines:
        data.error = "no weather in signal"
        return data

    data.location = location
    data.lines = lines[:12]
    return data
