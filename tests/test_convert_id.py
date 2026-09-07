"""Keep the allocator's inline invariants in the one-command suite.

`convert_id.py` remains directly executable because that makes its narrow
self-check cheap while editing it. This wrapper makes the same check part of
`tests/all.py`, where it cannot be skipped by habit.

Run: uv run python tests/test_convert_id.py
"""

import os
import subprocess
import sys

from helpers import REPO


if __name__ == "__main__":
    path = os.path.join(REPO, "src", "cli_issue_tracker", "convert_id.py")
    done = subprocess.run(
        [sys.executable, path],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert done.returncode == 0, (done.returncode, done.stdout, done.stderr)
    assert done.stdout == "ok\n" and done.stderr == "", (done.stdout, done.stderr)
    print("ok")
