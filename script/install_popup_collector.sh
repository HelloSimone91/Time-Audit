#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="$HOME/.time_audit"
APP_SOURCE="$ROOT_DIR/dist/TimeAuditPopup.app"
APP_DESTINATION="$INSTALL_DIR/TimeAuditPopup.app"
COLLECTOR_DESTINATION="$INSTALL_DIR/time_audit_popup_collector.py"
RUNNER="$INSTALL_DIR/run_popup_collector.sh"
PLIST="$HOME/Library/LaunchAgents/com.simone.timeaudit.popupcollector.plist"

if [[ "$MODE" != "--prepare" && "$MODE" != "--activate" ]]; then
  echo "usage: $0 [--prepare|--activate]" >&2
  exit 2
fi

"$ROOT_DIR/script/build_popup_helper.sh"
mkdir -p "$INSTALL_DIR/logs" "$INSTALL_DIR/screenshots" "$HOME/Library/LaunchAgents"
COPYFILE_DISABLE=1 ditto "$APP_SOURCE" "$APP_DESTINATION"
xattr -cr "$APP_DESTINATION"
codesign --force --deep --sign - "$APP_DESTINATION" >/dev/null
cp "$ROOT_DIR/src/time_audit_popup_collector.py" "$COLLECTOR_DESTINATION"
chmod +x "$COLLECTOR_DESTINATION"

if [[ ! -f "$INSTALL_DIR/config.env" ]]; then
  cp "$ROOT_DIR/config/example.env" "$INSTALL_DIR/config.env"
  chmod 600 "$INSTALL_DIR/config.env"
fi

if [[ "$MODE" == "--prepare" ]]; then
  echo "Prepared the popup collector at $INSTALL_DIR without scheduling or sending data."
  exit 0
fi

if grep -Eq 'your_token_here|your_data_source_here' "$INSTALL_DIR/config.env"; then
  echo "Fill in $INSTALL_DIR/config.env before activation." >&2
  exit 1
fi

cat > "$RUNNER" <<RUNNER
#!/bin/zsh
set -euo pipefail
while IFS= read -r line; do
  case "\$line" in
    ''|'#'*) continue ;;
    *=*) export "\$line" ;;
  esac
done < "$INSTALL_DIR/config.env"
/usr/bin/python3 "$COLLECTOR_DESTINATION" --helper-app "$APP_DESTINATION"
RUNNER
chmod +x "$RUNNER"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "https://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.simone.timeaudit.popupcollector</string>
  <key>ProgramArguments</key>
  <array><string>$RUNNER</string></array>
  <key>StartInterval</key>
  <integer>1800</integer>
  <key>StandardOutPath</key>
  <string>$INSTALL_DIR/logs/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$INSTALL_DIR/logs/launchd.err.log</string>
</dict>
</plist>
PLIST

plutil -lint "$PLIST" >/dev/null
launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST"
echo "Activated the Time Audit popup every 30 minutes."
