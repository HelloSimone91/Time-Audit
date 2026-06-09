#!/usr/bin/env python3
"""
Mac Time Audit Collector
Runs one snapshot and writes it to Notion.
Designed to be called every 30 minutes by macOS LaunchAgent.
"""

from __future__ import annotations

import datetime as dt
import json
import mimetypes
import os
import pathlib
import subprocess
import sys
import time
from typing import Any, Dict, Optional, Tuple

import requests

NOTION_VERSION = os.environ.get("NOTION_VERSION", "2026-03-11")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "").strip()
NOTION_DATA_SOURCE_ID = os.environ.get("NOTION_DATA_SOURCE_ID", "").strip() or os.environ.get("NOTION_DATABASE_ID", "").strip()
TIME_AUDIT_LOCATION_LABEL = os.environ.get("TIME_AUDIT_LOCATION_LABEL", "Austin, TX")
TIME_AUDIT_LAT = os.environ.get("TIME_AUDIT_LAT", "30.2672")
TIME_AUDIT_LON = os.environ.get("TIME_AUDIT_LON", "-97.7431")
TIME_AUDIT_SESSION_ID = os.environ.get("TIME_AUDIT_SESSION_ID", dt.date.today().isoformat())
SCREENSHOT_DIR = pathlib.Path(os.environ.get("TIME_AUDIT_SCREENSHOT_DIR", str(pathlib.Path.home() / "TimeAuditScreenshots")))

WEATHER_CODES = {
    0: "Clear sky", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    56: "Freezing drizzle", 57: "Dense freezing drizzle", 61: "Light rain", 63: "Rain",
    65: "Heavy rain", 66: "Freezing rain", 67: "Heavy freezing rain", 71: "Light snow",
    73: "Snow", 75: "Heavy snow", 77: "Snow grains", 80: "Light rain showers",
    81: "Rain showers", 82: "Heavy rain showers", 85: "Light snow showers",
    86: "Snow showers", 95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Heavy thunderstorm with hail",
}


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def notion_headers(content_type: Optional[str] = "application/json") -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def osascript(script: str) -> str:
    return run(["osascript", "-e", script])


def get_active_app() -> str:
    return osascript('tell application "System Events" to get name of first application process whose frontmost is true') or "Unknown"


def get_active_window_title() -> str:
    script = '''
    tell application "System Events"
      set frontApp to name of first application process whose frontmost is true
      try
        tell process frontApp to get name of front window
      on error
        return ""
      end try
    end tell
    '''
    return osascript(script) or ""


def get_browser_url(active_app: str) -> str:
    if active_app in {"Google Chrome", "Chrome", "Chromium", "Microsoft Edge", "Brave Browser"}:
        app = active_app
        script = f'tell application "{app}" to get URL of active tab of front window'
        return osascript(script)
    if active_app == "Safari":
        return osascript('tell application "Safari" to get URL of current tab of front window')
    return ""


def take_screenshot(now: dt.datetime) -> Optional[pathlib.Path]:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"time_audit_{now.strftime('%Y%m%d_%H%M%S')}.png"
    try:
        subprocess.check_call(["screencapture", "-x", str(path)], stderr=subprocess.DEVNULL)
        return path if path.exists() else None
    except Exception:
        return None


def get_weather() -> Tuple[Optional[float], str]:
    try:
        lat = float(TIME_AUDIT_LAT)
        lon = float(TIME_AUDIT_LON)
    except ValueError:
        return None, ""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,weather_code"
        "&temperature_unit=fahrenheit"
        "&timezone=auto"
    )
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        current = r.json().get("current", {})
        temp = current.get("temperature_2m")
        code = current.get("weather_code")
        desc = WEATHER_CODES.get(code, f"Weather code {code}" if code is not None else "")
        return temp, desc
    except Exception:
        return None, ""


def create_file_upload() -> Tuple[str, str]:
    r = requests.post("https://api.notion.com/v1/file_uploads", headers=notion_headers(), json={})
    r.raise_for_status()
    data = r.json()
    return data["id"], data["upload_url"]


def upload_file(upload_url: str, path: pathlib.Path) -> None:
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    with path.open("rb") as fh:
        files = {"file": (path.name, fh, mime)}
        r = requests.post(upload_url, headers=notion_headers(content_type=None), files=files)
        r.raise_for_status()


def prop_rich(text: str) -> Dict[str, Any]:
    return {"rich_text": [{"text": {"content": text[:2000]}}]} if text else {"rich_text": []}


def prop_select(name: str) -> Dict[str, Any]:
    return {"select": {"name": name}}


def interval_key(now: dt.datetime) -> str:
    # Round down to current 30-minute block for easy joining with iPhone check-ins.
    minute = 0 if now.minute < 30 else 30
    floored = now.replace(minute=minute, second=0, microsecond=0)
    return floored.strftime("%Y-%m-%d %H:%M")


def create_notion_page(now: dt.datetime, screenshot_upload_id: Optional[str]) -> None:
    temp, weather = get_weather()
    active_app = get_active_app()
    active_window = get_active_window_title()
    browser_url = get_browser_url(active_app)
    device = os.uname().nodename
    key = interval_key(now)

    raw_context = "\n".join([
        f"Entry Type: Mac Snapshot",
        f"Session ID: {TIME_AUDIT_SESSION_ID}",
        f"Interval Key: {key}",
        f"Device: {device}",
        f"Location: {TIME_AUDIT_LOCATION_LABEL}",
        f"Active App: {active_app}",
        f"Active Window: {active_window}",
        f"Browser URL: {browser_url}" if browser_url else "Browser URL:",
    ])

    props: Dict[str, Any] = {
        "Name": {"title": [{"text": {"content": f"Mac Snapshot {now.strftime('%Y-%m-%d %H:%M')}"}}]},
        "Timestamp": {"date": {"start": now.isoformat()}},
        "Response Status": {"checkbox": False},
        "Weather": prop_rich(weather),
        "Raw Context": prop_rich(raw_context),
        "Active App": prop_rich(active_app),
        "Active Window": prop_rich(active_window),
        "Interval Key": prop_rich(key),
        "Device": prop_rich(device),
    }

    if browser_url:
        props["Browser URL"] = {"url": browser_url}

    if temp is not None:
        props["Temperature"] = {"number": float(temp)}

    if screenshot_upload_id:
        props["Screenshot"] = {"files": [{"type": "file_upload", "file_upload": {"id": screenshot_upload_id}}]}

    payload = {"parent": {"data_source_id": NOTION_DATA_SOURCE_ID}, "properties": props}
    r = requests.post("https://api.notion.com/v1/pages", headers=notion_headers(), json=payload)
    if r.status_code >= 400:
        print(json.dumps(r.json(), indent=2), file=sys.stderr)
    r.raise_for_status()


def main() -> None:
    if not NOTION_TOKEN:
        die("NOTION_TOKEN is missing. Add it to ~/.time_audit/config.env")
    if not NOTION_DATA_SOURCE_ID:
        die("NOTION_DATA_SOURCE_ID is missing. Add it to ~/.time_audit/config.env")

    now = dt.datetime.now().astimezone()
    screenshot = take_screenshot(now)
    upload_id = None
    if screenshot:
        try:
            upload_id, upload_url = create_file_upload()
            upload_file(upload_url, screenshot)
        except Exception as exc:
            print(f"Screenshot upload failed: {exc}", file=sys.stderr)
            upload_id = None
    create_notion_page(now, upload_id)
    print(f"Logged Mac snapshot: {now.isoformat()}")


if __name__ == "__main__":
    main()
