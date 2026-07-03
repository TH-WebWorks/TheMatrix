"""Fullscreen Matrix digital rain with Spotify overlay."""

from __future__ import annotations

import argparse
import math
import random
import sys
from collections import deque
from datetime import datetime

import pygame

from display_setup import create_fullscreen_surface, list_displays
from font_setup import default_font_name, get_font
from lyrics_source import (
    LyricsData,
    LyricsSource,
    current_lyric_index,
    current_lyric_window,
    lyric_lines,
    wrap_lyric_line,
)
from matrix_ui import draw_keybind_table, keybind_rows
from ads_browser import MacRumorsBrowser
from news_source import NewsSource
from session_log import SessionLog
from weather_source import WeatherSource
from panels.hex_dump import format_hex_lines
from panels.registry import (
    PANEL_BY_ID,
    PANEL_BY_KEY,
    PanelRegistry,
    draw_dock_tabs,
    draw_panel_shell,
    draw_scrollbar,
    panel_bounds,
)
from settings_menu import open_settings_menu
from spotify_connect import is_logged_in
from spotify_source import (
    DemoSpotifySource,
    QueueTrack,
    SpotifyDevice,
    SpotifyPlayback,
    SpotifySource,
)

# Matrix palette
HEAD = (185, 255, 185)
BRIGHT = (80, 255, 120)
MID = (0, 170, 70)
DIM = (0, 55, 28)
UI_DIM = (50, 140, 75)
PANEL = (0, 18, 8)
WARN = (255, 200, 60)
SPOTIFY_GREEN = (30, 215, 96)

MATRIX_CHARS = (
    "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
    "0123456789ABCDEFabcdef"
    "アイウエオカキクケコサシスセソタチツテトナニヌネノ"
)


class RainColumn:
    __slots__ = ("x", "y", "speed", "length", "chars", "bright_head")

    def __init__(self, x: int, height: int, char_size: int) -> None:
        self.x = x
        self.speed = random.uniform(2.5, 9.0)
        self.length = random.randint(8, max(12, height // char_size // 3))
        self.chars = [random.choice(MATRIX_CHARS) for _ in range(self.length)]
        self.y = random.uniform(-self.length * char_size, height)
        self.bright_head = random.random() > 0.35

    def step(self, height: int, char_size: int) -> None:
        self.y += self.speed
        if self.y - self.length * char_size > height:
            self.y = random.uniform(-self.length * char_size, -char_size)
            self.speed = random.uniform(2.5, 9.0)
            self.length = random.randint(8, max(12, height // char_size // 3))
            self.chars = [random.choice(MATRIX_CHARS) for _ in range(self.length)]
            self.bright_head = random.random() > 0.35
        if random.random() < 0.02:
            i = random.randrange(self.length)
            self.chars[i] = random.choice(MATRIX_CHARS)


def _matrix_tint(surface: pygame.Surface) -> pygame.Surface:
    tinted = surface.copy()
    overlay = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 80, 30, 140))
    tinted.blit(overlay, (0, 0))
    glow = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)
    glow.fill((120, 255, 160, 40))
    tinted.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)
    return tinted


