"""Pass, or exit 1 saying why - and always before anything touches disk.

A bad status, priority, blocker, commit or handover field is a failed command,
not a half-applied one, and a rejected `create` must not burn an id. Every
check in here either returns or exits.

The one rule the whole file format rests on lives at the top of `clean_set`:
frontmatter has no list type, so `labels` and `blocked_by` are comma-joined
strings and no value may contain a comma. `evidence` is the documented
exception and holds JSON instead, which is why it is checked elsewhere.
"""

import subprocess
import sys

from cli_issue_tracker.fields import PRIORITIES
from cli_issue_tracker.fields import STATUSES
from cli_issue_tracker.fields import blockers_of
from cli_issue_tracker.deps import cycle_from
from cli_issue_tracker.storage import read_issue


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


def require_prose(value, kind):
    """A handover's free-text field: present, not blank, and no line of it
    starting with `## `. The heading is what the body parser splits on, so a
    summary carrying one would come back as two sections and quietly lose half
    itself - the same shape of silent loss the comma rule exists to stop."""
    text = (value or "").strip()
    if not text:
        print(f"A handover needs a {kind} - it cannot be blank", file=sys.stderr)
        sys.exit(1)
    if any(line.startswith("## ") for line in text.splitlines()):
        print(
            f"A {kind} cannot contain a line starting with '## ' - that is the "
            f"section marker in the handover body",
            file=sys.stderr,
        )
        sys.exit(1)
    return text


def require_items(values, kind):
    """One of the handover's repeatable lists. Each item is one `- ` line, so a
    newline inside one would split it in two on the way back; order is kept
    rather than sorted the way clean_set sorts, because these are steps and the
    order is the caller's meaning."""
    items = []
    for value in values:
        text = value.strip()
        if not text:
            print(f"A {kind} cannot be empty", file=sys.stderr)
            sys.exit(1)
        if "\n" in text:
            print(f"A {kind} must be one line - pass two flags instead", file=sys.stderr)
            sys.exit(1)
        items.append(text)
    return items


def require_issues(words):
    """Every referenced issue exists, in the order given - the first is the
    primary. Ordered rather than sorted like clean_ids: the caller said which
    issue this handover is mostly about by naming it first. clean_set is still
    what checks the two shared rules, because `issues:` is comma-joined like
    every other id field."""
    clean_set(words, "issue id")
    ids = list(dict.fromkeys(word.strip() for word in words))
    for id in ids:
        if read_issue(id) is None:
            print(f"Issue {id} Was Not Found", file=sys.stderr)
            sys.exit(1)
    return ids


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


def require_commits(shas):
    """Every --commit names a commit in this repository, or exit 1 before the
    write. Local only, and skipped entirely when there is no repo - the
    evidence is still worth recording, and network access must never be on the
    path to closing an issue. `git cat-file -e` answers 128 for both "no repo"
    and "no such object", so the repo test comes first; that is also how
    log_issue treats git having nothing to say."""
    if not shas:
        return
    repo = subprocess.run(
        ["git", "rev-parse", "--git-dir"], capture_output=True, text=True, encoding="utf-8"
    )
    if repo.returncode:
        return
    for sha in shas:
        # ^{commit} so a tree or a blob that happens to share the prefix is not
        # accepted as the implementation.
        found = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if found.returncode:
            print(f"No commit {sha} in this repository", file=sys.stderr)
            sys.exit(1)
