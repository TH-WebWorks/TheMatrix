# Architecture

Overview of TheMatrix codebase structure and data flow.

## Entry point

```
main.py → icon_setup.apply_app_icon() → matrix_display.main()
```

`matrix_display.py` is the core application: argument parsing, pygame loop, rain rendering, panel drawing, and Spotify integration.

## Module map

| Module | Responsibility |
|--------|----------------|
| `matrix_display.py` | Main loop, rain columns, panel rendering, inject queue |
| `matrix_ui.py` | Keybind table, shared UI chrome |
| `settings_menu.py` | Settings launcher GUI, Spotify connect modal |
| `display_setup.py` | Monitor enumeration, fullscreen/windowed surfaces |
| `font_setup.py` | Cross-platform font loading (Retina-safe on macOS) |
| `icon_setup.py` | App icon generation and Dock icon (macOS) |
| `spotify_connect.py` | OAuth, credentials, login status |
| `spotify_source.py` | Playback polling, queue, devices, demo source |
| `spotify_setup.py` | CLI setup and diagnostics |
| `spotify_qr.py` | QR code for connect flow |
| `lyrics_source.py` | LRCLIB synced lyrics fetcher |
| `news_source.py` | BBC RSS headline fetcher |
| `weather_source.py` | wttr.in weather fetcher |
| `session_log.py` | In-memory session event log |
| `ads_browser.py` | MacRumors pywebview wrapper |
| `panels/registry.py` | Panel definitions, dock tabs, panel chrome |
| `panels/hex_dump.py` | xxd-style hex formatting |

## Panel system

Panels are declared as `PanelDef` dataclasses in `panels/registry.py`:

```python
@dataclass(frozen=True)
class PanelDef:
    id: str
    key: int          # pygame key constant
    tab_labels: tuple[str, ...]
    title: str
    subtitle: str
```

`PanelRegistry` tracks:

- `active` — currently open panel id (or `None`)
- `scroll` — per-panel scroll offsets
- `tab_rects` — click targets for dock tabs

Rendering is split between `registry.py` (chrome) and `matrix_display.py` (panel content).

## Rain engine

`RainColumn` objects hold position, speed, length, and character arrays. Each frame:

1. Columns step downward
2. Random glyph mutations (~2% chance per frame)
3. Columns reset when they fall off-screen

`MATRIX_CHARS` includes Japanese katakana and alphanumeric characters.

### Rain injection

`inject_queue` holds strings from news and weather panels. Every ~45 frames, a payload is popped and characters are pushed into falling columns.

## Data sources

Background threads fetch external data:

```
NewsSource     → BBC RSS (15 min refresh)
WeatherSource  → wttr.in JSON (30 min refresh)
LyricsSource   → LRCLIB API (on track change)
SpotifySource  → Spotify Web API (adaptive poll interval)
```

All sources use threading with locks and expose dataclass state objects read by the main render loop.

## Spotify data flow

```
settings_menu → spotify_connect.connect_spotify()
                     ↓
              .spotify_cache (OAuth token)
                     ↓
spotify_source.SpotifySource.poll()
                     ↓
              SpotifyPlayback dataclass
                     ↓
         matrix_display render + panels
```

Rate-limit backoff adjusts poll interval and logs to `SessionLog`.

## Conduit encoding

Playback data is serialized to bytes (`_conduit_payload`), converted to bits, and rendered as a scrolling binary grid. Album art is downsampled to glyph brightness values.

## Display pipeline

```
create_fullscreen_surface() → pygame display surface
         ↓
Rain columns + inject → blit glyphs
         ↓
Spotify stream panel (right side)
         ↓
Active dock panel overlay
         ↓
_matrix_tint() post-process → flip display
```

## Threading model

| Thread | Work |
|--------|------|
| Main | pygame event loop, rendering |
| Spotify poll | API requests with backoff |
| News / Weather / Lyrics | HTTP fetches on timers |
| Connect flow | OAuth browser redirect (settings) |
| MacRumors webview | Separate pywebview process |

## Configuration files

| File | Created by | Purpose |
|------|------------|---------|
| `spotify_defaults.json` | `spotify_setup.py --init` | App credentials |
| `spotify_config.json` | User override | Custom credentials |
| `.spotify_cache` | spotipy OAuth | Token cache |

## Bundled app structure

```
TheMatrix.app/
  Contents/
    MacOS/run              # Launcher script (arm64 re-exec)
    Resources/
      AppIcon.icns
      app/
        .venv/             # Bundled Python environment
        main.py, *.py
        panels/
        assets/
        logs/launch.log
```

Built by `build_macos_app.sh`.
