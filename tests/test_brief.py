"""Checks for `issue brief`.

The brief is a rendering of decisions other functions already made, so what is
worth checking is that it never grows a second opinion: `brief` and `next` name
the same issue, the ready list is the same order minus that issue, and the caps
say how much they hid. Plus the two things only this command says out loud - a
blocker with no file, and a close from before `closed_at` existed.

Run: uv run python tests/test_brief.py
"""

import json
import os
import re
import tempfile

from helpers import close
from helpers import run
from cli_issue_tracker.issues import brief, create_issue, next_issue, set_fields
from cli_issue_tracker.storage import parse_issue, write_issue


def edit(tmp, id, **fields):
    """Write frontmatter the CLI will not write: a blocker whose file never
    existed (--blocked-by refuses one) and a close from before `closed_at`.
    None removes the field, the way an emptied one is popped rather than
    written back blank."""
    issue = parse_issue(os.path.join(tmp, f"{id}.md"))
    for field, value in fields.items():
        if value is None:
            issue.pop(field, None)
        else:
            issue[field] = value
    path = write_issue(issue)

    # write_issue reads the clock on every write, which is right for the tool
    # and useless for a fixture that has to have an older or newer one.
    if "updated_at" in fields:
        with open(path, "r", encoding="utf-8") as file:
            text = file.read()
        with open(path, "w", encoding="utf-8", newline="\n") as file:
            file.write(
                re.sub(r"^updated_at: .*$", f"updated_at: {fields['updated_at']}", text, count=1,
                       flags=re.M)
            )


def sections(out):
    """The human brief as {header: lines}, in the order it printed them.
    Sections are separated by a blank line and contain none, which is what
    makes this two lines instead of a parser."""
    found = {}
    for block in out.split("\n\n"):
        header, _, rest = block.partition("\n")
        found[header] = rest.splitlines()
    return found


def agreed():
    """The brief, both renderings, having checked that it and `next` still
    name the same issue - the one way this command can be worse than the five
    it replaces."""
    code, out, _ = run(brief)
    assert code is None, (code, out)
    code, dumped, _ = run(brief, as_json=True)
    assert code is None, (code, dumped)
    data = json.loads(dumped)

    _, chosen, _ = run(next_issue)
    picked = chosen.split()[0] if chosen else None
    assert (data["next"] or {}).get("id") == picked, (data["next"], picked)
    return sections(out), data


