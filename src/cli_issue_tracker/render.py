"""Turning issues into characters.

Every table, line and dict the commands print is built here, which is what
makes "stdout parses, stderr explains" checkable by reading one file instead of
grepping for `print`. Nothing in here decides anything: the values come from
`fields` and `deps`, and a rendering that re-derives one is how two commands
start naming different issues.

`as_dict` is the --json rendering and sits beside the human ones on purpose -
one model, two renderings, so they cannot drift.

`view` still builds its own rich Table in issues.py; moving that is a rewrite
of the command rather than a move, and it gets its own issue.
"""

from rich.console import Console
from rich.theme import Theme

from cli_issue_tracker.fields import assignee_of
from cli_issue_tracker.fields import blockers_of
from cli_issue_tracker.fields import labels_of
from cli_issue_tracker.fields import priority_of
from cli_issue_tracker.fields import resolution_of
from cli_issue_tracker.plan import SECTIONS as PLAN_SECTIONS
from cli_issue_tracker.deps import blocked_note
from cli_issue_tracker.deps import blocks
from cli_issue_tracker.deps import is_ready


THEME = Theme(
    {
        "markdown.h1": "bold bright_white",
        "markdown.h2": "bold bright_cyan",
        "markdown.h3": "bold cyan",
        "markdown.h4": "bold",
        "markdown.item.bullet": "bold cyan",
    }
)

console = Console(theme=THEME)


def describe(fields):
    """`{"status": "closed", "priority": "high"}` as "closed, priority high" -
    status reads as itself, the others need the word to make sense. Labels are
    bracketed because their value has commas in it and the fields are joined
    with commas too."""
    said = []
    for field, value in fields.items():
        if field == "status":
            said.append(value)
        elif field == "labels":
            said.append(f"labels [{value}]" if value else "no labels")
        elif field == "blocked_by":
            said.append(f"blocked by [{value}]" if value else "not blocked")
        elif field == "assignee":
            # Possessive, not "assigned to X" - "set to assigned to X" reads
            # badly, and this is the wording `claim` already prints.
            said.append(f"{value}'s" if value else "unassigned")
        else:
            said.append(f"{field} {value}")
    return ", ".join(said)


# name, value, and what "nothing here" looks like. A column with a blank is
# conditional - it disappears when every row in the result is blank, so a repo
# that does not use the field does not pay a column for it. None means always.
COLUMNS = (
    ("ID", lambda issue: issue["id"], None),
    ("TITLE", lambda issue: issue["title"], None),
    ("STATUS", lambda issue: issue["status"], None),
    ("PRIORITY", priority_of, None),
    ("CREATED AT", lambda issue: issue["created_at"], None),
    ("ASSIGNEE", assignee_of, "-"),
    ("LABELS", lambda issue: ", ".join(labels_of(issue)), ""),
)


def print_table(issues, notes=None):
    """The list, as aligned columns. Each column is as wide as its widest
    value, so nothing is truncated; the last one is not padded, so a long
    value there cannot push anything off the terminal. That is why LABELS is
    last - it is the column with no bound on its width, and a repo that does
    not use labels does not get an empty column at all."""
    columns = [
        (name, value)
        for name, value, blank in COLUMNS
        if blank is None or any(value(issue) != blank for issue in issues)
    ]
    widths = [
        max(len(name), *(len(value(issue)) for issue in issues)) + 2 for name, value in columns
    ]

    def row(cells):
        # The last cell is printed as-is: padding it would only add trailing
        # spaces, and it is the one column allowed to run long.
        padded = [f"{cell:<{width}}" for cell, width in zip(cells[:-1], widths)]
        # rstrip: an issue with no labels would otherwise end in the padding of
        # the column before it.
        return ("".join(padded) + cells[-1]).rstrip()

    print(row([name for name, _ in columns]))

    rule = "-" * (sum(widths[:-1]) + max(len(columns[-1][1](issue)) for issue in issues))
    previous = None
    for issue in issues:
        # Not on the first row: previous is None only before anything is printed.
        if previous is not None and issue["status"] != previous:
            print(rule)
        print(row([value(issue) for _, value in columns]))
        # Indented under the row rather than in a column: these lines have no
        # bound on their length and there can be several of them, which is the
        # one shape a table cannot hold.
        for line in (notes or {}).get(issue["id"], ()):
            print(f"    {line}")
        previous = issue["status"]


