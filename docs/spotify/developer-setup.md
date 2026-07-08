# Spotify developer setup

Configure Spotify app credentials **once** before release. End users only click **Connect Spotify** in the launcher.

## Prerequisites

- A [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) account
- Python 3 with project dependencies installed

## One-time setup

### 1. Create a Spotify app

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click **Create app**
3. Set **Redirect URI** to:

   ```
   http://127.0.0.1:8888/callback
   ```

### 2. Initialize credentials

```bash
python3 spotify_setup.py --init
```

Paste your app's **Client ID** and **Client Secret** when prompted. This creates `spotify_defaults.json` (bundled with releases).

### 3. Test the connection

```bash
python3 spotify_setup.py --connect
```

Approve in the browser, then verify:

```bash
python3 spotify_setup.py --check
```

## Credential files

| File | Purpose | Gitignored |
|------|---------|------------|
| `spotify_defaults.json` | Bundled app credentials for releases | Yes |
| `spotify_config.json` | Per-user custom credentials (advanced) | Yes |
| `.spotify_cache` | OAuth token cache | Yes |
| `spotify_defaults.json.example` | Template (safe to commit) | No |

### Example defaults file

```json
{
  "client_id": "your_spotify_app_client_id",
  "client_secret": "your_spotify_app_client_secret",
  "redirect_uri": "http://127.0.0.1:8888/callback"
}
```

## OAuth scopes

The app requests these Spotify scopes:

| Scope | Purpose |
|-------|---------|
| `user-read-currently-playing` | Now playing track |
| `user-read-playback-state` | Playback position, device |
| `user-modify-playback-state` | Play, pause, skip, device transfer |

## macOS app bundle

When building with `./build_macos_app.sh`:

- `spotify_defaults.json` is copied into the app bundle if present
- `spotify_defaults.json.example` is always copied as fallback

## API modules

| Module | Role |
|--------|------|
| `spotify_connect.py` | OAuth flow, credential storage, login status |
| `spotify_source.py` | Playback polling, queue, devices, demo mode |
| `spotify_setup.py` | CLI for init, connect, check, disconnect |
| `spotify_qr.py` | QR code surface for settings connect modal |

## Shipping releases

1. Run `spotify_setup.py --init` locally
2. Verify with `--check`
3. Include `spotify_defaults.json` in release artifacts (app bundle, zip, etc.)
4. Never commit secrets to a public repository
