"""Checks for `issue handover`.

Two things here can lose writing silently. The body parser is one: a handover
is `## Heading` sections and `- ` bullets, and a bug there does not raise - it
drops a decision and hands the next session a shorter file that looks complete.
`test_storage.py` guards the issue body with a deliberately nasty one; this does
the same for the handover body and for the same reason.

The other is the split the whole feature rests on: a handover is a checkpoint,
not a small issue. It must not move the status, must not claim, and a session
blocker must never become a `blocked_by` edge - `in_the_way` stays the only
thing that decides what blocked means.

Run: uv run python tests/test_handover.py
"""

import json
import os
import tempfile

from helpers import run
from cli_issue_tracker.handover import create_handover
from cli_issue_tracker.handover import latest_command
from cli_issue_tracker.handover import list_handovers
from cli_issue_tracker.handover import load_handovers
from cli_issue_tracker.handover import parse_handover
from cli_issue_tracker.handover import view_handover
from cli_issue_tracker.handover import write_handover
from cli_issue_tracker.issues import create_issue
from cli_issue_tracker.storage import read_issue

# Every construct that can end a section early or eat a bullet: a `## ` inside a
# bullet (only a line that starts with one is a heading), a heading's own name
# used as prose, a bare `---` that must not read as the end of the frontmatter,
# a comma in a value that no comma-joined field could have held, and non-ASCII.
NASTY = {
    "summary": "A summary with a --- rule in it,\nand a second line.",
    "done": [
        "Wrote the ## Summary section, then the rest",
        "Handled a café, a naïve résumé and a ▌ half block",
    ],
    "remaining": ["- a bullet that starts with a dash"],
    "decisions": ["Chose the boring one: no JSON arrays of prose"],
    "discoveries": ["`---` in a body is a horizontal rule"],
    "blockers": ["no Windows box"],
    "resume_at": "src/issues.py:set_issue",
    "next": "Next: run the suite,\nthen close it.",
}


def sections(handover):
    """Everything the file has to carry back, the git block aside - that one is
    read from the world rather than from the caller."""
    return {key: handover[key] for key in NASTY}


