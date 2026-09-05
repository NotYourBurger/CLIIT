"""What every check here needs: a way to call a command and a way to find the repo.

These are scripts, not a framework - each test file runs on its own with
`uv run python tests/<file>.py` and says "ok" or raises. This module exists
because four of them had grown their own copy of the same eight lines.
"""

import contextlib
import io
import os

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
