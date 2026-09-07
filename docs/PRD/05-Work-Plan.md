# PRD: Work Plan

Supersedes `04-Session-Handover.md`.

## Introduction

Replace the session handover with a **live work plan**: a mutable execution
record created before work begins and updated continuously while the agent
works.

Handover assumed a session has an end that somebody notices. It does not. The
common ending is a usage limit, a crash, a closed terminal — the session stops
mid-edit and nobody writes anything, because writing was a separate deliberate
act scheduled for a moment that never arrived. The evidence is on disk: this
repo shipped `issue handover` and then produced twenty-five issues and zero
handovers.

The fix is not a better prompt to remember. It is to stop treating the record
as an ending, and make it the thing the work already runs on.

```text
Issue       what needs to be achieved
Work plan   how this session is currently achieving it
Git         what actually changed
```

The plan is written before the first edit, ticked as each checkpoint lands, and
therefore always within one checkpoint of the truth. If the agent disappears
between two ticks, the loss is one checkpoint — not one session.

---

# Product Principle

The issue is the durable definition of the work and is edited rarely.

The work plan is the mutable execution state and is edited constantly.

They must not become the same thing. An agent whose approach evolves must never
be rewriting the original issue description to record that; that is what the
plan is for.

```text
Issue                    Work plan
  ↓                        ↓
Problem                  Goal
Acceptance Criteria      Plan (checkpoints)
Dependencies             Decisions
Implementation Context   Discoveries
                         Current
                         Next
```

A finished plan is not garbage. It is the account of how the issue was actually
implemented, in the order it happened — engineering history the repository keeps
for free.

---

## Why not `--resume`

Claude Code can reopen a cut-off session. That is not the workflow this targets,
for three reasons and one that matters most:

* A resumed session resumes a context that has already been compacted. The
  detail worth keeping was evicted before the cutoff, not by it.
* A resumed session resumes an agent that has already crossed out of its smart
  zone. A fresh context reliably produces better work than a long one.
* The next worker may be a different agent, a subagent, or a human. Conversation
  state is private to one CLI process; a repository artifact is not.

So the artifact is not a fallback for a lost conversation. It is the preferred
path, and its quality bar is that of a conversation it deliberately replaces.

---

# Goals

* Record execution state continuously, not at an ending nobody reaches
* Make the record cost nothing at the moment of writing
* Let a fresh agent resume from one command
* Keep the issue free of implementation churn
* Leave a finished issue with a readable account of how it was built
* Keep every artifact plain Markdown, local, and Git-trackable
* Delete more code than is added

---

# User Stories

## US-001: Open work with one command

**Description:** As an agent about to start substantial work, I want one command
that puts the issue into an in-progress state and gives me the plan file to
fill, so recording progress is the path of least resistance rather than an extra
chore.

### Acceptance Criteria

* [ ] Add `issue start <ID>`
* [ ] Referenced issue must exist
* [ ] Sets `status: in-progress`
* [ ] Claims the issue as `ISSUE_USER`
* [ ] Seeds `.issues/work/<ID>.md` when no plan exists
* [ ] All validation happens before any write

```bash
issue start ISS-002
```

---

## US-002: `start` is also the resume path

**Description:** As a resuming agent, I want the same command whether I am
opening work or continuing it, so I never have to know which situation I am in.

### Acceptance Criteria

* [ ] When a plan already exists, `start` prints it and does not overwrite it
* [ ] An existing plan is never clobbered, truncated or reseeded
* [ ] Re-running `start` on already-started work is not an error

The idempotence is the point. An agent that must first determine whether work
exists will sometimes determine it wrongly, and the cost of being wrong is the
plan.

---

## US-003: Starting blocked work is discouraged, not forbidden

**Description:** As a developer, I want to be told an issue is blocked before I
start it, and to be able to start it anyway when I have judged that the blocker
does not stop this particular work.

### Acceptance Criteria

* [ ] `start` refuses an issue `in_the_way()` reports as blocked
* [ ] Refusal exits 1, names the open blockers on stderr, and writes nothing
* [ ] `--anyway` proceeds
* [ ] When `--anyway` is used, the blockers are noted in the seeded plan header
* [ ] `in_the_way()` remains the only function that decides what blocked means

---

## US-004: The CLI seeds, the agent edits

**Description:** As an agent, I want to update the plan with the editing tools I
already hold, so a checkpoint costs one edit rather than a command invocation I
must remember to make.

### Acceptance Criteria

* [ ] `issue start` writes the plan skeleton
* [ ] No CLI command mutates the plan after that
* [ ] The plan is plain Markdown, editable by hand or by tool
* [ ] The CLI reads the plan and never rewrites it

