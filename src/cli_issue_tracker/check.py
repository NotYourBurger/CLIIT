"""Everything wrong with the files, or nothing at all.

`validate.py` is the same contract one step earlier: it refuses a bad command
before the write. This one goes the other way, over files already on disk -
the twenty-six written before a rule existed, and the ones a person edited in
an editor with the tool nowhere near.

The round trip is the reason this module exists. The file format is the API,
and its worst failure does not raise: a parser bug returns a plausible dict,
`write_issue` persists it over the prose, and the first person to notice is
reading a mangled issue weeks later. Nothing else here can lose writing.

`--plans` is the other half, and it is a report rather than a check: whether
each work plan was ever touched after it was seeded, how much of it is ticked,
and - as context now rather than verdict - how many commits it has and how
stale they are. ISS-031 wrote a threshold down before the numbers were known
and pointed it at the commit count; ISS-032 replaced the sensor, because that
count measures the committer. This workflow commits the plan edits at the end,
so every plan on disk read `1 commit` while every one of them had in fact been
edited repeatedly, and a kill switch wired to that would have deleted a feature
that works. The threshold now reads the same rows against `untouched`, and it
lives in docs/PRD/05-Work-Plan.md.

That threshold is a judgement taken once by a person, so nothing here fails on
it. The tool's job is to make the count cost one command instead of nobody ever
taking it, which is exactly how the handover survived twenty-five issues
without anyone noticing it was dead.
"""

import json
import os
import sys

