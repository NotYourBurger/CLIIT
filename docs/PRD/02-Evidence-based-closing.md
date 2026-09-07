# PRD: Evidence-Based Closing

## Introduction

Replace simple status-based closing with an explicit **resolution workflow**.

Today an issue can become closed with:

```bash
issue set ISS-014 closed
```

That tells a future human or AI agent only one thing:

> Someone considered this finished.

It does not explain:

* what was actually done
* why the issue was closed
* how the implementation was verified
* which commit contains the work
* whether the issue was completed, abandoned, duplicated, or superseded

Evidence-based closing makes closure a durable engineering artifact.

A completed issue should answer:

> **Why do we believe this issue is finished, and where is the proof?**

The issue Markdown file remains the canonical source of truth.

---

# Research Reference

## Kata

Kata treats closing as a **completion claim**, not merely a status mutation.

Its close workflow requires a substantive message and uses typed evidence. A `done` close requires one or more evidence items such as:

* commit
* pull request
* test command
* reviewed paths
* external evidence

Kata also distinguishes completion from `wontfix`, `duplicate`, `superseded`, and `audit-no-change`. Duplicate and superseded closures require another issue reference.

Example Kata workflow:

```bash
kata close abc4 --done \
  --message "Updated the CLI reference and verified docs-check passes." \
  --commit <sha>
```

Kata explicitly describes closing as asserting that the work is complete and instructs agents not to close work that has not actually been completed and tested.

### Product lesson

**Closing should capture a claim + rationale + evidence.**

---

## GitHub Issues

GitHub distinguishes broadly between work that is **completed** and work that is **not planned**. Issues can also be automatically closed through links from pull requests and commits using keywords such as `Fixes #10`.

This creates an important relationship:

```text
Issue
  ↓
Pull Request / Commit
  ↓
Merge
  ↓
Closed
```

GitHub therefore often gets completion evidence indirectly from development artifacts.

### Product lesson

**Code artifacts should be directly linkable to the resolution.**

---

## Linear

Linear models completion through workflow state. Typical workflows separate:

```text
In Progress
→ In Review
→ Ready to Merge
→ Done
```

and distinguish completed work from canceled work and duplicates.

Its GitHub integration can automatically move issue state based on pull request and commit activity.

### Product lesson

**Completion reason and workflow state should not be confused.**

`closed` means the lifecycle ended.

The resolution explains **why** it ended.

---

# Product Principle

A closed issue must become useful historical context.

A future agent reading:

```bash
issue view ISS-014
```

should understand:

1. What problem existed
2. What was implemented
3. Why the issue was closed
4. How the result was verified
5. Where the implementation lives

without opening GitHub, Linear, another database, or an old chat session.

---

# Goals

* Introduce explicit `issue close`
* Require a resolution reason when closing
* Require evidence for successfully completed work
* Preserve implementation and verification context inside the issue
* Link closed issues to commits, tests, PRs, or other evidence
* Make completed issues useful as persistent project memory
* Keep the workflow local-first and usable without network access
* Provide predictable structured output for AI agents
* Prevent accidental low-information closures

---

# User Stories

## US-001: Close an issue explicitly

**Description:** As a developer, I want a dedicated close command so completing work is distinct from modifying ordinary issue metadata.

### Acceptance Criteria

* [ ] Add `issue close <ID>`
* [ ] Closing changes the issue status to `closed`
* [ ] Closing records `closed_at`
* [ ] Closing records a resolution reason
* [ ] Closing records a resolution message
* [ ] Closing updates the canonical Markdown issue
* [ ] Unknown issue IDs fail without modifying files

Example:

```bash
issue close ISS-014 \
  --completed \
  --message "Added dependency cycle detection and regression coverage."
```

---

## US-002: Require a close reason

**Description:** As a future developer or agent, I want to know why an issue stopped being active so I can interpret historical project decisions correctly.

### Supported reasons

```text
completed
not-planned
duplicate
superseded
```

### Acceptance Criteria

* [ ] Every close has exactly one reason
* [ ] `completed` means the described work was implemented
* [ ] `not-planned` means the team intentionally decided not to perform the work
* [ ] `duplicate` means another issue represents the same work
* [ ] `superseded` means another issue or approach replaced this one
* [ ] Conflicting close reasons fail without modifying the issue
* [ ] Close reason appears in `issue view`
* [ ] Close reason appears in JSON output

---

## US-003: Require a resolution message

