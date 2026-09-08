"""Checks that a value cannot carry the format's own structure into the file.

`clean_set` guards the comma because a comma separates two values. A newline
separates two *fields*, which is the more dangerous of the two: a label
containing one is not a bad label, it is a new frontmatter line, and the issue
it lands in is closed and assigned by someone who never ran close (ISS-040).
The same class covers an id joined onto a path and a prefix joined onto a
filename, which are checked here too because they are the same question asked
of a different argument: does this value stay inside the field it was given to.

Run: uv run python tests/test_injection.py
"""

import os
import tempfile

from helpers import run
from cli_issue_tracker.check import check
from cli_issue_tracker.events import event_command
from cli_issue_tracker.issues import create_issue, log_issue, set_fields, view_issue
from cli_issue_tracker.storage import parse_issue


def read(tmp, id):
    return parse_issue(os.path.join(tmp, f"{id}.md"))


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        try:
            run(create_issue, "Login broken", "...", "high", ["bug"])

            # The payload from the issue: a label whose newline makes every
            # line after it a field of its own.
            payload = "bug\nstatus: closed\nassignee: mallory"
            code, _, said = run(set_fields, ["ISS-001"], None, [payload])
            assert code == 1, f"the newline was accepted (exit {code})"
            assert "newline" in said, said

            # Refused before the write, not after: the issue on disk is
            # untouched, and in particular is still open and unowned.
            issue = read(tmp, "ISS-001")
            assert issue["status"] == "open", issue
            assert "assignee" not in issue, issue
            assert issue["labels"] == "bug", issue

            # A carriage return alone is the same hole, and the one this
            # machine produces on its own: it writes CRLF by default.
            code, _, said = run(set_fields, ["ISS-001"], None, ["bug\rstatus: closed"])
            assert code == 1 and "carriage return" in said, (code, said)

            # `---` fences the frontmatter and `- ` opens a list, so a value the
            # format would read as either is refused too.
            code, _, said = run(set_fields, ["ISS-001"], None, ["--"])
            assert code == 1 and "cannot start with a dash" in said, (code, said)

            # Blockers go through the same one rule, which is the point of it
            # living in clean_set rather than in clean_labels.
            code, _, said = run(
                set_fields, ["ISS-001"], None, (), (), ["ISS-002\nstatus: closed"]
            )
            assert code == 1 and "newline" in said, (code, said)

            # And a printable label is still a label: rejecting a control
            # character must not cost the unicode ones that already round trip.
            run(set_fields, ["ISS-001"], None, ["mañana", "日本語"])
            assert read(tmp, "ISS-001")["labels"] == "bug, mañana, 日本語", read(
                tmp, "ISS-001"
            )
            # An id is joined onto a directory to make a path, and nothing ever
            # checked it was an id. `..` walks out of .issues/ entirely, and the
            # traversal is what makes this a shape check rather than a lookup:
            # "does not exist" is the right answer for ISS-999 and the wrong one
            # for a path.
            outside = os.path.join(tmp, "secret.md")
            with open(outside, "w", encoding="utf-8", newline="\n") as file:
                file.write(
                    "---\nid: SECRET\nstatus: open\ncreated_at: 2026-01-01T00:00:00+00:00\n"
                    "---\n\n# Not an issue\n\nReadable only by walking out of the tracker.\n"
                )
            os.environ["ISSUES_DIR"] = os.path.join(tmp, "nested")
            os.makedirs(os.environ["ISSUES_DIR"], exist_ok=True)

            for command in (view_issue, log_issue):
                code, out, said = run(command, os.path.join("..", "secret"))
                assert code == 1, (command.__name__, code)
                assert "not an issue id" in said, (command.__name__, said)
                assert "Not an issue" not in out, f"{command.__name__} read outside .issues/"

            # The event log is the write half of the same join: a bad id here
            # would create a file, not just read one.
            code, _, said = run(event_command, os.path.join("..", "secret"), "hello")
            assert code == 1 and "not an issue id" in said, (code, said)
            assert not os.path.exists(os.path.join(tmp, "secret.events.jsonl")), "wrote outside"

            # An id of the right shape that simply is not there keeps the old
            # answer - a failed lookup, not a rejected argument.
            code, _, said = run(view_issue, "ISS-999")
            assert code == 1 and "Doesnt Exist" in said, (code, said)

            # The prefix is the other half of the filename and had no check at
            # all, so it could carry a separator of its own.
            for bad in (os.path.join("..", "esc"), "ISS-1", ""):
                os.environ["ISSUE_PREFIX"] = bad
                code, _, said = run(create_issue, "T", "...")
                assert code == 1, (bad, code)
                assert "ISSUE_PREFIX must be letters" in said, (bad, said)
            os.environ.pop("ISSUE_PREFIX", None)
            assert sorted(os.listdir(os.environ["ISSUES_DIR"])) == [], os.listdir(
                os.environ["ISSUES_DIR"]
            )

            # The shape is checked where a user's argument becomes a path, not
            # in the path builders: `issue check` hands read_plan the names it
            # found in work/, and read_plan is documented as never raising. A
            # stray file there is a line in the report, not an exit.
            os.environ["ISSUES_DIR"] = tmp
            os.makedirs(os.path.join(tmp, "work"), exist_ok=True)
            stray = os.path.join(tmp, "work", "notes.md")
            with open(stray, "w", encoding="utf-8", newline="\n") as file:
                file.write("# scratch\n")
            code, out, _ = run(check, False, True)
            assert code in (0, None), code
            assert "notes" in out, out
        finally:
            os.environ.pop("ISSUES_DIR", None)
            os.environ.pop("ISSUE_PREFIX", None)
    print("ok")


if __name__ == "__main__":
    demo()
