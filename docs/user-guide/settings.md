# Settings launcher

The settings launcher is a pygame GUI for first-time setup and ongoing configuration.

## Open the launcher

```bash
python3 main.py --settings
```

The launcher also opens automatically on first launch via `start-matrix.sh`.

## In-display access

Press ++f1++ while the Matrix display is running to reopen settings.

## Launcher options

| Setting | Description |
|---------|-------------|
| **Connect Spotify** | Opens QR code + browser for OAuth login |
| **Rain only** | Disable Spotify integration |
| **Monitor** | Dropdown of connected displays |
| **Display mode** | Windowed, borderless, or exclusive |
| **Resolution** | Windowed resolution (e.g. 1920×1080) |
| **LAUNCH** | Start the display with chosen settings |

## Spotify connect flow

1. Click **Connect Spotify**
2. A QR code and browser window open
3. Approve access on this computer
4. Click **LAUNCH**

To reconnect later: ++f1++ → **Connect Spotify**.

## Rain only mode

Toggle **Rain only** in the launcher, or pass `--no-spotify` on the command line. Panels that don't need Spotify remain available.

## Launch settings dataclass

Settings are captured in `LaunchSettings` (`settings_menu.py`) and passed to `matrix_display.main()`:

- `display_index` — target monitor
- `mode` — windowed / borderless / exclusive
- `window_size` — `(width, height)` tuple
- `no_spotify` — rain-only flag
- `demo` — simulated tracks flag
