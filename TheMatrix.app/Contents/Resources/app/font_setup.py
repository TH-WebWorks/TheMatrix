"""Cross-platform font resolution.

On macOS, pygame.font.SysFont loses CJK glyphs once a display surface exists
(Retina/SDL quirk). Load a system TTF directly for Matrix rain and UI text.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import pygame

_MAC_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Supplemental/Andale Mono.ttf",
)

_TEST_GLYPHS = "ｱア♫01"


def default_font_name() -> str:
    if sys.platform == "darwin":
        return "Menlo"
    return "consolas"


def _glyphs_render(path: str, size: int) -> bool:
    try:
        font = pygame.font.Font(path, size)
    except Exception:
        return False
    for ch in _TEST_GLYPHS:
        surf = font.render(ch, True, (255, 255, 255))
        if surf.get_bounding_rect().width < 2:
            return False
        w, h = surf.get_size()
        filled = sum(1 for x in range(w) for y in range(h) if surf.get_at((x, y))[0] > 20)
        if filled < 8:
            return False
    return True


@lru_cache(maxsize=1)
def mac_font_path() -> str | None:
    if sys.platform != "darwin":
        return None
    pygame.font.init()
    for path in _MAC_FONT_CANDIDATES:
        if Path(path).is_file() and _glyphs_render(path, 20):
            return path
    return None


def get_font(
    size: int,
    *,
    name: str | None = None,
    bold: bool = False,
) -> pygame.font.Font:
    """Return a font that renders Matrix glyphs on this platform."""
    pygame.font.init()
    path = mac_font_path()
    if path and not bold:
        return pygame.font.Font(path, size)
    family = name or default_font_name()
    return pygame.font.SysFont(family, size, bold=bold)
