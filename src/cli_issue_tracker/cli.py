import typer
from cli_issue_tracker.issues import create_issue
from cli_issue_tracker.issues import list_issues
from cli_issue_tracker.issues import view_issue
from cli_issue_tracker.issues import set_status
from cli_issue_tracker.init import init
import sys
app = typer.Typer()
sys.stdout.reconfigure(encoding="utf-8")

@app.callback()
def main():
    pass


@app.command()
def create(
    title: str,
    description: str,
):
    create_issue(title, description)

@app.command("list")
def list_projects(status: str = typer.Argument(None)):
    list_issues(status)
    
@app.command("init")
def init_project():
    init()

@app.command("view")
def view(id):
    view_issue(id)

@app.command("set")
def set_command(ids: list[str], status: str):
    set_status(ids, status)
