#!/usr/bin/env python3
"""Native-popup Time Audit collector for macOS.

Dry-run mode never captures a screenshot and never makes a network request.
Normal mode saves locally first, then sends the configured fields and screenshot
to Notion.
"""

import argparse
import json
import mimetypes
import os
import platform
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


HOME = Path.home()
BASE_DIR = HOME / ".time_audit"
SCREENSHOT_DIR = BASE_DIR / "screenshots"
LOG_DIR = BASE_DIR / "logs"
LOCAL_LOG = LOG_DIR / "time_audit_entries.jsonl"
STATE_FILE = BASE_DIR / "last_values.json"
DEFAULT_HELPER_APP = Path(__file__).resolve().parents[1] / "dist" / "TimeAuditPopup.app"

DATA_SOURCE_ID = os.getenv("NOTION_DATA_SOURCE_ID") or os.getenv("NOTION_DATABASE_ID")
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_VERSION = os.getenv("NOTION_VERSION", "2026-03-11")
LOCATION_LABEL = os.getenv("TIME_AUDIT_LOCATION_LABEL", "Austin, TX")
LAT = os.getenv("TIME_AUDIT_LAT", "30.2672")
LON = os.getenv("TIME_AUDIT_LON", "-97.7431")
SESSION_ID = os.getenv("TIME_AUDIT_SESSION_ID", "time-audit-popup-v1")
INTERVAL_MINUTES = int(os.getenv("TIME_AUDIT_INTERVAL_MINUTES", "30"))

WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle",
    53: "Moderate drizzle", 55: "Dense drizzle", 56: "Light freezing drizzle",
    57: "Dense freezing drizzle", 61: "Slight rain", 63: "Moderate rain",
    65: "Heavy rain", 66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
    77: "Snow grains", 80: "Slight rain showers", 81: "Moderate rain showers",
    82: "Violent rain showers", 85: "Slight snow showers",
    86: "Heavy snow showers", 95: "Thunderstorm",
    96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


def run_text(command, timeout=8):
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.stdout.strip()
    except Exception:
        return ""


def active_app_name():
    script = 'tell application "System Events" to get name of first process whose frontmost is true'
    return run_text(["osascript", "-e", script]) or "Unknown"


def active_window_title():
    script = (
        'tell application "System Events"\n'
        "set frontApp to first process whose frontmost is true\n"
        "try\n"
        "get name of front window of frontApp\n"
        "on error\n"
        'return ""\n'
        "end try\n"
        "end tell"
    )
    return run_text(["osascript", "-e", script])


def browser_url(active_app):
    app = active_app.lower()
    if "safari" in app:
        script = 'tell application "Safari" to get URL of front document'
    elif "chrome" in app:
        script = 'tell application "Google Chrome" to get URL of active tab of front window'
    else:
        return ""
    return run_text(["osascript", "-e", script])


def load_last_values(path=STATE_FILE):
    defaults = {
        "activity": "Work", "mood": "Neutral", "energy": 3,
        "kindness": 3, "safety": 3,
    }
    try:
        saved = json.loads(Path(path).read_text(encoding="utf-8"))
        defaults.update({key: saved[key] for key in defaults if key in saved})
    except (OSError, ValueError, TypeError):
        pass
    return defaults


