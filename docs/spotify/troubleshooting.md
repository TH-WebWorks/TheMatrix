# Spotify troubleshooting

Common Spotify issues and how to resolve them.

## Quick diagnostics

```bash
python3 spotify_setup.py --check
```

| Result | Action |
|--------|--------|
| `FAIL: Spotify app credentials missing` | Run `python3 spotify_setup.py --init` (developer) |
| `FAIL: not logged in` | Run `python3 spotify_setup.py --connect` |
| `FAIL: API error 401` | Re-login with `--connect` |
| `WARN: rate-limited` | Wait for `Retry-After` to expire (see below) |
| `OK: logged in as …` | Credentials are fine; check desktop app playback |

## Re-login

```bash
python3 spotify_setup.py --connect
python3 spotify_setup.py --disconnect   # clear tokens first
```

Or use ++f1++ → **Connect Spotify** in the display.

## Rate limiting

If you see a **rate limit** message:

1. Stop **every** running `python main.py` window
2. Wait — often a few hours for severe limits
3. Let any `Retry-After` header fully expire before restarting

The display no longer blocks while waiting; it polls slower and logs events in the **Log** panel (++g++).

### Rate-limit prevention

- Run only **one** Matrix instance per Spotify account
- Leave playback running; idle/paused states poll slower automatically
- Avoid rapid skip/play spam for 30–60 seconds after startup
- If Spotify returns `Retry-After`, do not restart until it expires

## Playback not detected

| Symptom | Fix |
|---------|-----|
| No album art / track name | Open Spotify desktop and start playing |
| Skip/play does nothing | Requires [Premium](https://www.spotify.com/premium) |
| Queue / devices empty | Music must be actively playing |
| Stale track info | Check Status panel (++s++) for poll interval and backoff |

## Checklist

- [ ] Spotify **desktop** open (not just web player)
- [ ] Music **playing**
- [ ] [Premium](https://www.spotify.com/premium) for playback control
- [ ] Logged in via settings or `--connect`
- [ ] Single instance running
- [ ] App credentials configured (developer: `spotify_defaults.json` exists)

## Clear cache

```bash
python3 spotify_setup.py --disconnect
```

This removes the OAuth token cache. Reconnect afterward.

## macOS app issues

If the Dock app bounces and quits:

1. Check `TheMatrix.app/Contents/Resources/app/logs/launch.log`
2. Re-run `./build_macos_app.sh`
3. Remove the old Dock shortcut and add the newly built app

## Demo mode fallback

Test the display without Spotify:

```bash
python3 main.py --demo
```

Uses simulated tracks via `DemoSpotifySource`.
