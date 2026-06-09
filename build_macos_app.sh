#!/usr/bin/env bash
# Build Matrix icon + TheMatrix.app bundle for a proper macOS Dock icon.
set -euo pipefail
cd "$(dirname "$0")"

python3 -m pip install -q -r requirements.txt
python3 -c "from icon_setup import ensure_icon_png; ensure_icon_png()"

ICONSET="assets/icon.iconset"
ICNS="assets/matrix-icon.icns"
PNG="assets/matrix-icon.png"
APP="TheMatrix.app"

rm -rf "$ICONSET" "$APP"
mkdir -p "$ICONSET"

for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$PNG" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  dbl=$((size * 2))
  sips -z "$dbl" "$dbl" "$PNG" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$ICNS"
rm -rf "$ICONSET"

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$ICNS" "$APP/Contents/Resources/AppIcon.icns"

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
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

cat >"$APP/Contents/MacOS/run" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PROJECT_DIR="$(dirname "$APP_DIR")"
cd "$PROJECT_DIR"
python3 -m pip install -q -r requirements.txt
exec python3 main.py "$@"
EOF
chmod +x "$APP/Contents/MacOS/run"

echo "Built $APP with Matrix dock icon."
echo "Drag TheMatrix.app to your Dock, or run: open TheMatrix.app"
