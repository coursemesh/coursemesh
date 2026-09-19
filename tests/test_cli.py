import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from coursemesh.cli import main


class CliTests(unittest.TestCase):
    def test_sync_json_has_schema(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "demo.ics").write_text(
                "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:x\nSUMMARY:Demo\nEND:VEVENT\nEND:VCALENDAR\n"
            )
            cfg = root / "coursemesh.toml"
            cfg.write_text('''[[sources]]\nid="demo"\npath="demo.ics"\n''')
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(["--config", str(cfg), "sync", "--format", "json"])
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["sources"][0]["changes"][0]["kind"], "new")
            self.assertFalse(payload["sources"][0]["not_modified"])

    def test_status_json_distinguishes_attempt_and_success(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            feed = root / "demo.ics"
            feed.write_text(
                "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:x\nSUMMARY:Demo\nEND:VEVENT\nEND:VCALENDAR\n"
            )
            cfg = root / "coursemesh.toml"
            cfg.write_text('''[[sources]]\nid="demo"\npath="demo.ics"\n''')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--config", str(cfg), "sync"]), 0)
            feed.unlink()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--config", str(cfg), "sync"]), 1)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(["--config", str(cfg), "status", "--format", "json"])
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            source = payload["sources"][0]
            self.assertEqual(payload["schema_version"], 1)
            self.assertIsNotNone(source["last_success_at"])
            self.assertIsNotNone(source["last_attempt_at"])
            self.assertIn("FileNotFoundError", source["last_error"])
            self.assertEqual(source["event_count"], 1)


if __name__ == "__main__":
    unittest.main()
