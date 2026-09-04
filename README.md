# Time-Audit
This is a time audit repository so I can keep track of my self.
# Time Audit System

## Purpose

Collect objective and subjective data about how I spend my time so I can compare perception against reality.

## Current Features

- Native macOS popup with Activity, Mood, Energy, Kindness, Safety, and Notes
- Skip button and automatic missed check-in after two minutes
- Remembers the last-used selections
- Automatic Notion logging
- Automatic timestamp capture
- Automatic weather capture
- Automatic screenshot capture
- Active application tracking
- Active window tracking
- Browser URL tracking
- Participation tracking
- Manual mood/activity logging

## Notion Database

Properties:

- Name
- Timestamp
- Participated
- Activity
- Mood
- Energy
- Kindness Aligned
- Safety Aligned
- Notes
- Temperature
- Weather
- Location
- Screenshot
- Active App
- Active Window
- Browser URL
- Interval Key
- Device
- Raw Context

## Setup

Build and test the popup locally (the test does not capture or send data):

```bash
./script/build_and_run.sh
```

The Codex project Run action invokes that same command. The native app is built
at `dist/TimeAuditPopup.app` for the current Mac architecture.

The live collector is `src/time_audit_popup_collector.py`. Live mode captures a
screenshot and sends the screenshot, active app/window, browser URL, and form
fields to Notion, so it should only be scheduled after that upload behavior is
explicitly approved.

Load environment variables:

source ~/.time_audit/config.env

Run collector:

/usr/bin/python3 src/time_audit_popup_collector.py

To stage a local copy without scheduling it:

```bash
./script/install_popup_collector.sh --prepare
```

The `--activate` installer mode creates a 30-minute LaunchAgent. Because that
mode sends screenshots and work context to Notion, do not run it without the
user's explicit approval.

Once approved, configure the existing Time Audit data source and activate the
schedule with a hidden token prompt:

```bash
./script/configure_and_activate.sh
```

## Future Improvements

### Phase 2
- Popup audit form
- Automatic missed check-ins
- Notification scheduling

### Phase 3
- Menu bar countdown
- Streak tracking
- Daily completion percentage

### Phase 4
- iPhone shortcut integration
- Mobile check-ins
- Cross-device synchronization

## Repository Rules

- Commit after every working improvement.
- Never leave the project in a broken state.
- If something works, commit it before making another change.
