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
issue brief                         # what is happening in this project
issue brief --json                  # the same orientation, for an agent
issue next                          # the one issue to work on now
issue next --json                   # the same decision, for an agent
issue next --claim                  # ...and take it, retrying if the claim is lost
issue search "verification email"   # every issue whose body or title has both words
issue search auth --status open -p high   # the same filters list takes, ANDed with the query
issue view ISS-001                  # render the issue as formatted Markdown
issue set ISS-001 ISS-002 in-progress   # set the status of one or more issues
issue set ISS-001 --priority high   # set the priority instead, or alongside a status
issue set ISS-001 -l backend -L bug # add a label, remove a label, in one write
issue set ISS-012 -b ISS-009        # ISS-012 cannot start until ISS-009 closes
issue set ISS-012 -B ISS-009        # never mind (--blocked-by and --unblock in long form)
issue close ISS-014 --completed -m "..." --commit 81af03c   # closing takes a reason and proof
issue close ISS-014 --completed -m "..." --test "uv run python tests/all.py"
issue close ISS-018 --not-planned -m "Conflicts with the deterministic search contract."
issue close ISS-028 --duplicate-of ISS-014 -m "Same bug."
issue close ISS-022 --superseded-by ISS-031 -m "Replaced by the architecture index."
issue claim ISS-021                 # mine, if nobody else got there first
issue claim ISS-021 --by codex-1    # --by defaults to $ISSUE_USER, then git config user.name
issue assign ISS-021 --to codex-1   # hand it over, no questions
issue release ISS-021               # not mine any more
issue check                         # everything wrong with the files, or nothing at all
issue check --json                  # the same findings, for an agent
issue check --plans                 # how much each work plan is actually kept
issue log ISS-001                   # the issue's git history: who changed it, when, why
issue start ISS-042                 # open the work, or pick it back up where it stopped
issue start ISS-042 --anyway        # start it even though something blocks it
```

Statuses are `in-progress`, `open` and `closed` — `closed` is written by
`issue close`, not by `issue set`. `issue list` groups them with a
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

Issues assigned to somebody else are never returned either, by the rule
`claim` already had: an issue is yours to take when nobody owns it or you
already do. `next` was the command not reading that field, which is how two
agents asking at once were handed the same id — the tie-breaking down to the
id that makes the answer stable is exactly what makes it identical. Only when
there is a name to compare against: with no `$ISSUE_USER` and no
`git config user.name` nothing is filtered, because a solo user cannot be
anybody and must not be told their own backlog is spoken for. When every
candidate belongs to someone else it exits 1 with its own line —
`Nothing to work on - N issue(s) are assigned to someone else` — because going
to ask an owner is a different repair from closing or unblocking something.
`issue brief` is unfiltered on purpose: orientation has to show what other
people are on, and *what is going on here* is a different question from *what
may I start*.

Closed and blocked issues are never returned, by the same `in_the_way` rule
`--ready` uses — `--ready` is that rule plus "open", `next` is that rule plus
"not closed", and neither has its own idea of what blocks work. The human
output is four lines rather than a table, because the backlog is what you were
trying not to read; the `Ready:` line is the JSON's `ready` field rendered, so
it says `in progress` for a started issue rather than contradicting it. With
nothing to work on it prints nothing on stdout and exits 1, `search`'s
contract: a lookup that found nothing failed, unlike a filter that matched
nothing.

It is read-only by default. It does not claim the issue, does not set
`in-progress` and writes no file — asking what to do next should not decide it
for you, and that is also what makes it safe to ask twice.

`issue next --claim` is the version that decides, and it is a flag precisely so
the default stays a question. The ownership filter above narrows the window
between two agents asking; it cannot close it, because reading is not taking.
`--claim` closes it the way `issue claim` does — write the assignee, read the
file back, and exactly one caller sees its own name — and the loser then walks
to the next candidate rather than exiting. That retry is the whole point: an
agent that asked for something it could start is owed a row, and a `--claim`
that gave up on the first collision would be worth no more than the plain
`next` it replaced. N agents calling it under N names come away with N distinct
ids. When every candidate is lost in the race it exits 1 with
`Nothing to claim - N candidate(s) were taken while trying`, and with no
`$ISSUE_USER` and no `git config user.name` it refuses before writing anything,
rather than putting an owner in the file that nobody can be held to.

`issue brief` answers the question before that one: *what is going on here at
all*. It used to cost five calls — `list`, `list --ready`, `list --blocked`,
`list in-progress`, then a read of whatever closed recently — and a person
skimmed them while an agent paid for four tables it mostly discarded. The brief
is one load of `.issues/` and seven sections, printed bottom-up so that reading
*up* from the prompt gives them in the order you use them:

```
WARNINGS
ISS-004 references missing blocker ISS-042

