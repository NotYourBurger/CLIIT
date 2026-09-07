"""The doctor for the format that is the API.

Every other check here asserts what a command does with a file it wrote.
This one asserts what `check` says about files it did not: a hand-edited
status, a blocker whose file is gone, a plan whose issue is. The round trip
is the one that matters most and shows least - a parser bug does not raise,
it returns a plausible dict that gets written back over the user's prose.

Run: uv run python tests/test_check.py
"""

import json
import os
import tempfile

from helpers import REPO, run
from cli_issue_tracker.check import check

# A key written twice parses to the last value and rewrites as one line, so
# the first is gone and nothing ever said so. The whole reason for check 1.
WRITTEN_TWICE = """---
id: ISS-901
status: open
created_at: x
labels: auth
labels: sessions
---

# Written twice
"""

# blocked_by pointing at a file that is not there. Nothing blocks, nothing
# lists it, and until now nothing said a word.
WAITING_ON_NOTHING = """---
id: ISS-902
status: open
created_at: x
blocked_by: ISS-999
---

# Waiting on nothing
"""

# A word nobody wrote. `actionable` drops an unknown status silently, so this
# issue is gone from `next` with nothing said about it - and `priority` here
# matches no --priority filter either.
HAND_TYPED = """---
id: ISS-903
status: wip
created_at: x
priority: urgent
---

# Typed by hand
"""


def write(name, text, where=None):
    path = os.path.join(where, name)
    with open(path, "w", encoding="utf-8") as file:
        file.write(text)
    return path


if __name__ == "__main__":
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        issues = os.path.join(tmp, ".issues")
        os.makedirs(issues)
        os.environ["ISSUES_DIR"] = issues
        try:
            # 1. Nothing wrong is nothing said. A doctor that always prints
            #    something is a doctor nobody runs.
            code, out, err = run(check)
            assert code is None and out == "" and err == "", (code, out, err)

            # 2. The round trip: the failure class that corrupts silently.
            write("ISS-901.md", WRITTEN_TWICE, where=issues)
            code, out, err = run(check)
            assert code == 1 and out == "", (code, out, err)
            assert "ISS-901" in err and "rewrite" in err, err

            # 3. A blocker whose file is gone. `in_the_way` refuses to let a
            #    missing id block anything, which is right and is also why
            #    nothing has ever exited non-zero about it.
            write("ISS-902.md", WAITING_ON_NOTHING, where=issues)
            code, out, err = run(check)
            assert code == 1, (code, out, err)
            assert "ISS-902" in err and "ISS-999" in err, err

            # 4. A status and a priority outside the tuples. Both vanish from
            #    a filter rather than failing one, which is the quietest way
            #    for an issue to stop existing.
            write("ISS-903.md", HAND_TYPED, where=issues)
            code, out, err = run(check)
            assert code == 1, (code, out, err)
            assert "ISS-903" in err and "wip" in err and "urgent" in err, err

            # 5. A plan with no issue beside it. The plan is named after the
            #    issue and has no identity of its own, so an id that is not
            #    there means the work is being recorded against nothing.
            os.makedirs(os.path.join(issues, "work"))
            write("ISS-904.md", "# ISS-904 Work Plan", where=os.path.join(issues, "work"))
            code, out, err = run(check)
            assert code == 1, (code, out, err)
            assert "ISS-904" in err and "work" in err, err

            # Every finding, still there together: four scenarios, four lines,
            # and none of them masking another.
            assert len(err.strip().splitlines()) == 5, err

            # 6. --json moves the findings to stdout, where a script reads
            #    them. Same findings, same exit code - the rendering is the
            #    only thing that changes.
            code, out, err = run(check, as_json=True)
            assert code == 1 and err == "", (code, out, err)
            found = json.loads(out)
            # Grouped by file, in id order: everything wrong with ISS-903 is
            # two lines together, not two lines with someone else between them.
            assert [item["file"] for item in found] == [
                "ISS-901.md",
                "ISS-902.md",
                "ISS-903.md",
                "ISS-903.md",
                os.path.join("work", "ISS-904.md"),
            ], found
            assert all(item["problem"] for item in found), found

            # 7. The twenty-six real files, which are the ones that matter.
            #    test_storage reads one issue off disk; this reads every one,
            #    and the day a parser change starts eating prose it fails
            #    here rather than in an issue nobody reopens for a month.
            os.environ["ISSUES_DIR"] = os.path.join(REPO, ".issues")
            code, out, err = run(check)
            assert code is None, (code, out, err)

        finally:
            os.chdir(original)
            os.environ.pop("ISSUES_DIR", None)
    print("ok")
