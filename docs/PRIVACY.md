# Privacy model

CourseMesh is designed so a student can aggregate course calendars without creating a CourseMesh account or sending course data to a CourseMesh-operated service.

## Data CourseMesh handles

Depending on configured feeds, local state can contain event titles, descriptions, locations, course identifiers, dates, and provider-specific iCalendar fields. Private calendar URLs may contain bearer-like tokens that grant access to the feed.

## Where data goes

In the current architecture:

- configured HTTP(S) requests go directly from the user's machine to the configured provider;
- parsed event state is stored in the local SQLite database under `state_dir`;
- the merged calendar is written to the configured local output path;
- CourseMesh has no telemetry, analytics endpoint, hosted account system, or project-operated synchronization server.

This does not mean upstream providers are private: Moodle, Stud.IP, a university web server, or any other configured source still sees ordinary requests made to its feed URL.

## Secrets

Prefer `url_env` for private calendar URLs. CourseMesh intentionally resolves those variables only when the source is fetched and redacts resolved URLs from normal sync errors.

Environment variables can still leak through shell history, process inspection on some systems, crash dumps, screenshots, or unrelated tooling. OS keychain storage is planned for a future release.

For HTTP caching, CourseMesh stores provider-supplied `ETag` / `Last-Modified` values and a SHA-256 resource key derived from the resolved feed URL in the local SQLite database. The raw private URL is not stored for this purpose, and cached validators are not reused when the resolved URL changes.

## Local files

The state database and merged `.ics` output can contain academic information. Protect the user account and filesystem accordingly. CourseMesh does not encrypt local state by itself.

## Provider input is untrusted

Calendar payloads are treated as untrusted input. The current fetch layer limits a feed to 10 MiB. Future resource-download support must additionally defend against path traversal, unsafe filenames, overwrite attacks, and decompression/archive hazards before it is considered production-ready.

## Privacy promises we do not make

CourseMesh does not claim anonymity from a university, protection against a compromised local machine, or end-to-end encryption between the student and the LMS. Its privacy goal is narrower: do not introduce another hosted party that needs the student's course data or LMS credentials.
