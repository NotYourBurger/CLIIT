# Agent behaviour report

## 1. Setup

This run asked whether the repository's own workflow can carry a fresh agent
through issue work, including a session ending without a handoff. The target
issues were ISS-032 through ISS-035 on branch `iss-026-work-plan`.

Evidence was graded in this order:

1. commits and reflog;
2. issue and work-plan files;
3. working-tree diffs and file timestamps;
4. command output rerun by the coordinator;
5. worker self-report, only where the first four agreed.

ISS-034 and ISS-035 were each given to a fresh general-purpose worker without
inherited conversation context. Each prompt named the repository and issue,
pointed at `CLAUDE.md`, and required the repository workflow, verification,
commit, and evidence-based close. They ran sequentially. ISS-032 and the first
two ISS-033 sessions predate the final coordinator continuation; their durable
files and commits are available, but their task transcripts are not.

That distinction matters. The original scratchpad was not stored in the
repository. Probe A's stdout, the complete Phase 0 census, the intentional
kill's exact task event, and the killed worker's tool-call count did not survive
the later cutoff. This report does not turn those missing measurements into
facts. ISS-036 was filed for that failure.

**Sections 1, 3 and 4 were written while those measurements were unavailable.
They have since been recovered from the coordinating session, which was
rate-limited rather than terminated, and are supplied verbatim in section 8.**
The refusals below are left standing rather than rewritten, because what they
were right about is the mechanism: the data survived by luck, not by design,
which is why ISS-036 stays open.

The durable pre-control anchor is `ae715a9`, the ISS-031 close. The coordinator
continuation found `871849a` at `HEAD`: ISS-032 was closed, ISS-033 was
uncommitted and apparently finished, and ISS-034/035 were still untracked issue
files. The only unrelated residue was an untracked `AGENTS.md`, which every
worker left alone.

## 2. Per-agent timeline

### ISS-032: clean control

The issue's `updated_at` records `issue start` at 16:15:23 +06:00. The work plan
then records the design choices, test failure caused by the new table column,
and the live seven-plan comparison. The implementation commit `3070c17` landed
at 16:20:10, the issue closed at 16:20:26, and close commit `871849a` landed at
16:20:33: about five minutes from start to close.

At the implementation commit, five implementation checkpoints were ticked and
the compound "suite, commit, close" checkpoint remained open. The close commit
ticked it and stored commit/test evidence. No correction commit was needed.
Exact turn count and command order are unavailable because that worker's task
transcript was not durable.

### ISS-033: killed worker, fresh pickup, second cutoff

`issue start` wrote the in-progress issue at 16:22:39. The first worker changed
the write paths, byte-honest reads, encoding guard, regression tests, and
normalised files. The current plan records the pickup's observation that
`.gitattributes` already existed but its checkpoint was not ticked. Its file
timestamp is 16:27:20; the resumed plan was last written at 16:29:52. This
brackets the first handoff but does not recover the exact kill instant.

The pickup correctly inferred why `.gitattributes` was necessary: the index was
already LF while `core.autocrlf=true` recreated CRLF in the working tree. It
completed the tests and documentation and updated the plan. A second cutoff
then occurred before any ISS-033 commit or close.

The next coordinator's first three tool calls were:

1. inspect location, workflow files, branch, `HEAD`, status, and recent log;
2. read `AGENTS.md`, `CLAUDE.md`, ISS-033's issue and plan, and the diff;
3. read the plan, issue and `.gitattributes` as UTF-8, then inspect checkpoints
   and file timestamps.

It did not reimplement the feature. It graded the existing diff, reran all 13
test scripts, `issue check`, `issue check --plans`, the allocator self-check,
and a byte census. It then committed `1323f0a`, closed with evidence, and
committed `db039d5` at 16:40:46.

### ISS-034: clean run plus one recovery

The fresh worker's first three actions were to read `CLAUDE.md`/status/view,
run `issue start ISS-034` and inspect the relevant code, then fill in the work
plan. Start was recorded at 16:41:24. It found a genuine specification conflict:
the evidence PRD said reopen should retain resolution data, while the filed
issue and git-as-audit-trail rule required removing the current resolution. It
updated the PRD rather than hiding the contradiction.

Implementation, focused tests, the full suite, docs, and close completed by
16:46:02, about five minutes. The worker reported 21 tool calls in the main
run. Its behavior passed acceptance, but both commits omitted the run-level
`Claude-Session:` trailer. One specific recovery message caused the same worker
to rewrite the two commits, update close evidence, and rerun tests. The final
commits are `8994deb` and `902458f`. The recovery took 13 reported tool calls;
it included one PowerShell argument-parsing error and one mistyped short SHA,
both caught before handoff.

