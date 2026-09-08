<!--
CONTRIBUTING.md has the whole of this. The three lines below are the ones a
pull request here gets sent back for.
-->

## What changed

<!-- One or two sentences. The issue's own words are fine. -->

Issue:

## Checklist

- [ ] `uv run python tests/all.py` is green
- [ ] New behaviour has its own `tests/test_<thing>.py`
- [ ] This adds no new `.issues/*.md` file — ids are allocated on trunk only,
      so two forks both allocate `ISS-058` and git merges them with nothing to
      show you. Editing a file that already exists is fine.
- [ ] No linter, formatter or test framework added. Not an oversight; see
      CONTRIBUTING.md.
