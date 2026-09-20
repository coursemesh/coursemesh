import unittest

from coursemesh.ical import parse_calendar, parse_events, render_calendar
from coursemesh.models import CalendarTimeZone


SAMPLE = """BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:abc-1\r\nSUMMARY:Operating Systems Sheet 4\r\nDESCRIPTION:Line one\\nLine two\r\nDTSTART:20260924T215900Z\r\nDTEND:20260924T225900Z\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""

TIMEZONE_SAMPLE = """BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VTIMEZONE\r\nTZID:Europe/Berlin\r\nBEGIN:STANDARD\r\nDTSTART:20261025T030000\r\nTZOFFSETFROM:+0200\r\nTZOFFSETTO:+0100\r\nTZNAME:CET\r\nEND:STANDARD\r\nEND:VTIMEZONE\r\nBEGIN:VEVENT\r\nUID:tz-1\r\nSUMMARY:Local lecture\r\nDTSTART;TZID=Europe/Berlin:20261102T100000\r\nDTEND;TZID=Europe/Berlin:20261102T110000\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""


class ICalTests(unittest.TestCase):
    def test_parse_basic_event(self):
        events = parse_events(SAMPLE)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].uid, "abc-1")
        self.assertEqual(events[0].summary, "Operating Systems Sheet 4")
        self.assertEqual(events[0].starts_at, "20260924T215900Z")

    def test_parse_calendar_rejects_non_calendar_response(self):
        with self.assertRaisesRegex(ValueError, "VCALENDAR"):
            parse_calendar("<html><body>Sign in</body></html>")

    def test_parse_calendar_accepts_sequential_calendar_objects(self):
        first = "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:a\nSUMMARY:A\nEND:VEVENT\nEND:VCALENDAR\n"
        second = "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:b\nSUMMARY:B\nEND:VEVENT\nEND:VCALENDAR\n"
        calendar = parse_calendar(first + second)
        self.assertEqual([event.uid for event in calendar.events], ["a", "b"])

    def test_parse_calendar_accepts_utf8_bom_and_blank_outer_lines(self):
        text = "\n\ufeffBEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n\n"
        calendar = parse_calendar(text)
        self.assertEqual(calendar.events, tuple())
        self.assertEqual(calendar.timezones, tuple())

    def test_folded_line_is_unfolded(self):
        text = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:x\nSUMMARY:Very long\n title\nEND:VEVENT\nEND:VCALENDAR\n"
        event = parse_events(text)[0]
        self.assertEqual(event.summary, "Very longtitle")

    def test_fingerprint_ignores_dtstamp(self):
        a = parse_events("BEGIN:VEVENT\nUID:x\nSUMMARY:A\nDTSTAMP:20260101T000000Z\nEND:VEVENT")[0]
        b = parse_events("BEGIN:VEVENT\nUID:x\nSUMMARY:A\nDTSTAMP:20260901T000000Z\nEND:VEVENT")[0]
        self.assertEqual(a.fingerprint(), b.fingerprint())

    def test_colon_inside_quoted_parameter_is_not_value_separator(self):
        text = 'BEGIN:VEVENT\nUID:x\nDESCRIPTION;ALTREP="cid:part1@example.org":Project discussion\nEND:VEVENT'
        event = parse_events(text)[0]
        line = next(line for line in event.lines if line.name == "DESCRIPTION")
        self.assertEqual(line.params, 'ALTREP="cid:part1@example.org"')
        self.assertEqual(line.value, "Project discussion")

    def test_render_rewrites_uid_and_marks_source(self):
        event = parse_events(SAMPLE)[0]
        output = render_calendar([("moodle", "Moodle", event)])
        self.assertIn("UID:moodle.abc-1", output)
        self.assertIn("X-COURSEMESH-SOURCE:moodle", output)
        self.assertIn("SUMMARY:Operating Systems Sheet 4", output)

    def test_parse_calendar_preserves_vtimezone(self):
        calendar = parse_calendar(TIMEZONE_SAMPLE)
        self.assertEqual(len(calendar.events), 1)
        self.assertEqual(len(calendar.timezones), 1)
        timezone = calendar.timezones[0]
        self.assertEqual(timezone.tzid, "Europe/Berlin")
        self.assertIn("BEGIN:STANDARD", timezone.lines)
        self.assertIn("TZOFFSETTO:+0100", timezone.lines)

    def test_render_calendar_preserves_vtimezone_before_events(self):
        calendar = parse_calendar(TIMEZONE_SAMPLE)
        output = render_calendar(
            [("moodle", "Moodle", calendar.events[0])],
            [("moodle", calendar.timezones[0])],
        )
        self.assertIn("BEGIN:VTIMEZONE\r\nTZID:Europe/Berlin", output)
        self.assertLess(output.index("BEGIN:VTIMEZONE"), output.index("BEGIN:VEVENT"))
        self.assertIn("DTSTART;TZID=Europe/Berlin:20261102T100000", output)

    def test_render_deduplicates_identical_vtimezones(self):
        timezone = parse_calendar(TIMEZONE_SAMPLE).timezones[0]
        output = render_calendar([], [("a", timezone), ("b", timezone)])
        self.assertEqual(output.count("BEGIN:VTIMEZONE"), 1)

    def test_render_rejects_conflicting_vtimezone_definitions(self):
        first = parse_calendar(TIMEZONE_SAMPLE).timezones[0]
        second = CalendarTimeZone(
            tzid=first.tzid,
            lines=tuple(
                line.replace("TZOFFSETTO:+0100", "TZOFFSETTO:+0200")
                for line in first.lines
            ),
        )
        with self.assertRaisesRegex(ValueError, "Conflicting VTIMEZONE definitions"):
            render_calendar([], [("a", first), ("b", second)])

    def test_parse_rejects_mismatched_component_end(self):
        text = "BEGIN:VEVENT\nUID:x\nBEGIN:VALARM\nEND:VEVENT\n"
        with self.assertRaisesRegex(ValueError, "Mismatched iCalendar component ending"):
            parse_events(text)


if __name__ == "__main__":
    unittest.main()
