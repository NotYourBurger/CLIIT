# Security

## Reporting a vulnerability

**Email <tahmidkhanofficial@gmail.com>.** Do not open a GitHub issue for it.
[Reporting a bug or asking a
question](README.md#reporting-a-bug-or-asking-a-question) sends everything
else to the public tracker on purpose; this is the one thing that should not
arrive there first, because filing it is publishing it.

Include what you would want if you were reading it: what an attacker
controls, what they get, and the shortest thing that shows it. `issue
--version`, your OS and a `.issues/` file that triggers it are usually the
whole report.

One person reads that address. Expect an acknowledgement within a week and a
fix or an explicit "this is not a vulnerability, here is why" after it. If a
week passes with nothing, assume the mail was lost rather than ignored and
send it again.

## What counts as one here

This is a local CLI over a directory of Markdown files. It has no server, no
network calls and no privileges of its own, so the interesting boundary is
not a login — it is **content that arrives from somewhere else and is then
parsed, joined onto a path, or handed to git.** A `.issues/` directory comes
in over `git pull` from whoever else works on the repo, and a fork's pull
request can edit the files in it.

In scope, and the shapes worth looking at:

- **A value escaping the field it was given to.** A newline in a label is a
  new frontmatter line, and the issue it lands in is closed and assigned by
  somebody who never ran `close`. `clean_set` refuses it and
  [`tests/test_injection.py`](tests/test_injection.py) is the standing check;
  a way past it is a vulnerability.
- **A value escaping `.issues/`.** An id becomes a path and `ISSUE_PREFIX`
  becomes a filename. `storage.require_id` and `create`'s letters-only check
  are the two doors; a write outside `.issues/` is a vulnerability.
- **Anything reaching a shell.** The six git calls go through
  `storage.run_git` as an argument list with no shell. An argument that
  becomes a flag, or a path that becomes a command, counts.
- **Losing a file that has no other copy.** The body of an issue is not in
  git until it is committed. Every rewrite goes through
  `storage.write_atomic` for exactly that reason, and a crash or a race that
  leaves a truncated or empty issue file is in scope even though nobody
  attacked anything.
- **Terminal escape sequences** in issue content reaching your terminal
  through a rendered table.

Not in scope, because they are the design and are written down as such:

- **`.issues/` is trusted the way your working tree is trusted.** Somebody
  who can write files in your checkout can already write anything; the tool
  is not a sandbox over your own repo.
- **The write lock is advisory and one repo wide.** Two agents in one
  worktree are ordered by `.issues/.lock`; independent clones have no shared
  lock, but their generated IDs do not require one.
- Anything that needs the attacker to already be running as you.

## Supported versions

There is no release yet. The tip of `main` is the only version there is, and
a fix lands there. When the first release is cut this section says which
versions get one.
