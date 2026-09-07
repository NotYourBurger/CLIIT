import os
import sys
from datetime import datetime

ISSUES_DIR = ".issues"

# The keys that keep their documented order at the top of every file; anything
# a human added follows. One copy, because `check` compares a file against what
# `write_issue` would produce, and a second copy of this tuple is a false
# finding on every issue in the repo the day one of them is edited.
FIELD_ORDER = ("id", "status", "created_at", "updated_at")

def id_prefix() -> str:
    """The letters in front of every id. One source, read by next_id when it
    allocates and by nothing else - list, view, set and log all work off the
    filename or the frontmatter, so they never need to know it. Configured the
    way the directory is, by environment variable, because that is the knob
    this tool already has and a second mechanism for one string is not worth
    it. Changing it mid-project is safe: existing issues keep their own prefix
    and still list, and numbering restarts under the new one without colliding
    on disk."""
    return os.environ.get("ISSUE_PREFIX", "ISS")

def now() -> str:
    """The one timestamp format on disk - local time, second precision."""
    return datetime.now().astimezone().isoformat(timespec="seconds")

def local_issues_dir() -> str:
    """The .issues/ right here, without walking up - what `issue init` creates."""
    return os.environ.get("ISSUES_DIR") or os.path.join(os.getcwd(), ISSUES_DIR)

def issues_dir() -> str:
    """The .issues/ every command reads: $ISSUES_DIR, else the nearest one at or
    above the cwd. Walking up is what makes the tool work from a subdirectory,
    the way git finds .git and cargo finds Cargo.toml - resolving it from the cwd
    alone meant one `cd src` and the tracker was gone. It walks past a .git
    boundary on purpose: a .issues/ further up is still the tracker you meant,
    and there is no case yet that wants two. With none anywhere it returns the
    local path, so require_issue_dir still reports the same 'run issue init'."""
    if "ISSUES_DIR" in os.environ:
        return os.environ["ISSUES_DIR"]
    path = os.getcwd()
    while True:
        candidate = os.path.join(path, ISSUES_DIR)
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(path)
        # At the filesystem root dirname stops changing - that is the stop, not
        # a path comparison against "/" that is wrong on Windows.
        if parent == path:
            return local_issues_dir()
        path = parent

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

def split_file(file_path: str) -> tuple[dict, str] | None:
    """One frontmatter file as (fields, body), or None if it has no frontmatter.

    This is the file format with nothing issue-shaped left in it: parse_issue
    is this plus its required keys. Written out because a second frontmatter
    reader beside the first is how the two start disagreeing about what a
    `---` means."""
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

    fields = {}
    for line in lines[1:fence]:
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, "\n".join(lines[fence + 1 :]).strip()


def join_file(fields: dict, body: str, first=()) -> str:
    """The exact inverse of split_file. Change one and you must change the
    other, which is why they live together.

    `first` is the handful of keys that keep their documented order at the top;
    anything else a human added to the file follows, rather than being dropped
    or reshuffled on the next rewrite."""
    ordered = [f"{key}: {fields[key]}" for key in first if key in fields]
    ordered += [f"{key}: {value}" for key, value in fields.items() if key not in first]
    frontmatter = "\n".join(ordered)
    return f"""---
{frontmatter}
---

{body}
"""


def parse_issue(file_path: str) -> dict | None:
    """Read one issue file back into a dict. Returns None if it isn't a valid issue."""
    split = split_file(file_path)
    if split is None:
        return None
    issue, body = split

    # body is the file minus the frontmatter, verbatim - that is what the viewer
    # shows. title is pulled out separately because the list needs it as a column.
    issue["body"] = body
    for line in body.splitlines():
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

    # "title" is derived from the body heading, not a frontmatter field, so it
    # is not written back.
    fields = {key: value for key, value in issue.items() if key not in ("title", "body")}
    content = join_file(fields, issue["body"], first=FIELD_ORDER)

    # newline="\n" for the same reason encoding="utf-8" is here: text mode
    # takes a platform default, and on this one "\n" leaves as "\r\n". The file
    # format is the API and its bytes are part of it - a tool writing CRLF
    # beside an agent's editor writing LF is a diff on every line of a file
    # nobody touched, and `join_file` already committed to "\n". Reads stay
    # translated on purpose, so a hand-edited CRLF file still parses.
    file_path = os.path.join(path, f"{issue['id']}.md")
    with open(file_path, "w", encoding="utf-8", newline="\n") as md_file:
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
       

def split_sections(body: str) -> dict:
    """A Markdown body as {heading: text}. `## ` at the start of a line opens a
    section and everything until the next one belongs to it.

    The second half of this file's job: `split_file` is the frontmatter format,
    this is the body format. Anything before the first heading - a title, an
    HTML comment - belongs to no section and is dropped, so a hand-edited file
    can carry a note above them. It never raises and never rejects: a plan is
    written by whatever is editing it, and a reader that could refuse one would
    be a reader an agent can break by adding a paragraph."""
    found, heading = {}, None
    for line in body.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            found[heading] = []
        elif heading is not None:
            found[heading].append(line)
    return {heading: "\n".join(lines).strip() for heading, lines in found.items()}
