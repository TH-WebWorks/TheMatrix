# Spotify user setup

End users connect Spotify through the settings launcher — no API keys or terminal required.

## Steps

1. Launch the app (`./start-matrix.sh` or `start-matrix.bat`)
2. On first run, the **settings window** opens automatically
3. Click **Connect Spotify** — a QR code and browser window open
4. Approve access on this computer
5. Click **LAUNCH**
6. Play music in **Spotify desktop**

## Reconnect later

Press ++f1++ in the display → **Connect Spotify**.

## Rain only

Toggle **Rain only** in settings, or run:

```bash
python3 main.py --no-spotify
```

## Checklist when Spotify isn't working

- [ ] Spotify **desktop** is open
- [ ] Music is **playing** (not just paused at startup)
- [ ] You have [Spotify Premium](https://www.spotify.com/premium) for skip/play
- [ ] Only **one** Matrix instance is running per account
- [ ] You completed the connect flow (not just launched rain-only)

## Advanced CLI commands

For troubleshooting from the terminal:

```bash
python3 spotify_setup.py --check
python3 spotify_setup.py --connect    # re-login
python3 spotify_setup.py --disconnect
```

See [Troubleshooting](troubleshooting.md) for rate limits and error messages.
