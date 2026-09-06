import json
import os
import subprocess
import sys


from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table


from rich.theme import Theme

from cli_issue_tracker.convert_id import next_id
from cli_issue_tracker.storage import require_issue_dir
from cli_issue_tracker.storage import now
from cli_issue_tracker.storage import parse_issue
from cli_issue_tracker.storage import read_issue
from cli_issue_tracker.storage import write_issue

THEME = Theme(
    {
        "markdown.h1": "bold bright_white",
        "markdown.h2": "bold bright_cyan",
        "markdown.h3": "bold cyan",
        "markdown.h4": "bold",
        "markdown.item.bullet": "bold cyan",
    }
)

console = Console(theme=THEME)

def create_issue(title: str, description: str, priority: str = "medium", labels=()):

    # Before the id is allocated: a rejected create must not burn a number.
    require_priority(priority)
    labels = clean_labels(labels)
    path = require_issue_dir()
    issue = {
        "id": next_id(path),
        "created_at": now(),
        "status": "open",
        "priority": priority,
        # No labels means no field, not an empty one - the same rule the issues
        # that predate priority live by.
        **({"labels": ", ".join(labels)} if labels else {}),
        "body": f"# {title}\n\n{description}",
    }
    write_issue(issue)
    print(f"Issue {issue['id']} has been created")


STATUSES = ("in-progress", "open", "closed") ## Ordering
STATUS_ORDER = STATUSES[::-1]  # least urgent first: closed, open, in-progress


PRIORITIES = ("high", "medium", "low")
PRIORITY_ORDER = ("-",) + PRIORITIES[::-1]  # no priority, then low, medium, high


def priority_of(issue):
    """What to show and filter on. Missing stays missing - the issues written
    before this field existed never had a priority, and calling those "medium"
    would invent a decision nobody made."""
    return issue.get("priority", "-")


def assignee_of(issue):
    """Who owns it, or "-" for nobody. Same shape as priority_of, for the same
    reason: the reader is scanning a column and an empty cell reads as a
    rendering bug."""
    return issue.get("assignee", "-")


def current_user():
    """Who `claim` acts as when --by is not given: $ISSUE_USER, then
    `git config user.name`, then nothing.

    The name is a string this tool does not verify and cannot: an issue is a
    file in a git repo, anyone who can write the file can write any name into
    it. The audit trail already exists and is better - `issue log` says who
    committed the change. The environment variable is the knob this tool
    already has twice over, and it is what an agent sets once at the top of a
    run rather than threading a name through every call."""
    who = os.environ.get("ISSUE_USER", "").strip()
    if who:
        return who
    git = subprocess.run(
        ["git", "config", "user.name"], capture_output=True, text=True, encoding="utf-8"
    )
    return git.stdout.strip()


def set_field(issue, field):
    """A comma-joined frontmatter field as a list. Flat frontmatter has no list
    type, so the file holds one string and this is the only place that knows
    it. Absent, empty and blank all read back as nothing."""
    return [word.strip() for word in issue.get(field, "").split(",") if word.strip()]


def labels_of(issue):
    """The labels field as a list."""
    return set_field(issue, "labels")


def blockers_of(issue):
    """The blocked_by field as a list of ids - the second comma-joined set
    field, stored on the issue that is stuck. One side of the edge only; the
    other direction is derived, because one fact stored twice is two copies to
    disagree the first time someone hand-edits a file."""
    return set_field(issue, "blocked_by")


def clean_set(words, kind, clean=lambda word: word):
    """User words in, storable values out: stripped, deduped and sorted, each
    one through `clean`. Sorted because the file is read by humans and diffed
    by git, and an insertion-ordered list reorders itself for no reason.

    A comma is the delimiter, so no value can contain one - that is the whole
    shared validation. What a value may be beyond that differs per field, which
    is why the per-value check is a parameter rather than hard-coded in the
    middle: a label is invented, an id has to exist."""
    values = set()
    for word in words:
        value = clean(word.strip())
        if not value:
            print(f"A {kind} cannot be empty", file=sys.stderr)
            sys.exit(1)
        if "," in value:
            print(
                f"A {kind} cannot contain a comma - {word!r} is the separator "
                f"between two, so pass them as two flags",
                file=sys.stderr,
            )
            sys.exit(1)
        values.add(value)
    return sorted(values)


