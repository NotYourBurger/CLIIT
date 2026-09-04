import os
from datetime import datetime


from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table


from rich.theme import Theme

from cli_issue_tracker.convert_id import next_id
from cli_issue_tracker.storage import require_issue_dir
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
    if path is None:
        return

    issue = {
        "id": next_id(path),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "open",
        "body": f"# {title}\n\n{description}",
    }
    write_issue(issue)
    print(f"Issue {issue['id']} has been created")


def render(content):
    try:
        console.print(Markdown(content))
    except:
        print("Something Went Wrong")

    

STATUSES = ("in-progress", "open", "closed") ## Ordering


def rank(issue):
    """Sort key: position in STATUSES. Anything we never wrote sorts to the end
    rather than vanishing from the list."""
    status = issue["status"]
    return STATUSES.index(status) if status in STATUSES else len(STATUSES) #sorting the issues based on the STATUS ordering


def check_status(status):
    """True if it's a status we know. Prints why not when it isn't.
    Shared by list (filtering) and set (writing) so there is one list and
    one message, not two that drift apart."""
    if status in STATUSES:
        return True
    print(f"Unknown status {status!r} - use: {', '.join(STATUSES)}")
    return False


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


def list_issues(status=None):
    # Reject a bad word before touching the disk - "issue list opne" should say so,
    # not print an empty table and look like there is nothing to do. None is the
    # no-filter case, which is legitimate, so it skips the check.
    if status is not None and not check_status(status):
        return

    path = require_issue_dir()
    if path is None:
        return
    issues = []
    for filename in sorted(os.listdir(path)):
        if filename.startswith("ISS-") and filename.endswith(".md"):
            issue = parse_issue(os.path.join(path, filename))
            if issue is not None:
                issues.append(issue)

    if status is not None:
        issues = [issue for issue in issues if issue["status"] == status]

    if not issues:
        # Two different empty cases: nothing at all, or nothing matching.
        print("No issues yet - run: issue create" if status is None else f"No {status} issues")
        return

    # Widen each column to fit its longest value, so nothing gets truncated.
    # Computed across every issue being shown, before the sort, so all groups
    # share one set of column positions.
    width = max(len("TITLE"), *(len(issue["title"]) for issue in issues)) + 2
    status_width = max(len("STATUS"), *(len(issue["status"]) for issue in issues)) + 2

    # Stable sort, and the list is already in id order, so ids stay ordered
    # inside each group.
    issues.sort(key=rank)

    print(f"{'ID':<9}{'TITLE':<{width}}{'STATUS':<{status_width}}CREATED AT")
    print_rows(issues, width, status_width)


def view_issue(id):

    issue = read_issue(id)
    if issue is None:
        print(f"Issue {id} Doesnt Exist")
        return
    
    table = Table(show_header=True, header_style="bold cyan")
    for name in ("ID" , "STATUS", "CREATED AT"):
        table.add_column(name)
    table.add_row(issue["id"], issue["status"], issue["created_at"])
    console.print(table)
    render(issue["body"])
    

def set_status(ids: list[str], status: str):
    # Validated once for the whole batch - the status is typed by the user now,
    # so a typo must not reach the file. One bad word, one error line.
    if not check_status(status):
        return

    for id in ids:
        issue = read_issue(id)
        if issue is None:
            # Keep going: one bad id in a batch should not cancel the rest.
            print(f"Issue {id} Was Not Found")
            continue
        if issue["status"] == status:
            print(f"Issue {id} has already been {status}")
        else:
            issue["status"] = status
            write_issue(issue)
            print(f"{id} has been {status}")
