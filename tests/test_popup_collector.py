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


if __name__ == "__main__":
    unittest.main()
