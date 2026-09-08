# Contributing

Thanks for looking. This is a small tool with a few strong opinions, and most
of them are cheaper to read here than to discover in review.

- [README.md](README.md) is the user-facing spec — what every command does.
- [CLAUDE.md](CLAUDE.md) is the architecture: which module may import which,
  and why each rule is there. It is written for a coding agent working in this
  repo, but it is the honest account of the design and worth reading before a
  change that moves code between layers.

Nothing below is repeated in either of those. If the two ever disagree with
this file, they win and this file is the bug.

## Three things to know before you open a pull request

**Bugs and questions go to [GitHub
Issues](https://github.com/NotYourBurger/cli-issue-tracker/issues)**, not to a
file in `.issues/`. It needs no clone and no fork.

**A pull request may edit an existing `.issues/*.md`, but must not create
one.** Ids are allocated on trunk only — an id is one past the highest one
visible, so two forks each allocate `ISS-058`, both files are valid, and git
merges them with nothing to show you. If your change needs an issue that does
not exist yet, open the GitHub issue and it will be filed on trunk first.
README's [Reporting a bug or asking a
question](README.md#reporting-a-bug-or-asking-a-question) has the reasoning.

**A vulnerability does not go to GitHub Issues either.**
[SECURITY.md](SECURITY.md) has the private address and the list of what counts
as one here. Everything else about how people are expected to behave is
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Setup

```bash
uv sync                       # installs, and puts `issue` on the path
uv run python tests/all.py    # every check; prints one line per file
uv run issue --version
```

Python 3.10 is the floor. There are three runtime dependencies — `typer`,
`rich` and `tzlocal` — and nothing else to install. Please do not add a fourth
without saying why in the issue first.

## The loop

Work is tracked in the tool it is a tool for. The whole of it, as commands:

```bash
uv run issue next                    # what to work on, already ranked
uv run issue start ISS-058           # claims it, sets in-progress, seeds a plan

# ... edit .issues/work/ISS-058.md as you go, not at the end ...

uv run python tests/all.py           # green before the commit, not after
git commit -m "ISS-058: what changed, in the issue's own words"

uv run issue close ISS-058 --completed \
  -m "what actually happened" \
  --commit "$(git rev-parse --short HEAD)" \
  --test "uv run python tests/all.py"
git commit -am "ISS-058: close it with its evidence"
```

`issue start` seeds `.issues/work/ISS-058.md`, a work plan you edit while you
work. Break the change into checkpoints and tick each one when it is done —
not at the end of the session, because sessions end at closed terminals and a
plan written at the end is a plan that is never written. Record a decision
when you make it, especially a rejected alternative; that is the half a diff
cannot show. The plan stays in `work/` after the issue closes, as the account
of how the change was built.

`issue close` requires evidence and refuses without it — `--commit`,
`--test`, `--pr` or `--verified`, repeatable. "It works" is not a resolution.

You do not have to run any of this to send a small fix. A typo or a one-line
bug is welcome as a plain pull request; the loop above is for a change big
enough that somebody would want to know later why it looks like that.

## Commits

One issue per commit, id first:

```
ISS-019: issue next - the one issue to work on now
```

The subject says what changed. If there is a reason worth keeping, the body
carries it — `git log --follow` on a file is this repo's whole audit trail,
for issues and for code alike, so a commit message is the only place some
decisions are ever written down.

## Tests

New behaviour lands with its own `tests/test_<thing>.py`. There is no test
framework here and none is wanted: each file is a script that asserts and
prints `ok`, and `tests/all.py` runs them all in subprocesses and exits
non-zero if any of them failed. That is the whole harness.

[`tests/test_version.py`](tests/test_version.py) is the smallest complete
example — a module docstring saying which seam is under test and why, a
`demo()` full of asserts, and `if __name__ == "__main__": demo()` at the
bottom. `tests/helpers.py` has `run()`, which calls a command and hands back
`(exit code, stdout, stderr)`, so the exit code and the stream a message went
to can both be asserted; both of those are part of the promised interface.

A check that needs a corpus of real issues reads `tests/fixtures/` and never
this repo's own `.issues/`. The suite has to pass on a clone whose tracker
belongs to somebody else, and filing an issue while working must not be able
to fail a check about somebody else's change.

Comments explain why, not what. The existing prose records rejected
alternatives; match that register rather than annotating the syntax.

## Things deliberately not here

**No linter and no formatter.** Not an oversight, and not a gap waiting to be
filled helpfully. The diff a formatter produces on its first run touches every
file and buries the actual change under it, and the style here is consistent
enough without one. Match the surrounding code instead.

**No test framework.** See above — `tests/all.py` is a `glob`, a loop and a
`subprocess.run`, and there is nothing pytest would do for it worth the
dependency.

**No new `.issues/` file in a pull request.** See the top of this file.

## What CI checks

[`.github/workflows/ci.yml`](.github/workflows/ci.yml), on every push and
pull request:

- the suite on Linux, macOS and Windows, on Python 3.10 through 3.13 — the
  matrix is the point, because the write lock forks on platform, filename
  lookup is case-blind on Windows only, and one machine here defaults to
  cp1252
- `issue check` over this repo's real `.issues/`, where the state under test
  is the branch that changed it
- the built wheel installing into a venv that has never seen the checkout,
  and its `issue` running there
- the whole suite again on a machine with no `git` on the PATH, because six
  places shell out to git and none of them may fail the command it is inside

Run `uv run python tests/all.py` before you push and the first of those four
is usually all you need to think about.

## License

By contributing you agree that your work is licensed under the
[MIT License](LICENSE), the same terms as the rest of the project.