def next_lines(issue, by_id):
    """The four lines `next` prints, so `brief` prints the same four.

    Not a table: the backlog is what the caller was trying not to read. The
    Ready line is the JSON's `ready` rendered, not a second opinion. It reads
    "in progress" for a started issue because `ready` means what `list --ready`
    means everywhere else, and printing "no" on the issue the tool just told
    you to work on would read as a bug."""
    return [
        f"{issue['id']}  {issue['title']}",
        f"Status:   {issue['status']}",
        f"Priority: {priority_of(issue)}",
        f"Ready:    {'yes' if is_ready(issue, by_id) else 'in progress'}",
    ]


# Every section but IN PROGRESS is capped at this. Work already started is the
# thing you most want to not start again, and a repo with fifteen in-progress
# issues has a problem the brief should show rather than hide behind "+10 more".
BRIEF_CAP = 5

# Under the id and its two spaces, so a note lines up with the title above it -
# the same shape `list` indents its blocked line to.
INDENT = " " * 9


def omitted(count):
    """`+2 more`, or nothing. A cap that does not say what it hid is the one
    that makes you run `issue list` anyway.

    Printed at the top of its block, directly under the header: the rows below
    it end with the one you came for, and a tail-summary sitting under the most
    urgent row would read as if it were hiding something newer."""
    return [f"+{count} more"] if count else []


def brief_rows(issues, by_id):
    """`ISS-041  Add resolution metadata   high`, with the blocked line under
    the ones that have one - `blocked_note` again, because a blocked row that
    reads like a ready one is the exact thing that note exists to fix.

    Padded to the widest title in this section, not in the brief: the sections
    are read one at a time, and a common width would make a three-row section
    as wide as the longest title anywhere in the repo."""
    width = max(len(issue["title"]) for issue in issues)
    lines = []
    for issue in issues:
        lines.append(f"{issue['id']}  {issue['title']:<{width}}  {priority_of(issue)}")
        lines += [f"{INDENT}{note}" for note in blocked_note(issue, by_id)]
    return lines


def resolved_lines(issue):
    """Two lines: what it was, and why it stopped. The message is the whole
    point of the section - it is where a session finds out that the thing it
    was about to build was closed as not-planned last week - and the target of
    a duplicate or supersede close is the other half of that sentence.

    Evidence is deliberately not here: `issue view` renders it, and the brief
    points at where to look rather than loading it."""
    lines = [f"{issue['id']}  {issue['title']}"]
    resolution = resolution_of(issue)
    if resolution is None:
        # Closed before any of this existed. "closed" is all the file says, so
        # it is all this says - nothing is invented for it.
        return lines + [f"{INDENT}closed"]
    said = resolution["reason"]
    pointed = [
        item["value"]
        for item in resolution["evidence"]
        if item["type"] in ("duplicate-of", "superseded-by")
    ]
    if pointed:
        said += f" -> {pointed[0]}"
    if resolution["message"]:
        said += f" - {resolution['message']}"
    return lines + [f"{INDENT}{said}"]


def as_dict(issue, by_id):
    """The issue as JSON wants it, which is not quite as the file holds it.

    Arrays, so nothing downstream has to split a string the tool already split.
    `blocks` and `ready` although no file stores either: the consumer wants the
    fact, not the storage, and recomputing `ready` means an agent re-reading
    every file to check each blocker when the tool had them all in memory a
    moment ago. Unlike labels these three are always there - `ready` is the
    field an agent asks for on every issue, and a key it has to guess about is
    a key it has to write a branch for."""
    dumped = {**issue, "blocked_by": blockers_of(issue)}
    if "labels" in issue:
        dumped["labels"] = labels_of(issue)
    dumped["blocks"] = blocks(issue["id"], by_id)
    dumped["ready"] = is_ready(issue, by_id)

    # One object rather than the four flat keys the file stores, and the flat
    # keys go with it - the raw `evidence` line is JSON in a string, which is
    # the one shape a reader would have to parse twice. Absent when the issue
    # was closed before any of this existed, the rule labels already follow.
    resolution = resolution_of(issue)
    if resolution:
        for key in ("reason", "closed_at", "message", "evidence"):
            dumped.pop(key, None)
        dumped["resolution"] = resolution
    return dumped


PLAN_TEXT_CAP = 160
PLAN_PENDING_CAP = 3


