"""What a handover is: read, write, allocate, order - and the four commands.

An issue says what the work is. A handover says where it currently stands - the
delta one session produced, written by hand at the end of it. The two must not
become the same thing, so the split is a rule and not a style note: the issue is
the durable definition and is edited, a handover is a checkpoint in its
execution and is never edited. A correction is a new handover.

Which is why `create` does not set `in-progress`, does not claim, and does not
touch `blocked_by`. A session blocker is prose about why this session stopped;
`blocked_by: ISS-014` is the project dependency graph, and `in_the_way` stays
the only thing that decides what blocked means.

Where the fields go follows the split the content already has. Frontmatter is
what the tool computed - `id`, `created_at`, `issues`, the git block, `files` -
every one short and comma-safe, the same shape `set_field` already reads back.
The body is what the session said, as `## Heading` sections of prose and `- `
bullets, because those are sentences with commas in them and five more JSON
arrays would spend the promise that these files read fine without the tool.

The four command functions live here rather than in `issues.py`: they are verbs
about handovers, they need nothing from the issue verbs, and `issues.py` imports
`latest_handover` for the one line `issue view` shows. Imports still go one way.
"""

import json
import os
import subprocess
import sys

from cli_issue_tracker.convert_id import next_id
from cli_issue_tracker.fields import SECTIONS
from cli_issue_tracker.fields import set_field
from cli_issue_tracker.validate import require_issues
from cli_issue_tracker.validate import require_items
from cli_issue_tracker.validate import require_prose
from cli_issue_tracker.render import handover_as_dict
from cli_issue_tracker.render import handover_lines
from cli_issue_tracker.render import handover_rows
from cli_issue_tracker.storage import join_file
from cli_issue_tracker.storage import now
from cli_issue_tracker.storage import require_issue_dir
from cli_issue_tracker.storage import split_file

HANDOVERS = "handovers"
PREFIX = "H"

# Git names every changed path; a session that touched a generated directory
# would otherwise write hundreds of lines into a file whose whole point is that
# it is cheap to read. ponytail: a flat cap, no filtering - if the truncation
# ever hides the file that mattered, sort by something better than git's order.
FILE_CAP = 20


def handovers_dir(create=False) -> str:
    """`.issues/handovers/`. Made on demand rather than by `init`, so a repo
    that never writes one never grows an empty directory - and an older repo
    made before this existed needs no migration."""
    path = os.path.join(require_issue_dir(), HANDOVERS)
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def split_sections(body: str) -> dict:
    """The handover body as {heading: text}. `## ` at the start of a line opens
    a section and everything until the next one belongs to it - which is why
    `require_prose` refuses a summary containing such a line. Anything before
    the first heading (the `# Session Handover` title) belongs to no section and
    is dropped, so a hand-edited file can carry a note above them."""
    found, heading = {}, None
    for line in body.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            found[heading] = []
        elif heading is not None:
            found[heading].append(line)
    return {heading: "\n".join(lines).strip() for heading, lines in found.items()}


def join_sections(handover: dict) -> str:
    """The exact inverse of split_sections, plus the title. Empty sections are
    not written - absent means absent here too, and a file of blank headings is
    the shape that makes a reader hunt for the two lines that say something."""
    parts = ["# Session Handover"]
    for key, heading, is_list in SECTIONS:
        value = handover.get(key)
        if not value:
            continue
        text = "\n".join(f"- {item}" for item in value) if is_list else value
        parts.append(f"## {heading}\n\n{text}")
    return "\n\n".join(parts)


def parse_handover(file_path: str) -> dict | None:
    """One handover file as the dict everything else here passes around, or
    None if the file is not one of ours. The frontmatter reader is the issues'
    reader - one implementation of the file format, which is the property
    `test_storage.py` exists to defend."""
    split = split_file(file_path)
    if split is None:
        return None
    fields, body = split
    if not all(key in fields for key in ("id", "created_at")):
        return None

    sections = split_sections(body)
    handover = {
        "id": fields["id"],
        "created_at": fields["created_at"],
        "issues": set_field(fields, "issues"),
        "files": set_field(fields, "files"),
        # Absent outside a repo, and a reader that invented a branch for it
        # would be claiming a fact the session never recorded.
        "git": (
            {
                "branch": fields.get("git_branch", ""),
                "head": fields["git_head"],
                "dirty": fields.get("git_dirty") == "true",
            }
            if "git_head" in fields
            else None
        ),
    }
    for key, heading, is_list in SECTIONS:
        text = sections.get(heading, "")
        handover[key] = (
            [line[2:].strip() for line in text.splitlines() if line.startswith("- ")]
            if is_list
            else text
        )
    return handover


def write_handover(handover: dict) -> str:
    """Write one handover to .issues/handovers/<id>.md. Returns the path.

    No `updated_at` and no overwrite check, unlike `write_issue`: this is called
    once, on a file whose id was allocated a line earlier, and a handover that
    could be rewritten would stop being a checkpoint."""
    fields = {
        "id": handover["id"],
        "created_at": handover["created_at"],
        "issues": ", ".join(handover["issues"]),
    }
    if handover.get("git"):
        git = handover["git"]
        fields["git_branch"] = git["branch"]
        fields["git_head"] = git["head"]
        fields["git_dirty"] = "true" if git["dirty"] else "false"
    if handover.get("files"):
        fields["files"] = ", ".join(handover["files"])

    file_path = os.path.join(handovers_dir(create=True), f"{handover['id']}.md")
    with open(file_path, "w", encoding="utf-8") as md_file:
        md_file.write(join_file(fields, join_sections(handover)))
    return file_path


