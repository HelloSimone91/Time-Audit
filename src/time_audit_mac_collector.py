
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, Optional, Tuple

import requests
import tkinter as tk
from tkinter import ttk

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DATA_SOURCE_ID = os.environ["NOTION_DATA_SOURCE_ID"]
NOTION_VERSION = os.environ.get("NOTION_VERSION", "2026-03-11")

TIME_AUDIT_LOCATION_LABEL = os.environ.get("TIME_AUDIT_LOCATION_LABEL", "Austin, TX")
TIME_AUDIT_LAT = os.environ.get("TIME_AUDIT_LAT", "30.2672")
TIME_AUDIT_LON = os.environ.get("TIME_AUDIT_LON", "-97.7431")
TIME_AUDIT_SESSION_ID = os.environ.get("TIME_AUDIT_SESSION_ID", "time-audit-v2")

ACTIVITIES = [
    "Work",
    "Admin / Logistics",
    "Learning",
    "Social",
    "Entertainment",
    "Health",
    "Eating",
    "Travel / Errands",
    "Household",
    "Dogs",
    "Scrolling",
    "Rest",
    "Other",
]

MOODS = [
    "Energized",
    "Focused",
    "Content",
    "Neutral",
    "Tired",
    "Stressed",
    "Anxious",
    "Frustrated",
    "Other",
]


def notion_headers(json_content: bool = True) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
    }
    if json_content:
        headers["Content-Type"] = "application/json"
    return headers


def prop_rich(value: Optional[str]) -> Dict[str, Any]:
    return {"rich_text": [{"text": {"content": value or ""}}]}


def interval_key(now: dt.datetime) -> str:
    rounded_minute = 0 if now.minute < 30 else 30
    rounded = now.replace(minute=rounded_minute, second=0, microsecond=0)
    return rounded.strftime("%Y-%m-%d-%H%M")


def get_weather() -> Tuple[Optional[float], str]:
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={TIME_AUDIT_LAT}&longitude={TIME_AUDIT_LON}"
            "&current=temperature_2m,weather_code"
            "&temperature_unit=fahrenheit"
            "&timezone=auto"
        )
        data = requests.get(url, timeout=15).json()
        current = data.get("current", {})
        temp = current.get("temperature_2m")
        code = current.get("weather_code")
        weather = f"Weather code {code}" if code is not None else ""
        return temp, weather
    except Exception:
        return None, ""


def run_osascript(script: str) -> str:
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_active_app() -> str:
    return run_osascript(
        'tell application "System Events" to get name of first application process whose frontmost is true'
    )


def get_active_window_title() -> str:
    return run_osascript(
        'tell application "System Events" to get name of front window of first application process whose frontmost is true'
    )


def get_browser_url(active_app: str) -> str:
    if active_app in ["Google Chrome", "Chromium", "ChatGPT Atlas"]:
        return run_osascript(f'tell application "{active_app}" to get URL of active tab of front window')
    if active_app == "Safari":
        return run_osascript('tell application "Safari" to get URL of front document')
    return ""


def take_screenshot() -> Optional[str]:
    try:
        path = os.path.join(tempfile.gettempdir(), f"time_audit_{int(time.time())}.png")
        subprocess.run(["screencapture", "-x", path], check=True, timeout=10)
        return path
    except Exception as e:
        print(f"Screenshot failed: {e}", file=sys.stderr)
        return None


def upload_screenshot(path: str) -> Optional[str]:
    try:
        r = requests.post(
            "https://api.notion.com/v1/file_uploads",
            headers=notion_headers(),
            json={},
            timeout=20,
        )
        if r.status_code >= 400:
            print(json.dumps(r.json(), indent=2), file=sys.stderr)
        r.raise_for_status()

        upload = r.json()
        upload_id = upload["id"]
        upload_url = upload["upload_url"]

        with open(path, "rb") as f:
            files = {"file": (os.path.basename(path), f, "image/png")}
            r2 = requests.post(
                upload_url,
                headers=notion_headers(json_content=False),
                files=files,
                timeout=60,
            )
            if r2.status_code >= 400:
                print(r2.text, file=sys.stderr)
            r2.raise_for_status()

        return upload_id
    except Exception as e:
        print(f"Screenshot upload failed: {e}", file=sys.stderr)
        return None


def notify() -> None:
    subprocess.run([
        "osascript",
        "-e",
        'display notification "Log your current activity." with title "Time Audit"',
    ])


