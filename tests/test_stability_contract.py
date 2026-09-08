"""The four things README's Stability section promises an outsider.

Every other check here asks whether a verb does its job. This one asks
whether the surface a stranger pinned this version against is still the same
shape - which is a different question, and green on the first does not answer
it. Twelve files already exercise `--json` and nearly every test asserts an
exit code, but incidentally, on the way somewhere else: each reads the keys it
cares about and none reads the ones it does not, so dropping a key from `view`
passes all of them. Coverage of a surface is not a contract over it. The
contract is the enumeration.

The README constrains this as much as it motivates it. The shapes are stable
in what they contain and *not* in what they omit, so every assertion below is
a subset - a test that failed on an added key would contradict the promise it
is guarding. The other half of that promise is the split between ALWAYS and
SOMETIMES: "every documented key is always present" is the rule for the keys
this tool decides, and "absent means absent" is the rule for fields the file
may never have had. Both are checked, from the fixture that carries each.

Run: uv run python tests/test_stability_contract.py
"""

import json
import os
import shutil
import tempfile

from helpers import FIXTURES, run
from cli_issue_tracker.check import check
from cli_issue_tracker.events import event_command
from cli_issue_tracker.issues import brief
from cli_issue_tracker.issues import claim_issue
from cli_issue_tracker.issues import create_issue
from cli_issue_tracker.issues import list_issues
from cli_issue_tracker.issues import next_issue
from cli_issue_tracker.issues import search_issues
from cli_issue_tracker.issues import set_fields
from cli_issue_tracker.issues import start_issue
from cli_issue_tracker.issues import view_issue
from cli_issue_tracker.storage import read_issue

# Every key on every issue object, whatever the file says. Five are required
# frontmatter, `title` and `body` come out of the body, and the last three are
# derived - `blocked_by` as an array even when the file has no such line, and
# `blocks` and `ready` from facts no file stores. This is the set an agent may
# index without a branch.
ALWAYS = {"id", "status", "created_at", "title", "body", "blocked_by", "blocks", "ready"}

# The other rule, and the reason this is a second set rather than more of the
# first: an issue predating a field has no default invented for it, so these
# are present exactly when the file has them. Enumerated so that dropping one
# from `as_dict` fails here, against the fixture that carries it.
SOMETIMES = {"updated_at", "priority", "labels", "assignee", "resolution", "plan"}

# `brief` is the opposite case: nothing in it comes from a file, so every key
# is unconditional and stays so on a repo with nothing in it.
BRIEF = {
    "summary", "next", "in_progress", "ready", "ready_omitted",
    "blocked", "recently_resolved", "resolved_omitted", "warnings",
}
SUMMARY = {"open", "in_progress", "ready", "blocked", "closed"}

RESOLUTION = {"reason", "closed_at", "message", "evidence"}
PLAN = {"id", "checkpoints", "goal", "decisions", "discoveries", "current", "next"}
EVENT = {"at", "type", "text"}


def parsed(function, *args, **kwargs):
    """Run a read verb with --json and hand back (exit code, parsed stdout).

    Parsing here rather than in each caller is the assertion: stdout is only
    ever that JSON - every diagnostic goes to stderr - and json.loads is what
    says so, which is the half of the promise that makes a pipe into `jq`
    safe."""
    code, out, _ = run(function, *args, as_json=True, **kwargs)
    return code, json.loads(out) if out.strip() else None


def keys_hold(issue, always=ALWAYS):
    """The enumeration, for one issue object.

    A subset and not an equality: new keys may appear, and an issue may carry
    a frontmatter key somebody put there by hand, which the format promises to
    preserve and this promises not to trip over. The types go with the names -
    a `blocks` that turned into a comma-joined string would keep the key and
    break every consumer of it."""
    assert always <= set(issue), (sorted(always - set(issue)), issue.get("id"))
    assert isinstance(issue["blocked_by"], list) and isinstance(issue["blocks"], list), issue
    assert isinstance(issue["ready"], bool), issue
    for key in ("id", "status", "created_at", "title", "body"):
        assert isinstance(issue[key], str), (key, issue)