def clean_labels(words):
    """Lowercased, because a label is a word and not an identity. Unlike status
    and priority there is no list to check against: inventing the words is the
    point of labels."""
    return clean_set(words, "label", str.lower)


def clean_ids(words):
    """Ids keep their case - the prefix is configurable, so there is no
    normalisation that is right for every repo. Whether the id exists is
    checked where the issues are in hand, not here."""
    return clean_set(words, "issue id")


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


def require_blockers(ids, block, unblock, by_id):
    """Pass, or exit 1 saying why - before anything is written. An unknown id,
    a self-link or a cycle is a failed command, not a half-applied one.

    Existence is required of --blocked-by and not of --unblock: a blocker whose
    file was deleted is exactly the one you need to be able to remove."""
    for id in block:
        if id not in by_id:
            print(f"Issue {id} Was Not Found", file=sys.stderr)
            sys.exit(1)
    for id in ids:
        if id in block:
            print(f"{id} cannot block itself", file=sys.stderr)
            sys.exit(1)

    # The graph as it would be after the write: a cycle is cheapest to catch
    # here, while it is still one edge away from valid. Left in, neither issue
    # is ever ready and nothing ever says why - `--ready` just quietly returns
    # one row short forever.
    graph = {id: blockers_of(issue) for id, issue in by_id.items()}
    for id in ids:
        if id in graph:
            graph[id] = sorted((set(graph[id]) | set(block)) - set(unblock))
    for id in ids:
        path = cycle_from(id, graph)
        if path:
            # The path, not "cycle detected": it says which edge to drop
            # instead of sending you off to read four files.
            print(f"{id} would wait on itself: {' -> '.join(path)}", file=sys.stderr)
            sys.exit(1)


def rank(issue):
    """Sort key: least urgent first, so the list reads bottom-up. A terminal
    leaves the last line printed right above the prompt, which is where the eye
    already is - putting closed issues there and making you scroll for the
    in-progress one had it backwards.

    Both orders are the existing tuples reversed, so there is still one place
    that says what order statuses and priorities come in. Anything we never
    wrote - an unknown status, a hand-typed priority - sorts to the very top,
    which is the low-attention end.

    Ties keep id order, and the sort is stable, so the newest issue of a group
    is the one nearest the prompt."""
    status = issue["status"]
    priority = priority_of(issue)
    return (
        STATUS_ORDER.index(status) if status in STATUS_ORDER else -1,
        PRIORITY_ORDER.index(priority) if priority in PRIORITY_ORDER else -1,
    )


def next_rank(issue):
    """Sort key for `next`: most urgent first, the other end of `rank`.

    Status first, because unfinished work you already started is work you are
    about to abandon, and abandoning it is what this ordering exists to
    prevent. Then priority, then the oldest, then the id.

    That tail is not decoration. Two issues filed in the same second with the
    same priority have to come out in the same order on every call, or an agent
    asking twice is told to do two different things and finishes neither. It is
    also why the id is in here rather than left to the order the directory
    happened to list.

    Both orders are STATUSES and PRIORITIES read forwards, which is the pair
    `rank` reads backwards - there is still one place saying what urgent means.
    An unset priority sorts last here and first there, which is the same end of
    the same list."""
    priority = priority_of(issue)
    return (
        STATUSES.index(issue["status"]),
        PRIORITIES.index(priority) if priority in PRIORITIES else len(PRIORITIES),
        issue["created_at"],
        issue["id"],
    )