from cli_issue_tracker.events import SUFFIX as EVENTS_SUFFIX
from cli_issue_tracker.events import bad_lines
from cli_issue_tracker.fields import PRIORITIES
from cli_issue_tracker.fields import STATUSES
from cli_issue_tracker.fields import blockers_of
from cli_issue_tracker.plan import WORK
from cli_issue_tracker.plan import git
from cli_issue_tracker.plan import read_plan
from cli_issue_tracker.plan import untouched
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
    a stray note in the directory out of `issue list`.

    newline="" because "compare bytes" was not true before ISS-033: text mode
    collapses "\\r\\n" to "\\n" on the way in, and `join_file` emits "\\n", so a
    CRLF file matched its own rewrite while every line of it was about to
    change. The one module whose docstring says nothing else here can lose
    writing could not see the only line-ending bug this repo has actually
    had."""
    with open(path, "r", encoding="utf-8", newline="") as file:
        raw = file.read()
    split = split_file(path)
    if split is None:
        return raw
    fields, body = split
    return join_file(fields, body, first=FIELD_ORDER)


def plan_history(work, name):
    """(commits that touched this plan, commits to HEAD since the last one).

    (None, None) when git cannot answer, and (0, None) for a plan that exists
    but has never been committed - a real state, since `start` seeds the file
    and the commit comes later. `--follow` so a renamed plan keeps its count
    rather than looking freshly seeded, which is the one number this report is
    for."""
    log = git("log", "--follow", "--format=%H", "--", name, cwd=work)
    if log is None:
        return None, None
    shas = log.split()
    if not shas:
        return 0, None
    since = git("rev-list", "--count", f"{shas[0]}..HEAD", cwd=work)
    return len(shas), int(since.strip()) if since else None


def plan_rows():
    """One dict per plan on disk, in id order.

    Every plan, including one whose issue is gone: the threshold counts plans,
    so the row the findings pass would have thrown away is a row this needs.
    Whether a stale count matters is the reader's call - `issue list` already
    holds the status that answers it."""
    work = work_dir()
    rows = []
    for name in sorted(os.listdir(work)) if os.path.isdir(work) else ():
        if not name.endswith(".md"):
            continue
        id = name[: -len(".md")]
        commits, since = plan_history(work, name)
        # read_plan never raises and treats a missing section as absent, so a
        # file nobody has put a `## Plan` in counts as zero of zero rather
        # than dropping out of the report.
        plan = read_plan(id) or {}
        points = plan.get("checkpoints", [])
        rows.append(
            {
                "id": id,
                # First, because it is the verdict the threshold is read
                # against; the two git numbers below it are context.
                "untouched": untouched(plan),
                "commits": commits,
                "commits_since": since,
                "ticked": sum(1 for point in points if point["done"]),
                "checkpoints": len(points),
            }
        )
    return rows


def plan_cells(row):
    """One row as the cells a human reads. The two git columns are dropped
    rather than filled with a placeholder when git could not answer - a git
    failure costs the block and not the command, the call `git_context`
    already makes. `untouched` is never dropped: it is the verdict, it needs no
    git, and it is the column that stays true in a fresh clone."""
    state = "untouched" if row["untouched"] else "touched"
    ticked = f"{row['ticked']}/{row['checkpoints']} ticked"
    if row["commits"] is None:
        return [row["id"], state, ticked]
    commits = f"{row['commits']} commit{'s' * (row['commits'] != 1)}"
    # A plan with no commit yet is not stale, it is unwritten, and "0 commits
    # ago" would read as the opposite of what it means.
    since = "not committed" if row["commits_since"] is None else (
        f"last touched {row['commits_since']} commits ago"
    )
    return [row["id"], state, commits, since, ticked]


def check_plans(as_json=False):
    """The report. Always exit 0: these are numbers, not findings."""
    rows = plan_rows()
    if as_json:
        print(json.dumps(rows, indent=2))
        return
    if not rows:
        print("No work plans yet", file=sys.stderr)
        return
    table = [plan_cells(row) for row in rows]
    # Same rule as `print_table`: every column as wide as its widest value,
    # the last one unpadded so it cannot push anything off the terminal.
    widths = [max(len(cells[column]) for cells in table) + 2 for column in range(len(table[0]) - 1)]
    for cells in table:
        print(("".join(f"{cell:<{width}}" for cell, width in zip(cells, widths)) + cells[-1]).rstrip())


def check(as_json=False, plans=False):
    """Exit 0 and say nothing, or exit 1 with every finding.

    `--plans` is a different question about a different directory, so it takes
    the whole verb rather than adding rows to the findings: one is what is
    wrong, the other is a count of how the work is going."""
    if plans:
        return check_plans(as_json)

    path = require_issue_dir()

    findings, by_id, file_by_id = [], {}, {}
    for name in sorted(os.listdir(path)):
        if not name.endswith(".md"):
            continue
        file_path = os.path.join(path, name)
        # newline="" on both sides of the comparison or neither: this read is
        # the half `round_trip` is measured against.
        with open(file_path, "r", encoding="utf-8", newline="") as file:
            raw = file.read()
        if round_trip(file_path) != raw:
            findings.append(
                (name, "would not survive a rewrite - `issue set` on it loses or moves text")
            )
        issue = parse_issue(file_path)
        if issue is not None:
            id = issue["id"]
            if id in file_by_id:
                findings.append(
                    (name, f"duplicate id {id} is also used by {file_by_id[id]}")
                )
            else:
                file_by_id[id] = name
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

    # A plan or an event log is named after its issue and has no identity of
    # its own - no id of its own to allocate, no frontmatter - so an id with
    # no file beside it means work is being recorded against nothing.
    # Renaming an issue file by hand is how this happens, and the plan or log
    # is the half that goes quiet.
    work = work_dir()
    for name in sorted(os.listdir(work)) if os.path.isdir(work) else ():
        if name.endswith(".md"):
            if name[: -len(".md")] not in by_id:
                findings.append((os.path.join(WORK, name), "a work plan with no issue beside it"))
        elif name.endswith(EVENTS_SUFFIX):
            id = name[: -len(EVENTS_SUFFIX)]
            if id not in by_id:
                findings.append((os.path.join(WORK, name), "an event log with no issue beside it"))
            for number in bad_lines(os.path.join(work, name)):
                findings.append((os.path.join(WORK, name), f"line {number} is not valid JSON"))

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
