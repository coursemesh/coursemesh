from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile

from .config import AppConfig, SourceConfig
from .fetch import fetch_source
from .ical import parse_calendar, render_calendar
from .state import Change, StateStore


@dataclass(frozen=True)
class SourceResult:
    source_id: str
    source_name: str
    event_count: int | None
    changes: tuple[Change, ...]
    error: str | None = None


@dataclass(frozen=True)
class SyncResult:
    sources: tuple[SourceResult, ...]
    output_calendar: Path

    @property
    def failed(self) -> bool:
        return any(source.error for source in self.sources)


def sync_all(config: AppConfig) -> SyncResult:
    config.state_dir.mkdir(parents=True, exist_ok=True)
    db_path = config.state_dir / "state.db"
    results: list[SourceResult] = []

    with StateStore(db_path) as store:
        for source in config.sources:
            try:
                text = fetch_source(source)
                calendar = parse_calendar(text)
                events = list(calendar.events)
                timezones = list(calendar.timezones)
                changes = store.apply_source(
                    source.id, source.name, events, timezones
                )
                results.append(SourceResult(source.id, source.name, len(events), tuple(changes)))
            except Exception as exc:  # boundary: keep other sources syncing
                message = _safe_error(source, exc)
                store.record_error(source.id, source.name, message)
                results.append(SourceResult(source.id, source.name, None, tuple(), message))

        merged = render_calendar(store.all_events(), store.all_timezones())
        _atomic_write_text(config.output_calendar, merged)

    return SyncResult(tuple(results), config.output_calendar)


def _safe_error(source: SourceConfig, exc: Exception) -> str:
    message = f"{type(exc).__name__}: {exc}"
    replacements: list[tuple[str | None, str]] = [
        (source.url, "<redacted-calendar-url>"),
        (str(source.path) if source.path else None, "<redacted-local-calendar-path>"),
    ]
    if source.url_env:
        try:
            replacements.append((source.resolved_url(), "<redacted-calendar-url>"))
        except Exception:
            pass
    for secret, placeholder in replacements:
        if secret:
            message = message.replace(secret, placeholder)
    return message


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        finally:
            raise
