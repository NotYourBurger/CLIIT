"""A write that fails leaves the file that was already there untouched.

Every write this tool makes used to open the target with mode `w`, which
truncates before a byte of the new content exists on disk. The content is built
in memory first, so the window is small - and a full disk, a kill, a closed lid
or a crash in the two lines between is enough to land in it. What is left is a
0-byte file, and a 0-byte issue is not a short issue: the body is the part with
no other copy, which is the reason this tool exists at all.

So the checks here are about the failure path, not the happy one, and they run
the failure for real: a proxy that raises the moment anything is written, the
same shape a full disk has. Three things have to hold - the old bytes survive
exactly, no temp file is left behind either way, and the bytes a successful
write produces are the ones they always were.

The last check is the one guarding the others: it points the same injected
failure at a plain truncating write and asserts that one *does* erase the file.
Without it, an injection that quietly stopped firing would leave every
assertion above passing and prove nothing.

Run: uv run python tests/test_atomic.py
"""

import os
import tempfile

from helpers import run
from cli_issue_tracker import storage
from cli_issue_tracker.issues import create_issue
from cli_issue_tracker.issues import start_issue
from cli_issue_tracker.plan import plan_path
from cli_issue_tracker.plan import write_plan
from cli_issue_tracker.storage import parse_issue
from cli_issue_tracker.storage import read_issue
from cli_issue_tracker.storage import write_issue

from helpers import legacy_create
create_issue = legacy_create

REAL_OPEN = open


class DiskFull(Exception):
    """What the injection raises. Named for the case it stands in for."""


class Full:
    """A file that accepts being opened and refuses to hold anything.

    A proxy rather than a patched method because TextIOWrapper does not allow
    one to be assigned. `__exit__` still closes the real handle - on Windows an
    open handle cannot be unlinked, and the cleanup path being able to remove
    its own temp file is half of what is under test."""

    def __init__(self, file):
        self.file = file

    def write(self, text):
        raise DiskFull("disk full")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.file.close()
        return False


def failing_open(*args, **kwargs):
    return Full(REAL_OPEN(*args, **kwargs))


def raw(path):
    with REAL_OPEN(path, "rb") as file:
        return file.read()


def strays(directory):
    """Anything in the directory that is not an issue or a plan. Every reader
    here filters on `.md`, so a leftover temp file is invisible to them and
    would only ever be found by a check that goes looking for it."""
    return [
        name
        for name in os.listdir(directory)
        if not name.endswith(".md") and os.path.isfile(os.path.join(directory, name))
    ]


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        os.environ["ISSUE_USER"] = "tester"
        try:
            _, out, _ = run(create_issue, "Keep this prose", "The paragraph with no other copy.", "high")
            id = "ISS-001"
            path = os.path.join(tmp, f"{id}.md")
            before = raw(path)
            assert before, "nothing was written to begin with"

            # An issue write that fails part-way. The exception reaches the
            # caller - swallowing it would report a write that did not happen.
            issue = read_issue(id)
            issue["priority"] = "low"
            storage.open = failing_open
            try:
                write_issue(issue)
            except DiskFull:
                pass
            else:
                raise AssertionError("the injected failure did not fire")
            finally:
                storage.open = REAL_OPEN

            assert raw(path) == before, "a failed write changed the file"
            assert parse_issue(path) is not None, "the file no longer parses as an issue"
            assert not strays(tmp), strays(tmp)

            # The same guarantee for the plan, where the blast radius is
            # different rather than smaller: `start` will not reseed over a
            # plan that exists, so a 0-byte one is a checkpoint list that
            # cannot be recovered.
            run(start_issue, id)
            seeded = plan_path(id)
            plan_before = raw(seeded)
            work = os.path.dirname(seeded)

            storage.open = failing_open
            try:
                write_plan(id, "Keep this prose")
            except DiskFull:
                pass
            else:
                raise AssertionError("the injected failure did not fire for the plan")
            finally:
                storage.open = REAL_OPEN

            assert raw(seeded) == plan_before, "a failed write changed the plan"
            assert not strays(work), strays(work)

            # The success path is unchanged: the exact bytes, LF, and nothing
            # left beside the file. `join_file` already committed to "\n" and
            # the replacement must not have quietly reintroduced the platform
            # default that ISS-033 was about.
            written = write_issue(read_issue(id))
            assert written == path, written
            after = raw(path)
            assert b"\r\n" not in after, "CRLF came back"
            assert after.startswith(b"---\n"), after[:20]
            assert b"The paragraph with no other copy." in after
            assert not strays(tmp), strays(tmp)

            # And the check that keeps the three above honest: the injection is
            # real, and the shape this replaced really did lose the file.
            truncating = os.path.join(tmp, "not-an-issue.txt")
            with REAL_OPEN(truncating, "w", encoding="utf-8", newline="\n") as file:
                file.write("The paragraph with no other copy.\n")
            try:
                with failing_open(truncating, "w", encoding="utf-8", newline="\n") as file:
                    file.write("replacement")
            except DiskFull:
                pass
            assert os.path.getsize(truncating) == 0, "the injection is no longer failing a write"
        finally:
            storage.open = REAL_OPEN
            os.environ.pop("ISSUES_DIR", None)
            os.environ.pop("ISSUE_USER", None)
    print("ok")


if __name__ == "__main__":
    demo()
