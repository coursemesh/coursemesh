from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from .models import CalendarEvent, CalendarTimeZone


@dataclass(frozen=True)
class Change:
    kind: str
    source_id: str
    uid: str
    summary: str


@dataclass(frozen=True)
class SourceStatus:
    source_id: str
    source_name: str
    last_attempt_at: str | None
    last_success_at: str | None
    last_error: str | None
    event_count: int


class StateStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def __enter__(self) -> "StateStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.connection.close()

    def _migrate(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                last_sync_at TEXT,
                last_attempt_at TEXT,
                last_success_at TEXT,
                last_error TEXT,
                event_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        source_columns = {
            row[1]
            for row in self.connection.execute("PRAGMA table_info(sources)").fetchall()
        }
        if "last_attempt_at" not in source_columns:
            self.connection.execute("ALTER TABLE sources ADD COLUMN last_attempt_at TEXT")
        if "last_success_at" not in source_columns:
            self.connection.execute("ALTER TABLE sources ADD COLUMN last_success_at TEXT")
        self.connection.execute(
            """
            UPDATE sources
            SET last_attempt_at = COALESCE(last_attempt_at, last_sync_at),
                last_success_at = CASE
                    WHEN last_success_at IS NOT NULL THEN last_success_at
                    WHEN last_error IS NULL THEN last_sync_at
                    ELSE NULL
                END
            """
        )

        event_columns = {
            row[1]
            for row in self.connection.execute("PRAGMA table_info(events)").fetchall()
        }
        if not event_columns:
            self._create_events_table()
        elif "event_key" not in event_columns:
            # Pre-release v0.1 keyed events only by UID. iCalendar recurrence
            # overrides can legitimately reuse a UID, so migrate to an
            # instance key derived from UID + RECURRENCE-ID.
            self.connection.execute("ALTER TABLE events RENAME TO events_legacy")
            self._create_events_table()
            rows = self.connection.execute(
                "SELECT source_id, fingerprint, payload_json FROM events_legacy"
            ).fetchall()
            for source_id, fingerprint, payload in rows:
                event = CalendarEvent.from_json(payload)
                self.connection.execute(
                    """
                    INSERT INTO events(source_id, event_key, uid, fingerprint, payload_json)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    (source_id, event.instance_key, event.uid, fingerprint, payload),
                )
            self.connection.execute("DROP TABLE events_legacy")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS timezones (
                source_id TEXT NOT NULL,
                tzid TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (source_id, tzid),
                FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE CASCADE
            )
            """
        )
        self.connection.commit()

    def _create_events_table(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE events (
                source_id TEXT NOT NULL,
                event_key TEXT NOT NULL,
                uid TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (source_id, event_key),
                FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE CASCADE
            )
            """
        )

    def apply_source(
        self,
        source_id: str,
        source_name: str,
        events: list[CalendarEvent],
        timezones: list[CalendarTimeZone] | None = None,
    ) -> list[Change]:
        timezones = list(timezones or ())
        event_keys = [event.instance_key for event in events]
        if len(set(event_keys)) != len(event_keys):
            raise ValueError(
                f"Source {source_id!r} contains duplicate VEVENT instances "
                "with the same UID and RECURRENCE-ID"
            )
        tzids = [timezone.tzid for timezone in timezones]
        if len(set(tzids)) != len(tzids):
            raise ValueError(
                f"Source {source_id!r} contains duplicate VTIMEZONE definitions "
                "with the same TZID"
            )
        self._validate_timezone_compatibility(source_id, timezones)
        old_rows = self.connection.execute(
            """
            SELECT event_key, fingerprint, payload_json
            FROM events WHERE source_id = ?
            """,
            (source_id,),
        ).fetchall()
        old = {
            event_key: (fingerprint, CalendarEvent.from_json(payload))
            for event_key, fingerprint, payload in old_rows
        }
        new = {event.instance_key: event for event in events}

        changes: list[Change] = []
        for event_key, event in new.items():
            if event_key not in old:
                changes.append(Change("new", source_id, event.uid, event.summary))
            elif old[event_key][0] != event.fingerprint():
                changes.append(Change("changed", source_id, event.uid, event.summary))
        for event_key, (_, event) in old.items():
            if event_key not in new:
                changes.append(Change("removed", source_id, event.uid, event.summary))

        now = datetime.now(timezone.utc).isoformat()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO sources(
                    source_id, source_name, last_sync_at, last_attempt_at,
                    last_success_at, last_error, event_count
                )
                VALUES(?, ?, ?, ?, ?, NULL, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    source_name = excluded.source_name,
                    last_sync_at = excluded.last_sync_at,
                    last_attempt_at = excluded.last_attempt_at,
                    last_success_at = excluded.last_success_at,
                    last_error = NULL,
                    event_count = excluded.event_count
                """,
                (source_id, source_name, now, now, now, len(events)),
            )
            self.connection.execute("DELETE FROM events WHERE source_id = ?", (source_id,))
            self.connection.executemany(
                """
                INSERT INTO events(source_id, event_key, uid, fingerprint, payload_json)
                VALUES(?, ?, ?, ?, ?)
                """,
                [
                    (
                        source_id,
                        event.instance_key,
                        event.uid,
                        event.fingerprint(),
                        event.to_json(),
                    )
                    for event in events
                ],
            )
            self.connection.execute("DELETE FROM timezones WHERE source_id = ?", (source_id,))
            self.connection.executemany(
                """
                INSERT INTO timezones(source_id, tzid, payload_json)
                VALUES(?, ?, ?)
                """,
                [
                    (source_id, timezone.tzid, timezone.to_json())
                    for timezone in timezones
                ],
            )
        return sorted(changes, key=lambda item: (item.kind, item.summary.casefold(), item.uid))

    def _validate_timezone_compatibility(
        self, source_id: str, timezones: list[CalendarTimeZone]
    ) -> None:
        if not timezones:
            return
        incoming = {timezone.tzid: timezone for timezone in timezones}
        placeholders = ",".join("?" for _ in incoming)
        rows = self.connection.execute(
            f"""
            SELECT source_id, tzid, payload_json
            FROM timezones
            WHERE source_id != ? AND tzid IN ({placeholders})
            """,
            (source_id, *incoming),
        ).fetchall()
        for existing_source, tzid, payload in rows:
            existing = CalendarTimeZone.from_json(payload)
            if existing.lines != incoming[tzid].lines:
                raise ValueError(
                    "Conflicting VTIMEZONE definitions for "
                    f"TZID {tzid!r} from sources "
                    f"{existing_source!r} and {source_id!r}"
                )

    def record_error(self, source_id: str, source_name: str, message: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO sources(
                    source_id, source_name, last_sync_at, last_attempt_at,
                    last_success_at, last_error, event_count
                )
                VALUES(?, ?, ?, ?, NULL, ?, 0)
                ON CONFLICT(source_id) DO UPDATE SET
                    source_name = excluded.source_name,
                    last_sync_at = excluded.last_sync_at,
                    last_attempt_at = excluded.last_attempt_at,
                    last_error = excluded.last_error
                """,
                (source_id, source_name, now, now, message[:1000]),
            )

    def all_events(self) -> list[tuple[str, str, CalendarEvent]]:
        rows = self.connection.execute(
            """
            SELECT e.source_id, s.source_name, e.payload_json
            FROM events e JOIN sources s ON s.source_id = e.source_id
            ORDER BY e.source_id, e.event_key
            """
        ).fetchall()
        return [
            (source_id, source_name, CalendarEvent.from_json(payload))
            for source_id, source_name, payload in rows
        ]

    def all_timezones(self) -> list[tuple[str, CalendarTimeZone]]:
        rows = self.connection.execute(
            """
            SELECT source_id, payload_json
            FROM timezones
            ORDER BY source_id, tzid
            """
        ).fetchall()
        return [
            (source_id, CalendarTimeZone.from_json(payload))
            for source_id, payload in rows
        ]

    def source_status(self) -> list[SourceStatus]:
        rows = self.connection.execute(
            """
            SELECT source_id, source_name, last_attempt_at, last_success_at,
                   last_error, event_count
            FROM sources
            ORDER BY source_id
            """
        ).fetchall()
        return [SourceStatus(*row) for row in rows]
