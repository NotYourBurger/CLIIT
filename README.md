<div align="center">

# CLIIT

**Issue tracking that lives with your code.**

[![CI](https://github.com/NotYourBurger/CLIIT/actions/workflows/ci.yml/badge.svg)](https://github.com/NotYourBurger/CLIIT/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

[Install](#install) · [Quickstart](#quickstart) · [Usage](#usage) · [AI coding agents](#ai-coding-agents) · [Configuration](#configuration)

</div>

CLIIT (Command-Line Issue Tracker) stores each issue as a Markdown file in
`.issues/`. Keep your backlog beside your code, review changes in pull requests,
and share it through Git. No server or account required.

- **Plain files you own.** Read and edit issues in any text editor, even without CLIIT.
- **Focused daily workflow.** Search, prioritize, assign, and track dependencies from your terminal.
- **A clear next step.** `issue next` selects actionable work by status, priority, and age.
- **Continuity for coding agents.** JSON output, issue claims, and saved work plans help sessions pick up where they left off.

## Install

Requires **Python 3.10+**, [uv](https://docs.astral.sh/uv/getting-started/installation/),
and Git for the source installation below. Works on Linux, macOS, and Windows.

```bash
uv tool install git+https://github.com/NotYourBurger/CLIIT
issue --version
```

Both `issue` and `cliit` run the same CLI. To update, run `uv tool upgrade cliit`.
If your shell cannot find `issue`, run `uv tool update-shell` and reopen your terminal.

## Quickstart

Run these commands in your project's root directory:

```bash
issue init
issue create "Fix login redirect" "The session cookie disappears after sign-in." -p high -l bug
issue list
issue next
issue start ISS-001
```

The example assumes a new tracker; use the ID returned by `create` in an existing
one. `start` marks the issue in progress and creates `.issues/work/ISS-001.md`.
Edit that plan as you work, keeping its checkpoints and next step current.

After implementing and checking the fix, record the result:

```bash
issue close ISS-001 --completed -m "Fixed session cookie handling." --verified "Signed in and confirmed the session survives the redirect."
```

Commit `.issues/` alongside your code to keep the issue, work plan, and resolution
in the same history.

> [!TIP]
> Working with Codex or Claude Code? Use `issue init --agents` to configure their
> repository instructions. Plain `issue init` also adds workflow guidance to
> existing `AGENTS.md` or `CLAUDE.md` files.

## Usage

Run `issue --help` for all commands, or `issue <command> --help` for its options.

### Find and organize work

| Task | Command |
| --- | --- |
| Get a project overview | `issue brief` |
| Find the next issue to work on | `issue next` |
| List open, high-priority bugs | `issue list open -p high -l bug` |
| Find available work | `issue list --ready --unassigned` |
| See blocked issues | `issue list --blocked` |
| Search titles and descriptions | `issue search "login redirect"` |
| Read an issue | `issue view ISS-001` |
| Change priority or add a label | `issue set ISS-001 -p high -l auth` |
| Remove a label | `issue set ISS-001 --unlabel auth` |
| Add a dependency | `issue set ISS-002 --blocked-by ISS-001` |
| Remove a dependency | `issue set ISS-002 --unblock ISS-001` |
| Claim an issue | `issue claim ISS-001 --by alex` |
| Assign ownership | `issue assign ISS-001 --to alex` |
| Release ownership | `issue release ISS-001` |
| Reopen an issue | `issue set ISS-001 open` |
| Read its committed history | `issue log ISS-001` |
| Check tracker files for problems | `issue check` |

Statuses are `open`, `in-progress`, and `closed`. Priorities are `high`, `medium`
(the default), and `low`. Repeat `-l` to add or filter by multiple labels; filters
combine, and search requires every word to match, ignoring case.

`list` places the most urgent rows nearest your terminal prompt. `next` prefers
in-progress work, then higher priority, then older issues. It skips closed and
blocked issues, and skips other people's assignments when your identity is known.
It only reads unless you add `--claim`.

### Close with a reason

Every close requires one reason and a nonblank, single-line message (`-m`).

| Reason | Additional requirement |
| --- | --- |
| `--completed` | At least one piece of evidence |
| `--not-planned` | None |
| `--duplicate-of ID` | Another existing issue |
| `--superseded-by ID` | Another existing issue |

Evidence flags are repeatable: `--commit <sha>`, `--test "<command>"`,
`--pr <url>`, and `--verified "<manual check>"`. A close supported only by
`--verified` is accepted with a warning.

> [!NOTE]
> `--test` records a command; it does **not** run it. Run your checks before
> closing. Commit references are validated against the local Git repository
> when available; PR URLs are stored without fetching them.

Use `issue close` to close an issue; `issue set ... closed` is refused. Reopening
clears the current resolution, while committed history remains available through
`issue log`.

## AI coding agents

Set `ISSUE_USER` to a distinct name for each worker, or use your configured
`git config user.name`. Then use the same workflow from a script or agent:

```bash
issue init --agents
issue brief --json
issue next --claim --json
issue start ISS-001
```

Use the ID returned by `next` for `start`. Claims coordinate workers in the same
working copy; `--claim` tries another candidate if one is taken. Claiming requires
an identity and does not change the issue's status.

In a fresh project, `init --agents` creates shared instructions in `AGENTS.md`
and a `CLAUDE.md` import. Existing instructions are preserved.

**Work plans** live at `.issues/work/ISS-001.md`. Update checkpoints, decisions,
discoveries, Current, and Next as work progresses. Running `start` again resumes
an existing plan without overwriting it. It refuses blocked, closed, or
someone else's issues unless you explicitly use `--anyway` for blockers or
`--take` for ownership and reopening.

Use `issue next --compact` or `issue start ISS-001 --compact` for a shorter plan
summary. Read the full plan when recovering context; `next --compact` cannot be
combined with `--json`. `issue check --plans` reports plan progress.

**Event logs** record observations separately from the editable plan:

```bash
issue event ISS-001 "Worker started" --type lifecycle
issue event ISS-001 --json
```

Events are appended to `.issues/work/ISS-001.events.jsonl`. Use `--stdin` to
record piped output instead of a text argument.

## Configuration

Commands find `.issues/` by walking up from the current directory. `init` always
creates a tracker in the current directory.

| Environment variable | Purpose | Default |
| --- | --- | --- |
| `ISSUES_DIR` | Use a specific tracker directory, bypassing discovery | Nearest `.issues/` |
| `ISSUE_PREFIX` | Letters used for newly created IDs | `ISS` |
| `ISSUE_USER` | Identity for claims and work selection | `git config user.name` |

For example, set an agent identity with `export ISSUE_USER=agent-1` on macOS/Linux
or `$env:ISSUE_USER = "agent-1"` in PowerShell.

## File format

An issue is a Markdown document with flat `key: value` frontmatter:

```markdown
---
id: ISS-001
status: open
created_at: 2026-09-11T10:00:00+06:00
priority: high
labels: auth, bug
---
# Fix login redirect

The session cookie disappears after sign-in.
```

Optional metadata includes `updated_at`, `assignee`, and `blocked_by`. Labels and
blocker IDs are comma-separated; resolution evidence is a JSON array. Values
occupy one printable line. Write files as UTF-8 with LF line endings; CRLF is
accepted on read. Unknown frontmatter keys survive CLI edits.

You can edit files directly. Run `issue check` afterwards to catch malformed
metadata, missing references, dependency cycles, and damaged work artifacts.

## Stability

CLIIT is currently **0.1.0**. These interfaces are maintained compatibility
contracts, including before 1.0:

- **Issue files:** existing field names and meanings stay stable; absent optional
  fields stay absent, and unknown frontmatter keys are preserved.
- **JSON output:** existing keys and types stay stable; additional keys may appear.
  `list`, `search`, `check`, and event reads return arrays; `view`, `next`, and
  `brief` return objects on success. Optional issue fields may be absent.
  Diagnostics go to stderr.
- **Exit codes:** an empty filter result is `0`; a lookup with no result or a
  refused write is `1`. A partially successful batch write also returns `1`.
- **Configuration:** the three environment variables above keep their meanings.

Human-readable output, stderr wording, work-plan and event-log file formats, and
internal Python modules are not stable APIs. Use the CLI and `--json` for integrations.

<a id="non-goals"></a>

## Scope

CLIIT is built for a backlog shared through one repository. It works offline
and outside Git, but committed history requires Git. There is no hosted UI,
notification service, or synchronization with GitHub Issues.

> [!IMPORTANT]
> IDs are unique within one working copy, not across clones or forks. Coordinate
> issue creation across branches; pulling first does not prevent simultaneous
> allocations in separate clones.

<a id="reporting-a-bug-or-asking-a-question"></a>

For bugs and questions, use [GitHub Issues](https://github.com/NotYourBurger/CLIIT/issues).
For security reports, see [SECURITY.md](SECURITY.md). Project setup and the pull
request workflow are in [CONTRIBUTING.md](CONTRIBUTING.md).
