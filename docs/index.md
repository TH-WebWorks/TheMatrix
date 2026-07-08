# TheMatrix

Fullscreen **Matrix** digital rain on your **4K TV**, with **Spotify** (now playing, album art, playback controls).

TheMatrix is a pygame-based ambient display that renders cascading green glyphs across one or more monitors. A dock of hacker-style panels overlays the rain with live data: synced lyrics, hex dumps, binary signal decode, news, weather, and Spotify telemetry.

## Features

- **Matrix digital rain** — Japanese katakana and alphanumeric glyphs with auto-scaling for 4K displays
- **Spotify integration** — Now playing, album art, play/pause, skip, queue, and device switching
- **Dock panels** — Twelve toggleable panels (lyrics, hex, conduit, status, metadata, and more)
- **Rain injection** — News headlines and weather snippets cascade into the glyph stream
- **Multi-monitor** — Borderless fullscreen, windowed, or exclusive mode on any display
- **Settings launcher** — GUI for Spotify connect, monitor selection, and resolution
- **macOS app bundle** — Self-contained `.app` with Dock icon for one-click launch

## Quick start

=== "macOS"

    ```bash
    chmod +x start-matrix.sh
    python3 -m pip install -r requirements.txt
    ./start-matrix.sh
    ```

=== "Windows"

    ```bat
    start-matrix.bat
    ```

On first launch the **settings window** opens automatically. Connect Spotify, pick your monitor, then click **LAUNCH**.

## Controls at a glance

| Key | Action |
|-----|--------|
| ++esc++ | Quit |
| ++f1++ | Open settings |
| ++f11++ | Toggle fullscreen |
| ++space++ | Play / pause (Spotify) |
| ++left++ / ++right++ | Previous / next track |
| ++l++ … ++g++ | Open dock panels (see [Panels](user-guide/panels.md)) |

## Documentation

| Section | Description |
|---------|-------------|
| [Quick start](getting-started/quickstart.md) | Launch in under a minute |
| [Panels](user-guide/panels.md) | All twelve dock panels explained |
| [Spotify](spotify/overview.md) | Connect, configure, and troubleshoot |
| [CLI reference](reference/cli.md) | Every command-line flag |
| [Architecture](development/architecture.md) | How the codebase is organized |
| [Unity game](unity-game/overview.md) | TRACE PROTOCOL arcade game design |

## Build the docs locally

```bash
python3 -m pip install -r requirements-docs.txt
python3 -m mkdocs serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) to preview.
