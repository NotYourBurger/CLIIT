"""What a run event is: one append-only fact per issue, and how it is read back.

The work plan records what an agent decided and learned, in its own prose,
mid-thought, edited with the tool it is already holding. A running process -
a probe's stdout, a coordinator's kill hook, a lifecycle note - observes
something different: a fact, true at one instant, produced by whoever
observed it and never revisited afterwards. Mixing the two would put a
machine-appended line in the middle of prose someone is mid-edit on, so this
is a second file next to the plan, not a section inside it.

The agent-behaviour run (docs/agent-behaviour-report.md) is why this exists.
A claim-race probe's stdout, an intentional kill's exact plan snapshot, and a
killed worker's first tool calls all lived only in task output and a
scratchpad, and none of it survived the coordinator's own later cutoff. The
report could not turn those missing measurements into facts and filed
ISS-036 instead. This is `check.py`'s contract again, one layer earlier:
`check.py` finds what already went wrong on disk; this makes sure the fact
was on disk in the first place.
"""

import json
import os
import sys

from cli_issue_tracker.plan import work_dir
from cli_issue_tracker.storage import now
from cli_issue_tracker.storage import read_issue

DEFAULT_TYPE = "note"

# The suffix, not just an extension: `<ID>.md` is the plan, and an issue id
# can itself contain a dot, so `.jsonl` alone would have to be told apart from
# a plan by "the other one", which is fragile the day either name changes.
SUFFIX = ".events.jsonl"


def events_path(id: str) -> str:
    """One log per issue, named after it - the same call `plan_path` already
    makes, so the two live side by side in `work/` and neither needs an id or
    frontmatter of its own."""
    return os.path.join(work_dir(), f"{id}{SUFFIX}")


def append_event(id: str, text: str, type: str = DEFAULT_TYPE) -> dict:
    """Append one entry and return it. The only write in this module, and it
    is always an append: no read, no rewrite, so a process killed mid-write
    can corrupt at most the entry it was writing, never one already on disk."""
    entry = {"at": now(), "type": type, "text": text}
    path = os.path.join(work_dir(create=True), f"{id}{SUFFIX}")
    with open(path, "a", encoding="utf-8", newline="\n") as log_file:
        log_file.write(json.dumps(entry) + "\n")
    return entry


def bad_lines(path: str) -> list:
    """Line numbers (1-indexed) that will not parse as JSON. A blank line is
    not malformed - an append that landed its newline but was killed before
    the JSON was written leaves exactly one, and a log with a trailing blank
    line from that must not read as a lie about every entry before it."""
    found = []
    with open(path, "r", encoding="utf-8") as log_file:
        for number, line in enumerate(log_file, start=1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except ValueError:
                found.append(number)
    return found


def read_events(id: str) -> list:
    """Every entry for one issue, in the order they were written, or `[]` if
    the log does not exist yet - "absent means absent", the same call
    `read_plan` makes about a missing section. A line that will not parse is
    skipped rather than raising: `issue check` is where a malformed line is a
    finding, and every read here would otherwise have to repeat that warning."""
    path = events_path(id)
    if not os.path.isfile(path):
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as log_file:
        for line in log_file:
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
    return entries


def print_events(entries, as_json=False):
    """The log, human or `--json`. `at` is not padded to a fixed width like
    `print_table` would: it is already one fixed-width ISO string, and the
    type column is what varies, so only that one needs the running max."""
    if as_json:
        print(json.dumps(entries, indent=2))
        return
    if not entries:
        print("No events recorded", file=sys.stderr)
        return
    width = max(len(entry.get("type", "")) for entry in entries) + 2
    for entry in entries:
        at = entry.get("at", "")
        type = entry.get("type", "")
        # A snapshot's text is often another file's whole contents; indenting
        # every line after the first keeps one entry visually one entry
        # instead of letting its payload masquerade as the next line's time
        # and type.
        text = str(entry.get("text", "")).replace("\n", "\n" + " " * (len(at) + width + 2))
        print(f"{at}  {type:<{width}}{text}")


def event_command(id: str, text=None, type=DEFAULT_TYPE, as_json=False, use_stdin=False):
    """`issue event`. Append when there is something to append, read back
    otherwise - the read path costs nothing extra to add and the raw file
    stays one `cat` away regardless, the same call the work plan already
    made about needing no dedicated reader."""
    if text is not None and use_stdin:
        print("Pass TEXT or --stdin, not both", file=sys.stderr)
        sys.exit(1)
    if read_issue(id) is None:
        print(f"Issue {id} Was Not Found", file=sys.stderr)
        sys.exit(1)

    if use_stdin:
        text = sys.stdin.read()
    if text is not None:
        append_event(id, text, type)
        return

    print_events(read_events(id), as_json)
