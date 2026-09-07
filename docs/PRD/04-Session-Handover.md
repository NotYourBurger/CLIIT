# PRD: Session Handover

## Introduction

Add durable **session handovers** so a human or AI agent can stop work and another session can continue without reconstructing the previous conversation.

A coding session often ends before an issue is complete.

The agent may have:

* implemented half of the solution
* discovered important constraints
* made architectural decisions
* changed several files
* run some tests but not others
* found a blocker
* identified the exact next function to modify

Today, most of that information exists only in the chat context.

When the session ends, that context disappears.

The next agent sees:

```text
ISS-042
status: in-progress
```

but does not know:

> What has already been done?

> What remains?

> What was discovered?

> Where should I continue?

Session handover turns that temporary working context into a durable repository artifact.

```bash
issue handover create ISS-042
```

The handover represents:

> **The smallest useful packet of information another session needs to continue this work safely.**

---

# Product Principle

Issues describe **what the work is**.

Handovers describe **where the work currently stands**.

They must not become the same thing.

```text
Issue
  ↓
Problem
Acceptance Criteria
Dependencies
Implementation Context

Session Handover
  ↓
What changed this session
What was discovered
What remains
Where to continue
```

The issue remains the durable definition of the work.

The handover is an append-only checkpoint in its execution history.

---

# Goals

* Preserve implementation context across AI sessions
* Allow a new agent to resume work without reading the previous chat
* Capture only information expensive to reconstruct
* Tie handovers directly to relevant issues
* Preserve important decisions and discoveries
* Record the exact next action whenever possible
* Capture useful Git state automatically
* Keep handovers compact and AI-readable
* Support multiple handovers throughout a long-running issue
* Make handovers available to future `issue brief` and `issue context`
* Remain entirely local-first and Git-trackable

---

# User Stories

## US-001: Create a handover for active work

**Description:** As a developer or coding agent ending a session, I want to record the current implementation state so another session can continue from where I stopped.

### Acceptance Criteria

* [ ] Add `issue handover create <ID>`
* [ ] Referenced issue must exist
* [ ] Handover does not change issue status
* [ ] Handover is stored as a durable repository artifact
* [ ] Handover records its creation timestamp
* [ ] Multiple handovers may exist for the same issue
* [ ] Existing handovers are never overwritten when a new one is created

Example:

```bash
issue handover create ISS-042 \
  --summary "Cycle detection is implemented; CLI error handling remains." \
  --next "Update set_issue() error rendering and run blocker tests."
```

---

## US-002: Require a concise session summary

**Description:** As the next agent, I want a concise explanation of what happened during the previous session so I don't need its conversation history.

### Acceptance Criteria

* [ ] Every handover requires a summary
* [ ] Blank summaries are rejected
* [ ] Summary describes the state of work, not the original issue
* [ ] Summary remains available in human and JSON output

Example:

```text
Implemented cycle detection before dependency writes.
Added regression coverage for direct and transitive cycles.
CLI error rendering is not finished.
```

---

## US-003: Record the exact next action

**Description:** As a new agent, I want to know where to continue so I can begin useful work immediately.

### Acceptance Criteria

* [ ] Every handover requires a `next` action
* [ ] `next` cannot be blank
* [ ] The next action should describe the nearest concrete continuation point
* [ ] Next action appears prominently when viewing a handover

Example:

```text
NEXT
Update render_set_error() in src/issues.py to include the cycle path,
then run tests/test_blockers.py.
```

The goal is to avoid vague handovers such as:

```text
Continue working on the issue.
```

---

## US-004: Record completed work

**Description:** As the next agent, I want to know what has already been completed so I don't repeat work.

### Acceptance Criteria

* [ ] Support repeatable `--done`
* [ ] Completed items are stored structurally
* [ ] Multiple completed items are allowed
* [ ] Completed items appear in human and JSON output

Example:

```bash
issue handover create ISS-042 \
  --summary "Core dependency validation is working." \
  --done "Added DFS cycle detection" \
  --done "Added missing blocker handling" \
  --next "Improve CLI cycle error output"
```

---

## US-005: Record remaining work

**Description:** As a future agent, I want explicit remaining work so partial implementation is not mistaken for completion.

### Acceptance Criteria

* [ ] Support repeatable `--remaining`
* [ ] Remaining items are stored structurally
* [ ] Remaining work is clearly separated from completed work
* [ ] Empty remaining work is allowed

