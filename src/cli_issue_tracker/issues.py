import json
import os
import subprocess
import sys


from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table


from rich.theme import Theme

from cli_issue_tracker.convert_id import next_id
from cli_issue_tracker.storage import require_issue_dir
from cli_issue_tracker.storage import now
from cli_issue_tracker.storage import parse_issue
from cli_issue_tracker.storage import read_issue
from cli_issue_tracker.storage import write_issue

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

def create_issue(title: str, description: str, priority: str = "medium", labels=()):

    # Before the id is allocated: a rejected create must not burn a number.
    require_priority(priority)
    labels = clean_labels(labels)
    path = require_issue_dir()
    issue = {
        "id": next_id(path),
        "created_at": now(),
        "status": "open",
        "priority": priority,
        # No labels means no field, not an empty one - the same rule the issues
        # that predate priority live by.
        **({"labels": ", ".join(labels)} if labels else {}),
        "body": f"# {title}\n\n{description}",
    }
    write_issue(issue)
    print(f"Issue {issue['id']} has been created")


STATUSES = ("in-progress", "open", "closed") ## Ordering
STATUS_ORDER = STATUSES[::-1]  # least urgent first: closed, open, in-progress


PRIORITIES = ("high", "medium", "low")
PRIORITY_ORDER = ("-",) + PRIORITIES[::-1]  # no priority, then low, medium, high


def priority_of(issue):
    """What to show and filter on. Missing stays missing - the issues written
    before this field existed never had a priority, and calling those "medium"
    would invent a decision nobody made."""
    return issue.get("priority", "-")


def labels_of(issue):
    """The labels field as a list. Flat frontmatter has no list type, so the
    file holds one comma-joined string and this is the only place that knows
    it. Absent, empty and blank all read back as no labels."""
    return [word.strip() for word in issue.get("labels", "").split(",") if word.strip()]


def clean_labels(words):
    """User words in, storable labels out: stripped, lowercased, deduped and
    sorted. Sorted because the file is read by humans and diffed by git, and
    an insertion-ordered list reorders itself for no reason.

    A comma is the delimiter, so a label cannot contain one - that is the whole
    validation. Unlike status and priority there is no list to check against:
    inventing the words is the point of labels."""
    labels = set()
    for word in words:
        label = word.strip().lower()
        if not label:
            print("A label cannot be empty", file=sys.stderr)
            sys.exit(1)
        if "," in label:
            print(
                f"A label cannot contain a comma - {word!r} is the separator "
                "between two labels, so pass them as two --label flags",
                file=sys.stderr,
            )
            sys.exit(1)
        labels.add(label)
    return sorted(labels)


def rank(issue):
    """Sort key: least urgent first, so the list reads bottom-up. A terminal
    leaves the last line printed right above the prompt, which is where the eye
    already is - putting closed issues there and making you scroll for the
    in-progress one had it backwards.

    Both orders are the existing tuples reversed, so there is still one place
    that says what order statuses and priorities come in. Anything we never
    wrote - an unknown status, a hand-typed priority - sorts to the very top,
    which is the low-attention end.

    Ties keep id order, and the sort is stable, so the newest issue of a group
    is the one nearest the prompt."""
    status = issue["status"]
    priority = priority_of(issue)
    return (
        STATUS_ORDER.index(status) if status in STATUS_ORDER else -1,
        PRIORITY_ORDER.index(priority) if priority in PRIORITY_ORDER else -1,
    )


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
        else:
            said.append(f"{field} {value}")
    return ", ".join(said)


def require_status(status):
    """Pass, or exit 1 saying why. Shared by list (filtering) and set (writing)
    so there is one list and one message, not two that drift apart. Same
    contract as require_issue_dir - a word we cannot act on is a failed
    command, not a quiet one."""
    if status not in STATUSES:
        print(f"Unknown status {status!r} - use: {', '.join(STATUSES)}", file=sys.stderr)
        sys.exit(1)


def require_priority(priority):
    """The same contract as require_status, for the other three-word list. Two
    near-identical validators beat one parameterised one for lists this short -
    fold them together when there is a third."""
    if priority not in PRIORITIES:
        print(f"Unknown priority {priority!r} - use: {', '.join(PRIORITIES)}", file=sys.stderr)
        sys.exit(1)


COLUMNS = (
    ("ID", lambda issue: issue["id"]),
    ("TITLE", lambda issue: issue["title"]),
    ("STATUS", lambda issue: issue["status"]),
    ("PRIORITY", priority_of),
    ("CREATED AT", lambda issue: issue["created_at"]),
    ("LABELS", lambda issue: ", ".join(labels_of(issue))),
)


