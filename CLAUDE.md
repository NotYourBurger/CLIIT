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
`storage.py` (locating `.issues/`, the frontmatter format: `split_file` /
`join_file`, with `parse_issue` / `write_issue` as the issue-shaped wrapper
around them, and the body format: `split_sections`) → `fields.py` (reading one
parsed issue, and the status/priority tuples) → `deps.py` (what blocks what) →
`plan.py` (what a work plan is: the workflow rule, the seed, the reader, and
`git_context`) → `validate.py` (every check that exits before a write) →
`render.py` (every table, line and dict that gets printed). Plus
`check.py` (`validate.py`'s contract pointed the other way - every check that
runs over files already on disk, and the whole of `issue check`; a verb that
holds none of the filtering, blocking or ordering opinions `issues.py` exists
for, so `cli.py` calls it directly the way it already calls `init`),
`convert_id.py` (id allocation) and `init.py`, which imports `plan.rule_text`
to write the workflow rule into `CLAUDE.md` / `AGENTS.md`.

Nothing imports `issues.py`. If something wants to, the thing it wants belongs
in a lower layer — and Python raises on the cycle, so the suite says so at
import time.

`issues.py` is still the one large file on purpose: `list`, `next`, `brief`,
`search`, `view`, `set`, `close`, `claim` and `start` share their filtering, their
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

`plan.py` holds the second artifact: `.issues/work/ISS-NNN.md`, a live record
of where an issue's work stands, seeded by `issue start` and edited by whatever
is doing the work. It has no verbs of its own — `start`, `next`, `view` and
`close` are all issue verbs that happen to read it, which is why they stayed in
`issues.py`. It replaced `handover.py` (ISS-024, deleted in ISS-026); the
handover was written at the end of a session, and sessions end at usage limits
and closed terminals, so twenty-five issues shipped and zero handovers were
written. The rules that are not obvious from the code:

- **A plan is mutable, an issue is not churn.** The issue is the durable
  definition and is edited rarely; the plan is the execution state and is
  edited constantly. An agent whose approach evolves must never be rewriting
  the issue description to record that. `git log --follow` is the audit trail
  for how the plan changed, the same answer this repo already gives for issues.
- **The CLI seeds, the agent edits.** `write_plan` is the only write in
  `plan.py` and it happens once. There is deliberately no `plan check 3` — a
  shell round trip mid-work is a decision point, which is a place to skip, and
  ticking a box has to be cheaper than not ticking it. `start` reads before it
  writes: reseeding over an existing plan is the one unrecoverable thing it
  could do.
- **The reader is built not to need the shape enforced.** `read_plan` never
  raises, ignores headings it does not know, treats a missing section as absent
  rather than empty, and notes an unrecognisable file on stderr instead of
  failing. `bullets` rejoins a wrapped bullet, because a decision worth
  recording is a sentence and a truncated sentence loses the half with the
  reason in it.
- **Git is recomputed at read time and never stored.** The opposite of the
  handover's call, for the opposite reason: a stored HEAD in a live file is a
  lie the moment anything commits. A git failure costs the git block, not the
  output.
- **One constant, two renderings.** `RULE` is the nine-line workflow rule;
  `init` numbers it into the project file and every seeded plan carries
  `RULE[4:8]` as bullets in an HTML comment. Line 8 — do not wait until the end
  of the session — is the behavioural guarantee the whole feature rests on, and
  it lives in the plan file because a rule at the top of `CLAUDE.md` is the
  first thing a long session compacts away.
- **`close` warns and closes anyway.** Unticked checkpoints go to stderr and
  never block the write; the evidence rules already own completeness. The plan
  is never moved or archived — it stays in `work/` as the account of how the
  issue was built.

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

Start substantial work with `issue start ISS-NNN`, which seeds the work plan
described above; keep it ticked as you go rather than at the end.

Features are specified before they are built: `docs/PRD/` holds the PRD,
`.issues/ISS-NNN.md` holds the filed issue, and commits are prefixed with the
issue id (`ISS-019: issue next - the one issue to work on now`). New behaviour
lands with its own `tests/test_<thing>.py` — a script with a `demo()` that
asserts and prints `ok`, using `tests/helpers.py:run()` to capture exit code,
stdout and stderr. README.md is kept in sync as the user-facing spec.

## Work plans

When starting substantial work on an issue:

1. Read the issue and any existing active work plan.
2. If an unfinished plan exists, continue it instead of creating a new one.
3. Otherwise create a work plan before modifying code.
4. Break the work into meaningful checkpoints.
5. Mark each checkpoint complete immediately after completing it.
6. Record important discoveries or decisions as they happen.
7. Keep the Current and Next fields accurate.
8. Do not wait until the end of the session to record progress.
9. Close the issue only when the plan and acceptance criteria are complete.
