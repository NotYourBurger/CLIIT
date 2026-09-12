"""Checks for `issue close`.

Closing is the one status change that has to answer a question, so the branches
worth checking are the ones that refuse: no reason, two reasons, no message, a
`completed` with nothing behind it, and a duplicate pointing at itself or at
nothing. Every one of them must leave the file exactly as it was - a half
applied close is a file that says the work is done and cannot say why.

The rest is the round trip: a JSON array in flat frontmatter has to come back
out typed, through `view` and through `--json`, and the issues closed before any
of this existed have to keep rendering untouched.

Run: uv run python tests/test_close.py
"""

import json
import os
import tempfile

from helpers import REPO, run
from cli_issue_tracker.issues import (
    close_issue,
    create_issue,
    list_issues,
    set_fields,
    view_issue,
)
from cli_issue_tracker.storage import parse_issue, run_git, write_issue


def read(tmp, id):
    return parse_issue(os.path.join(tmp, f"{id}.md"))


def head_sha():
    """A commit that really is in this repository, for the one piece of
    evidence the tool validates. Empty outside a repo, which is exactly the
    case require_commits skips - so the check below skips with it.

    Through run_git rather than subprocess, for the reason run_git exists: a
    machine with no git raised here instead of answering "" and took the whole
    file down with it (ISS-047)."""
    git = run_git("rev-parse", "--short", "HEAD", cwd=REPO)
    return git.stdout.strip() if not git.returncode else ""


