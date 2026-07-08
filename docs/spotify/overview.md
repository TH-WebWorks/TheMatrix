# Spotify overview

TheMatrix integrates with Spotify for now playing, album art, playback controls, queue management, and device switching.

## What works without Spotify

Run with `--no-spotify` or toggle **Rain only** in settings. These panels still work:

- Lyrics, Hex, Conduit, Status, Time, News, Ads, Weather, Log

These panels require Spotify playback:

- Meta, Queue, Devices

Playback controls (++space++, ++left++, ++right++) also require Spotify.

## Requirements

| Requirement | Why |
|-------------|-----|
| Spotify **desktop** app | Web API reads desktop playback state |
| Music **playing** | Idle/paused states poll slower; some panels need active playback |
| [Spotify Premium](https://www.spotify.com/premium) | Skip/play API requires Premium |

## Two audiences

=== "End users"

    Click **Connect Spotify** in the settings launcher. No API keys, no terminal, no Developer Dashboard.

    → [User setup](user-setup.md)

=== "Developers / release builders"

    Configure app credentials once, bundle `spotify_defaults.json` with releases. End users never touch the Dashboard.

    → [Developer setup](developer-setup.md)

## Data sources

| Feature | API / source |
|---------|--------------|
| Now playing | Spotify Web API (`current_user_playing_track`) |
| Playback control | `user-modify-playback-state` scope |
| Queue | `get_queue()` |
| Devices | `devices()` + `transfer_playback()` |
| Lyrics | [LRCLIB](https://lrclib.net) (independent of Spotify) |
| Metadata | Track object from Spotify API |

## Rate limiting

Spotify enforces API rate limits. TheMatrix handles backoff automatically and logs rate-limit events in the session log panel. See [Troubleshooting](troubleshooting.md).

## Demo mode

Test without Spotify installed:

```bash
python3 main.py --demo
```

Uses `DemoSpotifySource` with simulated track data.
