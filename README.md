# TheMatrix

Fullscreen **Matrix** digital rain on your **4K TV**, with **Spotify** (now playing, album art, playback controls).

## Quick start

```bat
start-matrix.bat
```

**ESC** quits · **SPACE** play/pause · **← / →** prev/next track.

## Settings menu (monitor + mode + resolution)

Open launcher UI with dropdowns for monitor selection, display mode, and windowed resolution:

```bat
python main.py --settings
```

Use this to target your third monitor quickly (choose monitor `[2]` if listed that way).

### 4K TV / second monitor

List monitors and pick your TV index (often `1`):

```bat
python main.py --list-displays
python main.py --display 1
```

Uses **borderless windowed fullscreen** (fills your TV/monitor, scales properly with Windows display scaling). Add `--exclusive` only if you want old exclusive fullscreen.

## Spotify setup (one time)

1. [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) → **Create app**
2. **Redirect URI:** `http://127.0.0.1:8888/callback`
3. Run setup and paste Client ID / Secret:

```bat
python spotify_setup.py
```

4. Start TheMatrix — browser opens once to authorize. Token is cached in `.spotify_cache`.
5. Play music in **Spotify desktop** on the same PC (Premium required for API playback control).

Center panel shows album art (Matrix-tinted), track, artist, album, progress bar, and controls.

### Spotify not working?

After a network reset, close TheMatrix and run:

```bat
python spotify_setup.py --check
```

If login expired:

```bat
python spotify_setup.py --reauth
```

If you see a **rate limit** message, stop every running `python main.py` window and wait (often a few hours). The display no longer blocks while waiting.

Rate-limit tips:
- Run only one Matrix instance at a time per Spotify account.
- Leave playback running; idle/paused states now poll slower automatically.
- Avoid rapid skip/play spam for ~30-60 seconds after startup.
- If Spotify returns `Retry-After`, let it fully expire before restarting the app.

**Checklist:** Spotify **desktop** open on this PC · music **playing** · [Premium](https://www.spotify.com/premium) for skip/play API · redirect URI `http://127.0.0.1:8888/callback` in your [Developer app](https://developer.spotify.com/dashboard).

## Demo (no Spotify app)

```bat
python main.py --demo
```

## Rain only

```bat
python main.py --no-spotify
```

## Options

| Flag | Description |
|------|-------------|
| `--display N` | Borderless fullscreen on monitor N (4K TV) |
| `--exclusive` | Exclusive fullscreen (legacy) |
| `--list-displays` | Show monitor index + resolution |
| `--demo` | Simulated Spotify tracks |
| `--no-spotify` | Digital rain only |
| `--size N` | Rain glyph size (auto-scales on 4K) |
| `--settings` | Open launcher UI with monitor/mode/resolution dropdowns |
| `--mode borderless|exclusive|windowed` | Choose display mode |
| `--window-size WxH` | Windowed resolution (example: `1600x900`) |
