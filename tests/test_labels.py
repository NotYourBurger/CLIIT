"""Checks for labels.

Labels are the first field that merges instead of replacing, so the branches
worth checking are the ones status and priority never had: adding what is
already there, removing the last one, and the shape rules that keep a
comma-joined string readable back as a list.

Run: uv run python tests/test_labels.py
"""

import json
import os
import tempfile

from helpers import run
from cli_issue_tracker.issues import create_issue, labels_of, list_issues, set_fields
from cli_issue_tracker.storage import parse_issue


def read(tmp, id):
    return parse_issue(os.path.join(tmp, f"{id}.md"))


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        try:
            run(create_issue, "Login broken", "...", "high", ["bug", "Auth"])
            run(create_issue, "Plain one", "...")

            # Stored as one comma-joined string, lowercased and sorted - the
            # file is read by humans and diffed by git.
            assert read(tmp, "ISS-001")["labels"] == "auth, bug", read(tmp, "ISS-001")
            assert labels_of(read(tmp, "ISS-001")) == ["auth", "bug"]
            # No labels means no field, not an empty one.
            assert "labels" not in read(tmp, "ISS-002"), read(tmp, "ISS-002")
            assert labels_of(read(tmp, "ISS-002")) == []

            # A comma is the delimiter, so it cannot be in a label - and the
            # bad create must not write a file.
            assert run(create_issue, "T", "...", "medium", ["a,b"])[0] == 1
            assert not os.path.exists(os.path.join(tmp, "ISS-003.md")), "id was burned"

            # --label adds rather than replaces, and adding one that is already
            # there is not a change.
            _, said, _ = run(set_fields, ["ISS-001"], None, ["backend"])
            assert "has been set to labels [auth, backend, bug]" in said, said
            _, said, _ = run(set_fields, ["ISS-001"], None, ["backend"])
            assert "is already labels [auth, backend, bug]" in said, said

            # Add, remove and a status in one write, and only what moved is
            # reported - the labels moved, the status did not.
            run(set_fields, ["ISS-001", "closed"])
            _, said, _ = run(set_fields, ["ISS-001", "closed"], None, ["docs"], ["bug"])
            assert "has been set to labels [auth, backend, docs]" in said, said
            assert "closed" not in said, said
            assert labels_of(read(tmp, "ISS-001")) == ["auth", "backend", "docs"]

            # Removing the last label takes the field with it rather than
            # leaving "labels:" on the file.
            run(set_fields, ["ISS-001"], None, (), ["auth", "backend", "docs"])
            assert "labels" not in read(tmp, "ISS-001"), read(tmp, "ISS-001")
            _, said, _ = run(set_fields, ["ISS-001"], None, (), ["auth"])
            assert "is already no labels" in said, said

            run(set_fields, ["ISS-001"], None, ["bug", "auth"])
            assert run(set_fields, ["ISS-001"], None, ["x"], ["x"])[0] == 1, "add and remove"

            # Repeating the filter narrows: every label given, not any of them.
            _, both, _ = run(list_issues, None, None, ["bug", "auth"])
            assert "ISS-001" in both, both
            _, one, _ = run(list_issues, None, None, ["auth", "docs"])
            assert one.strip() == "No auth docs issues", one

            # The column is there only when some issue has labels, and it is
            # last so a long value cannot push another column off the screen.
            _, table, _ = run(list_issues)
            assert table.splitlines()[0].endswith("LABELS"), table
            _, plain, _ = run(list_issues, None, None, ["auth"])
            assert "auth, bug" in plain, plain

            # JSON is where the string becomes an array, so no consumer has to
            # split it again.
            _, dump, _ = run(list_issues, None, None, ["bug"], True)
            assert json.loads(dump)[0]["labels"] == ["auth", "bug"], dump
            _, dump, _ = run(list_issues, "open", None, (), True)
            assert "labels" not in json.loads(dump)[0], "no labels, no key"
        finally:
            os.environ.pop("ISSUES_DIR", None)
    print("ok")


if __name__ == "__main__":
    demo()
