"""issue log against a real throwaway git repo - the branches worth checking are
the three ways it can have nothing to print, not the formatting."""
import contextlib
import io
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from cli_issue_tracker.issues import log_issue
from cli_issue_tracker.storage import write_issue


def run(*args):
    subprocess.run(args, check=True, capture_output=True)


def log(id):
    """Returns (exit code or None, stdout)."""
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            log_issue(id)
    except SystemExit as exit:
        return exit.code, out.getvalue()
    return None, out.getvalue()


def demo():
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.chdir(tmp)
            run("git", "init")
            run("git", "config", "user.email", "t@example.com")
            run("git", "config", "user.name", "t")
            os.makedirs(".issues")
            os.environ["ISSUES_DIR"] = os.path.join(tmp, ".issues")

            assert log("ISS-404")[0] == 1, "a missing id must fail, not print an empty log"

            write_issue({"id": "ISS-001", "status": "open", "created_at": "x",
                         "body": "# Title\n\nbody"})
            assert log("ISS-001")[0] == 1, "an uncommitted file has no history - must fail"

            run("git", "add", "-A")
            run("git", "commit", "-m", "first commit")
            code, out = log("ISS-001")
            assert code is None, f"a committed issue must succeed, got exit {code}"
            assert "first commit" in out, out
        finally:
            os.chdir(original)
            os.environ.pop("ISSUES_DIR", None)
    print("ok")


if __name__ == "__main__":
    demo()