def compact_plan_lines(plan):
    """A bounded reminder for a session that already has the rationale.

    Omission is explicit: a shorter view must not look like the entire record.
    Callers add the full plan's path, which is navigation and cannot safely be
    shortened to fit a character budget.
    """
    def short(text):
        line = " ".join(text.split())
        return line if len(line) <= PLAN_TEXT_CAP else line[:PLAN_TEXT_CAP - 3] + "..."

    points = plan.get("checkpoints", [])
    pending = [point for point in points if not point["done"]]
    lines = [f"PLAN  {len(points) - len(pending)}/{len(points)}"]
    lines += [f"- [ ] {short(point['text'])}" for point in pending[:PLAN_PENDING_CAP]]
    if len(pending) > PLAN_PENDING_CAP:
        lines.append(f"+{len(pending) - PLAN_PENDING_CAP} more pending checkpoints")
    for key in ("current", "next"):
        if plan.get(key):
            lines.append(f"{key.capitalize()}: {short(plan[key])}")
    decisions = len(plan.get("decisions", []))
    discoveries = len(plan.get("discoveries", []))
    if decisions or discoveries:
        lines.append(f"In full plan: {decisions} decisions, {discoveries} discoveries")
    return lines


def plan_lines(plan):
    """Where the work stands, for a human. Every block is skipped when it is
    empty, so a freshly seeded plan renders as nothing at all rather than as
    six headings saying the agent has done six kinds of nothing.

    Unchecked checkpoints only. The done ones are the count, and printing them
    back at a session that is resuming is the noise the count exists to
    replace. NEXT is last because it is the line acted on, and the terminal
    leaves the last line printed right above the prompt - ISS-025's rule, the
    same one that puts GIT above all of this."""
    lines = []
    if plan["checkpoints"]:
        done = sum(1 for point in plan["checkpoints"] if point["done"])
        lines += ["", f"PLAN  {done}/{len(plan['checkpoints'])}"]
        lines += [f"- [ ] {point['text']}" for point in plan["checkpoints"] if not point["done"]]
    for key, heading, is_list in PLAN_SECTIONS:
        value = plan.get(key)
        # The goal is the issue's title and the caller has just printed it;
        # `plan_block` shows it because there the block stands on its own.
        if not value or key == "goal":
            continue
        lines.append("")
        lines.append(heading.upper())
        lines += [f"- {item}" for item in value] if is_list else value.splitlines()
    return lines[1:]


def plan_block(plan):
    """The three lines `issue view` shows: how far the work got, where it
    stands, and what is next. A pointer, not the plan - `issue start` prints
    the checkpoints and the file itself is one `cat` away, so inlining them in
    the middle of an issue would be the duplication this split exists to avoid.

    No Goal line: `view` prints the issue's title and body right under this,
    and in a seeded plan the goal is that title."""
    done = sum(1 for point in plan["checkpoints"] if point["done"])
    lines = [f"Work plan: {done}/{len(plan['checkpoints'])} checkpoints"]
    for name, key in (("Current", "current"), ("Next", "next")):
        if plan[key]:
            # The first line only, and padded to a column: these are prose
            # fields, and a three-line Current would bury the Next under it.
            lines.append(f"{name + ':':<9}{plan[key].splitlines()[0]}")
    return lines


def plan_as_dict(plan):
    """The plan as JSON wants it. Every key present, unlike the issue
    renderings: the shape is decided by this tool rather than by what an old
    file happens to carry, so a consumer branching on a missing `discoveries`
    would be paying for a fact we already know."""
    return {
        "id": plan["id"],
        "checkpoints": plan["checkpoints"],
        **{key: plan.get(key, [] if is_list else "") for key, _, is_list in PLAN_SECTIONS},
    }


def git_lines(git, files):
    """What actually changed, under the plan's account of what was meant to.
    Nothing at all outside a repo - "we could not read it" is not "the tree was
    clean", and inventing a branch would be claiming a fact.

    Above the plan sections rather than below them, which is ISS-025's rule:
    this is the state the work is in, and printed last it would leave a list of
    file paths at the prompt instead of the one line saying what to do."""
    if not git:
        return []
    said = f"{git['branch']} @ {git['head']}"
    return ["GIT", said + (" - uncommitted" if git["dirty"] else " - clean")] + list(files)