Example:

```text
REMAINING

- Improve CLI error
- Add JSON error coverage
- Run full test suite
```

---

## US-006: Record discoveries

**Description:** As a coding agent, I want to preserve important facts discovered while working so future sessions do not rediscover them.

### Acceptance Criteria

* [ ] Support repeatable `--discovered`
* [ ] Discoveries are preserved verbatim
* [ ] Discoveries appear separately from implementation progress
* [ ] Discoveries are available through JSON output

Example:

```text
DISCOVERED

- blocked_by is parsed before issue validation
- read_issue() preserves unknown frontmatter
- missing blockers intentionally count as ready
```

These are useful working facts, not necessarily permanent architectural decisions.

---

## US-007: Preserve important decisions

**Description:** As a future developer or agent, I want implementation decisions made during a session to survive the conversation that produced them.

### Acceptance Criteria

* [ ] Support repeatable `--decision`
* [ ] Decisions are stored separately from discoveries
* [ ] Decisions appear in handover output
* [ ] Decisions can later be promoted into the future permanent decision-memory system
* [ ] Recording a decision does not automatically modify the issue description

Example:

```text
DECISIONS

- Validate the entire dependency graph before writing either issue.
- Keep missing blockers non-blocking to preserve current tracker semantics.
```

A decision means:

> We intentionally chose this.

A discovery means:

> We learned this.

---

## US-008: Record blockers encountered during the session

**Description:** As a new agent, I want to know what prevented progress so I don't repeat failed attempts.

### Acceptance Criteria

* [ ] Support repeatable `--blocker`
* [ ] Session blockers may contain free-text explanations
* [ ] A session blocker does not automatically create an issue dependency
* [ ] Existing structured issue dependencies remain the canonical dependency graph

Example:

```text
BLOCKERS

- Windows test environment unavailable
- Need decision on legacy closed-issue migration
```

This distinction is important.

```text
blocked_by: ISS-014
```

means a structured project dependency.

A handover blocker may simply mean:

```text
Could not verify this on Windows.
```

---

## US-009: Capture Git position automatically

**Description:** As the next session, I want to know exactly which code state the handover describes.

### Acceptance Criteria

When Git is available, the handover automatically records:

* current branch
* current HEAD commit
* whether the working tree is dirty

Example:

```text
GIT

Branch: feature/evidence-close
HEAD:   81af03c
Dirty:  yes
```

* [ ] Git metadata does not require flags from the user
* [ ] Handovers still work outside a Git repository
* [ ] Git metadata is informational and does not mutate Git state
* [ ] Failure to read Git state does not destroy the handover

---

## US-010: Capture changed file names

**Description:** As a future coding agent, I want to know what files currently contain unfinished work so I can land on relevant code quickly.

### Acceptance Criteria

* [ ] When Git is available, record modified/untracked file paths
* [ ] Store file paths only, not entire diffs
* [ ] Generated output remains bounded
* [ ] Files appear in structured JSON

Example:

```text
FILES

M src/issues.py
M src/storage.py
M tests/test_blockers.py
```

This gives the next agent useful navigation without dumping code into the handover.

---

## US-011: Record an explicit continuation entry point

**Description:** As an AI coding agent, I want the previous session to point me to the most useful code location so I don't need to rescan the repository.

### Acceptance Criteria

* [ ] Support `--resume-at <value>`
* [ ] Value may identify a file, symbol, or both
* [ ] Field is optional
* [ ] Value is stored without requiring language-specific parsing

Example:

```bash
--resume-at "src/issues.py:set_issue"
```

Rendered:

```text
RESUME AT
src/issues.py:set_issue
```

This directly supports the project's context-efficiency vision.

---

## US-012: View the latest handover for an issue

**Description:** As a new session, I want the most recent checkpoint immediately so I can continue current work.

### Acceptance Criteria

Support:

```bash
issue handover latest ISS-042
```

* [ ] Returns exactly one handover
* [ ] Returns the newest handover associated with the issue
* [ ] Ordering uses handover creation timestamp
* [ ] Exit code is `1` when no handover exists
* [ ] Supports `--json`

---

## US-013: View handover history

**Description:** As a developer, I want to inspect previous checkpoints when understanding how implementation evolved.

### Acceptance Criteria

Support:

```bash
issue handover list ISS-042
```

Example:

