"""Checks for issue priority.

The branch worth checking is the old issues: thirteen files on disk have no
priority field, and the rule is that missing is missing - they still list, they
show "-", and they match no --priority filter.

Run: uv run python tests/test_priority.py
"""

import os
import tempfile

from helpers import run
from cli_issue_tracker.issues import create_issue, list_issues, set_fields
from cli_issue_tracker.storage import parse_issue, write_issue


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        try:
            # An issue from before the field existed: no priority key at all.
            write_issue(
                {
                    "id": "ISS-001",
                    "status": "open",
                    "created_at": "2026-01-01T00:00:00+06:00",
                    "body": "# Old issue\n\nFiled before priorities.",
                }
            )
            run(create_issue, "Login bug", "...", "high")

            filed = parse_issue(os.path.join(tmp, "ISS-002.md"))
            assert filed["priority"] == "high", filed
            assert parse_issue(os.path.join(tmp, "ISS-001.md")).get("priority") is None

            # A word that is not a priority fails before anything is written -
            # otherwise a typo burns an id.
            code, _, _ = run(create_issue, "Typo", "...", "urgent")
            assert code == 1, code
            assert not os.path.exists(os.path.join(tmp, "ISS-003.md")), "id was burned"
            assert run(list_issues, None, "urgent")[0] == 1, "bad filter must exit 1"

            # Both issues list; the old one shows "-" rather than a priority
            # nobody set.
            _, table, _ = run(list_issues)
            assert "PRIORITY" in table, table
            assert "high" in table and "-" in table, table

            _, only_high, _ = run(list_issues, None, "high")
            assert "ISS-002" in only_high and "ISS-001" not in only_high, only_high

            # No issue matches, and the message says what was asked for.
            _, empty, _ = run(list_issues, None, "low")
            assert empty.strip() == "No low issues", empty
            _, empty, _ = run(list_issues, "closed", "low")
            assert empty.strip() == "No low closed issues", empty

            # set: the status is still a bare word, priority is a flag, and
            # either one alone is enough.
            assert run(set_fields, ["ISS-001"], "low")[0] is None
            assert parse_issue(os.path.join(tmp, "ISS-001.md"))["priority"] == "low"
            assert parse_issue(os.path.join(tmp, "ISS-001.md"))["status"] == "open"

            run(set_fields, ["ISS-001", "ISS-002", "closed"])
            assert parse_issue(os.path.join(tmp, "ISS-002.md"))["status"] == "closed"
            assert parse_issue(os.path.join(tmp, "ISS-002.md"))["priority"] == "high", (
                "the status word must not touch the priority"
            )

            # Read bottom-up: closed above open, and within a status the
            # highest priority last, nearest the prompt.
            run(set_fields, ["ISS-002"], "low")
            run(create_issue, "Urgent", "...", "high")
            run(set_fields, ["ISS-001", "closed"])
            _, table, _ = run(list_issues)
            rows = [line.split()[0] for line in table.splitlines()[1:] if line.startswith("ISS")]
            assert rows == ["ISS-001", "ISS-002", "ISS-003"], rows

            # Both at once, then the same call again - the second is a no-op
            # that still reports success.
            _, said, _ = run(set_fields, ["ISS-002", "open"], "medium")
            assert "has been set to open, priority medium" in said, said
            _, said, _ = run(set_fields, ["ISS-002", "open"], "medium")
            assert "is already open, priority medium" in said, said

            # Half of it already true: the message must report what moved, not
            # what was asked for.
            _, said, _ = run(set_fields, ["ISS-002", "open"], "low")
            assert "has been set to priority low" in said, said
            assert "open" not in said, said

            # Nothing asked for, and a mistyped status - which is the same
            # branch, because a word that is not a status was read as an id.
            assert run(set_fields, ["ISS-001"])[0] == 1
            assert run(set_fields, ["ISS-001", "opne"])[0] == 1
            assert run(set_fields, ["ISS-001"], "urgent")[0] == 1
            assert run(set_fields, ["closed"])[0] == 1, "a status with no ids"
            assert run(set_fields, ["ISS-404"], "low")[0] == 1, "missing id must exit 1"
        finally:
            os.environ.pop("ISSUES_DIR", None)
    print("ok")


if __name__ == "__main__":
    demo()
