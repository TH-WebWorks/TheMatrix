# macOS

Platform-specific notes for running TheMatrix on macOS.

## Launcher script

`start-matrix.sh` installs dependencies and launches the display:

```bash
chmod +x start-matrix.sh
./start-matrix.sh
```

If `TheMatrix.app` exists, the script delegates to the bundled app instead.

## Dock icon / app bundle

Build a self-contained `.app`:

```bash
./build_macos_app.sh
```

Then drag `TheMatrix.app` to your Dock or Applications folder.

!!! note "Rebuild after updates"
    Re-run `./build_macos_app.sh` after code changes so the bundled app picks up new panel code.

If an old Dock shortcut bounces and quits, remove it and add the newly built app.

See [macOS app bundle](../development/building-macos-app.md) for build details.

## Fonts on Retina displays

Matrix rain uses a system TTF on macOS (**Arial Unicode** / **Hiragino**) because pygame's default font path cannot render Japanese katakana glyphs on Retina displays. Font selection is handled in `font_setup.py`.

## Display settings

- ++f1++ — reopen settings (monitor, borderless/windowed, resolution)
- ++f11++ — toggle windowed ↔ borderless fullscreen

## Apple Silicon

The app bundle launcher (`TheMatrix.app/Contents/MacOS/run`) re-execs natively on arm64 to avoid Rosetta-related Python issues when launched from Finder.

## Python invocation

Always use:

```bash
python3 -m pip install -r requirements.txt
```

Not bare `pip`, which may target the wrong Python installation.

## Logs

Bundled app launch logs:

```
TheMatrix.app/Contents/Resources/app/logs/launch.log
```

Session log (also visible in the ++g++ panel):

```
logs/session.log
```

## macOS-specific modules

| Module | Purpose |
|--------|---------|
| `icon_setup.py` | Generate Matrix icon, set Dock icon |
| `build_macos_app.sh` | Build script for `.app` bundle |
| `display_setup.py` | Monitor enumeration (shared with Windows) |
