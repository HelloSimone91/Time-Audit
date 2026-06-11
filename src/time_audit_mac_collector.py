
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
STATE_FILE = os.path.expanduser("~/.time_audit/last_values.json")

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
    try:
        result = subprocess.run(
            ["lsappinfo", "front"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        out = result.stdout.strip()

        if out:
            name_result = subprocess.run(
                ["lsappinfo", "info", "-only", "name", out],
                capture_output=True,
                text=True,
                timeout=5,
            )
            name = name_result.stdout.strip()

            if "=" in name:
                return name.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass

    script = """
    tell application "System Events"
        set frontApp to first application process whose frontmost is true
        return name of frontApp
    end tell
    """
    return run_osascript(script)


def get_active_window_title() -> str:
    app = get_active_app()
    if not app:
        return "Unknown"

    # Generic System Events method works better than browser-specific tab titles.
    script = f"""
    tell application "System Events"
        try
            tell process "{app}"
                return name of front window
            end tell
        on error
            return "Unknown"
        end try
    end tell
    """
    return run_osascript(script) or "Unknown"


def get_browser_url(active_app: str) -> str:
    if active_app in ["Google Chrome", "Chromium", "ChatGPT Atlas"]:
        return run_osascript(f'tell application "{active_app}" to get URL of active tab of front window')
    if active_app == "Safari":
        return run_osascript('tell application "Safari" to get URL of front document')
    return ""


def take_screenshot() -> Optional[str]:
    try:
        path = os.path.expanduser(
    f"~/Desktop/time_audit_{int(time.time())}.png"
)
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


def load_last_values() -> Dict[str, Any]:
    defaults = {
        "activity": "Work",
        "mood": "Neutral",
        "energy": 3,
        "kindness": "3",
        "safety": "3",
    }
    try:
        with open(STATE_FILE, "r") as f:
            saved = json.load(f)
        defaults.update(saved)
    except Exception:
        pass
    return defaults


def save_last_values(data: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump({
                "activity": data.get("activity", "Work"),
                "mood": data.get("mood", "Neutral"),
                "energy": data.get("energy", 3),
                "kindness": data.get("kindness", "3"),
                "safety": data.get("safety", "3"),
            }, f, indent=2)
    except Exception as e:
        print(f"Could not save last values: {e}", file=sys.stderr)


def make_searchable_combo(parent, variable, values):
    combo = ttk.Combobox(parent, textvariable=variable, values=values)
    combo._all_values = list(values)

    def filter_values(event=None):
        # Do not hijack navigation/control keys.
        if event and event.keysym in {
            "Up", "Down", "Left", "Right", "Return", "Escape", "Tab",
            "Shift_L", "Shift_R", "Control_L", "Control_R", "Command"
        }:
            return

        typed = variable.get().strip().lower()

        if typed:
            filtered = [v for v in combo._all_values if typed in v.lower()]
        else:
            filtered = combo._all_values

        combo["values"] = filtered if filtered else combo._all_values

    def accept_first_match(event=None):
        typed = variable.get().strip().lower()
        matches = [v for v in combo._all_values if typed in v.lower()]

        if matches:
            variable.set(matches[0])
            combo.icursor("end")
            return "break"

        return None

    def restore_options(event=None):
        combo["values"] = combo._all_values

    combo.bind("<KeyRelease>", filter_values)
    combo.bind("<Return>", accept_first_match)
    combo.bind("<FocusIn>", restore_options)
    combo.bind("<Button-1>", restore_options)

    return combo


def popup_form(active_app: str, active_window: str) -> Optional[Dict[str, Any]]:
    last = load_last_values()
    result: Dict[str, Any] = {"submitted": False, "data": None}

    root = tk.Tk()
    root.title("Time Audit")
    root.geometry("500x590")
    root.attributes("-topmost", True)

    

    root.columnconfigure(0, weight=1)

    ttk.Label(root, text="Time Audit Check-In", font=("Arial", 18, "bold")).grid(
        row=0, column=0, padx=18, pady=(18, 8), sticky="w"
    )

    ttk.Label(
        root,
        text=f"Active App: {active_app or 'Unknown'}\nActive Window: {active_window or 'Unknown'}",
        wraplength=440,
    ).grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")

    frame = ttk.Frame(root)
    frame.grid(row=2, column=0, padx=18, pady=4, sticky="ew")
    frame.columnconfigure(1, weight=1)

    activity_var = tk.StringVar(value=last.get("activity", "Work"))
    mood_var = tk.StringVar(value=last.get("mood", "Neutral"))
    energy_var = tk.StringVar(value=str(last.get("energy", 3)))
    kindness_var = tk.StringVar(value=str(last.get("kindness", "3")))
    safety_var = tk.StringVar(value=str(last.get("safety", "3")))

    widgets = [
        ("Activity", make_searchable_combo(frame, activity_var, ACTIVITIES)),
        ("Mood", make_searchable_combo(frame, mood_var, MOODS)),
    ]

    for i, (label, widget) in enumerate(widgets):
        ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", pady=8)
        widget.grid(row=i, column=1, sticky="ew", pady=8)

    def add_slider(row: int, label: str, variable: tk.StringVar) -> None:
        slider_frame = ttk.Frame(frame)
        slider_frame.grid(row=row, column=1, sticky="ew", pady=8)
        slider_frame.columnconfigure(0, weight=1)

        value_label = ttk.Label(slider_frame, text=variable.get(), width=3)
        value_label.grid(row=0, column=1, padx=(10, 0))

        def update_value(value: str) -> None:
            rounded = str(int(float(value)))
            variable.set(rounded)
            value_label.config(text=rounded)

        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=8)

        scale = ttk.Scale(
            slider_frame,
            from_=1,
            to=5,
            orient="horizontal",
            command=update_value,
        )
        scale.set(int(variable.get()))
        scale.grid(row=0, column=0, sticky="ew")

    add_slider(2, "Energy", energy_var)
    add_slider(3, "Kindness Aligned", kindness_var)
    add_slider(4, "Safety Aligned", safety_var)

    ttk.Label(root, text="Notes").grid(row=3, column=0, padx=18, pady=(12, 4), sticky="w")

    notes_box = tk.Text(root, height=7, wrap="word")
    notes_box.grid(row=4, column=0, padx=18, pady=(0, 12), sticky="nsew")

    countdown_var = tk.StringVar(value="Auto-log as missed in 120 seconds")
    ttk.Label(root, textvariable=countdown_var).grid(row=5, column=0, padx=18, pady=(0, 4), sticky="w")

    progress = ttk.Progressbar(root, orient="horizontal", mode="determinate", maximum=120, value=120)
    progress.grid(row=6, column=0, padx=18, pady=(0, 12), sticky="ew")

    def submit() -> None:
        data = {
            "activity": activity_var.get().strip() or "Other",
            "mood": mood_var.get().strip() or "Neutral",
            "energy": int(energy_var.get()),
            "kindness": kindness_var.get(),
            "safety": safety_var.get(),
            "notes": notes_box.get("1.0", "end").strip(),
        }
        save_last_values(data)
        result["submitted"] = True
        result["data"] = data
        root.destroy()

    def skip() -> None:
        result["submitted"] = False
        result["data"] = None
        root.destroy()

    button_frame = ttk.Frame(root)
    button_frame.grid(row=7, column=0, padx=18, pady=(0, 18), sticky="e")

    ttk.Button(button_frame, text="Skip", command=skip).grid(row=0, column=0, padx=6)
    ttk.Button(button_frame, text="Submit", command=submit).grid(row=0, column=1, padx=6)

    deadline = time.time() + 120

    def tick() -> None:
        remaining = max(0, int(deadline - time.time()))
        countdown_var.set(f"Auto-log as missed in {remaining} seconds")
        progress["value"] = remaining

        if remaining <= 0:
            skip()
        else:
            root.after(1000, tick)

    root.after(1000, tick)
    root.mainloop()

    return result["data"] if result["submitted"] else None


def parse_multi_select_input(value: str):
    parts = [
        part.strip()
        for part in value.replace(";", ",").replace("+", ",").split(",")
        if part.strip()
    ]

    clean_parts = []
    seen = set()

    for part in parts:
        # Notion multi-select option names cannot contain commas.
        safe = part.replace(",", " ").strip()

        if safe and safe.lower() not in seen:
            clean_parts.append({"name": safe})
            seen.add(safe.lower())

    return clean_parts


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
        props["Activity"] = {"multi_select": parse_multi_select_input(form_data["activity"])}
        props["Mood"] = {"multi_select": parse_multi_select_input(form_data["mood"])}
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