def describe(fields):
    """`{"status": "closed", "priority": "high"}` as "closed, priority high" -
    status reads as itself, the others need the word to make sense. Labels are
    bracketed because their value has commas in it and the fields are joined
    with commas too."""
    said = []
    for field, value in fields.items():
        if field == "status":
            said.append(value)
        elif field == "labels":
            said.append(f"labels [{value}]" if value else "no labels")
        elif field == "blocked_by":
            said.append(f"blocked by [{value}]" if value else "not blocked")
        elif field == "assignee":
            # Possessive, not "assigned to X" - "set to assigned to X" reads
            # badly, and this is the wording `claim` already prints.
            said.append(f"{value}'s" if value else "unassigned")
        else:
            said.append(f"{field} {value}")
    return ", ".join(said)


def require_status(status):
    """Pass, or exit 1 saying why. Shared by list (filtering) and set (writing)
    so there is one list and one message, not two that drift apart. Same
    contract as require_issue_dir - a word we cannot act on is a failed
    command, not a quiet one."""
    if status not in STATUSES:
        print(f"Unknown status {status!r} - use: {', '.join(STATUSES)}", file=sys.stderr)
        sys.exit(1)


def require_priority(priority):
    """The same contract as require_status, for the other three-word list. Two
    near-identical validators beat one parameterised one for lists this short -
    fold them together when there is a third."""
    if priority not in PRIORITIES:
        print(f"Unknown priority {priority!r} - use: {', '.join(PRIORITIES)}", file=sys.stderr)
        sys.exit(1)


# name, value, and what "nothing here" looks like. A column with a blank is
# conditional - it disappears when every row in the result is blank, so a repo
# that does not use the field does not pay a column for it. None means always.
COLUMNS = (
    ("ID", lambda issue: issue["id"], None),
    ("TITLE", lambda issue: issue["title"], None),
    ("STATUS", lambda issue: issue["status"], None),
    ("PRIORITY", priority_of, None),
    ("CREATED AT", lambda issue: issue["created_at"], None),
    ("ASSIGNEE", assignee_of, "-"),
    ("LABELS", lambda issue: ", ".join(labels_of(issue)), ""),
)


def print_table(issues, notes=None):
    """The list, as aligned columns. Each column is as wide as its widest
    value, so nothing is truncated; the last one is not padded, so a long
    value there cannot push anything off the terminal. That is why LABELS is
    last - it is the column with no bound on its width, and a repo that does
    not use labels does not get an empty column at all."""
    columns = [
        (name, value)
        for name, value, blank in COLUMNS
        if blank is None or any(value(issue) != blank for issue in issues)
    ]
    widths = [
        max(len(name), *(len(value(issue)) for issue in issues)) + 2 for name, value in columns
    ]

    def row(cells):
        # The last cell is printed as-is: padding it would only add trailing
        # spaces, and it is the one column allowed to run long.
        padded = [f"{cell:<{width}}" for cell, width in zip(cells[:-1], widths)]
        # rstrip: an issue with no labels would otherwise end in the padding of
        # the column before it.
        return ("".join(padded) + cells[-1]).rstrip()

    print(row([name for name, _ in columns]))

    rule = "-" * (sum(widths[:-1]) + max(len(columns[-1][1](issue)) for issue in issues))
    previous = None
    for issue in issues:
        # Not on the first row: previous is None only before anything is printed.
        if previous is not None and issue["status"] != previous:
            print(rule)
        print(row([value(issue) for _, value in columns]))
        # Indented under the row rather than in a column: these lines have no
        # bound on their length and there can be several of them, which is the
        # one shape a table cannot hold.
        for line in (notes or {}).get(issue["id"], ()):
            print(f"    {line}")
        previous = issue["status"]


def load_issues():
    """Every issue on disk, parsed, in id order."""
    path = require_issue_dir()
    issues = []
    for filename in sorted(os.listdir(path)):
        # No prefix test: parse_issue already returns None for anything
        # without our frontmatter, so it is the one thing deciding what is an
        # issue. Dropping the check is what lets a renamed prefix keep listing
        # the issues filed under the old one.
        if not filename.endswith(".md"):
            continue
        issue = parse_issue(os.path.join(path, filename))
        if issue is not None:
            issues.append(issue)
    return issues


