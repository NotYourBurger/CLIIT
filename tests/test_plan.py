"""Checks for `issue start` and the work plan.

The plan is the one artifact the CLI writes once and then never touches again,
so the two things that can go wrong sit at the ends. Seeding can write the
wrong file, and reading can lose what an agent has since put in it - both
silently: a plan whose `## Current` was dropped by the reader looks exactly
like a plan whose work has not started, and the resuming agent believes it.

So this checks the seed, the idempotence that makes `start` also the resume
path, the blocked refusal, and a reader pointed at a deliberately mangled plan.

Run: uv run python tests/test_plan.py
"""

import json
import os
import tempfile

from helpers import run
from cli_issue_tracker.issues import close_issue
from cli_issue_tracker.issues import create_issue
from cli_issue_tracker.issues import next_issue
from cli_issue_tracker.issues import set_fields
from cli_issue_tracker.issues import start_issue
from cli_issue_tracker.issues import view_issue
from cli_issue_tracker.init import init
from cli_issue_tracker.plan import plan_path
from cli_issue_tracker.plan import read_plan
from cli_issue_tracker.storage import read_issue

HEADINGS = ("## Goal", "## Plan", "## Decisions", "## Discoveries", "## Current", "## Next")

# A plan a session has been working in: two checkpoints, one of them ticked,
# and prose in the two fields that say where it stands.
UNDER_WAY = """# ISS-001 Work Plan

## Goal

Login and signup

## Plan

- [x] Read the auth code
- [ ] Wire the provider

## Decisions

- Auth state lives in AuthProvider
- Session persistence uses the existing backend mechanism, because the
  alternative was a second store to keep in sync

## Current

Connecting login to AuthProvider.

## Next

Wire the login result in, then handle the failure branch.
"""


# What an agent leaves behind: its own heading, a line that looks like a
# checkbox and is not, and a section it wrote prose into instead of bullets.
MANGLED = """# ISS-002 Work Plan

## Goal

Still readable

## Plan

Some prose about the approach.
- [~] Not a checkbox
- [ ] A real one

## Approach

An unknown section the tool has no opinion about.
"""


def read(path):
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def write(path, text, newline="\n"):
    with open(path, "w", encoding="utf-8", newline=newline) as file:
        file.write(text)


def raw_bytes(path):
    with open(path, "rb") as file:
        return file.read()


def rule_reaches_the_agent():
    """`issue init` writes the workflow rule where the agent will read it.

    Two renderings, one constant: the numbered rule in the project file and the
    condensed reminder in every seeded plan. The rule at the top of CLAUDE.md is
    the first thing a long session compacts away, which is why the plan file
    carries its own copy - and why they must not be two constants that drift."""
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            write(os.path.join(tmp, "CLAUDE.md"), "# House rules\n\nExisting prose.\n")
            run(init)
            written = read(os.path.join(tmp, "CLAUDE.md"))
            assert "Existing prose." in written, "init overwrote the file it appended to"
            assert "Do not wait until the end of the session" in written, written

            # Twice is once: init is the command you run again after pulling a
            # repo, and a rule appended on every run is a file nobody reads.
            run(init)
            assert read(os.path.join(tmp, "CLAUDE.md")) == written, "init wrote the rule twice"

            # The rule is a procedure with no way to invoke it: nine lines
            # that never say the tracker is `.issues/` and name not one verb.
            # It reads fine in this repo only because two hundred hand-written
            # lines above it explain the tool - the one case the feature does
            # not ship for.
            for verb in ("issue next", "issue start", "issue check", "issue close"):
                assert verb in written, (verb, written)

            # The second block goes on through the same idempotent loop, so
            # twice is still once for it too.
            assert written.count("issue next") == 1, written

            # AGENTS.md too when it is the file this repo keeps.
            write(os.path.join(tmp, "AGENTS.md"), "# Agents\n")
            run(init)
            agents = read(os.path.join(tmp, "AGENTS.md"))
            assert "Do not wait until the end" in agents, agents
            assert "issue start" in agents, agents
        finally:
            os.chdir(original)


