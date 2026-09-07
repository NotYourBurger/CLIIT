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
import re
import subprocess
import tempfile

from helpers import REPO, run
from cli_issue_tracker.check import check
from cli_issue_tracker.plan import seed

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


# A plan with three checkpoints, one of them done. The ticked count needs no
# git, so it is the one column asserted whether or not there is a repo.
SEEDED = """# ISS-901 Work Plan

## Plan

- [x] a
- [ ] b
- [ ] c
"""

# The same plan, one more box ticked - a second commit against it, which is
# the whole thing ISS-031 exists to count.
KEPT = SEEDED.replace("- [ ] b", "- [x] b")

# The seed exactly as `start` writes it, from `seed` itself rather than a copy
# of it here: the fixture must go stale the day the skeleton changes, because
# "is this still only the seed" is a question about that function's output.
ONLY_SEEDED = seed("ISS-902", "Waiting on nothing")

# A plan with no checkpoints at all and one line of prose. The case that says
# `untouched` is not a synonym for `0/0 ticked`: somebody came back, wrote down
# where they were, and never broke the work into boxes.
PROSE_ONLY = ONLY_SEEDED.replace(
    "## Current\n", "## Current\n\nHalfway through the parser.\n"
)


def git(*args, cwd):
    """A git call that never raises. Returns None when there is no git at all,
    which is the case every assertion below stays loose about."""
    try:
        done = subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=cwd,
        )
    except OSError:
        return None
    return done.stdout if done.returncode == 0 else None


def cells(out, id):
    """One row of `--plans`, split back into its columns.

    Two spaces is the separator; every column is padded to its widest value, so
    a fixture added three rows down moves the spaces in every other row. Match
    a literal line and the assertion breaks on a change it is not about."""
    line = next(line for line in out.splitlines() if line.startswith(id + " "))
    return re.split(r" {2,}", line)


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

            # 8. --plans is the other half of this verb: a report, not a
            #    check. One row per plan, on stdout, exit 0 - the threshold
            #    ISS-031 wrote down is a human decision taken once, not a
            #    condition a tool can fail on.
            work = os.path.join(issues, "work")
            write("ISS-901.md", SEEDED, where=work)
            code, out, err = run(check, plans=True)
            assert code is None, (code, out, err)

            # The ticked count comes from read_plan and needs no git, so it is
            # exact whether or not there is a repo here.
            assert "ISS-901" in out and "1/3 ticked" in out, out
            # Every plan, the orphan included: the count needs the rows the
            # findings pass would have thrown away.
            assert "ISS-904" in out and "0/0 ticked" in out, out

            # 8b. The signal ISS-032 replaced the commit count with, and it
            #     needs no git either. A plan that is still only what `start`
            #     wrote is the handover failure; one with a box ticked is not.
            write("ISS-902.md", ONLY_SEEDED, where=work)
            _, out, _ = run(check, plans=True)
            assert cells(out, "ISS-902") == ["ISS-902", "untouched", "0/0 ticked"], out
            assert cells(out, "ISS-901")[1] == "touched", out
            # A file with nothing in it a reader recognises is the seeded case
            # too: absent sections are absent, not touched.
            assert cells(out, "ISS-904")[1] == "untouched", out

            # Prose and no checkpoints is somebody having been here. Ticking is
            # the common way a plan gets kept, not the only one, and a signal
            # that missed this would report a working plan as abandoned.
            write("ISS-902.md", PROSE_ONLY, where=work)
            _, out, _ = run(check, plans=True)
            assert cells(out, "ISS-902") == ["ISS-902", "touched", "0/0 ticked"], out

            # 9. The number the whole issue is about. With a repo, a plan
            #    committed once and never touched again is the handover
            #    failure with a count on it. Without git, none of this is
            #    asserted - the same skip require_commits already makes.
            if git("init", "-q", cwd=tmp) is not None:
                assert git("add", "-A", cwd=tmp) is not None
                assert git("commit", "-qm", "seeded", cwd=tmp) is not None

                _, out, _ = run(check, plans=True)
                assert cells(out, "ISS-901")[1:] == [
                    "touched", "1 commit", "last touched 0 commits ago", "1/3 ticked",
                ], out

                # The two columns saying opposite things about the same file,
                # which is the whole of ISS-032: ISS-902 was edited after it
                # was seeded and then committed once, so its commit count is
                # indistinguishable from an abandoned plan and `untouched` is
                # not. This workflow commits at the end; that is the normal
                # case, not the odd one.
                assert cells(out, "ISS-902")[1:3] == ["touched", "1 commit"], out

                # A commit that is not this plan is what staleness counts.
                write("ISS-905.md", "# ISS-905 Work Plan", where=work)
                git("add", "-A", cwd=tmp)
                git("commit", "-qm", "another", cwd=tmp)
                _, out, _ = run(check, plans=True)
                assert cells(out, "ISS-901")[2:4] == [
                    "1 commit", "last touched 1 commits ago",
                ], out

                # And a plan that is actually being kept: two commits, and the
                # staleness clock back at zero.
                write("ISS-901.md", KEPT, where=work)
                git("add", "-A", cwd=tmp)
                git("commit", "-qm", "ticked one", cwd=tmp)
                _, out, err = run(check, plans=True)
                assert cells(out, "ISS-901")[1:] == [
                    "touched", "2 commits", "last touched 0 commits ago", "2/3 ticked",
                ], out

                # --json is the same report, typed, for whoever counts the
                # five. stdout stays parseable - the only thing on stderr is
                # read_plan saying a shapeless fixture is shapeless, which is
                # a diagnostic and not a row.
                _, out, err = run(check, plans=True, as_json=True)
                assert "ISS-905" in err and "recognise" in err, err
                rows = {row["id"]: row for row in json.loads(out)}
                assert rows["ISS-901"] == {
                    "id": "ISS-901",
                    "untouched": False,
                    "commits": 2,
                    "commits_since": 0,
                    "ticked": 2,
                    "checkpoints": 3,
                }, rows["ISS-901"]
                # The row the threshold is counted from, typed rather than
                # scraped out of a column.
                assert rows["ISS-905"]["untouched"] is True, rows["ISS-905"]

            # 7. The twenty-six real files, which are the ones that matter.
            #    test_storage reads one issue off disk; this reads every one,
            #    and the day a parser change starts eating prose it fails
            #    here rather than in an issue nobody reopens for a month.
            os.environ["ISSUES_DIR"] = os.path.join(REPO, ".issues")
            code, out, err = run(check)
            assert code is None, (code, out, err)

            # And the report over the plans this repo really keeps - the rows
            # the threshold in ISS-031 gets counted from.
            code, out, err = run(check, plans=True)
            assert code is None, (code, out, err)

        finally:
            os.chdir(original)
            os.environ.pop("ISSUES_DIR", None)
    print("ok")