def select_issues(
    status=None,
    priority=None,
    labels=(),
    words=(),
    ready=False,
    blocked=False,
    assignee=None,
    unassigned=False,
):
    """The issues passing every filter given, in list order, and every issue by
    id. One function because `list` and `search` narrow by the same fields plus
    a query, and two copies of that filtering drift the first time a new field
    is added. Each filter is None or empty for "don't care", so the no-filter
    call is just every issue.

    The map comes back with them because a blocker's status is a fact about a
    file the filter may have thrown away - `--ready`, the blocked line under a
    row and the JSON's `blocks` all need issues that are not in the result.

    Validation lives here too - "issue list opne" should say so before touching
    the disk, not print an empty table and look like there is nothing to do.
    None is the no-filter case, which is legitimate, so it skips the check."""
    if status is not None:
        require_status(status)
    if priority is not None:
        require_priority(priority)
    if assignee is not None and unassigned:
        # No repo state satisfies both, so an empty table would blame the repo
        # for the caller's mistake.
        print(
            "--assignee and --unassigned contradict - one asks for a name, the "
            "other for no name",
            file=sys.stderr,
        )
        sys.exit(1)
    labels = clean_labels(labels)

    everything = load_issues()
    by_id = {issue["id"]: issue for issue in everything}
    issues = []
    for issue in everything:
        if status is not None and issue["status"] != status:
            continue
        # Issues filed before the field existed match no filter - which is the
        # point of not defaulting them to medium.
        if priority is not None and priority_of(issue) != priority:
            continue
        # Every label given, not any of them: repeating a filter flag narrows,
        # the way adding --priority to a status does.
        if labels and not set(labels) <= set(labels_of(issue)):
            continue
        # Ownership is one name, so both filters are decidable from the issue
        # in hand - unlike --ready and --blocked below.
        if assignee is not None and issue.get("assignee") != assignee:
            continue
        if unassigned and issue.get("assignee"):
            continue
        if words and not matches(issue, words):
            continue
        # The two filters that cannot be decided from a single issue: they need
        # every blocker's status, so they run with the whole map in hand rather
        # than inside the loop over one file.
        if ready and not is_ready(issue, by_id):
            continue
        if blocked and not in_the_way(issue, by_id):
            continue
        issues.append(issue)

    # Stable sort, and the list is already in id order, so ids stay ordered
    # inside each group.
    issues.sort(key=rank)
    return issues, by_id


def matches(issue, words):
    """Every word, case-insensitively, as a substring, anywhere in the issue.
    All of them, so more words narrow rather than widen: "verification email"
    finds "verification of the email", which a phrase search would not, and
    getting nothing back for a query whose words are all in the file is the
    failure people give up on a search box over.

    Substring, not word-boundary, so `auth` finds `authentication` and `oauth` -
    the behaviour of every editor's find, which is where the expectation comes
    from. The body is the whole file below the frontmatter, title heading
    included, so searching it searches the title too."""
    text = issue["body"].lower()
    return all(word in text for word in words)


def matching_lines(issue, words):
    """Why this row is here: the body lines carrying a query word, minus the
    title heading, because the TITLE column already prints that one. Any word
    rather than all of them - the words of a match are often on different
    lines, and the point is to show where each one came from."""
    lines = []
    for line in issue["body"].splitlines():
        if line.startswith("# ") and line[2:].strip() == issue["title"]:
            continue
        if any(word in line.lower() for word in words):
            lines.append(line.strip())
    return lines


def narrowing(priority, status, labels, ready=False, blocked=False, assignee=None, unassigned=False):
    """The filters as the words the user typed, for the nothing-found line."""
    words = (priority, status, *clean_labels(labels),
             "ready" if ready else "", "blocked" if blocked else "",
             "unassigned" if unassigned else "", f"{assignee}'s" if assignee else "")
    return " ".join(word for word in words if word)


