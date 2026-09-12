"""Compact output must save repeated context without destroying the record.

Long active work, rather than completed plans alone, exercises both the pending
cap and prose truncation. Real CLI calls cover the flags and rejection before
--claim writes; function calls keep stream assertions consistent with the suite.
"""

import json
import os
import subprocess
import sys
import tempfile

from helpers import run
from cli_issue_tracker.issues import create_issue, next_issue, set_fields, start_issue
from cli_issue_tracker.plan import plan_path
from cli_issue_tracker.render import compact_plan_lines


def contents(path):
    with open(path, "rb") as file:
        return file.read()


def cli(*args):
    return subprocess.run(
        [sys.executable, "-c", "from cli_issue_tracker.cli import app; app()", *args],
        capture_output=True, text=True, encoding="utf-8",
    )


from helpers import legacy_create
create_issue = legacy_create


def demo():
    previous = {key: os.environ.get(key) for key in ("ISSUES_DIR", "ISSUE_USER", "ISSUE_PREFIX")}
    with tempfile.TemporaryDirectory() as tmp:
        os.environ.update(ISSUES_DIR=tmp, ISSUE_USER="compact-tester", ISSUE_PREFIX="ISS")
        try:
            run(create_issue, "Resume work", "Description stays available.")
            code, out, err = run(next_issue, compact=True)
            assert code is None and "Resume work" in out and "PLAN" not in out, (code, out, err)
            result = cli("start", "ISS-001", "--compact")
            assert result.returncode == 0 and "plan at" in result.stdout, result.stderr
            path = plan_path("ISS-001")
            seeded = contents(path)
            result = cli("start", "ISS-001", "--compact")
            assert result.returncode == 0 and "PLAN  0/0" in result.stdout, result.stderr
            assert contents(path) == seeded

            long_text = "Keep the Unicode rationale café available. " * 50
            body = (
                "# ISS-001 Work Plan\n\n## Plan\n\n- [x] Read the code\n"
                + "".join(f"- [ ] Task {n}: {long_text}\n" for n in range(5))
                + f"\n## Decisions\n\n- {long_text}\n\n## Discoveries\n\n- {long_text}\n"
                + f"\n## Current\n\nImplementing the change.\n{long_text}\n"
                + f"\n## Next\n\nVerify the interrupted work.\n{long_text}\n"
            )
            with open(path, "w", encoding="utf-8", newline="\n") as file:
                file.write(body)
            before = contents(path)
            issue_path = os.path.join(tmp, "ISS-001.md")
            issue_before = contents(issue_path)
            code, out, err = run(next_issue, compact=True)
            assert code is None and not err, (code, out, err)
            assert "PLAN  1/6" in out and out.count("- [ ]") == 3, out
            assert "+2 more pending checkpoints" in out, out
            assert "Current: Implementing the change." in out, out
            assert "Next: Verify the interrupted work." in out, out
            assert "1 decisions, 1 discoveries" in out and "Full plan:" in out, out
            assert "..." in out and "GIT\n" not in out, out
            assert len(out) < 1200, len(out)
            assert contents(path) == before and contents(issue_path) == issue_before

            code, full, err = run(start_issue, "ISS-001")
            assert code is None and long_text.strip() in full, (code, err)
            assert full.count("- [ ]") == 5 and "DECISIONS" in full, full
            code, raw, err = run(next_issue, as_json=True)
            dumped = json.loads(raw)
            assert len(dumped["plan"]["checkpoints"]) == 6
            assert dumped["plan"]["decisions"] == [long_text.strip()]
            assert contents(path) == before

            for args in (("start", "ISS-001", "--compact"), ("next", "--compact")):
                result = cli(*args)
                assert result.returncode == 0 and "PLAN  1/6" in result.stdout, result.stderr
                assert result.stdout.count("- [ ]") == 3
                assert contents(path) == before

            # A claim would now change ownership even within the same timestamp
            # second, so byte equality proves the rejected flags did not claim.
            run(set_fields, ["ISS-001"], assignee="")
            issue_before = contents(issue_path)
            result = cli("next", "--compact", "--json", "--claim")
            assert result.returncode == 1 and not result.stdout, result
            assert "cannot be combined" in result.stderr, result.stderr
            assert contents(issue_path) == issue_before and contents(path) == before
            assert compact_plan_lines({}) == ["PLAN  0/0"]
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    print("ok")


if __name__ == "__main__":
    demo()