def a_repo_with_neither_file():
    """The half of `init` that only happens in a repo that is not this one.

    Nothing is created without an explicit request. With --agents, AGENTS.md
    is the shared source and CLAUDE.md imports it, matching the two tools'
    documented discovery filenames without copying the workflow body."""
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            code, out, err = run(init)
            # Not a failure. The tracker itself installed fine, and this is the
            # half the user is allowed to not want.
            assert code is None, (code, out, err)
            assert os.path.isdir(os.path.join(tmp, ".issues")), out
            assert not os.path.isfile(os.path.join(tmp, "AGENTS.md")), "init invented a file"
            assert not os.path.isfile(os.path.join(tmp, "CLAUDE.md")), "init invented a file"
            assert "AGENTS.md" in err and "--agents" in err, err

            # Asked out loud, it writes the vendor-neutral source and the
            # documented Claude import. The workflow itself still has one copy.
            code, out, err = run(init, agents=True)
            assert code is None, (code, out, err)
            written = read(os.path.join(tmp, "AGENTS.md"))
            assert "Do not wait until the end of the session" in written, written
            assert "issue start" in written, written
            # A file this tool brought into being does not open on a blank line.
            assert written.startswith("## Work plans"), written
            assert read(os.path.join(tmp, "CLAUDE.md")) == "@AGENTS.md\n"

            # Re-running is byte-idempotent for both discovery files.
            run(init, agents=True)
            assert read(os.path.join(tmp, "AGENTS.md")) == written
            assert read(os.path.join(tmp, "CLAUDE.md")) == "@AGENTS.md\n"
        finally:
            os.chdir(original)


