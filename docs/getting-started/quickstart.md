# Quick start

Get TheMatrix running on your display in a few steps.

## macOS

```bash
chmod +x start-matrix.sh
python3 -m pip install -r requirements.txt   # first time only
./start-matrix.sh
```

Use `python3 -m pip`, not bare `pip`, to avoid installing into the wrong Python.

## Windows

```bat
start-matrix.bat
```

The batch file installs dependencies and launches the display.

## First launch

1. The **settings window** opens automatically on first run.
2. Click **Connect Spotify** — a QR code and browser window appear for one-time login.
3. Choose your monitor, display mode, and resolution.
4. Click **LAUNCH**.

Play music in **Spotify desktop** (Premium required for skip/play controls).

## Rain only (no Spotify)

Toggle **Rain only** in the settings launcher, or run:

```bash
python3 main.py --no-spotify
```

## Demo mode

Simulated Spotify tracks without the Spotify app:

```bash
python3 main.py --demo
```

## Essential controls

| Key | Action |
|-----|--------|
| ++esc++ | Quit |
| ++f1++ | Reopen settings |
| ++f11++ | Toggle windowed ↔ borderless fullscreen |
| ++space++ | Play / pause |
| ++left++ / ++right++ | Previous / next track |

Press a letter key or click a tab along the bottom-left rain area to open dock panels. Only one panel is open at a time.

## Next steps

- [Dock panels](../user-guide/panels.md) — lyrics, hex dump, weather, and more
- [Display & monitors](../user-guide/display.md) — target your 4K TV
- [Spotify user setup](../spotify/user-setup.md) — reconnect or switch accounts
