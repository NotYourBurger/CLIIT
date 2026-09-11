# PRD: Project Briefing — `issue brief`

## Introduction

Add a project-level briefing command:

```bash
issue brief
```

`issue brief` gives a human or AI agent the minimum useful context needed to understand the current state of the project and decide what to do next.

Today, a new coding session may need to run several commands:

```text
issue list
issue list --ready
issue list --blocked
issue list in-progress
issue search ...
issue view ...
git log ...
```

and then reconstruct project state manually.

For an AI agent, every extra lookup consumes context, tool calls, and reasoning budget.

`issue brief` compresses the project's issue state into one deterministic, read-only briefing.

The command should answer:

> **What is happening in this project, what needs attention, and what context should I know before I start working?**

It does not replace `issue view`, `issue next`, or the future issue-specific context system.

It is the **entry point into the project**.

---

# Product Principle

A coding agent should not need to rediscover project state every time a session begins.

Project state already exists in `.issues/`.

`issue brief` turns that durable state into a compact orientation artifact.

```text
Persistent Issues
       ↓
Dependencies
       ↓
Priorities
       ↓
Resolution History
       ↓
Current Work
       ↓
issue brief
       ↓
Human / AI understands project state
```

The briefing is derived.

`.issues/` remains the only source of truth.

---

# Goals

* Give humans and AI agents a one-command project orientation
* Reduce repeated backlog inspection at the beginning of coding sessions
* Surface actionable work immediately
* Surface active and blocked work
* Expose important recent project memory
* Keep output compact enough for AI context windows
* Produce deterministic output from repository state
* Support machine-readable output
* Remain entirely local-first
* Avoid requiring GitHub, Linear, MCP, databases, or network access

---

# User Stories

## US-001: Generate a project briefing

**Description:** As a developer entering an unfamiliar or previously paused project, I want one command that summarizes the current work state so I can quickly understand what is happening.

### Acceptance Criteria

* [ ] Add `issue brief`
* [ ] Command is read-only
* [ ] Command works from anywhere inside the initialized repository
* [ ] Brief is generated entirely from canonical `.issues/` data
* [ ] Brief does not modify any issue
* [ ] Brief succeeds when the project contains issues
* [ ] Brief remains usable without network connectivity

---

## US-002: Show current work

**Description:** As a developer or agent, I want to see work that is already underway so I don't start unrelated work while something important is unfinished.

### Acceptance Criteria

The briefing includes all `in-progress` issues.

Each entry includes at minimum:

* issue ID
* title
* priority
* readiness/blocking state

Example:

```text
IN PROGRESS

ISS-032  Evidence-based closing        high
ISS-028  Dependency graph rendering    medium
```

* [ ] In-progress work appears before unopened work
* [ ] Blocked in-progress work is visibly identified
* [ ] Closed issues never appear in this section

---

## US-003: Surface the recommended next issue

**Description:** As a coding agent, I want the project briefing to tell me what work is currently most actionable.

### Acceptance Criteria

* [ ] Brief includes the result of the existing `issue next` selection logic
* [ ] The selection logic is reused rather than duplicated
* [ ] Exactly one next issue is shown when actionable work exists
* [ ] No recommendation is shown when no issue is actionable
* [ ] The briefing does not automatically claim or start the issue

Example:

```text
NEXT

ISS-041  Add structured resolution metadata
Priority: high
Ready: yes
```

---

## US-004: Show blocked work

**Description:** As a developer, I want to see what work is stuck and why so I understand project bottlenecks.

### Acceptance Criteria

* [ ] Brief contains a blocked-work section when blocked issues exist
* [ ] Each blocked issue shows its direct blockers
* [ ] Blocker status is shown
* [ ] Missing blocker references remain visibly marked as missing
* [ ] No blocked section is printed when nothing is blocked

Example:

```text
BLOCKED

ISS-039  Static HTML export
         waiting on ISS-034 (open)

ISS-046  Architecture context
         waiting on ISS-042 (missing)
```

---

## US-005: Show ready work without dumping the backlog

**Description:** As an agent, I want to see a small set of other actionable issues without loading the entire backlog.

### Acceptance Criteria

* [ ] Brief includes a limited ready-work section
* [ ] Recommended next issue is not duplicated
* [ ] Ready issues follow the same deterministic ordering as `issue next`
* [ ] Default output shows at most 5 additional ready issues
* [ ] Large backlogs do not cause the brief to become a full issue listing
* [ ] If more ready issues exist, output indicates how many were omitted

Example:

```text
READY

ISS-045  Add close reason rendering        high
ISS-047  Preserve resolution on reopen     medium
ISS-049  Add JSON resolution output        medium

+7 more ready issues
```

---

## US-006: Surface recent project memory

**Description:** As a future coding agent, I want to know what recently changed so I don't rediscover decisions or repeat completed work.

### Acceptance Criteria