from helpers import legacy_create
create_issue = legacy_create


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        try:
            for n in range(1, 9):
                run(create_issue, f"Issue {n}", "...", "medium")

            sha = head_sha()

            # Nothing is written until every rule has passed: no reason, two of
            # them, no message, a blank one, completed with nothing behind it,
            # a commit that is not in the repo, and blank evidence.
            before = read(tmp, "ISS-001")
            refusals = [
                {"message": "x"},
                {"completed": True, "not_planned": True, "message": "x", "prs": ["u"]},
                {"completed": True, "verified": ["v"]},
                {"completed": True, "message": "   ", "verified": ["v"]},
                {"completed": True, "message": "x"},
                {"completed": True, "message": "x", "verified": ["  "]},
            ]
            if sha:
                refusals.append({"completed": True, "message": "x", "commits": ["deadbee"]})
            for kwargs in refusals:
                code, _, err = run(close_issue, "ISS-001", **kwargs)
                assert code == 1, (code, kwargs)
                assert err.strip(), "a refusal has to say why"
            assert read(tmp, "ISS-001") == before, "a refused close must write nothing"

            # The message names the accepted evidence: "needs evidence" without
            # the list is the error you have to go and read the source over.
            _, _, err = run(close_issue, "ISS-001", completed=True, message="Done")
            assert "--commit, --test, --pr, or --verified" in err, err

            # completed, with one of each kind of evidence.
            code, said, _ = run(
                close_issue,
                "ISS-001",
                completed=True,
                message="Wrote it, ran the checks.",
                commits=[sha] if sha else [],
                tests=["uv run python tests/all.py, twice"],
                prs=["https://example.invalid/pr/7"],
                verified=["clicked through it"],
            )
            assert code is None, (code, said)
            assert "ISS-001 is closed - completed" in said, said
            closed = read(tmp, "ISS-001")
            assert closed["status"] == "closed"
            assert closed["reason"] == "completed"
            assert closed["closed_at"] == closed["updated_at"], "one close, one clock"
            assert closed["message"] == "Wrote it, ran the checks."

            # The whole reason evidence is a JSON array and not a comma-joined
            # field: a value with a comma in it survives.
            evidence = json.loads(closed["evidence"])
            assert {"type": "test", "value": "uv run python tests/all.py, twice"} in evidence
            kinds = [item["type"] for item in evidence]
            assert kinds == (["commit"] if sha else []) + ["test", "pr", "verified"], evidence

            # --verified satisfies the evidence rule with a sentence no
            # machine can check, so the close says so - on stderr, and without
            # refusing, the same answer this command already gives an unticked
            # checkpoint. stdout is byte for byte what it was.
            code, said, err = run(
                close_issue,
                "ISS-007",
                completed=True,
                message="Read it through.",
                verified=["looks fine"],
            )
            assert code is None, (code, err)
            assert said.strip() == "ISS-007 is closed - completed", said
            assert "--verified" in err and "ISS-007" in err, err

            # One checkable item alongside it and there is nothing to warn
            # about: the loophole is evidence that is *only* verified.
            code, said, err = run(
                close_issue,
                "ISS-008",
                completed=True,
                message="Ran the suite.",
                tests=["uv run python tests/all.py"],
                verified=["looks fine"],
            )
            assert code is None, (code, err)
            assert "--verified" not in err, err

            # The three reasons that cost a word and a sentence. None of them
            # carries evidence, and none of them may pick up the warning.
            _, _, err = run(
                close_issue, "ISS-002", not_planned=True, message="Conflicts with search."
            )
            assert "--verified" not in err, err
            assert read(tmp, "ISS-002")["reason"] == "not-planned"
            assert "evidence" not in read(tmp, "ISS-002"), "no evidence, no field"

            run(close_issue, "ISS-003", duplicate_of="ISS-001", message="Same bug.")
            assert read(tmp, "ISS-003")["reason"] == "duplicate", "the flag carries the reason"
            assert json.loads(read(tmp, "ISS-003")["evidence"]) == [
                {"type": "duplicate-of", "value": "ISS-001"}
            ]

            run(close_issue, "ISS-004", superseded_by="ISS-001", message="Replaced.")
            assert read(tmp, "ISS-004")["reason"] == "superseded"
            assert json.loads(read(tmp, "ISS-004")["evidence"]) == [
                {"type": "superseded-by", "value": "ISS-001"}
            ]

            # The two checks --blocked-by already makes, for the same reason.
            was = read(tmp, "ISS-005")
            for kwargs in (
                {"duplicate_of": "ISS-005"},
                {"superseded_by": "ISS-005"},
                {"duplicate_of": "ISS-404"},
                {"superseded_by": "ISS-404"},
            ):
                code, _, _ = run(close_issue, "ISS-005", message="x", **kwargs)
                assert code == 1, (code, kwargs)
            assert read(tmp, "ISS-005") == was
            assert run(close_issue, "ISS-404", not_planned=True, message="x")[0] == 1

            # --json hands back one resolution object, not the four flat keys
            # the file stores - nothing downstream should have to parse the
            # evidence line for itself.
            _, out, _ = run(view_issue, "ISS-001", as_json=True)
            dumped = json.loads(out)
            assert set(dumped["resolution"]) == {"reason", "closed_at", "message", "evidence"}
            assert dumped["resolution"]["evidence"][-1]["type"] == "verified"
            assert not {"reason", "closed_at", "message", "evidence"} & set(dumped)

            # And `view` renders the same model, typed, under the table and
            # above the body.
            _, out, _ = run(view_issue, "ISS-001")
            assert "Resolution" in out and "Evidence" in out, out
            assert "Reason:     completed" in out, out
            assert "PR:         https://example.invalid/pr/7" in out, out
            assert out.index("Resolution") < out.index("Issue 1"), "resolution above the body"

            # Closing is the only thing that frees a blocked issue, and it says
            # so on the same run.
            run(set_fields, ["ISS-006"], None, (), (), ["ISS-005"])
            _, said, _ = run(close_issue, "ISS-005", not_planned=True, message="Dropping it.")
            assert "ISS-006 is now ready" in said, said

            # Reopening drops the resolution it no longer has. The previous
            # one is in git, which is where this project keeps history, and a
            # second close writes a fresh resolution rather than reviving it.
            run(set_fields, ["ISS-001", "open"])
            reopened = read(tmp, "ISS-001")
            assert reopened["status"] == "open"
            assert not {"reason", "closed_at", "message", "evidence"} & set(reopened)
            _, out, _ = run(view_issue, "ISS-001")
            assert "Resolution" not in out, out
            _, out, _ = run(view_issue, "ISS-001", as_json=True)
            assert "resolution" not in json.loads(out)
            run(close_issue, "ISS-001", not_planned=True, message="Actually, no.")
            again = read(tmp, "ISS-001")
            assert again["reason"] == "not-planned"
            assert again["message"] == "Actually, no."
            assert "evidence" not in again, "a new reason must not keep the old proof"

            # The second door is shut: `set` refuses the word and names the
            # command that takes a resolution, before writing anything.
            was = read(tmp, "ISS-006")
            code, _, err = run(set_fields, ["ISS-006", "closed"])
            assert code == 1, code
            assert "issue close ISS-006" in err, err
            assert read(tmp, "ISS-006") == was
            # A batch is refused whole, not up to the first id.
            assert run(set_fields, ["ISS-006", "ISS-002", "closed"], "low")[0] == 1
            assert read(tmp, "ISS-006") == was
            # The other two statuses still go through.
            assert run(set_fields, ["ISS-006", "in-progress"])[0] is None

            # An issue closed before any of this existed: no resolution keys,
            # nothing rewritten, and both renderings still work.
            old = read(tmp, "ISS-006")
            old["status"] = "closed"
            write_issue(old)
            assert "reason" not in read(tmp, "ISS-006")
            code, out, _ = run(view_issue, "ISS-006")
            assert code is None and "Resolution" not in out, out
            _, out, _ = run(view_issue, "ISS-006", as_json=True)
            assert "resolution" not in json.loads(out)
            assert run(list_issues, "closed")[0] is None
            run(set_fields, ["ISS-006", "open"])
            legacy = read(tmp, "ISS-006")
            assert legacy["status"] == "open"
            assert not {"reason", "closed_at", "message", "evidence"} & set(legacy)

            # A hand-edited evidence line that is not JSON is ignored, loudly,
            # rather than taking `view` down or being written back wrong.
            broken = read(tmp, "ISS-003")
            broken["evidence"] = "the commit, I think"
            write_issue(broken)
            code, out, err = run(view_issue, "ISS-003")
            assert code is None, code
            assert "not readable JSON" in err, err
            assert "Resolution" in out and "Evidence" not in out, out

            print("ok")
        finally:
            os.environ.pop("ISSUES_DIR", None)


if __name__ == "__main__":
    demo()
