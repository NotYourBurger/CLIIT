# cli-issue-tracker

A small issue tracker that lives in your repo. Issues are plain Markdown files
in a `.issues/` folder, so they version with your code and read fine without
the tool.

## Install

```bash
uv sync
```

## Usage

```bash
issue init                          # create .issues/ in the current directory
issue create "Title" "Description"  # write .issues/ISS-001.md
issue create "Title" "..." --priority high   # high, medium (default) or low, -p for short
issue create "Title" "..." -l bug -l auth    # labels, repeat the flag for more
issue list                          # every issue, grouped by status
issue list open                     # only one status: in-progress, open or closed
issue list --priority high          # only one priority; combines with a status
issue list --label bug              # only issues with every label given
issue list --ready                  # open, and nothing open is in the way
issue list --blocked                # stuck, and what on
issue list --assignee tahmid        # what tahmid is on (-a for short)
issue list --unassigned             # what nobody has taken
issue list --ready --unassigned --json    # what an agent may safely start
issue next                          # the one issue to work on now
issue next --json                   # the same decision, for an agent
issue search "verification email"   # every issue whose body or title has both words
issue search auth --status open -p high   # the same filters list takes, ANDed with the query
issue view ISS-001                  # render the issue as formatted Markdown
issue set ISS-001 ISS-002 closed    # set the status of one or more issues
issue set ISS-001 --priority high   # set the priority instead, or alongside a status
issue set ISS-001 -l backend -L bug # add a label, remove a label, in one write
issue set ISS-012 -b ISS-009        # ISS-012 cannot start until ISS-009 closes
issue set ISS-012 -B ISS-009        # never mind (--blocked-by and --unblock in long form)
issue claim ISS-021                 # mine, if nobody else got there first
issue claim ISS-021 --by codex-1    # --by defaults to $ISSUE_USER, then git config user.name
issue assign ISS-021 --to codex-1   # hand it over, no questions
issue release ISS-021               # not mine any more
issue log ISS-001                   # the issue's git history: who changed it, when, why
```

Statuses are `in-progress`, `open` and `closed`. `issue list` groups them with a
rule between groups and prints them least urgent first — closed, then open, then
in-progress — with the highest priority last inside each group. The list reads
bottom-up on purpose: the last line printed sits right above the prompt, which
is where you are already looking, so what needs attention is there and the
closed pile is what scrolls away.

Priorities are `high`, `medium` and `low`, stored as a `priority` frontmatter
field. They filter, they show in a column, and they are the second sort term
under status — highest last. Issues filed before the field existed have no
priority: they show `-`, they sort to the top as the least urgent thing there
is, and they match no `--priority` filter rather than being counted as
`medium`.

Labels say what kind of issue it is — `bug`, `auth`, `docs`, whatever you
invent. They are stored as one comma-joined `labels` field, lowercased, deduped
and sorted, so a label cannot contain a comma; no labels means no field at all.
`--label` on `set` adds and `--unlabel` (`-L`) removes, because a label is
something you learn about an issue after filing it. Removing the last one takes
the field with it.

`issue list --label bug --label auth` wants both, not either: repeating a filter
narrows, the way adding `--priority` to a status does. The LABELS column shows
up only when something has labels, and it is last, so a long label set cannot
push another column off the screen. `--json` is the one place the output is not
a literal transcript of the file — labels come out as an array, so nothing
downstream has to split the string again.

`issue search` is `list` narrowed by words: split on whitespace, all of them
required, case-insensitive, as substrings, anywhere in the title or the body —
so `auth` finds `authentication`, and `"verification email"` finds
"verification of the email" that a phrase search would miss. Deliberately not
regex, fuzzy matching or ranking. It takes the same `--status`, `--priority` and
`--label` filters as `list`, ANDed with the query and each other, and prints the
same table in the same order, plus **the line each match came from** indented
under the row — the thing `list` cannot show. A title-only match adds no line,
because the TITLE column is already it.