**Description:** As a future agent, I want a concise explanation of what happened so I don't have to reconstruct the resolution from Git history.

### Acceptance Criteria

* [ ] Every close requires `--message`
* [ ] Blank or whitespace-only messages are rejected
* [ ] The message is stored with the issue
* [ ] The message is visible from `issue view`
* [ ] The message is available through `--json`

Example:

```text
Resolution:
Added cycle detection before dependency writes. Invalid cycles now fail
without modifying either issue.
```

The message should describe the **outcome**, not repeat the issue title.

---

## US-004: Attach commit evidence

**Description:** As a developer or coding agent, I want to link the implementation commit so future readers can immediately locate the code change.

### Acceptance Criteria

* [ ] Support `--commit <sha>`
* [ ] Multiple commits may be attached
* [ ] Commit evidence is stored with the issue
* [ ] When inside a Git repository, the CLI validates that the commit exists locally
* [ ] An unknown commit fails before the issue is closed
* [ ] Commit SHA is shown in `issue view`
* [ ] Commit evidence is included in JSON output

Example:

```bash
issue close ISS-014 \
  --completed \
  --message "Implemented dependency cycle detection." \
  --commit 81af03c
```

---

## US-005: Attach test evidence

**Description:** As a future developer or reviewer, I want to know how the implementation was verified.

### Acceptance Criteria

* [ ] Support repeatable test evidence
* [ ] Test evidence records the command or verification performed
* [ ] Test evidence does not automatically execute arbitrary commands
* [ ] Multiple test entries can be stored
* [ ] Test evidence appears in `issue view`
* [ ] Test evidence appears in JSON output

Example:

```bash
issue close ISS-014 \
  --completed \
  --message "Implemented dependency cycle detection." \
  --commit 81af03c \
  --test "uv run python tests/test_blockers.py" \
  --test "uv run python tests/all.py"
```

This records a verification claim.

It does not imply that `issue` itself executed the tests.

---

## US-006: Require evidence for completed work

**Description:** As a project maintainer, I want completed issues to contain proof so `closed` cannot become a meaningless status.

### Acceptance Criteria

* [ ] `completed` requires at least one evidence item
* [ ] Accepted evidence types initially include:

  * commit
  * test
  * PR
  * manual verification
* [ ] Attempting to complete an issue without evidence fails
* [ ] Failure leaves the issue unchanged
* [ ] Error explains what evidence types are accepted

Example invalid command:

```bash
issue close ISS-014 \
  --completed \
  --message "Done"
```

Expected:

```text
Cannot close ISS-014 as completed: completion requires evidence.
Provide --commit, --test, --pr, or --verified.
```

---

## US-007: Support pull request evidence

**Description:** As a developer using GitHub or another Git host, I want to reference a pull request without making the tracker dependent on that service.

### Acceptance Criteria

* [ ] Support `--pr <URL>`
* [ ] PR references are stored as evidence
* [ ] No GitHub API request is required
* [ ] No network connection is required
* [ ] URL is exposed through `issue view`
* [ ] URL is included in JSON output

The tracker records the reference.

It does not need to verify that the remote PR exists.

This preserves local-first behavior.

---

## US-008: Support manual verification

**Description:** As a developer, I want to close work that cannot be represented by a commit or automated test while still documenting how it was verified.

### Acceptance Criteria

* [ ] Support `--verified "<description>"`
* [ ] Description cannot be blank
* [ ] Manual verification qualifies as evidence for `completed`
* [ ] Verification text remains clearly identified as manually asserted evidence

Example:

```bash
issue close ISS-021 \
  --completed \
  --message "Corrected terminal rendering on Windows." \
  --verified "Manually tested in PowerShell and Windows Terminal"
```

---

## US-009: Close work that will not be implemented

**Description:** As a developer, I want to close intentionally abandoned work without pretending it was completed.

### Acceptance Criteria

* [ ] `--not-planned` closes the issue
* [ ] A resolution message explaining the decision is required
* [ ] Implementation evidence is not required
* [ ] The issue records `reason: not-planned`
* [ ] It is visibly different from a successfully completed issue

Example:

```bash
issue close ISS-018 \
  --not-planned \
  --message "Regex search conflicts with the intentionally simple search contract."
```

---

## US-010: Close duplicate issues

**Description:** As a developer, I want duplicate issues to point to the canonical issue so context is not fragmented.

### Acceptance Criteria