def popup_form(active_app: str, active_window: str) -> Optional[Dict[str, Any]]:
    result: Dict[str, Any] = {"submitted": False, "data": None}

    root = tk.Tk()
    root.title("Time Audit")
    root.geometry("470x560")
    root.attributes("-topmost", True)

    root.columnconfigure(0, weight=1)

    ttk.Label(root, text="Time Audit Check-In", font=("Arial", 18, "bold")).grid(
        row=0, column=0, padx=18, pady=(18, 8), sticky="w"
    )

    ttk.Label(
        root,
        text=f"Active App: {active_app or 'Unknown'}\nActive Window: {active_window or 'Unknown'}",
        wraplength=420,
    ).grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")

    frame = ttk.Frame(root)
    frame.grid(row=2, column=0, padx=18, pady=4, sticky="ew")
    frame.columnconfigure(1, weight=1)

    activity_var = tk.StringVar(value="Work")
    other_activity_var = tk.StringVar()
    mood_var = tk.StringVar(value="Neutral")
    other_mood_var = tk.StringVar()
    energy_var = tk.StringVar(value="3")
    kindness_var = tk.StringVar(value="3")
    safety_var = tk.StringVar(value="3")

    fields = [
        ("Activity", ttk.Combobox(frame, textvariable=activity_var, values=ACTIVITIES, state="readonly")),
        ("Other Activity", ttk.Entry(frame, textvariable=other_activity_var)),
        ("Mood", ttk.Combobox(frame, textvariable=mood_var, values=MOODS, state="readonly")),
        ("Other Mood", ttk.Entry(frame, textvariable=other_mood_var)),
        ("Energy", ttk.Combobox(frame, textvariable=energy_var, values=["1", "2", "3", "4", "5"], state="readonly")),
        ("Kindness Aligned", ttk.Combobox(frame, textvariable=kindness_var, values=["1", "2", "3", "4", "5"], state="readonly")),
        ("Safety Aligned", ttk.Combobox(frame, textvariable=safety_var, values=["1", "2", "3", "4", "5"], state="readonly")),
    ]

    for i, (label, widget) in enumerate(fields):
        ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", pady=6)
        widget.grid(row=i, column=1, sticky="ew", pady=6)

    ttk.Label(root, text="Notes").grid(row=3, column=0, padx=18, pady=(12, 4), sticky="w")

    notes_box = tk.Text(root, height=5, wrap="word")
    notes_box.grid(row=4, column=0, padx=18, pady=(0, 12), sticky="nsew")

    countdown_var = tk.StringVar(value="Auto-log as missed in 120 seconds")
    ttk.Label(root, textvariable=countdown_var).grid(row=5, column=0, padx=18, pady=(0, 8), sticky="w")

    def submit() -> None:
        activity = activity_var.get()
        mood = mood_var.get()

        if activity == "Other" and other_activity_var.get().strip():
            activity = other_activity_var.get().strip()

        if mood == "Other" and other_mood_var.get().strip():
            mood = other_mood_var.get().strip()

        result["submitted"] = True
        result["data"] = {
            "activity": activity,
            "mood": mood,
            "energy": int(energy_var.get()),
            "kindness": kindness_var.get(),
            "safety": safety_var.get(),
            "notes": notes_box.get("1.0", "end").strip(),
        }
        root.destroy()

    def skip() -> None:
        result["submitted"] = False
        result["data"] = None
        root.destroy()

    button_frame = ttk.Frame(root)
    button_frame.grid(row=6, column=0, padx=18, pady=(0, 18), sticky="e")

    ttk.Button(button_frame, text="Skip", command=skip).grid(row=0, column=0, padx=6)
    ttk.Button(button_frame, text="Submit", command=submit).grid(row=0, column=1, padx=6)

    deadline = time.time() + 120

    def tick() -> None:
        remaining = max(0, int(deadline - time.time()))
        countdown_var.set(f"Auto-log as missed in {remaining} seconds")
        if remaining <= 0:
            skip()
        else:
            root.after(1000, tick)

    root.after(1000, tick)
    root.mainloop()

    return result["data"] if result["submitted"] else None


def create_notion_page(
    now: dt.datetime,
    screenshot_upload_id: Optional[str],
    form_data: Optional[Dict[str, Any]],
    active_app: str,
    active_window: str,
    browser_url: str,
) -> None:
    temp, weather = get_weather()
    device = os.uname().nodename
    key = interval_key(now)
    participated = form_data is not None

    raw_context = "\n".join([
        "Entry Type: Mac Popup Audit",
        f"Session ID: {TIME_AUDIT_SESSION_ID}",
        f"Interval Key: {key}",
        f"Device: {device}",
        f"Location Label: {TIME_AUDIT_LOCATION_LABEL}",
        f"Latitude: {TIME_AUDIT_LAT}",
        f"Longitude: {TIME_AUDIT_LON}",
        f"Active App: {active_app}",
        f"Active Window: {active_window}",
        f"Browser URL: {browser_url}" if browser_url else "Browser URL:",
    ])

    props: Dict[str, Any] = {
        "Name": {"title": [{"text": {"content": f"Audit {now.strftime('%Y-%m-%d %H:%M')}"}}]},
        "Timestamp": {"date": {"start": now.isoformat()}},
        "Participated": {"checkbox": participated},
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

    if form_data:
        props["Activity"] = {"multi_select": [{"name": form_data["activity"]}]}
        props["Mood"] = {"multi_select": [{"name": form_data["mood"]}]}
        props["Energy"] = {"number": form_data["energy"]}
        props["Kindness Aligned"] = {"select": {"name": form_data["kindness"]}}
        props["Safety Aligned"] = {"select": {"name": form_data["safety"]}}
        props["Notes"] = prop_rich(form_data["notes"])

    if screenshot_upload_id:
        props["Screenshot"] = {
            "files": [{"type": "file_upload", "file_upload": {"id": screenshot_upload_id}}]
        }

    payload = {"parent": {"data_source_id": NOTION_DATA_SOURCE_ID}, "properties": props}

    r = requests.post("https://api.notion.com/v1/pages", headers=notion_headers(), json=payload)
    if r.status_code >= 400:
        print(json.dumps(r.json(), indent=2), file=sys.stderr)
    r.raise_for_status()


def main() -> None:
    now = dt.datetime.now().astimezone()

    active_app = get_active_app()
    active_window = get_active_window_title()
    browser_url = get_browser_url(active_app)

    notify()

    screenshot_path = take_screenshot()
    upload_id = upload_screenshot(screenshot_path) if screenshot_path else None

    form_data = popup_form(active_app, active_window)

    create_notion_page(
        now=now,
        screenshot_upload_id=upload_id,
        form_data=form_data,
        active_app=active_app,
        active_window=active_window,
        browser_url=browser_url,
    )

    print("Logged time audit entry.")


if __name__ == "__main__":
    main()