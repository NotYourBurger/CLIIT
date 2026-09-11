# Changelog

All notable changes to this project are documented here. Releases follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html); while the project
is below 1.0, minor releases may include interface changes.

## [Unreleased]

## [0.1.1]

Documentation only; the package itself is unchanged. The 0.1.0 project page on
PyPI was built from a README that still told people to install from GitHub, so
this release exists to publish the current one.

### Changed

- Rewrote the README hero to say what CLIIT is for and what it keeps in Git.
- Added a recorded terminal demo above the fold, with `docs/demo.sh` and
  `docs/demo.cast` beside it so it can be regenerated rather than re-performed.

## [0.1.0]

First public release.

### Added

- Markdown-native issues stored alongside the code in `.issues/`.
- Commands to create, rank, search, claim, assign, start, validate, and close
  issues with structured evidence.
- Stable JSON output and meaningful exit codes for scripts and coding agents.
- Race-safe claims, exclusive ID allocation, and atomic issue rewrites.
- Durable work plans and append-only event logs for interrupted agent runs.
- Project instruction setup for Codex, Claude Code, and other coding agents.
- `issue` and `cliit` executable names for the CLIIT command-line application.
- Cross-platform tests for Python 3.10 through 3.13 and clean-wheel smoke tests.

[Unreleased]: https://github.com/NotYourBurger/CLIIT/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/NotYourBurger/CLIIT/releases/tag/v0.1.1
[0.1.0]: https://github.com/NotYourBurger/CLIIT/releases/tag/v0.1.0