def list_issues(
    status=None,
    priority=None,
    labels=(),
    as_json=False,
    ready=False,
    blocked=False,
    assignee=None,
    unassigned=False,
):
    issues, by_id = select_issues(
        status, priority, labels, ready=ready, blocked=blocked,
        assignee=assignee, unassigned=unassigned,
    )

    # Everything above collects; everything below renders. --json swaps the
    # renderer and nothing else - same issues, same order, same filter.
    if as_json:
        # Before the empty check on purpose: "no issues" is [] to a script, not
        # a sentence it would choke on.
        print(json.dumps([as_dict(issue, by_id) for issue in issues], indent=2))
        return

    if not issues:
        # Two different empty cases: nothing at all, or nothing matching.
        # Either is exit 0 - a filter matching nothing is a fact about the
        # repo, which is the distinction `search` draws against.
        wanted = narrowing(priority, status, labels, ready, blocked, assignee, unassigned)
        print(f"No {wanted} issues" if wanted else "No issues yet - run: issue create")
        return

    print_table(issues, {issue["id"]: blocked_note(issue, by_id) for issue in issues})


def next_issue(as_json=False):
    """The one issue to work on now, and nothing else - `issue list --ready`
    hands back a table and leaves the last step to the caller, which for an
    agent is a backlog scan and a paragraph of reasoning to re-derive a
    decision that was already deterministic.

    Read-only on purpose: it does not claim, assign or set in-progress. Asking
    the question should not answer it, and that is also what makes it cheap to
    ask twice."""
    issues, by_id = select_issues()
    candidates = [issue for issue in issues if actionable(issue, by_id)]

    if not candidates:
        # Nothing on stdout in either mode, and exit 1: a parser gets a clean
        # EOF instead of a prose apology, and a script gets the branch it
        # wants. Same contract `search` has - a lookup that found nothing
        # failed, unlike a filter that matched nothing.
        print(
            "Nothing to work on - every issue is closed or blocked",
            file=sys.stderr,
        )
        sys.exit(1)

    # min, not sort: one pass, and next_rank breaks every tie, so this is the
    # answer rather than the first of several equally good ones.
    issue = min(candidates, key=next_rank)

    if as_json:
        # The same as_dict `list --json` prints, one object rather than an
        # array of one - the caller asked for the next issue, not for a list
        # that happens to be short.
        print(json.dumps(as_dict(issue, by_id), indent=2))
        return

    # Four lines, not a table: the backlog is what the caller was trying not
    # to read. The Ready line is the JSON's `ready` rendered, not a second
    # opinion - so the two renderings of one decision cannot disagree. It
    # reads "in progress" for a started issue because `ready` means what
    # `list --ready` means everywhere else, and printing "no" on the issue the
    # tool just told you to work on would read as a bug.
    print(f"{issue['id']}  {issue['title']}")
    print(f"Status:   {issue['status']}")
    print(f"Priority: {priority_of(issue)}")
    print(f"Ready:    {'yes' if is_ready(issue, by_id) else 'in progress'}")


def search_issues(query, status=None, priority=None, labels=(), as_json=False):
    """`list`, narrowed by words and told why each row is there. Same order and
    same columns as `list` on purpose: two arrangements of the same ids means
    noticing which command printed them before you can read them.

    Exit 1 when nothing matched, --json or not. That is grep's contract, and
    search is a grep-shaped command - `issue search "x" || issue create "..."`
    should work. It differs from `list` printing "No open issues" at 0, and the
    difference is the point: a filter finding nothing is a fact about the repo,
    a lookup finding nothing failed, the same way `view` on a missing id does."""
    words = query.lower().split()
    if not words:
        # Not a listing of everything - `issue list` already does that.
        print(
            'Give something to search for - e.g. issue search "verification email"',
            file=sys.stderr,
        )
        sys.exit(1)

    issues, by_id = select_issues(status, priority, labels, words)
    found = {issue["id"]: matching_lines(issue, words) for issue in issues}

    if as_json:
        print(
            json.dumps(
                [{**as_dict(issue, by_id), "matches": found[issue["id"]]} for issue in issues],
                indent=2,
            )
        )
    elif issues:
        # Why the row is stuck, then why it is here: one notes map, two kinds
        # of line.
        print_table(
            issues,
            {id: blocked_note(by_id[id], by_id) + lines for id, lines in found.items()},
        )

    if not issues:
        # stderr, so stdout stays parseable - and it names the filters as well
        # as the query, because "no results" without the question is the
        # message that makes you re-run the command to find out what you asked.
        wanted = narrowing(priority, status, labels)
        print(
            f"No {wanted + ' ' if wanted else ''}issues match {query!r}",
            file=sys.stderr,
        )
        sys.exit(1)