### ISS-035: clean run

The fresh worker first read `CLAUDE.md`, status and the issue; inspected the raw
issue and allocator/checker structure; then ran `issue start ISS-035` and read
the seeded plan. It added tests first. The duplicate-ID test failed for the
expected reason before implementation, while the allocator wrapper already
passed.

It kept duplicate detection in the directory pass that builds `by_id`, added
the worktree-ceiling `ponytail:` comment, and put the allocator self-check under
the globbed suite as `test_convert_id.py`. Start was recorded at 16:50:47,
implementation commit `43e6e64` landed at 16:55:41, and close commit `68a6a81`
landed at 16:56:49. The worker reported about 22 tool calls and no unplanned
correction.

## 3. The kill test

### Snapshot that survived

The intentional kill-time file was not separately copied into the repository,
so its exact bytes cannot be recovered from the repository alone. **They were
copied to the coordinator's scratchpad at 16:27 and are reproduced in section
8.4**, along with the kill trigger and timing in 8.3. The durable plan says what
the pickup found:

> The resumed session found `.gitattributes` written but its checkpoint unticked.
> Nothing else was misrecorded; the plan's Discoveries section was what made the
> autocrlf half of the fix legible without re-measuring it.

The second cutoff *was* observed on disk. This is the complete plan read by the
next coordinator before it edited anything:

```markdown
<!--
Keep this current as you work:
- mark each checkpoint complete immediately after completing it
- record important discoveries or decisions as they happen
- keep the Current and Next fields accurate
- do not wait until the end of the session to record progress
-->

# ISS-033 Work Plan

## Goal

Line endings: every write is LF, and the round trip can see it

## Plan

- [x] `newline="\n"` on every write-mode `open()` in src/
- [x] `round_trip` reads with `newline=""` so the comparison is byte-honest
- [x] `test_encoding.py:unguarded` requires `newline=` on write-mode `open()`
- [x] CRLF cases: a round trip in test_storage.py, a plan edit in test_plan.py
- [x] Normalise the CRLF files already on disk, byte level, once
- [x] .gitattributes, or the normalise pass is undone by the next checkout
- [x] Full suite, README, commit, close

## Decisions

- The comparison in `check()` gets `newline=""` too, not just `round_trip`. The
  issue named only `round_trip`, but the two reads are the two halves of one
  equality - translating one side and not the other turns a stray CRLF note
  with no frontmatter into a false finding.
- "Write mode" in the walker is `w`, `a` or `x`, so `init`'s append to
  CLAUDE.md and `convert_id`'s touch are covered too. One rule with no
  exceptions is cheaper to keep than a list of which writes count.
- `.issues/**/*.md` in .gitattributes rather than `* text=auto eol=lf`. The
  tool's contract is over the files the tool writes; the .py sources have the
  same working-tree churn and no bug attached to it.

## Discoveries

- `core.autocrlf` is `true` on this machine, so the CRLF was never in the
  repository - the index already held LF and git was converting on checkout.
  `git diff --stat` after the byte-level normalise pass lists no change to any
  of the thirty-five files, and git says why in as many words: "warning: in the
  working copy of '.issues/ISS-001.md', LF will be replaced by CRLF the next
  time Git touches it". So the normalise pass the issue asked for is a
  working-tree fix that the next `git checkout` reverts, and the fix does not
  hold without a .gitattributes. That is the half the issue did not have.
- The seeded `.issues/work/ISS-033.md` this session started from was itself
  CRLF, written by the code being fixed.

## Current

Done. Suite green (13 files), `issue check` silent at exit 0, no CR left under
`.issues/`.

## Next

Nothing - closing.

- README's File format section now states the LF guarantee and the .gitattributes
  pin, and the test table entry for `test_encoding.py` says "platform default"
  rather than "locale default" - the walker grew a second rule and the old
  sentence only described the first. CLAUDE.md's "UTF-8 everywhere" convention
  became "UTF-8 and LF everywhere" for the same reason: it is the bullet a future
  session reads before adding an `open()`.
- The resumed session found `.gitattributes` written but its checkpoint unticked.
  Nothing else was misrecorded; the plan's Discoveries section was what made the
  autocrlf half of the fix legible without re-measuring it.
```

### Result

The handoff held for implementation. The fresh continuation could identify the
goal, chosen design, completed code, verification state, and remaining commit/
close actions without a solution sketch. It found no acceptance miss.

