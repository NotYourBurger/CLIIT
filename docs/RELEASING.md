# Releasing CLIIT

Releases are built and published by `.github/workflows/release.yml`. Do not
upload distributions from a workstation and do not add a PyPI token to GitHub.

## One-time setup

1. Rename the GitHub repository to `NotYourBurger/CLIIT` and make it public.
2. In the repository settings, enable private vulnerability reporting.
3. Create a GitHub environment named `pypi` and require maintainer approval.
4. On PyPI's pending-publisher page, register:
   - project: `cliit`
   - owner: `NotYourBurger`
   - repository: `CLIIT`
   - workflow: `release.yml`
   - environment: `pypi`

The PyPI project is created by the first trusted publish. No long-lived
credential is involved.

## Cut a release

1. Update the version in `pyproject.toml` and move the release notes out of
   `Unreleased` in `CHANGELOG.md`.
2. Run `uv lock`, `uv run python tests/all.py`, `uv run issue check`, and
   `uv build --no-sources`.
3. Commit the release and merge it to `main`.
4. Tag that exact commit with the matching version and push the tag:

   ```bash
   git tag -s v0.1.0 -m "CLIIT 0.1.0"
   git push origin v0.1.0
   ```

The workflow refuses a tag that does not exactly equal `v` plus the version in
`pyproject.toml`. It runs the full OS/Python matrix, builds once, checks the
wheel and source distribution, publishes that artifact through PyPI Trusted
Publishing, and attaches the same files to a generated GitHub release.

After the first publish succeeds, replace README's Git install example with
`uv tool install cliit` and remove the "Not on PyPI yet" note.
