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
so its exact bytes cannot be recovered. The durable plan says what the pickup
found:

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

The claim-race probe cannot be scored. No durable file contains either worker's
stdout, whether both initially selected the same ID, or the loser's retry text.
The final issue files and git history cannot reconstruct reverted assignee
writes. Treating a clean final status as proof would repeat ISS-031's sensor
mistake.

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
