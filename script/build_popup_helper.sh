#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="TimeAuditPopup"
APP_BUNDLE="$ROOT_DIR/dist/$APP_NAME.app"
STAGING_DIR="$(mktemp -d /private/tmp/time-audit-build.XXXXXX)"
STAGING_APP="$STAGING_DIR/$APP_NAME.app"
APP_CONTENTS="$STAGING_APP/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_BINARY="$APP_MACOS/$APP_NAME"
XCODE_DEVELOPER_DIR="/Applications/Xcode.app/Contents/Developer"
MODULE_CACHE="$ROOT_DIR/build/module-cache"

trap 'rm -rf "$STAGING_DIR"' EXIT
mkdir -p "$APP_MACOS" "$MODULE_CACHE"
DEVELOPER_DIR="$XCODE_DEVELOPER_DIR" /usr/bin/xcrun swiftc \
  -module-cache-path "$MODULE_CACHE" \
  "$ROOT_DIR/src/time_audit_popup_helper.swift" \
  -framework AppKit -framework Foundation -o "$APP_BINARY"
chmod +x "$APP_BINARY"

cat > "$APP_CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "https://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>$APP_NAME</string>
  <key>CFBundleIdentifier</key><string>com.simone.timeaudit.popup</string>
  <key>CFBundleName</key><string>Time Audit</string>
  <key>CFBundleDisplayName</key><string>Time Audit</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSPrincipalClass</key><string>NSApplication</string>
</dict>
</plist>
PLIST

plutil -lint "$APP_CONTENTS/Info.plist" >/dev/null
xattr -cr "$STAGING_APP"
codesign --force --deep --sign - "$STAGING_APP" >/dev/null
codesign --verify --deep --strict "$STAGING_APP"

rm -rf "$APP_BUNDLE"
mkdir -p "$ROOT_DIR/dist"
COPYFILE_DISABLE=1 ditto "$STAGING_APP" "$APP_BUNDLE"
echo "Built $APP_BUNDLE"