The rejected alternative was a verb per mutation — `plan check 3`,
`plan note "..."`, `plan next "..."`. Every one of those is a shell round trip
mid-flow, which is a decision point, which is a place to skip. Ticking a box
must be cheaper than not ticking it or it will not happen. The cost is that
nothing enforces the file's shape, which US-006 answers by refusing to need it
enforced.

---

## US-005: The plan has a known shape

**Description:** As a reader of a plan I did not write, I want a predictable
structure so I can find the state of work without reading prose end to end.

### Acceptance Criteria

Sections:

```text
## Goal          one line: what this issue is
## Plan          - [ ] / - [x] checkpoints
## Decisions     what we intentionally chose
## Discoveries   what we learned
## Current       what is being worked on right now
## Next          the nearest concrete continuation point
```

* [ ] Checkpoints are `- [ ]` / `- [x]` bullets under `## Plan`
* [ ] Checkpoints represent recoverable units of progress, not keystrokes
* [ ] `Decisions` and `Discoveries` stay distinct — chose versus learned
* [ ] `Current` and `Next` are prose, one to three lines

A checkpoint is `Login UI`, not `Open auth.py`, `Add import`, `Save file`. The
rule of thumb is three to ten per issue; forty is noise and an agent will
correctly stop maintaining noise. This is guidance in the workflow rule, not a
validated constraint — a tool that rejects an eleventh checkpoint would be
wrong about a large issue.

---

## US-006: The reader tolerates drift

**Description:** As a maintainer, I want an agent editing the plan freely to be
unable to break the tools that read it.

### Acceptance Criteria

* [ ] Known headings are recognised; unknown headings are preserved and ignored
* [ ] A missing section is absent, not empty and not defaulted
* [ ] Reading a plan never raises
* [ ] A file with no recognised section produces a stderr note, not a failure
* [ ] The body reader is the one already written for handovers, moved down a
      layer

Absent means absent, the same call `priority_of` already makes.

---

## US-007: "Keep working" resolves to one command

**Description:** As a user returning after a cut-off session, I want to say
"keep working" and have the agent land on the right issue at the right place
without me naming either.

### Acceptance Criteria

* [ ] `issue next` output includes the chosen issue's plan state
* [ ] Shown: `Current`, `Next`, and unchecked checkpoints
* [ ] `--json` exposes the plan structurally
* [ ] `next` remains read-only — asking does not claim, assign or start
* [ ] Ordering is unchanged

`next_rank` already sorts `in-progress` above `open` and breaks every tie down
to the id, so `next` already names the correct issue deterministically. It
simply does not yet say what was happening there. Nothing about the ordering
changes.

---

## US-008: Resume output includes live Git state

**Description:** As a resuming agent, I want the plan's account of intent and
the repository's account of reality in the same output.

### Acceptance Criteria

* [ ] `issue next` shows current branch, HEAD and uncommitted file paths
* [ ] Git state is computed at read time and never stored in the plan
* [ ] Git inspection stays read-only
* [ ] Git failure costs the Git block, not the output
* [ ] File paths only; never diffs

The handover stored Git state because a handover was immutable and a stored fact
could not go stale. The plan is live, so the opposite is true: a stored HEAD
would be a lie the moment anything committed, and recomputing is now the correct
choice rather than the wrong one.

---

## US-009: `issue view` surfaces the plan

**Description:** As someone inspecting an issue I am not working on, I want to
see where its work stands without starting it.

### Acceptance Criteria

* [ ] `issue view <ID>` shows a compact plan block when a plan exists
* [ ] Shown: `Goal`, `Current`, `Next`, and checked/total counts
* [ ] No plan block appears when no plan exists
* [ ] The block replaces the handover line `view` shows today
* [ ] `--json` may expose the plan

`start` mutates status, so it cannot be the way to read a stranger's plan.
`view` can, and the full file is one `cat` away by design.

---

## US-010: Closing warns about unfinished checkpoints

**Description:** As a maintainer, I want to know when an issue is being closed
with plan items still open, without that fact being able to block a legitimate
close.

### Acceptance Criteria

* [ ] `issue close` proceeds regardless of unchecked checkpoints
* [ ] Unchecked checkpoints produce a stderr warning naming them
* [ ] stdout stays parseable
* [ ] The plan file is not moved, archived or rewritten on close
* [ ] Evidence requirements are unchanged

A checkpoint that stopped being relevant mid-work must not be able to veto a
close, and the acceptance criteria already own the question of completeness.
The warning exists so the divergence is visible, not so it is enforced.