def as_dict(issue, by_id):
    """The issue as JSON wants it, which is not quite as the file holds it.

    Arrays, so nothing downstream has to split a string the tool already split.
    `blocks` and `ready` although no file stores either: the consumer wants the
    fact, not the storage, and recomputing `ready` means an agent re-reading
    every file to check each blocker when the tool had them all in memory a
    moment ago. Unlike labels these three are always there - `ready` is the
    field an agent asks for on every issue, and a key it has to guess about is
    a key it has to write a branch for."""
    dumped = {**issue, "blocked_by": blockers_of(issue)}
    if "labels" in issue:
        dumped["labels"] = labels_of(issue)
    dumped["blocks"] = blocks(issue["id"], by_id)
    dumped["ready"] = is_ready(issue, by_id)
    return dumped


def view_issue(id, as_json=False):

    issue = read_issue(id)
    if issue is None:
        # An id that isn't there is a failed lookup, not an empty one - same
        # contract as require_issue_dir, so a script gets a non-zero exit rather
        # than success with nothing on stdout.
        print(f"Issue {id} Doesnt Exist", file=sys.stderr)
        sys.exit(1)

    # Both directions need the others: `blocks` is stored nowhere.
    by_id = {other["id"]: other for other in load_issues()}

    if as_json:
        # body included verbatim - it is the field the table cannot carry and
        # the one an external reader actually wants.
        print(json.dumps(as_dict(issue, by_id), indent=2))
        return

    # Issues written before updated_at existed have none - say so rather than
    # inventing a time we never recorded. LABELS only appears when there are
    # some: this table is already five columns of timestamps that rich has to
    # elide, and an empty sixth would cost the others width for nothing.
    fields = [
        ("ID", issue["id"]),
        ("STATUS", issue["status"]),
        ("PRIORITY", priority_of(issue)),
        ("CREATED AT", issue["created_at"]),
        ("UPDATED AT", issue.get("updated_at", "unknown")),
        ("ASSIGNEE", assignee_of(issue)),
    ]
    if labels_of(issue):
        fields.append(("LABELS", ", ".join(labels_of(issue))))

    table = Table(show_header=True, header_style="bold cyan")
    for name, _ in fields:
        table.add_column(name)
    table.add_row(*(value for _, value in fields))
    console.print(table)

    # Both directions, each id with its status, because a blocker's status is
    # the only thing about it that matters. Neither line when that side of the
    # edge is empty.
    for name, ids in (("Blocked by", blockers_of(issue)), ("Blocks", blocks(id, by_id))):
        if ids:
            console.print(f"{name + ':':<12}{said_blockers(ids, by_id)}", highlight=False)

    console.print(Markdown(issue["body"]))
    

