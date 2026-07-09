"""Standalone YouTube embed webview (spawned beside the pygame display)."""

from __future__ import annotations

import argparse
import html

import webview

from youtube_player import REFERRER_ORIGIN, youtube_embed_url

_DEFAULT_VIDEO_ID = "dQw4w9WgXcQ"


def _clean_video_id(video_id: str) -> str:
    return "".join(ch for ch in (video_id or "") if ch.isalnum() or ch in "-_")[:32]


def build_embed_html(video_id: str) -> str:
    """HTML wrapper page — iframe requests inherit Referer from the webview base URL."""
    embed_src = youtube_embed_url(video_id) or youtube_embed_url(_DEFAULT_VIDEO_ID)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="referrer" content="strict-origin-when-cross-origin">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    html, body {{
      margin: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #0f0f0f;
    }}
    iframe {{
      border: 0;
      width: 100%;
      height: 100%;
      display: block;
    }}
  </style>
</head>
<body>
  <iframe
    src="{html.escape(embed_src, quote=True)}"
    title="YouTube video player"
    referrerpolicy="strict-origin-when-cross-origin"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
    allowfullscreen
  ></iframe>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="YouTube embed satellite player")
    parser.add_argument("--video-id", default=_DEFAULT_VIDEO_ID)
    parser.add_argument("--title", default="YouTube · Mini Player")
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--height", type=int, default=405)
    args = parser.parse_args()

    video_id = _clean_video_id(args.video_id) or _DEFAULT_VIDEO_ID
    if not youtube_embed_url(video_id):
        return 1

    label = html.unescape(args.title.strip() or "YouTube · Mini Player")
    player_html = build_embed_html(video_id)
    player_loaded = False

    window = webview.create_window(
        label[:96],
        width=max(480, args.width),
        height=max(270, args.height),
        background_color="#0f0f0f",
    )

    def load_player() -> None:
        nonlocal player_loaded
        if player_loaded:
            return
        player_loaded = True
        # WKWebView needs a bundle-ID base URL so YouTube receives a valid Referer.
        window.load_html(player_html, REFERRER_ORIGIN)

    window.events.loaded += load_player
    webview.start(private_mode=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