---

## US-011: The finished plan is the history

**Description:** As a developer reading a closed issue months later, I want to
know how it was actually built.

### Acceptance Criteria

* [ ] Plans persist after close, in place
* [ ] No archive directory, no second format, no promotion step
* [ ] Git history records how the plan evolved

The plan was going to be deleted or copied somewhere on close. Both are work
that buys nothing: the file is already Markdown, already in Git, already named
after the issue.

---

## US-012: The workflow rule reaches the agent twice

**Description:** As an agent in a repository that uses this tool, I want the
working rule available both as a project instruction and at the moment I am
editing the plan.

### Acceptance Criteria

* [ ] `issue init` writes the workflow rule into `CLAUDE.md` / `AGENTS.md`
* [ ] The seeded plan carries a condensed reminder as an HTML comment
* [ ] Both renderings come from one constant in the source
* [ ] The rule is visible in the plan file itself, not only in project docs

The rule:

```text
When starting substantial work on an issue:

1. Read the issue and any existing active work plan.
2. If an unfinished plan exists, continue it instead of creating a new one.
3. Otherwise create a work plan before modifying code.
4. Break the work into meaningful checkpoints.
5. Mark each checkpoint complete immediately after completing it.
6. Record important discoveries or decisions as they happen.
7. Keep the Current and Next fields accurate.
8. Do not wait until the end of the session to record progress.
9. Close the issue only when the plan and acceptance criteria are complete.
```

Line 8 is the behavioural guarantee the whole feature rests on. It lives in the
plan file because a rule at the top of `CLAUDE.md` is the first thing a long
session compacts away, and the plan file is on disk and re-read every time the
agent touches it.

---

## US-013: Handover is removed

**Description:** As a maintainer, I want one execution artifact rather than two
overlapping ones.

### Acceptance Criteria

* [ ] `issue handover create` / `latest` / `list` / `view` are removed
* [ ] `handover.py` is removed
* [ ] `tests/test_handover.py` is removed
* [ ] The README handover section is replaced by the work plan
* [ ] `split_sections` / `join_sections` / `git_context` move down a layer and
      keep their tests
* [ ] `04-Session-Handover.md` remains in `docs/PRD/` as the record of the
      superseded shape
* [ ] No migration is needed — no handover has ever been written

`issue view`'s handover line becomes the plan block. Nothing else referenced
handovers.

---

# Functional Requirements

## Commands

* FR-1: Add `issue start <ID>` with `--anyway`
* FR-2: `start` validates fully before writing anything
* FR-3: `start` is idempotent: seed if absent, print if present
* FR-4: Extend `issue next` with plan state and live Git state
* FR-5: Extend `issue view` with a compact plan block
* FR-6: Extend `issue close` with an unchecked-checkpoint warning
* FR-7: Remove the four `handover` verbs
* FR-8: `start` is the only command added

## Storage

* FR-9: Plans live at `.issues/work/<ISSUE-ID>.md`
* FR-10: One plan per issue
* FR-11: `work/` is created on demand, not by `init`
* FR-12: Plans are plain Markdown with no frontmatter requirement
* FR-13: Plans are mutable and are never rewritten by the CLI after seeding

## Reading

* FR-14: The plan reader never raises
* FR-15: Unknown sections are preserved
* FR-16: Missing sections are absent
* FR-17: Git state is recomputed at read time, never stored
* FR-18: `--json` exposes plan structure wherever a plan is shown

---

# Storage Model

```text
.issues/
├── ISS-001.md          durable definition
├── ISS-002.md
└── work/
    └── ISS-002.md      mutable execution state
```

A seeded plan:

```markdown
<!--
Keep this current as you work:
- tick each checkpoint the moment it lands
- record decisions and discoveries when they happen, not later
- keep Current and Next accurate
- never wait until the end of the session
-->

# ISS-002 Work Plan

## Goal

Login and signup with persistent authentication state.

## Plan

## Decisions

## Discoveries

## Current

## Next
```

The same plan mid-session:

```markdown
## Plan

- [x] Inspect existing auth architecture
- [x] Build login page UI
- [x] Build signup page UI
- [x] Create user database schema
- [x] Implement signup async function
- [x] Implement login async function
- [ ] Connect authentication state to application
- [ ] Add logout flow
- [ ] Handle invalid credentials
- [ ] Add tests

## Decisions

- Authentication state lives in `AuthProvider`.
- Session persistence uses the existing backend session mechanism.

## Discoveries

- The router already has protected-route support.
- The signup API returns the user object directly.

## Current

Connecting successful login to `AuthProvider`.

## Next

Wire the login result into `AuthProvider`, then handle the failure branch.
```

