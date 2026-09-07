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
  that is the whole shared validation in `clean_set()`. `evidence` is the one
  exception and holds a JSON array: a `--test` command has commas in it, and
  `partition(":")` keeps the whole rest of the line, so it round trips. It is
  deliberately the only ugly line in the file; `issue view` pays it back by
  rendering a Resolution block.
- **Absent means absent.** Issues predating a field have no default invented for
  them: `priority_of` returns `-`, and they match no `--priority` filter. An
  emptied field is popped, not written as `labels:`.
- **git is the audit trail.** `issue log` is `git log --follow` on the file. No
  history is stored in the tool.

## Architecture

`cli.py` (Typer, argument shapes only) → `issues.py` (the commands) → five
layers under them, imported in this order and never the other way:
`storage.py` (locating `.issues/`, and the frontmatter format: `split_file` /
`join_file`, with `parse_issue` / `write_issue` as the issue-shaped wrapper
around them) → `fields.py` (reading one parsed issue, the status/priority
tuples, and the handover `SECTIONS` table) → `deps.py` (what blocks what) →
`validate.py` (every check that exits before a write) → `render.py` (every
table, line and dict that gets printed) → `handover.py` (what a handover is,
plus its own four commands). Plus `convert_id.py` (id allocation) and
`init.py`.

Nothing imports `issues.py`. If something wants to, the thing it wants belongs
in a lower layer — and Python raises on the cycle, so the suite says so at
import time.

`issues.py` is still the one large file on purpose: `list`, `next`, `brief`,
`search`, `view`, `set`, `close` and `claim` share their filtering, their
blocking rule and their ordering, and a module per verb would give each verb a
private copy of an opinion this repo has exactly one of. The split was the
other way — the layers under the verbs, not the verbs. The pieces worth
knowing:

- `select_issues()` is the single filter path — `list` and `search` both go
  through it and get back `(issues, by_id)`. `by_id` is every issue on disk, not
  just the matches, because blocker status is a fact about files the filter
  threw away.
- `in_the_way()` is the only function that decides what "blocked" means;
  `is_ready` (= open + unblocked) and `actionable` (= not closed + unblocked,
  what `next` uses) are both built on it. Do not grow a third opinion.
- `close_issue()` is the only thing that writes `status: closed`; `set_fields`
  refuses the word and says so. Everything is validated before the write, and
  the "ISS-012 is now ready" cascade lives there, because closing is now the
  only thing that frees a blocked issue.
- `rank` (list, least-urgent-first so the terminal reads bottom-up) and
  `next_rank` (`next`, most-urgent-first) are the same `STATUSES` / `PRIORITIES`
  tuples read in opposite directions. `next_rank` breaks every tie down to the
  id so repeated calls are deterministic.
- Dependencies are stored on the blocked issue only (`blocked_by`). The reverse
  direction (`blocks`) is always derived. One fact, one place.

`handover.py` holds the second artifact: `.issues/handovers/H-NNN.md`, an
append-only checkpoint saying where an issue's work stands. It keeps its own
four verbs rather than adding them to `issues.py` — they share nothing with the
issue verbs, and `issues.py` imports `latest_handover` for the one line
`issue view` prints. The rules that are not obvious from the code:

- **A handover is not a small issue.** The issue is the durable definition and
  is edited; a handover is never edited, a correction is a new one. So `create`
  does not set `in-progress`, does not claim, and does not touch `blocked_by` —
  a `--blocker` is prose about why the session stopped, and `in_the_way` stays
  the only thing that decides what blocked means.
- **Frontmatter is what the tool computed, the body is what the session said.**
  `done`, `remaining`, `decisions`, `discoveries` and `blockers` are lists of
  sentences, and sentences have commas, so the comma-joined trick is out and
  five more `evidence`-style JSON lines would spend the promise that these
  files read fine in a diff. They are `## Heading` sections of `- ` bullets
  instead, which costs the body parser in `split_sections` / `join_sections` —
  exact inverses, guarded by `tests/test_handover.py` the way `test_storage.py`
  guards the issue body.
- **Git is read at creation and stored, never recomputed.** A `latest` that
  re-shelled out to git would rewrite history every time it was called. A git
  failure loses the git block, not the handover.
- **Ordering is `(created_at, id)`,** never what `listdir` returned, so two
  calls to `latest` cannot name different checkpoints.

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
- **Comments explain why, not what.** The existing prose across `issues.py`,
  `storage.py` and the four layers records rejected alternatives, and each
  module's docstring is the paragraph that covers the whole file. Match that
  register; don't strip it.
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
