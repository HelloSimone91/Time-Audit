#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="TimeAuditPopup"
COLLECTOR="$ROOT_DIR/src/time_audit_popup_collector.py"

pkill -x "$APP_NAME" >/dev/null 2>&1 || true
"$ROOT_DIR/script/build_popup_helper.sh"

case "$MODE" in
  --help|-h|help)
    echo "usage: $0 [run|--verify|--debug|--logs|--telemetry]"
    ;;
  run)
    /usr/bin/python3 "$COLLECTOR" --dry-run --timeout "${TIME_AUDIT_TEST_TIMEOUT:-120}"
    ;;
  --verify|verify)
    /usr/bin/python3 "$COLLECTOR" --dry-run --timeout 6 &
    COLLECTOR_PID=$!
    sleep 2
    pgrep -x "$APP_NAME" >/dev/null
    wait "$COLLECTOR_PID"
    ;;
  --debug|debug)
    lldb -- "$ROOT_DIR/dist/$APP_NAME.app/Contents/MacOS/$APP_NAME"
    ;;
  --logs|logs)
    /usr/bin/log stream --info --style compact --predicate "process == \"$APP_NAME\""
    ;;
  --telemetry|telemetry)
    /usr/bin/log stream --info --style compact --predicate 'subsystem == "com.simone.timeaudit.popup"'
    ;;
  *)
    echo "usage: $0 [run|--verify|--debug|--logs|--telemetry]" >&2
    exit 2
    ;;
esac
