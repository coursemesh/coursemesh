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
    path: Path | None = None
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


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{label} must not be empty")
    return value


def _resolve_inside(config_dir: Path, value: object, label: str) -> Path:
    raw = _optional_text(value, label)
    if raw is None:
        raise ValueError(f"{label} must be configured")

    base = config_dir.resolve()
    candidate = (base / raw).resolve()
    if not candidate.is_relative_to(base):
        raise ValueError(f"{label} must stay within the configuration directory")
    return candidate


def load_config(path: Path) -> AppConfig:
    config_path = path.resolve()
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)

    app = data.get("coursemesh", {})
    if not isinstance(app, dict):
        raise ValueError("[coursemesh] must be a table")

    config_dir = config_path.parent
    state_dir = _resolve_inside(
        config_dir,
        app.get("state_dir", ".coursemesh"),
        "coursemesh.state_dir",
    )
    output_calendar = _resolve_inside(
        config_dir,
        app.get("output_calendar", ".coursemesh/calendar.ics"),
        "coursemesh.output_calendar",
    )

    raw_sources = data.get("sources", [])
    if not isinstance(raw_sources, list):
        raise ValueError("[[sources]] entries must be an array of tables")

    sources: list[SourceConfig] = []
    seen: set[str] = set()
    for raw in raw_sources:
        if not isinstance(raw, dict):
            raise ValueError("Each [[sources]] entry must be a table")

        source_id = str(raw.get("id", "")).strip()
        if not source_id:
            raise ValueError("Every source needs a non-empty id")
        if source_id in seen:
            raise ValueError(f"Duplicate source id: {source_id}")
        seen.add(source_id)

        kind = str(raw.get("type", "ics")).strip().lower()
        if kind not in {"ics", "moodle_ics", "studip_ics"}:
            raise ValueError(f"Unsupported source type: {kind}")

        url = _optional_text(raw.get("url"), f"Source {source_id!r} url")
        path_value = _optional_text(raw.get("path"), f"Source {source_id!r} path")
        url_env = _optional_text(raw.get("url_env"), f"Source {source_id!r} url_env")
        selectors = sum(value is not None for value in (url, path_value, url_env))
        if selectors != 1:
            raise ValueError(
                f"Source {source_id!r} must set exactly one of url, path, or url_env"
            )

        local_path = None
        if path_value is not None:
            local_path = _resolve_inside(
                config_dir,
                path_value,
                f"Source {source_id!r} path",
            )

        sources.append(
            SourceConfig(
                id=source_id,
                name=str(raw.get("name", source_id)).strip() or source_id,
                kind=kind,
                url=url,
                path=local_path,
                url_env=url_env,
            )
        )

    if not sources:
        raise ValueError("Config contains no [[sources]] entries")
    return AppConfig(tuple(sources), state_dir, output_calendar)
