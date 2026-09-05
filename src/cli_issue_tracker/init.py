import os
import sys
from cli_issue_tracker.storage import issues_dir
from cli_issue_tracker.storage import local_issues_dir

def init():
    # The one command that does not walk up: `issue init` means "make one here".
    path = local_issues_dir()
    if os.path.isdir(path):
        print("Project is already Initialized")
        return

    # But say so if there is one above us. Two trackers allocate ids
    # independently, so both hand out the same ISS-NNN and neither half ever
    # sees the other - the point is that it is never silent.
    found = issues_dir()
    if os.path.isdir(found):
        print(f"Warning: an existing tracker at {found} - making a second one here", file=sys.stderr)

    os.mkdir(path)
    print("Feel free to explore .issues folder")
