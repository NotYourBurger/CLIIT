"""Round trip checks for the issue file format.

parse_issue and write_issue must be exact inverses: parse -> write -> parse
gives back the same dict. A parser bug here does not raise - it returns a wrong
dict that write_issue then persists over the file, so this is the one path in
the codebase that can silently lose your writing.

Run: uv run python tests/test_storage.py
"""

import os
import shutil
import tempfile

from helpers import REPO
from cli_issue_tracker.storage import issues_dir, parse_issue, write_issue

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
    return parse_issue(write_issue(issue))


def stable(issue):
    """Everything a rewrite must preserve. updated_at is excluded because
    write_issue restamps it on purpose - that is the one field allowed to
    differ between a dict and its own round trip."""
    return {key: value for key, value in issue.items() if key != "updated_at"}


if __name__ == "__main__":
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        issues = os.path.join(tmp, ".issues")
        os.makedirs(issues)
        # $ISSUES_DIR is what keeps this test off the real .issues/ - it is
        # checked before the walk up, so pointing the tool at a scratch
        # directory no longer means chdir-ing into one.
        os.environ["ISSUES_DIR"] = issues
        try:

            def write_raw(name, text, newline="\n"):
                path = os.path.join(issues, name)
                with open(path, "w", encoding="utf-8", newline=newline) as file:
                    file.write(text)
                return path

            def raw_bytes(path):
                with open(path, "rb") as file:
                    return file.read()

            # 1. A real issue file off disk survives a rewrite, and a second
            #    rewrite changes nothing more (idempotent, not just stable once).
            real = os.path.join(issues, "ISS-003.md")
            shutil.copyfile(os.path.join(REPO, ".issues", "ISS-003.md"), real)
            issue = parse_issue(real)
            assert issue is not None, "ISS-003.md no longer parses as an issue"
            assert "updated_at" not in issue, "ISS-003.md on disk predates updated_at"
            assert stable(round_trip(issue)) == stable(issue), "ISS-003 changed on rewrite"
            assert stable(round_trip(round_trip(issue))) == stable(issue), "rewrite is not idempotent"

            # An old file has no updated_at and must still parse - requiring it
            # would drop every pre-existing issue out of `issue list`. The first
            # rewrite is what fills it in.
            assert round_trip(issue)["updated_at"], "a rewrite did not stamp updated_at"

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
            assert stable(round_trip(got)) == stable(got), "the nasty body is not stable across a rewrite"

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
            assert stable(round_trip(extra)) == stable(extra), "an unknown frontmatter field was dropped on rewrite"

            # The four documented keys keep their documented order and any
            # extras follow, so a rewrite does not reshuffle every file in the
            # repo. title comes from the body heading, not the frontmatter, so
            # it must not leak back out as a duplicate key.
            extra["status"] = "closed"
            with open(write_issue(extra), encoding="utf-8") as file:
                head = file.read().splitlines()[:7]
            assert head == [
                "---",
                "id: ISS-903",
                "status: closed",
                "created_at: x",
                f"updated_at: {extra['updated_at']}",
                "assignee: tahmid",
                "---",
            ], head

            # 5. Line endings are part of the format, so they are part of the
            #    round trip. A file hand-edited on Windows arrives as CRLF and
            #    must still parse - reads keep their translation for exactly
            #    that - but what goes back is LF, because `join_file` writes
            #    "\n" and the tool must not be the one thing in the repo
            #    disagreeing with every editor about it.
            crlf = write_raw(
                "ISS-904.md",
                "---\r\nid: ISS-904\r\nstatus: open\r\ncreated_at: x\r\n---\r\n\r\n"
                "# Typed in Notepad\r\n\r\nTwo lines,\r\nboth of them CRLF.\r\n",
                newline="",
            )
            assert b"\r\n" in raw_bytes(crlf), "the fixture is not actually CRLF"
            hand_edited = parse_issue(crlf)
            assert hand_edited is not None, "a hand-edited CRLF file no longer parses"
            assert hand_edited["title"] == "Typed in Notepad", hand_edited
            assert hand_edited["body"] == "# Typed in Notepad\n\nTwo lines,\nboth of them CRLF.", (
                "CR survived into the body"
            )
            after = raw_bytes(write_issue(hand_edited))
            assert b"\r" not in after, "a rewrite kept CRLF"
            assert stable(parse_issue(crlf)) == stable(hand_edited), "the CRLF round trip changed it"

            # And every write goes out the same way, including one whose text
            # never had a CR in it - that is the write text mode used to
            # translate behind us.
            assert b"\r" not in raw_bytes(write_issue(nasty)), "write_issue emitted CRLF"

            # 6. issues_dir walks up, so every command works from a
            #    subdirectory, and $ISSUES_DIR wins over the walk - which is
            #    what every check above relies on.
            del os.environ["ISSUES_DIR"]
            deep = os.path.join(tmp, "src", "pkg")
            os.makedirs(deep)
            os.chdir(deep)
            assert issues_dir() == issues, "did not walk up to the parent .issues/"
            os.environ["ISSUES_DIR"] = os.path.join(tmp, "elsewhere")
            assert issues_dir() != issues, "$ISSUES_DIR did not win over the walk"
            del os.environ["ISSUES_DIR"]

            # With no .issues/ anywhere the walk has to stop at the filesystem
            # root rather than spin forever on dirname(root) - reaching the next
            # line at all is the check.
            os.chdir(tempfile.gettempdir())
            issues_dir()

        finally:
            os.chdir(original)
            os.environ.pop("ISSUES_DIR", None)
    print("ok")
