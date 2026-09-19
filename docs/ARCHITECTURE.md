# Architecture

CourseMesh is designed around a local-first invariant: provider credentials and course data do not need to pass through a CourseMesh-operated server.

## Data flow

```text
coursemesh.toml + environment
            |
            v
       SourceConfig
            |
      +-----+------+
      |            |
 local file     HTTP(S)
      |            |
      +-----+------+
            v
        ICS parser
            |
            v
      CalendarEvent[]
            |
            v
        StateStore  <---- previous successful snapshot
            |
       +----+----+
       |         |
     diffs    last-known-good events
       |         |
       v         v
      CLI     ICS renderer
                 |
                 v
          merged calendar.ics
```

## Ownership boundaries

### Config

`config.py` validates user-owned configuration and keeps secret resolution lazy. A source can specify exactly one of `url`, `url_env`, or `path`.

### Fetch

`fetch.py` is the I/O boundary. It accepts only local files and HTTP(S). Future authenticated provider APIs belong behind this boundary rather than in the parser.

### iCalendar

`ical.py` owns syntax-level parsing and rendering. It does not know Moodle or Stud.IP. `VEVENT` content lines are retained so provider-specific fields can survive a merge.

### State

`state.py` owns persistence and diff semantics. A source update is transactional. Errors are recorded without deleting the last successful events.

### Sync orchestration

`sync.py` coordinates sources independently. One broken provider must not stop healthy sources from updating or destroy the aggregate calendar.

## Compatibility policy

- Python 3.11+.
- No runtime dependencies in v0.1.
- SQLite schema changes require migration coverage.
- Provider failures must be isolated per source.
- Secret-bearing URLs must never be printed by normal commands.
- Event diffing should ignore volatile metadata such as `DTSTAMP`.

## Extension direction

A future adapter protocol should return provider-neutral entities (`CalendarEvent`, `Announcement`, `Resource`) and declare capabilities. Provider implementations should not write SQLite directly. This keeps authentication, parsing, persistence, and presentation independently testable.
