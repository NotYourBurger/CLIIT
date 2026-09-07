"""Make a tracker here, and tell the agent how to work in it.

The rule is the second half on purpose. A tool whose whole guarantee is a
sentence an agent has to follow has to put that sentence where the agent
actually reads - and `init` is the one moment this tool is allowed to write
outside `.issues/`."""

import os
import sys

from cli_issue_tracker.plan import rule_text
from cli_issue_tracker.storage import issues_dir
from cli_issue_tracker.storage import local_issues_dir

# Whichever of these the repo keeps. Both when it keeps both - two agents
# reading two files is exactly the case one of them exists for.
PROJECT_FILES = ("CLAUDE.md", "AGENTS.md")

HEADING = "## Work plans"

def write_rule():
    """Append the workflow rule to the project files that exist, once.

    Appended rather than written: these files are the repo's, not ours, and the
    one thing worse than not writing the rule is truncating the instructions
    already in there. The check is the rule's own first line - re-running
    `init` after a pull is normal, and a rule that stacks up nine times is a
    file nobody finishes reading.

    Nothing is created when neither file exists. A tool that invents a
    CLAUDE.md in a repo that never had one is making a decision about that
    repo's conventions that it has no standing to make, and `issue init`
    already printed what it did."""
    first = rule_text().splitlines()[0]
    for name in PROJECT_FILES:
        path = os.path.join(os.getcwd(), name)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as file:
            text = file.read()
        if first in text:
            continue
        with open(path, "a", encoding="utf-8") as file:
            file.write(f"\n{HEADING}\n\n{rule_text()}\n")
        print(f"Workflow rule added to {name}")


def init():
    # The one command that does not walk up: `issue init` means "make one here".
    path = local_issues_dir()
    if os.path.isdir(path):
        print("Project is already Initialized")
        # Still the rule: re-running `init` is how a repo that predates it gets
        # the rule, and there is no second command to remember.
        write_rule()
        return

    # But say so if there is one above us. Two trackers allocate ids
    # independently, so both hand out the same ISS-NNN and neither half ever
    # sees the other - the point is that it is never silent.
    found = issues_dir()
    if os.path.isdir(found):
        print(f"Warning: an existing tracker at {found} - making a second one here", file=sys.stderr)

    os.mkdir(path)
    print("Feel free to explore .issues folder")
    write_rule()