RECENTLY RESOLVED
+1 more
ISS-019  issue next - the one issue to work on now
         completed - next ships: ranked, deterministic, read-only.
ISS-020  Evidence-based closing
         completed - issue close ships: four reasons, required message.

BLOCKED
ISS-003  Issue 3  medium
         blocked by ISS-009 (open)

READY
+2 more
ISS-004  Issue 4  medium
         blocked by ISS-042 (missing)
ISS-002  Issue 2  high

IN PROGRESS
ISS-001  Issue 1  medium

NEXT
ISS-001  Issue 1
Status:   in-progress
Priority: medium
Ready:    in progress

PROJECT
Open: 8   In progress: 1   Ready: 7   Blocked: 1   Closed: 0
```

The reversal is the same convention `list` already holds to: a terminal leaves
you at the bottom, so the thing you came for has to be the part already on
screen. Printed in reading order, `PROJECT` and `NEXT` are the first two things
to scroll away on any repo with a few closed issues.

It goes all the way down: **a header opens its block, and the items inside it
end with the one you came for.** `READY` ends on the most urgent row, so the
one to start first is the one under the cursor and `list` and `brief` agree
about which end of a list is urgent; `RECENTLY RESOLVED` ends on the newest
close. `+N more` summarises the tail that was cut, so it sits directly under
the header — below the top row it would read as if it were hiding something
more urgent. The reversal happens in the printing, after the cap, never in the
sort keys: `next` takes the head of the same ranked list, and `--json` keeps
its logical order because nothing scrolls in a parser.

Every number in there comes from the function that already decides it —
`next` is the head of the same ranked list `issue next` picks from, `ready` is
that list minus it, `in_the_way` says what is blocked, `resolution_of` reads a
close. Nothing is re-derived: the day `brief` and `next` name different issues,
the brief is worse than the five commands it replaced, because it is
confidently wrong instead of merely verbose.

Everything but `IN PROGRESS` is capped — one next issue, five ready, five
resolved, `+N more` for the rest. Work already started is uncapped on purpose:
it is the thing you most want to not start again, and fifteen in-progress
issues is a problem the brief should show rather than hide. `RECENTLY RESOLVED`
is what makes this project memory rather than a dashboard — it is where you
find out that the thing you were about to build was closed as `not-planned` last
week. It sorts on `closed_at`, falling back to `updated_at` for issues closed
before that field existed; nothing is backfilled, because an approximate date
that looks exactly like a recorded one is the lie this file format exists to
prevent. `WARNINGS` is blockers pointing at ids with no file: they never block
anything, and this is the first thing that says the graph has a hole in it.

Empty sections are omitted in the human output and present-but-empty in
`--json` — a blank `BLOCKED` header teaches a reader nothing, and a parser
branching on whether a key exists learns worse than nothing. It always exits 0,
including on an empty project: `next` is a lookup and a lookup that finds
nothing failed, but `brief` is a report and an empty backlog is a finding.

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

## Closing

`issue close` is the only way an issue becomes closed. `issue set ISS-014 closed`
is refused and names the command to use instead — a breaking change on purpose,
because a second door into closing makes the evidence rule advisory, and an
advisory rule is the one an agent in a hurry routes around. `set` keeps `open`
and `in-progress`, so reopening stays where it is.

Every close takes exactly one reason and a `--message` that is not blank and is
one line:

| Reason              | What it says                                  | Needs                          |
| ------------------- | --------------------------------------------- | ------------------------------ |
| `--completed`       | the described work was implemented            | at least one piece of evidence |
| `--not-planned`     | we decided not to do it                       | the message                    |
| `--duplicate-of ID` | another issue already tracks it               | an issue that exists           |
| `--superseded-by ID`| another issue replaced it                     | an issue that exists           |

Evidence is `--commit <sha>`, `--test "<command>"`, `--pr <url>` and
`--verified "<what you checked>"`, each repeatable. `completed` is the one
reason that requires some, and that requirement is the whole feature: without it
`completed` decays back into "someone considered this finished" inside a month.
The other three are a word and a sentence.

Evidence is a claim, not a proof. `--test` records the command; it does not run
it, and nothing here should. `--pr` is a reference the tool stores and never
fetches — closing an issue must never need the network. `--commit` is the one
piece that is checked, with `git cat-file` against your local repo, and the
check is skipped rather than fatal when there is no repo.

Which leaves one soft spot, and `close` names it rather than closing it. A
`completed` whose evidence is nothing but `--verified` gets one line on stderr
saying so — the sentence satisfied the rule, and no machine can tell you whether
it was true. Requiring a commit or a test instead would give the rule teeth and
would also refuse the honest case: this project's own test fixtures close with
`--verified` so they are not tied to whatever repo they run inside. So the
divergence is made visible and nothing more. Exit code and stdout are unchanged.

`--duplicate-of` and `--superseded-by` carry the reason themselves, and take the
same two checks `--blocked-by` does: the id has to exist, and it cannot be the
issue itself. A dangling pointer in the one field whose job is to point somewhere
is the one thing worth refusing.

The resolution lands in the issue file as `reason`, `closed_at`, `message` and a
typed `evidence` list, and `issue view` prints it between the table and the
description:

```text
Resolution
Reason:     completed
Closed:     2026-09-06T16:44:17+06:00
Message:    Added cycle detection before dependency writes.

