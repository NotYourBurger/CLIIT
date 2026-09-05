import json
import os
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

def create_issue(title: str, description: str):

    path = require_issue_dir()
    issue = {
        "id": next_id(path),
        "created_at": now(),
        "status": "open",
        "body": f"# {title}\n\n{description}",
    }
    write_issue(issue)
    print(f"Issue {issue['id']} has been created")


STATUSES = ("in-progress", "open", "closed") ## Ordering


def rank(issue):
    """Sort key: position in STATUSES. Anything we never wrote sorts to the end
    rather than vanishing from the list."""
    status = issue["status"]
    return STATUSES.index(status) if status in STATUSES else len(STATUSES) #sorting the issues based on the STATUS ordering


def require_status(status):
    """Pass, or exit 1 saying why. Shared by list (filtering) and set (writing)
    so there is one list and one message, not two that drift apart. Same
    contract as require_issue_dir - a word we cannot act on is a failed
    command, not a quiet one."""
    if status not in STATUSES:
        print(f"Unknown status {status!r} - use: {', '.join(STATUSES)}", file=sys.stderr)
        sys.exit(1)


def print_rows(issues, width, status_width):

    rule = "-" * (
        9 + width + status_width + max(len(issue["created_at"]) for issue in issues)
    )
    previous = None
    for issue in issues:
        # Not on the first row: previous is None only before anything is printed.
        if previous is not None and issue["status"] != previous:
            print(rule)
        print(
            f"{issue['id']:<9}{issue['title']:<{width}}{issue['status']:<{status_width}}{issue['created_at']}"
        )
        previous = issue["status"]


def list_issues(status=None, as_json=False):
    # Reject a bad word before touching the disk - "issue list opne" should say so,
    # not print an empty table and look like there is nothing to do. None is the
    # no-filter case, which is legitimate, so it skips the check.
    if status is not None:
        require_status(status)

    path = require_issue_dir()
    issues = []
    for filename in sorted(os.listdir(path)):
        if filename.startswith("ISS-") and filename.endswith(".md"):
            issue = parse_issue(os.path.join(path, filename))
            if issue is not None:
                issues.append(issue)

    if status is not None:
        issues = [issue for issue in issues if issue["status"] == status]

    # Stable sort, and the list is already in id order, so ids stay ordered
    # inside each group.
    issues.sort(key=rank)

    # Everything above collects; everything below renders. --json swaps the
    # renderer and nothing else - same issues, same order, same filter.
    if as_json:
        # Before the empty check on purpose: "no issues" is [] to a script, not
        # a sentence it would choke on.
        print(json.dumps(issues, indent=2))
        return

    if not issues:
        # Two different empty cases: nothing at all, or nothing matching.
        print("No issues yet - run: issue create" if status is None else f"No {status} issues")
        return

    # Widen each column to fit its longest value, so nothing gets truncated.
    # Computed across every issue being shown, so all groups share one set of
    # column positions.
    width = max(len("TITLE"), *(len(issue["title"]) for issue in issues)) + 2
    status_width = max(len("STATUS"), *(len(issue["status"]) for issue in issues)) + 2

    print(f"{'ID':<9}{'TITLE':<{width}}{'STATUS':<{status_width}}CREATED AT")
    print_rows(issues, width, status_width)


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
        print(json.dumps(issue, indent=2))
        return

    table = Table(show_header=True, header_style="bold cyan")
    for name in ("ID" , "STATUS", "CREATED AT", "UPDATED AT"):
        table.add_column(name)
    # Issues written before updated_at existed have none - say so rather than
    # inventing a time we never recorded.
    table.add_row(
        issue["id"], issue["status"], issue["created_at"], issue.get("updated_at", "unknown")
    )
    console.print(table)
    console.print(Markdown(issue["body"]))
    

def set_status(ids: list[str], status: str):
    # Validated once for the whole batch - the status is typed by the user now,
    # so a typo must not reach the file. One bad word, one error line.
    require_status(status)

    for id in ids:
        issue = read_issue(id)
        if issue is None:
            # Keep going: one bad id in a batch should not cancel the rest.
            print(f"Issue {id} Was Not Found", file=sys.stderr)
            continue
        if issue["status"] == status:
            print(f"Issue {id} has already been {status}")
        else:
            issue["status"] = status
            write_issue(issue)
            print(f"{id} has been {status}")
