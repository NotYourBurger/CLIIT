"""Everything wrong with the files, or nothing at all.

`validate.py` is the same contract one step earlier: it refuses a bad command
before the write. This one goes the other way, over files already on disk -
the twenty-six written before a rule existed, and the ones a person edited in
an editor with the tool nowhere near.

The round trip is the reason this module exists. The file format is the API,
and its worst failure does not raise: a parser bug returns a plausible dict,
`write_issue` persists it over the prose, and the first person to notice is
reading a mangled issue weeks later. Nothing else here can lose writing.
"""

import json
import os
import sys

from cli_issue_tracker.fields import PRIORITIES
from cli_issue_tracker.fields import STATUSES
from cli_issue_tracker.fields import blockers_of
from cli_issue_tracker.plan import WORK
from cli_issue_tracker.plan import work_dir
from cli_issue_tracker.storage import FIELD_ORDER
from cli_issue_tracker.storage import join_file
from cli_issue_tracker.storage import parse_issue
from cli_issue_tracker.storage import require_issue_dir
from cli_issue_tracker.storage import split_file


def round_trip(path):
    """The file as this tool would write it back.

    Read the text, split it, join it, compare bytes - the same two functions
    every write already goes through, in the same order, so what this proves
    is exactly what a rewrite would do rather than a model of it. A file with
    no frontmatter is not ours and can never be a finding - it comes back
    unchanged - because `parse_issue` already skips those, which is what keeps
    a stray note in the directory out of `issue list`."""
    with open(path, "r", encoding="utf-8") as file:
        raw = file.read()
    split = split_file(path)
    if split is None:
        return raw
    fields, body = split
    return join_file(fields, body, first=FIELD_ORDER)


def check(as_json=False):
    """Exit 0 and say nothing, or exit 1 with every finding."""
    path = require_issue_dir()

    findings, by_id = [], {}
    for name in sorted(os.listdir(path)):
        if not name.endswith(".md"):
            continue
        file_path = os.path.join(path, name)
        with open(file_path, "r", encoding="utf-8") as file:
            raw = file.read()
        if round_trip(file_path) != raw:
            findings.append(
                (name, "would not survive a rewrite - `issue set` on it loses or moves text")
            )
        issue = parse_issue(file_path)
        if issue is not None:
            by_id[issue["id"]] = issue

    # One pass per issue, so everything wrong with one file prints together.
    #
    # A word outside the tuples, in the two fields that have one:
    # `require_status` rejects it at the door, and a file edited in an editor
    # never went past the door. What it costs is silence - `actionable` drops
    # an unknown status rather than raising, so the issue is simply gone from
    # `next`, and an unknown priority matches no --priority filter. Absent is
    # not checked for anywhere: "absent means absent" is the rule, and only a
    # value that is there and wrong is a finding.
    #
    # A blocker that is not here is the same shape of silence. `in_the_way`
    # refuses to let a missing id block anything - it could never be closed,
    # so counting it would strand the issue forever - which is right, and is
    # also why nothing has ever had a reason to say the hole is there. `brief`
    # prints it as a warning; this puts an exit code on it.
    for id, issue in sorted(by_id.items()):
        for field, known in (("status", STATUSES), ("priority", PRIORITIES)):
            value = issue.get(field)
            if value is not None and value not in known:
                findings.append((f"{id}.md", f"{field} is {value!r} - use: {', '.join(known)}"))
        missing = [blocker for blocker in blockers_of(issue) if blocker not in by_id]
        if missing:
            findings.append(
                (f"{id}.md", f"blocked_by names {', '.join(missing)}, which is not here")
            )

    # A plan is named after its issue and has no identity of its own - no id
    # of its own to allocate, no frontmatter - so an id with no file beside it
    # means work is being recorded against nothing. Renaming an issue file by
    # hand is how this happens, and the plan is the half that goes quiet.
    work = work_dir()
    for name in sorted(os.listdir(work)) if os.path.isdir(work) else ():
        if name.endswith(".md") and name[: -len(".md")] not in by_id:
            findings.append((os.path.join(WORK, name), "a work plan with no issue beside it"))

    if as_json:
        # Always the list, empty included: a script branching on whether the
        # key is there learns worse than nothing, and the exit code is what it
        # reads first anyway.
        findings_json = [{"file": name, "problem": problem} for name, problem in findings]
        print(json.dumps(findings_json, indent=2))
    else:
        for name, problem in findings:
            print(f"{name}: {problem}", file=sys.stderr)
    if findings:
        sys.exit(1)