```text
HANDOVERS FOR ISS-042

H-006  2026-09-07  Core validation implemented
H-004  2026-09-06  Dependency model investigated
H-002  2026-09-06  Initial implementation started
```

* [ ] Newest appears first
* [ ] Each handover has a stable identifier
* [ ] List remains concise
* [ ] Supports JSON output

---

## US-014: View a specific handover

**Description:** As a developer or agent, I want to retrieve an exact checkpoint so historical implementation context remains addressable.

### Acceptance Criteria

Support:

```bash
issue handover view H-006
```

* [ ] Stable handover ID resolves to exactly one handover
* [ ] Full structured handover is displayed
* [ ] Supports `--json`
* [ ] Unknown handover IDs exit with code `1`

---

## US-015: Support handovers involving multiple issues

**Description:** As a coding agent working across related issues in one session, I want one handover to reference all affected work instead of duplicating the same context.

### Acceptance Criteria

Support additional issue references:

```bash
issue handover create ISS-042 ISS-045 ISS-047 ...
```

* [ ] At least one issue is required
* [ ] All referenced issues must exist
* [ ] Handover is discoverable through every referenced issue
* [ ] No handover content is duplicated on disk
* [ ] One issue may be identified as the primary issue

The first ID is the primary issue.

---

## US-016: Keep handovers append-only

**Description:** As a project maintainer, I want historical checkpoints to remain trustworthy instead of silently changing after the session ends.

### Acceptance Criteria

* [ ] Existing handover content cannot be edited through the normal CLI
* [ ] New information creates a new handover
* [ ] Git history naturally records handover creation
* [ ] Handovers may be manually edited as plain files, but the CLI does not present editing as the normal workflow

Handovers represent:

> What this session believed at this point in time.

They are not live documents.

---

## US-017: Make handovers machine-readable

**Description:** As an AI agent, I want structured handover output so I can resume work without parsing presentation-oriented Markdown.

### Acceptance Criteria

`issue handover latest ISS-042 --json` exposes data conceptually like:

```json
{
  "id": "H-006",
  "created_at": "2026-09-07T03:18:00+06:00",
  "issues": ["ISS-042"],
  "summary": "Core dependency validation is implemented.",
  "done": [
    "Added cycle detection",
    "Added regression coverage"
  ],
  "remaining": [
    "Improve CLI error rendering"
  ],
  "decisions": [
    "Validate graph before any write"
  ],
  "discoveries": [
    "Missing blockers intentionally remain non-blocking"
  ],
  "blockers": [],
  "next": "Update cycle error rendering and run blocker tests.",
  "resume_at": "src/issues.py:set_issue",
  "git": {
    "branch": "feature/dependency-validation",
    "head": "81af03c",
    "dirty": true
  },
  "files": [
    "src/issues.py",
    "tests/test_blockers.py"
  ]
}
```

* [ ] Arrays use predictable types
* [ ] Human terminal formatting never appears in JSON
* [ ] Empty optional collections remain predictable
* [ ] Handover IDs remain stable

---

## US-018: Surface handovers through `issue view`

**Description:** As a developer inspecting active work, I want to know that continuation context exists without separately searching for it.

### Acceptance Criteria

For issues with handovers, `issue view` shows a compact reference:

```text
Latest handover: H-006 · 2026-09-07
Core dependency validation implemented.
Next: Improve CLI cycle error rendering.
```

* [ ] Full handover is not embedded into normal issue view
* [ ] Only latest related handover is surfaced
* [ ] No handover section appears when none exists
* [ ] JSON issue output may expose `latest_handover`

---

# Functional Requirements

## Creation

* FR-1: Add `issue handover create`
* FR-2: Require at least one valid issue
* FR-3: Require `summary`
* FR-4: Require `next`
* FR-5: Record `created_at`
* FR-6: Generate a stable handover ID
* FR-7: Handover creation must not mutate issue status

## Structured Context

A handover may contain:

```text
issues
summary
done[]
remaining[]
decisions[]
discoveries[]
blockers[]
next
resume_at
git
files[]
```

---

## Git Context

* FR-8: Capture current branch when available
* FR-9: Capture current HEAD when available
* FR-10: Capture dirty state when available
* FR-11: Capture changed file paths when available
* FR-12: Never store the entire Git diff automatically

---

## Retrieval

