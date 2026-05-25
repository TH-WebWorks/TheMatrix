"""Borderless windowed fullscreen for 4K / multi-monitor (Windows-friendly scaling)."""

from __future__ import annotations

import os
import sys


def enable_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes = __import__("ctypes")
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
    except Exception:
        try:
            ctypes = __import__("ctypes")
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def configure_display_index(display_index: int | None) -> None:
    if display_index is not None:
        os.environ["SDL_VIDEO_FULLSCREEN_DISPLAY"] = str(display_index)


def _monitor_rects_win32() -> list[tuple[int, int, int, int]]:
    """Return [(x, y, width, height), ...] for each monitor."""
    import ctypes
    from ctypes import wintypes

    rects: list[tuple[int, int, int, int]] = []

    def callback(_hmon, _hdc, lprect, _data):
        r = lprect.contents
        rects.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(wintypes.RECT),
        wintypes.LPARAM,
    )
    ctypes.windll.user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(callback), 0)
    return rects


def _position_window_on_monitor(display_index: int) -> tuple[int, int, int, int]:
    """
    Return (x, y, width, height) for borderless placement.
    Prefer Win32 monitor enum; fall back to pygame desktop sizes.
    """
    import pygame

    if sys.platform == "win32":
        try:
            monitors = _monitor_rects_win32()
            if monitors and 0 <= display_index < len(monitors):
                x, y, w, h = monitors[display_index]
                os.environ["SDL_VIDEO_WINDOW_POS"] = f"{x},{y}"
                return x, y, w, h
        except Exception:
            pass

    sizes = pygame.display.get_desktop_sizes()
    idx = min(display_index, len(sizes) - 1) if sizes else 0
    w, h = sizes[idx] if sizes else (1920, 1080)
    os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
    return 0, 0, w, h


def list_displays() -> list[tuple[int, tuple[int, int]]]:
    import pygame

    pygame.display.init()
    try:
        if sys.platform == "win32":
            monitors = _monitor_rects_win32()
            if monitors:
                return [(i, (w, h)) for i, (_x, _y, w, h) in enumerate(monitors)]
        return [(i, size) for i, size in enumerate(pygame.display.get_desktop_sizes())]
    finally:
        pygame.display.quit()


def create_fullscreen_surface(display_index: int | None = None, exclusive: bool = False):
    """
    Create the main display surface.

    Default: borderless windowed fullscreen (NOFRAME) on the chosen monitor.
    This scales correctly on 4K TVs with Windows display scaling.

    Return (screen, width, height, scale, display_index).
    """
    import pygame

    enable_windows_dpi_awareness()
    configure_display_index(display_index)

    pygame.init()
    pygame.mouse.set_visible(False)

    sizes = pygame.display.get_desktop_sizes()
    if not sizes:
        raise RuntimeError("No displays detected")

    idx = display_index if display_index is not None else 0
    if idx < 0 or idx >= len(sizes):
        idx = 0

    _x, _y, w, h = _position_window_on_monitor(idx)

    if exclusive:
        flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
    else:
        # Borderless windowed fullscreen — fills the monitor without exclusive mode.
        flags = pygame.NOFRAME | pygame.DOUBLEBUF

    screen = pygame.display.set_mode((w, h), flags, display=idx)
    pygame.display.set_caption("TheMatrix")

    actual_w, actual_h = screen.get_size()
    scale = actual_h / 1080.0
    return screen, actual_w, actual_h, scale, idx