Evidence
Commit:     81af03c
Test:       uv run python tests/all.py
```

`--json` gives the same model as one `resolution` object, so an agent never
parses prose. Reopening with `issue set ISS-014 open` leaves the resolution
alone — it is history, and `issue log` shows it either way. Closing again
overwrites it rather than appending: a list of resolutions in frontmatter is an
event log, and an event log in a Markdown file is a database with no queries.
Issues closed before any of this existed keep working untouched — no reason is
invented for them, the same rule the issues that predate `priority` live by.

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

## Work plans

An issue says what the work is. It does not say where the work currently
stands, and that gap is paid for once per session: you pick up
`ISS-042 / in-progress`, re-read the repo, re-derive the decisions the last
session already made, and rediscover the constraint that changed the approach.
All of that existed — in a conversation that is gone.

A work plan is that state, kept in a file while the work happens:

```bash
issue start ISS-042
```

`start` sets the issue `in-progress`, claims it as `$ISSUE_USER`, and seeds
`.issues/work/ISS-042.md` — a Markdown skeleton of `## Goal`, `## Plan`,
`## Decisions`, `## Discoveries`, `## Current` and `## Next`. You fill it in as
you work: the `## Plan` bullets are `- [ ]` checkpoints, ticked to `- [x]` the
moment each one lands.

Nothing in the CLI edits the plan after that. There is deliberately no
`plan check 3` or `plan note "..."` — every one of those is a shell round trip
in the middle of the work, which is a decision point, which is a place to skip.
Ticking a box has to be cheaper than not ticking it, or it does not happen, and
"it does not happen" is the whole reason this replaced the handover it grew
out of: that one was written at the end of a session, and a session usually
ends at a usage limit, a crash or a closed terminal. Twenty-five issues shipped
and not one handover was ever written.

Which is why the record is created *before* the first edit rather than after
the last one. If the session disappears between two ticks, the loss is one
checkpoint, not one session.

Checkpoints are recoverable units of progress — `Login UI`, not `Open
auth.py` / `Add import` / `Save file`. Three to ten is the rule of thumb;
nothing enforces it, because a tool that rejected an eleventh would be wrong
about a large issue.

`start` is also the resume path. Run it again and it prints the plan instead of
reseeding it — an existing plan is never clobbered, truncated or overwritten,
so an agent never has to work out first whether work exists. It refuses a
blocked issue, naming the blockers and writing nothing; `--anyway` starts it
regardless and records in the plan header that the call was made.

Reading it back is `issue next`, which already names the right issue and now
says what was happening there:

