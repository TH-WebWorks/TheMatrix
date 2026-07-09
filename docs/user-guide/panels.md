# Dock panels

Dock panels overlay the Matrix rain with hacker-terminal style data views. Press a letter key or click a tab along the bottom-left rain area. Only one panel is open at a time.

Mouse wheel scrolls content; click **−** to minimize.

## Panel reference

| Key | Panel | Description | Spotify required |
|-----|-------|-------------|------------------|
| ++l++ | **Lyrics** | Full synced lyrics scroll; auto-follows current line via [LRCLIB](https://lrclib.net) | No |
| ++h++ | **Hex** | xxd-style hex dump of live playback signal; bright bytes = changed | No |
| ++b++ | **Conduit** | 0/1 binary grid, album-art portrait, synced lyric window | No |
| ++s++ | **Status** | Link telemetry: device, poll interval, FPS, rate-limit backoff | No |
| ++m++ | **Meta** | Track metadata: release year, popularity, genres, track ID | Yes |
| ++t++ | **Time** | Local date and timezone clock | No |
| ++n++ | **News** | BBC RSS headlines with age tags; injected into rain | No |
| ++a++ | **Ads** | MacRumors.com in a native webview (real JS ads) | No |
| ++q++ | **Queue** | Spotify up-next queue | Yes |
| ++d++ | **Devices** | Spotify Connect endpoints; click a row to switch | Yes |
| ++w++ | **Weather** | Local conditions via [wttr.in](https://wttr.in); injected into rain | No |
| ++y++ | **YouTube** | Search YouTube for songs and play a selected result in a mini webview | No |
| ++g++ | **Log** | Session trace: track changes, panel opens, rate limits | No |

## Rain injection

Headlines from the **News** panel and weather snippets from the **Weather** panel are injected into the falling glyph stream. Injected text appears as uppercase glyphs cascading with the rain.

## Conduit panel

The Conduit panel is the visual centerpiece:

- **Binary grid** — Playback data encoded as a scrolling 0/1 matrix
- **Album art portrait** — Album cover rendered as bright/dim glyph cells; falls back to a glyph portrait when art is unavailable
- **Synced lyrics** — Current lyric line highlighted in a center window

## Hex panel

The hex dump shows a live `xxd`-style view of captured playback bytes. Changed bytes render in a brighter green to highlight signal activity.

## Ads panel

Opens `macrumors.com` in a `pywebview` satellite window. Close the panel to dismiss the webview.

## YouTube panel

The YouTube panel uses the official YouTube Data API v3. Add an API key in the `F1` settings launcher, then:

- Type a song, artist, or album query
- Press `Enter` to search
- Use `Up` / `Down` to change the highlighted result
- Press `Shift+Enter` or click a row to play the selected video in a mini webview beside the display
- Close the panel to dismiss the player (falls back to your browser if `pywebview` is unavailable)

## Panel registry

Panels are defined in `panels/registry.py` as `PanelDef` entries with id, key binding, tab labels, title, and subtitle. The `PanelRegistry` class tracks which panel is active, scroll positions, and click targets for dock tabs.
