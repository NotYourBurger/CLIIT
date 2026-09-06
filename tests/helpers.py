"""What every check here needs: a way to call a command and a way to find the repo.

These are scripts, not a framework - each test file runs on its own with
`uv run python tests/<file>.py` and says "ok" or raises. This module exists
because four of them had grown their own copy of the same eight lines.
"""

import contextlib
import io
import os

from cli_issue_tracker.issues import close_issue

# The repo, not this directory: test_storage reads a real issue out of .issues/
# and test_encoding walks the source.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(function, *args, **kwargs):
    """Call a command function, and return (exit code or None, stdout, stderr).

    The exit code is the whole point of the validators, so it cannot be
    swallowed - a bare call would end the test run instead. stderr is separate
    rather than merged because which stream a message went to is itself the
    contract: stdout is what a script parses, stderr is what a human reads."""
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            function(*args, **kwargs)
    except SystemExit as exit:
        return exit.code, out.getvalue(), err.getvalue()
    return None, out.getvalue(), err.getvalue()


def close(*ids):
    """Close issues, for the checks that need something closed rather than
    something checked about closing - a blocker out of the way, a row in the
    closed group. Manual verification is the evidence with no dependencies:
    --commit would tie these files to whatever repo they run inside.

    The rules themselves live in test_close.py. Returns the last call's
    (code, stdout, stderr), which is what the one caller that reads a cascade
    line wants."""
    for id in ids:
        result = run(
            close_issue, id, completed=True, message="done", verified=["checked by hand"]
        )
    return result