def print_table(issues):
    """The list, as aligned columns. Each column is as wide as its widest
    value, so nothing is truncated; the last one is not padded, so a long
    value there cannot push anything off the terminal. That is why LABELS is
    last - it is the column with no bound on its width, and a repo that does
    not use labels does not get an empty column at all."""
    columns = [
        (name, value)
        for name, value in COLUMNS
        if name != "LABELS" or any(labels_of(issue) for issue in issues)
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
        previous = issue["status"]


def list_issues(status=None, priority=None, labels=(), as_json=False):
    # Reject a bad word before touching the disk - "issue list opne" should say so,
    # not print an empty table and look like there is nothing to do. None is the
    # no-filter case, which is legitimate, so it skips the check.
    if status is not None:
        require_status(status)
    if priority is not None:
        require_priority(priority)
    labels = clean_labels(labels)

    path = require_issue_dir()
    issues = []
    for filename in sorted(os.listdir(path)):
        # No prefix test: parse_issue already returns None for anything
        # without our frontmatter, so it is the one thing deciding what is an
        # issue. Dropping the check is what lets a renamed prefix keep listing
        # the issues filed under the old one.
        if filename.endswith(".md"):
            issue = parse_issue(os.path.join(path, filename))
            if issue is not None:
                issues.append(issue)

    if status is not None:
        issues = [issue for issue in issues if issue["status"] == status]
    if priority is not None:
        # Issues filed before the field existed match no filter - which is the
        # point of not defaulting them to medium.
        issues = [issue for issue in issues if priority_of(issue) == priority]
    if labels:
        # Every label given, not any of them: repeating a filter flag narrows,
        # the way adding --priority to a status does.
        issues = [
            issue for issue in issues if set(labels) <= set(labels_of(issue))
        ]

    # Stable sort, and the list is already in id order, so ids stay ordered
    # inside each group.
    issues.sort(key=rank)

    # Everything above collects; everything below renders. --json swaps the
    # renderer and nothing else - same issues, same order, same filter.
    if as_json:
        # Before the empty check on purpose: "no issues" is [] to a script, not
        # a sentence it would choke on.
        print(json.dumps([as_dict(issue) for issue in issues], indent=2))
        return

    if not issues:
        # Two different empty cases: nothing at all, or nothing matching.
        wanted = " ".join(word for word in (priority, status, *labels) if word)
        print(f"No {wanted} issues" if wanted else "No issues yet - run: issue create")
        return

    print_table(issues)


def as_dict(issue):
    """The issue as JSON wants it, which is not quite as the file holds it:
    labels come out as an array. Splitting a string every consumer would have
    to split itself is worth the one place the output stops being a literal
    transcript of the frontmatter."""
    if "labels" not in issue:
        return issue
    return {**issue, "labels": labels_of(issue)}


def view_issue(id, as_json=False):

    issue = read_issue(id)
    if issue is None:
        # An id that isn't there is a failed lookup, not an empty one - same
        # contract as require_issue_dir, so a script gets a non-zero exit rather
        # than success with nothing on stdout.
        print(f"Issue {id} Doesnt Exist", file=sys.stderr)
        sys.exit(1)

    if as_json:
        # body included verbatim - it is the field the table cannot carry and
        # the one an external reader actually wants.
        print(json.dumps(as_dict(issue), indent=2))
        return

    # Issues written before updated_at existed have none - say so rather than
    # inventing a time we never recorded. LABELS only appears when there are
    # some: this table is already five columns of timestamps that rich has to
    # elide, and an empty sixth would cost the others width for nothing.
    fields = [
        ("ID", issue["id"]),
        ("STATUS", issue["status"]),
        ("PRIORITY", priority_of(issue)),
        ("CREATED AT", issue["created_at"]),
        ("UPDATED AT", issue.get("updated_at", "unknown")),
    ]
    if labels_of(issue):
        fields.append(("LABELS", ", ".join(labels_of(issue))))

    table = Table(show_header=True, header_style="bold cyan")
    for name, _ in fields:
        table.add_column(name)
    table.add_row(*(value for _, value in fields))
    console.print(table)
    console.print(Markdown(issue["body"]))
    

def set_fields(words: list[str], priority: str = None, add=(), remove=()):
    """`issue set ISS-001 closed`, `issue set ISS-001 --priority high`, or both
    at once. The status stayed a bare word because that is what the README
    documents and what people already type; which word it is, is decided here
    rather than by the parser - click cannot tell a trailing optional word from
    an id when only one word is given, and reads `issue set ISS-001` as a
    status with no ids.

    Labels are the field that does not replace: --label adds, --unlabel takes
    away, and both are computed per issue because the result depends on what
    that issue already has."""
    ids = list(words)
    status = ids.pop() if ids and ids[-1] in STATUSES else None
    add, remove = clean_labels(add), clean_labels(remove)

    both = set(add) & set(remove)
    if both:
        print(
            f"Cannot add and remove the same label: {', '.join(sorted(both))}",
            file=sys.stderr,
        )
        sys.exit(1)

    if status is None and priority is None and not add and not remove:
        # Also where a mistyped status lands: it is not a status, so it was
        # read as an id, and nothing was asked for. Saying what the words are
        # beats "Issue opne Was Not Found".
        print(
            f"Give a status ({', '.join(STATUSES)}), --priority "
            f"({', '.join(PRIORITIES)}), --label or --unlabel "
            "- e.g. issue set ISS-001 closed",
            file=sys.stderr,
        )
        sys.exit(1)
    if not ids:
        print("No issue ids given", file=sys.stderr)
        sys.exit(1)
    # Validated once for the whole batch - the words are typed by the user now,
    # so a typo must not reach the file. One bad word, one error line.
    if priority is not None:
        require_priority(priority)

    fixed = {"status": status, "priority": priority}
    fixed = {field: value for field, value in fixed.items() if value is not None}

    missing = []
    for id in ids:
        issue = read_issue(id)
        if issue is None:
            # Keep going: one bad id in a batch should not cancel the rest.
            # The exit code carries the failure instead, once, at the end.
            print(f"Issue {id} Was Not Found", file=sys.stderr)
            missing.append(id)
            continue
        wanted = dict(fixed)
        if add or remove:
            labels = [label for label in labels_of(issue) if label not in remove]
            wanted["labels"] = ", ".join(sorted(set(labels + add)))

        # get(field, "") and not get(field): an issue with no labels and a call
        # that removes its last one both mean "", and that is not a change.
        changed = {
            field: value for field, value in wanted.items() if issue.get(field, "") != value
        }
        if not changed:
            # Already there is success - what the caller asked for is what is on
            # disk, which is all `set` promises.
            print(f"Issue {id} is already {describe(wanted)}")
        else:
            for field, value in changed.items():
                # Empty means gone: the last label removed takes the field with
                # it, rather than leaving "labels:" behind on the file.
                if value:
                    issue[field] = value
                else:
                    issue.pop(field, None)
            write_issue(issue)
            print(f"{id} has been set to {describe(changed)}")

    # Partial failure is failure: `issue set A B closed && git commit` must not
    # commit when B was never set. The good ids are still written - the batch
    # ran to the end first.
    if missing:
        sys.exit(1)


def log_issue(id):
    """`git log` for one issue file. The history is already in the repo because
    issues are files - this only points git at the right path and gets out of
    the way. No parsing of git's output: --format is the whole formatter."""
    file_path = os.path.join(require_issue_dir(), f"{id}.md")
    if not os.path.isfile(file_path):
        print(f"Issue {id} Doesnt Exist", file=sys.stderr)
        sys.exit(1)

    # -- before the path so an id that looks like a revision cannot be read as one.
    # encoding: git writes UTF-8; text=True alone decodes with the locale
    # default, which is cp1252 here and turns every accent into mojibake at
    # exit 0. Same reason storage.py passes it to every open().
    git = ["git", "log", "--follow", "--date=short", "--format=%h  %ad  %s", "--", file_path]
    result = subprocess.run(git, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        # Not a git repo, or the file is outside it - git already said which.
        print(result.stderr.strip() or "git log failed", file=sys.stderr)
        sys.exit(1)
    if not result.stdout.strip():
        # An empty log is not a successful one: the file exists but git has
        # never seen it, and printing nothing at exit 0 looks like no history.
        print(f"Issue {id} has never been committed", file=sys.stderr)
        sys.exit(1)

    print(result.stdout, end="")

    # Edits that are not committed yet are invisible above. Say so on stderr,
    # so it is a note to the reader and not a row to whatever is parsing stdout.
    pending = subprocess.run(
        ["git", "status", "--porcelain", "--", file_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if pending.stdout.strip():
        print(f"({id} has uncommitted changes, not shown above)", file=sys.stderr)
