#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="$HOME/.time_audit"
CONFIG_FILE="$INSTALL_DIR/config.env"
DATA_SOURCE_ID="37906423-ccc1-80b9-96b7-000b196f9131"

echo "This activates a Time Audit popup every 30 minutes."
echo "Each run uploads its screenshot, app/window/browser context, and check-in fields to Notion."
read -r -s -p "Paste your Notion integration token (hidden): " NOTION_TOKEN_INPUT
echo

if [[ -z "$NOTION_TOKEN_INPUT" ]]; then
  echo "No token entered; nothing was activated." >&2
  exit 1
fi

mkdir -p "$INSTALL_DIR"
umask 077
TEMP_CONFIG="$(mktemp "$INSTALL_DIR/config.env.XXXXXX")"
trap 'rm -f "$TEMP_CONFIG"' EXIT

{
  printf 'NOTION_TOKEN=%s\n' "$NOTION_TOKEN_INPUT"
  printf 'NOTION_DATA_SOURCE_ID=%s\n' "$DATA_SOURCE_ID"
  printf 'NOTION_VERSION=2026-03-11\n'
  printf 'TIME_AUDIT_LOCATION_LABEL=Austin, TX\n'
  printf 'TIME_AUDIT_LAT=30.2672\n'
  printf 'TIME_AUDIT_LON=-97.7431\n'
  printf 'TIME_AUDIT_SESSION_ID=time-audit-popup-v1\n'
  printf 'TIME_AUDIT_INTERVAL_MINUTES=30\n'
} > "$TEMP_CONFIG"

mv "$TEMP_CONFIG" "$CONFIG_FILE"
chmod 600 "$CONFIG_FILE"
unset NOTION_TOKEN_INPUT
trap - EXIT

"$ROOT_DIR/script/install_popup_collector.sh" --activate
launchctl kickstart -k "gui/$UID/com.simone.timeaudit.popupcollector"
echo "The schedule is active and the first popup is starting now."
