# Compatibility status

CourseMesh separates **implemented parsing paths** from **real-provider validation**. A provider name in configuration is not a claim that every institutional deployment has been tested.

| Source | v0.1 path | Upstream interface | Repository tests | Live deployment validation |
| --- | --- | --- | --- | --- |
| Generic ICS file | Supported | iCalendar file | Event, recurrence, folding, and `VTIMEZONE` regression coverage | N/A |
| Generic HTTP(S) ICS | Supported | iCalendar URL | Fetch/state tests; live network is not used in unit tests | Not tracked per server |
| Moodle | ICS preset | Moodle calendar export | Generic ICS behavior | **Validated by maintainer against a real Moodle ICS file export** |
| Stud.IP | ICS preset | Stud.IP external calendar URL | Generic ICS behavior | **Needs maintainer/community validation** |

### Moodle validation

Maintainer validation on 2026-09-19:

- real Moodle calendar ICS export;
- macOS;
- initial sync succeeded with 2 events;
- repeated syncs remained stable with the same 2 events;
- status reported no errors;
- no private calendar URL, token, student data, or raw export is stored in the repository.

This validates parsing and state handling for a real Moodle ICS file export. Live Moodle calendar-URL synchronization has not yet been validated.

## What counts as validated

A provider can move from “needs validation” to a tested status when we have:

1. an end-to-end sync against a deployment the tester is authorized to use;
2. a sanitized regression fixture for any provider-specific behavior we depend on;
3. no live token, student name, course membership, or private URL committed to the repository;
4. the relevant upstream documentation linked in `docs/PROVIDERS.md`.

Institution-specific UI wording and enabled features can vary even when the underlying LMS is the same. CourseMesh should document those differences instead of implying universal support.

## How to help validate a provider

Run CourseMesh against your own export, then report:

- LMS/provider and version if visible;
- CourseMesh version;
- operating system and Python version;
- whether initial sync and a second sync succeed;
- sanitized example lines only when necessary to reproduce a parser issue.

Never include the private calendar URL itself.

## Calendar fidelity

CourseMesh preserves `VTIMEZONE` components from successful source snapshots and writes them before merged events. Identical definitions for the same `TZID` are deduplicated. If two sources provide different definitions for the same `TZID`, CourseMesh fails the merge instead of silently choosing one and producing ambiguous timezone semantics.

This behavior is covered by synthetic RFC-style regression fixtures. The maintainer's current Moodle validation export uses UTC/floating timestamps and therefore does not independently validate provider-generated `VTIMEZONE` blocks.