def set_fields(
    words: list[str],
    priority: str = None,
    add=(),
    remove=(),
    block=(),
    unblock=(),
    assignee: str = None,
    quiet: bool = False,
):
    """`issue set ISS-001 closed`, `issue set ISS-001 --priority high`, or both
    at once. The status stayed a bare word because that is what the README
    documents and what people already type; which word it is, is decided here
    rather than by the parser - click cannot tell a trailing optional word from
    an id when only one word is given, and reads `issue set ISS-001` as a
    status with no ids.

    Labels and blockers are the fields that do not replace: --label/--unlabel
    and --blocked-by/--unblock are the same add/remove pair, computed per issue
    because the result depends on what that issue already has. Blockers get the
    validation labels do not need - a label is invented, an id must exist.

    --assignee replaces, like status and priority, and empty clears it - which
    is all `assign` and `release` are. `claim` is the third way in, and passes
    quiet because it prints its own line; one function writes the field so the
    "already assigned" message and the real behaviour cannot drift."""
    ids = list(words)
    status = ids.pop() if ids and ids[-1] in STATUSES else None
    add, remove = clean_labels(add), clean_labels(remove)
    if assignee is not None:
        assignee = assignee.strip()
    block, unblock = clean_ids(block), clean_ids(unblock)

    both = (set(add) & set(remove)) | (set(block) & set(unblock))
    if both:
        print(
            f"Cannot add and remove the same thing: {', '.join(sorted(both))}",
            file=sys.stderr,
        )
        sys.exit(1)

    if (
        status is None
        and priority is None
        and assignee is None
        and not (add or remove or block or unblock)
    ):
        # Also where a mistyped status lands: it is not a status, so it was
        # read as an id, and nothing was asked for. Saying what the words are
        # beats "Issue opne Was Not Found".
        print(
            f"Give a status ({', '.join(STATUSES)}), --priority "
            f"({', '.join(PRIORITIES)}), --assignee, --label, --unlabel, "
            "--blocked-by or --unblock - e.g. issue set ISS-001 closed",
            file=sys.stderr,
        )
        sys.exit(1)
    if not ids:
        print("No issue ids given", file=sys.stderr)
        sys.exit(1)
    # Validated once for the whole batch - the words are typed by the user now,
    # so a typo must not reach the file. One bad word, one error line.
    if priority is not None:
        require_priority(priority)

    fixed = {"status": status, "priority": priority, "assignee": assignee}
    fixed = {field: value for field, value in fixed.items() if value is not None}

    # Every issue, not just the ones named: a blocker's status lives in another
    # file, and the same map answers "what is in the way", "does this close a
    # cycle" and "what did closing this free".
    by_id = {issue["id"]: issue for issue in load_issues()}
    if block:
        require_blockers(ids, block, unblock, by_id)

    missing, closed = [], []
    for id in ids:
        issue = by_id.get(id)
        if issue is None:
            # Keep going: one bad id in a batch should not cancel the rest.
            # The exit code carries the failure instead, once, at the end.
            print(f"Issue {id} Was Not Found", file=sys.stderr)
            missing.append(id)
            continue

        stuck = in_the_way(issue, by_id)
        if stuck and status is not None and status != "closed":
            # Blocked is not forbidden, only reported: a tracker that refuses
            # is one people stop telling the truth to, and the first time it is
            # wrong someone deletes the field rather than argue with it. stderr,
            # so it is a note to the reader and not a row to whatever is parsing.
            print(f"{id} is blocked by {said_blockers(stuck, by_id)}", file=sys.stderr)

        wanted = dict(fixed)
        if add or remove:
            labels = [label for label in labels_of(issue) if label not in remove]
            wanted["labels"] = ", ".join(sorted(set(labels + add)))
        if block or unblock:
            blockers = [was for was in blockers_of(issue) if was not in unblock]
            wanted["blocked_by"] = ", ".join(sorted(set(blockers + block)))

        # get(field, "") and not get(field): an issue with no labels and a call
        # that removes its last one both mean "", and that is not a change.
        changed = {
            field: value for field, value in wanted.items() if issue.get(field, "") != value
        }
        if not changed:
            # Already there is success - what the caller asked for is what is on
            # disk, which is all `set` promises.
            if not quiet:
                print(f"Issue {id} is already {describe(wanted)}")
        else:
            for field, value in changed.items():
                # Empty means gone: the last label removed takes the field with
                # it, rather than leaving "labels:" behind on the file.
                if value:
                    issue[field] = value
                else:
                    issue.pop(field, None)
            write_issue(issue)
            if not quiet:
                print(f"{id} has been set to {describe(changed)}")
            if changed.get("status") == "closed":
                closed.append(id)

    # Closing is the one write with consequences in other files. by_id holds
    # the same dicts that were just written, so what it says now is what is on
    # disk - no second scan. stdout, id first, one line each: an agent that
    # just closed something picks up the next thing without a second command,
    # and `awk` gets the id from where it always is.
    for issue in by_id.values():
        if set(closed) & set(blockers_of(issue)) and is_ready(issue, by_id):
            print(f"{issue['id']} is now ready")

    # Partial failure is failure: `issue set A B closed && git commit` must not
    # commit when B was never set. The good ids are still written - the batch
    # ran to the end first.
    if missing:
        sys.exit(1)