```text
$ issue next
ISS-042  Login and signup
Status:   in-progress
Priority: high
Ready:    in progress

GIT
feature/auth @ 81af03c - uncommitted
src/auth/provider.ts
src/pages/login.tsx

PLAN  6/10
- [ ] Connect authentication state to the application
- [ ] Add the logout flow

DECISIONS
- Authentication state lives in AuthProvider

CURRENT
Connecting successful login to AuthProvider.

NEXT
Wire the login result into AuthProvider, then handle the failure branch.
```

Git is read at display time and never stored — the plan is live, so a stored
HEAD would be a lie the moment anything committed. Paths only, never a diff,
capped so a noisy tree cannot bury the rest, and nothing at all outside a repo,
because "we could not read it" is not "the tree was clean". `GIT` sits above
the plan because `NEXT` is the line acted on and the terminal leaves the last
line printed right above the prompt.

`next` stays read-only: asking what to work on must not claim, assign or start
it. `start` is the command that does that.

`issue view` shows three lines for an issue you are *not* working on — how far
it got, where it stands, what is next — and nothing at all when there is no
plan:

```text
Work plan: 6/10 checkpoints
Current: Connecting successful login to AuthProvider.
Next:    Wire the login result into AuthProvider.
```

Both `next --json` and `view --json` carry a `plan` object, absent when there
is none.

`issue close` warns on stderr when checkpoints are still unticked and closes
anyway — a checkpoint that stopped being relevant must not be able to veto a
close, and the evidence rules already own the question of completeness. The
plan is not moved or archived: it stays in `work/` as the account of how the
issue was actually built, and `git log` says how it got that way.

Nothing enforces any of this. A seeded plan that is never ticked is worse than
no plan — it is confidently stale and the next agent believes it. What changes
the odds is that the plan is created before the work, is edited with the tool
the agent is already holding, and carries its own instructions: `issue init`
writes the nine-line workflow rule into `CLAUDE.md` or `AGENTS.md`, and every
seeded plan repeats the four lines that matter mid-session as an HTML comment
at the top of the file. Both come from one constant in the source.

## Checking the files

The file format is the API, and its worst failure does not raise. A parser bug
returns a plausible dict that `issue set` then writes back over your prose, and
the first person to notice is reading a mangled issue weeks later. `issue check`
is the doctor for that:

| Finding             | Why it is silent otherwise                                    |
| ------------------- | ------------------------------------------------------------- |
| Would not survive a rewrite | Read, written back, compared byte for byte — the only failure class that loses text |
| A blocker that is not here  | A missing id never blocks, so nothing has ever had a reason to mention the hole |
| A status or priority nobody wrote | `issue next` drops an unknown status rather than raising, so the issue simply stops being offered |
| A work plan with no issue   | The plan is named after the issue and has no identity of its own |

Clean is exit 0 and no output. Anything found is exit 1, one line each on
stderr — or on stdout as JSON under `--json`. A hand-edited `labels: auth,
sessions` is deliberately not checked: after the split it is indistinguishable
from two labels, so it is undetectable by construction, and a check that
pretends otherwise is worse than none.

### `issue check --plans`

A different question about a different directory, so it takes the whole verb:
not what is wrong with the files, but whether the work plans are being kept.

```text
ISS-026  touched    1 commit   last touched 9 commits ago  8/8 ticked
ISS-029  touched    2 commits  last touched 0 commits ago  5/5 ticked
ISS-031  untouched  0 commits  not committed               0/0 ticked
```

The first column is the answer. A plan is **untouched** when it is still
exactly what `issue start` seeded — no checkpoints, and nothing in `Decisions`,
`Discoveries`, `Current` or `Next`. `Goal` does not count towards it, because
the CLI writes that one from the issue title. Anything else at all means
somebody came back to the file, which is the behaviour the feature rests on.
The ticked count comes from the same reader `issue view` uses.

The two git columns are context: the commit count is `git log --follow` on the
plan, and staleness is how many commits have landed since it last changed. A
plan that is touched but last committed nineteen commits ago is still worth a
look. It is a report and not a check — always exit 0, on stdout, `--json` for
whoever is counting.

This exists because ISS-026 shipped the work plan on an argument and put the
risk on the record in the same breath: nothing enforces it, and a seeded plan
that is never ticked is worse than no plan, because the next agent believes it.
The handover died of exactly that and it took twenty-five issues to notice —
because nobody was counting. The threshold is written down in
`docs/PRD/05-Work-Plan.md`: after five issues worked through `issue start`, if
fewer than three of five plans report as touched, the work plan goes the way of
the handover.

