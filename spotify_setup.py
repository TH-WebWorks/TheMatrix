"""Spotify setup — developer (release) and advanced troubleshooting."""

from __future__ import annotations

import argparse
import getpass
import shutil

from spotify_connect import (
    APP_DIR,
    DEFAULTS_PATH,
    connect_spotify,
    credentials_configured,
    disconnect_spotify,
    get_status,
    is_logged_in,
    save_custom_credentials,
)
from spotify_source import CACHE_PATH, CONFIG_PATH, clear_spotify_cache, load_spotify_config


def _check_connection() -> int:
    status = get_status()
    if not status.credentials_ready:
        print("FAIL: Spotify app credentials missing")
        print("Developer: python spotify_setup.py --init")
        return 1
    if not status.logged_in:
        print("FAIL: not logged in")
        print("Run: python spotify_setup.py --connect")
        return 1

    try:
        import spotipy
        from spotipy.exceptions import SpotifyException
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        print("FAIL: spotipy not installed — pip install spotipy")
        return 1

    config = load_spotify_config()
    if not config:
        return 1

    redirect = config.get("redirect_uri", "http://127.0.0.1:8888/callback")
    auth = SpotifyOAuth(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        redirect_uri=redirect,
        scope=(
            "user-read-currently-playing "
            "user-read-playback-state "
            "user-modify-playback-state"
        ),
        cache_path=str(CACHE_PATH),
        open_browser=False,
    )
    sp = spotipy.Spotify(auth_manager=auth, retries=0, requests_timeout=10)

    print("Checking Spotify connection...")
    try:
        me = sp.current_user()
        print(f"OK: logged in as {me.get('display_name') or me.get('id')}")
    except SpotifyException as exc:
        print(f"FAIL: API error {exc.http_status} — {exc}")
        if exc.http_status == 401:
            print("Run: python spotify_setup.py --connect")
        return 1

    try:
        data = sp.current_user_playing_track()
    except SpotifyException as exc:
        if exc.http_status == 429:
            retry = (getattr(exc, "headers", None) or {}).get("Retry-After", "?")
            print(f"WARN: login OK, but playback API is rate-limited (wait {retry}s)")
            return 1
        print(f"FAIL: now playing — {exc}")
        return 1

    if not data or not data.get("item"):
        print("OK: API works, but nothing is playing right now.")
        print("Start Spotify desktop and press Play.")
        return 0

    item = data["item"]
    artist = ", ".join(a["name"] for a in item.get("artists", []))
    print(f"OK: playing {item.get('name')} — {artist}")
    return 0


def _init_defaults(client_id: str | None, client_secret: str | None) -> int:
    example = APP_DIR / "spotify_defaults.json.example"
    if not DEFAULTS_PATH.exists() and example.exists():
        shutil.copy(example, DEFAULTS_PATH)
        print(f"Created {DEFAULTS_PATH}")

    print("\nTheMatrix — one-time developer setup")
    print("1. https://developer.spotify.com/dashboard → Create app")
    print("2. Redirect URI: http://127.0.0.1:8888/callback")
    print("3. Paste Client ID and Secret (shipped with releases)\n")

    cid = client_id or input("Client ID: ").strip()
    secret = client_secret or getpass.getpass("Client Secret: ").strip()
    if not cid or not secret:
        print("Cancelled.")
        return 1

    DEFAULTS_PATH.write_text(
        (
            "{\n"
            f'  "client_id": "{cid}",\n'
            f'  "client_secret": "{secret}",\n'
            '  "redirect_uri": "http://127.0.0.1:8888/callback"\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    print(f"\nSaved {DEFAULTS_PATH}")
    print("Users can now launch the app and click Connect Spotify.")
    print("Test: python spotify_setup.py --connect")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Spotify setup for TheMatrix")
    parser.add_argument("--init", action="store_true", help="Create spotify_defaults.json (developer, one time)")
    parser.add_argument("--connect", action="store_true", help="Open browser and log in to Spotify")
    parser.add_argument("--disconnect", action="store_true", help="Clear saved Spotify login")
    parser.add_argument("--client-id", help="Spotify app Client ID (with --init)")
    parser.add_argument("--client-secret", help="Spotify app Client Secret (with --init)")
    parser.add_argument("--reauth", action="store_true", help="Alias for --connect")
    parser.add_argument("--check", action="store_true", help="Test API connection and show current track")
    parser.add_argument(
        "--custom",
        action="store_true",
        help="Save credentials to spotify_config.json instead of spotify_defaults.json",
    )
    args = parser.parse_args()

    if args.check:
        return _check_connection()
    if args.init:
        return _init_defaults(args.client_id, args.client_secret)
    if args.disconnect:
        disconnect_spotify()
        print("Disconnected.")
        return 0
    if args.connect or args.reauth:
        if args.reauth:
            clear_spotify_cache()
        if not credentials_configured():
            print("Credentials missing. Run: python spotify_setup.py --init")
            return 1
        ok, msg, _ = connect_spotify()
        print(msg)
        return 0 if ok else 1
    if args.custom:
        print("Advanced: save personal Spotify app credentials to spotify_config.json")
        cid = args.client_id or input("Client ID: ").strip()
        secret = args.client_secret or getpass.getpass("Client Secret: ").strip()
        save_custom_credentials(cid, secret)
        print(f"Saved {CONFIG_PATH}")
        return 0

    status = get_status()
    print("TheMatrix Spotify")
    print(f"  Credentials: {'ready' if status.credentials_ready else 'missing'}")
    print(f"  Logged in:   {'yes' if is_logged_in() else 'no'}")
    if status.display_name:
        print(f"  Account:     {status.display_name}")
    print()
    print("Users: launch the app → Connect Spotify in the settings window")
    print("Developer: python spotify_setup.py --init")
    print("Advanced:  python spotify_setup.py --check | --connect | --disconnect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
