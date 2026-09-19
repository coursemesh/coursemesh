import unittest

from coursemesh.ical import parse_events, render_calendar


SAMPLE = """BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:abc-1\r\nSUMMARY:Operating Systems Sheet 4\r\nDESCRIPTION:Line one\\nLine two\r\nDTSTART:20260924T215900Z\r\nDTEND:20260924T225900Z\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""


class ICalTests(unittest.TestCase):
    def test_parse_basic_event(self):
        events = parse_events(SAMPLE)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].uid, "abc-1")
        self.assertEqual(events[0].summary, "Operating Systems Sheet 4")
        self.assertEqual(events[0].starts_at, "20260924T215900Z")

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


if __name__ == "__main__":
    unittest.main()
