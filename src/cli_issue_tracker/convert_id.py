import os

from cli_issue_tracker.storage import id_prefix


def next_id(issues_dir: str) -> str:
    """Next free id: one past the highest already in issues_dir under the
    current prefix. Ids carrying some other prefix are counted separately, so
    switching prefixes does not renumber on top of the issues already there.

    One id space, because issues are the only thing this tool numbers - a work
    plan is named after the issue it belongs to and allocates nothing."""
    prefix = id_prefix()
    nums = []
    # A scan is a question about a moment, so this alone is not an allocation -
    # two processes ask it between either of them writing and both are told the
    # same number. `reserve_id` is what callers want; this stays because it is
    # the "what is next" half and the tests read it on its own.
    for name in os.listdir(issues_dir):
        stem, ext = os.path.splitext(name)
        head, _, num = stem.partition("-")
        if ext == ".md" and head == prefix and num.isdigit():
            nums.append(int(num))
    return f"{prefix}-{max(nums, default=0) + 1:03d}"


def reserve_id(issues_dir: str) -> str:
    """Allocate an id and claim its file in one step, so no other process can
    be handed the same one.

    `next_id` asks who is highest; between that answer and the write another
    process asks the same question and gets the same answer, and the second
    write lands on top of the first - two "has been created" lines, one file,
    one issue that never existed (ISS-039). The tracker lock would order the
    two, but O_EXCL is the stronger answer and the same three lines: the file
    is created empty, exclusively, and the loser gets `FileExistsError` and
    asks again. That holds across worktrees and machines, where a lock file
    under one `.issues/` does not.

    What is left behind is a 0-byte `.md` until the caller writes the issue
    into it. Every reader here goes through `parse_issue`, which returns None
    for a file with no frontmatter, so an empty one is skipped rather than
    listed as a broken issue - the same answer they already give a stray file.
    A create that dies in that window leaves a burnt id and `issue check`
    reports the empty file, which is the visible half of the trade."""
    while True:
        id = next_id(issues_dir)
        try:
            os.close(os.open(os.path.join(issues_dir, f"{id}.md"), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return id
        except FileExistsError:
            # Someone took it between the scan and the create. next_id will now
            # see their file and count past it.
            continue


if __name__ == "__main__":
    import tempfile

    def touch(d, name):
        open(os.path.join(d, name), "w", encoding="utf-8", newline="\n").close()

    with tempfile.TemporaryDirectory() as d:
        assert next_id(d) == "ISS-001", "empty dir starts at 001"
        touch(d, "ISS-001.md")
        assert next_id(d) == "ISS-002"
        touch(d, "ISS-009.md")
        assert next_id(d) == "ISS-010", "counts from the max, not the file count"
        touch(d, "notes.txt")
        touch(d, "ISS-abc.md")
        assert next_id(d) == "ISS-010", "non-issue files are ignored"

        # A different prefix numbers from its own ids, not from the ISS ones
        # sitting next to it - otherwise switching prefix skips 001-009 for
        # no reason, and switching back would collide.
        os.environ["ISSUE_PREFIX"] = "BUG"
        try:
            assert next_id(d) == "BUG-001", "a new prefix starts at 001"
            touch(d, "BUG-001.md")
            assert next_id(d) == "BUG-002"
            os.environ["ISSUE_PREFIX"] = "ISS"
            assert next_id(d) == "ISS-010", "BUG ids must not bump the ISS count"
        finally:
            os.environ.pop("ISSUE_PREFIX", None)

    # Reservation, which is the same allocation with the window shut. Two
    # callers asking before either writes is exactly the interleaving that
    # lost an issue, so it is asked for that way here: back to back, with
    # nothing written in between.
    with tempfile.TemporaryDirectory() as d:
        assert reserve_id(d) == "ISS-001"
        assert reserve_id(d) == "ISS-002", "a reserved id is not handed out twice"
        assert sorted(os.listdir(d)) == ["ISS-001.md", "ISS-002.md"]
        assert os.path.getsize(os.path.join(d, "ISS-001.md")) == 0, "reservation wrote content"

        # And it steps over a file it did not create, rather than truncating it.
        with open(os.path.join(d, "ISS-003.md"), "w", encoding="utf-8", newline="\n") as file:
            file.write("Alice's report")
        assert reserve_id(d) == "ISS-004"
        with open(os.path.join(d, "ISS-003.md"), encoding="utf-8") as file:
            assert file.read() == "Alice's report", "reservation clobbered an existing issue"
    print("ok")