* [ ] Support `--duplicate-of <ID>`
* [ ] Referenced issue must exist
* [ ] An issue cannot duplicate itself
* [ ] Duplicate target is stored as structured resolution evidence
* [ ] Close reason automatically becomes `duplicate`
* [ ] Duplicate relationship appears in `issue view`
* [ ] JSON output exposes the referenced issue

Example:

```bash
issue close ISS-028 \
  --duplicate-of ISS-014 \
  --message "Same dependency cycle bug already tracked by ISS-014."
```

---

## US-011: Close superseded issues

**Description:** As a developer, I want an obsolete plan to point to the issue that replaced it so future agents understand how planning evolved.

### Acceptance Criteria

* [ ] Support `--superseded-by <ID>`
* [ ] Referenced issue must exist
* [ ] An issue cannot supersede itself
* [ ] Close reason automatically becomes `superseded`
* [ ] Replacement issue is stored as structured resolution context
* [ ] Relationship appears in human and JSON views

Example:

```bash
issue close ISS-022 \
  --superseded-by ISS-031 \
  --message "Replaced by the architecture-index implementation."
```

This is especially important for persistent planning memory.

---

## US-012: Prevent bypassing evidence-based closure

**Description:** As a project maintainer, I want every new closure to follow the same contract so historical data remains trustworthy.

### Acceptance Criteria

* [ ] `issue set ISS-014 closed` is no longer allowed
* [ ] The command explains that closing requires `issue close`
* [ ] `issue set` continues to manage `open` and `in-progress`
* [ ] Existing already-closed issues remain valid and readable
* [ ] Old issue files are not automatically rewritten

Expected output:

```text
Closing an issue requires a resolution.

Use:
  issue close ISS-014 ...
```

---

## US-013: Display resolution context

**Description:** As a human, I want closed issues to explain their resolution directly when viewed.

### Acceptance Criteria

`issue view ISS-014` shows a resolution section containing:

```text
Resolution
Reason:     completed
Closed:     2026-09-06T...
Message:    Added dependency cycle detection.

Evidence
Commit:     81af03c
Test:       uv run python tests/test_blockers.py
Test:       uv run python tests/all.py
```

* [ ] Resolution is visually separated from original issue description
* [ ] Missing optional evidence types are omitted
* [ ] Existing pre-feature closed issues remain renderable

---

## US-014: Agent-readable resolution

**Description:** As an AI coding agent, I want closure information in structured output so completed issues can serve as historical context without parsing terminal text.

### Acceptance Criteria

`issue view ISS-014 --json` exposes structured resolution data.

Conceptually:

```json
{
  "id": "ISS-014",
  "status": "closed",
  "resolution": {
    "reason": "completed",
    "closed_at": "...",
    "message": "Added dependency cycle detection.",
    "evidence": [
      {
        "type": "commit",
        "value": "81af03c"
      },
      {
        "type": "test",
        "value": "uv run python tests/all.py"
      }
    ]
  }
}
```

* [ ] Evidence is represented as structured values
* [ ] Agents do not need to parse Markdown prose
* [ ] JSON stdout contains no human formatting
* [ ] Historical issues without resolution metadata remain readable

---

# Functional Requirements

### Closure

* FR-1: Introduce `issue close <ID>`
* FR-2: Every close records a reason
* FR-3: Every close records a message
* FR-4: Every close records `closed_at`
* FR-5: Closing changes status to `closed`
* FR-6: Close operations are atomic: failed validation writes nothing

### Resolution Reasons

* FR-7: Support `completed`
* FR-8: Support `not-planned`
* FR-9: Support `duplicate`
* FR-10: Support `superseded`

### Evidence

* FR-11: `completed` requires at least one evidence item
* FR-12: Support commit evidence
* FR-13: Support test evidence
* FR-14: Support PR evidence
* FR-15: Support manual verification evidence
* FR-16: Evidence is typed rather than stored as one undifferentiated text string

### Relationships

* FR-17: Duplicate closure requires a valid issue reference
* FR-18: Superseded closure requires a valid issue reference
* FR-19: Self-references are rejected

### Output

* FR-20: `issue view` displays resolution details
* FR-21: JSON output exposes structured resolution information
* FR-22: Existing closed issues without resolution metadata continue to work

### Workflow Integrity

* FR-23: `issue set <ID> closed` must not bypass the resolution workflow
* FR-24: Network access must never be required to close an issue
* FR-25: Closing must modify only the canonical issue artifact

---

# Proposed CLI UX

### Completed with commit

