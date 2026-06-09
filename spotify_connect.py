"""User-facing Spotify connect / disconnect helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from spotify_source import CACHE_PATH, CONFIG_PATH, SCOPES, clear_spotify_cache, save_spotify_config

APP_DIR = Path(__file__).resolve().parent
DEFAULTS_PATH = APP_DIR / "spotify_defaults.json"
REDIRECT_URI = "http://127.0.0.1:8888/callback"

_PLACEHOLDER_MARKERS = {
    "",
    "your_spotify_app_client_id",
    "your_spotify_app_client_secret",
    "your_client_id",
    "your_client_secret",
    "changeme",
    "replace_me",
}


@dataclass
class SpotifyStatus:
    credentials_ready: bool
    logged_in: bool
    display_name: str = ""
    message: str = ""


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _valid_credential(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() not in _PLACEHOLDER_MARKERS


def get_credentials() -> dict | None:
    """Bundled defaults, overridden by spotify_config.json if present."""
    data = _read_json(DEFAULTS_PATH) or {}
    override = _read_json(CONFIG_PATH)
    if override:
        data.update(override)
    client_id = str(data.get("client_id", "")).strip()
    client_secret = str(data.get("client_secret", "")).strip()
    if not _valid_credential(client_id) or not _valid_credential(client_secret):
        return None
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": str(data.get("redirect_uri", REDIRECT_URI)).strip() or REDIRECT_URI,
    }


def credentials_configured() -> bool:
    return get_credentials() is not None


def is_logged_in() -> bool:
    return CACHE_PATH.exists() and credentials_configured()


def get_status() -> SpotifyStatus:
    if not credentials_configured():
        return SpotifyStatus(
            credentials_ready=False,
            logged_in=False,
            message="Spotify app credentials missing — see README for release setup",
        )
    if not CACHE_PATH.exists():
        return SpotifyStatus(
            credentials_ready=True,
            logged_in=False,
            message="Click Connect Spotify to log in",
        )
    name = _fetch_display_name()
    if name:
        return SpotifyStatus(
            credentials_ready=True,
            logged_in=True,
            display_name=name,
            message=f"Connected as {name}",
        )
    return SpotifyStatus(
        credentials_ready=True,
        logged_in=False,
        message="Session expired — click Connect Spotify",
    )


def _fetch_display_name() -> str:
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        return ""

    config = get_credentials()
    if not config:
        return ""

    auth = SpotifyOAuth(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        redirect_uri=config["redirect_uri"],
        scope=SCOPES,
        cache_path=str(CACHE_PATH),
        open_browser=False,
    )
    try:
        sp = spotipy.Spotify(auth_manager=auth, retries=0, requests_timeout=10)
        me = sp.current_user()
        return str(me.get("display_name") or me.get("id") or "")
    except Exception:
        return ""


def _build_auth_manager(*, open_browser: bool = False):
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth

    config = get_credentials()
    if not config:
        return None, None
    auth = SpotifyOAuth(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        redirect_uri=config["redirect_uri"],
        scope=SCOPES,
        cache_path=str(CACHE_PATH),
        open_browser=open_browser,
    )
    return auth, spotipy


def get_authorize_url() -> str | None:
    """Spotify login URL for browser or QR code."""
    auth, _ = _build_auth_manager(open_browser=False)
    if not auth:
        return None
    try:
        return auth.get_authorize_url()
    except Exception:
        return None


def connect_spotify(*, open_browser: bool = True) -> tuple[bool, str, str]:
    """Complete OAuth. Returns (success, message, display_name)."""
    auth, spotipy_mod = _build_auth_manager(open_browser=open_browser)
    if not auth or not spotipy_mod:
        return (
            False,
            "Add Spotify app credentials below, then try again.",
            "",
        )

    try:
        sp = spotipy_mod.Spotify(auth_manager=auth, retries=0, requests_timeout=10)
        me = sp.current_user()
        name = str(me.get("display_name") or me.get("id") or "Spotify user")
        return True, f"Connected as {name}", name
    except Exception as exc:
        return False, f"Login failed: {exc}"[:120], ""


def disconnect_spotify() -> None:
    clear_spotify_cache()


def save_defaults_credentials(client_id: str, client_secret: str) -> None:
    """Save bundled app credentials (developer one-time setup)."""
    DEFAULTS_PATH.write_text(
        json.dumps(
            {
                "client_id": client_id.strip(),
                "client_secret": client_secret.strip(),
                "redirect_uri": REDIRECT_URI,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def save_custom_credentials(client_id: str, client_secret: str) -> None:
    save_spotify_config(client_id.strip(), client_secret.strip(), REDIRECT_URI)