* FR-13: Add `issue handover latest <ID>`
* FR-14: Add `issue handover list <ID>`
* FR-15: Add `issue handover view <HANDOVER-ID>`
* FR-16: All retrieval commands support `--json`

---

## Integrity

* FR-17: Handovers are append-only through normal CLI workflows
* FR-18: Referenced issues must exist at creation time
* FR-19: Handover ordering must be deterministic
* FR-20: Failure during validation must not create a partial handover

---

# Proposed CLI UX

## Minimal handover

```bash
issue handover create ISS-042 \
  --summary "Cycle detection works; CLI handling remains." \
  --next "Update error rendering and run blocker tests."
```

---

## Detailed handover

```bash
issue handover create ISS-042 \
  --summary "Core dependency cycle validation is implemented." \
  --done "Added DFS cycle detection" \
  --done "Added cycle regression tests" \
  --remaining "Improve CLI cycle error" \
  --remaining "Run full suite" \
  --decision "Validate graph before performing any writes" \
  --discovered "Missing blockers intentionally remain non-blocking" \
  --resume-at "src/issues.py:set_issue" \
  --next "Update cycle error rendering, then run tests/test_blockers.py"
```

---

# Proposed Human Output

```text
Handover H-006
ISS-042 · 2026-09-07 03:18

SUMMARY
Core dependency cycle validation is implemented.

DONE
- Added DFS cycle detection
- Added regression coverage

REMAINING
- Improve CLI cycle error rendering
- Run full suite

DECISIONS
- Validate the graph before performing any writes.

DISCOVERED
- Missing blockers intentionally remain non-blocking.

RESUME AT
src/issues.py:set_issue

NEXT
Update cycle error rendering, then run tests/test_blockers.py.

GIT
feature/dependency-validation @ 81af03c
Working tree has uncommitted changes.

FILES
src/issues.py
tests/test_blockers.py
```

---

# Storage Model

Handovers should be first-class repository artifacts.

Recommended structure:

```text
.issues/
├── ISS-001.md
├── ISS-002.md
├── ISS-003.md
└── handovers/
    ├── H-001.md
    ├── H-002.md
    └── H-003.md
```

The handover file contains structured metadata plus human-readable content.

Conceptually:

```yaml
---
id: H-006
created_at: 2026-09-07T03:18:00+06:00
issues: ISS-042
git_branch: feature/dependency-validation
git_head: 81af03c
git_dirty: true
files: src/issues.py, tests/test_blockers.py
---

# Session Handover

## Summary

Core dependency cycle validation is implemented.

## Done

- Added DFS cycle detection
- Added regression coverage

## Remaining

- Improve CLI error rendering

## Decisions

- Validate graph before performing any writes.

## Discoveries

- Missing blockers intentionally remain non-blocking.

## Resume At

src/issues.py:set_issue

## Next

Update cycle error rendering and run blocker tests.
```

The exact serialization remains an implementation decision.

The contract is that:

> Handovers must remain plain, Git-trackable, human-readable and structurally parseable without a database or external service.

---

# Relationship to Issues

A handover must not duplicate the entire issue.

Bad handover:

```text
The goal of ISS-042 is to add dependency cycles...
Acceptance criteria...
Priority...
Labels...
```

That information already exists.

Good handover:

```text
Cycle detection is implemented.

The remaining bug is in CLI rendering.

Resume at:
src/issues.py:set_issue

Next:
Fix error output and run blocker tests.
```

The handover stores the **delta generated by the session**.

---

# Relationship to `issue brief`

`issue brief` provides project-level orientation.

When an active issue has a recent handover, the project briefing can eventually surface:

```text
IN PROGRESS

ISS-042  Dependency cycle validation

Latest handover:
Core validation implemented.
Next: Improve CLI error rendering.
```

This means a new session can start with:

```text
issue brief
      ↓
see active issue + latest handover
      ↓
issue handover latest ISS-042
```

without searching historical chats.

---

# Relationship to Future `issue context`

`issue context` should eventually include the latest relevant handover automatically.

The issue context becomes:

```text
Problem
Acceptance Criteria
Dependencies
Relevant Files
Architecture
Decisions
Latest Handover
    ↓
    Done
    Remaining
    Resume At
    Next
```

Therefore:

```bash
issue context ISS-042
```

may eventually be enough to resume implementation in one call.

---

# Relationship to Evidence-Based Closing

Handovers represent incomplete work.

