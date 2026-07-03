"""Dock-tab panel registry and shared overlay chrome."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

HEAD = (185, 255, 185)
BRIGHT = (80, 255, 120)
MID = (0, 170, 70)
DIM = (0, 55, 28)
PANEL = (0, 18, 8)


@dataclass(frozen=True)
class PanelDef:
    id: str
    key: int
    tab_labels: tuple[str, ...]
    title: str
    subtitle: str


PANEL_DEFS: tuple[PanelDef, ...] = (
    PanelDef(
        "lyrics",
        pygame.K_l,
        ("LYRICS · L", "L"),
        "LYRICS · FULL SIGNAL",
        "synced scroll · current line highlighted · L dock",
    ),
    PanelDef(
        "hex",
        pygame.K_h,
        ("HEX · H", "H"),
        "HEX · RAW SIGNAL",
        "xxd dump · bright = changed bytes · scroll · H dock",
    ),
    PanelDef(
        "conduit",
        pygame.K_b,
        ("CONDUIT · B", "0/1 · B", "B"),
        "CONDUIT · SIGNAL DECODE",
        "1 = bright · center = synced lyrics · scroll noise · B dock",
    ),
    PanelDef(
        "status",
        pygame.K_s,
        ("STATUS · S", "S"),
        "STATUS · LINK TELEMETRY",
        "device · poll · display · rain inject · S dock",
    ),
    PanelDef(
        "meta",
        pygame.K_m,
        ("META · M", "M"),
        "META · TRACK INTEL",
        "release · popularity · genres · track id · M dock",
    ),
    PanelDef(
        "time",
        pygame.K_t,
        ("TIME · T", "T"),
        "TIME · SYSTEM CLOCK",
        "local phosphor clock · T dock",
    ),
    PanelDef(
        "news",
        pygame.K_n,
        ("NEWS · N", "N"),
        "NEWS · SIGNAL FEED",
        "BBC headlines · age tags · injected into rain · N dock",
    ),
    PanelDef(
        "ads",
        pygame.K_a,
        ("ADS · A", "A"),
        "ADS · MACRUMORS SIGNAL",
        "live webview satellite window · A dock · close panel to dismiss",
    ),
    PanelDef(
        "queue",
        pygame.K_q,
        ("QUEUE · Q", "Q"),
        "QUEUE · UP NEXT",
        "upcoming tracks · scroll · Q dock",
    ),
    PanelDef(
        "devices",
        pygame.K_d,
        ("DEVICES · D", "D"),
        "DEVICES · CONNECT ENDPOINTS",
        "Spotify Connect targets · click to switch · D dock",
    ),
    PanelDef(
        "weather",
        pygame.K_w,
        ("WEATHER · W", "W"),
        "WEATHER · ATMOSPHERE",
        "local conditions · injected into rain · scroll · W dock",
    ),
    PanelDef(
        "log",
        pygame.K_g,
        ("LOG · G", "G"),
        "LOG · SESSION TRACE",
        "track changes · panels · rate limits · scroll · G dock",
    ),
)

PANEL_BY_ID = {p.id: p for p in PANEL_DEFS}
PANEL_BY_KEY = {p.key: p for p in PANEL_DEFS}


class PanelRegistry:
    def __init__(self) -> None:
        self.active: str | None = None
        self.scroll: dict[str, int] = {p.id: 0 for p in PANEL_DEFS}
        self.tab_rects: dict[str, pygame.Rect] = {}
        self.min_btn_rect: pygame.Rect | None = None

    def toggle(self, panel_id: str) -> None:
        if self.active == panel_id:
            self.active = None
        else:
            self.active = panel_id
            self.scroll[panel_id] = 0

    def close(self) -> None:
        self.active = None

    def scroll_active(self, delta: int) -> None:
        if not self.active:
            return
        current = self.scroll.get(self.active, 0)
        self.scroll[self.active] = max(0, current + delta)

    def active_scroll(self) -> int:
        if not self.active:
            return 0
        return self.scroll.get(self.active, 0)

    def set_scroll(self, panel_id: str, value: int) -> None:
        self.scroll[panel_id] = max(0, value)

    def scroll_for(self, panel_id: str) -> int:
        return self.scroll.get(panel_id, 0)


def _stream_width(w: int) -> int:
    return int(min(520, w * 0.24))


def _tab_label(definition: PanelDef, *, open_panel: bool) -> str:
    if open_panel:
        return definition.tab_labels[0]
    for label in definition.tab_labels:
        return label
    return definition.tab_labels[-1]


def draw_dock_tabs(
    screen: pygame.Surface,
    font_sm: pygame.font.Font,
    registry: PanelRegistry,
    w: int,
    h: int,
    scale: float,
    margin: int,
) -> None:
    """Draw horizontal dock tabs; store click rects in registry.tab_rects."""
    stream_w = _stream_width(w)
    rain_right = w - stream_w - margin
    tab_h = int(34 * scale)
    tab_y = h - tab_h - int(44 * scale)
    tab_pad = int(12 * scale)
    gap = int(6 * scale)

    registry.tab_rects.clear()
    x = max(margin, rain_right)
    for definition in reversed(PANEL_DEFS):
        is_active = registry.active == definition.id
        label = _tab_label(definition, open_panel=is_active)
        msg = font_sm.render(label, True, HEAD)
        tab_w = min(msg.get_width() + tab_pad * 2, rain_right - margin)
        x -= tab_w + gap
        if x < margin:
            break
        rect = pygame.Rect(x, tab_y, tab_w, tab_h)
        registry.tab_rects[definition.id] = rect

        tab = pygame.Surface((tab_w, tab_h), pygame.SRCALPHA)
        alpha = 235 if is_active else 200
        tab.fill((*PANEL, alpha))
        border = BRIGHT if is_active else MID
        border_alpha = 180 if is_active else 90
        pygame.draw.rect(tab, (*border, border_alpha), tab.get_rect(), width=max(1, int(2 * scale)))
        screen.blit(tab, rect.topleft)
        text_x = rect.x + (rect.width - msg.get_width()) // 2
        screen.blit(msg, (text_x, rect.y + (rect.height - msg.get_height()) // 2))


def panel_bounds(w: int, h: int, margin: int) -> tuple[int, int, int, int]:
    stream_w = _stream_width(w)
    rain_w = w - stream_w - margin * 2
    panel_w = int(min(rain_w, w * 0.68))
    panel_h = int(min(h - margin * 2, h * 0.78))
    return margin, margin, panel_w, panel_h


def draw_panel_shell(
    screen: pygame.Surface,
    registry: PanelRegistry,
    definition: PanelDef,
    font_sm: pygame.font.Font,
    font_md: pygame.font.Font,
    w: int,
    h: int,
    scale: float,
    margin: int,
) -> tuple[int, int, int, int, int, int, int]:
    """
    Draw veil + panel chrome. Returns
    (px, py, panel_w, panel_h, inner_x, inner_y, inner_w, inner_h, footer_h).
    """
    px, py, panel_w, panel_h = panel_bounds(w, h, margin)

    veil = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 175))
    screen.blit(veil, (px, py))

    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((*PANEL, 235))
    pygame.draw.rect(panel, (*MID, 120), panel.get_rect(), width=max(1, int(2 * scale)))
    screen.blit(panel, (px, py))

    hx = px + int(16 * scale)
    hy = py + int(12 * scale)
    screen.blit(font_md.render(definition.title, True, HEAD), (hx, hy))

    min_sz = int(28 * scale)
    registry.min_btn_rect = pygame.Rect(
        px + panel_w - min_sz - int(10 * scale),
        py + int(8 * scale),
        min_sz,
        min_sz,
    )
    pygame.draw.rect(screen, (*DIM, 200), registry.min_btn_rect, border_radius=4)
    minus = font_md.render("−", True, HEAD)
    screen.blit(
        minus,
        (
            registry.min_btn_rect.centerx - minus.get_width() // 2,
            registry.min_btn_rect.centery - minus.get_height() // 2,
        ),
    )

    screen.blit(font_sm.render(definition.subtitle, True, DIM), (hx, hy + int(26 * scale)))

    footer_h = int(52 * scale)
    inner_x = hx
    inner_y = hy + int(50 * scale)
    inner_w = panel_w - int(32 * scale)
    inner_h = panel_h - int(62 * scale) - footer_h
    return px, py, panel_w, panel_h, inner_x, inner_y, inner_w, inner_h, footer_h


def draw_scrollbar(
    screen: pygame.Surface,
    inner_x: int,
    inner_y: int,
    inner_w: int,
    inner_h: int,
    scroll: int,
    max_scroll: int,
    scale: float,
) -> None:
    if max_scroll <= 0:
        return
    bar_x = inner_x + inner_w - int(8 * scale)
    track_h = inner_h - int(4 * scale)
    pygame.draw.rect(screen, (*DIM, 160), (bar_x, inner_y + 2, 6, track_h))
    thumb_h = max(int(24 * scale), int(track_h * (inner_h / max(1, max_scroll + inner_h))))
    ty = inner_y + 2 + int((track_h - thumb_h) * (scroll / max_scroll))
    pygame.draw.rect(screen, (*BRIGHT, 200), (bar_x, ty, 6, thumb_h))
