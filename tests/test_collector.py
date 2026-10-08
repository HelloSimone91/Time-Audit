"""Unit tests for the Mac Time Audit collector."""
import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import time_audit_mac_collector_pre_popup as collector


class TestRun(unittest.TestCase):
    def test_returns_stripped_stdout(self):
        with mock.patch.object(
            collector.subprocess, "check_output", return_value="  hello\n"
        ) as check_output:
            self.assertEqual(collector.run(["echo", "hello"]), "hello")
            check_output.assert_called_once_with(
                ["echo", "hello"], text=True, stderr=subprocess.DEVNULL
            )

    def test_returns_empty_string_on_failure(self):
        with mock.patch.object(
            collector.subprocess,
            "check_output",
            side_effect=subprocess.CalledProcessError(1, ["false"]),
        ):
            self.assertEqual(collector.run(["false"]), "")

    def test_returns_empty_string_on_missing_binary(self):
        with mock.patch.object(
            collector.subprocess, "check_output", side_effect=FileNotFoundError()
        ):
            self.assertEqual(collector.run(["nope-not-a-binary"]), "")


class TestApplescriptEscape(unittest.TestCase):
    def test_plain_string_unchanged(self):
        self.assertEqual(collector.applescript_escape("Google Chrome"), "Google Chrome")

    def test_escapes_double_quotes(self):
        self.assertEqual(
            collector.applescript_escape('Evil" App'), 'Evil\\" App'
        )

    def test_escapes_backslashes_first(self):
        self.assertEqual(
            collector.applescript_escape('back\\slash"quote'), 'back\\\\slash\\"quote'
        )


class TestGetBrowserUrl(unittest.TestCase):
    def test_unknown_app_skips_osascript(self):
        with mock.patch.object(collector, "osascript", return_value="") as osascript:
            self.assertEqual(collector.get_browser_url("Some Random App"), "")
            osascript.assert_not_called()

    def test_known_browser_uses_escaped_name(self):
        with mock.patch.object(
            collector, "osascript", return_value="https://example.com"
        ) as osascript:
            url = collector.get_browser_url("Google Chrome")
            self.assertEqual(url, "https://example.com")
            sent_script = osascript.call_args[0][0]
            self.assertIn('tell application "Google Chrome"', sent_script)


if __name__ == "__main__":
    unittest.main()
