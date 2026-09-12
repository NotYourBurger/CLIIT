"""Checks for `issue search`.

The branches worth checking: all query words must match but they may be on
different lines, the filters AND with the query, the match line shows up under
the row but the title line does not, and nothing found is exit 1 - which is the
one place search disagrees with list.

Run: uv run python tests/test_search.py
"""

import json
import os
import tempfile

from helpers import run
from cli_issue_tracker.issues import create_issue, list_issues, search_issues


from helpers import legacy_create
create_issue = legacy_create


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        try:
            run(
                create_issue,
                "Signup is broken",
                "The verification of the email never arrives.\nClerk returns 500.",
                "high",
                ["bug"],
            )
            run(create_issue, "Rotate the OAuth secrets", "Authentication keys expire soon.", "low")
            run(create_issue, "Write the README", "Nothing to do with mail.", "medium")

            # Every word, anywhere, in any order - and on different lines, which
            # is what a phrase search would miss.
            code, table, _ = run(search_issues, "verification email")
            assert code is None, code
            assert "ISS-001" in table and "ISS-002" not in table, table
            code, table, _ = run(search_issues, "clerk signup")
            assert "ISS-001" in table, table

            # Substring, case-insensitive: auth finds authentication and OAuth.
            _, table, _ = run(search_issues, "AUTH")
            assert "ISS-002" in table and "ISS-001" not in table, table

            # One word present, one missing, matches nothing - more words narrow.
            code, _, err = run(search_issues, "clerk readme")
            assert code == 1, code
            assert "clerk readme" in err, err

            # The line the match came from is printed under the row; a title-only
            # match adds no line, because the TITLE column already showed it.
            _, table, _ = run(search_issues, "clerk")
            assert "    Clerk returns 500." in table.splitlines(), table
            _, table, _ = run(search_issues, "readme")
            assert "ISS-003" in table, table
            assert not any(line.startswith("    ") for line in table.splitlines()), table

            # Filters AND with the query and with each other.
            assert run(search_issues, "the", "open")[0] is None
            assert run(search_issues, "the", "closed")[0] == 1, "status must narrow"
            _, table, _ = run(search_issues, "the", None, "high")
            assert "ISS-001" in table and "ISS-002" not in table, table
            assert run(search_issues, "the", None, None, ["bug"])[0] is None
            assert run(search_issues, "oauth", None, None, ["bug"])[0] == 1, "label must narrow"
            assert run(search_issues, "clerk", None, "low")[0] == 1, "priority must narrow"

            # Bad filter words fail the same way they do on list.
            assert run(search_issues, "clerk", "opne")[0] == 1
            assert run(search_issues, "clerk", None, "urgent")[0] == 1

            # An empty query is an error, not a listing of everything.
            assert run(search_issues, "   ")[0] == 1

            # Same order as list: least urgent first, and the same rows.
            _, listed, _ = run(list_issues)
            _, searched, _ = run(search_issues, "the")
            ids = lambda text: [
                line.split()[0] for line in text.splitlines() if line.startswith("ISS")
            ]
            assert ids(listed) == ids(searched) == ["ISS-002", "ISS-003", "ISS-001"], searched

            # --json: the list array plus why each issue matched.
            code, payload, _ = run(search_issues, "clerk", None, None, (), True)
            found = json.loads(payload)
            assert [issue["id"] for issue in found] == ["ISS-001"], found
            assert found[0]["matches"] == ["Clerk returns 500."], found
            assert found[0]["labels"] == ["bug"], found

            # Nothing found is still valid JSON on stdout, the reason on stderr,
            # and exit 1 either way - grep's contract.
            code, payload, err = run(search_issues, "nonesuch", None, None, (), True)
            assert code == 1, code
            assert json.loads(payload) == [], payload
            assert "nonesuch" in err and payload.strip() == "[]", (payload, err)
        finally:
            os.environ.pop("ISSUES_DIR", None)
    print("ok")


if __name__ == "__main__":
    demo()