Nothing matched is exit 1, `--json` or not, with the query named on stderr so
stdout stays parseable — that is `grep`'s contract, so
`issue search "verification" || issue create "..."` works. It differs from
`issue list closed` printing "No closed issues" at exit 0 on purpose: a filter
finding nothing is a fact about the repo, a lookup finding nothing failed.
`search --json` is the `list --json` array with a `matches` array added per
issue, so an agent never has to re-read the files to find out why something
matched. Because the query is `search`'s positional argument, its status is the
`--status` flag — and `list` accepts `--status open` as a second spelling of its
trailing word, so the two commands do not disagree about how you name a status.

Dependencies say what blocks what — the question `--priority` cannot answer,
because the highest priority open issue is very often the one nobody can touch.
`--blocked-by` (`-b`) adds a blocker and `--unblock` (`-B`) removes one, the same
add/remove pair as `--label`, stored as one comma-joined `blocked_by` field —
**on the blocked issue only**. "A blocks B" and "B is blocked by A" are one fact,
and storing it twice means the first hand-edit or deleted file leaves two copies
disagreeing with nothing able to decide which is true. The other direction is
derived by reading the others, which every command already does. It also degrades
the right way: delete the blocker and the stuck issue still says what it was
waiting for.

An unknown id, an issue blocking itself, or a cycle is exit 1 with nothing
written — and a cycle prints the path, `ISS-012 -> ISS-009 -> ISS-004 ->
ISS-012`, because "cycle detected" sends you off to read four files to find the
edge to drop. `--unblock` is the one that does *not* require the id to exist: a
blocker whose file was deleted is exactly the one you need to remove.

`issue list --ready` is open with every blocker closed — the standup question,
and `issue list --ready --json` is an agent's whole "what do I pick up next" in
one call. Direct blockers only, not transitive: if someone closed B while C was
still open, B is done because a person said so, and B's blockers stopped being
A's problem then. A **missing** blocker never blocks either — it can never be
closed, so counting it would strand the issue forever; it prints as
`ISS-042 (missing)` instead, which is louder and points at the repair.

`issue next` goes one step further and picks. `--ready` hands back a table and
leaves the last row to you, which is fine for eyes and expensive for an agent —
list, read the statuses, read the priorities, chase the blockers, decide, every
time, before any work starts. `issue next` is that decision in one call, and
`issue next --json` is the whole of an agent's "what do I do now".

It returns one issue, ranked: `in-progress` before `open`, then priority high
to low with no priority last, then the oldest `created_at`, then the id. The
tail of that list is the point — two issues filed in the same second with the
same priority must come out in the same order every time, or asking twice gets
you two different answers and neither gets finished. The status and priority
orders are the same two tuples `list` reads backwards, so there is one place
saying what urgent means.

Closed and blocked issues are never returned, by the same `in_the_way` rule
`--ready` uses — `--ready` is that rule plus "open", `next` is that rule plus
"not closed", and neither has its own idea of what blocks work. The human
output is four lines rather than a table, because the backlog is what you were
trying not to read; the `Ready:` line is the JSON's `ready` field rendered, so
it says `in progress` for a started issue rather than contradicting it. With
nothing to work on it prints nothing on stdout and exits 1, `search`'s
contract: a lookup that found nothing failed, unlike a filter that matched
nothing.

It is read-only. It does not claim the issue, does not set `in-progress` and
writes no file — asking what to do next should not decide it for you, and that
is also what makes it safe to ask twice. `issue claim` is one call away.

Blocked issues get a `blocked by ISS-009 (open)` line indented under the row —
the same mechanism `search` uses for a match line, so there is no new column, and
it shows on plain `issue list` too. A blocked row that looks identical to a ready
one is the thing this exists to fix; `--ready` is the filter that takes them
away. `view` shows both directions with each blocker's status. `--json` grows
`blocked_by`, `blocks` and `ready` on every issue — `blocks` and `ready` are
stored in no file, but the consumer wants the fact, not the storage.

