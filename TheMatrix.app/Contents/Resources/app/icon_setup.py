"""Matrix-themed app icon generation and macOS dock / window icon setup."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pygame

from font_setup import get_font

APP_DIR = Path(__file__).resolve().parent
ICON_PNG = APP_DIR / "assets" / "matrix-icon.png"
ICON_ICNS = APP_DIR / "assets" / "matrix-icon.icns"

_RAIN_CHARS = "01ｱｲｳｴｵｶｷｸｹｺABCDEF"


def generate_matrix_icon(size: int = 512) -> pygame.Surface:
    """Draw a Matrix rain app icon."""
    surface = pygame.Surface((size, size))
    surface.fill((0, 5, 0))

    glow = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(glow, (30, 255, 90, 36), (size // 2, size // 2), int(size * 0.34))
    surface.blit(glow, (0, 0))

    cell = max(10, size // 22)
    cols = size // cell
    font = get_font(cell)

    for col in range(cols):
        x = col * cell + cell // 2
        length = random.randint(5, max(6, size // cell // 2))
        y0 = random.randint(-length * cell, size // 3)
        for row in range(length):
            y = y0 + row * cell
            if y < -cell or y > size + cell:
                continue
            ch = random.choice(_RAIN_CHARS)
            if row == 0:
                color = (210, 255, 210)
            elif row < 3:
                color = (70, 255, 120)
            else:
                fade = min(1.0, row / max(1, length))
                color = (0, int(180 * (1 - fade * 0.75)), int(70 * (1 - fade * 0.6)))
            glyph = font.render(ch, True, color)
            surface.blit(glyph, (x - glyph.get_width() // 2, y))

    letter = get_font(int(size * 0.42), bold=True).render("M", True, (120, 255, 150))
    shadow = get_font(int(size * 0.42), bold=True).render("M", True, (0, 40, 15))
    lx = (size - letter.get_width()) // 2
    ly = (size - letter.get_height()) // 2 - int(size * 0.02)
    surface.blit(shadow, (lx + 2, ly + 2))
    surface.blit(letter, (lx, ly))
    return surface


def ensure_icon_png() -> Path:
    ICON_PNG.parent.mkdir(parents=True, exist_ok=True)
    if ICON_PNG.exists():
        return ICON_PNG

    pygame.init()
    pygame.font.init()
    icon = generate_matrix_icon(512)
    pygame.image.save(icon, str(ICON_PNG))
    return ICON_PNG


def _set_macos_dock_icon(path: Path) -> bool:
    if sys.platform != "darwin":
        return False
    try:
        from AppKit import NSApplication, NSImage  # type: ignore[import-untyped]

        image = NSImage.alloc().initWithContentsOfFile_(str(path.resolve()))
        if image is None:
            return False
        NSApplication.sharedApplication().setApplicationIconImage_(image)
        return True
    except Exception:
        return False


def apply_app_icon() -> None:
    """Set window + macOS dock icon from bundled Matrix artwork."""
    path = ensure_icon_png()
    if not pygame.get_init():
        pygame.init()
    try:
        icon = pygame.image.load(str(path))
        pygame.display.set_icon(icon)
    except pygame.error:
        pass
    if ICON_ICNS.exists():
        _set_macos_dock_icon(ICON_ICNS)
    else:
        _set_macos_dock_icon(path)
