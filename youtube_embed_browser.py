"""Standalone YouTube embed webview (spawned beside the pygame display)."""

from __future__ import annotations

import argparse
import html
import json
import tempfile
from pathlib import Path

import webview

_DEFAULT_VIDEO_ID = "dQw4w9WgXcQ"


def _clean_video_id(video_id: str) -> str:
    return "".join(ch for ch in (video_id or "") if ch.isalnum() or ch in "-_")[:32]


def build_embed_html(video_id: str, *, autoplay: bool = True) -> str:
    vid = _clean_video_id(video_id) or _DEFAULT_VIDEO_ID
    autoplay_flag = "1" if autoplay else "0"
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
    id="player"
    title="YouTube video player"
    referrerpolicy="strict-origin-when-cross-origin"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
    allowfullscreen
  ></iframe>
  <script>
    (function () {{
      const videoId = {json.dumps(vid)};
      const params = new URLSearchParams({{
        autoplay: {json.dumps(autoplay_flag)},
        rel: "0",
        modestbranding: "1",
        playsinline: "1",
        enablejsapi: "1",
        origin: location.origin,
      }});
      document.getElementById("player").src =
        "https://www.youtube-nocookie.com/embed/" +
        encodeURIComponent(videoId) +
        "?" +
        params.toString();
    }})();
  </script>
</body>
</html>"""


def _write_embed_page(video_id: str) -> Path:
    root = Path(tempfile.mkdtemp(prefix="matrix-youtube-"))
    page = root / "index.html"
    page.write_text(build_embed_html(video_id), encoding="utf-8")
    return page


def main() -> int:
    parser = argparse.ArgumentParser(description="YouTube embed satellite player")
    parser.add_argument("--video-id", default=_DEFAULT_VIDEO_ID)
    parser.add_argument("--title", default="YouTube · Mini Player")
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--height", type=int, default=405)
    args = parser.parse_args()

    label = html.unescape(args.title.strip() or "YouTube · Mini Player")
    page = _write_embed_page(args.video_id)
    webview.create_window(
        label[:96],
        url=str(page),
        width=max(480, args.width),
        height=max(270, args.height),
        background_color="#0f0f0f",
    )
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
