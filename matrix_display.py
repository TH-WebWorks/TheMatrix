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

    def run(self) -> None:
        screen, w, h, scale, _used_display = create_fullscreen_surface(
            self.display_index,
            exclusive=self.exclusive,
        )
        char_size = self.char_size or max(14, int(18 * scale))
        margin = int(28 * scale)

        font = pygame.font.SysFont(self.font_name or "consolas", char_size)
        font_lg = pygame.font.SysFont(self.font_name or "consolas", int(32 * scale), bold=True)
        font_md = pygame.font.SysFont(self.font_name or "consolas", int(22 * scale))
        font_sm = pygame.font.SysFont(self.font_name or "consolas", int(16 * scale))
        font_xl = pygame.font.SysFont(self.font_name or "consolas", int(40 * scale), bold=True)
        font_track = pygame.font.SysFont(self.font_name or "consolas", int(28 * scale), bold=True)

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
                    elif self.spotify:
                        if event.key == pygame.K_SPACE:
                            self.spotify.play_pause()
                        elif event.key == pygame.K_RIGHT:
                            self.spotify.next_track()
                        elif event.key == pygame.K_LEFT:
                            self.spotify.previous_track()

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

        hint = "ESC quit"
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
