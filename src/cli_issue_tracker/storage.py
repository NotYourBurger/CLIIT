import os
import sys
from datetime import datetime

ISSUES_DIR = ".issues"

def now() -> str:
    """The one timestamp format on disk - local time, second precision."""
    return datetime.now().astimezone().isoformat(timespec="seconds")

def issues_dir() -> str:
    return os.path.join(os.getcwd(), ISSUES_DIR)

def require_issue_dir() -> str:
    """The .issues/ path, or exit 1. Nothing this tool does works without the
    directory, so failing here rather than returning None means every command
    reports the failure in its exit code instead of returning 0 with no output -
    which is what a script piping --json needs to see. stderr for the same
    reason: stdout is what the parser reads."""
    path = issues_dir()
    if not os.path.isdir(path):
        print("Please Run - issue init - to initialize the project first", file=sys.stderr)
        sys.exit(1)
    return path

def parse_issue(file_path: str) -> dict | None:
    """Read one issue file back into a dict. Returns None if it isn't a valid issue."""
    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.read().splitlines()

    # Frontmatter is only ever the block at the very top, fenced by the first
    # two --- lines. Find where it ends, then never look at those markers again -
    # a --- further down is a horizontal rule in the description, not a fence.
    if not lines or lines[0] != "---":
        return None
    try:
        fence = lines.index("---", 1)
    except ValueError:
        return None

    issue = {}
    for line in lines[1:fence]:
        key, _, value = line.partition(":")
        issue[key.strip()] = value.strip()

    # body is the file minus the frontmatter, verbatim - that is what the viewer
    # shows. title is pulled out separately because the list needs it as a column.
    body = lines[fence + 1 :]
    issue["body"] = "\n".join(body).strip()
    for i, line in enumerate(body):
        if line.startswith("# "):
            issue["title"] = line[2:].strip()
            break

    # A file missing any of these isn't an issue we wrote - skip it. updated_at
    # is deliberately not required: files written before it existed don't have
    # one, and requiring it would drop them out of `issue list` entirely.
    if not all(k in issue for k in ("id", "status", "created_at", "title")):
        return None
    return issue

def write_issue(issue: dict) -> str:
    """Write an issue dict to .issues/<id>.md. Returns the path."""
    path = require_issue_dir()

    # Every write is a change, and every change goes through here, so this is
    # the one place the clock is read. Mutates the caller's dict so it matches
    # what just landed on disk.
    issue["updated_at"] = now()

    # The exact inverse of parse_issue - every frontmatter key back out, same
    # fence, same body. Change one and you must change the other, which is why
    # they live together. The four known keys keep their documented order;
    # anything else a human added to the file follows, rather than being
    # dropped on the next rewrite. "title" is derived from the body heading,
    # not a frontmatter field, so it is not written back.
    known = ("id", "status", "created_at", "updated_at")
    fields = [f"{key}: {issue[key]}" for key in known]
    fields += [
        f"{key}: {value}"
        for key, value in issue.items()
        if key not in known + ("title", "body")
    ]
    frontmatter = "\n".join(fields)

    content = f"""---
{frontmatter}
---

{issue["body"]}
"""

    file_path = os.path.join(path, f"{issue['id']}.md")
    with open(file_path, "w", encoding="utf-8") as md_file:
        md_file.write(content)
    return file_path


def read_issue(id: str) -> dict | None:
    path = require_issue_dir()
    file_name = f"{id}.md"
    file_path = os.path.join(path,file_name)
    if os.path.isfile(file_path):
        return parse_issue(file_path)
    else:
        return None
       