def a_repo_with_claude_only():
    """--agents adds Codex discovery without copying existing instructions."""
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            write(os.path.join(tmp, "CLAUDE.md"), "# Existing instructions\n")
            run(init, agents=True)
            claude = read(os.path.join(tmp, "CLAUDE.md"))
            agents = read(os.path.join(tmp, "AGENTS.md"))
            assert "Existing instructions" in claude
            assert "issue next" in claude
            assert "CLAUDE.md" in agents
            assert "issue next" not in agents, "the shared workflow was copied"
        finally:
            os.chdir(original)


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        os.environ["ISSUE_USER"] = "tester"
        try:
            run(create_issue, "Login and signup", "...", "high")

            # Seeding: the status moves, the issue is claimed, and the plan
            # file appears with every heading a reader knows about.
            code, out, err = run(start_issue, "ISS-001")
            assert code is None, (code, out, err)
            issue = read_issue("ISS-001")
            assert issue["status"] == "in-progress", issue
            assert issue["assignee"] == "tester", issue

            path = plan_path("ISS-001")
            assert os.path.isfile(path), path
            seeded = read(path)
            for heading in HEADINGS:
                assert heading in seeded, (heading, seeded)
            # The goal is the issue's title, so the plan says what it is about
            # without the reader opening a second file.
            assert "Login and signup" in seeded, seeded
            # Line 8 of the workflow rule is the behavioural guarantee the
            # whole feature rests on, and CLAUDE.md is the first thing a long
            # session compacts away. It has to be in the file being edited.
            assert "end of the session" in seeded, seeded

            # The seed goes out LF on a machine whose text mode would have made
            # it CRLF. The plan is the one file the CLI hands straight to an
            # agent to edit with its own tool, so a CRLF seed is a whole-file
            # diff on the first edit - and worse, an edit that matches on
            # nothing and silently does not land.
            assert b"\r" not in raw_bytes(path), "the seeded plan is CRLF"

            # The other direction: a plan hand-edited on Windows arrives CRLF
            # and every section still reads back, with no CR left in the prose.
            # ISS-031's own plan records what this costs - "the edit that was
            # supposed to fill it in had silently failed on CRLF line endings."
            write(path, UNDER_WAY.replace("\n", "\r\n"), newline="")
            assert b"\r\n" in raw_bytes(path), "the fixture is not actually CRLF"
            crlf = read_plan("ISS-001")
            assert crlf["checkpoints"] == [
                {"text": "Read the auth code", "done": True},
                {"text": "Wire the provider", "done": False},
            ], crlf
            assert crlf["current"] == "Connecting login to AuthProvider.", crlf
            assert crlf["decisions"][0] == "Auth state lives in AuthProvider", crlf

            # Resuming: the same command, on work that already has a plan. The
            # file an agent has been editing is never reseeded - it is the only
            # copy of everything the last session worked out.
            write(path, UNDER_WAY)
            code, out, err = run(start_issue, "ISS-001")
            assert code is None, (code, out, err)
            assert read(path) == UNDER_WAY, "start reseeded a plan that already existed"

            # And it says where the work stands rather than only that it
            # started - a resuming agent that has to `cat` the file has been
            # handed a second step, which is a place to skip.
            assert "1/2" in out, out
            assert "- [ ] Wire the provider" in out, out
            assert "- [x] Read the auth code" not in out, "a done checkpoint is noise on resume"
            assert "Connecting login to AuthProvider." in out, out

            # The reader sees the same thing the printer did.
            plan = read_plan("ISS-001")
            assert plan["checkpoints"] == [
                {"text": "Read the auth code", "done": True},
                {"text": "Wire the provider", "done": False},
            ], plan
            assert plan["current"] == "Connecting login to AuthProvider.", plan
            assert plan["goal"] == "Login and signup", plan
            # A bullet that wrapped is one bullet. Taking only the first line
            # would drop the half of the sentence carrying the reason, and
            # nothing would say so - the silent loss this reader exists to
            # refuse.
            assert plan["decisions"] == [
                "Auth state lives in AuthProvider",
                "Session persistence uses the existing backend mechanism, because the "
                "alternative was a second store to keep in sync",
            ], plan
            # Absent means absent: nothing was written under Discoveries, so
            # nothing is invented for it.
            assert plan["discoveries"] == [], plan
            assert read_plan("ISS-404") is None, "no plan at all is None, not an empty one"

            # Blocked work is discouraged, not forbidden. The refusal names the
            # blockers and writes nothing at all - a start that half-happened
            # would leave an in-progress issue with no plan, which is the state
            # the whole feature exists to make impossible.
            run(create_issue, "Wire the provider", "...", "medium")
            run(create_issue, "Ship the schema", "...", "medium")
            run(set_fields, ["ISS-002"], None, (), (), ["ISS-003"])
            code, out, err = run(start_issue, "ISS-002")
            assert code == 1 and out == "", (code, out, err)
            assert "ISS-003" in err, err
            assert not os.path.isfile(plan_path("ISS-002")), "a refused start wrote a plan"
            assert read_issue("ISS-002")["status"] == "open", "a refused start moved the status"

            # --anyway is the judgement call, and the plan records that it was
            # made: the next reader sees an issue started with a blocker open
            # without having to work out why.
            code, out, err = run(start_issue, "ISS-002", anyway=True)
            assert code is None, (code, out, err)
            assert "ISS-003" in read(plan_path("ISS-002")), read(plan_path("ISS-002"))
            assert read_issue("ISS-002")["status"] == "in-progress"

            # The reader is pointed at a file an agent has mangled: a heading
            # nobody knows, a checkbox-looking line that is not one, prose
            # under Plan. Nothing raises, the unknown section is left alone,
            # and only real checkpoints are counted.
            write(plan_path("ISS-002"), MANGLED)
            plan = read_plan("ISS-002")
            assert plan["checkpoints"] == [{"text": "A real one", "done": False}], plan
            assert plan["current"] == "", "a section that is not there is not empty prose"
            assert plan["goal"] == "Still readable", plan

            # A file with nothing recognisable in it is still the agent's file:
            # a note on stderr, not a failure, and never a reseed on top of it.
            write(plan_path("ISS-002"), "# ISS-002\n\nJust prose, no headings.\n")
            code, out, err = run(read_plan, "ISS-002")
            assert code is None and "recognise" in err, (code, err)
            code, out, err = run(start_issue, "ISS-002", anyway=True)
            assert "Just prose" in read(plan_path("ISS-002")), "start reseeded an unreadable plan"

            # "Keep working" is one command: `next` already names the right
            # issue, and now it says what was happening there. Read-only still
            # - asking the question must not answer it.
            write(plan_path("ISS-001"), UNDER_WAY)
            before = read(plan_path("ISS-001"))
            code, out, err = run(next_issue)
            assert code is None, (code, out, err)
            assert out.splitlines()[0].startswith("ISS-001"), out
            assert "PLAN  1/2" in out, out
            assert "- [ ] Wire the provider" in out, out
            assert "Connecting login to AuthProvider." in out, out
            assert "Auth state lives in AuthProvider" in out, out
            # The title is already the first line of this output; a GOAL block
            # under it would say the same thing twice.
            assert "GOAL" not in out, out
            # ISS-025's rule: the last line printed is the one you came for,
            # and on a resume that is what to do next - not the file paths.
            assert out.strip().endswith("Wire the login result in, then handle the failure branch."), out
            assert read(plan_path("ISS-001")) == before, "next wrote to the plan"

            # --json exposes the plan structurally, so an agent reading it does
            # not parse the block a human reads.
            code, out, err = run(next_issue, as_json=True)
            chosen = json.loads(out)
            assert chosen["id"] == "ISS-001", chosen
            assert chosen["plan"]["checkpoints"][1] == {
                "text": "Wire the provider",
                "done": False,
            }, chosen
            assert chosen["plan"]["current"] == "Connecting login to AuthProvider.", chosen

            # `view` is for an issue you are not working on, so it shows where
            # the work stands without starting it: a pointer, not the plan.
            code, out, err = run(view_issue, "ISS-001")
            assert code is None, (code, out, err)
            assert "Work plan: 1/2 checkpoints" in out, out
            assert "Connecting login to AuthProvider." in out, out
            assert "Wire the login result in" in out, out
            # Not the whole file: the checkpoints and the decisions are one
            # `cat` away, and inlining them is what `start` is for.
            assert "- [ ] Wire the provider" not in out, out
            assert "Auth state lives in AuthProvider" not in out, out

            # Nothing at all when there is no plan - an empty block would read
            # as work that has started and produced nothing.
            run(create_issue, "Untouched", "...", "low")
            code, out, err = run(view_issue, "ISS-004")
            assert code is None and "Work plan" not in out, (code, out)

            # --json wherever the plan is shown, so an agent reads the
            # structure rather than the block a human reads.
            code, out, err = run(view_issue, "ISS-001", as_json=True)
            assert json.loads(out)["plan"]["checkpoints"][0]["done"] is True, out
            code, out, err = run(view_issue, "ISS-004", as_json=True)
            assert "plan" not in json.loads(out), out

            # `start` is a claim, and a claim is the one ownership verb that can
            # fail. Someone else's issue is refused by name rather than quietly
            # reassigned: an agent starting a mistyped id must not take alice's
            # work off her, silently, in a command whose subject is a plan file.
            run(set_fields, ["ISS-004"], assignee="alice")
            code, out, err = run(start_issue, "ISS-004")
            assert code == 1 and out == "", (code, out, err)
            assert "alice" in err, err
            assert read_issue("ISS-004")["status"] == "open", "a refused start moved the status"
            assert not os.path.isfile(plan_path("ISS-004")), "a refused start wrote a plan"

            # --take is that same decision made out loud, and it says whose work
            # it took - the line the refusal would have printed, after the fact.
            code, out, err = run(start_issue, "ISS-004", take=True)
            assert code is None, (code, out, err)
            assert "alice" in out, out
            assert read_issue("ISS-004")["assignee"] == "tester", read_issue("ISS-004")

            # Closing with checkpoints still open warns and closes anyway. A
            # checkpoint that stopped being relevant must not be able to veto a
            # close, and the acceptance criteria already own completeness - so
            # the divergence is made visible, not enforced.
            code, out, err = run(
                close_issue, "ISS-001", completed=True, message="done",
                verified=["checked by hand"],
            )
            assert code is None, (code, out, err)
            assert read_issue("ISS-001")["status"] == "closed"
            assert "Wire the provider" in err, err
            # stdout stays parseable: the warning is a note to a human.
            assert "Wire the provider" not in out, out
            # And the plan stays where it is - it is the account of how the
            # issue was actually built, which is worth more after the close
            # than during it.
            assert os.path.isfile(plan_path("ISS-001")), "close moved the plan"

            # close -> start -> inspect, the mirror of close -> reopen ->
            # inspect in test_close.py. Finished work is refused first:
            # reopening is a real transition and not something a nearby id
            # should be able to do on the way to writing a plan file.
            code, out, err = run(start_issue, "ISS-001")
            assert code == 1 and out == "", (code, out, err)
            assert "closed" in err, err
            assert read_issue("ISS-001")["status"] == "closed"

            # And when it is asked for, it reopens cleanly. `start` writes the
            # status through the same function `set` does, so the four fields
            # ISS-034 taught that function to drop go with it - rather than the
            # exact file ISS-034 was filed to make impossible: an in-progress
            # issue carrying proof that it was completed.
            code, out, err = run(start_issue, "ISS-001", take=True)
            assert code is None, (code, out, err)
            restarted = read_issue("ISS-001")
            assert restarted["status"] == "in-progress", restarted
            assert not {"reason", "closed_at", "message", "evidence"} & set(restarted), restarted
            code, out, err = run(view_issue, "ISS-001")
            assert "Resolution" not in out, out
        finally:
            os.environ.pop("ISSUES_DIR", None)
            os.environ.pop("ISSUE_USER", None)
    rule_reaches_the_agent()
    a_repo_with_neither_file()
    a_repo_with_claude_only()
    print("ok")


if __name__ == "__main__":
    demo()
