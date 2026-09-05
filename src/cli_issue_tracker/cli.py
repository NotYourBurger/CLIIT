import typer
from cli_issue_tracker.issues import create_issue
from cli_issue_tracker.issues import list_issues
from cli_issue_tracker.issues import view_issue
from cli_issue_tracker.issues import set_fields
from cli_issue_tracker.issues import log_issue
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
    priority: str = typer.Option(None, "--priority", "-p", help="Only issues with this priority"),
    label: list[str] = typer.Option([], "--label", "-l", help="Only issues with every label given"),
    as_json: bool = typer.Option(False, "--json", help="Print the issues as JSON"),
):
    list_issues(status, priority, label, as_json)
    
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
):
    set_fields(words, priority, label, unlabel)

@app.command("log")
def log(id):
    log_issue(id)
