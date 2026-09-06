import typer
from cli_issue_tracker.issues import create_issue
from cli_issue_tracker.issues import list_issues
from cli_issue_tracker.issues import next_issue
from cli_issue_tracker.issues import search_issues
from cli_issue_tracker.issues import view_issue
from cli_issue_tracker.issues import set_fields
from cli_issue_tracker.issues import log_issue
from cli_issue_tracker.issues import claim_issue
from cli_issue_tracker.init import init
import sys
app = typer.Typer()
# Both streams, not just stdout. The console default here is cp1252, so a
# non-ASCII git message or issue title printed as an error came out mangled -
# quietly, because stderr defaults to backslashreplace instead of raising.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

@app.callback()
def main():
    pass


@app.command()
def create(
    title: str,
    description: str,
    priority: str = typer.Option("medium", "--priority", "-p", help="high, medium or low"),
    label: list[str] = typer.Option([], "--label", "-l", help="Repeat for more than one"),
):
    create_issue(title, description, priority, label)

@app.command("list")
def list_projects(
    status: str = typer.Argument(None),
    # Two spellings of one filter: the bare word is what the README documents
    # and what people type, --status is what `search` has to use because its
    # positional is the query. The two commands should not disagree about how
    # you name a status, so both accept both.
    status_flag: str = typer.Option(None, "--status", "-s", help="Same as the trailing word"),
    priority: str = typer.Option(None, "--priority", "-p", help="Only issues with this priority"),
    label: list[str] = typer.Option([], "--label", "-l", help="Only issues with every label given"),
    ready: bool = typer.Option(False, "--ready", help="Open, with every blocker closed"),
    blocked: bool = typer.Option(False, "--blocked", help="Only issues something is in the way of"),
    assignee: str = typer.Option(None, "--assignee", "-a", help="Only issues this person owns"),
    unassigned: bool = typer.Option(False, "--unassigned", help="Only issues nobody has taken"),
    as_json: bool = typer.Option(False, "--json", help="Print the issues as JSON"),
):
    list_issues(
        status or status_flag, priority, label, as_json, ready, blocked, assignee, unassigned
    )


@app.command("next")
def next_up(
    as_json: bool = typer.Option(False, "--json", help="Print the issue as JSON"),
):
    next_issue(as_json)


@app.command("search")
def search(
    query: str = typer.Argument(..., help="Words to find; every one of them must match"),
    status: str = typer.Option(None, "--status", "-s", help="Only issues with this status"),
    priority: str = typer.Option(None, "--priority", "-p", help="Only issues with this priority"),
    label: list[str] = typer.Option([], "--label", "-l", help="Only issues with every label given"),
    as_json: bool = typer.Option(False, "--json", help="Print the matches as JSON"),
):
    search_issues(query, status, priority, label, as_json)
    
@app.command("init")
def init_project():
    init()

@app.command("view")
def view(id, as_json: bool = typer.Option(False, "--json", help="Print the issue as JSON")):
    view_issue(id, as_json)

@app.command("set")
def set_command(
    words: list[str] = typer.Argument(
        ..., metavar="IDS... [STATUS]", help="Issue ids, optionally followed by a status"
    ),
    priority: str = typer.Option(None, "--priority", "-p", help="high, medium or low"),
    label: list[str] = typer.Option([], "--label", "-l", help="Add a label; repeatable"),
    unlabel: list[str] = typer.Option([], "--unlabel", "-L", help="Remove a label; repeatable"),
    blocked_by: list[str] = typer.Option(
        [], "--blocked-by", "-b", help="Cannot start until this issue closes; repeatable"
    ),
    unblock: list[str] = typer.Option(
        [], "--unblock", "-B", help="Remove a blocker; repeatable"
    ),
    assignee: str = typer.Option(None, "--assignee", "-a", help="Set the owner; empty clears it"),
):
    set_fields(words, priority, label, unlabel, blocked_by, unblock, assignee)


# claim, assign and release are the ownership verbs. Two of them are spellings
# of `set --assignee` and say so by being one call; claim is the one with a
# precondition, so it is the one with a function.
@app.command("claim")
def claim(
    id: str,
    by: str = typer.Option(None, "--by", help="Defaults to $ISSUE_USER, then git config user.name"),
):
    claim_issue(id, by)


@app.command("assign")
def assign(id: str, to: str = typer.Option(..., "--to", help="Hand it over, no questions")):
    set_fields([id], assignee=to)


@app.command("release")
def release(id: str):
    set_fields([id], assignee="")

@app.command("log")
def log(id):
    log_issue(id)
