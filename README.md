# cli-issue-tracker

A small issue tracker that lives in your repo. Issues are plain Markdown files
in a `.issues/` folder, so they version with your code and read fine without
the tool.

## Install

```bash
uv sync
```

## Usage

```bash
issue init                          # create .issues/ in the current directory
issue create "Title" "Description"  # write .issues/ISS-001.md
issue create "Title" "..." --priority high   # high, medium (default) or low, -p for short
issue create "Title" "..." -l bug -l auth    # labels, repeat the flag for more
issue list                          # every issue, grouped by status
issue list open                     # only one status: in-progress, open or closed
issue list --priority high          # only one priority; combines with a status
issue list --label bug              # only issues with every label given
issue list --ready                  # open, and nothing open is in the way
issue list --blocked                # stuck, and what on
issue search "verification email"   # every issue whose body or title has both words
issue search auth --status open -p high   # the same filters list takes, ANDed with the query
issue view ISS-001                  # render the issue as formatted Markdown
issue set ISS-001 ISS-002 closed    # set the status of one or more issues
issue set ISS-001 --priority high   # set the priority instead, or alongside a status
issue set ISS-001 -l backend -L bug # add a label, remove a label, in one write
issue set ISS-012 -b ISS-009        # ISS-012 cannot start until ISS-009 closes
issue set ISS-012 -B ISS-009        # never mind (--blocked-by and --unblock in long form)
issue log ISS-001                   # the issue's git history: who changed it, when, why
```

Statuses are `in-progress`, `open` and `closed`. `issue list` groups them with a
rule between groups and prints them least urgent first — closed, then open, then
in-progress — with the highest priority last inside each group. The list reads
bottom-up on purpose: the last line printed sits right above the prompt, which
is where you are already looking, so what needs attention is there and the
closed pile is what scrolls away.

Priorities are `high`, `medium` and `low`, stored as a `priority` frontmatter
field. They filter, they show in a column, and they are the second sort term
under status — highest last. Issues filed before the field existed have no
priority: they show `-`, they sort to the top as the least urgent thing there
is, and they match no `--priority` filter rather than being counted as
`medium`.

Labels say what kind of issue it is — `bug`, `auth`, `docs`, whatever you
invent. They are stored as one comma-joined `labels` field, lowercased, deduped
and sorted, so a label cannot contain a comma; no labels means no field at all.
`--label` on `set` adds and `--unlabel` (`-L`) removes, because a label is
something you learn about an issue after filing it. Removing the last one takes
the field with it.

`issue list --label bug --label auth` wants both, not either: repeating a filter
narrows, the way adding `--priority` to a status does. The LABELS column shows
up only when something has labels, and it is last, so a long label set cannot
push another column off the screen. `--json` is the one place the output is not
a literal transcript of the file — labels come out as an array, so nothing
downstream has to split the string again.

`issue search` is `list` narrowed by words: split on whitespace, all of them
required, case-insensitive, as substrings, anywhere in the title or the body —
so `auth` finds `authentication`, and `"verification email"` finds
"verification of the email" that a phrase search would miss. Deliberately not
regex, fuzzy matching or ranking. It takes the same `--status`, `--priority` and
`--label` filters as `list`, ANDed with the query and each other, and prints the
same table in the same order, plus **the line each match came from** indented
under the row — the thing `list` cannot show. A title-only match adds no line,
because the TITLE column is already it.

Nothing matched is exit 1, `--json` or not, with the query named on stderr so
stdout stays parseable — that is `grep`'s contract, so
`issue search "verification" || issue create "..."` works. It differs from
`issue list closed` printing "No closed issues" at exit 0 on purpose: a filter
finding nothing is a fact about the repo, a lookup finding nothing failed.
`search --json` is the `list --json` array with a `matches` array added per
issue, so an agent never has to re-read the files to find out why something
matched. Because the query is `search`'s positional argument, its status is the
`--status` flag — and `list` accepts `--status open` as a second spelling of its
trailing word, so the two commands do not disagree about how you name a status.

Dependencies say what blocks what — the question `--priority` cannot answer,
because the highest priority open issue is very often the one nobody can touch.
`--blocked-by` (`-b`) adds a blocker and `--unblock` (`-B`) removes one, the same
add/remove pair as `--label`, stored as one comma-joined `blocked_by` field —
**on the blocked issue only**. "A blocks B" and "B is blocked by A" are one fact,
and storing it twice means the first hand-edit or deleted file leaves two copies
disagreeing with nothing able to decide which is true. The other direction is
derived by reading the others, which every command already does. It also degrades
the right way: delete the blocker and the stuck issue still says what it was
waiting for.

An unknown id, an issue blocking itself, or a cycle is exit 1 with nothing
written — and a cycle prints the path, `ISS-012 -> ISS-009 -> ISS-004 ->
ISS-012`, because "cycle detected" sends you off to read four files to find the
edge to drop. `--unblock` is the one that does *not* require the id to exist: a
blocker whose file was deleted is exactly the one you need to remove.