ISS-031 pointed that threshold at the commit count and ISS-032 moved it, for a
reason worth knowing before reading those two columns: they count **commits,
not edits**. A plan edited all the way through the work and committed once at
the end reads as `1 commit`, exactly like one seeded and abandoned — and that
is the normal case here, not the odd one. Reading the content instead also
survives a fresh clone, which has no mtimes, and a squash, which has no count.

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
horizontal rules all survive a read/write round trip. A closed issue also
carries `reason`, `closed_at`, `message` and `evidence` — the last one is a JSON
array, because frontmatter has no list type and the comma-joining that `labels`
and `blocked_by` use would cut a `--test` command in half at its first comma. Frontmatter fields the tool
does not know about are kept too, so you can add your own by hand. Ids are
allocated as one past the highest existing id with the same prefix, so deleting
an issue never reuses a live id.

Every file the tool writes goes out UTF-8 with LF line endings, on every
platform, and `.gitattributes` pins `.issues/**/*.md` to `eol=lf` so a checkout
does not put CRLF back. Reads still accept CRLF, so a file hand-edited in
Notepad parses — it just comes back LF. This matters more than it sounds: the
plan is a file an agent edits with its own tool, and an edit whose search text
has the wrong line endings matches nothing and silently does not land.

Work plans are one directory down, in `.issues/work/ISS-NNN.md`, and are the
one artifact here with no frontmatter at all — the issue already carries the
id and the metadata, and the plan is its execution state rather than a second
thing with its own identity. See [Work plans](#work-plans).

## Layout

| File            | Owns                                                   |
| --------------- | ------------------------------------------------------ |
| `cli.py`        | Typer commands                                         |
| `issues.py`     | what each command does                                 |
| `fields.py`     | reading one issue's fields, and what they may hold     |
| `deps.py`       | what blocks what                                       |
| `plan.py`       | what a work plan is: the rule, the seed, the reader    |
| `validate.py`   | the checks that run before anything is written         |
| `check.py`      | the checks that run over what is already written       |
| `render.py`     | how output looks, human and `--json`                   |
| `storage.py`    | finding `.issues/`, and the file format                 |
| `convert_id.py` | allocating the next id                                 |
| `init.py`       | creating `.issues/` here, and only here                |
| `tests/`        | one script per thing that can break, plus the runner   |

`issue log` is `git log --follow --reverse` pointed at the issue file — the
history comes free from issues being files. `--reverse` because git's default
puts the newest commit off the top of a long history and leaves the initial
filing at the prompt. Uncommitted edits are invisible to git, so it says so
rather than looking like nothing changed.

## Status

Working: `init`, `create`, `list`, `brief`, `next`, `search`, `view`, `set`,
`close`, `claim`, `assign`, `release`, `log`, `start`, `check`.

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
| `test_next.py`       | the `next` ranking, every tie-breaker, ownership, empty case |
| `test_close.py`      | closing: the reasons, the evidence rule, and what it refuses |
| `test_plan.py`       | seeding, resuming, the blocked refusal, and a mangled plan  |
| `test_check.py`      | `issue check`, against files the tool did not write, and the real `.issues/` |
| `test_encoding.py`   | that nothing reads or writes text at the platform default   |

No framework: each file is a script with a `demo()` that asserts and prints
`ok`, so `uv run python tests/test_search.py` runs one on its own and the
runner is a `for` loop over the rest. It runs each in its own subprocess —
these tests `chdir` and set `ISSUES_DIR`, and one process would let the first
skipped cleanup break the next file and blame the wrong one. One failure does
not stop the others; the exit code counts them. `tests/helpers.py` holds the
two things they all wanted: `run()`, which calls a command and hands back its
exit code, stdout and stderr, and `REPO`.

`test_encoding.py` exists because the same mistake landed four times: this machine
defaults to cp1252 and to CRLF, so anything reading or writing text without
being told mangles accents or line endings quietly and still exits 0. It parses
the source and fails on any `open()` or `subprocess` call that takes the
platform default — `encoding=` on every text call, and `newline=` on every
write-mode `open()` — rather than waiting for a fifth bug report. Reads are
deliberately left translated, which is what lets a hand-edited CRLF file parse.
