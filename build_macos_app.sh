#!/usr/bin/env bash
# Build Matrix icon + self-contained TheMatrix.app for macOS Dock.
set -euo pipefail
cd "$(dirname "$0")"

BUILD_PY="$(command -v python3 || echo /usr/bin/python3)"
if [[ "$(uname -m)" == "arm64" ]]; then
  BUILD_PY=(arch -arm64 "$BUILD_PY")
fi

"${BUILD_PY[@]}" -m pip install -q -r requirements.txt
"${BUILD_PY[@]}" -c "from icon_setup import ensure_icon_png; ensure_icon_png()"

ICONSET="assets/icon.iconset"
ICNS="assets/matrix-icon.icns"
PNG="assets/matrix-icon.png"
APP="TheMatrix.app"
APP_HOME="$APP/Contents/Resources/app"

rm -rf "$ICONSET" "$APP"
mkdir -p "$ICONSET"

for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$PNG" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  dbl=$((size * 2))
  sips -z "$dbl" "$dbl" "$PNG" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$ICNS"
rm -rf "$ICONSET"

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$APP_HOME/assets"

cp "$ICNS" "$APP/Contents/Resources/AppIcon.icns"
cp assets/matrix-icon.png assets/matrix-icon.icns "$APP_HOME/assets/" 2>/dev/null || cp assets/matrix-icon.png "$APP_HOME/assets/"
cp *.py requirements.txt "$APP_HOME/"
cp spotify_defaults.json.example "$APP_HOME/" 2>/dev/null || true
if [[ -f spotify_defaults.json ]]; then
  cp spotify_defaults.json "$APP_HOME/"
fi

echo "Creating app Python environment..."
"${BUILD_PY[@]}" -m venv "$APP_HOME/.venv"
"$APP_HOME/.venv/bin/pip" install -q --upgrade pip
"$APP_HOME/.venv/bin/pip" install -q -r "$APP_HOME/requirements.txt"

cat >"$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>run</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>com.thematrix.display</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>TheMatrix</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>10.13</string>
  <key>LSRequiresNativeExecution</key>
  <true/>
  <key>LSArchitecturePriority</key>
  <array>
    <string>arm64</string>
  </array>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

cat >"$APP/Contents/MacOS/run" <<'EOF'
#!/bin/bash
# Finder sometimes launches .app under Rosetta (uname -m = x86_64 on M1/M2/M3).
# Re-exec this script natively on Apple Silicon before touching Python.
if [[ "$(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" == "1" ]]; then
  if [[ "$(uname -m)" != "arm64" ]]; then
    exec /usr/bin/arch -arm64 /bin/bash "$0" "$@"
  fi
fi

APP_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP_HOME="$APP_ROOT/Contents/Resources/app"
LOG_DIR="$APP_HOME/logs"
LOG_FILE="$LOG_DIR/launch.log"
PYTHON="$APP_HOME/.venv/bin/python3"

alert() {
  /usr/bin/osascript -e "display alert \"TheMatrix\" message \"$1\"" >/dev/null 2>&1 || true
}

mkdir -p "$LOG_DIR"
{
  echo "=== $(date) ==="
  echo "APP_HOME=$APP_HOME"
  echo "ARCH=$(uname -m)"
  echo "PYTHON=$PYTHON"
} >>"$LOG_FILE"

if [[ ! -x "$PYTHON" ]]; then
  alert "App environment missing. Re-run ./build_macos_app.sh in the project folder."
  exit 1
fi

if [[ ! -f "$APP_HOME/main.py" ]]; then
  alert "App files are missing. Re-run ./build_macos_app.sh in the project folder."
  exit 1
fi

cd "$APP_HOME" || {
  alert "Could not open app folder."
  exit 1
}

"$PYTHON" main.py "$@" >>"$LOG_FILE" 2>&1
STATUS=$?
if [[ "$STATUS" -ne 0 ]]; then
  alert "TheMatrix exited with an error. See logs/launch.log inside the app."
  exit "$STATUS"
fi
EOF
chmod +x "$APP/Contents/MacOS/run"

echo "Built $APP (self-contained with bundled Python — safe for Dock/Applications)."
echo "Replace any old Dock shortcut, then open TheMatrix.app."