def _fmt_time(ms: int) -> str:
    s = max(0, ms // 1000)
    return f"{s // 60}:{s % 60:02d}"


def _bytes_to_bits(data: bytes) -> list[int]:
    bits: list[int] = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


def _conduit_payload(sp: SpotifyPlayback, activity: deque[str], lyrics: LyricsData | None = None) -> bytes:
    """UTF-8 byte stream of everything on screen — the 'captured signal'."""
    lines: list[str] = []
    if sp.track:
        lines.extend([sp.track, sp.artist, sp.album])
    lines.append(f"{_fmt_time(sp.progress_ms)}/{_fmt_time(sp.duration_ms)}")
    lines.append(f"live={sp.connected} play={sp.playing}")
    if sp.error:
        lines.append(sp.error[:200])
    if lyrics and lyrics.ready:
        _, cur, nxt = current_lyric_window(lyrics, sp.progress_ms)
        if cur:
            lines.append(cur)
        if nxt:
            lines.append(nxt)
    act = list(activity)
    if sp.track and (not act or not act[0].endswith(sp.track)):
        act = [f"♫ {sp.track}"] + act
    lines.extend(act[:16])
    blob = "\x1e".join(lines).encode("utf-8", errors="replace")
    return blob if blob else b"\x00"


def _tint_glyph(src: pygame.Surface, rgb: tuple[int, int, int], level: float) -> pygame.Surface:
    out = src.copy()
    c = (int(rgb[0] * level), int(rgb[1] * level), int(rgb[2] * level))
    out.fill((*c, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return out


def _surface_to_reveal_bits(surface: pygame.Surface, gw: int, gh: int) -> list[int]:
    """Rasterize image into gw×gh bits (row-major). Bright pixels become 1."""
    gw = max(8, gw)
    gh = max(8, gh)
    scaled = pygame.transform.smoothscale(surface, (gw, gh))
    bits: list[int] = []
    for y in range(gh):
        for x in range(gw):
            r, g, b = scaled.get_at((x, y))[:3]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            thresh = 118 + ((x + y * 3) & 3) * 14
            bits.append(1 if lum > thresh else 0)
    return bits


def _text_fallback_surface(track: str, artist: str, font: pygame.font.Font) -> pygame.Surface:
    """Glyph portrait when album art is unavailable."""
    size = 320
    surf = pygame.Surface((size, size))
    surf.fill((0, 0, 0))
    line1 = font.render((track or "NO SIGNAL")[:22], True, (240, 255, 240))
    line2 = font.render((artist or "")[:26], True, (120, 200, 120))
    surf.blit(line1, ((size - line1.get_width()) // 2, size // 2 - line1.get_height() - 6))
    surf.blit(line2, ((size - line2.get_width()) // 2, size // 2 + 8))
    return surf


def _decode_answer(sp: SpotifyPlayback, lyrics: LyricsData | None = None) -> str:
    if lyrics and lyrics.ready and sp.track:
        _, cur, _ = current_lyric_window(lyrics, sp.progress_ms)
        if cur:
            return cur
    if sp.track:
        if sp.artist:
            return f"{sp.track} — {sp.artist}"
        return sp.track
    if sp.error:
        return sp.error[:72]
    return "awaiting transmission"


def _conduit_glyph_variants(
    font: pygame.font.Font,
) -> tuple[list[pygame.Surface], list[pygame.Surface], int, int]:
    base_0 = font.render("0", True, (255, 255, 255))
    base_1 = font.render("1", True, (255, 255, 255))
    levels = (0.38, 0.52, 0.68, 0.84, 1.0)
    zeros = [_tint_glyph(base_0, DIM, lv) for lv in levels]
    ones = [_tint_glyph(base_1, HEAD, lv) for lv in levels]
    return zeros, ones, base_0.get_width(), base_0.get_height()


def _draw_matrix_cursor(
    screen: pygame.Surface,
    x: int,
    y: int,
    scale: float,
    pulse: float,
    frame: int,
) -> None:
    """Green phosphor crosshair with bracket corners and a soft trail."""
    glow = 0.75 + 0.25 * math.sin(pulse * 2.1)
    core = (
        int(HEAD[0] * glow),
        int(HEAD[1] * glow),
        int(HEAD[2] * glow),
    )
    ring = (int(BRIGHT[0] * glow * 0.7), int(BRIGHT[1] * glow * 0.7), int(BRIGHT[2] * glow * 0.7))
    arm = int(14 * scale)
    bracket = int(10 * scale)
    gap = int(5 * scale)

    trail = pygame.Surface((int(48 * scale), int(48 * scale)), pygame.SRCALPHA)
    pygame.draw.circle(trail, (*BRIGHT, 28), (trail.get_width() // 2, trail.get_height() // 2), int(16 * scale))
    screen.blit(trail, (x - trail.get_width() // 2, y - trail.get_height() // 2))

    pygame.draw.line(screen, ring, (x - arm, y), (x - gap, y), max(1, int(2 * scale)))
    pygame.draw.line(screen, ring, (x + gap, y), (x + arm, y), max(1, int(2 * scale)))
    pygame.draw.line(screen, ring, (x, y - arm), (x, y - gap), max(1, int(2 * scale)))
    pygame.draw.line(screen, ring, (x, y + gap), (x, y + arm), max(1, int(2 * scale)))

    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        bx, by = x + dx * bracket, y + dy * bracket
        pygame.draw.line(screen, core, (bx, by), (bx + dx * int(6 * scale), by), 2)
        pygame.draw.line(screen, core, (bx, by), (bx, by + dy * int(6 * scale)), 2)

    pygame.draw.circle(screen, core, (x, y), max(2, int(3 * scale)))
    bit_ch = "1" if (frame // 8) % 2 else "0"
    tip_font = get_font(max(9, int(10 * scale)))
    tip = tip_font.render(bit_ch, True, BRIGHT)
    screen.blit(tip, (x + int(8 * scale), y + int(8 * scale)))


class MatrixDisplay:
    def __init__(
        self,
        spotify: SpotifySource | None,
        font_name: str | None = None,
        char_size: int | None = None,
        display_index: int | None = None,
        exclusive: bool = False,
        display_mode: str = "windowed",
        window_size: tuple[int, int] | None = None,
    ) -> None:
        self.spotify = spotify
        self.font_name = font_name
        self.char_size = char_size
        self.display_index = display_index
        self.exclusive = exclusive
        self.display_mode = "exclusive" if exclusive else display_mode
        self.window_size = window_size
        self.spotify_playback = SpotifyPlayback()
        self.inject_queue: list[str] = []
        self.activity: deque[str] = deque(maxlen=24)
        self._last_track = ""
        self._running = True
        self._scroll = 0
        self.panels = PanelRegistry()
        self._hex_prev_payload: bytes = b""
        self._fps = 0.0
        self._lyrics_user_scroll = False
        self._conduit_key: tuple = ()
        self._conduit_bits: list[int] = []
        self._reveal_key: tuple = ()
        self._reveal_bits: list[int] = []
        self._reveal_w = 0
        self._reveal_h = 0
        self._decode_answer = "awaiting transmission"
        self.lyrics = LyricsSource(demo=isinstance(spotify, DemoSpotifySource))
        self.news = NewsSource()
        self.ads_browser = MacRumorsBrowser()
        self.weather = WeatherSource()
        self.session_log = SessionLog()
        self._last_error = ""

    def _device_id_at(self, mx: int, my: int, w: int, h: int, margin: int, scale: float) -> str | None:
        if not self.spotify or self.panels.active != "devices":
            return None
        px, py, panel_w, panel_h = panel_bounds(w, h, margin)
        inner_x = px + int(16 * scale)
        inner_y = py + int(62 * scale)
        inner_w = panel_w - int(32 * scale)
        inner_h = panel_h - int(62 * scale) - int(52 * scale)
        if mx < inner_x or mx > inner_x + inner_w or my < inner_y or my > inner_y + inner_h:
            return None
        devices = list(getattr(self.spotify, "devices", None) or [])
        if not devices:
            return None
        line_h = int(30 * scale)
        scroll = self.panels.scroll_for("devices")
        idx = (my - inner_y + scroll) // line_h
        if 0 <= idx < len(devices):
            return devices[idx].id
        return None

    def _on_panel_opened(self, panel_id: str) -> None:
        self.session_log.add(f"panel: {panel_id}")
        if panel_id == "lyrics":
            self._lyrics_user_scroll = False
        elif panel_id == "queue" and self.spotify:
            self.spotify.fetch_queue()
        elif panel_id == "devices" and self.spotify:
            self.spotify.fetch_devices()
        elif panel_id == "ads":
            mode = self.ads_browser.launch()
            self.session_log.add(f"ads: {mode}")

    def _on_panel_closed(self, panel_id: str) -> None:
        if panel_id == "ads":
            self.ads_browser.close()

    def _panel_toggle(self, panel_id: str) -> None:
        prev = self.panels.active
        was_open = prev == panel_id
        self.panels.toggle(panel_id)
        new = self.panels.active
        if prev == "ads" and new != "ads":
            self._on_panel_closed("ads")
        if new == panel_id and not was_open:
            self._on_panel_opened(panel_id)

    def _panel_minimize(self) -> None:
        prev = self.panels.active
        self.panels.close()
        if prev == "ads":
            self._on_panel_closed("ads")

    def _log_key(self, key: int) -> None:
        name = pygame.key.name(key).upper()
        if not name or name == "UNKNOWN":
            return
        self.session_log.add(f"key: {name}")

    def run(self) -> str:
        reopen_settings = False
        toggle_display = False
        screen, w, h, scale, _used_display = create_fullscreen_surface(
            self.display_index,
            exclusive=self.exclusive,
            mode=self.display_mode,
            window_size=self.window_size,
        )
        char_size = self.char_size or max(14, int(18 * scale))
        margin = int(28 * scale)
        pygame.mouse.set_visible(False)

        family = self.font_name or default_font_name()
        font = get_font(char_size, name=family)
        font_lg = get_font(int(32 * scale), name=family, bold=True)
        font_md = get_font(int(22 * scale), name=family)
        font_sm = get_font(int(16 * scale), name=family)
        font_xl = get_font(int(40 * scale), name=family, bold=True)
        font_track = get_font(int(28 * scale), name=family, bold=True)
        font_bin = get_font(max(11, int(13 * scale)), name=family)
        font_conduit = get_font(max(9, int(10 * scale)), name=family)
        glyph_zeros, glyph_ones, cell_w, cell_h = _conduit_glyph_variants(font_conduit)

        cols = max(1, w // char_size)
        columns = [
            RainColumn(i * char_size + char_size // 2, h, char_size)
            for i in range(cols)
        ]

        fade = pygame.Surface((w, h), pygame.SRCALPHA)
        fade.fill((0, 0, 0, 28))

        clock = pygame.time.Clock()
        pulse = 0.0
        frame = 0

        def on_spotify(p: SpotifyPlayback) -> None:
            if p.track and p.track != self._last_track:
                self._last_track = p.track
                line = f"♫ {p.track} — {p.artist}"
                self.activity.appendleft(line)
                self.session_log.add(f"track: {p.track} — {p.artist}")
                if line not in self.inject_queue and len(self.inject_queue) < 8:
                    self.inject_queue.append(line.upper())
            if p.error and p.error != self._last_error:
                self._last_error = p.error
                self.session_log.add(f"spotify: {p.error[:72]}")
            elif not p.error:
                self._last_error = ""
            if p.track:
                self.lyrics.request(p.track, p.artist, p.album, p.duration_ms)
            self.spotify_playback = p

        if self.spotify:
            self.spotify.on_update = on_spotify
            self.spotify.start()
        self.news.start()
        self.weather.start()
        self.session_log.add("session: matrix online")

        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                elif event.type == pygame.KEYDOWN:
                    if not getattr(event, "repeat", False):
                        self._log_key(event.key)
                    if event.key == pygame.K_F1:
                        reopen_settings = True
                        self._running = False
                    elif event.key == pygame.K_F11:
                        toggle_display = True
                        self.session_log.add("display: toggle fullscreen")
                        self._running = False
                    elif not getattr(event, "repeat", False) and event.key in PANEL_BY_KEY:
                        self._panel_toggle(PANEL_BY_KEY[event.key].id)
                    elif event.key == pygame.K_ESCAPE:
                        self._running = False
                    elif self.spotify:
                        if event.key == pygame.K_SPACE:
                            self.spotify.play_pause()
                        elif event.key == pygame.K_RIGHT:
                            self.spotify.next_track()
                        elif event.key == pygame.K_LEFT:
                            self.spotify.previous_track()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    clicked_device = False
                    if self.panels.active == "devices" and self.spotify:
                        device_id = self._device_id_at(mx, my, w, h, margin, scale)
                        if device_id:
                            if self.spotify.transfer_device(device_id):
                                name = next(
                                    (d.name for d in self.spotify.devices if d.id == device_id),
                                    device_id,
                                )
                                self.session_log.add(f"device: {name}")
                                self.spotify.fetch_devices()
                            clicked_device = True
                    clicked_tab = False
                    if not clicked_device:
                        for panel_id, rect in self.panels.tab_rects.items():
                            if rect.collidepoint(mx, my):
                                self._panel_toggle(panel_id)
                                clicked_tab = True
                                break
                    if not clicked_tab and (
                        self.panels.active
                        and self.panels.min_btn_rect
                        and self.panels.min_btn_rect.collidepoint(mx, my)
                    ):
                        self._panel_minimize()
                elif event.type == pygame.MOUSEWHEEL and self.panels.active:
                    delta = -event.y * int(18 * scale)
                    self.panels.scroll_active(delta)
                    if self.panels.active == "lyrics":
                        self._lyrics_user_scroll = True

            screen.blit(fade, (0, 0))
            pulse += 0.08
            frame += 1
            self._scroll += 1

            if self.inject_queue and frame % 45 == 0:
                payload = self.inject_queue.pop(0)
                col = random.choice(columns)
                for i, ch in enumerate(payload[: min(len(col.chars), 24)]):
                    col.chars[i] = ch if ch in MATRIX_CHARS else random.choice(MATRIX_CHARS)

            if frame % 180 == 0:
                news = self.news.snapshot()
                if news.headlines:
                    headline = news.headlines[(frame // 180) % len(news.headlines)]
                    snippet = headline.title.upper()[:24]
                    if snippet not in self.inject_queue and len(self.inject_queue) < 8:
                        self.inject_queue.append(snippet)

            if frame % 210 == 105:
                wx = self.weather.snapshot()
                if wx.lines:
                    line = wx.lines[(frame // 210) % len(wx.lines)]
                    snippet = line.upper()[:24]
                    if snippet not in self.inject_queue and len(self.inject_queue) < 8:
                        self.inject_queue.append(snippet)

            for col in columns:
                col.step(h, char_size)
                for i, ch in enumerate(col.chars):
                    y = int(col.y - i * char_size)
                    if y < -char_size or y > h + char_size:
                        continue
                    if i == 0 and col.bright_head:
                        color = HEAD
                    elif i == 0:
                        color = BRIGHT
                    elif i < 3:
                        color = MID
                    else:
                        t = min(1.0, i / max(1, col.length - 1))
                        color = (
                            int(DIM[0] + (MID[0] - DIM[0]) * (1 - t)),
                            int(DIM[1] + (MID[1] - DIM[1]) * (1 - t)),
                            int(DIM[2] + (MID[2] - DIM[2]) * (1 - t)),
                        )
                    glyph = font.render(ch, True, color)
                    screen.blit(glyph, (col.x - glyph.get_width() // 2, y))

            self._draw_hud(
                screen,
                font_lg,
                font_md,
                font_sm,
                font_xl,
                font_track,
                w,
                h,
                scale,
                margin,
                pulse,
            )
            self._fps = clock.get_fps()
            self._draw_panels_ui(
                screen,
                font_sm,
                font_md,
                font_bin,
                w,
                h,
                scale,
                margin,
                self.spotify_playback,
                frame,
                pulse,
                glyph_zeros,
                glyph_ones,
                cell_w,
                cell_h,
            )
            mx, my = pygame.mouse.get_pos()
            _draw_matrix_cursor(screen, mx, my, scale, pulse, frame)
            pygame.display.flip()
            clock.tick(60)

        if self.spotify:
            self.spotify.stop()
        self.news.stop()
        self.ads_browser.close()
        self.weather.stop()
        pygame.quit()
        if toggle_display:
            return "toggle_display"
        if reopen_settings:
            return "settings"
        return ""

    def _draw_hud(
        self,
        screen: pygame.Surface,
        font_lg: pygame.font.Font,
        font_md: pygame.font.Font,
        font_sm: pygame.font.Font,
        font_xl: pygame.font.Font,
        font_track: pygame.font.Font,
        w: int,
        h: int,
        scale: float,
        margin: int,
        pulse: float,
    ) -> None:
        sp = self.spotify_playback

        if self.spotify:
            self._draw_spotify_panel(
                screen, font_lg, font_md, font_sm, font_xl, font_track, w, h, scale, sp
            )

        # Right activity stream
        stream_w = int(min(520, w * 0.24))
        stream = pygame.Surface((stream_w, h), pygame.SRCALPHA)
        stream.fill((*PANEL, 160))
        screen.blit(stream, (w - stream_w, 0))

        sy = margin
        glow = 0.85 + 0.15 * math.sin(pulse)
        title_c = (int(HEAD[0] * glow), int(HEAD[1] * glow), int(HEAD[2] * glow))
        screen.blit(font_lg.render("THE MATRIX", True, title_c), (w - stream_w + margin, sy))
        sy += font_lg.get_height() + int(6 * scale)
        screen.blit(font_sm.render("NOW PLAYING", True, UI_DIM), (w - stream_w + margin, sy))
        sy += int(36 * scale)

        events = list(self.activity)
        if sp.track and (not events or not events[0].endswith(sp.track)):
            events = [f"♫ {sp.track}"] + events
        for i, ev in enumerate(events[:16]):
            col = (0, min(255, 140 + i * 4), 60)
            screen.blit(font_sm.render(ev[:56], True, col), (w - stream_w + margin, sy))
            sy += int(22 * scale)

        draw_keybind_table(
            screen,
            margin,
            margin,
            font_sm,
            font_md,
            keybind_rows(include_spotify=bool(self.spotify)),
            scale,
            pulse,
        )

        footer = "dock tabs · mouse wheel scrolls panel"
        if self.spotify:
            footer = "dock tabs · wheel scroll  ·  SPACE · ← →"
        screen.blit(font_sm.render(footer, True, UI_DIM), (margin, h - int(36 * scale)))

    def _draw_spotify_panel(
        self,
        screen: pygame.Surface,
        font_lg: pygame.font.Font,
        font_md: pygame.font.Font,
        font_sm: pygame.font.Font,
        font_xl: pygame.font.Font,
        font_track: pygame.font.Font,
        w: int,
        h: int,
        scale: float,
        sp: SpotifyPlayback,
    ) -> None:
        panel_w = int(min(900, w * 0.46))
        panel_h = int(min(420, h * 0.42))
        px = (w - panel_w) // 2
        py = h - panel_h - int(48 * scale)

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((*PANEL, 230))
        pygame.draw.rect(panel, (*MID, 80), panel.get_rect(), width=max(1, int(2 * scale)))
        screen.blit(panel, (px, py))

        art_size = int(min(220, panel_h - 40) * scale / max(scale, 1))
        art_size = min(art_size, panel_h - int(60 * scale))
        x = px + int(24 * scale)
        y = py + int(20 * scale)

        header = "SPOTIFY"
        if sp.connected and not sp.error:
            header += "  ● LIVE" if sp.playing else "  ○ PAUSED"
        screen.blit(font_sm.render(header, True, SPOTIFY_GREEN), (x, y))
        y += int(28 * scale)

        art_x = x
        if self.spotify and self.spotify.art_surface:
            art = pygame.transform.smoothscale(self.spotify.art_surface, (art_size, art_size))
            art = _matrix_tint(art)
            screen.blit(art, (art_x, y))
        else:
            placeholder = pygame.Surface((art_size, art_size), pygame.SRCALPHA)
            placeholder.fill((*DIM, 120))
            pygame.draw.rect(placeholder, MID, placeholder.get_rect(), width=2)
            screen.blit(placeholder, (art_x, y))
            screen.blit(font_sm.render("NO ART", True, UI_DIM), (art_x + art_size // 4, y + art_size // 2))

        text_x = art_x + art_size + int(28 * scale)
        text_w = panel_w - (text_x - px) - int(24 * scale)

        if not sp.connected and sp.error:
            screen.blit(font_md.render("NOT LINKED", True, WARN), (text_x, y))
            screen.blit(font_sm.render(sp.error[:48], True, UI_DIM), (text_x, y + int(32 * scale)))
            screen.blit(
                font_sm.render("Press F1 → Connect Spotify", True, UI_DIM),
                (text_x, y + int(56 * scale)),
            )
            return

        if not sp.track:
            screen.blit(font_track.render("Nothing playing", True, DIM), (text_x, y + int(40 * scale)))
            open_hint = "Open Spotify on this Mac" if sys.platform == "darwin" else "Open Spotify on this PC"
            screen.blit(font_sm.render(open_hint, True, UI_DIM), (text_x, y + int(80 * scale)))
            return

        track = sp.track
        if len(track) > 42:
            offset = (self._scroll // 6) % max(1, len(track) - 38)
            track = track[offset : offset + 38] + "…"

        screen.blit(font_xl.render("♫", True, SPOTIFY_GREEN), (text_x, y))
        screen.blit(font_track.render(track, True, HEAD), (text_x + int(36 * scale), y))
        y += int(44 * scale)
        screen.blit(font_md.render(sp.artist, True, BRIGHT), (text_x, y))
        y += int(30 * scale)
        screen.blit(font_sm.render(sp.album, True, MID), (text_x, y))
        y += int(36 * scale)

        bar_w = text_w
        bar_h = max(4, int(8 * scale))
        progress = sp.progress_ms / sp.duration_ms if sp.duration_ms else 0
        pygame.draw.rect(screen, DIM, (text_x, y, bar_w, bar_h))
        pygame.draw.rect(screen, SPOTIFY_GREEN, (text_x, y, int(bar_w * progress), bar_h))
        y += int(18 * scale)
        times = f"{_fmt_time(sp.progress_ms)} / {_fmt_time(sp.duration_ms)}"
        screen.blit(font_sm.render(times, True, UI_DIM), (text_x, y))
        y += int(24 * scale)
        screen.blit(
            font_sm.render("SPACE play/pause   ← prev   → next", True, UI_DIM),
            (text_x, y),
        )

    def _refresh_conduit_bits(self, sp: SpotifyPlayback, lyrics: LyricsData) -> None:
        key = (
            sp.track,
            sp.artist,
            sp.album,
            sp.progress_ms // 800,
            sp.playing,
            tuple(list(self.activity)[:8]),
            lyrics.key(),
            current_lyric_window(lyrics, sp.progress_ms)[1] if lyrics.ready else "",
        )
        if key != self._conduit_key:
            self._conduit_key = key
            self._conduit_bits = _bytes_to_bits(_conduit_payload(sp, self.activity, lyrics))
        self._decode_answer = _decode_answer(sp, lyrics)

    def _refresh_conduit_reveal(
        self,
        sp: SpotifyPlayback,
        cols: int,
        rows: int,
        font_md: pygame.font.Font,
    ) -> None:
        art_url = ""
        if self.spotify:
            art_url = getattr(self.spotify, "_art_cache_url", "") or sp.art_url
        key = (sp.track, sp.artist, art_url)
        if key == self._reveal_key and self._reveal_bits:
            return
        self._reveal_key = key

        rw = max(16, int(cols * 0.5))
        rh = max(20, int(rows * 0.58))
        if self.spotify and self.spotify.art_surface:
            src = self.spotify.art_surface
        else:
            src = _text_fallback_surface(sp.track, sp.artist, font_md)
        self._reveal_w = rw
        self._reveal_h = rh
        self._reveal_bits = _surface_to_reveal_bits(src, rw, rh)

    def _draw_conduit_grid(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        glyph_zeros: list[pygame.Surface],
        glyph_ones: list[pygame.Surface],
        cell_w: int,
        cell_h: int,
        frame: int,
        pulse: float,
    ) -> None:
        """Dense 0/1 field — static at edges, portrait of the answer at center."""
        cols = max(1, rect.width // cell_w)
        rows = max(1, rect.height // cell_h)
        bits = self._conduit_bits or [0]
        n_bits = len(bits)
        drift = (frame // 12) % n_bits

        row_off = int(self.panels.scroll.get("conduit", 0) // cell_h)
        scan_y = (frame * 2 + int(self.panels.scroll.get("conduit", 0) * 0.4)) % max(1, rows)
        cx = cols / 2

        rw = self._reveal_w
        rh = self._reveal_h
        reveal = self._reveal_bits
        pcol0 = max(0, (cols - rw) // 2)
        prow0 = max(0, (rows - rh) // 2)

        for row in range(rows):
            gy = rect.y + row * cell_h
            if gy + cell_h > rect.bottom:
                break
            in_row = prow0 <= row < prow0 + rh
            for col in range(cols):
                idx = (row + row_off) * cols + col + drift
                dist = abs(col - cx) / max(1, cx)

                if (
                    in_row
                    and reveal
                    and pcol0 <= col < pcol0 + rw
                ):
                    lx = col - pcol0
                    ly = row - prow0
                    bit = reveal[ly * rw + lx]
                    vi = 4 if bit else min(4, int((0.5 + 0.12 * (1 - dist)) * 5))
                else:
                    bit = bits[idx % n_bits]
                    if dist > 0.78 and ((idx * 1103515245 + frame) & 0xFF) < 150:
                        bit = (idx + frame) & 1
                    flicker = 0.82 + 0.18 * math.sin(pulse + idx * 0.07 + frame * 0.05)
                    vi = min(4, int(flicker * 5))

                gx = rect.x + col * cell_w
                screen.blit(glyph_ones[vi] if bit else glyph_zeros[vi], (gx, gy))

            if row == scan_y:
                pygame.draw.line(
                    screen,
                    (*BRIGHT, 90),
                    (rect.x, gy),
                    (rect.right, gy),
                    1,
                )

        if rw > 0 and rh > 0:
            bx = rect.x + pcol0 * cell_w - 2
            by = rect.y + prow0 * cell_h - 2
            pygame.draw.rect(
                screen,
                BRIGHT,
                (bx, by, rw * cell_w + 4, rh * cell_h + 4),
                width=1,
            )

    def _draw_conduit_lyrics(
        self,
        screen: pygame.Surface,
        grid_rect: pygame.Rect,
        cell_w: int,
        cell_h: int,
        cols: int,
        rows: int,
        lyrics: LyricsData,
        progress_ms: int,
        font_lyric: pygame.font.Font,
        font_lyric_sm: pygame.font.Font,
        scale: float,
        pulse: float,
    ) -> None:
        """Synced lyrics overlay in the center decode window."""
        rw = self._reveal_w
        rh = self._reveal_h
        if rw <= 0 or rh <= 0:
            return

        pcol0 = max(0, (cols - rw) // 2)
        prow0 = max(0, (rows - rh) // 2)
        bx = grid_rect.x + pcol0 * cell_w
        by = grid_rect.y + prow0 * cell_h
        bw = rw * cell_w
        bh = rh * cell_h

        panel = pygame.Surface((bw, bh), pygame.SRCALPHA)
        panel.fill((0, 8, 4, 205))
        screen.blit(panel, (bx, by))
        pygame.draw.rect(screen, (*BRIGHT, 180), (bx, by, bw, bh), width=1)

        pad = int(12 * scale)
        inner_w = max(40, bw - pad * 2)
        cx = bx + bw // 2

        if lyrics.loading:
            msg = font_lyric_sm.render("decoding lyrics…", True, UI_DIM)
            screen.blit(msg, (cx - msg.get_width() // 2, by + (bh - msg.get_height()) // 2))
            return

        if not lyrics.ready:
            msg = font_lyric_sm.render(lyrics.error or "no lyrics in signal", True, UI_DIM)
            screen.blit(msg, (cx - msg.get_width() // 2, by + (bh - msg.get_height()) // 2))
            return

        prev_line, cur_line, next_line = current_lyric_window(lyrics, progress_ms)
        if not cur_line:
            return

        glow = 0.88 + 0.12 * math.sin(pulse * 1.5)
        cur_c = (
            int(HEAD[0] * glow),
            int(HEAD[1] * glow),
            int(HEAD[2] * glow),
        )

        blocks: list[tuple[pygame.Surface, int]] = []
        gap_sm = int(4 * scale)
        gap_lg = int(10 * scale)

        if prev_line:
            for line in wrap_lyric_line(prev_line, font_lyric_sm, inner_w)[:2]:
                blocks.append((font_lyric_sm.render(line, True, DIM), gap_sm))
        for line in wrap_lyric_line(cur_line, font_lyric, inner_w)[:3]:
            blocks.append((font_lyric.render(line, True, cur_c), gap_sm))
        next_blocks: list[tuple[pygame.Surface, int]] = []
        if next_line:
            for line in wrap_lyric_line(next_line, font_lyric_sm, inner_w)[:2]:
                next_blocks.append((font_lyric_sm.render(line, True, UI_DIM), gap_sm))

        total_h = sum(surf.get_height() + gap for surf, gap in blocks)
        if next_blocks:
            total_h += gap_lg + sum(surf.get_height() + gap for surf, gap in next_blocks) - next_blocks[-1][1]
        else:
            total_h -= blocks[-1][1] if blocks else 0
        y = by + max(pad, (bh - total_h) // 2)
        for surf, gap in blocks:
            screen.blit(surf, (cx - surf.get_width() // 2, y))
            y += surf.get_height() + gap
        if next_blocks:
            y += gap_lg - gap_sm
            for surf, gap in next_blocks:
                screen.blit(surf, (cx - surf.get_width() // 2, y))
                y += surf.get_height() + gap

    def _draw_panels_ui(
        self,
        screen: pygame.Surface,
        font_sm: pygame.font.Font,
        font_md: pygame.font.Font,
        font_bin: pygame.font.Font,
        w: int,
        h: int,
        scale: float,
        margin: int,
        sp: SpotifyPlayback,
        frame: int,
        pulse: float,
        glyph_zeros: list[pygame.Surface],
        glyph_ones: list[pygame.Surface],
        cell_w: int,
        cell_h: int,
    ) -> None:
        draw_dock_tabs(screen, font_sm, self.panels, w, h, scale, margin)
        if not self.panels.active:
            return

        definition = PANEL_BY_ID[self.panels.active]
        shell = draw_panel_shell(
            screen, self.panels, definition, font_sm, font_md, w, h, scale, margin
        )
        px, py, panel_w, panel_h, inner_x, inner_y, inner_w, inner_h, footer_h = shell

        lyrics = self.lyrics.snapshot()
        if sp.track:
            self.lyrics.request(sp.track, sp.artist, sp.album, sp.duration_ms)
            lyrics = self.lyrics.snapshot()

        if self.panels.active == "conduit":
            self._draw_conduit_panel_content(
                screen,
                font_sm,
                font_md,
                inner_x,
                inner_y,
                inner_w,
                inner_h,
                footer_h,
                scale,
                sp,
                lyrics,
                frame,
                pulse,
                glyph_zeros,
                glyph_ones,
                cell_w,
                cell_h,
            )
        elif self.panels.active == "lyrics":
            self._draw_lyrics_panel_content(
                screen, font_sm, font_md, inner_x, inner_y, inner_w, inner_h, footer_h, scale, sp, lyrics, pulse
            )
        elif self.panels.active == "hex":
            self._draw_hex_panel_content(
                screen, font_sm, font_bin, inner_x, inner_y, inner_w, inner_h, footer_h, scale, sp, lyrics
            )
        elif self.panels.active == "status":
            self._draw_status_panel_content(
                screen, font_sm, font_md, inner_x, inner_y, inner_w, inner_h, footer_h, scale, w, h, sp
            )
        elif self.panels.active == "meta":
            self._draw_meta_panel_content(
                screen, font_sm, font_md, inner_x, inner_y, inner_w, inner_h, footer_h, scale, sp
            )
        elif self.panels.active == "time":
            self._draw_time_panel_content(
                screen, font_sm, font_md, inner_x, inner_y, inner_w, inner_h, scale
            )
        elif self.panels.active == "news":
            self._draw_news_panel_content(
                screen, font_sm, font_md, inner_x, inner_y, inner_w, inner_h, footer_h, scale
            )
        elif self.panels.active == "ads":
            self._draw_ads_panel_content(
                screen, font_sm, font_md, inner_x, inner_y, inner_w, inner_h, footer_h, scale
            )
        elif self.panels.active == "queue":
            self._draw_queue_panel_content(
                screen, font_sm, font_md, inner_x, inner_y, inner_w, inner_h, footer_h, scale, sp
            )
        elif self.panels.active == "devices":
            self._draw_devices_panel_content(
                screen, font_sm, font_md, inner_x, inner_y, inner_w, inner_h, footer_h, scale, sp
            )
        elif self.panels.active == "weather":
            self._draw_weather_panel_content(
                screen, font_sm, font_md, inner_x, inner_y, inner_w, inner_h, footer_h, scale
            )
        elif self.panels.active == "log":
            self._draw_log_panel_content(
                screen, font_sm, font_md, inner_x, inner_y, inner_w, inner_h, footer_h, scale
            )

    def _draw_conduit_panel_content(
        self,
        screen: pygame.Surface,
        font_sm: pygame.font.Font,
        font_md: pygame.font.Font,
        inner_x: int,
        inner_y: int,
        inner_w: int,
        inner_h: int,
        footer_h: int,
        scale: float,
        sp: SpotifyPlayback,
        lyrics: LyricsData,
        frame: int,
        pulse: float,
        glyph_zeros: list[pygame.Surface],
        glyph_ones: list[pygame.Surface],
        cell_w: int,
        cell_h: int,
    ) -> None:
        self._refresh_conduit_bits(sp, lyrics)
        grid_rect = pygame.Rect(inner_x, inner_y, inner_w, inner_h)
        pygame.draw.rect(screen, (*DIM, 80), grid_rect, width=1)

        cols = max(1, inner_w // cell_w)
        rows = max(1, inner_h // cell_h)
        self._refresh_conduit_reveal(sp, cols, rows, font_md)
        max_scroll = max(0, (rows + len(self._conduit_bits) // max(1, cols)) * cell_h - inner_h)
        self.panels.set_scroll("conduit", min(self.panels.scroll["conduit"], max_scroll))

        prev_clip = screen.get_clip()
        screen.set_clip(grid_rect)
        self._draw_conduit_grid(
            screen,
            grid_rect,
            glyph_zeros,
            glyph_ones,
            cell_w,
            cell_h,
            frame,
            pulse,
        )
        font_lyric = get_font(max(14, int(18 * scale)), name=self.font_name or default_font_name())
        font_lyric_sm = get_font(max(11, int(14 * scale)), name=self.font_name or default_font_name())
        self._draw_conduit_lyrics(
            screen,
            grid_rect,
            cell_w,
            cell_h,
            cols,
            rows,
            lyrics,
            sp.progress_ms,
            font_lyric,
            font_lyric_sm,
            scale,
            pulse,
        )
        screen.set_clip(prev_clip)
        draw_scrollbar(
            screen,
            inner_x,
            inner_y,
            inner_w,
            inner_h,
            self.panels.scroll["conduit"],
            max_scroll,
            scale,
        )

        decode_y = inner_y + inner_h + int(8 * scale)
        pygame.draw.line(screen, (*MID, 120), (inner_x, decode_y), (inner_x + inner_w, decode_y), 1)
        screen.blit(font_sm.render("▼ THE ANSWER READS", True, BRIGHT), (inner_x, decode_y + int(6 * scale)))
        answer = self._decode_answer
        if len(answer) > 64:
            answer = answer[:61] + "…"
        screen.blit(font_md.render(answer, True, HEAD), (inner_x, decode_y + int(24 * scale)))

    def _draw_lyrics_panel_content(
        self,
        screen: pygame.Surface,
        font_sm: pygame.font.Font,
        font_md: pygame.font.Font,
        inner_x: int,
        inner_y: int,
        inner_w: int,
        inner_h: int,
        footer_h: int,
        scale: float,
        sp: SpotifyPlayback,
        lyrics: LyricsData,
        pulse: float,
    ) -> None:
        inner_rect = pygame.Rect(inner_x, inner_y, inner_w, inner_h)
        pygame.draw.rect(screen, (*DIM, 80), inner_rect, width=1)

        font_lyric = get_font(max(13, int(17 * scale)), name=self.font_name or default_font_name())
        line_h = int(24 * scale)

        if lyrics.loading:
            msg = font_md.render("decoding lyrics…", True, UI_DIM)
            screen.blit(msg, (inner_x + (inner_w - msg.get_width()) // 2, inner_y + inner_h // 2))
            return
        if not lyrics.ready:
            msg = font_md.render(lyrics.error or "no lyrics in signal", True, UI_DIM)
            screen.blit(msg, (inner_x + (inner_w - msg.get_width()) // 2, inner_y + inner_h // 2))
            return

        lines = lyric_lines(lyrics)
        if not lines:
            msg = font_md.render("no lyrics in signal", True, UI_DIM)
            screen.blit(msg, (inner_x + (inner_w - msg.get_width()) // 2, inner_y + inner_h // 2))
            return

        cur_idx = current_lyric_index(lyrics, sp.progress_ms)
        total_h = len(lines) * line_h
        max_scroll = max(0, total_h - inner_h)

        if not self._lyrics_user_scroll and max_scroll > 0:
            target = cur_idx * line_h - inner_h // 2
            self.panels.set_scroll("lyrics", max(0, min(max_scroll, target)))

        scroll = self.panels.scroll["lyrics"]
        glow = 0.88 + 0.12 * math.sin(pulse * 1.5)
        cur_c = (int(HEAD[0] * glow), int(HEAD[1] * glow), int(HEAD[2] * glow))

        prev_clip = screen.get_clip()
        screen.set_clip(inner_rect)
        y = inner_y - scroll
        for i, line in enumerate(lines):
            if y + line_h < inner_y or y > inner_y + inner_h:
                y += line_h
                continue
            if i == cur_idx:
                color = cur_c
            elif i < cur_idx:
                color = DIM
            else:
                color = UI_DIM
            text = line if len(line) <= 72 else line[:69] + "…"
            screen.blit(font_lyric.render(text, True, color), (inner_x + int(8 * scale), y))
            y += line_h
        screen.set_clip(prev_clip)
        draw_scrollbar(screen, inner_x, inner_y, inner_w, inner_h, scroll, max_scroll, scale)

        footer_y = inner_y + inner_h + int(8 * scale)
        footer = f"SYNC · {_fmt_time(sp.progress_ms)} / {_fmt_time(sp.duration_ms)}  ·  LINE {cur_idx + 1} / {len(lines)}"
        screen.blit(font_sm.render(footer, True, BRIGHT), (inner_x, footer_y + int(6 * scale)))

    def _draw_hex_panel_content(
        self,
        screen: pygame.Surface,
        font_sm: pygame.font.Font,
        font_bin: pygame.font.Font,
        inner_x: int,
        inner_y: int,
        inner_w: int,
        inner_h: int,
        footer_h: int,
        scale: float,
        sp: SpotifyPlayback,
        lyrics: LyricsData,
    ) -> None:
        payload = _conduit_payload(sp, self.activity, lyrics)
        rows = format_hex_lines(payload)
        line_h = font_bin.get_height() + int(2 * scale)
        total_h = len(rows) * line_h
        max_scroll = max(0, total_h - inner_h)
        self.panels.set_scroll("hex", min(self.panels.scroll["hex"], max_scroll))
        scroll = self.panels.scroll["hex"]

        inner_rect = pygame.Rect(inner_x, inner_y, inner_w, inner_h)
        pygame.draw.rect(screen, (*DIM, 80), inner_rect, width=1)
        prev_clip = screen.get_clip()
        screen.set_clip(inner_rect)

        prev = self._hex_prev_payload
        y = inner_y - scroll
        for offset, hex_part, ascii_part in rows:
            if y + line_h < inner_y or y > inner_y + inner_h:
                y += line_h
                continue
            row_text = f"{offset:05X}  {hex_part}  |{ascii_part}|"
            color = HEAD
            if prev and offset < len(prev):
                end = min(offset + 16, len(payload), len(prev))
                if payload[offset:end] != prev[offset:end]:
                    color = BRIGHT
            screen.blit(font_bin.render(row_text, True, color), (inner_x + int(4 * scale), y))
            y += line_h
        screen.set_clip(prev_clip)
        self._hex_prev_payload = payload

        draw_scrollbar(screen, inner_x, inner_y, inner_w, inner_h, scroll, max_scroll, scale)
        footer_y = inner_y + inner_h + int(8 * scale)
        screen.blit(
            font_sm.render(f"BYTES · {len(payload)}  ·  bright = changed", True, BRIGHT),
            (inner_x, footer_y + int(6 * scale)),
        )

    def _draw_status_panel_content(
        self,
        screen: pygame.Surface,
        font_sm: pygame.font.Font,
        font_md: pygame.font.Font,
        inner_x: int,
        inner_y: int,
        inner_w: int,
        inner_h: int,
        footer_h: int,
        scale: float,
        w: int,
        h: int,
        sp: SpotifyPlayback,
    ) -> None:
        lines: list[tuple[str, tuple[int, int, int]]] = []
        lines.append(("LINK", HEAD))
        lines.append((f"  connected: {sp.connected}", BRIGHT if sp.connected else WARN))
        lines.append((f"  playing: {sp.playing}", BRIGHT if sp.playing else UI_DIM))
        lines.append((f"  device: {sp.device or '—'}", MID))
        if sp.error:
            lines.append((f"  error: {sp.error[:56]}", WARN))

        lines.append(("SIGNAL", HEAD))
        poll = self.spotify.poll_interval if self.spotify else 0.0
        lines.append((f"  poll interval: {poll:.1f}s", MID))
        if self.spotify:
            age = self.spotify.last_poll_age
            lines.append((f"  last update: {age:.1f}s ago", MID))
            backoff = self.spotify.backoff_remaining
            if backoff > 0:
                lines.append((f"  rate limit backoff: {backoff:.0f}s", WARN))

        lines.append(("DISPLAY", HEAD))
        lines.append((f"  monitor: {self.display_index if self.display_index is not None else 0}", MID))
        lines.append((f"  resolution: {w} x {h}", MID))
        lines.append((f"  mode: {self.display_mode}", MID))
        lines.append((f"  fps: {self._fps:.0f}", MID))

        lines.append(("RAIN", HEAD))
        lines.append((f"  inject queue: {len(self.inject_queue)}", MID))
        lines.append((f"  activity log: {len(self.activity)}", MID))

        y = inner_y
        gap = int(4 * scale)
        section_gap = int(10 * scale)
        for text, color in lines:
            if text.isupper() and not text.startswith(" "):
                if y > inner_y:
                    y += section_gap
            surf = font_md.render(text, True, color) if text.isupper() and not text.startswith(" ") else font_sm.render(text, True, color)
            screen.blit(surf, (inner_x, y))
            y += surf.get_height() + gap

        footer_y = inner_y + inner_h + int(8 * scale)
        screen.blit(font_sm.render("▼ SYSTEM TELEMETRY", True, BRIGHT), (inner_x, footer_y + int(6 * scale)))

    def _draw_meta_panel_content(
        self,
        screen: pygame.Surface,
        font_sm: pygame.font.Font,
        font_md: pygame.font.Font,
        inner_x: int,
        inner_y: int,
        inner_w: int,
        inner_h: int,
        footer_h: int,
        scale: float,
        sp: SpotifyPlayback,
    ) -> None:
        fields = [
            ("TRACK", sp.track or "—"),
            ("ARTIST", sp.artist or "—"),
            ("ALBUM", sp.album or "—"),
            ("RELEASE", sp.release_year or "—"),
            ("DURATION", _fmt_time(sp.duration_ms) if sp.duration_ms else "—"),
            ("POPULARITY", str(sp.popularity) if sp.track else "—"),
            ("GENRES", sp.genres or "—"),
            ("TRACK ID", sp.track_id or "—"),
        ]
        y = inner_y
        gap = int(8 * scale)
        for label, value in fields:
            screen.blit(font_sm.render(label, True, BRIGHT), (inner_x, y))
            y += font_sm.get_height() + int(2 * scale)
            val = value if len(value) <= 58 else value[:55] + "…"
            screen.blit(font_md.render(val, True, HEAD), (inner_x + int(8 * scale), y))
            y += font_md.get_height() + gap

        footer_y = inner_y + inner_h + int(8 * scale)
        screen.blit(font_sm.render("▼ TRACK INTEL", True, BRIGHT), (inner_x, footer_y + int(6 * scale)))

    def _draw_time_panel_content(
        self,
        screen: pygame.Surface,
        font_sm: pygame.font.Font,
        font_md: pygame.font.Font,
        inner_x: int,
        inner_y: int,
        inner_w: int,
        inner_h: int,
        scale: float,
    ) -> None:
        now = datetime.now()
        family = self.font_name or default_font_name()
        clock_font = get_font(max(48, int(72 * scale)), name=family, bold=True)
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%A · %B %d, %Y")

        time_surf = clock_font.render(time_str, True, HEAD)
        date_surf = font_md.render(date_str, True, BRIGHT)
        tz_surf = font_sm.render(now.strftime("%Z"), True, UI_DIM)

        cx = inner_x + inner_w // 2
        cy = inner_y + inner_h // 2
        screen.blit(time_surf, (cx - time_surf.get_width() // 2, cy - time_surf.get_height() - int(10 * scale)))
        screen.blit(date_surf, (cx - date_surf.get_width() // 2, cy + int(8 * scale)))
        screen.blit(tz_surf, (cx - tz_surf.get_width() // 2, cy + int(8 * scale) + date_surf.get_height() + int(6 * scale)))

        footer_y = inner_y + inner_h + int(8 * scale)
        screen.blit(font_sm.render("▼ LOCAL TIME", True, BRIGHT), (inner_x, footer_y + int(6 * scale)))

    def _draw_news_panel_content(
        self,
        screen: pygame.Surface,
        font_sm: pygame.font.Font,
        font_md: pygame.font.Font,
        inner_x: int,
        inner_y: int,
        inner_w: int,
        inner_h: int,
        footer_h: int,
        scale: float,
    ) -> None:
        news = self.news.snapshot()
        line_h = int(26 * scale)
        pad = int(6 * scale)

        if news.loading and not news.headlines:
            msg = font_md.render("tuning signal feed…", True, UI_DIM)
            screen.blit(msg, (inner_x + (inner_w - msg.get_width()) // 2, inner_y + inner_h // 2))
            return
        if news.error and not news.headlines:
            msg = font_md.render(news.error, True, WARN)
            screen.blit(msg, (inner_x + (inner_w - msg.get_width()) // 2, inner_y + inner_h // 2))
            return

        headlines = news.headlines or []
        rows: list[tuple[str, str, tuple[int, int, int]]] = []
        for i, item in enumerate(headlines):
            rank = f"{i + 1:02d}"
            when = item.when or "—"
            title = item.title if len(item.title) <= 64 else item.title[:61] + "…"
            rows.append((rank, when, title))

        total_h = len(rows) * line_h
        max_scroll = max(0, total_h - inner_h)
        self.panels.set_scroll("news", min(self.panels.scroll["news"], max_scroll))
        scroll = self.panels.scroll["news"]

        rank_w = int(28 * scale)
        when_w = int(36 * scale)
        title_x = inner_x + rank_w + when_w + int(10 * scale)

        inner_rect = pygame.Rect(inner_x, inner_y, inner_w, inner_h)
        pygame.draw.rect(screen, (*DIM, 80), inner_rect, width=1)
        header_y = inner_y - scroll
        screen.blit(font_sm.render("#", True, UI_DIM), (inner_x + pad, header_y))
        screen.blit(font_sm.render("AGE", True, UI_DIM), (inner_x + rank_w, header_y))
        screen.blit(font_sm.render("HEADLINE", True, UI_DIM), (title_x, header_y))

        prev_clip = screen.get_clip()
        screen.set_clip(inner_rect)
        y = inner_y + line_h - scroll
        for i, (rank, when, title) in enumerate(rows):
            if y + line_h < inner_y or y > inner_y + inner_h:
                y += line_h
                continue
            rank_c = HEAD if i == 0 else BRIGHT
            when_c = WARN if when.endswith("m") else UI_DIM
            title_c = HEAD if i == 0 else MID
            screen.blit(font_sm.render(rank, True, rank_c), (inner_x + pad, y))
            screen.blit(font_sm.render(when, True, when_c), (inner_x + rank_w, y))
            screen.blit(font_sm.render(title, True, title_c), (title_x, y))
            y += line_h
        screen.set_clip(prev_clip)
        draw_scrollbar(screen, inner_x, inner_y, inner_w, inner_h, scroll, max_scroll, scale)

        footer_y = inner_y + inner_h + int(8 * scale)
        screen.blit(
            font_sm.render(f"▼ BBC NEWS · {len(headlines)} HEADLINES", True, BRIGHT),
            (inner_x, footer_y + int(6 * scale)),
        )

    def _draw_ads_panel_content(
        self,
        screen: pygame.Surface,
        font_sm: pygame.font.Font,
        font_md: pygame.font.Font,
        inner_x: int,
        inner_y: int,
        inner_w: int,
        inner_h: int,
        footer_h: int,
        scale: float,
    ) -> None:
        self.ads_browser.sync()
        mode = self.ads_browser.mode
        lines: list[tuple[str, tuple[int, int, int]]] = [
            ("SATELLITE BROWSER", HEAD),
            ("", DIM),
            ("macrumors.com loads in a native", MID),
            ("webview beside the Matrix display.", MID),
            ("", DIM),
        ]
        if mode == "webview" or self.ads_browser.is_open:
            lines.extend(
                [
                    ("status: live · JS ads enabled", BRIGHT),
                    ("close this panel (A) to dismiss", UI_DIM),
                ]
            )
        elif mode == "fallback":
            lines.extend(
                [
                    ("status: opened system browser", WARN),
                    ("install pywebview for embedded view", UI_DIM),
                ]
            )
        else:
            lines.extend(
                [
                    ("status: waiting for launch…", UI_DIM),
                    ("press A if the window did not open", UI_DIM),
                ]
            )

        total_h = len(lines) * int(26 * scale)
        y = inner_y + max(0, (inner_h - total_h) // 2)
        for text, color in lines:
            if not text:
                y += int(10 * scale)
                continue
            surf = font_md.render(text, True, color) if color == HEAD else font_sm.render(text, True, color)
            screen.blit(surf, (inner_x + (inner_w - surf.get_width()) // 2, y))
            y += int(26 * scale)

        footer_y = inner_y + inner_h + int(8 * scale)
        screen.blit(
            font_sm.render("▼ MACRUMORS.COM · LIVE WEBVIEW", True, BRIGHT),
            (inner_x, footer_y + int(6 * scale)),
        )

    def _draw_queue_panel_content(
        self,
        screen: pygame.Surface,
        font_sm: pygame.font.Font,
        font_md: pygame.font.Font,
        inner_x: int,
        inner_y: int,
        inner_w: int,
        inner_h: int,
        footer_h: int,
        scale: float,
        sp: SpotifyPlayback,
    ) -> None:
        entries: list[tuple[str, str, tuple[int, int, int]]] = []
        if not self.spotify:
            msg = font_md.render("requires Spotify link", True, WARN)
            screen.blit(msg, (inner_x + (inner_w - msg.get_width()) // 2, inner_y + inner_h // 2))
            return

        queue_tracks: list[QueueTrack] = list(getattr(self.spotify, "queue_tracks", None) or [])
        queue_error = str(getattr(self.spotify, "queue_error", "") or "")

        if sp.track:
            entries.append(("NOW", sp.track, HEAD))
            entries.append(("", sp.artist, BRIGHT))
        for i, item in enumerate(queue_tracks[:10], start=1):
            name = getattr(item, "name", "") or ""
            artist = getattr(item, "artist", "") or ""
            if not name:
                continue
            entries.append((f"{i}.", name, MID))
            entries.append(("", artist, UI_DIM))

        line_h = int(26 * scale)
        inner_rect = pygame.Rect(inner_x, inner_y, inner_w, inner_h)
        pygame.draw.rect(screen, (*DIM, 80), inner_rect, width=1)

        if not entries:
            msg = queue_error or "queue empty — play music in Spotify"
            color = WARN if queue_error else UI_DIM
            surf = font_md.render(msg, True, color)
            screen.blit(surf, (inner_x + (inner_w - surf.get_width()) // 2, inner_y + inner_h // 2))
        else:
            total_h = len(entries) * line_h
            max_scroll = max(0, total_h - inner_h)
            scroll = self.panels.scroll_for("queue")
            self.panels.set_scroll("queue", min(scroll, max_scroll))
            scroll = self.panels.scroll_for("queue")
            prev_clip = screen.get_clip()
            screen.set_clip(inner_rect)
            y = inner_y - scroll
            for prefix, text, color in entries:
                if y + line_h < inner_y or y > inner_y + inner_h:
                    y += line_h
                    continue
                if prefix:
                    screen.blit(font_sm.render(prefix, True, BRIGHT), (inner_x + int(6 * scale), y))
                if text:
                    val = text if len(text) <= 58 else text[:55] + "…"
                    screen.blit(font_md.render(val, True, color), (inner_x + int(34 * scale), y))
                y += line_h
            screen.set_clip(prev_clip)
            draw_scrollbar(screen, inner_x, inner_y, inner_w, inner_h, scroll, max_scroll, scale)

        footer_y = inner_y + inner_h + int(8 * scale)
        count = len(queue_tracks)
        screen.blit(font_sm.render(f"▼ UP NEXT · {count} track(s)", True, BRIGHT), (inner_x, footer_y + int(6 * scale)))

    def _draw_devices_panel_content(
        self,
        screen: pygame.Surface,
        font_sm: pygame.font.Font,
        font_md: pygame.font.Font,
        inner_x: int,
        inner_y: int,
        inner_w: int,
        inner_h: int,
        footer_h: int,
        scale: float,
        sp: SpotifyPlayback,
    ) -> None:
        inner_rect = pygame.Rect(inner_x, inner_y, inner_w, inner_h)
        pygame.draw.rect(screen, (*DIM, 80), inner_rect, width=1)

        if not self.spotify:
            msg = font_md.render("requires Spotify link", True, WARN)
            screen.blit(msg, (inner_x + (inner_w - msg.get_width()) // 2, inner_y + inner_h // 2))
            return

        devices: list[SpotifyDevice] = list(getattr(self.spotify, "devices", None) or [])
        devices_error = str(getattr(self.spotify, "devices_error", "") or "")
        line_h = int(30 * scale)

        if not devices:
            msg = devices_error or "no Connect devices found"
            color = WARN if devices_error else UI_DIM
            surf = font_md.render(msg, True, color)
            screen.blit(surf, (inner_x + (inner_w - surf.get_width()) // 2, inner_y + inner_h // 2))
        else:
            total_h = len(devices) * line_h
            max_scroll = max(0, total_h - inner_h)
            scroll = self.panels.scroll_for("devices")
            self.panels.set_scroll("devices", min(scroll, max_scroll))
            scroll = self.panels.scroll_for("devices")
            prev_clip = screen.get_clip()
            screen.set_clip(inner_rect)
            y = inner_y - scroll
            for device in devices:
                if inner_y <= y <= inner_y + inner_h - line_h:
                    if device.is_active:
                        pygame.draw.rect(screen, (*BRIGHT, 35), pygame.Rect(inner_x, y, inner_w, line_h))
                    name = device.name if len(device.name) <= 42 else device.name[:39] + "…"
                    color = HEAD if device.is_active else MID
                    screen.blit(font_md.render(name, True, color), (inner_x + int(8 * scale), y + int(2 * scale)))
                    meta = f"{device.type or 'device'} · vol {device.volume}%"
                    if device.is_active:
                        meta += " · ACTIVE"
                    screen.blit(font_sm.render(meta, True, UI_DIM), (inner_x + int(8 * scale), y + int(16 * scale)))
                y += line_h
            screen.set_clip(prev_clip)
            draw_scrollbar(screen, inner_x, inner_y, inner_w, inner_h, scroll, max_scroll, scale)

        footer_y = inner_y + inner_h + int(8 * scale)
        active = sp.device or "—"
        screen.blit(
            font_sm.render(f"▼ ENDPOINTS · active: {active} · click row to switch", True, BRIGHT),
            (inner_x, footer_y + int(6 * scale)),
        )

    def _draw_weather_panel_content(
        self,
        screen: pygame.Surface,
        font_sm: pygame.font.Font,
        font_md: pygame.font.Font,
        inner_x: int,
        inner_y: int,
        inner_w: int,
        inner_h: int,
        footer_h: int,
        scale: float,
    ) -> None:
        wx = self.weather.snapshot()
        line_h = int(24 * scale)

        if wx.loading and not wx.lines:
            msg = font_md.render("tuning atmosphere feed…", True, UI_DIM)
            screen.blit(msg, (inner_x + (inner_w - msg.get_width()) // 2, inner_y + inner_h // 2))
            return
        if wx.error and not wx.lines:
            msg = font_md.render(wx.error, True, WARN)
            screen.blit(msg, (inner_x + (inner_w - msg.get_width()) // 2, inner_y + inner_h // 2))
            return

        lines = wx.lines or ["no weather in signal"]
        total_h = len(lines) * line_h
        max_scroll = max(0, total_h - inner_h)
        scroll = self.panels.scroll_for("weather")
        self.panels.set_scroll("weather", min(scroll, max_scroll))
        scroll = self.panels.scroll_for("weather")

        inner_rect = pygame.Rect(inner_x, inner_y, inner_w, inner_h)
        pygame.draw.rect(screen, (*DIM, 80), inner_rect, width=1)
        prev_clip = screen.get_clip()
        screen.set_clip(inner_rect)
        y = inner_y - scroll
        for i, line in enumerate(lines):
            if y + line_h < inner_y or y > inner_y + inner_h:
                y += line_h
                continue
            text = line if len(line) <= 64 else line[:61] + "…"
            color = HEAD if i == 0 else MID
            screen.blit(font_sm.render(f"▸ {text}", True, color), (inner_x + int(6 * scale), y))
            y += line_h
        screen.set_clip(prev_clip)
        draw_scrollbar(screen, inner_x, inner_y, inner_w, inner_h, scroll, max_scroll, scale)

        footer_y = inner_y + inner_h + int(8 * scale)
        loc = wx.location or "local"
        screen.blit(font_sm.render(f"▼ ATMOSPHERE · {loc} · {len(lines)}", True, BRIGHT), (inner_x, footer_y + int(6 * scale)))

    def _draw_log_panel_content(
        self,
        screen: pygame.Surface,
        font_sm: pygame.font.Font,
        font_md: pygame.font.Font,
        inner_x: int,
        inner_y: int,
        inner_w: int,
        inner_h: int,
        footer_h: int,
        scale: float,
    ) -> None:
        entries = self.session_log.snapshot()
        line_h = int(22 * scale)
        inner_rect = pygame.Rect(inner_x, inner_y, inner_w, inner_h)
        pygame.draw.rect(screen, (*DIM, 80), inner_rect, width=1)

        if not entries:
            msg = font_md.render("no session events yet", True, UI_DIM)
            screen.blit(msg, (inner_x + (inner_w - msg.get_width()) // 2, inner_y + inner_h // 2))
            return

        total_h = len(entries) * line_h
        max_scroll = max(0, total_h - inner_h)
        scroll = self.panels.scroll_for("log")
        self.panels.set_scroll("log", min(scroll, max_scroll))
        scroll = self.panels.scroll_for("log")

        prev_clip = screen.get_clip()
        screen.set_clip(inner_rect)
        y = inner_y - scroll
        for i, entry in enumerate(entries):
            if y + line_h < inner_y or y > inner_y + inner_h:
                y += line_h
                continue
            msg = entry.message if len(entry.message) <= 56 else entry.message[:53] + "…"
            if entry.message.startswith("spotify:"):
                color = WARN
            elif entry.message.startswith("track:"):
                color = HEAD
            elif entry.message.startswith("panel:"):
                color = BRIGHT
            elif entry.message.startswith("key:"):
                color = UI_DIM
            else:
                color = MID if i % 2 == 0 else UI_DIM
            row = f"{entry.time}  {msg}"
            screen.blit(font_sm.render(row, True, color), (inner_x + int(6 * scale), y))
            y += line_h
        screen.set_clip(prev_clip)
        draw_scrollbar(screen, inner_x, inner_y, inner_w, inner_h, scroll, max_scroll, scale)

        footer_y = inner_y + inner_h + int(8 * scale)
        screen.blit(font_sm.render(f"▼ SESSION TRACE · {len(entries)}", True, BRIGHT), (inner_x, footer_y + int(6 * scale)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Matrix fullscreen display with Spotify")
    parser.add_argument("--demo", action="store_true", help="Simulated Spotify tracks (no API)")
    parser.add_argument(
        "--font",
        default=None,
        help=f"Font family (default: {default_font_name()})",
    )
    parser.add_argument("--size", type=int, default=None, help="Rain glyph size (auto on 4K)")
    parser.add_argument(
        "--display",
        type=int,
        default=None,
        help="Monitor index for fullscreen (0=primary, 1=second/TV, ...)",
    )
    parser.add_argument(
        "--list-displays",
        action="store_true",
        help="Print monitor indices and exit",
    )
    parser.add_argument("--no-spotify", action="store_true", help="Rain only, no Spotify panel")
    parser.add_argument(
        "--mode",
        choices=("borderless", "exclusive", "windowed"),
        default="windowed",
        help="Display mode: windowed, borderless fullscreen, or exclusive fullscreen",
    )
    parser.add_argument(
        "--window-size",
        default="1920x1080",
        help="Windowed size as WIDTHxHEIGHT (used only with --mode windowed)",
    )
    parser.add_argument(
        "--settings",
        action="store_true",
        help="Open settings menu (monitor dropdown, display mode, resolution)",
    )
    parser.add_argument(
        "--exclusive",
        action="store_true",
        help="Use exclusive fullscreen (default is windowed 1920×1080)",
    )
    args = parser.parse_args(argv)

    if args.list_displays:
        for idx, size in list_displays():
            print(f"  [{idx}]  {size[0]} x {size[1]}")
        return 0

    mode = "exclusive" if args.exclusive else args.mode
    win_w, win_h = 1920, 1080
    try:
        ws = str(args.window_size).lower().replace(" ", "")
        left, right = ws.split("x", 1)
        win_w, win_h = max(640, int(left)), max(360, int(right))
    except (ValueError, TypeError):
        pass

    selected_display = args.display
    enable_spotify = not args.no_spotify and not args.demo
    needs_launcher = args.settings or (enable_spotify and not is_logged_in())
    if needs_launcher:
        selected = open_settings_menu(
            selected_display,
            mode,
            (win_w, win_h),
            default_spotify=enable_spotify,
        )
        if selected is None:
            return 0
        selected_display = selected.display_index
        mode = selected.mode
        win_w, win_h = selected.window_size
        enable_spotify = selected.enable_spotify

    while True:
        if not enable_spotify:
            spotify = None
        elif args.demo:
            spotify = DemoSpotifySource()
        else:
            spotify = SpotifySource()

        display = MatrixDisplay(
            spotify=spotify,
            font_name=args.font,
            char_size=args.size,
            display_index=selected_display,
            exclusive=(mode == "exclusive"),
            display_mode=mode,
            window_size=(win_w, win_h),
        )
        try:
            action = display.run()
        except KeyboardInterrupt:
            if spotify:
                spotify.stop()
            break
        if action == "settings":
            selected = open_settings_menu(
                selected_display,
                mode,
                (win_w, win_h),
                default_spotify=enable_spotify,
            )
            if selected is None:
                break
            selected_display = selected.display_index
            mode = selected.mode
            win_w, win_h = selected.window_size
            enable_spotify = selected.enable_spotify
            continue
        if action == "toggle_display":
            mode = "borderless" if mode == "windowed" else "windowed"
            continue
        break
    return 0


if __name__ == "__main__":
    sys.exit(main())