def load_handovers(issue_id=None) -> list:
    """Every handover on disk, oldest first, optionally only those naming an
    issue. Sorted on (created_at, id) and never on what listdir returned: two
    handovers written in the same second must still order the same way twice, or
    `latest` names a different checkpoint each time it is called - the tie
    `closed_key` already breaks down to the id, for the same reason."""
    path = handovers_dir()
    if not os.path.isdir(path):
        return []
    found = []
    for filename in sorted(os.listdir(path)):
        if not filename.endswith(".md"):
            continue
        handover = parse_handover(os.path.join(path, filename))
        if handover is not None and (issue_id is None or issue_id in handover["issues"]):
            found.append(handover)
    return sorted(found, key=lambda handover: (handover["created_at"], handover["id"]))


def latest_handover(issue_id: str):
    """The newest handover naming this issue, or None. What `issue view` shows
    a line about and what a new session reads first."""
    found = load_handovers(issue_id)
    return found[-1] if found else None


def git_context():
    """(git dict, files) as they are right now, or (None, []) with no repo.

    Read once, at creation, and stored - a `latest` that re-shelled out to git
    would quietly rewrite history every time it was called. Read-only, and a git
    failure costs the git block rather than the handover: the context is worth
    recording either way, which is the same call `require_commits` makes about
    closing without a repo."""

    def git(*args):
        # stdout verbatim, not stripped: `git status --porcelain` puts the
        # staged/unstaged pair in the first two columns and " M a.txt" starts
        # with a space, so stripping the output eats one character of the first
        # path. The callers that want a single line strip it themselves.
        done = subprocess.run(
            ["git", *args], capture_output=True, text=True, encoding="utf-8"
        )
        return done.stdout if done.returncode == 0 else None

    head = git("rev-parse", "--short", "HEAD")
    if head is None:
        return None, []
    head = head.strip()

    status = git("status", "--porcelain") or ""
    files = []
    for line in status.splitlines():
        # `R  old -> new` names two paths and the new one is where the work is.
        path = line[3:].partition(" -> ")[2] or line[3:]
        # `files` is comma-joined like every other id field, so a path with a
        # comma in it cannot be stored. Dropping the path beats corrupting the
        # list - this is navigation, and git itself still knows.
        if path and "," not in path:
            files.append(path)

    return (
        {"branch": (git("rev-parse", "--abbrev-ref", "HEAD") or "").strip(), "head": head,
         "dirty": bool(status.strip())},
        files[:FILE_CAP],
    )


def create_handover(
    ids,
    summary,
    next_action,
    done=(),
    remaining=(),
    decisions=(),
    discoveries=(),
    blockers=(),
    resume_at=None,
):
    """Record where the work stands. Everything is validated first, so a create
    naming an issue that does not exist does not burn an H- id - the rule
    `create_issue` already follows."""
    handover = {
        "issues": require_issues(ids),
        "summary": require_prose(summary, "summary"),
        "next": require_prose(next_action, "next action"),
        "done": require_items(done, "done item"),
        "remaining": require_items(remaining, "remaining item"),
        "decisions": require_items(decisions, "decision"),
        "discoveries": require_items(discoveries, "discovery"),
        "blockers": require_items(blockers, "blocker"),
        # Optional, and not prose - it is a file, a symbol or both, stored
        # without being parsed. Blank is the same as not given.
        "resume_at": (resume_at or "").strip(),
    }
    handover["git"], handover["files"] = git_context()
    handover["created_at"] = now()
    handover["id"] = next_id(handovers_dir(create=True), PREFIX)

    write_handover(handover)
    # No status change, no claim: recording where the work stands is not a
    # claim about what state it is in.
    print(f"Handover {handover['id']} recorded for {', '.join(handover['issues'])}")


def latest_command(id, as_json=False):
    """One handover, the newest for this issue. A lookup that finds nothing is
    exit 1 - grep's contract, the one `next` and `view` already keep."""
    handover = latest_handover(id)
    if handover is None:
        print(f"No handover for {id}", file=sys.stderr)
        sys.exit(1)
    print_handover(handover, as_json)


def list_handovers(id, as_json=False):
    """Every handover for one issue, newest first - the history, read to see how
    the work moved. Nothing found is exit 1 like `latest`: this takes an id, and
    an id that names no checkpoint is a failed lookup, not an empty filter."""
    found = load_handovers(id)[::-1]
    if not found:
        print(f"No handover for {id}", file=sys.stderr)
        sys.exit(1)
    if as_json:
        print(json.dumps([handover_as_dict(handover) for handover in found], indent=2))
        return
    print(f"HANDOVERS FOR {id}")
    print("\n".join(handover_rows(found)))


def view_handover(id, as_json=False):
    """One handover by its own id."""
    path = os.path.join(handovers_dir(), f"{id}.md")
    handover = parse_handover(path) if os.path.isfile(path) else None
    if handover is None:
        print(f"Handover {id} Doesnt Exist", file=sys.stderr)
        sys.exit(1)
    print_handover(handover, as_json)


def print_handover(handover, as_json):
    """The one place a whole handover reaches stdout - two renderings of one
    dict, so `latest` and `view` cannot drift apart."""
    if as_json:
        print(json.dumps(handover_as_dict(handover), indent=2))
    else:
        print("\n".join(handover_lines(handover)))
