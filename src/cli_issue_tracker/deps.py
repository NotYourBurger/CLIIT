"""What blocks what.

`in_the_way` is the only function that decides whether an issue is stuck, and
`is_ready` (open and unblocked) and `actionable` (not closed and unblocked) are
both it plus a status test. A tracker with two opinions about blocked
recommends work it also refuses to list, so a third one does not get to grow
here - if a new rule needs writing, it goes inside `in_the_way`.

Edges are stored on the blocked issue only, as `blocked_by`. `blocks` is
derived by reading the others, because one fact stored twice is two copies to
disagree the first time someone hand-edits a file.
"""

from cli_issue_tracker.fields import STATUSES
from cli_issue_tracker.fields import blockers_of


def blocker_status(id, by_id):
    """A blocker's status, or "missing" for an id whose file is gone. The only
    thing about a blocker that matters, so an id is never printed without it."""
    return by_id[id]["status"] if id in by_id else "missing"


def said_blockers(ids, by_id):
    """`ISS-009 (open), ISS-004 (closed)`."""
    return ", ".join(f"{id} ({blocker_status(id, by_id)})" for id in ids)


def in_the_way(issue, by_id):
    """The blockers actually stopping this issue: known, and not closed.

    Direct blockers only, not transitive. If A waits on B and B waits on C, and
    someone closed B with C still open, then B is done because a person said
    so, and B's blockers stopped being A's problem at that moment.

    A missing id never blocks: it can never be closed, so counting it would
    strand the issue forever with no way out but a hand edit. It still prints
    as `(missing)`, which is louder than a wrong "blocked" and points at the
    repair."""
    return [id for id in blockers_of(issue) if id in by_id and by_id[id]["status"] != "closed"]


def is_ready(issue, by_id):
    """Open, with every blocker closed - the standup question, the "what do I
    pick up" question, and the one an agent asks before it does anything."""
    return issue["status"] == "open" and not in_the_way(issue, by_id)


def actionable(issue, by_id):
    """Something you could start right now: a status we know, not closed, and
    nothing in the way.

    `is_ready` is this plus "open", which is right for the filter it was
    written for and wrong here - a ready in-progress issue is the first thing
    `next` should return. Both are `in_the_way` plus a status test, and
    `in_the_way` stays the only thing that decides what blocks work: two
    functions with their own idea of blocked is how a tracker starts
    recommending work it also refuses to list.

    A status nobody wrote - a hand-typed word in a file - is not actionable
    rather than a crash in next_rank, which has no position to sort it into.
    `next` recommends the statuses it knows about."""
    status = issue["status"]
    return status in STATUSES and status != "closed" and not in_the_way(issue, by_id)


def blocks(id, by_id):
    """The other side of the edge, derived by reading the others - which `list`
    and `search` already do on every run."""
    return sorted(other for other, issue in by_id.items() if id in blockers_of(issue))


def blocked_note(issue, by_id):
    """The line under a row, for every blocker that is not closed. Same
    mechanism `search` uses to say why a row matched, which is why this adds no
    column: two columns with no bound on their width cannot both be last.

    It prints on plain `list` too, not only under `--blocked`. A blocked row
    that looks identical to a ready one is the precise failure this exists to
    fix; `--ready` is the filter that takes them away."""
    stuck = [id for id in blockers_of(issue) if blocker_status(id, by_id) != "closed"]
    return [f"blocked by {said_blockers(stuck, by_id)}"] if stuck else []


def cycle_from(start, graph, path=None):
    """The blocked_by path from `start` back to itself, or None.

    Depth-first, and the path is the visited set, so what comes back is the
    route to print rather than a bare yes. ponytail: re-walks shared tails,
    which costs nothing at a few dozen issues - it wants a colour marking north
    of a few thousand, the same ceiling the directory scan already has."""
    path = path or [start]
    for next_id in graph.get(path[-1], ()):
        if next_id == start:
            return path + [start]
        if next_id in path:
            continue
        found = cycle_from(start, graph, path + [next_id])
        if found:
            return found
    return None
