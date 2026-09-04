import importlib.util
import json
import tempfile
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
        self.assertEqual(values["mood"], "Neutral")
        self.assertEqual(values["energy"], 3)

    def test_save_and_reload_last_values(self):
        result = {
            "activity": "Learning", "mood": "Focused", "energy": 4,
            "kindness": 5, "safety": 2,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            collector.save_last_values(result, path)
            self.assertEqual(collector.load_last_values(path), result)

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


if __name__ == "__main__":
    unittest.main()
