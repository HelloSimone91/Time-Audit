import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "time_audit_popup_collector.py"
SPEC = importlib.util.spec_from_file_location("popup_collector", MODULE_PATH)
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class PopupCollectorTests(unittest.TestCase):
    def test_load_last_values_uses_defaults_for_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            values = collector.load_last_values(Path(directory) / "missing.json")
        self.assertEqual(values["activity"], "Work")
        self.assertEqual(values["mood"], ["Neutral"])
        self.assertEqual(values["activityOptions"], [])
        self.assertEqual(values["moodOptions"], [])
        self.assertEqual(values["energy"], 3)

    def test_save_and_reload_last_values(self):
        result = {
            "activity": "Learning", "mood": ["Focused", "Hopeful"], "energy": 4,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            collector.save_last_values(result, path)
            saved = collector.load_last_values(path)
            self.assertEqual(saved["activity"], "Learning")
            self.assertEqual(saved["mood"], ["Focused", "Hopeful"])
            self.assertEqual(saved["activityOptions"], [])
            self.assertEqual(saved["moodOptions"], [])

    def test_write_in_activity_is_saved_for_future_popups(self):
        result = {
            "activity": "Community Garden", "mood": ["Connected"], "energy": 4,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            collector.save_last_values(result, path)
            self.assertEqual(
                collector.load_last_values(path)["activityOptions"],
                ["Community Garden"],
            )

    def test_legacy_single_mood_is_migrated_to_multi_select(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(json.dumps({"mood": "Content"}))
            self.assertEqual(collector.load_last_values(path)["mood"], ["Content"])

    def test_write_in_feelings_are_saved_for_future_popups(self):
        result = {
            "activity": "Learning",
            "mood": ["Calm", "Chill", "chill", "Reflective"],
            "energy": 3,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            collector.save_last_values(result, path)
            self.assertEqual(
                collector.load_last_values(path)["moodOptions"],
                ["Chill", "Reflective"],
            )

    def test_multi_select_accepts_one_or_many_values(self):
        self.assertEqual(collector.multi_select("Calm"), [{"name": "Calm"}])
        self.assertEqual(
            collector.multi_select(["Calm", "Hopeful"]),
            [{"name": "Calm"}, {"name": "Hopeful"}],
        )

    def test_append_local_writes_json_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "entries.jsonl"
            collector.append_local({"outcome": "skipped"}, path)
            self.assertEqual(json.loads(path.read_text()), {"outcome": "skipped"})

    def test_dry_run_flag_is_explicit(self):
        args = collector.parse_args(["--dry-run", "--timeout", "8"])
        self.assertTrue(args.dry_run)
        self.assertEqual(args.timeout, 8)

    def test_alignment_options_match_the_live_notion_schema(self):
        self.assertEqual(collector.alignment_option("kindness", 1), "1 Totally fucking up")
        self.assertEqual(collector.alignment_option("kindness", 5), "5 Kind to self and surroundings")
        self.assertEqual(collector.alignment_option("safety", 5), "5 Safe to self and surroundings")
        self.assertEqual(collector.alignment_option("safety", 3), "3")

    def test_dry_run_context_disables_screenshot_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            context = collector.make_context(
                8, Path(directory) / "state.json", capture_screenshot=False
            )
        self.assertFalse(context["captureScreenshot"])
        self.assertEqual(context["screenshotPath"], "")

    def test_prune_old_screenshots_removes_only_expired_pngs(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            old_png = directory / "old.png"
            recent_png = directory / "recent.png"
            old_note = directory / "old.txt"
            for path in (old_png, recent_png, old_note):
                path.write_text("test")
            old_time = now - 15 * 24 * 60 * 60
            os.utime(old_png, (old_time, old_time))
            os.utime(old_note, (old_time, old_time))

            removed = collector.prune_old_screenshots(directory, 14, now=now)

            self.assertEqual(removed, 1)
            self.assertFalse(old_png.exists())
            self.assertTrue(recent_png.exists())
            self.assertTrue(old_note.exists())


if __name__ == "__main__":
    unittest.main()
