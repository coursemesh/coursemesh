from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from coursemesh.config import AppConfig, SourceConfig
from coursemesh.sync import sync_all


_CALENDAR_V1 = """BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//CourseMesh Test//EN\r\nBEGIN:VEVENT\r\nUID:demo-1\r\nDTSTART:20260920T100000Z\r\nSUMMARY:Initial\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""
_CALENDAR_V2 = _CALENDAR_V1.replace("SUMMARY:Initial", "SUMMARY:Updated")


class _FeedState:
    def __init__(self) -> None:
        self.etag = '"calendar-v1"'
        self.body = _CALENDAR_V1.encode("utf-8")
        self.if_none_match: list[str | None] = []


class HttpConditionalIntegrationTests(unittest.TestCase):
    def test_sync_uses_real_http_etag_304_and_refreshes_changed_feed(self):
        feed = _FeedState()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - stdlib handler API
                if self.path != "/calendar.ics":
                    self.send_error(404)
                    return
                conditional = self.headers.get("If-None-Match")
                feed.if_none_match.append(conditional)
                if conditional == feed.etag:
                    self.send_response(304)
                    self.send_header("ETag", feed.etag)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/calendar; charset=utf-8")
                self.send_header("Content-Length", str(len(feed.body)))
                self.send_header("ETag", feed.etag)
                self.end_headers()
                self.wfile.write(feed.body)

            def log_message(self, format, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.addCleanup(thread.join, 5)

        host, port = server.server_address
        url = f"http://{host}:{port}/calendar.ics"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AppConfig(
                sources=(SourceConfig(id="remote", name="Remote", kind="ics", url=url),),
                state_dir=root / ".coursemesh",
                output_calendar=root / ".coursemesh" / "calendar.ics",
            )

            first = sync_all(config)
            self.assertFalse(first.failed)
            self.assertFalse(first.sources[0].not_modified)
            self.assertEqual([change.kind for change in first.sources[0].changes], ["new"])
            self.assertIn("SUMMARY:Initial", config.output_calendar.read_text())

            second = sync_all(config)
            self.assertFalse(second.failed)
            self.assertTrue(second.sources[0].not_modified)
            self.assertEqual(second.sources[0].changes, tuple())
            self.assertIn("SUMMARY:Initial", config.output_calendar.read_text())

            feed.etag = '"calendar-v2"'
            feed.body = _CALENDAR_V2.encode("utf-8")

            third = sync_all(config)
            self.assertFalse(third.failed)
            self.assertFalse(third.sources[0].not_modified)
            self.assertEqual([change.kind for change in third.sources[0].changes], ["changed"])
            self.assertIn("SUMMARY:Updated", config.output_calendar.read_text())

            fourth = sync_all(config)
            self.assertFalse(fourth.failed)
            self.assertTrue(fourth.sources[0].not_modified)
            self.assertEqual(fourth.sources[0].changes, tuple())

        self.assertEqual(feed.if_none_match, [None, '"calendar-v1"', '"calendar-v1"', '"calendar-v2"'])


if __name__ == "__main__":
    unittest.main()
