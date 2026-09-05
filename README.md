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
issue view ISS-001                  # render the issue as formatted Markdown
issue set ISS-001 ISS-002 closed    # set the status of one or more issues
issue set ISS-001 --priority high   # set the priority instead, or alongside a status
issue set ISS-001 -l backend -L bug # add a label, remove a label, in one write
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

`issue log` is `git log --follow` pointed at the issue file — the history comes
free from issues being files. Uncommitted edits are invisible to git, so it says
so rather than looking like nothing changed.

## Status

Working: `init`, `create`, `list`, `view`, `set`, `log`.

Run the checks with `uv run python test_storage.py` (file format round trips),
`uv run python test_log.py` (`issue log` against a throwaway git repo),
`uv run python test_priority.py` (priority, and the issues that predate it),
`uv run python test_labels.py` (labels, the first field that merges instead of
replacing) and `uv run python test_encoding.py`.

That last one exists because the same mistake landed three times: this machine
defaults to cp1252, so anything reading or writing text without being told
UTF-8 mangles accents quietly and still exits 0. It parses the source and fails
on any `open()` or `subprocess` call that takes the locale default, rather than
waiting for a fourth bug report.
