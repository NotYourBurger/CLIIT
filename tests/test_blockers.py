"""Checks for issue dependencies.

The branches worth checking are the ones a single-file field never had: the
edge is stored on one side and read from both, "ready" depends on another
file's status, and the three ways of writing a bad edge have to fail before
anything lands on disk. Plus the two rules that look like bugs until you read
them - a missing blocker does not block, and a blocked issue can still be
worked on.

Run: uv run python tests/test_blockers.py
"""

import json
import os
import tempfile

from helpers import close
from helpers import run
from cli_issue_tracker.issues import (
    blockers_of,
    create_issue,
    list_issues,
    set_fields,
    view_issue,
)
from cli_issue_tracker.storage import parse_issue


def read(tmp, id):
    return parse_issue(os.path.join(tmp, f"{id}.md"))


def ids(text):
    return [line.split()[0] for line in text.splitlines() if line.startswith("ISS")]


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        try:
            for n in range(1, 5):
                run(create_issue, f"Issue {n}", "...", "medium")

            # One side of the edge: the stuck issue records it, the blocker's
            # file does not change at all.
            before = read(tmp, "ISS-001")
            _, said, _ = run(set_fields, ["ISS-002"], None, (), (), ["ISS-001"])
            assert "has been set to blocked by [ISS-001]" in said, said
            assert read(tmp, "ISS-002")["blocked_by"] == "ISS-001"
            assert read(tmp, "ISS-001") == before, "the blocker's file must not move"

            # Repeatable and merging, like --label, and adding one that is
            # already there is not a change.
            run(set_fields, ["ISS-002"], None, (), (), ["ISS-003"])
            assert blockers_of(read(tmp, "ISS-002")) == ["ISS-001", "ISS-003"]
            _, said, _ = run(set_fields, ["ISS-002"], None, (), (), ["ISS-003"])
            assert "is already blocked by [ISS-001, ISS-003]" in said, said

            # --unblock removes, and the last one takes the field with it.
            run(set_fields, ["ISS-002"], None, (), (), (), ["ISS-003"])
            assert blockers_of(read(tmp, "ISS-002")) == ["ISS-001"]
            _, said, _ = run(set_fields, ["ISS-002"], None, (), (), (), ["ISS-001"])
            assert "not blocked" in said, said
            assert "blocked_by" not in read(tmp, "ISS-002"), read(tmp, "ISS-002")
            run(set_fields, ["ISS-002"], None, (), (), ["ISS-001"])

            # Nothing written for an unknown id, a self-link or a cycle - and
            # the cycle prints the path, not "cycle detected".
            was = read(tmp, "ISS-002")
            assert run(set_fields, ["ISS-002"], None, (), (), ["ISS-099"])[0] == 1
            assert run(set_fields, ["ISS-002"], None, (), (), ["ISS-002"])[0] == 1
            code, _, err = run(set_fields, ["ISS-001"], None, (), (), ["ISS-002"])
            assert code == 1, code
            assert "ISS-001 -> ISS-002 -> ISS-001" in err, err
            assert read(tmp, "ISS-002") == was, "a rejected edge must write nothing"

            # A longer cycle prints the whole route, so you can see which edge
            # to drop: 3 waits on 2 waits on 1, and 1 must not wait on 3.
            run(set_fields, ["ISS-003"], None, (), (), ["ISS-002"])
            _, _, err = run(set_fields, ["ISS-001"], None, (), (), ["ISS-003"])
            assert "ISS-001 -> ISS-003 -> ISS-002 -> ISS-001" in err, err
            run(set_fields, ["ISS-003"], None, (), (), (), ["ISS-002"])

            # --ready is open with every blocker closed; --blocked is the
            # complement, and both AND with the other filters.
            _, ready, _ = run(list_issues, None, None, (), False, True)
            assert ids(ready) == ["ISS-001", "ISS-003", "ISS-004"], ready
            _, stuck, _ = run(list_issues, None, None, (), False, False, True)
            assert ids(stuck) == ["ISS-002"], stuck
            assert "No high ready issues" in run(list_issues, None, "high", (), False, True)[1]

            # The blocked line shows on plain `list`, not only under --blocked -
            # a blocked row that looks like a ready one is the whole problem.
            _, table, _ = run(list_issues)
            assert "    blocked by ISS-001 (open)" in table.splitlines(), table

            # Closing the blocker frees it, and says so on the same run.
            _, said, _ = close("ISS-001")
            assert "ISS-002 is now ready" in said, said
            _, ready, _ = run(list_issues, None, None, (), False, True)
            assert ids(ready) == ["ISS-002", "ISS-003", "ISS-004"], ready
            # A closed blocker is not in the way, so no line under the row.
            _, table, _ = run(list_issues)
            assert not any(line.startswith("    ") for line in table.splitlines()), table
            # Closing something nothing waited on frees nothing, quietly.
            _, said, _ = close("ISS-004")
            assert "now ready" not in said, said

            # Direct blockers only: 3 waits on 2, someone closes 2 while 1 is
            # open again - 3 is ready, because closing 2 was a decision.
            run(set_fields, ["ISS-003"], None, (), (), ["ISS-002"])
            run(set_fields, ["ISS-001"], None, (), (), ["ISS-004"])
            run(set_fields, ["ISS-001", "open"])
            run(set_fields, ["ISS-002"], None, (), (), ["ISS-001"])
            close("ISS-002")
            _, ready, _ = run(list_issues, None, None, (), False, True)
            assert "ISS-003" in ids(ready), ready

            # Blocked is not forbidden: in-progress on a blocked issue says
            # what is in the way, on stderr, and then does it.
            run(set_fields, ["ISS-003"], None, (), (), (), ["ISS-002"])
            run(set_fields, ["ISS-003"], None, (), (), ["ISS-001"])
            code, said, err = run(set_fields, ["ISS-003", "in-progress"])
            assert code is None, code
            assert "ISS-003 is blocked by ISS-001 (open)" in err, err
            assert read(tmp, "ISS-003")["status"] == "in-progress", "must still write"

            # A missing blocker never blocks - it can never be closed - but it
            # prints as (missing) everywhere an id is shown.
            os.remove(os.path.join(tmp, "ISS-001.md"))
            _, table, _ = run(list_issues)
            assert "    blocked by ISS-001 (missing)" in table.splitlines(), table
            _, ready, _ = run(list_issues, None, None, (), False, True)
            assert "ISS-004" not in ids(ready), "closed is not ready"
            run(set_fields, ["ISS-003", "open"])
            _, ready, _ = run(list_issues, None, None, (), False, True)
            assert "ISS-003" in ids(ready), ready
            # And it is removable, which is the repair: --unblock takes an id
            # whose file is gone, where --blocked-by would not.
            run(set_fields, ["ISS-003"], None, (), (), (), ["ISS-001"])
            assert "blocked_by" not in read(tmp, "ISS-003")

            # view shows both directions, each id with its status.
            run(set_fields, ["ISS-003"], None, (), (), ["ISS-002"])
            _, shown, _ = run(view_issue, "ISS-002")
            assert "Blocked by:" in shown and "ISS-001 (missing)" in shown, shown
            assert "Blocks:" in shown and "ISS-003 (open)" in shown, shown
            # Nothing on either side, no lines at all.
            _, shown, _ = run(view_issue, "ISS-004")
            assert "Blocked by" not in shown and "Blocks" not in shown, shown

            # --json: both directions as arrays, plus ready, on every issue.
            _, dump, _ = run(list_issues, None, None, (), True)
            found = {issue["id"]: issue for issue in json.loads(dump)}
            assert found["ISS-003"]["blocked_by"] == ["ISS-002"], found["ISS-003"]
            assert found["ISS-002"]["blocks"] == ["ISS-003"], found["ISS-002"]
            # A closed blocker is recorded but not in the way, so ready holds.
            assert found["ISS-003"]["ready"] is True, found["ISS-003"]
            assert found["ISS-002"]["ready"] is False, "closed is never ready"
            assert found["ISS-004"]["blocked_by"] == [] and found["ISS-004"]["blocks"] == []
        finally:
            os.environ.pop("ISSUES_DIR", None)
    print("ok")


if __name__ == "__main__":
    demo()
