"""What a work plan is: where it lives, what it seeds as, and how it reads back.

The issue is the durable definition of the work and is edited rarely. The plan
is the mutable execution state and is edited constantly, and they must not
become the same thing - an agent whose approach evolves must never be rewriting
the issue description to record that.

This replaces the handover, which assumed a session has an end somebody
notices. It does not: the common ending is a usage limit, a crash, a closed
terminal, and none of them pause to write anything. The evidence was on disk -
this repo shipped `issue handover` and then produced twenty-five issues and
zero handovers. So the record stopped being an ending and became the thing the
work already runs on: written before the first edit, ticked as each checkpoint
lands, and therefore never more than one checkpoint behind the truth.

Which fixes the direction of two decisions the handover made the other way.
Git is recomputed at read time rather than stored, because a stored HEAD in a
live file is a lie the moment anything commits. And nothing here writes a plan
after `start` seeds it: the agent flips `- [ ]` to `- [x]` with the editing
tool it is already holding, because a `plan check 3` round trip mid-flow is a
decision point, which is a place to skip, and "it does not happen" is the whole
bug being fixed. The cost is that nothing enforces the file's shape, so the
reader here is built not to need it.
"""

import os
import sys

from cli_issue_tracker.storage import require_issue_dir
from cli_issue_tracker.storage import run_git
from cli_issue_tracker.storage import split_sections
from cli_issue_tracker.storage import write_atomic

WORK = "work"

# Git names every changed path; a session that touched a generated directory
# would otherwise print hundreds of lines into output whose whole point is that
# it is cheap to read. ponytail: a flat cap, no filtering - if the truncation
# ever hides the file that mattered, sort by something better than git's order.
FILE_CAP = 20

# The nine lines, once. `issue init` numbers them into CLAUDE.md and the seeded
# plan carries lines 5-8 as bullets in its HTML comment - two renderings of one
# constant, because two copies of a rule drift and the drift is invisible until
# an agent follows the stale one.
RULE = (
    "Read the issue and any existing active work plan.",
    "If an unfinished plan exists, continue it instead of creating a new one.",
    "Otherwise create a work plan before modifying code.",
    "Break the work into meaningful checkpoints.",
    "Mark each checkpoint complete immediately after completing it.",
    "Record important discoveries or decisions as they happen.",
    "Keep the Current and Next fields accurate.",
    "Do not wait until the end of the session to record progress.",
    "Close the issue only when the plan and acceptance criteria are complete.",
)

# The headings this reads back, and whether the section is prose or `- `
# bullets. `Plan` is neither and is not here: its bullets are checkboxes and
# get their own reader.
SECTIONS = (
    ("goal", "Goal", False),
    ("decisions", "Decisions", True),
    ("discoveries", "Discoveries", True),
    ("current", "Current", False),
    ("next", "Next", False),
)

# The four that are about the moment of writing rather than the shape of the
# work - the ones a session in the middle of an edit needs in front of it.
REMINDER = RULE[4:8]


def rule_text() -> str:
    """The workflow rule as `issue init` writes it into CLAUDE.md."""
    lines = "\n".join(f"{n}. {line}" for n, line in enumerate(RULE, 1))
    return f"When starting substantial work on an issue:\n\n{lines}"


def work_dir(create=False) -> str:
    """`.issues/work/`. Made on demand rather than by `init`, so a repo that
    never starts anything never grows an empty directory, and a repo made
    before this existed needs no migration."""
    path = os.path.join(require_issue_dir(), WORK)
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def plan_path(id: str) -> str:
    """One plan per issue, named after it. No id allocation and no frontmatter:
    the issue already has both, and the plan is not a second artifact with its
    own identity - it is this issue's execution state.

    No id-shape check, unlike `read_issue`: `issue check` walks work/ and hands
    this back the names it found, and `read_plan` is documented as never
    raising. The shape is checked where a user's argument first becomes a path
    - which every verb that reaches here has already been through."""
    return os.path.join(work_dir(), f"{id}.md")


def seed(id: str, title: str, blockers=()) -> str:
    """The skeleton `start` writes. Empty headings on purpose: this is the one
    place "absent means absent" does not apply, because the file is not being
    read yet - it is being handed to an agent, and a heading it has to remember
    to add is a section it will not write."""
    blocked = f"\nStarted with blockers open: {', '.join(blockers)}.\n" if blockers else ""
    reminder = "\n".join(f"- {line[0].lower() + line[1:].rstrip('.')}" for line in REMINDER)
    return f"""<!--
Keep this current as you work:
{reminder}
-->

# {id} Work Plan
{blocked}
## Goal

{title}

## Plan

## Decisions

## Discoveries

## Current

## Next
"""


def write_plan(id: str, title: str, blockers=()) -> str:
    """Seed one plan. The only write in this module, and it happens once.

    Through `write_atomic` for a reason the issue does not have: a 0-byte plan
    is worse than no plan, because `read_plan` returns one for it and `start`
    will not reseed over a plan that exists, so the checkpoint list is gone
    with nothing that can bring it back."""
    path = os.path.join(work_dir(create=True), f"{id}.md")
    return write_atomic(path, seed(id, title, blockers))


def bullets(text: str) -> list:
    """The `- ` lines of a section, as a list, with wrapped ones rejoined.

    A decision worth recording is a sentence, a sentence wraps, and an editor
    that hard-wraps at eighty columns is the normal case rather than the odd
    one. Taking the first line only would drop the half carrying the reason and
    say nothing about it - the silent loss this reader exists to refuse. So an
    indented line under a bullet belongs to it; a line at the left margin that
    is not a bullet is prose the agent wrote around them and is skipped."""
    found = []
    for line in text.splitlines():
        if line.startswith("- "):
            found.append(line[2:].strip())
        elif found and line[:1].isspace() and line.strip():
            found[-1] += " " + line.strip()
    return found


