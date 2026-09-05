"""Round trip checks for the issue file format.

parse_issue and write_issue must be exact inverses: parse -> write -> parse
gives back the same dict. A parser bug here does not raise - it returns a wrong
dict that write_issue then persists over the file, so this is the one path in
the codebase that can silently lose your writing.

Run: uv run python test_storage.py
"""

import os
import shutil
import tempfile

from cli_issue_tracker.storage import parse_issue, write_issue

REPO = os.path.dirname(os.path.abspath(__file__))

# Everything the parser has ever got wrong, in one body: a second "# " heading
# (title must be first-wins), a bare "---" rule (must not read as the end of the
# frontmatter), a table, a fenced block containing a "#" comment, a blockquote,
# and non-ASCII text, which is only safe while both ends open the file as utf-8.
NASTY_BODY = """# The real title

Prose before anything weird happens.

Unicode survives too — a café, a naïve résumé, and a ▌ half block.

---

## A heading after a horizontal rule

# Not the title - the first heading wins

| Current status | Command            | Result   |
| -------------- | ------------------ | -------- |
| `open`         | `issue close <id>` | `closed` |

```python
# a hash inside a fence is a comment, not a heading
x = 1
```

> A blockquote with a --- inside it
> and a second line."""


def round_trip(issue):
    """Write the issue out and read it straight back."""
    path = write_issue(issue)
    assert path is not None, "write_issue found no .issues/ - the setup is wrong"
    return parse_issue(path)


if __name__ == "__main__":
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        issues = os.path.join(tmp, ".issues")
        os.makedirs(issues)
        # write_issue resolves .issues/ from the cwd, so the test has to move
        # into a scratch repo - never write against the real .issues/.
        os.chdir(tmp)
        try:

            def write_raw(name, text):
                path = os.path.join(issues, name)
                with open(path, "w", encoding="utf-8") as file:
                    file.write(text)
                return path

            # 1. A real issue file off disk survives a rewrite, and a second
            #    rewrite changes nothing more (idempotent, not just stable once).
            real = os.path.join(issues, "ISS-003.md")
            shutil.copyfile(os.path.join(REPO, ".issues", "ISS-003.md"), real)
            issue = parse_issue(real)
            assert issue is not None, "ISS-003.md no longer parses as an issue"
            assert round_trip(issue) == issue, "ISS-003 changed on rewrite"
            assert round_trip(round_trip(issue)) == issue, "rewrite is not idempotent"

            # 2. The nasty body: every construct that has broken the parser.
            nasty = {
                "id": "ISS-900",
                "status": "in-progress",
                "created_at": "2026-09-05T05:39:08+06:00",
                "body": NASTY_BODY,
            }
            got = round_trip(nasty)
            assert got["body"] == NASTY_BODY, "body did not survive the round trip"
            assert got["title"] == "The real title", "a later '# ' heading overwrote the title"
            assert got["status"] == "in-progress", "a '---' in the body ended the frontmatter early"
            assert got["created_at"] == nasty["created_at"]
            assert round_trip(got) == got, "the nasty body is not stable across a rewrite"

            # 3. Files we did not write are skipped, not half-parsed. list_issues
            #    walks the whole directory, so None here is what keeps junk out.
            assert parse_issue(write_raw("empty.md", "")) is None
            assert parse_issue(write_raw("plain.md", "# Just a note\n")) is None, "no frontmatter"
            assert parse_issue(write_raw("open.md", "---\nid: ISS-901\n")) is None, "unclosed fence"
            assert parse_issue(
                write_raw("bare.md", "---\nid: ISS-902\nstatus: open\ncreated_at: x\n---\n\nno heading\n")
            ) is None, "a body with no '# ' heading has no title"

            # 4. A frontmatter field we do not know about is still ours to keep.
            #    Nothing in the tool writes one, but a human editing the file by
            #    hand can, and `issue set` must not eat it on the next rewrite.
            extra = parse_issue(
                write_raw(
                    "ISS-903.md",
                    "---\nid: ISS-903\nstatus: open\ncreated_at: x\nassignee: tahmid\n---\n\n# Has an assignee\n",
                )
            )
            assert extra["assignee"] == "tahmid", "parse should keep unknown frontmatter fields"
            assert round_trip(extra) == extra, "an unknown frontmatter field was dropped on rewrite"

            # The three documented keys keep their documented order and any
            # extras follow, so a rewrite does not reshuffle every file in the
            # repo. title comes from the body heading, not the frontmatter, so
            # it must not leak back out as a duplicate key.
            extra["status"] = "closed"
            with open(write_issue(extra), encoding="utf-8") as file:
                head = file.read().splitlines()[:6]
            assert head == [
                "---",
                "id: ISS-903",
                "status: closed",
                "created_at: x",
                "assignee: tahmid",
                "---",
            ], head

        finally:
            os.chdir(original)
    print("ok")