```bash
issue close ISS-014 \
  --completed \
  --message "Implemented cycle detection before dependency writes." \
  --commit 81af03c
```

### Completed with tests

```bash
issue close ISS-014 \
  --completed \
  --message "Implemented and verified dependency cycle detection." \
  --commit 81af03c \
  --test "uv run python tests/test_blockers.py"
```

### Completed with manual verification

```bash
issue close ISS-014 \
  --completed \
  --message "Fixed Windows terminal rendering." \
  --verified "Tested in PowerShell and Windows Terminal"
```

### Not planned

```bash
issue close ISS-014 \
  --not-planned \
  --message "Feature conflicts with the intentionally deterministic search model."
```

### Duplicate

```bash
issue close ISS-014 \
  --duplicate-of ISS-009 \
  --message "Same root problem."
```

### Superseded

```bash
issue close ISS-014 \
  --superseded-by ISS-021 \
  --message "Replacement issue contains the revised architecture."
```

---

# Data Model

The canonical issue must contain structured resolution metadata sufficient to reconstruct:

```text
reason
closed_at
message
evidence[]
```

Evidence must preserve its type:

```text
commit
test
pr
verified
duplicate-of
superseded-by
```

The exact Markdown/frontmatter serialization is an implementation decision.

However:

> An agent must be able to recover the resolution structure without GitHub, Linear, an API call, or access to the original closing session.

---

# Reopening Behavior

Reopening must not leave an open issue claiming a current resolution. Historical
completion context remains in git and is available through `issue log`.

When a closed issue is reopened:

* status becomes `open`
* `reason`, `closed_at`, `message` and `evidence` are removed from the current file
* a future agent can see the previous resolution through `issue log`
* closing it again creates a fresh resolution

The complete lifecycle may eventually become:

```text
created
↓
in-progress
↓
closed
  completed
  commit 81af03c
  tests passed
↓
reopened
  regression discovered
↓
closed
  completed
  commit a921be2
```

Full lifecycle/event-log UX is outside this PRD, but the data design must not prevent it.

---

# Agent Experience

Before evidence-based closing:

```text
ISS-014
status: closed
```

A future agent must investigate:

```text
What changed?
Which commit?
Was it tested?
Was it actually fixed?
Why was it closed?
```

After evidence-based closing:

```text
ISS-014
status: closed
reason: completed

Implemented dependency cycle validation before writes.

commit: 81af03c
test: uv run python tests/test_blockers.py
```

The issue itself becomes compressed historical context.

This directly supports the product's persistent AI memory goal.

---

# Non-Goals

* No GitHub API integration
* No automatic PR merge detection
* No automatic issue closing from commit messages
* No CI integration
* No automatic execution of supplied test commands
* No cryptographic proof that tests were executed
* No remote reviewer approval system
* No user permissions or authorization
* No automatic AI-generated resolution summary
* No full event database
* No hosted activity feed

These can be built later without changing the fundamental resolution model.

---

# Technical Considerations

* Existing issue parsing/writing must continue preserving unknown metadata
* Resolution data should round-trip without modifying the issue description
* Evidence validation should happen before any write
* Local commit evidence can be validated using Git
* PR URLs are references only and should never require network access
* Evidence rendering and evidence storage should remain separate
* Human and JSON output should use the same underlying resolution model
* Existing legacy closed issues must not break

Because issues themselves are already Git-tracked Markdown files, the issue's resolution changes also inherit Git history automatically.

---

# Success Criteria

The feature succeeds when a developer or agent can open a completed issue months later and answer:

* Why was this closed?
* Was it implemented or abandoned?
* What changed?
* Which commit contains it?
* How was it verified?
* Did another issue replace it?

without reading an old AI conversation or searching an external tracker.

---

# Future Extensions

Evidence-based closing becomes the foundation for:

```text
issue context ISS-014
issue history ISS-014
issue verify ISS-014
issue review-context ISS-014
issue memory search "dependency cycle"
```

Later, `issue context` could use resolution evidence from completed related issues to give an agent historical implementation knowledge automatically.

That creates the longer-term flow:

```text
Planning
   ↓
Structured Issue
   ↓
Implementation Context
   ↓
Implementation
   ↓
Verification
   ↓
Evidence-Based Resolution
   ↓
Persistent Project Memory
   ↓
Future Agent Context
```

The close operation therefore isn't merely the end of an issue.

It is the point where temporary implementation work becomes durable project knowledge.