def checkpoints(text: str) -> list:
    """The `- [ ]` / `- [x]` lines under `## Plan`, in the order they are
    written - that order is the caller's meaning and there is nothing to sort
    them by. A `- ` bullet that is not a checkbox is prose about the plan and
    is skipped rather than counted as an unfinished checkpoint, which would
    make `close` warn about a sentence."""
    found = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) > 4 and line.startswith("- [") and line[4] == "]" and line[3] in " xX":
            found.append({"text": line[5:].strip(), "done": line[3] in "xX"})
    return found


def read_plan(id: str):
    """One issue's plan, or None if it has none. Never raises.

    Nothing enforces this file's shape - the agent edits it with the tool it is
    already holding, and it will reorder sections, add its own and leave one
    out. So every question this asks is "is it here", never "is it valid": a
    heading nobody knows about is ignored and left where it is, and a missing
    one is absent rather than empty or defaulted, the call `priority_of`
    already makes about a field predating itself.

    A file with nothing recognisable in it is still a plan - it is the agent's
    file - so this says so on stderr and returns what it found, rather than
    returning None and having `start` reseed on top of it.

    Including a file that is not UTF-8. This tool writes the seed and an agent
    writes everything after it, so the bytes here are not necessarily ours: a
    truncated write (ISS-038), an editor saving latin-1, a paste through a bad
    terminal. `errors="replace"` because the three answers are crash, mangle
    silently and surface - and the plan is somebody's only copy of where the
    work stands, so the U+FFFD is left in the returned text to be read around
    and the path is named on stderr for whoever can repair it."""
    path = plan_path(id)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as md_file:
        text = md_file.read()
    if "�" in text:
        print(f"{id}: {path} is not valid UTF-8 - re-save it as UTF-8", file=sys.stderr)
    sections = split_sections(text)

    known = ("Plan",) + tuple(heading for _, heading, _ in SECTIONS)
    if not any(heading in sections for heading in known):
        print(f"{id}: the work plan has no section this tool recognises", file=sys.stderr)

    plan = {"id": id, "checkpoints": checkpoints(sections.get("Plan", ""))}
    for key, heading, is_list in SECTIONS:
        text = sections.get(heading, "")
        plan[key] = bullets(text) if is_list else text
    return plan


def untouched(plan) -> bool:
    """Is this plan still only what `seed` wrote?

    The one question worth asking about a plan nobody kept, and it is asked of
    the content rather than of git - so it survives a fresh clone, which has no
    mtime, and a squashed history, which has no count. ISS-031 counted commits
    and its own Discoveries recorded why that cannot answer: a plan edited all
    the way through the work and committed once at the end reads identically to
    one seeded and abandoned, so the sensor measured the committer.

    `goal` is excluded because `seed` fills it in from the issue title - it is
    written by the tool, not by anybody who came back. Everything else `seed`
    leaves empty, so anything at all in any of them is somebody having been
    here. A missing key counts as empty: `read_plan` treats an absent section
    as absent, and a plan with no sections at all is the seeded case."""
    return not plan.get("checkpoints") and not any(
        plan.get(key) for key, _, _ in SECTIONS if key != "goal"
    )


def git(*args, cwd=None):
    """One read-only git call: its stdout, or None if it did not work.

    None is the whole interface. Every caller here treats "no repo" and "git
    said no" as the same absent answer and drops the block that needed it,
    rather than raising into output whose point is that it is cheap to read.

    stdout verbatim, not stripped: `git status --porcelain` puts the
    staged/unstaged pair in the first two columns and " M a.txt" starts with a
    space, so stripping the output eats one character of the first path. The
    callers that want a single line strip it themselves.

    `cwd` because the repo is wherever `.issues/` was found, which is not
    necessarily where the command was typed.

    The call itself is `storage.run_git`, which is also what the callers that
    need the return code rather than the stdout use - one place knows that a
    missing binary is an absent answer and not an exception (ISS-043)."""
    done = run_git(*args, cwd=cwd)
    return done.stdout if done.returncode == 0 else None


def git_context():
    """(git dict, files) as they are right now, or (None, []) with no repo.

    Read every time it is shown and never stored. The handover stored it
    because a handover was immutable and a stored fact could not go stale; a
    plan is live, so a stored HEAD would be a lie the moment anything
    committed, and recomputing is now the right answer rather than the wrong
    one. Read-only, and a git failure costs the git block rather than the
    output - the same call `require_commits` makes about closing without a
    repo."""
    head = git("rev-parse", "--short", "HEAD")
    if head is None:
        return None, []
    head = head.strip()

    status = git("status", "--porcelain") or ""
    files = []
    for line in status.splitlines():
        # `R  old -> new` names two paths and the new one is where the work is.
        path = line[3:].partition(" -> ")[2] or line[3:]
        # `files` is comma-joined like every other id field, so a path with a
        # comma in it cannot be stored. Dropping the path beats corrupting the
        # list - this is navigation, and git itself still knows.
        if path and "," not in path:
            files.append(path)

    return (
        {"branch": (git("rev-parse", "--abbrev-ref", "HEAD") or "").strip(), "head": head,
         "dirty": bool(status.strip())},
        files[:FILE_CAP],
    )