Evidence-based resolution represents completed work.

```text
Session 1
   ↓
handover H-001

Session 2
   ↓
handover H-002

Session 3
   ↓
implementation complete
   ↓
issue close
   ↓
resolution + evidence
```

Once an issue is closed successfully, its resolution becomes the durable final account.

Its historical handovers remain useful for understanding how the solution evolved but are no longer the authoritative description of completion.

---

# When a Handover Should Be Written

The normal trigger is the end of a work session.

However, handovers should also be useful as checkpoints whenever the cost of reconstructing current state becomes high.

Examples:

* before context compaction
* before switching to another issue
* after a major implementation decision
* after landing substantial partial work
* before handing work to another agent
* before an interruption
* after discovering a blocker that changes the approach

The CLI itself does not automatically decide when to create them in this version.

Agents and humans invoke the command explicitly.

---

# Agent Experience

Without handovers:

```text
Session A
   ↓
understands issue
   ↓
explores repository
   ↓
makes decisions
   ↓
implements 70%
   ↓
session ends

Session B
   ↓
reads issue
   ↓
explores repository again
   ↓
reconstructs changes
   ↓
rediscovers decisions
   ↓
figures out what remains
   ↓
continues
```

With handovers:

```text
Session A
   ↓
work
   ↓
issue handover create ISS-042

Session B
   ↓
issue brief
   ↓
latest handover
   ↓
resume at src/issues.py:set_issue
   ↓
continue
```

The handover converts expensive reconstruction into cheap retrieval.

---

# Non-Goals

* No automatic AI-generated handover
* No chat transcript storage
* No storing complete prompts
* No source-code snapshots
* No complete Git diffs
* No session replay
* No background session tracking
* No Claude/Codex-specific integration
* No automatic issue status changes
* No automatic creation on terminal exit
* No automatic compaction hooks
* No agent ownership/claiming system
* No replacement for issue descriptions
* No replacement for permanent architectural decisions
* No remote synchronization service

---

# Technical Considerations

* Handover parsing should reuse the same Markdown/frontmatter philosophy as issues
* Handovers should live beneath the same discovered `.issues/` project root
* IDs should never be reused after deletion
* File iteration order must not determine `latest`
* Human rendering and JSON serialization must consume the same normalized handover object
* Git inspection must be read-only
* Git metadata should be captured at creation rather than recomputed later
* Changed files should represent the state when the handover was created
* No field should require source-code parsing
* Manual file editing should remain possible
* UTF-8 behavior must follow existing tracker guarantees

---

# Success Criteria

The feature succeeds when a completely new coding agent can take over an unfinished issue and answer:

* What happened during the previous session?
* What is already implemented?
* What remains?
* What decisions were made?
* What important things were discovered?
* Is anything blocking progress?
* Which files contain current work?
* What Git state does this checkpoint describe?
* Where should I resume?
* What should I do first?

without reading the previous AI conversation or scanning the entire repository.

---

# Future Extensions

## Automatic Session Integration

Claude Code, Codex, or another agent could eventually be instructed to create a handover automatically before ending or compacting context.

```text
Agent session ending
       ↓
issue handover create
       ↓
durable checkpoint
```

---

## Handover Freshness

Because every handover records its Git HEAD, future tooling could detect when the repository has moved significantly since the checkpoint:

```text
Latest handover: H-006

Recorded HEAD: 81af03c
Current HEAD:  b72d190

Warning:
Repository changed after this handover.
```

---

## Promote Decisions

A useful session decision could eventually become permanent project memory:

```bash
issue decision promote H-006 D-01
```

---

## Context Integration

Future:

```bash
issue context ISS-042
```

could automatically combine:

```text
Issue definition
+
Architecture context
+
Relevant historical decisions
+
Latest handover
```

into one bounded implementation context package.

---

# Long-Term Role

Session handover completes the missing middle of the persistent-context lifecycle.

```text
Plan
  ↓
Structured Issue
  ↓
Session begins
  ↓
Implementation
  ↓
Session Handover
  ↓
Next session
  ↓
Implementation continues
  ↓
Session Handover
  ↓
Verification
  ↓
Evidence-Based Closing
  ↓
Persistent Project Memory
```

Normal AI coding treats each context window as disposable.

This system should make each context window leave behind a useful artifact for the next one.

The core principle is:

> **A session may be temporary. Its useful context should not be.**
