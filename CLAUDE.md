# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                                  # install; exposes the `issue` entry point
uv run python tests/all.py               # every check
uv run python tests/test_search.py       # one check (each test file is a standalone script)
uv run python src/cli_issue_tracker/convert_id.py   # convert_id's inline self-check
uv run issue <command>                   # run the CLI without activating the venv
```

There is no linter, formatter or test framework configured. Do not add one.

## What this is

An issue tracker whose entire database is `.issues/*.md` — one Markdown file per
issue, flat `key: value` frontmatter plus a body. Consequences that shape every
change:

- **The file format is the API.** `parse_issue` / `write_issue` in `storage.py`
  must stay exact inverses; a parser bug does not raise, it returns a wrong dict
  that gets written back over the user's prose. `tests/test_storage.py` guards
  this with a deliberately nasty body (second `# ` heading, bare `---` rule,
  fenced code, unicode). Unknown frontmatter keys are preserved on rewrite.
- **Frontmatter has no list type.** `labels` and `blocked_by` are comma-joined
  strings, read back through `set_field()`. So no value may contain a comma —
  that is the whole shared validation in `clean_set()`.
- **Absent means absent.** Issues predating a field have no default invented for
  them: `priority_of` returns `-`, and they match no `--priority` filter. An
  emptied field is popped, not written as `labels:`.
- **git is the audit trail.** `issue log` is `git log --follow` on the file. No
  history is stored in the tool.

## Architecture

`cli.py` (Typer, argument shapes only) → `issues.py` (all behaviour and output)
→ `storage.py` (locating `.issues/`, parse/write) + `convert_id.py` (id
allocation) + `init.py`.

`issues.py` is the one large file on purpose. The pieces worth knowing:

- `select_issues()` is the single filter path — `list` and `search` both go
  through it and get back `(issues, by_id)`. `by_id` is every issue on disk, not
  just the matches, because blocker status is a fact about files the filter
  threw away.
- `in_the_way()` is the only function that decides what "blocked" means;
  `is_ready` (= open + unblocked) and `actionable` (= not closed + unblocked,
  what `next` uses) are both built on it. Do not grow a third opinion.
- `rank` (list, least-urgent-first so the terminal reads bottom-up) and
  `next_rank` (`next`, most-urgent-first) are the same `STATUSES` / `PRIORITIES`
  tuples read in opposite directions. `next_rank` breaks every tie down to the
  id so repeated calls are deterministic.
- Dependencies are stored on the blocked issue only (`blocked_by`). The reverse
  direction (`blocks`) is always derived. One fact, one place.

## Conventions this repo already holds to

- **stdout parses, stderr explains.** Every diagnostic, warning and "no match"
  line goes to stderr so `--json` output stays clean.
- **Exit codes carry meaning.** A filter matching nothing is exit 0 (`list`); a
  lookup finding nothing is exit 1 (`search`, `view`, `next`, missing id) — grep's
  contract. A batch `set` with one bad id still writes the good ones, then exits 1.
- **Validate before writing.** Bad status/priority/blocker exits before anything
  touches disk; a rejected `create` must not burn an id.
- **UTF-8 everywhere, explicitly.** This machine defaults to cp1252 and the same
  bug landed three times. Every `open()` and `subprocess.run(text=True)` must pass
  `encoding="utf-8"`; `tests/test_encoding.py` walks the source with `ast` and
  fails on any new one.
- **Comments explain why, not what.** The existing prose in `issues.py` and
  `storage.py` records rejected alternatives. Match that register; don't strip it.
- Deliberate shortcuts with a known ceiling are marked `ponytail:` with the
  upgrade path.

## Environment knobs

`ISSUES_DIR` (skip the walk-up entirely), `ISSUE_PREFIX` (id letters, read only
by `create`), `ISSUE_USER` (who `claim` acts as). Every command except `init`
finds `.issues/` by walking up from the cwd, git-style; `init` is deliberately
local.

## Working in this repo

Features are specified before they are built: `docs/PRD/` holds the PRD,
`.issues/ISS-NNN.md` holds the filed issue, and commits are prefixed with the
issue id (`ISS-019: issue next - the one issue to work on now`). New behaviour
lands with its own `tests/test_<thing>.py` — a script with a `demo()` that
asserts and prints `ok`, using `tests/helpers.py:run()` to capture exit code,
stdout and stderr. README.md is kept in sync as the user-facing spec.
