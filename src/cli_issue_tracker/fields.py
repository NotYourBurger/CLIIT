"""Reading one parsed issue: the fields, and the words the fields may hold.

Pure functions of the dict `parse_issue` returns - no disk, no printing. This
is where "absent means absent" lives: an issue written before a field existed
has no value for it and none is invented, which is why the getters return "-"
and the setters elsewhere pop rather than write an empty line.
"""

import json
import os
import subprocess
import sys


STATUSES = ("in-progress", "open", "closed") ## Ordering
STATUS_ORDER = STATUSES[::-1]  # least urgent first: closed, open, in-progress


PRIORITIES = ("high", "medium", "low")
PRIORITY_ORDER = ("-",) + PRIORITIES[::-1]  # no priority, then low, medium, high


# Exactly one of these per close. Three of them cost a word and a sentence;
# `completed` is the one with a precondition, and that precondition is the
# whole feature - without it `completed` decays back into "someone said so".
REASONS = ("completed", "not-planned", "duplicate", "superseded")

# What `set` may still write. Closing goes through `issue close`, but "closed"
# stays in STATUSES so a trailing "closed" is still read as a status and gets
# the sentence that names the right command, instead of being taken for an id.
SETTABLE = tuple(status for status in STATUSES if status != "closed")


# The body of a handover file, and the JSON keys, in one table: the heading a
# section is written under, and whether it is a list of `- ` lines or prose.
# One table rather than a writer and a reader that each know the order - they
# have to be exact inverses, which is the property test_handover.py defends.
SECTIONS = (
    ("summary", "Summary", False),
    ("done", "Done", True),
    ("remaining", "Remaining", True),
    ("decisions", "Decisions", True),
    ("discoveries", "Discoveries", True),
    ("blockers", "Blockers", True),
    ("resume_at", "Resume At", False),
    ("next", "Next", False),
)


def priority_of(issue):
    """What to show and filter on. Missing stays missing - the issues written
    before this field existed never had a priority, and calling those "medium"
    would invent a decision nobody made."""
    return issue.get("priority", "-")


def assignee_of(issue):
    """Who owns it, or "-" for nobody. Same shape as priority_of, for the same
    reason: the reader is scanning a column and an empty cell reads as a
    rendering bug."""
    return issue.get("assignee", "-")


def current_user():
    """Who `claim` acts as when --by is not given: $ISSUE_USER, then
    `git config user.name`, then nothing.

    The name is a string this tool does not verify and cannot: an issue is a
    file in a git repo, anyone who can write the file can write any name into
    it. The audit trail already exists and is better - `issue log` says who
    committed the change. The environment variable is the knob this tool
    already has twice over, and it is what an agent sets once at the top of a
    run rather than threading a name through every call."""
    who = os.environ.get("ISSUE_USER", "").strip()
    if who:
        return who
    git = subprocess.run(
        ["git", "config", "user.name"], capture_output=True, text=True, encoding="utf-8"
    )
    return git.stdout.strip()


def set_field(issue, field):
    """A comma-joined frontmatter field as a list. Flat frontmatter has no list
    type, so the file holds one string and this is the only place that knows
    it. Absent, empty and blank all read back as nothing."""
    return [word.strip() for word in issue.get(field, "").split(",") if word.strip()]


def labels_of(issue):
    """The labels field as a list."""
    return set_field(issue, "labels")


def blockers_of(issue):
    """The blocked_by field as a list of ids - the second comma-joined set
    field, stored on the issue that is stuck. One side of the edge only; the
    other direction is derived, because one fact stored twice is two copies to
    disagree the first time someone hand-edits a file."""
    return set_field(issue, "blocked_by")


def evidence_of(issue):
    """The typed evidence behind a close, as a list of `{type, value}`.

    Frontmatter has no list type, and the two fields that already wanted one -
    labels, blocked_by - comma-join instead, which is why neither may contain a
    comma. A test command may, so that trick does not stretch here and
    pretending it does is how someone's --test string gets cut in half. The
    line holds a JSON array instead: `partition(":")` keeps the whole rest of
    the line, so it round trips through the existing reader and writer
    untouched, no value is restricted, and the type survives - which is what
    --json needs and what a second `key: value` per type would lose.

    It is the one ugly line in a file we promise reads fine without the tool.
    `issue view` rendering a real Resolution block is what pays that back.

    A hand-edited line that is not JSON reads as no evidence and says so on
    stderr, rather than taking `view` down or, worse, being written back wrong."""
    try:
        return json.loads(issue.get("evidence", "[]"))
    except json.JSONDecodeError:
        print(
            f"{issue['id']}: evidence is not readable JSON - ignoring it",
            file=sys.stderr,
        )
        return []


def resolution_of(issue):
    """Why this issue stopped being active, or None for one closed before any
    of this existed. Absent stays absent - no reason is invented for old files
    and none of them is rewritten, the same rule the issues predating `priority`
    live by."""
    if "reason" not in issue:
        return None
    return {
        "reason": issue["reason"],
        "closed_at": issue.get("closed_at", ""),
        "message": issue.get("message", ""),
        "evidence": evidence_of(issue),
    }


def evidence_label(kind):
    """`pr` is the only type whose name is not a word; the rest are their own
    label with the hyphen spelled out."""
    return "PR" if kind == "pr" else kind.replace("-", " ").capitalize()
