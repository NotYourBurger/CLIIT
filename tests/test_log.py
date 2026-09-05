"""issue log against a real throwaway git repo - the branches worth checking are
the three ways it can have nothing to print, not the formatting."""
import os
import subprocess
import tempfile

from helpers import run
from cli_issue_tracker.issues import log_issue
from cli_issue_tracker.storage import write_issue


def git(*args):
    subprocess.run(args, check=True, capture_output=True)


def log(id):
    """`issue log`, captured. stderr matters: once the repo has a commit, a
    missing id and a never-committed file both exit 1, so the message is the
    only thing that says which branch ran."""
    return run(log_issue, id)


def demo():
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.chdir(tmp)
            git("git", "init")
            git("git", "config", "user.email", "t@example.com")
            git("git", "config", "user.name", "t")
            os.makedirs(".issues")
            os.environ["ISSUES_DIR"] = os.path.join(tmp, ".issues")

            # Commit first. In a repo with no commits at all `git log` fails
            # outright (returncode 128), so every case below would exit 1
            # through the git-failed branch and the two branches these lines
            # are here to cover would never run.
            write_issue({"id": "ISS-001", "status": "open", "created_at": "x",
                         "body": "# Title\n\nbody"})
            git("git", "add", "-A")
            git("git", "commit", "-m", "Résumé — naïve café")

            code, out, _ = log("ISS-001")
            assert code is None, f"a committed issue must succeed, got exit {code}"
            # Non-ASCII survives the subprocess decode - git writes UTF-8 and
            # the locale default here does not.
            assert "Résumé — naïve café" in out, out

            # Both of these reach git with a path it has no history for, which
            # now returns 0 and an empty log rather than failing.
            code, _, err = log("ISS-404")
            assert code == 1, "a missing id must fail, not print an empty log"
            assert "Doesnt Exist" in err, f"a missing id must say so, said: {err!r}"

            write_issue({"id": "ISS-002", "status": "open", "created_at": "x",
                         "body": "# Uncommitted\n\nbody"})
            code, _, err = log("ISS-002")
            assert code == 1, "an uncommitted file has no history - must fail"
            assert "never been committed" in err, f"said: {err!r}"
        finally:
            os.chdir(original)
            os.environ.pop("ISSUES_DIR", None)
    print("ok")


if __name__ == "__main__":
    demo()
