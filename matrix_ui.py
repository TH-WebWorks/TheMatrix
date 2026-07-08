"""Shared Matrix-styled UI chrome — keybind tables, panel frames."""

from __future__ import annotations

import math

import pygame

from panels.registry import PANEL_DEFS

HEAD = (185, 255, 185)
BRIGHT = (80, 255, 120)
MID = (0, 170, 70)
DIM = (0, 55, 28)
UI_DIM = (50, 140, 75)
PANEL = (0, 18, 8)
WARN = (255, 200, 60)


def keybind_rows(*, include_spotify: bool = True) -> list[tuple[str, str]]:
    """Return (key, action) rows for the on-screen keymap."""
    rows: list[tuple[str, str]] = [
        ("ESC", "quit"),
        ("F1", "settings"),
        ("F11", "toggle fullscreen"),
    ]
    panel_actions = {
        "lyrics": "full lyrics",
        "hex": "hex signal dump",
        "conduit": "binary decode",
        "status": "link telemetry",
        "meta": "track metadata",
        "time": "local clock",
        "news": "BBC news feed",
        "ads": "MacRumors webview",
        "queue": "up next queue",
        "devices": "Spotify devices",
        "weather": "weather feed",
        "youtube": "YouTube search",
        "log": "session log",
    }
    for panel in PANEL_DEFS:
        key = pygame.key.name(panel.key).upper()
        action = panel_actions.get(panel.id, panel.id)
        rows.append((key, action))
    if include_spotify:
        rows.extend(
            [
                ("SPACE", "play / pause"),
                ("← →", "prev / next track"),
            ]
        )
    return rows


def _corner_brackets(
    screen: pygame.Surface,
    rect: pygame.Rect,
    color: tuple[int, int, int],
    scale: float,
    *,
    arm: int | None = None,
) -> None:
    arm = arm or max(6, int(10 * scale))
    thick = max(1, int(2 * scale))
    x, y, r, b = rect.left, rect.top, rect.right, rect.bottom
    for cx, cy, dx, dy in (
        (x, y, 1, 1),
        (r, y, -1, 1),
        (x, b, 1, -1),
        (r, b, -1, -1),
    ):
        px, py = cx + dx * 1, cy + dy * 1
        pygame.draw.line(screen, color, (px, py), (px + dx * arm, py), thick)
        pygame.draw.line(screen, color, (px, py), (px, py + dy * arm), thick)


def draw_panel_frame(
    screen: pygame.Surface,
    rect: pygame.Rect,
    scale: float,
    pulse: float,
    *,
    fill_alpha: int = 210,
    border: tuple[int, int, int] = MID,
    brackets: bool = True,
) -> None:
    """Semi-transparent panel with border and optional corner brackets."""
    glow = 0.82 + 0.18 * math.sin(pulse * 1.4)
    edge = (
        int(border[0] * glow),
        int(border[1] * glow),
        int(border[2] * glow),
    )
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    panel.fill((*PANEL, fill_alpha))
    pygame.draw.rect(panel, (*edge, 160), panel.get_rect(), width=max(1, int(2 * scale)))
    screen.blit(panel, rect.topleft)
    if brackets:
        bracket_c = (
            int(HEAD[0] * glow),
            int(HEAD[1] * glow),
            int(HEAD[2] * glow),
        )
        _corner_brackets(screen, rect, bracket_c, scale)


