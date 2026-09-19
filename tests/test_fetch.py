from email.message import Message
from io import BytesIO
from urllib.error import HTTPError
import unittest
from unittest.mock import patch

from coursemesh.config import SourceConfig
from coursemesh.fetch import fetch_source
from coursemesh.models import HttpCacheState


class FakeResponse:
    def __init__(self, body: bytes, headers: Message):
        self._body = BytesIO(body)
        self.headers = headers

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


class FetchTests(unittest.TestCase):
    def test_http_validators_are_reused_for_matching_url_and_304(self):
        source = SourceConfig(
            id="demo",
            name="Demo",
            kind="ics",
            url="https://example.invalid/calendar.ics",
        )
        first_headers = Message()
        first_headers["Content-Type"] = "text/calendar; charset=utf-8"
        first_headers["ETag"] = '"calendar-v1"'
        first_headers["Last-Modified"] = "Sat, 19 Sep 2026 17:00:00 GMT"

        with patch(
            "coursemesh.fetch.urlopen",
            return_value=FakeResponse(b"BEGIN:VCALENDAR\nEND:VCALENDAR\n", first_headers),
        ):
            first = fetch_source(source)

        self.assertIsNotNone(first.http_cache)
        self.assertEqual(first.http_cache.etag, '"calendar-v1"')

        response_headers = Message()
        response_headers["ETag"] = '"calendar-v1"'
        captured = {}

        def not_modified(request, timeout):
            captured.update(dict(request.header_items()))
            raise HTTPError(
                request.full_url,
                304,
                "Not Modified",
                response_headers,
                None,
            )

        with patch("coursemesh.fetch.urlopen", side_effect=not_modified):
            second = fetch_source(source, http_cache=first.http_cache)

        lowered = {key.lower(): value for key, value in captured.items()}
        self.assertEqual(lowered["if-none-match"], '"calendar-v1"')
        self.assertEqual(
            lowered["if-modified-since"], "Sat, 19 Sep 2026 17:00:00 GMT"
        )
        self.assertTrue(second.not_modified)
        self.assertIsNone(second.text)
        self.assertEqual(second.http_cache.etag, '"calendar-v1"')

    def test_unsolicited_304_is_rejected(self):
        source = SourceConfig(
            id="demo",
            name="Demo",
            kind="ics",
            url="https://example.invalid/calendar.ics",
        )

        def not_modified(request, timeout):
            raise HTTPError(
                request.full_url,
                304,
                "Not Modified",
                Message(),
                None,
            )

        with patch("coursemesh.fetch.urlopen", side_effect=not_modified):
            with self.assertRaisesRegex(ValueError, "matching conditional request"):
                fetch_source(source)

    def test_unsafe_cached_validator_is_not_sent(self):
        source = SourceConfig(
            id="demo",
            name="Demo",
            kind="ics",
            url="https://example.invalid/calendar.ics",
        )
        initial_headers = Message()
        initial_headers["ETag"] = '"safe"'
        with patch(
            "coursemesh.fetch.urlopen",
            return_value=FakeResponse(b"BEGIN:VCALENDAR\nEND:VCALENDAR\n", initial_headers),
        ):
            initial = fetch_source(source)

        unsafe_cache = HttpCacheState(
            initial.http_cache.resource_key,
            "bad\r\nInjected: header",
            None,
        )
        captured = {}

        def response(request, timeout):
            captured.update(dict(request.header_items()))
            return FakeResponse(b"BEGIN:VCALENDAR\nEND:VCALENDAR\n", Message())

        with patch("coursemesh.fetch.urlopen", side_effect=response):
            fetch_source(source, http_cache=unsafe_cache)

        lowered = {key.lower(): value for key, value in captured.items()}
        self.assertNotIn("if-none-match", lowered)

    def test_validators_are_not_sent_to_a_different_url(self):
        old_source = SourceConfig(
            id="demo",
            name="Demo",
            kind="ics",
            url="https://old.example.invalid/calendar.ics",
        )
        headers = Message()
        headers["ETag"] = '"old"'
        with patch(
            "coursemesh.fetch.urlopen",
            return_value=FakeResponse(b"BEGIN:VCALENDAR\nEND:VCALENDAR\n", headers),
        ):
            old_result = fetch_source(old_source)

        new_source = SourceConfig(
            id="demo",
            name="Demo",
            kind="ics",
            url="https://new.example.invalid/calendar.ics",
        )
        captured = {}

        def new_response(request, timeout):
            captured.update(dict(request.header_items()))
            return FakeResponse(b"BEGIN:VCALENDAR\nEND:VCALENDAR\n", Message())

        with patch("coursemesh.fetch.urlopen", side_effect=new_response):
            fetch_source(new_source, http_cache=old_result.http_cache)

        lowered = {key.lower(): value for key, value in captured.items()}
        self.assertNotIn("if-none-match", lowered)
        self.assertNotIn("if-modified-since", lowered)

    def test_unsafe_response_validator_is_not_persisted(self):
        source = SourceConfig(
            id="demo",
            name="Demo",
            kind="ics",
            url="https://example.invalid/calendar.ics",
        )
        headers = Message()
        headers["ETag"] = "x" * 5000
        with patch(
            "coursemesh.fetch.urlopen",
            return_value=FakeResponse(b"BEGIN:VCALENDAR\nEND:VCALENDAR\n", headers),
        ):
            result = fetch_source(source)

        self.assertIsNone(result.http_cache)


if __name__ == "__main__":
    unittest.main()