* [ ] Brief includes recently closed issues
* [ ] Default maximum is 5 recent closures
* [ ] Most recently closed issues appear first
* [ ] Issues with evidence-based resolution show their resolution reason
* [ ] Completed issues show a concise resolution message when available
* [ ] Legacy closed issues without resolution metadata remain supported

Example:

```text
RECENTLY RESOLVED

ISS-030  completed
         Added deterministic issue-next ranking.
         commit: 81af03c

ISS-027  superseded → ISS-032
         Resolution workflow replaced direct status closing.
```

This section is project memory, not merely activity history.

---

## US-007: Keep the briefing compact

**Description:** As an AI agent, I want project context to contain useful information without consuming unnecessary context-window capacity.

### Acceptance Criteria

* [ ] Default briefing does not include full issue descriptions
* [ ] Default briefing does not include entire resolution histories
* [ ] Default briefing does not print all closed issues
* [ ] Default briefing does not print the complete dependency graph
* [ ] Repeated information is avoided
* [ ] Output prioritizes actionable and recent information
* [ ] Large repositories produce bounded output

The command should prefer:

```text
useful context / tokens
```

over:

```text
maximum information / tokens
```

---

## US-008: Provide machine-readable briefing output

**Description:** As a coding agent, I want structured briefing data so I don't have to parse terminal formatting.

### Acceptance Criteria

Support:

```bash
issue brief --json
```

JSON contains structured sections such as:

```json
{
  "next": {},
  "in_progress": [],
  "ready": [],
  "blocked": [],
  "recently_resolved": [],
  "summary": {}
}
```

* [ ] JSON uses existing normalized issue structures where possible
* [ ] Derived values remain explicitly represented
* [ ] Arrays are empty rather than omitted where predictable structure is useful
* [ ] Human-readable output is never mixed into JSON stdout
* [ ] Ordering matches human briefing semantics

---

## US-009: Include project health summary

**Description:** As a developer, I want a small numerical overview so I can understand the scale and state of the backlog immediately.

### Acceptance Criteria

Brief includes counts for:

```text
open
in-progress
ready
blocked
closed
```

Example:

```text
PROJECT

Open:         18
In progress:   2
Ready:        11
Blocked:       5
Closed:       34
```

* [ ] Counts use existing status/readiness rules
* [ ] Missing dependency references do not silently distort counts
* [ ] Summary does not require additional stored metadata

---

## US-010: Handle an empty project

**Description:** As a user who just initialized issue tracking, I want `issue brief` to explain that there is currently no project work rather than failing mysteriously.

### Acceptance Criteria

When `.issues/` exists but contains no issues:

```text
No issues yet.

Create one with:
  issue create "Title" "Description"
```

* [ ] Command exits successfully
* [ ] JSON output remains valid
* [ ] Empty project is distinguished from an uninitialized repository

---

## US-011: Surface inconsistent project context

**Description:** As an agent, I want the briefing to warn me about issue-state problems that could make its recommendations unreliable.

### Acceptance Criteria

The brief surfaces important integrity warnings already detectable by the tracker, including:

* missing blockers
* malformed issue references
* unreadable issue files where applicable

Example:

```text
WARNINGS

ISS-042 references missing blocker ISS-017
```

* [ ] Warnings do not prevent the rest of the brief from rendering when safe
* [ ] Warning details remain concise
* [ ] `--json` exposes warnings structurally

---

## US-012: Reuse existing business rules

**Description:** As a maintainer, I want project briefing logic to remain consistent with the rest of the CLI.

### Acceptance Criteria

`issue brief` must reuse existing logic for:

* issue loading
* statuses
* priorities
* dependencies
* readiness
* next-issue ranking
* resolution parsing

It must not create a second interpretation of project state.

For example:

```text
issue next
```

and:

```text
issue brief
```

must never disagree about which issue is next.

---

# Functional Requirements

## Brief Generation

* FR-1: Add `issue brief`
* FR-2: Command must be read-only
* FR-3: Brief must derive entirely from canonical issue files
* FR-4: Command must work from anywhere within the repository

## Sections

Default brief contains:

1. Project summary
2. Recommended next issue
3. In-progress work
4. Other ready work
5. Blocked work
6. Recently resolved work
7. Integrity warnings

Sections with no relevant data may be omitted in human output.

---

## Output Limits

* FR-5: Show at most one recommended next issue
* FR-6: Show all in-progress issues
* FR-7: Show at most five additional ready issues by default
* FR-8: Show blocked issues with direct blockers
* FR-9: Show at most five recently resolved issues by default
* FR-10: Indicate omitted counts where sections are truncated

---

## Machine Output

* FR-11: Support `--json`
* FR-12: JSON output exposes both canonical and derived project state
* FR-13: JSON must remain deterministic
* FR-14: JSON stdout must remain free of terminal prose

---

# Proposed CLI UX

```bash
issue brief
```

Example:

