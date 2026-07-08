# macOS app bundle

Build a self-contained `TheMatrix.app` for Dock and Applications folder launch.

## Build

```bash
./build_macos_app.sh
```

The script:

1. Installs Python dependencies
2. Generates the Matrix rain icon (`icon_setup.ensure_icon_png()`)
3. Creates `.icns` from PNG via `iconutil`
4. Copies all Python source, panels, assets, and requirements into the bundle
5. Creates a dedicated `.venv` inside the app
6. Writes `Info.plist` and the `run` launcher script

## Output

```
TheMatrix.app/
  Contents/
    MacOS/run
    Resources/
      AppIcon.icns
      app/          # Full Python project + .venv
```

## Usage

Drag `TheMatrix.app` to:

- **Dock** — one-click launch
- **Applications** — standard macOS install location

## Rebuild after code changes

Re-run `./build_macos_app.sh` whenever panel code or dependencies change. The bundled app does not auto-sync with the development tree.

## Launcher behavior

`start-matrix.sh` detects the bundled app and delegates:

```bash
if [[ -d TheMatrix.app/Contents/MacOS/run ]]; then
  exec TheMatrix.app/Contents/MacOS/run "$@"
fi
```

## Apple Silicon

The `run` script re-execs under `arch -arm64` when Finder launches under Rosetta, preventing mixed-architecture Python failures.

## Spotify credentials in bundle

- `spotify_defaults.json` is copied if it exists in the project root
- `spotify_defaults.json.example` is always copied as fallback

## Troubleshooting

### App bounces and quits

1. Remove the old Dock shortcut
2. Re-run `./build_macos_app.sh`
3. Add the newly built app to Dock

### Check launch log

```
TheMatrix.app/Contents/Resources/app/logs/launch.log
```

Common errors:

| Message | Fix |
|---------|-----|
| App environment missing | Re-run `build_macos_app.sh` |
| App files are missing | Re-run `build_macos_app.sh` |
| Exited with an error | Check `launch.log` for Python traceback |

## Info.plist

| Key | Value |
|-----|-------|
| `CFBundleIdentifier` | `com.thematrix.display` |
| `CFBundleExecutable` | `run` |
| `LSArchitecturePriority` | `arm64` |
| `NSHighResolutionCapable` | `true` |
