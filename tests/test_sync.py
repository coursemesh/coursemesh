from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coursemesh.config import AppConfig, SourceConfig, load_config
from coursemesh.fetch import FetchResult
from coursemesh.models import HttpCacheState
from coursemesh.sync import _safe_error, sync_all


ICS_A = """BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:1\nSUMMARY:Math lecture\nDTSTART:20260920T100000Z\nEND:VEVENT\nEND:VCALENDAR\n"""
ICS_B = """BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:1\nSUMMARY:Math lecture moved\nDTSTART:20260920T110000Z\nEND:VEVENT\nEND:VCALENDAR\n"""

ICS_TZ = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VTIMEZONE
TZID:Europe/Berlin
BEGIN:STANDARD
DTSTART:20261025T030000
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:2
SUMMARY:Local lecture
DTSTART;TZID=Europe/Berlin:20261102T100000
END:VEVENT
END:VCALENDAR
"""


class SyncTests(unittest.TestCase):
    def test_local_sync_and_change_detection(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "demo.ics").write_text(ICS_A)
            (root / "coursemesh.toml").write_text(
                '''[coursemesh]\noutput_calendar="out.ics"\n[[sources]]\nid="demo"\nname="Demo"\npath="demo.ics"\n'''
            )
            cfg = load_config(root / "coursemesh.toml")
            first = sync_all(cfg)
            self.assertFalse(first.failed)
            self.assertEqual(first.sources[0].changes[0].kind, "new")
            self.assertTrue((root / "out.ics").exists())

            (root / "demo.ics").write_text(ICS_B)
            second = sync_all(cfg)
            self.assertEqual(second.sources[0].changes[0].kind, "changed")

    def test_vtimezone_survives_provider_failure_with_last_known_good_events(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "demo.ics"
            source.write_text(ICS_TZ)
            (root / "coursemesh.toml").write_text(
                '[coursemesh]\noutput_calendar="out.ics"\n[[sources]]\nid="demo"\nname="Demo"\npath="demo.ics"\n'
            )
            cfg = load_config(root / "coursemesh.toml")
            first = sync_all(cfg)
            self.assertFalse(first.failed)
            self.assertIn("BEGIN:VTIMEZONE", (root / "out.ics").read_text())

            source.unlink()
            second = sync_all(cfg)
            self.assertTrue(second.failed)
            merged = (root / "out.ics").read_text()
            self.assertIn("BEGIN:VTIMEZONE", merged)
            self.assertIn("TZID:Europe/Berlin", merged)
            self.assertIn("SUMMARY:Local lecture", merged)

    def test_conflicting_timezone_fails_only_conflicting_source(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "a.ics").write_text(ICS_TZ)
            conflicting = ICS_TZ.replace("UID:2", "UID:3").replace(
                "TZOFFSETTO:+0100", "TZOFFSETTO:+0200"
            )
            (root / "b.ics").write_text(conflicting)
            (root / "coursemesh.toml").write_text(
                '[coursemesh]\noutput_calendar="out.ics"\n'
                '[[sources]]\nid="a"\nname="A"\npath="a.ics"\n'
                '[[sources]]\nid="b"\nname="B"\npath="b.ics"\n'
            )
            cfg = load_config(root / "coursemesh.toml")
            result = sync_all(cfg)
            self.assertTrue(result.failed)
            self.assertIsNone(result.sources[0].error)
            self.assertIn("Conflicting VTIMEZONE definitions", result.sources[1].error)
            merged = (root / "out.ics").read_text()
            self.assertIn("SUMMARY:Local lecture", merged)
            self.assertEqual(merged.count("BEGIN:VTIMEZONE"), 1)

    def test_http_304_reuses_snapshot_without_reparsing(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = SourceConfig(
                id="remote",
                name="Remote",
                kind="ics",
                url="https://example.invalid/calendar.ics",
            )
            cfg = AppConfig((source,), root / ".coursemesh", root / "out.ics")
            cache = HttpCacheState("resource", '"v1"', None)

            with patch(
                "coursemesh.sync.fetch_source",
                side_effect=[
                    FetchResult(ICS_A, cache),
                    FetchResult(None, cache, not_modified=True),
                ],
            ) as fetch:
                first = sync_all(cfg)
                second = sync_all(cfg)

            self.assertFalse(first.failed)
            self.assertFalse(second.failed)
            self.assertTrue(second.sources[0].not_modified)
            self.assertEqual(second.sources[0].event_count, 1)
            self.assertEqual(second.sources[0].changes, tuple())
            self.assertIn("SUMMARY:Math lecture", (root / "out.ics").read_text())
            self.assertIsNone(fetch.call_args_list[0].kwargs["http_cache"])
            self.assertEqual(fetch.call_args_list[1].kwargs["http_cache"], cache)

    def test_http_304_after_error_clears_error_and_keeps_snapshot(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = SourceConfig(
                id="remote",
                name="Remote",
                kind="ics",
                url="https://example.invalid/calendar.ics",
            )
            cfg = AppConfig((source,), root / ".coursemesh", root / "out.ics")
            cache = HttpCacheState("resource", '"v1"', None)

            with patch(
                "coursemesh.sync.fetch_source",
                side_effect=[
                    FetchResult(ICS_A, cache),
                    RuntimeError("temporary network error"),
                    FetchResult(None, cache, not_modified=True),
                ],
            ):
                self.assertFalse(sync_all(cfg).failed)
                self.assertTrue(sync_all(cfg).failed)
                recovered = sync_all(cfg)

            self.assertFalse(recovered.failed)
            self.assertTrue(recovered.sources[0].not_modified)
            self.assertIn("SUMMARY:Math lecture", (root / "out.ics").read_text())

    def test_broken_source_returns_failure_but_writes_calendar(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "coursemesh.toml").write_text(
                '''[coursemesh]\noutput_calendar="out.ics"\n[[sources]]\nid="broken"\npath="missing.ics"\n'''
            )
            cfg = load_config(root / "coursemesh.toml")
            result = sync_all(cfg)
            self.assertTrue(result.failed)
            self.assertTrue((root / "out.ics").exists())


class RedactionTests(unittest.TestCase):
    def test_url_is_redacted_from_sync_error(self):
        secret = "https://example.invalid/calendar?token=supersecret"
        source = SourceConfig(id="x", name="X", kind="ics", url=secret)
        message = _safe_error(source, RuntimeError(f"failed while fetching {secret}"))
        self.assertNotIn("supersecret", message)
        self.assertIn("<redacted-calendar-url>", message)

    def test_local_path_is_redacted_from_sync_error(self):
        secret_path = Path("/Users/example/private/calendar.ics")
        source = SourceConfig(id="x", name="X", kind="ics", path=secret_path)
        message = _safe_error(source, RuntimeError(f"failed while reading {secret_path}"))
        self.assertNotIn(str(secret_path), message)
        self.assertIn("<redacted-local-calendar-path>", message)


if __name__ == "__main__":
    unittest.main()