if __name__ == "__main__":
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        # A writable copy of the frozen corpus. The reads below would be happy
        # with FIXTURES itself, but half of this file is about what a write
        # does - refusing one, preserving a key through one - and a test that
        # edits the corpus changes what every other file here measures
        # (ISS-049).
        issues = os.path.join(tmp, ".issues")
        shutil.copytree(FIXTURES, issues)
        os.environ["ISSUES_DIR"] = issues
        for knob in ("ISSUE_PREFIX", "ISSUE_USER"):
            os.environ.pop(knob, None)
        try:
            # 1. The array commands. `list` is the shape everything else is
            #    built on, so it is enumerated first and the rest are checked
            #    with the same function.
            code, listed = parsed(list_issues)
            assert code is None, code
            assert isinstance(listed, list) and len(listed) == 3, listed
            for issue in listed:
                keys_hold(issue)
            by_id = {issue["id"]: issue for issue in listed}

            # 1b. Absent means absent, and that is a promise in both
            #     directions. ISS-003 predates every optional field, so a
            #     default invented for it would be a break as real as a
            #     dropped key.
            #
            #     Named against SOMETIMES rather than asserted equal to
            #     ALWAYS: an equality here would fail the day a new key is
            #     added, which the README says may happen, and a test that
            #     fails on the thing its own promise allows is a test that
            #     gets deleted rather than read.
            assert not SOMETIMES & set(by_id["ISS-003"]), by_id["ISS-003"]

            # 1c. And every optional key, from the fixture that has it. This
            #     is the assertion that fails when one is dropped from
            #     `as_dict`: SOMETIMES is enumerated here or nowhere.
            live, closed = by_id["ISS-004"], by_id["ISS-005"]
            assert {"updated_at", "priority", "labels", "assignee"} <= set(live), live
            assert isinstance(live["labels"], list) and live["labels"], live
            # An unknown frontmatter key reaches the JSON rather than being
            # filtered out of it: the format preserves what this tool did not
            # write, and a rendering that dropped it would make the file and
            # the API disagree about the same issue.
            assert live["reviewer"] == "someone else", live
            assert "resolution" in closed and RESOLUTION <= set(closed["resolution"]), closed
            assert all(
                {"type", "value"} <= set(item) for item in closed["resolution"]["evidence"]
            ), closed["resolution"]
            # The four flat keys the file stores are gone from the JSON. The
            # raw `evidence` line is JSON inside a string, and leaving both
            # would be one fact in two shapes with nothing keeping them equal.
            assert not RESOLUTION & set(closed), closed
            # A closed issue with no resolution keeps that pair honest: the
            # key is absent, not an empty object.
            assert "resolution" not in by_id["ISS-003"], by_id["ISS-003"]

            # 2. `search` is the `list` array with one key added per issue, so
            #    the same enumeration plus that one.
            code, found = parsed(search_issues, "parser")
            assert code is None and found, (code, found)
            for issue in found:
                keys_hold(issue, ALWAYS | {"matches"})
                assert isinstance(issue["matches"], list) and issue["matches"], issue

            # 3. The object commands. `view` and `next` each print one
            #    `as_dict`, which is the point of them printing the same one.
            code, viewed = parsed(view_issue, "ISS-004")
            assert code is None, code
            keys_hold(viewed)
            code, chosen = parsed(next_issue)
            assert code is None, code
            keys_hold(chosen)

            # 4. `brief`, where every key is unconditional. Empty rather than
            #    missing is the whole difference between this and an issue
            #    object: a consumer branching on whether `warnings` exists is
            #    paying for a fact we already know.
            code, briefed = parsed(brief)
            assert code is None, code
            assert BRIEF <= set(briefed), sorted(BRIEF - set(briefed))
            assert SUMMARY <= set(briefed["summary"]), briefed["summary"]
            assert all(isinstance(count, int) for count in briefed["summary"].values()), briefed
            for key in ("ready_omitted", "resolved_omitted"):
                assert isinstance(briefed[key], int), (key, briefed[key])
            for key in ("in_progress", "ready", "blocked", "recently_resolved", "warnings"):
                assert isinstance(briefed[key], list), (key, briefed[key])
            for key in ("in_progress", "ready", "blocked", "recently_resolved"):
                for issue in briefed[key]:
                    keys_hold(issue)
            keys_hold(briefed["next"])

            # 5. The two array verbs wired straight in cli.py. Both are empty
            #    here, which is the shape that matters: `[]` and exit 0, not
            #    silence.
            code, findings = parsed(check)
            assert code is None and findings == [], (code, findings)
            code, logged = parsed(event_command, "ISS-004")
            assert code is None and logged == [], (code, logged)

            # One entry, so the enumeration is over something. The type is a
            # free label and is deliberately not asserted to be one of a set -
            # the reader tolerating an unknown one is itself the contract.
            run(event_command, "ISS-004", "a probe said something", type="probe")
            code, logged = parsed(event_command, "ISS-004")
            assert code is None and len(logged) == 1, (code, logged)
            assert EVENT <= set(logged[0]), logged[0]
            assert logged[0]["type"] == "probe", logged[0]

            # 6. The `plan` object, on both verbs that carry one. Absent until
            #    there is a plan - asserted above, where there was not - and
            #    then every key present, because this shape is decided by the
            #    tool rather than by what a file happens to hold.
            assert "plan" not in viewed and "plan" not in chosen, (viewed, chosen)
            run(start_issue, "ISS-004", take=True)
            for command, args in ((view_issue, ("ISS-004",)), (next_issue, ())):
                _, dumped = parsed(command, *args)
                assert PLAN <= set(dumped["plan"]), dumped["plan"]
                assert isinstance(dumped["plan"]["checkpoints"], list), dumped["plan"]

            # 7. The exit codes, which a script branches on before it reads a
            #    byte of output. A filter matching nothing is a fact about the
            #    repo and exits 0; a lookup finding nothing failed and exits
            #    1. That is grep's contract, and it is the whole reason
            #    `issue search X || issue create X` works.
            code, empty = parsed(list_issues, priority="low", status="open")
            assert code is None and empty == [], (code, empty)

            for lookup, args in (
                (search_issues, ("zzzz-matches-nothing",)),
                (view_issue, ("ISS-999",)),
            ):
                code, _, err = run(lookup, *args, as_json=True)
                assert code == 1, (lookup, code)
                # Named on stderr, so stdout stays parseable either way.
                assert err, lookup

            # 8. A refused write is 1 with nothing written, and a partly
            #    refused batch is 1 with the good ids written anyway - it does
            #    not roll back, and the exit code is how a caller finds out
            #    that one of them did not land.
            #
            #    A bad --priority and not a bad status word: `set` reads a
            #    trailing word it does not recognise as an id rather than as a
            #    mistyped status, so that path is an unknown id and this one
            #    is the validator.
            code, out, err = run(set_fields, ["ISS-003"], priority="urgent")
            assert code == 1, (code, err)
            assert "priority" not in read_issue("ISS-003"), read_issue("ISS-003")

            code, out, err = run(set_fields, ["ISS-003", "ISS-999"], priority="low")
            assert code == 1, (code, err)
            assert read_issue("ISS-003")["priority"] == "low", "the good id is still written"

            # 9. An unknown frontmatter key survives a rewrite. This is the
            #    forward compatibility the format promises instead of a
            #    `format_version` key, so another tool's field has to come
            #    back off disk after this tool has written the file - not just
            #    out of the parser, which is what test_storage already asks.
            before = read_issue("ISS-004")["reviewer"]
            code, out, err = run(set_fields, ["ISS-004"], priority="low")
            assert code is None, (code, err)
            assert read_issue("ISS-004")["reviewer"] == before, read_issue("ISS-004")

        finally:
            os.chdir(original)
            os.environ.pop("ISSUES_DIR", None)

    # 10. The three environment knobs. ISSUES_DIR is the one under test now
    #     rather than the one holding the test up, so it gets a tree of its
    #     own and a cwd that is nowhere near it.
    with tempfile.TemporaryDirectory() as tmp:
        elsewhere = os.path.join(tmp, "not-the-tracker")
        os.makedirs(elsewhere)
        issues = os.path.join(tmp, "somewhere-else", ".issues")
        os.makedirs(issues)
        os.chdir(elsewhere)
        try:
            # ISSUES_DIR skips the walk-up entirely: nothing in the cwd or
            # above it inside tmp is a .issues/, so the file landing in this
            # one is the knob and not the walk.
            os.environ["ISSUES_DIR"] = issues
            code, out, err = run(create_issue, "Filed from elsewhere", "Body")
            assert code is None, (code, err)
            assert os.path.exists(os.path.join(issues, "ISS-001.md")), os.listdir(issues)

            # ISSUE_PREFIX is read by `create` and by nothing else, so the
            # numbering restarts under the new letters instead of continuing
            # across both.
            os.environ["ISSUE_PREFIX"] = "BUG"
            code, out, err = run(create_issue, "Filed under another prefix", "Body")
            assert code is None, (code, err)
            assert os.path.exists(os.path.join(issues, "BUG-001.md")), os.listdir(issues)
            os.environ.pop("ISSUE_PREFIX")

            # ISSUE_USER is who `claim` acts as when --by is not given, read
            # ahead of `git config user.name` - which is why this asserts the
            # value and not merely that something was written. A machine with
            # a user.name configured would pass a weaker assertion either way.
            os.environ["ISSUE_USER"] = "agent-1"
            code, out, err = run(claim_issue, "ISS-001")
            assert code is None, (code, err)
            assert read_issue("ISS-001")["assignee"] == "agent-1", read_issue("ISS-001")
        finally:
            os.chdir(original)
            for knob in ("ISSUES_DIR", "ISSUE_PREFIX", "ISSUE_USER"):
                os.environ.pop(knob, None)
    print("ok")