`issue list --ready` is open with every blocker closed — the standup question,
and `issue list --ready --json` is an agent's whole "what do I pick up next" in
one call. Direct blockers only, not transitive: if someone closed B while C was
still open, B is done because a person said so, and B's blockers stopped being
A's problem then. A **missing** blocker never blocks either — it can never be
closed, so counting it would strand the issue forever; it prints as
`ISS-042 (missing)` instead, which is louder and points at the repair.

Blocked issues get a `blocked by ISS-009 (open)` line indented under the row —
the same mechanism `search` uses for a match line, so there is no new column, and
it shows on plain `issue list` too. A blocked row that looks identical to a ready
one is the thing this exists to fix; `--ready` is the filter that takes them
away. `view` shows both directions with each blocker's status. `--json` grows
`blocked_by`, `blocks` and `ready` on every issue — `blocks` and `ready` are
stored in no file, but the consumer wants the fact, not the storage.

Being blocked does not forbid anything: `issue set ISS-012 in-progress` prints
what is in the way on stderr and then does it. A tracker that refuses is one
people stop telling the truth to — the first time it is wrong about a dependency
someone deletes the field rather than argue with it, and a graph people route
around is worse than no graph. Closing the last blocker reports what it freed on
the same run, one line per issue, id first: `ISS-012 is now ready`.

`issue set` takes any of a status, a `--priority`, a `--label`/`--unlabel`, or
all of them — `issue set ISS-001 closed --priority low -l bug` is one write, and
it reports only what actually moved. The status stays a bare trailing word so
the old form keeps working; a word that is not a status is read as an id, so a
mistyped one gets told which words `set` accepts instead of being written.

Every command except `init` finds `.issues/` by walking up from the current
directory, the way `git` finds `.git`, so they all work from anywhere in the
repo. `init` is deliberately local — it creates `.issues/` right where you are,
and warns if there is already one above it. Set `ISSUES_DIR` to point the tool at
a specific directory and skip the walk entirely.

Ids are `ISS-001`, `ISS-002` and so on. Set `ISSUE_PREFIX` to use different
letters — `ISSUE_PREFIX=BUG issue create ...` files `BUG-001.md`. Only `create`
reads it; everything else works off the filename, so issues filed under an old
prefix keep listing and numbering restarts under the new one instead of
continuing across both.

## File format

Each issue is one Markdown file with YAML-style frontmatter:

```markdown
---
id: ISS-001
status: open
created_at: 2026-09-04T14:04:43+06:00
priority: medium
labels: bug, frontend
blocked_by: ISS-009
---

# List View for the Issue Tracker

Running `issue list` should print every issue in the repo as an aligned table.
```

Everything below the frontmatter is yours — headings, tables, code fences and
horizontal rules all survive a read/write round trip. Frontmatter fields the tool
does not know about are kept too, so you can add your own by hand. Ids are
allocated as one past the highest existing id with the same prefix, so deleting
an issue never reuses a live id.

## Layout

| File            | Owns                                                   |
| --------------- | ------------------------------------------------------ |
| `cli.py`        | Typer commands                                         |
| `issues.py`     | what each command does and how output looks            |
| `storage.py`    | finding `.issues/`, and the file format                 |
| `convert_id.py` | allocating the next id                                 |
| `init.py`       | creating `.issues/` here, and only here                |
| `tests/`        | one script per thing that can break, plus the runner   |

`issue log` is `git log --follow` pointed at the issue file — the history comes
free from issues being files. Uncommitted edits are invisible to git, so it says
so rather than looking like nothing changed.

## Status

Working: `init`, `create`, `list`, `search`, `view`, `set`, `log`.

Run every check with `uv run python tests/all.py`. They live in `tests/`, one
file per thing that can break:

| Check                | Covers                                                     |
| -------------------- | ---------------------------------------------------------- |
| `test_storage.py`    | the file format, parse → write → parse round trips          |
| `test_log.py`        | `issue log` against a throwaway git repo                    |
| `test_priority.py`   | priority, and the issues that predate the field             |
| `test_labels.py`     | labels, the first field that merges instead of replacing    |
| `test_search.py`     | matching, the filters that AND with it, and the exit code   |
| `test_blockers.py`   | dependencies: one stored side, two read, and the bad edges  |
| `test_encoding.py`   | that nothing reads or writes text at the locale default     |

No framework: each file is a script with a `demo()` that asserts and prints
`ok`, so `uv run python tests/test_search.py` runs one on its own and the
runner is a `for` loop over the rest. It runs each in its own subprocess —
these tests `chdir` and set `ISSUES_DIR`, and one process would let the first
skipped cleanup break the next file and blame the wrong one. One failure does
not stop the others; the exit code counts them. `tests/helpers.py` holds the
two things they all wanted: `run()`, which calls a command and hands back its
exit code, stdout and stderr, and `REPO`.

`test_encoding.py` exists because the same mistake landed three times: this machine
defaults to cp1252, so anything reading or writing text without being told
UTF-8 mangles accents quietly and still exits 0. It parses the source and fails
on any `open()` or `subprocess` call that takes the locale default, rather than
waiting for a fourth bug report.
