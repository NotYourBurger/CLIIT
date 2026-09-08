# Compact plan output

Repeated reads should not require replaying a plan's entire rationale. The ten
plans reviewed on 2026-09-08 produce 791-2656 characters from `plan_lines`, with
a mean of 1535.6. These are character measurements, not tokenizer counts.

`issue start ID --compact` and `issue next --compact` provide an opt-in summary
for a session that already has context. Full output remains the default: the
agent-behaviour report demonstrates that discoveries helped a fresh session
recover interrupted work. The plan file and existing JSON schema stay intact.

## Acceptance criteria

- Show completed/total checkpoints and at most three unfinished checkpoints.
- Flatten each pending checkpoint, Current, and Next to one line, at most 160
  characters each; an ellipsis marks shortened text.
- Explicitly count additional pending checkpoints and omitted decisions and
  discoveries. Always point to the complete plan file when a plan exists.
- Omit git details in compact next output. Issue identity, status, priority and
  readiness remain visible. This bounds the plan summary, not arbitrary issue
  titles, blocker lists, or filesystem paths.
- Reject `next --compact --json`, including with `--claim`, before any write.
- Resume never edits the existing plan; full output and JSON retain all details.
- Test the actual CLI flags as subprocesses, long active plans, missing sections,
  empty plans, explicit omissions, and byte preservation with standalone scripts.
- Compare output size on existing plans; do not claim a model-token percentage
  or a successful fresh-agent recovery experiment from character counts alone.

## Scope

This changes rendering only. It does not fix ownership races, lifecycle
transitions, storage validation, or introduce a new plan format. Agents should
use full output or read the indicated file when resuming without prior context.
