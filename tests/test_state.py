from pathlib import Path
import sqlite3
import tempfile
import unittest

from coursemesh.ical import parse_events
from coursemesh.state import StateStore


def event(summary: str, recurrence_id: str | None = None):
    recurrence = f"\nRECURRENCE-ID:{recurrence_id}" if recurrence_id else ""
    return parse_events(
        f"BEGIN:VEVENT\nUID:x\nSUMMARY:{summary}\nDTSTART:20260920T100000Z{recurrence}\nEND:VEVENT"
    )[0]


class StateTests(unittest.TestCase):
    def test_detects_new_changed_and_removed(self):
        with tempfile.TemporaryDirectory() as raw:
            db = Path(raw) / "state.db"
            with StateStore(db) as store:
                changes = store.apply_source("demo", "Demo", [event("A")])
                self.assertEqual([c.kind for c in changes], ["new"])
                changes = store.apply_source("demo", "Demo", [event("B")])
                self.assertEqual([c.kind for c in changes], ["changed"])
                changes = store.apply_source("demo", "Demo", [])
                self.assertEqual([c.kind for c in changes], ["removed"])

    def test_allows_recurrence_overrides_with_same_uid(self):
        with tempfile.TemporaryDirectory() as raw:
            db = Path(raw) / "state.db"
            with StateStore(db) as store:
                changes = store.apply_source(
                    "demo",
                    "Demo",
                    [
                        event("Series"),
                        event("Moved occurrence", "20260927T100000Z"),
                    ],
                )
                self.assertEqual(len(changes), 2)
                self.assertEqual(len(store.all_events()), 2)

    def test_rejects_duplicate_event_instances(self):
        with tempfile.TemporaryDirectory() as raw:
            db = Path(raw) / "state.db"
            with StateStore(db) as store:
                with self.assertRaisesRegex(ValueError, "duplicate VEVENT instances"):
                    store.apply_source("demo", "Demo", [event("A"), event("B")])

    def test_error_does_not_delete_existing_events_or_last_success(self):
        with tempfile.TemporaryDirectory() as raw:
            db = Path(raw) / "state.db"
            with StateStore(db) as store:
                store.apply_source("demo", "Demo", [event("A")])
                before = store.source_status()[0]
                store.record_error("demo", "Demo", "network down")
                after = store.source_status()[0]
                self.assertEqual(len(store.all_events()), 1)
                self.assertEqual(after.last_success_at, before.last_success_at)
                self.assertEqual(after.event_count, 1)
                self.assertEqual(after.last_error, "network down")
                self.assertIsNotNone(after.last_attempt_at)

    def test_migrates_pre_release_uid_schema(self):
        with tempfile.TemporaryDirectory() as raw:
            db = Path(raw) / "state.db"
            connection = sqlite3.connect(db)
            connection.executescript(
                """
                CREATE TABLE sources (
                    source_id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    last_sync_at TEXT,
                    last_error TEXT,
                    event_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE events (
                    source_id TEXT NOT NULL,
                    uid TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (source_id, uid)
                );
                """
            )
            old_event = event("Existing")
            connection.execute(
                "INSERT INTO sources VALUES (?, ?, ?, NULL, ?)",
                ("demo", "Demo", "2026-09-19T00:00:00+00:00", 1),
            )
            connection.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?)",
                ("demo", old_event.uid, old_event.fingerprint(), old_event.to_json()),
            )
            connection.commit()
            connection.close()

            with StateStore(db) as store:
                self.assertEqual(len(store.all_events()), 1)
                status = store.source_status()[0]
                self.assertEqual(status.last_success_at, "2026-09-19T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
