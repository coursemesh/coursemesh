# Compatibility status

CourseMesh separates **implemented parsing paths** from **real-provider validation**. A provider name in configuration is not a claim that every institutional deployment has been tested.

| Source | v0.1 path | Upstream interface | Repository tests | Live deployment validation |
| --- | --- | --- | --- | --- |
| Generic ICS file | Supported | iCalendar file | Yes | N/A |
| Generic HTTP(S) ICS | Supported | iCalendar URL | Fetch/state tests; live network is not used in unit tests | Not tracked per server |
| Moodle | ICS preset | Moodle calendar export URL | Generic ICS behavior | **Needs maintainer/community validation** |
| Stud.IP | ICS preset | Stud.IP external calendar URL | Generic ICS behavior | **Needs maintainer/community validation** |

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
