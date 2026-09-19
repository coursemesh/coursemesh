# CourseMesh

CourseMesh is a local-first command-line tool that combines course calendar feeds and reports what changed between syncs.

It is designed for students whose schedules are split across Moodle, Stud.IP, department calendars, and other iCalendar sources. CourseMesh has no hosted backend, no account system, and no telemetry. Provider data is fetched directly by the user's machine and state is kept locally.

> **Status:** alpha. Moodle-generated ICS file exports have been validated against a real export. Live Moodle calendar-URL synchronization and Stud.IP deployment compatibility still need broader validation.

## What it does

- reads local or HTTP(S) iCalendar feeds;
- provides `moodle_ics`, `studip_ics`, and generic `ics` source types;
- detects new, changed, and removed events between syncs;
- preserves last-known-good events if one provider fails;
- writes one merged `.ics` calendar;
- stores synchronization state in local SQLite;
- provides stable JSON output for automation;
- has no runtime Python dependencies.

## Requirements

- Python 3.11 or newer

## Install from source

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --no-deps -e .
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Quick start

Create a starter configuration:

```bash
coursemesh init
```

For private provider URLs, keep the URL out of the repository and reference an environment variable:

```toml
[coursemesh]
state_dir = ".coursemesh"
output_calendar = ".coursemesh/calendar.ics"

[[sources]]
id = "moodle"
name = "Moodle"
type = "moodle_ics"
url_env = "COURSEMESH_MOODLE_ICS_URL"
```

Then set the value in your shell and validate the configuration:

```bash
export COURSEMESH_MOODLE_ICS_URL='https://your-moodle.example/calendar/export_execute.php?...'
coursemesh doctor
coursemesh sync
coursemesh status
```

A local ICS file can be configured instead:

```toml
[[sources]]
id = "moodle-offline"
name = "Moodle offline export"
type = "ics"
path = "private/icalexport.ics"
```

Configured local paths are resolved relative to `coursemesh.toml` and are required to stay inside that configuration directory. This prevents a repository configuration from directing CourseMesh to read or write arbitrary paths elsewhere on the machine.

## Automation

```bash
coursemesh sync --format json
coursemesh status --format json
```

The machine-readable schema is versioned. See [`docs/AUTOMATION.md`](docs/AUTOMATION.md).

## Privacy and secrets

Calendar URLs can contain bearer-like tokens. Prefer `url_env` rather than committing those URLs. CourseMesh does not run a synchronization service or send calendar data to a CourseMesh-operated server.

Local state and the merged calendar can still contain academic information. Treat `.coursemesh/`, local configuration, and private ICS exports as sensitive local files.

See [`docs/PRIVACY.md`](docs/PRIVACY.md) and [`docs/PROVIDERS.md`](docs/PROVIDERS.md).

## Development

Install the repository in an isolated environment and run the standard checks:

```bash
python -m pip install --no-deps -e .
python -m unittest discover -s tests -v
python -m compileall -q src
```

Build and validate distributions with:

```bash
python -m pip install build twine
python -m build
python -m twine check --strict dist/*
```

Compatibility status is documented in [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md). Release procedure is documented in [`docs/RELEASING.md`](docs/RELEASING.md).

## License

CourseMesh is licensed under the MIT License. See [`LICENSE`](LICENSE).
