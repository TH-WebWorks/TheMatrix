"""One-time Spotify Developer app linking."""

from __future__ import annotations

import argparse
import getpass

from spotify_source import (
    CACHE_PATH,
    CONFIG_PATH,
    clear_spotify_cache,
    load_spotify_config,
    save_spotify_config,
)


def _check_connection() -> int:
    config = load_spotify_config()
    if not config:
        print("FAIL: spotify_config.json missing or incomplete")
        print("Run: python spotify_setup.py")
        return 1

    try:
        import spotipy
        from spotipy.exceptions import SpotifyException
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        print("FAIL: spotipy not installed — pip install spotipy")
        return 1

    if not CACHE_PATH.exists():
        print("FAIL: no login token (.spotify_cache missing)")
        print("Run: python spotify_setup.py --reauth")
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
        if exc.http_status == 429:
            retry = (getattr(exc, "headers", None) or {}).get("Retry-After", "?")
            print(f"Rate limited. Wait {retry}s, close extra Matrix windows, then retry.")
        elif exc.http_status == 401:
            print("Run: python spotify_setup.py --reauth")
        return 1

    try:
        data = sp.current_user_playing_track()
    except SpotifyException as exc:
        if exc.http_status == 429:
            retry = (getattr(exc, "headers", None) or {}).get("Retry-After", "?")
            print(f"WARN: login OK, but playback API is rate-limited (wait {retry}s)")
            print("Close all Matrix windows and try again later.")
            return 1
        print(f"FAIL: now playing — {exc}")
        return 1

    if not data or not data.get("item"):
        print("OK: API works, but nothing is playing right now.")
        print("Start Spotify desktop on this PC and press Play.")
        return 0

    item = data["item"]
    artist = ", ".join(a["name"] for a in item.get("artists", []))
    print(f"OK: playing {item.get('name')} — {artist}")
    return 0


def _reauthorize() -> int:
    if clear_spotify_cache():
        print("Cleared .spotify_cache")
    else:
        print("No cache file to clear")

    config = load_spotify_config()
    if not config:
        print("spotify_config.json missing — run setup first.")
        return 1

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        print("Install spotipy: pip install spotipy")
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
        open_browser=True,
    )
    print("Opening browser for Spotify login...")
    sp = spotipy.Spotify(auth_manager=auth, retries=0, requests_timeout=10)
    try:
        me = sp.current_user()
        print(f"Linked as {me.get('display_name') or me.get('id')}")
    except Exception as exc:
        print(f"Login failed: {exc}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create spotify_config.json for TheMatrix")
    parser.add_argument("--client-id", help="Spotify app Client ID")
    parser.add_argument("--client-secret", help="Spotify app Client Secret")
    parser.add_argument(
        "--reauth",
        action="store_true",
        help="Clear cached token and log in again (after network reset)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Test API connection and show current track",
    )
    args = parser.parse_args()

    if args.check:
        return _check_connection()
    if args.reauth:
        return _reauthorize()

    print("TheMatrix Spotify setup")
    print("1. https://developer.spotify.com/dashboard → Create app")
    print("2. Redirect URI: http://127.0.0.1:8888/callback")
    print("3. Paste Client ID and Secret below\n")

    client_id = args.client_id or input("Client ID: ").strip()
    client_secret = args.client_secret or getpass.getpass("Client Secret: ").strip()
    redirect = "http://127.0.0.1:8888/callback"

    save_spotify_config(client_id, client_secret, redirect)
    print(f"\nSaved {CONFIG_PATH}")
    print("Run: python spotify_setup.py --reauth")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
