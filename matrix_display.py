"""Fullscreen Matrix digital rain with Spotify overlay."""

from __future__ import annotations

import argparse
import math
import random
import sys
from collections import deque

import pygame

from display_setup import create_fullscreen_surface, list_displays
from spotify_source import DemoSpotifySource, SpotifyPlayback, SpotifySource

# Matrix palette
HEAD = (185, 255, 185)
BRIGHT = (80, 255, 120)
MID = (0, 170, 70)
DIM = (0, 55, 28)
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


def _conduit_payload(sp: SpotifyPlayback, activity: deque[str]) -> bytes:
    """UTF-8 byte stream of everything on screen — the 'captured signal'."""
    lines: list[str] = []
    if sp.track:
        lines.extend([sp.track, sp.artist, sp.album])
    lines.append(f"{_fmt_time(sp.progress_ms)}/{_fmt_time(sp.duration_ms)}")
    lines.append(f"live={sp.connected} play={sp.playing}")
    if sp.error:
        lines.append(sp.error[:200])
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


def _decode_answer(sp: SpotifyPlayback) -> str:
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
    tip_font = pygame.font.SysFont("consolas", max(9, int(10 * scale)))
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
    ) -> None:
        self.spotify = spotify
        self.font_name = font_name
        self.char_size = char_size
        self.display_index = display_index
        self.exclusive = exclusive
        self.spotify_playback = SpotifyPlayback()
        self.inject_queue: list[str] = []
        self.activity: deque[str] = deque(maxlen=24)
        self._last_track = ""
        self._running = True
        self._scroll = 0
        self.binary_panel_open = False
        self.binary_scroll = 0
        self._binary_tab_rect: pygame.Rect | None = None
        self._binary_min_btn_rect: pygame.Rect | None = None
        self._conduit_key: tuple = ()
        self._conduit_bits: list[int] = []
        self._reveal_key: tuple = ()
        self._reveal_bits: list[int] = []
        self._reveal_w = 0
        self._reveal_h = 0
        self._decode_answer = "awaiting transmission"

    def run(self) -> None:
        screen, w, h, scale, _used_display = create_fullscreen_surface(
            self.display_index,
            exclusive=self.exclusive,
        )
        char_size = self.char_size or max(14, int(18 * scale))
        margin = int(28 * scale)
        pygame.mouse.set_visible(False)

        font = pygame.font.SysFont(self.font_name or "consolas", char_size)
        font_lg = pygame.font.SysFont(self.font_name or "consolas", int(32 * scale), bold=True)
        font_md = pygame.font.SysFont(self.font_name or "consolas", int(22 * scale))
        font_sm = pygame.font.SysFont(self.font_name or "consolas", int(16 * scale))
        font_xl = pygame.font.SysFont(self.font_name or "consolas", int(40 * scale), bold=True)
        font_track = pygame.font.SysFont(self.font_name or "consolas", int(28 * scale), bold=True)
        font_bin = pygame.font.SysFont(self.font_name or "consolas", max(11, int(13 * scale)))
        font_conduit = pygame.font.SysFont(self.font_name or "consolas", max(9, int(10 * scale)))
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
                if line not in self.inject_queue and len(self.inject_queue) < 8:
                    self.inject_queue.append(line.upper())
            self.spotify_playback = p

        if self.spotify:
            self.spotify.on_update = on_spotify
            self.spotify.start()

        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        self._running = False
                    elif event.key == pygame.K_b and not getattr(event, "repeat", False):
                        self.binary_panel_open = not self.binary_panel_open
                        if self.binary_panel_open:
                            self.binary_scroll = 0
                    elif self.spotify:
                        if event.key == pygame.K_SPACE:
                            self.spotify.play_pause()
                        elif event.key == pygame.K_RIGHT:
                            self.spotify.next_track()
                        elif event.key == pygame.K_LEFT:
                            self.spotify.previous_track()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    if self._binary_tab_rect and self._binary_tab_rect.collidepoint(mx, my):
                        self.binary_panel_open = not self.binary_panel_open
                        if self.binary_panel_open:
                            self.binary_scroll = 0
                    elif (
                        self.binary_panel_open
                        and self._binary_min_btn_rect
                        and self._binary_min_btn_rect.collidepoint(mx, my)
                    ):
                        self.binary_panel_open = False
                elif event.type == pygame.MOUSEWHEEL and self.binary_panel_open:
                    self.binary_scroll = max(0, self.binary_scroll - event.y * int(18 * scale))

            screen.blit(fade, (0, 0))
            pulse += 0.08
            frame += 1
            self._scroll += 1

            if self.inject_queue and frame % 45 == 0:
                payload = self.inject_queue.pop(0)
                col = random.choice(columns)
                for i, ch in enumerate(payload[: min(len(col.chars), 24)]):
                    col.chars[i] = ch if ch in MATRIX_CHARS else random.choice(MATRIX_CHARS)

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
                    screen.blit(font.render(ch, True, color), (col.x, y))

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
            self._binary_tab_rect = None
            self._binary_min_btn_rect = None
            self._draw_binary_ui(
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
        pygame.quit()

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
        screen.blit(font_sm.render("NOW PLAYING", True, DIM), (w - stream_w + margin, sy))
        sy += int(36 * scale)

        events = list(self.activity)
        if sp.track and (not events or not events[0].endswith(sp.track)):
            events = [f"♫ {sp.track}"] + events
        for i, ev in enumerate(events[:16]):
            col = (0, min(255, 140 + i * 4), 60)
            screen.blit(font_sm.render(ev[:56], True, col), (w - stream_w + margin, sy))
            sy += int(22 * scale)

        hint = "ESC quit  ·  B conduit 0/1"
        if self.spotify:
            hint += "  ·  SPACE play/pause  ·  ← → skip"
        screen.blit(font_sm.render(hint, True, DIM), (margin, h - int(36 * scale)))

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
        panel.fill((*PANEL, 210))
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
            screen.blit(font_sm.render("NO ART", True, DIM), (art_x + art_size // 4, y + art_size // 2))

        text_x = art_x + art_size + int(28 * scale)
        text_w = panel_w - (text_x - px) - int(24 * scale)

        if not sp.connected and sp.error:
            screen.blit(font_md.render("NOT LINKED", True, WARN), (text_x, y))
            screen.blit(font_sm.render(sp.error[:48], True, DIM), (text_x, y + int(32 * scale)))
            screen.blit(
                font_sm.render("Run: python spotify_setup.py", True, DIM),
                (text_x, y + int(56 * scale)),
            )
            return

        if not sp.track:
            screen.blit(font_track.render("Nothing playing", True, DIM), (text_x, y + int(40 * scale)))
            screen.blit(font_sm.render("Open Spotify on this PC", True, DIM), (text_x, y + int(80 * scale)))
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
        screen.blit(font_sm.render(times, True, DIM), (text_x, y))
        y += int(24 * scale)
        screen.blit(
            font_sm.render("SPACE play/pause   ← prev   → next", True, DIM),
            (text_x, y),
        )

    def _refresh_conduit_bits(self, sp: SpotifyPlayback) -> None:
        key = (
            sp.track,
            sp.artist,
            sp.album,
            sp.progress_ms // 800,
            sp.playing,
            tuple(list(self.activity)[:8]),
        )
        if key != self._conduit_key:
            self._conduit_key = key
            self._conduit_bits = _bytes_to_bits(_conduit_payload(sp, self.activity))
        self._decode_answer = _decode_answer(sp)

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

        row_off = int(self.binary_scroll // cell_h)
        scan_y = (frame * 2 + int(self.binary_scroll * 0.4)) % max(1, rows)
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

    def _binary_tab_layout(
        self,
        font_sm: pygame.font.Font,
        w: int,
        h: int,
        scale: float,
        margin: int,
        *,
        open_panel: bool,
    ) -> tuple[int, int, int, int, pygame.Surface]:
        """Dock tab sized to label, placed in the rain area left of the HUD stream."""
        stream_w = int(min(520, w * 0.24))
        rain_right = w - stream_w - margin
        tab_pad = int(12 * scale)
        tab_h = int(34 * scale)
        max_tab_w = max(int(72 * scale), rain_right - margin)
        candidates = ("CONDUIT · B",) if open_panel else ("CONDUIT · B", "0/1 · B", "B")
        msg = font_sm.render("B", True, HEAD)
        tab_w = int(72 * scale)
        for label in candidates:
            msg = font_sm.render(label, True, HEAD)
            need = msg.get_width() + tab_pad * 2
            if need <= max_tab_w:
                tab_w = need
                break
        else:
            tab_w = max_tab_w
        tab_x = max(margin, rain_right - tab_w)
        tab_y = h - tab_h - int(44 * scale)
        return tab_x, tab_y, tab_w, tab_h, msg

    def _draw_binary_ui(
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
        tab_x, tab_y, tab_w, tab_h, msg = self._binary_tab_layout(
            font_sm, w, h, scale, margin, open_panel=self.binary_panel_open
        )
        tab_pad = int(12 * scale)

        if not self.binary_panel_open:
            tab = pygame.Surface((tab_w, tab_h), pygame.SRCALPHA)
            tab.fill((*PANEL, 200))
            pygame.draw.rect(tab, (*MID, 90), tab.get_rect(), width=max(1, int(2 * scale)))
            screen.blit(tab, (tab_x, tab_y))
            text_x = tab_x + (tab_w - msg.get_width()) // 2
            screen.blit(msg, (text_x, tab_y + (tab_h - msg.get_height()) // 2))
            self._binary_tab_rect = pygame.Rect(tab_x, tab_y, tab_w, tab_h)
            return

        self._binary_tab_rect = pygame.Rect(tab_x, tab_y, tab_w, tab_h)

        self._refresh_conduit_bits(sp)

        stream_w = int(min(520, w * 0.24))
        rain_w = w - stream_w - margin * 2
        panel_w = int(min(rain_w, w * 0.68))
        panel_h = int(min(h - margin * 2, h * 0.78))
        px = margin
        py = margin

        veil = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 175))
        screen.blit(veil, (px, py))

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((*PANEL, 235))
        pygame.draw.rect(panel, (*MID, 120), panel.get_rect(), width=max(1, int(2 * scale)))
        screen.blit(panel, (px, py))

        hx = px + int(16 * scale)
        hy = py + int(12 * scale)
        title = font_md.render("CONDUIT · SIGNAL DECODE", True, HEAD)
        screen.blit(title, (hx, hy))
        min_sz = int(28 * scale)
        self._binary_min_btn_rect = pygame.Rect(
            px + panel_w - min_sz - int(10 * scale),
            py + int(8 * scale),
            min_sz,
            min_sz,
        )
        pygame.draw.rect(screen, (*DIM, 200), self._binary_min_btn_rect, border_radius=4)
        minus = font_md.render("−", True, HEAD)
        screen.blit(
            minus,
            (
                self._binary_min_btn_rect.centerx - minus.get_width() // 2,
                self._binary_min_btn_rect.centery - minus.get_height() // 2,
            ),
        )

        sub = font_sm.render(
            "1 = bright · center = hidden image · scroll noise · B dock",
            True,
            DIM,
        )
        screen.blit(sub, (hx, hy + int(26 * scale)))

        inner_x = hx
        inner_y = hy + int(50 * scale)
        inner_w = panel_w - int(32 * scale)
        decode_h = int(52 * scale)
        inner_h = panel_h - int(62 * scale) - decode_h
        grid_rect = pygame.Rect(inner_x, inner_y, inner_w, inner_h)

        pygame.draw.rect(screen, (*DIM, 80), grid_rect, width=1)

        cols = max(1, inner_w // cell_w)
        rows = max(1, inner_h // cell_h)
        self._refresh_conduit_reveal(sp, cols, rows, font_md)
        max_scroll = max(0, (rows + len(self._conduit_bits) // max(1, cols)) * cell_h - inner_h)
        self.binary_scroll = min(self.binary_scroll, max_scroll)

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
        screen.set_clip(prev_clip)

        decode_y = inner_y + inner_h + int(8 * scale)
        pygame.draw.line(
            screen,
            (*MID, 120),
            (inner_x, decode_y),
            (inner_x + inner_w, decode_y),
            1,
        )
        read_lbl = font_sm.render("▼ THE ANSWER READS", True, BRIGHT)
        screen.blit(read_lbl, (inner_x, decode_y + int(6 * scale)))
        answer = self._decode_answer
        if len(answer) > 64:
            answer = answer[:61] + "…"
        readout = font_md.render(answer, True, HEAD)
        screen.blit(readout, (inner_x, decode_y + int(24 * scale)))

        if max_scroll > 0:
            bar_x = inner_x + inner_w - int(8 * scale)
            track_h = inner_h - int(4 * scale)
            pygame.draw.rect(screen, (*DIM, 160), (bar_x, inner_y + 2, 6, track_h))
            thumb_h = max(int(24 * scale), int(track_h * (inner_h / max(1, max_scroll + inner_h))))
            ty = inner_y + 2 + int((track_h - thumb_h) * (self.binary_scroll / max_scroll))
            pygame.draw.rect(screen, (*BRIGHT, 200), (bar_x, ty, 6, thumb_h))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Matrix fullscreen display with Spotify")
    parser.add_argument("--demo", action="store_true", help="Simulated Spotify tracks (no API)")
    parser.add_argument("--font", default=None, help="Font family (default: consolas)")
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
        "--exclusive",
        action="store_true",
        help="Use exclusive fullscreen (default is borderless windowed)",
    )
    args = parser.parse_args(argv)

    if args.list_displays:
        for idx, size in list_displays():
            print(f"  [{idx}]  {size[0]} x {size[1]}")
        return 0

    if args.no_spotify:
        spotify = None
    elif args.demo:
        spotify = DemoSpotifySource()
    else:
        spotify = SpotifySource()

    display = MatrixDisplay(
        spotify=spotify,
        font_name=args.font,
        char_size=args.size,
        display_index=args.display,
        exclusive=args.exclusive,
    )
    try:
        display.run()
    except KeyboardInterrupt:
        if spotify:
            spotify.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
