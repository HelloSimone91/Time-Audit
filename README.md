# Time-Audit
This is a time audit repository so I can keep track of my self.
# Time Audit System

## Purpose

Collect objective and subjective data about how I spend my time so I can compare perception against reality.

## Current Features

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

Load environment variables:

source ~/.time_audit/config.env

Run collector:

~/.time_audit/.venv/bin/python ~/.time_audit/time_audit_mac_collector.py

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