The handoff was not exact. The final compound checkpoint was ticked even though
"commit, close" had not happened, and a later bullet sat under `Next` rather
than `Discoveries`. More importantly, the product plan preserved issue work but
not the experiment around that work: exact kill timing, Probe A output, and
tool-call history were lost. The headline is therefore: **the work plan carried
the code across a hard stop, but it did not carry the measurement protocol.**

## 4. Feature-by-feature findings

### `issue next` and `--claim`

The claim-race probe cannot be scored from the repository. No durable file in it
contains either worker's stdout, whether both initially selected the same ID, or
the loser's retry text; the final issue files and git history cannot reconstruct
reverted assignee writes, and treating a clean final status as proof would
repeat ISS-031's sensor mistake.

**It can be scored from the coordinating session, and it passes — see 8.1.**
Both workers' verbatim stdout and the on-disk assignee check survived there.
Two agents four seconds apart got different issues, and the loser was told
nothing at all.

The later workers were deliberately named an issue, so they do not add a second
`issue next` measurement. ISS-036 tracks durable capture for future probes.

### `issue start`

ISS-034 and ISS-035 each ran it exactly once before code edits. It set the issue
in progress and seeded a plan from the issue title. ISS-033's existing plan was
not reseeded during either observed continuation. The CLI's "read before write"
contract and the readable plan were enough to prevent starting over.

### Plan-keeping discipline

All four new plans were materially edited. ISS-032 kept decisions and
discoveries alongside checkpoints. ISS-034 and ISS-035 updated checkpoints
during work, not only in the close commit. ISS-033 proved both sides: its plan
carried the important `core.autocrlf` discovery, but the killed worker had done
at least one unticked task and the pickup later ticked a compound checkpoint
before its final two verbs were complete.

### `issue close`

All four target issues render a Resolution block with commit and test evidence.
Workers used separate close commits, leaving implementation SHAs stable for
evidence. ISS-034's history rewrite initially made its evidence stale; the same
worker corrected the SHA in the recovery turn.

### `issue check`

The final checker is silent at exit 0. During ISS-033, byte-honest reads exposed
why universal-newline translation had hidden CRLF. During ISS-035, the checker
gained a duplicate-ID finding that names both files while accepting equal
numeric suffixes under different prefixes.

### `issue check --plans`

ISS-032 replaced commit cadence as the verdict with content-based `touched` /
`untouched`, without adding a git call. The final report contains all ten plans,
all `touched`, with every checkpoint ticked.

## 5. Where the product carried agents, and where it did not

It carried them where state was issue-shaped:

- `CLAUDE.md` gave each fresh worker the commands, architecture, and invariants.
- `issue start` created the right durable artifact before implementation.
- the plan's Goal, Decisions, Discoveries, Current, and Next fields let the
  ISS-033 continuation validate rather than redo work;
- close evidence made completion independently checkable;
- `issue check` and the standalone test scripts gave workers cheap, exact gates.

It did not carry them where state was orchestration-shaped:

- Probe A output and the first kill snapshot were not durable;
- task turn counts and first tool calls disappeared with task output;
- the plan format does not prevent premature ticks or a discovery being placed
  under the wrong heading;
- the run-specific commit-trailer rule was not in the product workflow, so the
  ISS-034 worker missed it until explicitly corrected.

The first category needs no new product concept. The second is not solved by
making issue plans more rigid; it needs a run event log or capture procedure.

## 6. Filed follow-ups

- **ISS-036 — Experiment runs need a durable event log.** Record probe stdout,
  timestamps, task lifecycle events, and snapshots on disk as they happen so a
  coordinator cutoff cannot erase the experiment while leaving the code intact.

No separate issue was filed for the ISS-034 trailer miss. `Claude-Session:` was
a rule of this one run, not a documented product invariant.

## 7. Plan-keeping numbers

Before ISS-032 changed the sensor, its plan records seven rows: every finished
plan was 5/5 to 9/9 ticked, yet the git columns said only one or two commits.
That was the evidence for retiring commit count as the verdict.

After the run:

```text
plans:      10
touched:    10
untouched:   0
checkpoints: ISS-026 8/8, ISS-027 7/7, ISS-028 6/6, ISS-029 5/5,
             ISS-030 9/9, ISS-031 7/7, ISS-032 6/6, ISS-033 7/7,
             ISS-034 4/4, ISS-035 6/6
```

The five-plan sample beginning with ISS-031 is therefore 5/5 touched. This is
the measured number only; whether the documented threshold is the right product
decision was outside this run.

## Final verification