Being blocked does not forbid anything: `issue set ISS-012 in-progress` prints
what is in the way on stderr and then does it. A tracker that refuses is one
people stop telling the truth to — the first time it is wrong about a dependency
someone deletes the field rather than argue with it, and a graph people route
around is worse than no graph. Closing the last blocker reports what it freed on
the same run, one line per issue, id first: `ISS-012 is now ready`.

Ownership says who is working on it — the question `--ready` cannot answer,
because it gives every caller the same answer and two agents asking a second
apart both start the same issue. It is one `assignee` frontmatter field holding
one name, deliberately a field and not a label: ownership has an arity, exactly
one, and "exactly one" is the entire feature — a set cannot hold that rule, and
two labels named after two people record the collision instead of preventing
it. It would also mix people into the same namespace as `bug` and `auth`.

`issue claim` is the one with a precondition: it succeeds only if the issue is
unassigned or already yours, and exits 1 naming the current owner otherwise, so
the next thing you do is pick another issue or go and ask that person. `assign`
has no precondition — handing work over is normal, and a tool that makes you
release first is a tool people work around. `release` clears the field, and
already-unassigned is success, the same way `set` treats a field that is
already what you asked for. All three are one write: `assign` is
`issue set ISS-021 --assignee codex-1` and `release` is the same with an empty
value, so the messages and the behaviour cannot drift apart.

Check-then-write is not atomic and there is no lock to take, so `claim` writes
and then reads the file back: if the name that comes back is not yours, you
lost the race, and it says who won and exits 1. Whichever order two writes
land in, exactly one caller reads its own name back, so exactly one is told it
succeeded.

The name is not verified and cannot be — an issue is a file in a git repo, and
anyone who can write the file can write any name into it. The audit trail
already exists and is better: `issue log ISS-021` shows who committed the
change. `--by` defaults to `$ISSUE_USER`, then `git config user.name`; with
neither, `claim` says so and exits 1 rather than writing an owner nobody can be
held to. `$ISSUE_USER` is what an agent sets once at the top of a run instead of
threading a name through every call.

A closed issue cannot be claimed — there is nothing to start, and a claim on one
is almost always a typo'd id that happens to exist — but it can still be
assigned and released, because cleaning up after the fact is real. A **blocked**
issue *can* be claimed: claiming is saying you will do it, which is the
reasonable thing to do about work you are waiting on.

`--assignee` and `--unassigned` AND with every other filter, and with each other
they contradict — that is exit 1 with a sentence, not an empty table, because no
repo state can satisfy it and printing "no issues" blames the repo for the
caller's mistake. `issue list --ready --unassigned --json` is an agent's whole
loop: find work nothing is blocking and nobody owns, `claim` one, and the claim
is what makes the next agent's query return something different. The ASSIGNEE
column is conditional the way LABELS is — absent entirely when nothing in the
result is owned — and sits before LABELS, because LABELS is the one value with
no bound on its width and a name has a bound. Unassigned shows `-`, like a
missing priority. In `--json`, `assignee` is there when the issue has one and
absent when it does not, the same rule labels follow.

Not in scope, deliberately: `claim` setting `in-progress` as a side effect (two
facts written by one word, and then `release` has to guess whether to undo it),
multiple assignees, reviewers, teams, and expiring a stale claim after N days —
the last one is a scheduler, not a tracker.

`issue set` takes any of a status, a `--priority`, an `--assignee`, a `--label`/`--unlabel`, or
all of them — `issue set ISS-001 closed --priority low -l bug` is one write, and
it reports only what actually moved. The status stays a bare trailing word so
the old form keeps working; a word that is not a status is read as an id, so a
mistyped one gets told which words `set` accepts instead of being written.

