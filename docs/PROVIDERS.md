# Provider setup

CourseMesh v0.1 uses standards-based calendar exports instead of automating provider login pages.

## Moodle

Moodle documents calendar export to an `.ics` file or a generated calendar URL. The generated URL may contain an authentication token and should be treated as a secret.

Upstream documentation:
- https://docs.moodle.org/402/en/Using_Calendar
- https://docs.moodle.org/402/de/Kalender_nutzen

Recommended CourseMesh configuration:

```toml
[[sources]]
id = "moodle"
name = "Moodle"
type = "moodle_ics"
url_env = "COURSEMESH_MOODLE_ICS_URL"
```

Then set the generated calendar URL outside the repository:

```bash
export COURSEMESH_MOODLE_ICS_URL='https://moodle.example/calendar/export_execute.php?...'
coursemesh sync
```

## Stud.IP

Stud.IP documents generating a web address that can be added to external calendar applications. Availability and UI wording can differ by Stud.IP version and institution.

Upstream documentation:
- https://hilfe.studip.de/help/6/en/Basis/TerminkalenderExportSync
- https://hilfe.studip.de/help/5/de/Basis/TerminkalenderExportSync

Recommended CourseMesh configuration:

```toml
[[sources]]
id = "studip"
name = "Stud.IP"
type = "studip_ics"
url_env = "COURSEMESH_STUDIP_ICS_URL"
```

## Generic ICS

Any HTTP(S) calendar URL or local `.ics` file can be configured with `type = "ics"`.

Public URL:

```toml
[[sources]]
id = "department"
name = "Department"
type = "ics"
url = "https://example.edu/calendar.ics"
```

Local file:

```toml
[[sources]]
id = "fixture"
name = "Fixture"
type = "ics"
path = "calendar.ics"
```

## Security note

If a generated calendar URL grants access without an interactive login, possession of that URL may be enough to read the feed. Prefer `url_env`; do not paste private URLs into bug reports, screenshots, shell history you plan to publish, or committed configuration.
