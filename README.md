# TheMatrix

Fullscreen **Matrix** digital rain on your **4K TV**, with **Spotify** (now playing, album art, playback controls).

## Quick start

**macOS**

```bash
chmod +x start-matrix.sh
./start-matrix.sh
```

**Windows**

```bat
start-matrix.bat
```

**ESC** quits · **F1** settings · **SPACE** play/pause · **← / →** prev/next track.

### Dock panels (one open at a time)

Press a letter key or click a tab along the bottom-left rain area. Only one panel is open at a time. Mouse wheel scrolls; click **−** to minimize.

| Key | Panel | Notes |
|-----|-------|-------|
| **L** | Full synced lyrics scroll | Auto-follows current line; LRCLIB |
| **H** | Hex dump of live signal | xxd-style view of captured playback data |
| **B** | CONDUIT binary decode | 0/1 grid, album-art portrait, synced lyric window |
| **S** | Link / display / FPS telemetry | Device, poll interval, rate-limit backoff |
| **M** | Track metadata | Release year, popularity, genres, track ID |
| **T** | Local clock | Date and timezone |
| **N** | News headlines | BBC RSS feed; headlines also injected into rain |
| **Q** | Up next queue | Spotify queue (requires playback) |
| **D** | Spotify Connect devices | Active endpoint; click a row to switch |
| **W** | Weather feed | Local conditions via wttr.in; also injected into rain |
| **G** | Session log | Track changes, panel opens, rate limits |

Panels **L**, **H**, **B**, **S**, **T**, **N**, **W**, and **G** work in rain-only mode (`--no-spotify`). **M**, **Q**, and **D** need Spotify playback.

## Settings menu (monitor + mode + resolution)

Open launcher UI with dropdowns for monitor selection, display mode, and windowed resolution:

```bash
python3 main.py --settings   # macOS
python main.py --settings    # Windows
```

Use this to target your third monitor quickly (choose monitor `[2]` if listed that way).

### 4K TV / second monitor

List monitors and pick your TV index (often `1`):

```bat
python main.py --list-displays
python main.py --display 1
```

Uses **borderless windowed fullscreen** (fills your TV/monitor, scales properly with Windows display scaling). Add `--exclusive` only if you want old exclusive fullscreen.

## Spotify (for users)

1. Launch the app (`./start-matrix.sh` or `start-matrix.bat`).
2. On first run, the **settings window** opens automatically.
3. Click **Connect Spotify** — a QR code and browser window open for a one-time login.
4. Approve access on this computer, then click **LAUNCH**.
5. Play music in **Spotify desktop** (Premium required for skip/play).

To reconnect later: press **F1** → **Connect Spotify**.

Rain only? Toggle **Rain only** in settings, or run with `--no-spotify`.

## Spotify (for developers — one time before release)

End users should never need the Spotify Developer Dashboard. You configure the app once, then ship it:

1. [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) → **Create app**
2. **Redirect URI:** `http://127.0.0.1:8888/callback`
3. Run:

```bash
python3 spotify_setup.py --init
```

4. Paste your app's Client ID and Secret. This creates `spotify_defaults.json` (bundled with releases).
5. Test: `python3 spotify_setup.py --connect`

Users only click **Connect Spotify** in the launcher — no API keys, no terminal.

### Spotify not working?

```bash
python3 spotify_setup.py --check
python3 spotify_setup.py --connect    # re-login
python3 spotify_setup.py --disconnect
```

If you see a **rate limit** message, stop every running `python main.py` window and wait (often a few hours). The display no longer blocks while waiting.

Rate-limit tips:
- Run only one Matrix instance at a time per Spotify account.
- Leave playback running; idle/paused states now poll slower automatically.
- Avoid rapid skip/play spam for ~30-60 seconds after startup.
- If Spotify returns `Retry-After`, let it fully expire before restarting the app.

**Checklist:** Spotify **desktop** open · music **playing** · [Premium](https://www.spotify.com/premium) for skip/play API.

## macOS notes

- The launcher script (`start-matrix.sh`) installs deps and opens the settings window on first launch.
- **Dock icon:** run `./build_macos_app.sh` once, then drag `TheMatrix.app` to your Dock (green Matrix rain icon). The app is self-contained — you can move it to Applications. Re-run `./build_macos_app.sh` after updates so the bundled app picks up new panel code. If an old Dock shortcut bounces and quits, remove it and add the newly built app.
- Matrix rain uses a system TTF on macOS (Arial Unicode / Hiragino) because pygame's default font path cannot render Japanese glyphs on Retina displays.
- Use **F1** in the display to reopen display settings (monitor, borderless/windowed, resolution).

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
| `--settings` | Open launcher (Spotify connect + monitor/mode/resolution) |
| `--mode borderless|exclusive|windowed` | Choose display mode |
| `--window-size WxH` | Windowed resolution (example: `1600x900`) |