def demo():
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        issues = os.path.join(tmp, ".issues")
        os.makedirs(issues)
        os.environ["ISSUES_DIR"] = issues
        # Out of any repo, so `git status` has nothing to say about this
        # directory and the checks below do not depend on what the real one
        # looks like while they run.
        os.chdir(tmp)
        try:
            run(create_issue, "First", "body")
            run(create_issue, "Second", "body")

            # 1. Required, and blank is not given. Both before anything is
            #    written, so a rejected create does not burn an H- id.
            code, _, err = run(create_handover, ["ISS-001"], "   ", "next")
            assert code == 1 and "summary" in err, err
            code, _, err = run(create_handover, ["ISS-001"], "summary", "  \n ")
            assert code == 1 and "next" in err, err
            code, _, err = run(create_handover, ["ISS-404"], "summary", "next")
            assert code == 1 and "ISS-404" in err, err
            assert not os.path.isdir(os.path.join(issues, "handovers")) or not os.listdir(
                os.path.join(issues, "handovers")
            ), "a rejected create wrote a handover"

            # A `## ` line would come back as a section of its own, so it is
            # refused rather than silently split in two.
            code, _, err = run(create_handover, ["ISS-001"], "ok\n## Done\nnot ok", "next")
            assert code == 1 and "##" in err, err
            code, _, err = run(create_handover, ["ISS-001"], "ok", "next", done=["two\nlines"])
            assert code == 1 and "one line" in err, err

            # 2. The nasty body round trips. Written through the command and
            #    read back off disk, because the two halves of the format are
            #    only inverses if the whole path is.
            code, out, err = run(
                create_handover,
                ["ISS-001", "ISS-002", "ISS-001"],
                NASTY["summary"],
                NASTY["next"],
                done=NASTY["done"],
                remaining=NASTY["remaining"],
                decisions=NASTY["decisions"],
                discoveries=NASTY["discoveries"],
                blockers=NASTY["blockers"],
                resume_at=NASTY["resume_at"],
            )
            assert code is None, err
            assert "H-001" in out, out

            path = os.path.join(issues, "handovers", "H-001.md")
            got = parse_handover(path)
            assert sections(got) == NASTY, sections(got)
            # A repeated id is one reference, and the order the caller gave is
            # kept - the first id is the primary issue.
            assert got["issues"] == ["ISS-001", "ISS-002"], got["issues"]

            # Written back out, the file is byte-identical: the writer and the
            # reader are inverses, not merely close.
            with open(path, encoding="utf-8") as file:
                before = file.read()
            write_handover(got)
            with open(path, encoding="utf-8") as file:
                assert file.read() == before, "a rewrite changed the file"

            # 3. Discoverable from every issue it names, and stored once.
            assert [h["id"] for h in load_handovers("ISS-001")] == ["H-001"]
            assert [h["id"] for h in load_handovers("ISS-002")] == ["H-001"]
            assert len(os.listdir(os.path.join(issues, "handovers"))) == 1

            # 4. Nothing about the issue moved. A session blocker is prose
            #    about why this session stopped; blocked_by is the dependency
            #    graph, and the first must never write the second.
            issue = read_issue("ISS-001")
            assert issue["status"] == "open", issue["status"]
            assert "blocked_by" not in issue, "a session blocker became a dependency"
            assert "assignee" not in issue, "creating a handover claimed the issue"

            # 5. latest is a sort, not whatever listdir returned. Three files
            #    sharing a timestamp still order down to the id, so two calls
            #    in a row cannot name different checkpoints.
            for id in ("H-007", "H-002", "H-004"):
                write_handover(
                    {
                        "id": id,
                        "created_at": "2026-09-08T03:18:00+06:00",
                        "issues": ["ISS-001"],
                        "summary": f"checkpoint {id}",
                        "next": "keep going",
                    }
                )
            assert [h["id"] for h in load_handovers("ISS-001")] == [
                "H-001",
                "H-002",
                "H-004",
                "H-007",
            ], "handovers are not ordered by (created_at, id)"

            code, out, err = run(latest_command, "ISS-001")
            assert code is None and out.splitlines()[0] == "Handover H-007", out

            # Oldest first, one line each: the newest checkpoint is the one a
            # resuming session wants, so it is the line left at the prompt.
            # The header still opens its block.
            code, out, err = run(list_handovers, "ISS-001")
            assert code is None, err
            assert [line.split()[0] for line in out.splitlines()[1:]] == [
                "H-001",
                "H-002",
                "H-004",
                "H-007",
            ], out

            # --json keeps newest first - a parser has no cursor.
            code, out, err = run(list_handovers, "ISS-001", as_json=True)
            assert [h["id"] for h in json.loads(out)] == [
                "H-007",
                "H-004",
                "H-002",
                "H-001",
            ], out

            # NEXT is the last line printed, even with a git block and files.
            # Those are the state the checkpoint describes, so they read as
            # context above it; printed after NEXT they left the cursor on a
            # list of file paths instead of the one line to act on.
            write_handover(
                {
                    "id": "H-009",
                    "created_at": "2026-09-08T04:00:00+06:00",
                    "issues": ["ISS-009"],
                    "summary": "checkpoint with git",
                    "next": "run the suite",
                    "git": {"branch": "main", "head": "abc1234", "dirty": True},
                    "files": ["src/cli_issue_tracker/render.py"],
                }
            )
            code, out, err = run(latest_command, "ISS-009")
            assert code is None, err
            assert out.splitlines()[-2:] == ["NEXT", "run the suite"], out
            assert "GIT" in out and "FILES" in out, out

            # 6. A lookup that finds nothing is exit 1 - grep's contract, the
            #    one `next` and `view` already keep.
            code, out, err = run(latest_command, "ISS-002")
            assert code is None, "ISS-002 was named by H-001"
            code, out, err = run(latest_command, "ISS-404")
            assert code == 1 and out == "", (code, out)
            code, out, err = run(list_handovers, "ISS-404")
            assert code == 1 and out == "", (code, out)
            code, out, err = run(view_handover, "H-099")
            assert code == 1 and out == "", (code, out)

            # 7. --json: every optional list present and empty, and no
            #    terminal formatting anywhere in it.
            code, out, err = run(view_handover, "H-002", as_json=True)
            assert code is None, err
            dumped = json.loads(out)
            assert dumped == {
                "id": "H-002",
                "created_at": "2026-09-08T03:18:00+06:00",
                "issues": ["ISS-001"],
                "summary": "checkpoint H-002",
                "done": [],
                "remaining": [],
                "decisions": [],
                "discoveries": [],
                "blockers": [],
                "resume_at": "",
                "next": "keep going",
                "git": None,
                "files": [],
            }, dumped

            # The full one keeps its lists as lists rather than as the prose
            # the file stores them as.
            code, out, _ = run(view_handover, "H-001", as_json=True)
            full = json.loads(out)
            assert full["done"] == NASTY["done"], full["done"]
            assert full["issues"] == ["ISS-001", "ISS-002"]

            # 8. A hand-edited file still reads: this format promises manual
            #    editing stays possible, so headings in another order, an
            #    unknown section and a missing one are all fine.
            hand = os.path.join(issues, "handovers", "H-010.md")
            with open(hand, "w", encoding="utf-8") as file:
                file.write(
                    "---\n"
                    "id: H-010\n"
                    "created_at: 2026-09-07T09:00:00+06:00\n"
                    "issues: ISS-001\n"
                    "---\n\n"
                    "# Session Handover\n\n"
                    "A note above the sections.\n\n"
                    "## Next\n\nfinish it\n\n"
                    "## Something Else\n\nignored\n\n"
                    "## Summary\n\nwritten by hand\n"
                )
            hand_read = parse_handover(hand)
            assert hand_read["summary"] == "written by hand"
            assert hand_read["next"] == "finish it"
            assert hand_read["done"] == [] and hand_read["git"] is None

        finally:
            os.chdir(original)
            os.environ.pop("ISSUES_DIR", None)
    print("ok")


if __name__ == "__main__":
    demo()
