from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .config import load_config
from .state import StateStore
from .sync import sync_all


SCHEMA_VERSION = 1

SAMPLE_CONFIG = '''[coursemesh]\nstate_dir = ".coursemesh"\noutput_calendar = ".coursemesh/calendar.ics"\n\n# Prefer url_env for calendar URLs containing private tokens.\n[[sources]]\nid = "moodle"\nname = "Moodle"\ntype = "moodle_ics"\nurl_env = "COURSEMESH_MOODLE_ICS_URL"\n\n# Add more sources, for example:\n# [[sources]]\n# id = "studip"\n# name = "Stud.IP"\n# type = "studip_ics"\n# url_env = "COURSEMESH_STUDIP_ICS_URL"\n'''


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coursemesh",
        description="Local-first course calendar sync",
    )
    parser.add_argument("--version", action="version", version=f"coursemesh {__version__}")
    parser.add_argument("--config", type=Path, default=Path("coursemesh.toml"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create a starter coursemesh.toml")
    sync_parser = sub.add_parser(
        "sync", help="Fetch sources, detect changes, and write a merged calendar"
    )
    sync_parser.add_argument("--format", choices=("text", "json"), default="text")
    status_parser = sub.add_parser("status", help="Show the last known state for each source")
    status_parser.add_argument("--format", choices=("text", "json"), default="text")
    sub.add_parser("doctor", help="Validate configuration without contacting providers")
    return parser


def _sync_json(result) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "failed": result.failed,
        "output_calendar": str(result.output_calendar),
        "sources": [
            {
                "id": source.source_id,
                "name": source.source_name,
                "event_count": source.event_count,
                "error": source.error,
                "changes": [
                    {
                        "kind": change.kind,
                        "uid": change.uid,
                        "summary": change.summary,
                    }
                    for change in source.changes
                ],
            }
            for source in result.sources
        ],
    }


def _status_json(rows) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "sources": [
            {
                "id": row.source_id,
                "name": row.source_name,
                "last_attempt_at": row.last_attempt_at,
                "last_success_at": row.last_success_at,
                "last_error": row.last_error,
                "event_count": row.event_count,
            }
            for row in rows
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path: Path = args.config.resolve()

    if args.command == "init":
        if config_path.exists():
            print(f"Refusing to overwrite existing {config_path}", file=sys.stderr)
            return 2
        config_path.write_text(SAMPLE_CONFIG, encoding="utf-8")
        print(f"Created {config_path}")
        print("Set the calendar URL environment variable, then run: coursemesh sync")
        return 0

    try:
        config = load_config(config_path)
    except Exception as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.command == "doctor":
        print(f"OK: {len(config.sources)} source(s) configured")
        print(f"State directory: {config.state_dir}")
        print(f"Merged calendar: {config.output_calendar}")
        for source in config.sources:
            location = "environment variable" if source.url_env else ("local file" if source.path else "URL")
            print(f"- {source.id}: {source.kind} via {location}")
        return 0

    if args.command == "sync":
        result = sync_all(config)
        if args.format == "json":
            print(json.dumps(_sync_json(result), ensure_ascii=False, indent=2))
        else:
            for source in result.sources:
                if source.error:
                    print(f"ERROR {source.source_name}: {source.error}")
                    continue
                print(f"OK {source.source_name}: {source.event_count} event(s)")
                for change in source.changes:
                    marker = {"new": "+", "changed": "~", "removed": "-"}[change.kind]
                    print(f"  {marker} {change.kind.upper():7} {change.summary}")
            print(f"Merged calendar: {result.output_calendar}")
        return 1 if result.failed else 0

    if args.command == "status":
        db_path = config.state_dir / "state.db"
        if not db_path.exists():
            if args.format == "json":
                print(json.dumps({"schema_version": SCHEMA_VERSION, "sources": []}, indent=2))
            else:
                print("No sync state yet. Run: coursemesh sync")
            return 0
        with StateStore(db_path) as store:
            rows = store.source_status()
        if args.format == "json":
            print(json.dumps(_status_json(rows), ensure_ascii=False, indent=2))
            return 0
        if not rows:
            print("No source state yet. Run: coursemesh sync")
            return 0
        for row in rows:
            if row.last_error:
                state = f"ERROR {row.last_error}"
            else:
                state = f"OK {row.event_count} event(s)"
            print(
                f"{row.source_name} [{row.source_id}]: {state}; "
                f"last success {row.last_success_at or 'never'}; "
                f"last attempt {row.last_attempt_at or 'never'}"
            )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