def claim_issue(id, by=None):
    """The one ownership verb that can fail. `assign` and `release` are
    spellings of `set --assignee` and win by definition; `claim` is a write
    with a condition attached, and a command that can be perfectly well formed
    and still fail is a different contract, worth a different word.

    It succeeds on an issue that is unassigned or already yours, and exits 1
    naming the owner when it is not - because the next thing the caller does is
    either pick another issue or go and ask that person.

    A closed issue cannot be claimed: there is nothing to start, and a claim on
    one is almost always a typo'd id that happens to exist. A blocked one can
    be - claiming is saying you will do it, which is the reasonable thing to do
    about work you are waiting on."""
    who = (by or current_user()).strip()
    if not who:
        # Rather than writing an owner nobody can be held to.
        print(
            "No name to claim as - pass --by, or set $ISSUE_USER or git config user.name",
            file=sys.stderr,
        )
        sys.exit(1)

    issue = read_issue(id)
    if issue is None:
        print(f"Issue {id} Was Not Found", file=sys.stderr)
        sys.exit(1)
    if issue["status"] == "closed":
        print(f"{id} is closed - there is nothing to claim", file=sys.stderr)
        sys.exit(1)
    owner = issue.get("assignee")
    if owner and owner != who:
        print(f"{id} is already {owner}'s", file=sys.stderr)
        sys.exit(1)

    set_fields([id], assignee=who, quiet=True)

    # Check-then-write is not atomic and there is no lock to take. Read the
    # file back: whichever order two writes land in, exactly one caller reads
    # its own name back, so exactly one is told it succeeded and the other goes
    # and picks the next row instead of starting the same work.
    #
    # ponytail: this closes the window, it does not remove it - a reader
    # interleaved between another writer's two operations can still be told the
    # wrong thing, and the fix if it ever matters is an O_EXCL claim file, not
    # a lock.
    landed = (read_issue(id) or {}).get("assignee")
    if landed != who:
        print(f"{id} is already {landed}'s", file=sys.stderr)
        sys.exit(1)

    print(f"{id} is now {who}'s")


def log_issue(id):
    """`git log` for one issue file. The history is already in the repo because
    issues are files - this only points git at the right path and gets out of
    the way. No parsing of git's output: --format is the whole formatter."""
    file_path = os.path.join(require_issue_dir(), f"{id}.md")
    if not os.path.isfile(file_path):
        print(f"Issue {id} Doesnt Exist", file=sys.stderr)
        sys.exit(1)

    # -- before the path so an id that looks like a revision cannot be read as one.
    # encoding: git writes UTF-8; text=True alone decodes with the locale
    # default, which is cp1252 here and turns every accent into mojibake at
    # exit 0. Same reason storage.py passes it to every open().
    git = ["git", "log", "--follow", "--date=short", "--format=%h  %ad  %s", "--", file_path]
    result = subprocess.run(git, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        # Not a git repo, or the file is outside it - git already said which.
        print(result.stderr.strip() or "git log failed", file=sys.stderr)
        sys.exit(1)
    if not result.stdout.strip():
        # An empty log is not a successful one: the file exists but git has
        # never seen it, and printing nothing at exit 0 looks like no history.
        print(f"Issue {id} has never been committed", file=sys.stderr)
        sys.exit(1)

    print(result.stdout, end="")

    # Edits that are not committed yet are invisible above. Say so on stderr,
    # so it is a note to the reader and not a row to whatever is parsing stdout.
    pending = subprocess.run(
        ["git", "status", "--porcelain", "--", file_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if pending.stdout.strip():
        print(f"({id} has uncommitted changes, not shown above)", file=sys.stderr)