---

# Proposed Human Output

`issue next`:

```text
ISS-002  high  Login and signup with state
in-progress · tahmid

PLAN  6/10
- [ ] Connect authentication state to application
- [ ] Add logout flow
- [ ] Handle invalid credentials
- [ ] Add tests

CURRENT
Connecting successful login to AuthProvider.

NEXT
Wire the login result into AuthProvider, then handle the failure branch.

GIT
feature/auth @ 81af03c · uncommitted
src/auth/provider.ts
src/pages/login.tsx
```

`issue view ISS-002`:

```text
Work plan: 6/10 checkpoints
Current: Connecting successful login to AuthProvider.
Next:    Wire the login result into AuthProvider.
```

---

# Lifecycle

```text
issue start ISS-002
      ↓
agent writes checkpoints
      ↓
work → tick → work → tick
      ↓
session ends without warning        X
      ↓
new session: "keep working"
      ↓
issue next  →  plan + git in one command
      ↓
work continues from the last tick
      ↓
issue close  →  plan stays as the build history
```

---

# Non-Goals

* No hooks, no transcript reading, no session ids
* No Claude- or Codex-specific code in the tracker
* No CLI verbs that mutate the plan
* No enforced checkpoint count
* No blocking close on unchecked checkpoints
* No archive directory or promotion step
* No stored Git state
* No plan frontmatter, no id allocation for plans
* No second artifact alongside the plan
* No automatic status changes beyond `start`
* No editing the issue to record implementation churn

---

# Known Risks

Recorded because they are real, not because they are solved.

**Nothing enforces any of this.** A seeded plan that is never ticked is worse
than no plan: it is confidently stale and the resuming agent trusts it. The
behavioural guarantee is one sentence in a file. The last such guarantee
produced zero handovers across twenty-five issues. What changes the odds here is
that the plan is created before the work rather than after it, is edited with
the tool the agent is already holding, and carries its own instructions — but
the guarantee is still a sentence, and if it fails again the next move is a hook,
not a stronger sentence.

**Close only warns.** Nothing ever forces reconciliation between the plan and
what shipped. A closed issue may leave four unchecked checkpoints that were done
but never ticked, and the history is wrong in the direction that looks like
abandoned work.

**A shipped feature is being deleted six commits after it landed.** ISS-024 and
ISS-025 stay closed and their evidence stays true; the deletion is a reversal
recorded as its own issue, not a retraction of theirs.

---

# The Threshold

Written down before the result is known, because the previous answer to "is
this artifact alive?" was a habit, and a habit is what produced zero handovers
across twenty-five issues.

**After the next five issues worked through `issue start`: if fewer than three
of those five plans report as `touched`, the work plan is deleted the way the
handover was, and this document records why.**

`issue check --plans` is the instrument. A plan is `untouched` when it is still
exactly what `start` seeded — no checkpoints, and nothing written in
`Decisions`, `Discoveries`, `Current` or `Next`. `Goal` does not count, because
the CLI writes it from the issue title. Anything else at all is somebody having
come back to the file, which is the behaviour the whole feature rests on.

```text
ISS-026  touched    1 commit   last touched 11 commits ago  8/8 ticked
ISS-032  untouched  0 commits  not committed                0/0 ticked
```

Baseline the day this was written: six plans on disk, all six `touched`, 5/5 to
9/9 ticked.

## Why the commit count was retired

ISS-031 wrote this threshold first and pointed it at `git log --follow` on the
plan: a plan with exactly one commit was seeded and never touched again. Its
own Discoveries then recorded why that cannot answer the question. The count
measures the committer, not the writer. This workflow commits the plan edits
together at the end of the work, so all six kept plans read `1 commit` or
`2 commits` while every one of them was in fact edited a dozen times — and a
kill switch wired to that sensor would have deleted a feature that works.

The replacement reads content instead of history, which also means it survives
the two things history does not: a fresh clone has no mtimes, and a squashed
branch has no per-file commit count.

The two Git columns stay. They are not wrong, they are insufficient — a plan
that is `touched` but last committed nineteen commits ago is still worth
looking at. They are context now rather than verdict.

---

# Success Criteria

The feature succeeds when a cut-off session costs one checkpoint instead of one
session: the user says "keep working", the agent runs one command, and gets the
issue, what is done, what remains, what was decided, what was learned, where the
work stands, what to do next, and which files are dirty — without reading a
conversation that no longer exists and without being asked to write anything at
the end.
