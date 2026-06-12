"""Hex/ASCII dump helpers for the HEX panel."""

from __future__ import annotations


def format_hex_lines(data: bytes, *, bytes_per_row: int = 16) -> list[tuple[int, str, str]]:
    """Return [(offset, hex_part, ascii_part), ...] for xxd-style display."""
    rows: list[tuple[int, str, str]] = []
    for offset in range(0, len(data), bytes_per_row):
        chunk = data[offset : offset + bytes_per_row]
        hex_parts = [f"{b:02x}" for b in chunk]
        hex_part = " ".join(hex_parts).ljust(bytes_per_row * 3 - 1)
        ascii_part = "".join(chr(ch) if 32 <= ch < 127 else "." for ch in chunk)
        rows.append((offset, hex_part, ascii_part))
    return rows
