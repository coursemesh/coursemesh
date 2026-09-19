# Releasing CourseMesh

CourseMesh uses tagged GitHub releases. The release process is intentionally small enough for one maintainer to audit.

## Before tagging

1. Ensure `CHANGELOG.md` describes the release.
2. Ensure the version in `pyproject.toml` and `src/coursemesh/__init__.py` matches.
3. Install the packaging helper and run:

```bash
python -m pip install build
python -m unittest discover -s tests -v
python -m compileall -q src
python -m build
```

4. Install the wheel into a fresh virtual environment and run `coursemesh --version`.
5. Push `main` and wait for CI to pass.

## GitHub release

Create an annotated or lightweight tag named `vX.Y.Z` and push it. `.github/workflows/release.yml` rebuilds the package, smoke-tests the wheel, creates the GitHub release, and attaches the distributions.

## PyPI

PyPI publishing is deliberately a separate manual workflow so a repository fork or accidental tag cannot publish a package.

Before the first publish:

1. Create the `coursemesh` project on PyPI if the name is available.
2. Configure a PyPI Trusted Publisher for this GitHub repository and the `pypi` GitHub environment.
3. Protect the `pypi` environment in repository settings if desired.

Then run **Publish to PyPI** from GitHub Actions and provide an existing release tag such as `v0.1.0`.

The workflow uses OpenID Connect rather than storing a long-lived PyPI API token in GitHub Secrets.

## Failed releases

Never move an existing public release tag to different source code. If a release artifact is broken, fix the issue and publish a new patch version.
