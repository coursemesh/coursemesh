# Releasing CourseMesh

CourseMesh uses tagged GitHub releases. The release process is intentionally small enough for one maintainer to audit.

## Before tagging

1. Ensure `CHANGELOG.md` describes the release.
2. Ensure `src/coursemesh/__init__.py` contains the release version. Package metadata reads this value dynamically.
3. Install the packaging helpers and run:

```bash
python -m pip install build twine
python -m unittest discover -s tests -v
python -m compileall -q src
python -m build
python -m twine check --strict dist/*
```

4. Install the wheel into a fresh virtual environment and run `coursemesh --version`.
5. Push `main` and wait for CI to pass.

## Release evidence

Before a minor release, keep the release evidence focused on behavior that packaging alone cannot establish:

- the full automated test suite passes, including the loopback HTTP integration test that exercises a real request/response cycle, conditional `ETag` reuse, `304 Not Modified`, and a changed upstream response;
- at least one maintainer-controlled real provider feed is validated end to end without committing its private URL, token, raw calendar, or generated local state;
- `docs/COMPATIBILITY.md` states exactly what was validated and does not generalize one institutional deployment into universal provider support;
- the built wheel is installed into a fresh virtual environment and the reported CLI version matches the intended release tag.

A real-provider validation is evidence for release readiness, not a test fixture. Keep credentials and unredacted provider data outside Git.

## GitHub release

Create an annotated or lightweight tag named `vX.Y.Z` and push it. `.github/workflows/release.yml` rebuilds the package, smoke-tests the wheel, creates the GitHub release, and attaches the distributions.

## PyPI

PyPI publishing is deliberately a separate manual workflow so a repository fork or accidental tag cannot publish a package.

Before the first publish:

1. Create the `coursemesh` project on PyPI if the name is available.
2. Configure a PyPI Trusted Publisher for this GitHub repository and the `pypi` GitHub environment.
3. Protect the `pypi` environment in repository settings if desired.

Then run **Publish to PyPI** from GitHub Actions and provide the exact release tag, for example `v0.2.0`.

The workflow uses OpenID Connect rather than storing a long-lived PyPI API token in GitHub Secrets.

After publishing, verify the public artifact from a clean environment rather than reusing the local build:

```bash
python -m venv /tmp/coursemesh-pypi-smoke
/tmp/coursemesh-pypi-smoke/bin/python -m pip install --disable-pip-version-check --no-deps "coursemesh==0.2.0"
/tmp/coursemesh-pypi-smoke/bin/coursemesh --version
```

This final check proves that the package users can actually retrieve from PyPI is installable and reports the intended version.

## Failed releases

Never move an existing public release tag to different source code. If a release artifact is broken, fix the issue and publish a new patch version.