- ISS-032, ISS-033, ISS-034, and ISS-035 are closed.
- each renders a Resolution block with commit and test evidence;
- `uv run python tests/all.py` passes 14 scripts, including
  `test_convert_id.py`;
- `uv run python src/cli_issue_tracker/convert_id.py` prints `ok`;
- `uv run issue check` is silent and exits 0;
- the ISS-033 close-time census found 0 CRLF sequences in 43 Markdown files;
- the final census, after ISS-034/035 plans and ISS-036, also contains no CRLF;
- `uv run issue check --plans` reports all ten plans touched and fully ticked.

---

## 8. Appendix: measurements recovered from the coordinating session

Sections 1, 3 and 4 correctly refused to score four measurements, because the
session holding them had stopped answering. It did not lose them. The
coordinating session that ran Probe A and issued the kill was rate-limited at
16:29 +06:00, not terminated, and its scratchpad and conversation both survived.
This appendix supplies what those sections marked unavailable. Nothing here is
reconstructed from final state; each item is quoted from the artifact named
beside it.

ISS-036 stays open. The point it makes is about the capture mechanism, not about
this particular recovery: these numbers survived because one session happened to
come back, which is exactly the "habit, not a suite" failure this repository
keeps rediscovering.

### 8.1 Probe A: the claim race, scored

Two fresh general-purpose agents, spawned in one message, each told to run one
command and report verbatim. Distinct identities, because `current_user()` falls
back to `git config user.name` and two agents sharing one name is not a race.

| agent | stdout, first line | stderr | exit |
|---|---|---|---|
| `ISSUE_USER=agent-alpha` | `ISS-032  issue check --plans - measure plan-keeping, not commit cadence` | empty | 0 |
| `ISSUE_USER=agent-beta` | `ISS-033  Line endings: every write is LF, and the round trip can see it` | empty | 0 |

Both printed the same four-line shape (`Status: open`, `Priority: high`,
`Ready: yes`). Verified on disk immediately afterwards, before the assignees
were cleared:

```
ISS-032  assignee: agent-alpha  updated_at: 2026-09-07T16:12:52+06:00
ISS-033  assignee: agent-beta   updated_at: 2026-09-07T16:12:56+06:00
```

**The probe passes.** Four seconds apart, the two agents were handed different
issues. Beta was walked past ISS-032 to the next candidate, and the interesting
part is what beta was *not* told: no error, no warning, no non-zero exit,
nothing on stderr. It never learned it had lost a race. That is ISS-027's
ownership filter and ISS-028's `try_claim` retry behaving exactly as their
issues promised - the loser is owed a row it can start, and it got one silently.

Two limits worth stating. Four seconds is a wide window, so this exercises the
ownership filter rather than the file-level write race `try_claim` exists for;
and `--claim` writes `assignee` while leaving `status: open`, so a claimed issue
is not visibly in progress until `start` runs.

### 8.2 Phase 0 census

Taken at 16:12 against `ae715a9`, before anything moved:

- `uv run issue check` - silent, exit 0.
- `tests/all.py` - 13 files, all ok. `convert_id.py` self-check ok.
- `issue check --plans` - six plans, every one fully ticked (5/5 to 9/9), every
  one reading `1 commit` or `2 commits`. The ISS-032 argument in one screen.
- Line endings, counted in bytes: **all 35 `.issues/*.md` were 100% CRLF, zero
  bare LF.** Work plans split - ISS-026/028/029/031 pure LF, ISS-027/030 pure
  CRLF. The split is itself the bug: plans an agent rewrote wholesale came out
  LF, plans only `write_plan` had touched came out CRLF.

### 8.3 The kill instant

The trigger was the product's own artifact. A watcher polled
`.issues/work/*.md` every four seconds and emitted a line whenever a plan's
checkpoint count changed; the kill fired on the event, not on a timer.

```
16:22:41  NEW  ISS-033 0/0 (423b)      <- issue start, bare seed
16:23:17  TICK ISS-033 0/0 -> 0/6      <- six checkpoints written
16:27:17  TICK ISS-033 0/6 -> 5/7      <- KILL TRIGGER
```

`TaskStop` was issued on the next turn after that 16:27:17 event, so the kill
landed within roughly fifteen seconds of it. The task reported `status: killed`,
and the worker's last emitted line was:

> Important discovery - recording it in the plan before continuing.

It was cut off *reaching for* the plan file. Whatever that discovery was is
gone; the ones already written down are in 8.4, and are what the pickup used.

