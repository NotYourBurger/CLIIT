"""Checks for the two no-raise contracts: reading a plan, and asking git.

Both are recovery paths, and a traceback on a recovery path costs the tool the
moment it is needed. `read_plan` documents that an unrecognisable file is still
a plan; `git` documents that a failure costs the git block and not the output.
Neither promise survived contact with a byte that is not UTF-8 or a machine
with no git on it (ISS-043).

The seam is the command functions, the same one every other check here uses -
not `subprocess.run`, because a stub for the call being fixed is how you get a
green suite and a crashing tool. git is removed the way a stripped image
removes it: PATH.

Run: uv run python tests/test_degraded.py
"""

import os
import tempfile

from helpers import run
from cli_issue_tracker.issues import close_issue
from cli_issue_tracker.issues import create_issue
from cli_issue_tracker.issues import log_issue
from cli_issue_tracker.issues import next_issue
from cli_issue_tracker.issues import start_issue
from cli_issue_tracker.issues import view_issue
from cli_issue_tracker.plan import plan_path
from cli_issue_tracker.plan import read_plan
from cli_issue_tracker.storage import read_issue

# 0xe9 is latin-1 'é' - one byte an editor saving in the wrong encoding leaves
# behind, and the exact byte in the report.
BAD_BYTE = b"\xe9"


def plant_bad_byte(id):
    """Corrupt one plan the way a truncated write or a latin-1 save does:
    valid text either side, one byte in the middle that is not UTF-8."""
    path = plan_path(id)
    with open(path, "rb") as file:
        raw = file.read()
    with open(path, "wb") as file:
        file.write(raw.replace(b"## Current", b"## Current\n\nCaf" + BAD_BYTE + b" work.", 1))
    return path


def undecodable_plan_is_still_a_plan():
    """A bad byte costs the byte, not the command.

    `start` reads the plan before it decides whether to reseed, so a plan that
    cannot be read is a plan that cannot be resumed - and the file it would
    reseed over is the agent's only copy of the work."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        os.environ["ISSUE_USER"] = "tester"
        try:
            run(create_issue, "Login and signup", "...", "high")
            run(start_issue, "ISS-001")
            path = plant_bad_byte("ISS-001")
            before = os.path.getsize(path)

            # The reader itself: it returns a plan and says which file needs
            # repairing, rather than raising out of whatever was calling it.
            code, out, err = run(read_plan, "ISS-001")
            assert code is None, (code, out, err)
            assert path in err, err

            # And `start` does not reseed over it - the plan is still the
            # agent's file, byte for byte.
            code, out, err = run(start_issue, "ISS-001")
            assert code is None, (code, out, err)
            assert os.path.getsize(path) == before, "start reseeded over a plan it could not decode"

            # The commands that read a plan in passing still print their own
            # output: one bad byte in one plan must not take out `view`.
            code, out, err = run(view_issue, "ISS-001")
            assert code is None, (code, out, err)
            assert "Login and signup" in out, out

            code, out, err = run(next_issue)
            assert code is None, (code, out, err)
            assert "ISS-001" in out, out
        finally:
            os.environ.pop("ISSUES_DIR", None)
            os.environ.pop("ISSUE_USER", None)


class no_git:
    """git off PATH, the way a container or a stripped image has it off.

    Not a stub for `subprocess.run`: the bug is that the call raises before
    anything gets to interpret it, so a fake that never raises would agree with
    the broken code. An empty directory on PATH is the real absence."""

    def __enter__(self):
        self.empty = tempfile.TemporaryDirectory()
        self.original = os.environ.get("PATH", "")
        os.environ["PATH"] = self.empty.name
        return self

    def __exit__(self, *exception):
        os.environ["PATH"] = self.original
        self.empty.cleanup()


def missing_git_is_the_absent_answer():
    """No git binary reads exactly like no repo, everywhere it is asked.

    `require_commits` already decided that closing an issue must not depend on
    a repository - "network access must never be on the path to closing an
    issue" - and then crashed on the machine where git is not installed, which
    is the same absence for the same reason."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        try:
            with no_git():
                # `claim` asks git for a name when $ISSUE_USER is not set, and
                # that is the first git call a fresh run makes.
                os.environ.pop("ISSUE_USER", None)
                code, out, err = run(create_issue, "Login and signup", "...", "high")
                assert code is None, (code, out, err)
                code, out, err = run(start_issue, "ISS-001")
                assert code is None, (code, out, err)

                # The optional git block is what is lost, not the output.
                code, out, err = run(view_issue, "ISS-001")
                assert code is None, (code, out, err)
                assert "Login and signup" in out, out
                code, out, err = run(next_issue)
                assert code is None, (code, out, err)
                assert "ISS-001" in out, out

                # `log` has nothing to print without git and says so - exit 1
                # is its answer for a file git cannot speak about at all.
                code, out, err = run(log_issue, "ISS-001")
                assert code == 1 and out == "", (code, out, err)
                assert err.strip(), "log failed silently"

                # And --commit skips the check it already skips with no repo,
                # rather than taking the close down with it.
                code, out, err = run(
                    close_issue, "ISS-001", completed=True, message="done",
                    commits=["deadbeef"],
                )
                assert code is None, (code, out, err)
                assert read_issue("ISS-001")["status"] == "closed", read_issue("ISS-001")
        finally:
            os.environ.pop("ISSUES_DIR", None)


def demo():
    undecodable_plan_is_still_a_plan()
    missing_git_is_the_absent_answer()
    print("ok")


if __name__ == "__main__":
    demo()
