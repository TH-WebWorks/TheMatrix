"""Standalone webview entrypoint (spawned beside the pygame display)."""

from __future__ import annotations

import argparse

import webview

_DEFAULT_URL = "https://www.macrumors.com/"


def main() -> int:
    parser = argparse.ArgumentParser(description="MacRumors satellite browser")
    parser.add_argument("--url", default=_DEFAULT_URL)
    parser.add_argument("--width", type=int, default=1000)
    parser.add_argument("--height", type=int, default=900)
    args = parser.parse_args()

    webview.create_window(
        "MacRumors · Ad Signal",
        args.url,
        width=max(640, args.width),
        height=max(480, args.height),
    )
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
