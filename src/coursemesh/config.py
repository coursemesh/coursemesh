from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class SourceConfig:
    id: str
    name: str
    kind: str
    url: str | None = None
    path: str | None = None
    url_env: str | None = None

    def resolved_url(self) -> str | None:
        if self.url_env:
            value = os.getenv(self.url_env)
            if not value:
                raise ValueError(f"Environment variable {self.url_env} is not set")
            return value
        return self.url


@dataclass(frozen=True)
class AppConfig:
    sources: tuple[SourceConfig, ...]
    state_dir: Path
    output_calendar: Path


def load_config(path: Path) -> AppConfig:
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    app = data.get("coursemesh", {})
    state_dir = (path.parent / app.get("state_dir", ".coursemesh")).resolve()
    output_calendar = (path.parent / app.get("output_calendar", ".coursemesh/calendar.ics")).resolve()

    sources: list[SourceConfig] = []
    seen: set[str] = set()
    for raw in data.get("sources", []):
        source_id = str(raw.get("id", "")).strip()
        if not source_id:
            raise ValueError("Every source needs a non-empty id")
        if source_id in seen:
            raise ValueError(f"Duplicate source id: {source_id}")
        seen.add(source_id)
        kind = str(raw.get("type", "ics")).strip().lower()
        if kind not in {"ics", "moodle_ics", "studip_ics"}:
            raise ValueError(f"Unsupported source type: {kind}")
        source = SourceConfig(
            id=source_id,
            name=str(raw.get("name", source_id)).strip() or source_id,
            kind=kind,
            url=raw.get("url"),
            path=raw.get("path"),
            url_env=raw.get("url_env"),
        )
        selectors = sum(bool(x) for x in (source.url, source.path, source.url_env))
        if selectors != 1:
            raise ValueError(
                f"Source {source_id!r} must set exactly one of url, path, or url_env"
            )
        sources.append(source)

    if not sources:
        raise ValueError("Config contains no [[sources]] entries")
    return AppConfig(tuple(sources), state_dir, output_calendar)
