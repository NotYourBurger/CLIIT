"""Checks for `issue next`.

The whole command is one ranking and one guarantee, so that is what this
checks: every term of next_rank in isolation, in-progress ahead of a
higher-priority open issue, a blocked issue never selected in either status,
and the empty backlog exiting 1 with nothing on stdout.

Run: uv run python tests/test_next.py
"""

import json
import os
import tempfile

from helpers import run
from cli_issue_tracker.issues import create_issue, next_issue, set_fields
from cli_issue_tracker.storage import parse_issue, write_issue


def filed_at(tmp, id, created_at):
    """Backdate an issue. create_issue reads a clock with second precision, so
    issues filed in a loop share a created_at and the tie-breaker under test
    never gets exercised."""
    issue = parse_issue(os.path.join(tmp, f"{id}.md"))
    issue["created_at"] = created_at
    write_issue(issue)


def picked(**kwargs):
    code, out, _ = run(next_issue, **kwargs)
    assert code is None, (code, out)
    return out.split()[0]


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        try:
            # Nothing at all is the same answer as nothing actionable.
            code, out, err = run(next_issue)
            assert code == 1 and out == "" and "Nothing to work on" in err, (code, out, err)

            for n in range(1, 6):
                run(create_issue, f"Issue {n}", "...", "medium")
            run(set_fields, ["ISS-001"], "low")
            run(set_fields, ["ISS-002"], "high")

            # Priority first among open issues, and the output says why.
            code, out, _ = run(next_issue)
            assert out.splitlines() == [
                "ISS-002  Issue 2",
                "Status:   open",
                "Priority: high",
                "Ready:    yes",
            ], out

            # An in-progress issue outranks a higher-priority open one: the
            # work already started is the work about to be abandoned.
            run(set_fields, ["ISS-004", "in-progress"])
            assert picked() == "ISS-004"
            # ...and says so rather than "Ready: no", which is what the JSON's
            # `ready` says for the same issue - that word belongs to --ready.
            _, out, _ = run(next_issue)
            assert "Ready:    in progress" in out, out
            _, out, _ = run(next_issue, as_json=True)
            assert json.loads(out)["ready"] is False, out

            # Blocked is never selected, in either status.
            run(set_fields, ["ISS-004"], None, (), (), ["ISS-005"])
            assert picked() == "ISS-002"
            run(set_fields, ["ISS-002"], None, (), (), ["ISS-005"])
            assert picked() == "ISS-003"

            # Unblocking by closing the blocker puts it back at the top - the
            # readiness rule is in_the_way's, not a second copy.
            run(set_fields, ["ISS-005", "closed"])
            assert picked() == "ISS-004"

            # Priority ranks above nothing-at-all: ISS-003 and ISS-005 are
            # medium, ISS-001 is low, and an issue with no priority field at
            # all is last of the four.
            issue = parse_issue(os.path.join(tmp, "ISS-005.md"))
            del issue["priority"]
            issue["status"] = "open"
            write_issue(issue)
            run(set_fields, ["ISS-004", "ISS-002", "closed"])
            assert picked() == "ISS-003"
            run(set_fields, ["ISS-003", "closed"])
            assert picked() == "ISS-001"
            run(set_fields, ["ISS-001", "closed"])
            assert picked() == "ISS-005"

            # Same status, same priority: the older one, then the lower id -
            # and the answer does not move between two identical calls.
            run(set_fields, ["ISS-002"], None, (), (), (), ["ISS-005"])
            run(set_fields, ["ISS-005", "closed"])
            run(set_fields, ["ISS-001", "ISS-002", "ISS-003", "open"], "medium")
            filed_at(tmp, "ISS-001", "2026-01-02T00:00:00+06:00")
            filed_at(tmp, "ISS-002", "2026-01-01T00:00:00+06:00")
            filed_at(tmp, "ISS-003", "2026-01-01T00:00:00+06:00")
            assert picked() == "ISS-002"
            assert picked() == "ISS-002"

            # --json is one object, not an array of one, and nothing else is
            # on stdout to trip a parser.
            _, out, _ = run(next_issue, as_json=True)
            chosen = json.loads(out)
            assert chosen["id"] == "ISS-002" and chosen["ready"] is True, chosen
            assert chosen["blocks"] == [] and chosen["blocked_by"] == [], chosen

            # Read-only: the pick is unchanged on disk after all of that.
            before = parse_issue(os.path.join(tmp, "ISS-002.md"))
            run(next_issue)
            run(next_issue, as_json=True)
            assert parse_issue(os.path.join(tmp, "ISS-002.md")) == before

            # Everything closed is the empty case again, and --json keeps
            # stdout empty rather than printing a sentence into it.
            run(set_fields, ["ISS-001", "ISS-002", "ISS-003", "closed"])
            code, out, err = run(next_issue, as_json=True)
            assert code == 1 and out == "" and "Nothing to work on" in err, (code, out, err)
        finally:
            os.environ.pop("ISSUES_DIR", None)
    print("ok")


if __name__ == "__main__":
    demo()