```text
CLIIT

PROJECT
Open: 12    In progress: 1    Ready: 7    Blocked: 4    Closed: 26

NEXT
ISS-041  Add structured resolution metadata
         high · ready

IN PROGRESS
ISS-038  Evidence-based closing
         high · ready

READY
ISS-043  Render closure evidence
ISS-045  Preserve resolution history
ISS-048  Add resolution JSON output
+3 more

BLOCKED
ISS-050  Static HTML project explorer
         waiting on ISS-043 (open)

ISS-051  Architecture index
         waiting on ISS-047 (open)

RECENTLY RESOLVED
ISS-036  completed
         Added deterministic next-issue selection.
         commit: a21fc49

ISS-034  superseded → ISS-038
         Replaced direct closed-status mutation with resolution workflow.
```

---

# Agent Experience

Without `issue brief`, a fresh coding agent may need to discover state manually:

```text
issue list
↓
issue list --ready
↓
issue list --blocked
↓
issue list in-progress
↓
inspect recent closed issues
↓
reason about priority
↓
determine what matters
```

This produces unnecessary tool chatter and repeatedly spends context on project orientation.

With the feature:

```bash
issue brief --json
```

returns the starting state in one call.

The agent then chooses the next narrow operation:

```text
issue brief
     ↓
issue next
     ↓
issue context ISS-041      # future feature
     ↓
implementation
```

The project briefing is therefore a **routing layer for context**.

It tells the agent *where to look next* without giving it everything.

---

# Brief vs `issue next`

These commands solve different problems.

### `issue next`

Answers:

> What single issue should I work on?

### `issue brief`

Answers:

> What is happening in this project right now?

`issue next` is a decision.

`issue brief` is orientation.

The brief may contain the result of `issue next`, but it must not replace it.

---

# Brief vs Future `issue context`

These also operate at different levels.

### `issue brief`

Project-level:

```text
current work
ready work
blocked work
recent memory
project health
```

### `issue context ISS-041`

Issue-level:

```text
problem
acceptance criteria
relevant files
entry points
public APIs
architecture
dependencies
prior decisions
handover
```

The expected agent flow becomes:

```text
issue brief
      ↓
choose work
      ↓
issue context ISS-041
      ↓
start coding
```

This separation prevents the project briefing from becoming another context dump.

---

# Data Model

`issue brief` introduces **no canonical project state of its own**.

No `brief.json`.

No generated metadata that needs synchronization.

No briefing database.

Every value is computed from:

```text
.issues/*.md
```

and later optionally from other canonical repo-native context artifacts such as:

```text
.issues/architecture/
```

The brief is a **view**, not a source of truth.

---

# Non-Goals

* No AI-generated project summary
* No LLM invocation
* No source-code scanning
* No automatic architecture inference
* No automatic task execution
* No claiming issues
* No changing issue status
* No remote API calls
* No GitHub or Linear synchronization
* No MCP requirement
* No complete issue history dump
* No complete project roadmap
* No static HTML generation
* No issue-specific implementation context

Those belong to separate features.

---

# Technical Considerations

* Briefing should operate on one normalized load of project issues rather than repeatedly reading the same files
* Existing filtering, readiness, dependency, priority, and resolution helpers should be reused
* Rendering should remain separate from briefing-data generation
* Human and JSON views must share the same generated briefing model
* Section ordering must be deterministic
* Filesystem ordering must never affect output
* Legacy issues without newer metadata must remain usable
* Brief generation should remain fast enough to run automatically at the beginning of an AI coding session

---

# Success Criteria

The feature succeeds when a developer or coding agent can enter an existing repository after days, weeks, or months away, run:

```bash
issue brief
```

and immediately understand:

* what is currently being worked on
* what should probably happen next
* what work is blocked
* what else is ready
* what recently changed
* whether the issue graph contains obvious problems

without scanning the full backlog or reconstructing context from old chats.

---

# Future Extensions

The briefing can later consume additional first-class context artifacts.

## Architecture Awareness

When the architecture index exists:

```text
ARCHITECTURE CHANGED

storage
  Updated by ISS-041

dependency-graph
  Referenced by 3 active issues
```

---

## Session Handover

When persistent handovers exist:

```text
LAST HANDOVER

ISS-041
Cycle validation is implemented.
Remaining: JSON resolution rendering.
Start at src/issues.py:render_issue()
```

---

## Context Budget

Agents could eventually request:

```bash
issue brief --budget 2000
issue brief --budget 5000
```

The command would choose how much project context to expose within an approximate context budget.

---

## Historical Memory

Future project-memory features could enrich recent resolution context:

```text
RELEVANT MEMORY

Dependency storage is intentionally one-directional.
Decision originated in ISS-012.
```

without requiring an agent to search every completed issue.

---

# Long-Term Role

`issue brief` becomes the front door to the AI-native context system.

```text
Enter repository
      ↓
issue brief
      ↓
Understand project state
      ↓
issue next
      ↓
Select work
      ↓
issue context
      ↓
Load implementation context
      ↓
Implement
      ↓
Evidence-based close
      ↓
Durable project memory
      ↓
Future issue brief
```

The important property is the loop:

> **Work performed today improves the context available to the next session.**

That is the core difference between a normal issue tracker and a persistent AI context system.
