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
issue list                          # every issue, grouped by status
issue list open                     # only one status: in-progress, open or closed
issue view ISS-001                  # render the issue as formatted Markdown
issue set ISS-001 ISS-002 closed    # set the status of one or more issues
```

Statuses are `in-progress`, `open` and `closed`. `issue list` groups them in that
order with a rule between groups, so what you are working on stays at the top.

## File format

Each issue is one Markdown file with YAML-style frontmatter:

```markdown
---
id: ISS-001
status: open
created_at: 2026-09-04T14:04:43+06:00
---

# List View for the Issue Tracker

Running `issue list` should print every issue in the repo as an aligned table.
```

Everything below the frontmatter is yours — headings, tables, code fences and
horizontal rules all survive a read/write round trip. Ids are allocated as one
past the highest existing `ISS-NNN`, so deleting an issue never reuses a live id.

## Layout

| File            | Owns                                                   |
| --------------- | ------------------------------------------------------ |
| `cli.py`        | Typer commands                                         |
| `issues.py`     | what each command does and how output looks            |
| `storage.py`    | where issues live on disk and the file format          |
| `convert_id.py` | allocating the next `ISS-NNN`                          |
| `init.py`       | creating `.issues/`                                    |

## Status

Working: `init`, `create`, `list`, `view`, `set`.
