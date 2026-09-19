# Changelog

All notable changes to CourseMesh are documented here.

## Unreleased

### Changed

- Preserve `VTIMEZONE` components across parsing, local state, provider failures, and merged calendar output.
- Deduplicate identical timezone definitions and reject conflicting definitions for the same `TZID` instead of emitting an ambiguous calendar.
- Tighten component parsing so mismatched nested iCalendar components fail explicitly.

## 0.1.1 - 2026-09-19

### Security

- Restrict configured state, output, and local ICS paths to the directory containing `coursemesh.toml`.
- Resolve local source paths once during configuration loading instead of resolving them again during fetch.
- Redact configured local calendar paths from synchronization errors stored or printed by CourseMesh.

### Fixed

- Add the missing project README used as Python package long description.
- Add the MIT license file and modern PEP 639 package license metadata.
- Use one runtime version source for package metadata, CLI output, HTTP user agent, and generated calendar product identifier.

## 0.1.0 - 2026-09-19

- Initial alpha release with local and HTTP(S) ICS sources, change detection, last-known-good state, merged calendar output, JSON automation output, and real-world Moodle ICS file validation.
