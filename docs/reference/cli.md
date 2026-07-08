# CLI options

All command-line flags for `python main.py` (or `python3 main.py` on macOS).

## Usage

```bash
python3 main.py [OPTIONS]
```

On Windows:

```bat
python main.py [OPTIONS]
```

## Flags

| Flag | Description |
|------|-------------|
| `--display N` | Borderless fullscreen on monitor `N` |
| `--exclusive` | Exclusive fullscreen (legacy) |
| `--list-displays` | Print monitor index and resolution, then exit |
| `--demo` | Simulated Spotify tracks (no API) |
| `--no-spotify` | Digital rain only, no Spotify integration |
| `--size N` | Rain glyph size in pixels (auto-scales on 4K if omitted) |
| `--settings` | Open launcher (Spotify connect + monitor/mode/resolution) |
| `--mode MODE` | Display mode: `borderless`, `exclusive`, or `windowed` |
| `--window-size WxH` | Windowed resolution (example: `1600x900`) |
| `--font NAME` | Override rain font family |

## Examples

### List monitors

```bash
python3 main.py --list-displays
```

### Fullscreen on second monitor

```bash
python3 main.py --display 1 --mode borderless
```

### Windowed at custom resolution

```bash
python3 main.py --mode windowed --window-size 1600x900
```

### Open settings launcher

```bash
python3 main.py --settings
```

### Demo mode

```bash
python3 main.py --demo
```

### Rain only

```bash
python3 main.py --no-spotify
```

### Custom glyph size

```bash
python3 main.py --size 20
```

## spotify_setup.py

Separate CLI for Spotify configuration and diagnostics.

```bash
python3 spotify_setup.py --init         # Developer: create spotify_defaults.json
python3 spotify_setup.py --connect      # OAuth login
python3 spotify_setup.py --check        # Verify credentials and API access
python3 spotify_setup.py --disconnect   # Clear OAuth cache
```

## Launch scripts

| Script | Passes arguments |
|--------|------------------|
| `./start-matrix.sh [ARGS]` | Forwards to `main.py` or bundled app |
| `start-matrix.bat [ARGS]` | Forwards to `main.py` |

Example:

```bash
./start-matrix.sh --display 2 --mode borderless
```

## Default behavior

When no flags are provided:

- Opens settings on first launch (via `start-matrix.sh`)
- Windowed 1920×1080
- Spotify enabled (unless rain-only toggled in settings)
- Auto-scaled glyph size based on display resolution