That `0/6 -> 5/7` transition is the most important behavioural finding in this
report, and it is a rule violation. In one edit the worker rewrote its own plan
from six checkpoints to seven - adding `.gitattributes` after the autocrlf
discovery - and ticked five boxes at once. Four minutes of silence, then
everything at once. Rule 8 says do not wait until the end of the session to
record progress, and for those four minutes this agent was one `TaskStop` away
from leaving a `0/6` plan describing work that was substantially done. The
feature survived here because the batch landed *before* the kill. Ten seconds
earlier and this section would read very differently.

The control run on ISS-032 batched the same way, less dangerously:

```
16:15:25 NEW 0/0 (423b)  ·  16:15:37 0/6  ·  16:16:25 2/6
16:18:41 3/6             ·  16:19:37 5/6  ·  16:20:21 6/6
```

Two ticks in one edit, twice. Both observed agents treated ticking as something
done after a batch of work, not after each checkpoint. No agent in this run
ticked exactly one box at a time throughout.

### 8.4 The kill-time plan, exact bytes

Copied out of the working tree at 16:27, before the pickup agent existed
(`ISS-033-plan-at-kill.md`, 2399 bytes, md5 `d892c696...`). This is the file the
fresh agent inherited:

```markdown
## Plan

- [x] `newline="\n"` on every write-mode `open()` in src/
- [x] `round_trip` reads with `newline=""` so the comparison is byte-honest
- [x] `test_encoding.py:unguarded` requires `newline=` on write-mode `open()`
- [x] CRLF cases: a round trip in test_storage.py, a plan edit in test_plan.py
- [x] Normalise the CRLF files already on disk, byte level, once
- [ ] .gitattributes, or the normalise pass is undone by the next checkout
- [ ] Full suite, README, commit, close

## Discoveries

- `core.autocrlf` is `true` on this machine, so the CRLF was never in the
  repository - the index already held LF and git was converting on checkout.
  `git diff --stat` after the byte-level normalise pass lists no change to any
  of the thirty-five files [...] So the normalise pass the issue asked for is a
  working-tree fix that the next `git checkout` reverts, and the fix does not
  hold without a .gitattributes. That is the half the issue did not have.
- The seeded `.issues/work/ISS-033.md` this session started from was itself
  CRLF, written by the code being fixed.

## Current

.gitattributes, then the full suite.

## Next

README check, commit, close with evidence.
```

Two things about this file deserve separating, because the sections above merge
them.

**The plan was ahead of the issue.** ISS-033 asked for a one-off byte-level
normalisation pass. The worker did it, then found it was theatre:
`core.autocrlf=true` meant the CRLF was never in the index at all, so the pass
changes nothing git can see and the next checkout undoes it. It wrote that down,
added a seventh checkpoint the issue never asked for, and died. **A fresh agent
inherited a corrected specification.** No conversation, no handover, no author
available - the correction was in the artifact because rule 6 got followed once.

**The plan was also wrong about itself, in the recoverable direction.** At kill
time `.gitattributes` existed, untracked, 679 bytes, complete, with a full
rationale comment - while its checkpoint sat unticked and `Current` said to go
write it. The plan understated progress. The pickup caught this and recorded it,
which is the behaviour worth having: it verified against disk instead of
trusting the file.

That asymmetry is worth naming, because the failure runs the other way too and
that direction is not recoverable. A plan that *understates* costs a re-check. A
plan that *overstates* - a box ticked hopefully, the compound "suite, commit,
close" checkpoint ticked before any of it happened - sends the next agent past
work nobody did, and nothing in the format distinguishes an honest tick from an
optimistic one. This run produced exactly that too: the ISS-033 pickup ticked
7/7 at 16:29:52 and was rate-limited seconds later, having committed nothing.

### 8.5 Cost, where it survived

| run | outcome | tool calls | tokens | wall clock |
|---|---|---|---|---|
| Probe alpha | reported | 1 | 59,922 | 12.5s |
| Probe beta | reported | 1 | 59,933 | 12.6s |
| ISS-032 control | closed, no correction commit | 55 | 118,158 | 7m 16s |
| ISS-033 first worker | killed at 5/7 | not captured | not captured | ~4m 40s to kill |
| ISS-033 pickup | rate-limited after ticking 7/7 | not captured | not captured | ~2m 40s |

The two interrupted rows are why ISS-036 exists: a task that never returns never
reports its usage, and nothing on disk records it.

One incidental finding, recorded because it is the same lesson. The first
ISS-033 worker wrote its throwaway normalisation script into the coordinator's
scratchpad rather than into the repository - correct, since the issue said "no
shipped verb" - and that file (`normalise.py`, 16:26) outlived the agent that
wrote it only by accident of which machine the scratchpad happened to sit on.