from helpers import legacy_create
create_issue = legacy_create


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        try:
            # An empty project is a finding, not a failure: exit 0, and --json
            # is still every key, so a parser has no branch to write.
            code, out, _ = run(brief)
            assert code is None and "No issues yet." in out, (code, out)
            code, out, _ = run(brief, as_json=True)
            data = json.loads(out)
            assert code is None and data["next"] is None, (code, data)
            assert data["ready"] == [] and data["warnings"] == [], data
            assert data["summary"] == {
                "open": 0, "in_progress": 0, "ready": 0, "blocked": 0, "closed": 0
            }, data

            for n in range(1, 10):
                run(create_issue, f"Issue {n}", "...", "medium")
            run(set_fields, ["ISS-001", "in-progress"])
            run(set_fields, ["ISS-002"], "high")
            run(set_fields, ["ISS-003"], None, (), (), ["ISS-009"])
            edit(tmp, "ISS-004", blocked_by="ISS-042")

            found, data = agreed()

            # Printed bottom-up, so this list reads backwards and the prompt
            # lands under PROJECT. Nothing is closed yet, so RECENTLY RESOLVED
            # is absent rather than printed empty.
            assert list(found) == [
                "WARNINGS", "BLOCKED", "READY", "IN PROGRESS", "NEXT", "PROJECT"
            ], list(found)

            # in-progress outranks the high-priority open one, the same
            # ranking `next` uses - which agreed() just confirmed.
            assert found["NEXT"][0].startswith("ISS-001"), found["NEXT"]
            assert data["summary"] == {
                "open": 8, "in_progress": 1, "ready": 7, "blocked": 1, "closed": 0
            }, data["summary"]

            # Five of seven, the highest last - the row nearest the prompt is
            # the one to start first, the arrangement `rank` gives `list`. The
            # "+2 more" opens the block instead of closing it: it summarises
            # the tail that was cut, and under the top row it would read as if
            # it were hiding something more urgent.
            # The next issue is not in there: it is already two sections up.
            # ISS-004 is: a missing blocker never blocks, and the note under
            # the row is the only thing that says the id was ever written.
            rows = [row.split()[0] for row in found["READY"] if row.startswith("ISS-")]
            assert rows == ["ISS-007", "ISS-006", "ISS-005", "ISS-004", "ISS-002"], found["READY"]
            assert found["READY"][5].strip() == "blocked by ISS-042 (missing)", found["READY"]
            assert found["READY"][0] == "+2 more", found["READY"]
            assert data["ready_omitted"] == 2, data["ready_omitted"]
            assert not any(row.startswith("ISS-001") for row in found["READY"]), found["READY"]

            # The reversal is in the printing, after the cap. --json is still
            # most-urgent-first, and it is the same five ids: a parser has no
            # cursor, and moving this into `ranked_actionable` or `closed_key`
            # would quietly change which issue `next` picks.
            assert [issue["id"] for issue in data["ready"]] == rows[::-1], data["ready"]

            # A missing blocker never blocks - ISS-004 is ready above - but it
            # is a hole in the graph and this is the first thing that says so.
            assert found["WARNINGS"] == ["ISS-004 references missing blocker ISS-042"], found
            assert data["warnings"] == [
                {"id": "ISS-004", "missing_blockers": ["ISS-042"]}
            ], data["warnings"]

            # Blocked shows the blocker and its status, not just the id.
            assert found["BLOCKED"][0].startswith("ISS-003"), found["BLOCKED"]
            assert found["BLOCKED"][1].strip() == "blocked by ISS-009 (open)", found["BLOCKED"]

            close("ISS-004", "ISS-005", "ISS-006", "ISS-007", "ISS-008", "ISS-009")

            # Closed before `closed_at` existed: no reason, no close time. It
            # still places, on `updated_at`, and nothing is backfilled into it.
            edit(
                tmp,
                "ISS-004",
                reason=None,
                closed_at=None,
                message=None,
                evidence=None,
                blocked_by=None,
                updated_at="2099-01-01T00:00:00+06:00",
            )

            found, data = agreed()
            assert list(found) == [
                "RECENTLY RESOLVED", "READY", "IN PROGRESS", "NEXT", "PROJECT"
            ], list(found)

            # --json newest first, printed oldest first: the newest close is
            # the one line the reader came for, so it ends up at the prompt.
            resolved = [issue["id"] for issue in data["recently_resolved"]]
            assert resolved == ["ISS-004", "ISS-009", "ISS-008", "ISS-007", "ISS-006"], resolved
            printed = [
                row.split()[0] for row in found["RECENTLY RESOLVED"] if row.startswith("ISS-")
            ]
            assert printed == resolved[::-1], found["RECENTLY RESOLVED"]
            assert data["resolved_omitted"] == 1, data["resolved_omitted"]
            assert found["RECENTLY RESOLVED"][0] == "+1 more", found["RECENTLY RESOLVED"]
            assert "resolution" not in data["recently_resolved"][0], data["recently_resolved"][0]
            assert found["RECENTLY RESOLVED"][-2:] == [
                "ISS-004  Issue 4",
                "         closed",
            ], found["RECENTLY RESOLVED"]
            assert found["RECENTLY RESOLVED"][2].strip() == "completed - done", found

            # Read-only, after all of that.
            before = {name: parse_issue(os.path.join(tmp, name)) for name in os.listdir(tmp)}
            run(brief)
            run(brief, as_json=True)
            assert {
                name: parse_issue(os.path.join(tmp, name)) for name in os.listdir(tmp)
            } == before

            # Everything closed is not a failed lookup - unlike `next`, which
            # exits 1 on the same repo. There is no NEXT and no READY, and the
            # brief still exits 0 with valid JSON.
            close("ISS-001", "ISS-002", "ISS-003")
            found, data = agreed()
            assert list(found) == ["RECENTLY RESOLVED", "PROJECT"], list(found)
            assert data["next"] is None and data["ready"] == [], data
            assert data["summary"]["closed"] == 9, data["summary"]
        finally:
            os.environ.pop("ISSUES_DIR", None)
    print("ok")


if __name__ == "__main__":
    demo()
