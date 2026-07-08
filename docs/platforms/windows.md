# Windows

Platform-specific notes for running TheMatrix on Windows.

## Launcher script

```bat
start-matrix.bat
```

Installs dependencies via `pip` and runs `main.py` with any passed arguments.

## Python invocation

```bat
python -m pip install -r requirements.txt
python main.py
```

## Settings launcher

```bat
python main.py --settings
```

## List displays

```bat
python main.py --list-displays
python main.py --display 1
```

## Display modes

| Command | Effect |
|---------|--------|
| `python main.py --mode windowed` | Windowed (default 1920×1080) |
| `python main.py --mode borderless --display 1` | Borderless fullscreen on monitor 1 |
| `python main.py --exclusive --display 1` | Legacy exclusive fullscreen |

## DPI awareness

`display_setup.py` calls `enable_windows_dpi_awareness()` so monitor coordinates and scaling are correct on high-DPI displays. Monitor enumeration uses Win32 `EnumDisplayMonitors`.

## Demo and rain-only

```bat
python main.py --demo
python main.py --no-spotify
```

## Spotify setup

```bat
python spotify_setup.py --init
python spotify_setup.py --connect
python spotify_setup.py --check
```

## No macOS app bundle

The `.app` bundle and `build_macos_app.sh` are macOS-only. On Windows, run from source or create your own shortcut to `start-matrix.bat`.

## Controls

Same as macOS: ++esc++ quit, ++f1++ settings, ++f11++ fullscreen, ++space++ play/pause, letter keys for panels.
