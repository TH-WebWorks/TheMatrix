# Installation

TheMatrix runs on **macOS** and **Windows** with Python 3.10+.

## Requirements

| Dependency | Purpose |
|------------|---------|
| Python 3.10+ | Runtime |
| pygame ≥ 2.5 | Display, input, rendering |
| spotipy ≥ 2.23 | Spotify Web API |
| qrcode ≥ 7.4 | QR code in settings connect flow |
| pillow ≥ 9.0 | Album art and icon generation |
| pywebview ≥ 5.0 | MacRumors ads panel webview |

## Install from source

=== "macOS"

    ```bash
    git clone https://github.com/TH-WebWorks/TheMatrix.git
    cd TheMatrix
    python3 -m pip install -r requirements.txt
  ```

=== "Windows"

    ```bat
    git clone https://github.com/TH-WebWorks/TheMatrix.git
    cd TheMatrix
    python -m pip install -r requirements.txt
    ```

## Launch scripts

| Script | Platform | Behavior |
|--------|----------|----------|
| `start-matrix.sh` | macOS | Installs deps, runs `main.py` (or bundled `.app` if present) |
| `start-matrix.bat` | Windows | Installs deps, runs `main.py` |

## macOS app bundle (optional)

For a Dock icon and self-contained install:

```bash
./build_macos_app.sh
```

Drag `TheMatrix.app` to Applications or the Dock. Re-run the build script after code updates. See [macOS app bundle](../development/building-macos-app.md).

## Virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

## Documentation dependencies

To build or serve this documentation site:

```bash
python3 -m pip install -r requirements-docs.txt
python3 -m mkdocs serve
```

## Files created at runtime

These files are generated locally and are gitignored:

| File | Purpose |
|------|---------|
| `.spotify_cache` | OAuth token cache |
| `spotify_config.json` | User Spotify credentials (if customized) |
| `spotify_defaults.json` | Bundled app credentials (developer setup) |
| `logs/session.log` | Session log panel output |
