"""What every check here needs: a way to call a command and a way to find the repo.

These are scripts, not a framework - each test file runs on its own with
`uv run python tests/<file>.py` and says "ok" or raises. This module exists
because four of them had grown their own copy of the same eight lines.
"""

import contextlib
import io
import os
import re

from cli_issue_tracker.issues import close_issue
from cli_issue_tracker.issues import create_issue as _create_issue
from cli_issue_tracker.storage import issues_dir, read_issue, write_issue

# The repo, not this directory: test_encoding walks the source.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A frozen .issues/ that is committed and never moves. The two checks that
# needed a real corpus - the parser round trip and the whole-directory pass -
# used to read the repo's own .issues/, which made their result depend on which
# issues happened to be filed rather than on the code (ISS-049). See the README
# in there before adding to it.
FIXTURES = os.path.join(REPO, "tests", "fixtures")


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


def legacy_create(*args, **kwargs):
    """Create an issue, then make it a numeric legacy fixture.

    Most command tests exercise legacy IDs on purpose; the dedicated ID-scheme
    test covers newly generated IDs without duplicating every command test.
    """
    directory = issues_dir()
    before = set(os.listdir(directory))
    _create_issue(*args, **kwargs)
    created = next(name for name in set(os.listdir(directory)) - before if name.endswith(".md"))
    issue = read_issue(created[:-3])
    numbers = [int(match.group(1)) for name in before if (match := re.fullmatch(r"ISS-(\d+)\.md", name))]
    issue["id"] = f"ISS-{max(numbers, default=0) + 1:03d}"
    write_issue(issue)
    os.unlink(os.path.join(directory, created))


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
