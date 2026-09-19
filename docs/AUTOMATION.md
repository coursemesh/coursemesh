# Automation interface

CourseMesh keeps machine-readable output versioned so scripts do not need to scrape human CLI text.

## Sync

```bash
coursemesh sync --format json
```

The top-level `schema_version` is currently `1`. A source includes its event count, an optional error, and zero or more changes. Each change has `kind`, `uid`, and `summary`.

A sync exits with code `1` when at least one source fails. Healthy sources still update, and the merged calendar is rebuilt from last-known-good state.

## Status

```bash
coursemesh status --format json
```

Status separates `last_attempt_at` from `last_success_at`. A failed provider fetch updates the attempt time and error but preserves the previous successful snapshot and event count.

## Compatibility policy

Fields may be added within schema version 1. Existing fields will not be removed or change meaning without incrementing `schema_version`.
