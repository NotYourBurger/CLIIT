# PRD: Run Event Log

## Introduction

`issue start` gave the *code* a durable record that survives a session ending
without warning: a work plan, written before the first edit and ticked as it
goes. The agent-behaviour run (`docs/agent-behaviour-report.md`) tested that
claim on ISS-032 through ISS-035 and found it held for implementation state -
and found a second class of state it does not cover at all.

Running probes against this tool - a claim race between two agents, an
intentional kill of a worker mid-task, a coordinator watching several workers
at once - produces measurements that are not implementation state and do not
belong in a work plan: which agent's `issue claim` call printed what, the
exact bytes of a plan at the moment a process was killed, a worker's first
three tool calls, how many turns a task took. None of that lived anywhere but
task output and a scratchpad. When the coordinator itself was cut off, all of
it was gone - the plan and the git history recovered the *code*, but the
*experiment* was unrecoverable, and the report had to say so rather than
invent a number.

The fix is the same shape as the work plan: stop trusting an ending to write
the record, and make the record durable at the moment the fact is true.

## Product Principle

The work plan is what an agent decided and learned, in its own prose, edited
with the tool it is already holding. It is mid-thought by design, and reading
it back means reading a person's account.

The event log is what a running process observed, one fact per line, written
by whatever produced the fact - a probe's stdout, a coordinator's kill hook,
an agent noting a lifecycle event - at the instant it is true. It is not
prose and nobody edits it afterwards.

```text
Work plan     what the agent decided and learned      edited by hand
Event log     what a process observed, and when       appended, never edited
```

They stay separate artifacts for the same reason the issue and the plan do:
mixing a machine-appended timestamp into hand-edited prose makes both worse to
read, and an append that lands mid-edit could not corrupt hand-written text if
it is never in the same file.

## Goals

* Make probe output, timestamps, and lifecycle events durable the instant
  they happen, not at an ending that may not arrive
* Survive the process that is writing them being killed mid-run
* Cost one command, usable from a shell probe or a coordinator script and not
  only from an agent
* Keep the artifact plain text, local, and Git-trackable like everything else
  here
* Leave a closed issue with a readable record of what was observed while it
  was worked, alongside the plan that records what was decided

## User Stories

### US-001: Recording an event costs one command

**Description:** As a coordinator or agent that just observed something worth
keeping - a probe's result, a worker starting, a worker being killed - I want
to record it in one call so capturing it is cheaper than losing it.

#### Acceptance Criteria

* [ ] Add `issue event <ID> <TEXT>`
* [ ] Referenced issue must exist
* [ ] Appends one entry to `.issues/work/<ID>.events.jsonl`, creating the file
      and `work/` if either is missing
* [ ] Never rewrites or reorders an existing entry
* [ ] `--type` labels the entry (`note` if omitted); any value is accepted
* [ ] Each entry stores its own timestamp, taken at write time

### US-002: Piping output in avoids a shell-quoting problem

**Description:** As a coordinator capturing a probe's real stdout or a
snapshot of another file, I want to redirect it in rather than pass it as a
shell argument, so multi-line or shell-hostile text is not mangled first.

#### Acceptance Criteria

* [ ] `--stdin` reads TEXT from standard input instead of the argument
* [ ] Passing both `TEXT` and `--stdin` is rejected before any write
* [ ] Multi-line input is stored whole and read back whole

```bash
issue event ISS-033 --type snapshot --stdin < .issues/work/ISS-033.md
probe_command | issue event ISS-036 --type probe --stdin
```

### US-003: The log reads back without leaving the CLI

**Description:** As someone investigating after the fact, I want to see an
issue's recorded events without hand-parsing JSONL, while the raw file stays
directly readable for anyone who wants it.

#### Acceptance Criteria

* [ ] `issue event <ID>` with no TEXT and no `--stdin` prints the log
* [ ] Human output: one line per entry, time, type, and text
* [ ] `--json` prints the entries as a JSON array
* [ ] No entries and no file yet is not an error - it is an empty log
* [ ] The file itself is plain JSON Lines, readable with `cat` or `jq`

### US-004: The log is checked like everything else on disk

**Description:** As a maintainer, I want a stray event log - one written
after its issue was renamed or removed by hand - to be visible the way an
orphaned work plan already is.

#### Acceptance Criteria

* [ ] `issue check` reports an event log with no issue beside it
* [ ] A malformed line in an existing log is reported by file and line number
      rather than raising
* [ ] Nothing here validates `--type` values; a log is data, not a schema

## Functional Requirements

### Commands

* FR-1: `issue event <ID> [TEXT]` is the only command added
* FR-2: TEXT or `--stdin`, never both; neither prints the log instead of
  appending to it
* FR-3: `--type` defaults to `note` and accepts any string
* FR-4: `--json` on the read path prints the raw entries

### Storage

* FR-5: One file per issue, `.issues/work/<ID>.events.jsonl`, sibling to that
  issue's work plan
* FR-6: `work/` is created on demand, the same call `plan.py` already makes
* FR-7: Every write is a single `open(..., "a")` appending one line - no read,
  rewrite, or reordering of what is already there
* FR-8: One JSON object per line: `at` (the same timestamp format as
  everything else on disk), `type`, `text`
* FR-9: Encoding and newlines follow the repo-wide rule: UTF-8, `\n`, even on
  append

### Reading

* FR-10: The reader never raises; a line that fails to parse as JSON is
  skipped and reported, not fatal to the rest of the file
* FR-11: A missing file reads back as an empty list, not an error

## Storage Model

```text
.issues/
├── ISS-036.md                     durable definition
└── work/
    ├── ISS-036.md                 mutable execution state (the plan)
    └── ISS-036.events.jsonl       append-only observations
```

One line:

```json
{"at": "2026-09-08T11:04:02+06:00", "type": "lifecycle", "text": "worker started, 0 tool calls"}
```

## Non-Goals

* No structured schema beyond `at` / `type` / `text` - a probe that wants more
  puts it in `text`
* No CLI verb edits or removes an entry once written
* No cross-issue or run-level log; every entry belongs to one issue, the same
  way a plan does
* No enforced `--type` vocabulary
* No automatic instrumentation of `issue` commands themselves - this records
  what a caller chooses to record, not a hidden audit trail of CLI usage
* No concurrent-write guarantee beyond what append mode already gives a single
  small write; two processes racing on the same log is not the problem this
  solves

## Success Criteria

The feature succeeds when a coordinator killing a worker mid-task, or two
agents racing a claim, leaves a file on disk that answers what happened and
when - so the next report is a read, not an admission that the measurement is
gone.
