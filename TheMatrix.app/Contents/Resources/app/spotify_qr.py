"""QR code helper for Spotify login URL."""

from __future__ import annotations

import pygame


def make_qr_surface(url: str, pixel_size: int = 168) -> pygame.Surface | None:
    """Render a QR code pygame surface for the given URL."""
    try:
        import qrcode
    except ImportError:
        return None

    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    if pixel_size > 0:
        img = img.resize((pixel_size, pixel_size))

    surface = pygame.image.frombytes(img.tobytes(), img.size, img.mode)
    if pygame.display.get_surface() is not None:
        surface = surface.convert()
    return surface