Every command except `init` finds `.issues/` by walking up from the current
directory, the way `git` finds `.git`, so they all work from anywhere in the
repo. `init` is deliberately local — it creates `.issues/` right where you are,
and warns if there is already one above it. Set `ISSUES_DIR` to point the tool at
a specific directory and skip the walk entirely.

`ISSUE_USER` is the third environment knob: it is who `issue claim` acts as
when `--by` is not given, checked before `git config user.name`.

Ids are `ISS-001`, `ISS-002` and so on. Set `ISSUE_PREFIX` to use different
letters — `ISSUE_PREFIX=BUG issue create ...` files `BUG-001.md`. Only `create`
reads it; everything else works off the filename, so issues filed under an old
prefix keep listing and numbering restarts under the new one instead of
continuing across both.

## File format

Each issue is one Markdown file with YAML-style frontmatter:

```markdown
---
id: ISS-001
status: open
created_at: 2026-09-04T14:04:43+06:00
priority: medium
assignee: tahmid
labels: bug, frontend
blocked_by: ISS-009
---

# List View for the Issue Tracker

Running `issue list` should print every issue in the repo as an aligned table.
```

Everything below the frontmatter is yours — headings, tables, code fences and
horizontal rules all survive a read/write round trip. Frontmatter fields the tool
does not know about are kept too, so you can add your own by hand. Ids are
allocated as one past the highest existing id with the same prefix, so deleting
an issue never reuses a live id.

## Layout

| File            | Owns                                                   |
| --------------- | ------------------------------------------------------ |
| `cli.py`        | Typer commands                                         |
| `issues.py`     | what each command does and how output looks            |
| `storage.py`    | finding `.issues/`, and the file format                 |
| `convert_id.py` | allocating the next id                                 |
| `init.py`       | creating `.issues/` here, and only here                |
| `tests/`        | one script per thing that can break, plus the runner   |

`issue log` is `git log --follow` pointed at the issue file — the history comes
free from issues being files. Uncommitted edits are invisible to git, so it says
so rather than looking like nothing changed.

## Status

Working: `init`, `create`, `list`, `next`, `search`, `view`, `set`, `claim`,
`assign`, `release`, `log`.

Run every check with `uv run python tests/all.py`. They live in `tests/`, one
file per thing that can break:

| Check                | Covers                                                     |
| -------------------- | ---------------------------------------------------------- |
| `test_storage.py`    | the file format, parse → write → parse round trips          |
| `test_log.py`        | `issue log` against a throwaway git repo                    |
| `test_priority.py`   | priority, and the issues that predate the field             |
| `test_labels.py`     | labels, the first field that merges instead of replacing    |
| `test_search.py`     | matching, the filters that AND with it, and the exit code   |
| `test_blockers.py`   | dependencies: one stored side, two read, and the bad edges  |
| `test_assignee.py`   | ownership: the one write with a precondition, and the race  |
| `test_next.py`       | the `next` ranking, every tie-breaker, and the empty case    |
| `test_encoding.py`   | that nothing reads or writes text at the locale default     |

No framework: each file is a script with a `demo()` that asserts and prints
`ok`, so `uv run python tests/test_search.py` runs one on its own and the
runner is a `for` loop over the rest. It runs each in its own subprocess —
these tests `chdir` and set `ISSUES_DIR`, and one process would let the first
skipped cleanup break the next file and blame the wrong one. One failure does
not stop the others; the exit code counts them. `tests/helpers.py` holds the
two things they all wanted: `run()`, which calls a command and hands back its
exit code, stdout and stderr, and `REPO`.

`test_encoding.py` exists because the same mistake landed three times: this machine
defaults to cp1252, so anything reading or writing text without being told
UTF-8 mangles accents quietly and still exits 0. It parses the source and fails
on any `open()` or `subprocess` call that takes the locale default, rather than
waiting for a fourth bug report.