def save_last_values(result, path=STATE_FILE):
    values = {
        "activity": result["activity"], "mood": result["mood"],
        "energy": result["energy"], "kindness": result["kindness"],
        "safety": result["safety"],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")


def show_popup(helper_app, context, state_file=STATE_FILE):
    helper_app = Path(helper_app).resolve()
    binary = helper_app / "Contents" / "MacOS" / "TimeAuditPopup"
    if not binary.is_file():
        raise RuntimeError(f"Popup helper is not built: {binary}")

    with tempfile.TemporaryDirectory(prefix="time-audit-popup-") as temp_dir:
        context_path = Path(temp_dir) / "context.json"
        output_path = Path(temp_dir) / "result.json"
        context_path.write_text(json.dumps(context), encoding="utf-8")
        result = subprocess.run(
            [
                "/usr/bin/open", "-W", "-n", str(helper_app), "--args",
                "--context", str(context_path), "--output", str(output_path),
            ],
            capture_output=True, text=True, timeout=context["timeoutSeconds"] + 30,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Popup helper did not launch")
        if not output_path.is_file():
            raise RuntimeError("Popup helper closed without returning a result")
        popup_result = json.loads(output_path.read_text(encoding="utf-8"))

    if popup_result.get("outcome") == "submitted":
        save_last_values(popup_result, state_file)
    return popup_result


def take_screenshot(interval_key):
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_path = SCREENSHOT_DIR / f"{interval_key}.png"
    result = subprocess.run(
        ["screencapture", "-x", str(screenshot_path)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode == 0 and screenshot_path.exists():
        return str(screenshot_path)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / "screenshot.err.log").write_text(
        f"{datetime.now().isoformat()} screencapture failed with code {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}\n",
        encoding="utf-8",
    )
    return ""


def weather_snapshot():
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={LAT}&longitude={LON}"
            "&current=temperature_2m,weather_code&temperature_unit=fahrenheit"
        )
        with urllib.request.urlopen(url, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        current = payload.get("current", {})
        code = current.get("weather_code")
        return {
            "temperature": current.get("temperature_2m"),
            "weather": WEATHER_CODES.get(code, f"Unknown weather code {code}"),
        }
    except Exception as exc:
        return {"temperature": None, "weather": f"Weather unavailable: {exc}"}


def notify(title, message):
    escaped_title = title.replace('"', '\\"')
    escaped_message = message.replace('"', '\\"')
    run_text([
        "osascript", "-e",
        f'display notification "{escaped_message}" with title "{escaped_title}"',
    ])


def request_json(path, payload, version=NOTION_VERSION):
    if not NOTION_TOKEN or not DATA_SOURCE_ID:
        raise RuntimeError("Missing NOTION_TOKEN or NOTION_DATA_SOURCE_ID in ~/.time_audit/config.env")
    request = urllib.request.Request(
        f"https://api.notion.com/v1/{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Content-Type": "application/json",
            "Notion-Version": version,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Notion API error {exc.code}: {body}") from exc


def upload_file_to_notion(path):
    file_path = Path(path)
    if not file_path.exists():
        return None
    if file_path.stat().st_size > 20 * 1024 * 1024:
        raise RuntimeError(f"Screenshot is over 20 MB: {file_path}")
    upload = request_json("file_uploads", {}, version=NOTION_VERSION)
    upload_id = upload["id"]
    mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    boundary = f"----time-audit-{uuid.uuid4().hex}"
    filename = file_path.name
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + file_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = urllib.request.Request(
        f"https://api.notion.com/v1/file_uploads/{upload_id}/send",
        data=body,
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            uploaded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Notion file upload error {exc.code}: {body_text}") from exc
    if uploaded.get("status") != "uploaded":
        raise RuntimeError(f"Screenshot upload did not finish: {uploaded}")
    return {"name": filename, "type": "file_upload", "file_upload": {"id": upload_id}}


def multi_select(value):
    return [{"name": value}] if value else []


def create_notion_entry(entry):
    participated = entry["outcome"] == "submitted"
    properties = {
        "Name": {"title": [{"text": {"content": entry["name"]}}]},
        "Timestamp": {"date": {"start": entry["timestamp"]}},
        "Participated": {"checkbox": participated},
        "Raw Context": {"rich_text": [{"text": {"content": json.dumps(entry, indent=2)[:2000]}}]},
        "Active Window": {"rich_text": [{"text": {"content": entry["active_window"][:2000]}}]},
        "Active App": {"rich_text": [{"text": {"content": entry["active_app"][:2000]}}]},
        "Interval Key": {"rich_text": [{"text": {"content": entry["interval_key"]}}]},
        "Device": {"rich_text": [{"text": {"content": entry["device"][:2000]}}]},
        "Entry Type": {"select": {"name": "Mac Popup Audit"}},
        "Notes": {"rich_text": [{"text": {"content": (entry.get("notes") or "")[:2000]}}]},
        "Weather": {"rich_text": [{"text": {"content": entry["weather"][:2000]}}]},
        "Temperature": {"number": entry["temperature"]},
    }
    if entry["browser_url"]:
        properties["Browser URL"] = {"url": entry["browser_url"]}
    if participated:
        properties.update({
            "Activity": {"multi_select": multi_select(entry["activity"])},
            "Mood": {"multi_select": multi_select(entry["mood"])},
            "Energy": {"number": entry["energy"]},
            "Kindness Aligned": {"select": {"name": str(entry["kindness"])}},
            "Safety Aligned": {"select": {"name": str(entry["safety"])}},
        })
    if entry.get("screenshot_upload"):
        properties["Screenshot"] = {"files": [entry["screenshot_upload"]]}
    return request_json(
        "pages", {"parent": {"data_source_id": DATA_SOURCE_ID}, "properties": properties}
    )


def append_local(entry, path=LOCAL_LOG):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def make_context(timeout_seconds, state_file=STATE_FILE):
    app = active_app_name()
    return {
        "activeApp": app,
        "activeWindow": active_window_title(),
        "browserURL": browser_url(app),
        "timeoutSeconds": timeout_seconds,
        **load_last_values(state_file),
    }


def build_entry(context, popup_result, include_capture):
    now = datetime.now(timezone.utc)
    local_now = datetime.now().astimezone()
    interval_epoch = int(time.time() // (INTERVAL_MINUTES * 60))
    interval_key = f"{SESSION_ID}-{interval_epoch}"
    weather = weather_snapshot() if include_capture else {"temperature": None, "weather": "Dry run"}
    screenshot = take_screenshot(interval_key) if include_capture else ""
    return {
        "name": f"Mac popup audit {local_now.strftime('%Y-%m-%d %H:%M')}",
        "timestamp": now.isoformat(), "local_time": local_now.isoformat(),
        "interval_key": interval_key, "session_id": SESSION_ID,
        "device": f"{platform.node()} ({platform.machine()})",
        "location_label": LOCATION_LABEL, "latitude": LAT, "longitude": LON,
        "temperature": weather["temperature"], "weather": weather["weather"],
        "active_app": context["activeApp"], "active_window": context["activeWindow"],
        "browser_url": context["browserURL"], "screenshot_path": screenshot,
        **popup_result,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show the popup but never capture or transmit data")
    parser.add_argument("--timeout", type=int, default=120, help="Seconds before a missed check-in")
    parser.add_argument("--helper-app", type=Path, default=DEFAULT_HELPER_APP)
    parser.add_argument("--local-log", type=Path, default=LOCAL_LOG)
    parser.add_argument("--state-file", type=Path, default=STATE_FILE)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.timeout < 1:
        raise SystemExit("--timeout must be at least 1 second")
    context = make_context(args.timeout, args.state_file)
    popup_result = show_popup(args.helper_app, context, args.state_file)
    entry = build_entry(context, popup_result, include_capture=not args.dry_run)
    if args.dry_run:
        print(json.dumps({"mode": "dry-run", "entry": entry}, indent=2))
        return 0

    append_local(entry, args.local_log)
    try:
        if entry.get("screenshot_path"):
            entry["screenshot_upload"] = upload_file_to_notion(entry["screenshot_path"])
        result = create_notion_entry(entry)
    except Exception as exc:
        notify("Time Audit saved locally", "Notion logging failed; the local entry is safe.")
        print(f"Saved local entry: {args.local_log}")
        print(f"Notion sync failed: {exc}", file=sys.stderr)
        return 2
    notify("Time Audit logged", "Your popup check-in was added to Notion.")
    print(json.dumps({"notion_url": result.get("url"), "local_log": str(args.local_log)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
