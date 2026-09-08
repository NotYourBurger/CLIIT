"""Two writers in one worktree do not lose each other's work.

Every write here is read-validate-modify-write with nothing serialising it, so
two agents in the same `.issues/` interleave. Two shapes of that, both reported
in ISS-039 and both forced here rather than raced for:

- a claim `try_claim` told *both* callers they won, because reading the file
  back only proves ownership when the two writes are adjacent, and a third
  operation fits between a writer's write and its read-back;
- an id `next_id` handed out twice, because a directory scan answers a question
  about a moment and both callers wrote to the same name.

Nothing in here sleeps and waits to see what happens. The id checks force the
interleaving directly - both callers allocate before either writes - and the
lock checks use a child process that says on disk when it holds the lock, so
"held" is a fact the parent reads rather than a duration it hopes for. The
non-blocking acquire exists for exactly that: it turns "does the lock hold" into
an assertion instead of a stopwatch.

Run: uv run python tests/test_concurrency.py
"""

import os
import subprocess
import sys
import tempfile
import time

from helpers import run
from cli_issue_tracker.convert_id import next_id
from cli_issue_tracker.convert_id import reserve_id
from cli_issue_tracker.issues import create_issue
from cli_issue_tracker.issues import try_claim
from cli_issue_tracker.storage import Busy
from cli_issue_tracker.storage import locked
from cli_issue_tracker.storage import read_issue

# A child that takes the lock, says so by creating the empty marker `held`, and
# keeps it until `release` appears - or until it is killed, which is the whole
# point of the stale-lock check. Inline rather than a fixture file: it is nine
# lines and it only makes sense next to the assertions that read its signals.
# The markers are created with os.open and never written to: an empty file is
# the whole signal, so there is no text and no encoding to state.
HOLDER = """
import os, sys, time
sys.path.insert(0, %r)
os.environ["ISSUES_DIR"] = sys.argv[1]
from cli_issue_tracker.storage import locked
with locked():
    os.close(os.open(os.path.join(sys.argv[1], "held"), os.O_CREAT | os.O_WRONLY))
    while not os.path.exists(os.path.join(sys.argv[1], "release")):
        time.sleep(0.01)
"""


def holder(tmp):
    """Start the child and return it once it actually holds the lock."""
    source = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
    child = subprocess.Popen([sys.executable, "-c", HOLDER % source, tmp])
    deadline = time.monotonic() + 30
    while not os.path.exists(os.path.join(tmp, "held")):
        assert child.poll() is None, f"the holder exited with {child.returncode}"
        assert time.monotonic() < deadline, "the holder never took the lock"
        time.sleep(0.01)
    return child


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        try:
            # Two creates that both allocate before either writes - the exact
            # interleaving that printed two "has been created" lines and left
            # one file. Reservation is what makes it forceable in one process:
            # the id is not an answer, it is a file that now exists.
            first, second = reserve_id(tmp), reserve_id(tmp)
            assert first != second, f"one id for two creates: {first}"
            assert sorted(os.listdir(tmp)) == [f"{first}.md", f"{second}.md"]
            for name in (first, second):
                os.unlink(os.path.join(tmp, f"{name}.md"))

            # And the scan on its own is still the scan - it has to keep
            # answering "what is next" for the reservation loop to count past
            # a file someone else just took.
            assert next_id(tmp) == next_id(tmp), "next_id is not supposed to allocate"

            run(create_issue, "Alice's report", "Body A", "high")
            run(create_issue, "Bob's report", "Body B", "high")
            ids = sorted(n for n in os.listdir(tmp) if n.endswith(".md"))
            assert ids == ["ISS-001.md", "ISS-002.md"], ids
            assert read_issue("ISS-001")["title"] == "Alice's report"
            assert read_issue("ISS-002")["title"] == "Bob's report"

            # A claim is one caller's, and the loser is told so rather than
            # being told it won and starting the same work.
            assert try_claim("ISS-001", "alice") is True
            assert try_claim("ISS-001", "bob") is False
            assert read_issue("ISS-001")["assignee"] == "alice"

            # The lock those two now run inside really does exclude another
            # process. Forced, not timed: the child has the lock before this
            # line runs, and a non-blocking acquire answers immediately.
            child = holder(tmp)
            try:
                try:
                    with locked(blocking=False):
                        raise AssertionError("two processes held the lock at once")
                except Busy:
                    pass
            finally:
                os.close(os.open(os.path.join(tmp, "release"), os.O_CREAT | os.O_WRONLY))
                child.wait(timeout=30)
            os.unlink(os.path.join(tmp, "held"))
            os.unlink(os.path.join(tmp, "release"))

            # And it is released when the holder is gone. This is why the lock
            # is the kernel's and not a file with a timestamp in it: a killed
            # agent must not wedge the tracker for everyone after it.
            child = holder(tmp)
            child.kill()
            child.wait(timeout=30)
            with locked(blocking=False):
                pass
            assert try_claim("ISS-002", "bob") is True, "a killed holder wedged the lock"

            # Cheap enough that every write can take it. A poll-and-sleep
            # implementation would blow this by two orders of magnitude.
            started = time.monotonic()
            for _ in range(100):
                with locked():
                    pass
            elapsed = time.monotonic() - started
            assert elapsed < 2, f"100 lock round trips took {elapsed:.2f}s"
        finally:
            os.environ.pop("ISSUES_DIR", None)
    print("ok")


if __name__ == "__main__":
    demo()
