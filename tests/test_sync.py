from pathlib import Path
import tempfile
import unittest

from coursemesh.config import load_config
from coursemesh.sync import sync_all


ICS_A = """BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:1\nSUMMARY:Math lecture\nDTSTART:20260920T100000Z\nEND:VEVENT\nEND:VCALENDAR\n"""
ICS_B = """BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:1\nSUMMARY:Math lecture moved\nDTSTART:20260920T110000Z\nEND:VEVENT\nEND:VCALENDAR\n"""


class SyncTests(unittest.TestCase):
    def test_local_sync_and_change_detection(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "demo.ics").write_text(ICS_A)
            (root / "coursemesh.toml").write_text('''[coursemesh]\noutput_calendar="out.ics"\n[[sources]]\nid="demo"\nname="Demo"\npath="demo.ics"\n''')
            cfg = load_config(root / "coursemesh.toml")
            first = sync_all(cfg, root)
            self.assertFalse(first.failed)
            self.assertEqual(first.sources[0].changes[0].kind, "new")
            self.assertTrue((root / "out.ics").exists())

            (root / "demo.ics").write_text(ICS_B)
            second = sync_all(cfg, root)
            self.assertEqual(second.sources[0].changes[0].kind, "changed")

    def test_broken_source_returns_failure_but_writes_calendar(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "coursemesh.toml").write_text('''[coursemesh]\noutput_calendar="out.ics"\n[[sources]]\nid="broken"\npath="missing.ics"\n''')
            cfg = load_config(root / "coursemesh.toml")
            result = sync_all(cfg, root)
            self.assertTrue(result.failed)
            self.assertTrue((root / "out.ics").exists())


if __name__ == "__main__":
    unittest.main()

class RedactionTests(unittest.TestCase):
    def test_url_is_redacted_from_sync_error(self):
        from coursemesh.config import SourceConfig
        from coursemesh.sync import _safe_error

        secret = "https://example.invalid/calendar?token=supersecret"
        source = SourceConfig(id="x", name="X", kind="ics", url=secret)
        message = _safe_error(source, RuntimeError(f"failed while fetching {secret}"))
        self.assertNotIn("supersecret", message)
        self.assertIn("<redacted-calendar-url>", message)
