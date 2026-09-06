# PRD: `issue next`

## Introduction

Add an `issue next` command that answers one question:

> **What should I work on next?**

The command selects the single best actionable issue using existing issue metadata such as status, priority, dependencies, and creation time.

The feature is deterministic and read-only. It does not assign, claim, or modify an issue.

## Goals

* Give humans and AI agents one command to identify the next actionable issue
* Avoid requiring agents to list, filter, and reason over the entire backlog
* Never recommend work that is currently blocked
* Use deterministic selection so repeated calls return the same result until project state changes
* Support machine-readable output for agents

## User Stories

### US-001: Select the next actionable issue

**Description:** As a developer, I want `issue next` to return the best issue I can work on so I don't have to inspect the backlog manually.

**Acceptance Criteria:**

* [ ] `issue next` returns exactly one issue
* [ ] Only actionable issues are considered
* [ ] Closed issues are never selected
* [ ] Blocked issues are never selected
* [ ] Existing readiness rules are reused rather than reimplemented differently
* [ ] Command exits successfully when an issue is found

### US-002: Prioritize active work

**Description:** As a developer, I want unfinished work I already started to be surfaced before new work so I don't accidentally abandon active issues.

**Acceptance Criteria:**

* [ ] Ready `in-progress` issues rank above ready `open` issues
* [ ] Blocked `in-progress` issues are not selected
* [ ] If no actionable `in-progress` issue exists, selection falls back to ready `open` issues

### US-003: Rank issues by priority

**Description:** As a user, I want higher-priority work selected first so `issue next` reflects project urgency.

**Acceptance Criteria:**

* [ ] High priority ranks above medium
* [ ] Medium ranks above low
* [ ] Low ranks above issues without a priority
* [ ] Priority ranking works identically for `open` and `in-progress` candidates

### US-004: Deterministic tie-breaking

**Description:** As a human or AI agent, I need `issue next` to behave predictably so the same project state always produces the same recommendation.

**Acceptance Criteria:**

* [ ] Issues with equal status and priority are ordered by `created_at`
* [ ] Older issues rank before newer issues
* [ ] Issue ID is used as the final tie-breaker
* [ ] Repeated calls against unchanged issue state return the same issue

### US-005: Explain why the issue was selected

**Description:** As a user, I want enough information in the output to understand why this issue is next.

**Acceptance Criteria:**

* [ ] Human output includes issue ID, title, status, and priority
* [ ] Output clearly identifies the issue as ready/actionable
* [ ] The command does not print the entire backlog
* [ ] Output remains compact enough for terminal use

Example:

```text
ISS-014  Fix dependency cycle detection
Status:   open
Priority: high
Ready:    yes
```

### US-006: Agent-readable output

**Description:** As a coding agent, I want structured output so I can consume the recommendation without parsing terminal formatting.

**Acceptance Criteria:**

* [ ] `issue next --json` is supported
* [ ] JSON contains the same issue fields exposed by existing issue JSON output
* [ ] Includes computed readiness information
* [ ] Exactly one issue object is returned
* [ ] Human-readable text is never mixed into stdout when `--json` is used

### US-007: Handle an empty actionable backlog

**Description:** As a user, I want a clear result when there is nothing available to work on.

**Acceptance Criteria:**

* [ ] If no actionable issue exists, no issue is returned
* [ ] Human output clearly states that no issue is ready
* [ ] Command exits with code `1`
* [ ] JSON mode remains parseable and does not mix error text into stdout

## Functional Requirements

* FR-1: Add `issue next`
* FR-2: Reuse the existing dependency/readiness calculation
* FR-3: Candidate issues must not be closed or blocked
* FR-4: Rank candidates in this order:

  1. `in-progress`
  2. `open`
  3. priority: high → medium → low → unset
  4. oldest `created_at`
  5. issue ID
* FR-5: Return only the highest-ranked issue
* FR-6: Support `--json`
* FR-7: Return exit code `1` when no actionable issue exists
* FR-8: The command must not mutate issue state

## Agent Experience

`issue next` should become the cheapest possible answer to:

> "What can I work on right now?"

An agent should not need to:

```text
issue list
→ inspect statuses
→ inspect priorities
→ inspect dependencies
→ determine readiness
→ choose an issue
```

Instead:

```bash
issue next --json
```

should provide the decision in one call.

This reduces context usage and unnecessary repository/backlog inspection.

## Non-Goals

* No automatic claiming of the returned issue
* No automatic status change to `in-progress`
* No AI-generated ranking
* No semantic understanding of issue descriptions
* No due dates or scheduling
* No user-specific recommendations
* No weighting based on labels
* No automatic execution of the issue

## Technical Considerations

* Selection logic should operate on the same normalized issue data used by `issue list --ready`
* Readiness logic must have one source of truth
* Ranking should be implemented separately from terminal rendering
* Human and JSON output should consume the same selected issue
* Missing blockers should follow the tracker's existing readiness semantics
* Selection must not depend on filesystem iteration order

## Success Criteria

* A human can determine their next task with one command
* An AI agent can determine its next actionable issue with one command and no backlog scan
* Blocked work is never accidentally recommended
* Identical project state always produces the same result
* `issue next` adds no new source of truth or issue metadata

## Future Extensions

Not part of this feature, but `issue next` can later become the foundation for:

```text
issue next --label backend
issue next --context
issue claim ISS-014
issue context ISS-014
```

Eventually an agent workflow could become:

```text
issue next --json
        ↓
issue context ISS-014 --json
        ↓
implement
        ↓
verify
        ↓
close with evidence
```

This keeps `issue next` small while making it the entry point into the larger AI-native context workflow.
