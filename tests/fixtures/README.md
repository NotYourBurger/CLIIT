A frozen `.issues/` directory, checked in.

`test_check` points `ISSUES_DIR` here and asserts `issue check` exits clean;
`test_storage` copies `ISS-003.md` out of here as its round-trip fixture. Both
used to read the repo's own `.issues/`, which made the suite's result depend on
repository state: filing an issue while working - which this repo's workflow
tells you to do - could fail a test about somebody else's change, and a clone
where ISS-003 had been renamed failed outright (ISS-049).

So these files are the corpus, and they do not change when the tracker does.
They are real prose on purpose - a table, a fenced block, a blockquote, a bare
`---` rule, non-ASCII - because what the whole-directory pass is really asking
is whether a parser change has started eating writing. Add a file here when a
new shape of frontmatter or body becomes possible, not when a new issue is
filed.

`README.md` has no frontmatter, so `parse_issue` returns None for it and
`check` skips it - which is itself the rule that keeps a stray note out of
`issue list`, tested from the other side in `test_storage`.