def draw_keybind_table(
    screen: pygame.Surface,
    x: int,
    y: int,
    font_sm: pygame.font.Font,
    font_md: pygame.font.Font,
    rows: list[tuple[str, str]],
    scale: float,
    pulse: float,
    *,
    title: str = "SIGNAL · KEYMAP",
    compact: bool = False,
) -> pygame.Rect:
    """Draw a phosphor keymap table; return its bounding rect."""
    pad_x = int(14 * scale)
    pad_y = int(10 * scale)
    key_w = int(52 * scale) if not compact else int(44 * scale)
    row_h = int(22 * scale) if not compact else int(20 * scale)
    header_h = int(30 * scale)
    gap = int(2 * scale)

    action_w = 0
    for key, action in rows:
        action_w = max(action_w, font_sm.size(action)[0])
    key_col_w = max(key_w, max(font_md.size(k)[0] for k, _ in rows) + int(8 * scale))
    table_w = pad_x * 2 + key_col_w + int(14 * scale) + action_w
    table_h = pad_y * 2 + header_h + len(rows) * (row_h + gap) + int(4 * scale)
    rect = pygame.Rect(x, y, table_w, table_h)

    draw_panel_frame(screen, rect, scale, pulse, fill_alpha=200)

    glow = 0.85 + 0.15 * math.sin(pulse * 1.6)
    title_c = (int(HEAD[0] * glow), int(HEAD[1] * glow), int(HEAD[2] * glow))
    hx = rect.x + pad_x
    hy = rect.y + pad_y
    screen.blit(font_md.render(title, True, title_c), (hx, hy))

    rule_y = hy + font_md.get_height() + int(4 * scale)
    pygame.draw.line(
        screen,
        (*BRIGHT, 120),
        (hx, rule_y),
        (rect.right - pad_x, rule_y),
        1,
    )

    col_div_x = hx + key_col_w
    screen.blit(font_sm.render("KEY", True, UI_DIM), (hx, rule_y + int(6 * scale)))
    screen.blit(font_sm.render("ACTION", True, UI_DIM), (col_div_x + int(8 * scale), rule_y + int(6 * scale)))
    header_bottom = rule_y + int(24 * scale)
    pygame.draw.line(screen, (*DIM, 180), (hx, header_bottom), (rect.right - pad_x, header_bottom), 1)
    pygame.draw.line(
        screen,
        (*DIM, 120),
        (col_div_x, header_bottom),
        (col_div_x, rect.bottom - pad_y),
        1,
    )

    row_y = header_bottom + int(4 * scale)
    for i, (key, action) in enumerate(rows):
        if i > 0:
            pygame.draw.line(
                screen,
                (*DIM, 70),
                (hx, row_y - gap),
                (rect.right - pad_x, row_y - gap),
                1,
            )
        key_c = HEAD if key in ("ESC", "F1", "F11", "SPACE") else BRIGHT
        screen.blit(font_md.render(key, True, key_c), (hx + int(4 * scale), row_y))
        action_c = MID if i % 2 == 0 else UI_DIM
        screen.blit(font_sm.render(action, True, action_c), (col_div_x + int(8 * scale), row_y + int(1 * scale)))
        row_y += row_h + gap

    return rect


def draw_settings_frame(
    screen: pygame.Surface,
    rect: pygame.Rect,
    pulse: float,
) -> None:
    """Outer launcher frame with Matrix chrome."""
    glow = 0.82 + 0.18 * math.sin(pulse * 1.2)
    edge = (int(BRIGHT[0] * glow), int(BRIGHT[1] * glow), int(BRIGHT[2] * glow))

    shadow = pygame.Surface((rect.width + 16, rect.height + 16), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 90))
    screen.blit(shadow, (rect.x + 8, rect.y + 8))

    frame = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    frame.fill((*PANEL, 238))
    pygame.draw.rect(frame, (*edge, 200), frame.get_rect(), width=2, border_radius=12)
    inner = frame.get_rect().inflate(-int(8), -int(8))
    pygame.draw.rect(frame, (*DIM, 90), inner, width=1, border_radius=10)
    screen.blit(frame, rect.topleft)
    _corner_brackets(screen, rect, HEAD, 1.0, arm=14)

    scan_y = rect.y + int(52 + (pulse * 40) % max(1, rect.height - 104))
    scan = pygame.Surface((rect.width - 24, 2), pygame.SRCALPHA)
    scan.fill((*BRIGHT, 28))
    screen.blit(scan, (rect.x + 12, scan_y))
