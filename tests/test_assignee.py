"""Checks for issue ownership.

The branches worth checking are the ones the other fields do not have: claim
is the only write with a precondition, so it has three ways to fail and one
way to succeed twice; the two filters contradict each other; and the ASSIGNEE
column has to disappear on a repo that owns nothing.

Run: uv run python tests/test_assignee.py
"""

import json
import os
import tempfile

from helpers import close
from helpers import run
from cli_issue_tracker.issues import (
    claim_issue,
    create_issue,
    current_user,
    list_issues,
    set_fields,
    view_issue,
)
from cli_issue_tracker.storage import parse_issue


def read(tmp, id):
    return parse_issue(os.path.join(tmp, f"{id}.md"))


def ids(text):
    """The row ids only - the indented blocked-by notes name ids too."""
    return [line.split()[0] for line in text.splitlines() if line.startswith("ISS")]


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        os.environ["ISSUE_USER"] = "tahmid"
        try:
            for n in range(1, 4):
                run(create_issue, f"Issue {n}", "...", "medium")

            # Nothing is owned yet, so the column is not there at all - the
            # same rule LABELS lives by.
            _, table, _ = run(list_issues)
            assert "ASSIGNEE" not in table, table

            # claim with no --by takes $ISSUE_USER, and prints one line, id first.
            assert current_user() == "tahmid"
            code, said, _ = run(claim_issue, "ISS-001")
            assert code is None and said.strip() == "ISS-001 is now tahmid's", (code, said)
            assert read(tmp, "ISS-001")["assignee"] == "tahmid"

            # Claiming your own again is success, not a conflict.
            code, said, _ = run(claim_issue, "ISS-001", "tahmid")
            assert code is None and said.strip() == "ISS-001 is now tahmid's", (code, said)

            # Someone else's is exit 1, and the message names the owner so the
            # caller knows who to go and ask.
            code, _, err = run(claim_issue, "ISS-001", "codex-1")
            assert code == 1, code
            assert "ISS-001 is already tahmid's" in err, err
            assert read(tmp, "ISS-001")["assignee"] == "tahmid", "nothing must be written"

            # assign has no precondition - handing work over is normal.
            run(set_fields, ["ISS-001"], None, (), (), (), (), "codex-1")
            assert read(tmp, "ISS-001")["assignee"] == "codex-1"
            _, said, _ = run(set_fields, ["ISS-001"], None, (), (), (), (), "codex-1")
            assert "is already codex-1's" in said, said

            # release clears it, and the empty field leaves the file entirely.
            _, said, _ = run(set_fields, ["ISS-001"], None, (), (), (), (), "")
            assert "has been set to unassigned" in said, said
            assert "assignee" not in read(tmp, "ISS-001")
            # Already unassigned is success, the way set treats any no-op.
            code, said, _ = run(set_fields, ["ISS-001"], None, (), (), (), (), "")
            assert code is None and "is already unassigned" in said, (code, said)

            # A closed issue cannot be claimed, but can still be assigned and
            # released - cleaning up after the fact is real.
            close("ISS-003")
            code, _, err = run(claim_issue, "ISS-003")
            assert code == 1 and "closed" in err, (code, err)
            assert run(set_fields, ["ISS-003"], None, (), (), (), (), "tahmid")[0] is None
            assert read(tmp, "ISS-003")["assignee"] == "tahmid"

            # A blocked issue can be claimed: claiming is saying you will do it.
            run(set_fields, ["ISS-002"], None, (), (), ["ISS-001"])
            assert run(claim_issue, "ISS-002")[0] is None
            assert read(tmp, "ISS-002")["assignee"] == "tahmid"

            # Filters AND with everything else, and contradict each other.
            _, owned, _ = run(list_issues, None, None, (), False, False, False, "tahmid")
            assert ids(owned) == ["ISS-003", "ISS-002"], owned
            _, free, _ = run(list_issues, None, None, (), False, False, False, None, True)
            assert ids(free) == ["ISS-001"], free
            code, _, err = run(list_issues, None, None, (), False, False, False, "tahmid", True)
            assert code == 1 and "contradict" in err, (code, err)

            # Nobody owns nothing: the message names the filter that found none.
            _, empty, _ = run(list_issues, None, None, (), False, False, False, "nobody")
            assert empty.strip() == "No nobody's issues", empty

            # The agent loop: ready and nobody's, as JSON.
            _, raw, _ = run(list_issues, None, None, (), True, True, False, None, True)
            rows = json.loads(raw)
            assert [row["id"] for row in rows] == ["ISS-001"], rows
            assert "assignee" not in rows[0], "absent when there is none, like labels"

            _, raw, _ = run(list_issues, None, None, (), True, False, False, "tahmid")
            assert all(row["assignee"] == "tahmid" for row in json.loads(raw))

            # The column is there now, before LABELS, and unowned reads "-".
            _, table, _ = run(list_issues)
            header = table.splitlines()[0]
            assert "ASSIGNEE" in header, header
            run(set_fields, ["ISS-001"], None, ["bug"])
            _, table, _ = run(list_issues)
            header = table.splitlines()[0]
            assert header.index("ASSIGNEE") < header.index("LABELS"), header
            # Unassigned reads "-", not an empty cell.
            row = next(l for l in table.splitlines() if l.startswith("ISS-001"))
            assert row.split() == ["ISS-001", "Issue", "1", "open", "medium",
                                   row.split()[5], "-", "bug"], row

            _, shown, _ = run(view_issue, "ISS-001")
            assert "ASSIGNEE" in shown, shown

            # With no name available at all, claim refuses rather than writing
            # an owner nobody can be held to.
            os.environ["ISSUE_USER"] = ""
            os.environ["GIT_CONFIG_GLOBAL"] = os.path.join(tmp, "nogit")
            os.environ["GIT_CONFIG_SYSTEM"] = os.path.join(tmp, "nogit")
            code, _, err = run(claim_issue, "ISS-001")
            assert code == 1 and "--by" in err, (code, err)
        finally:
            for key in ("ISSUES_DIR", "ISSUE_USER", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM"):
                os.environ.pop(key, None)
    print("ok")


if __name__ == "__main__":
    demo()
