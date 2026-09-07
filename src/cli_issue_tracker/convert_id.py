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
    # ponytail: this directory scan sees one worktree, so concurrent worktrees
    # can allocate the same id. Git makes that collision loud as add/add and
    # `issue check` catches renamed residue; if allocation itself must prevent
    # it, replace this with a shared atomic counter outside the worktrees.
    for name in os.listdir(issues_dir):
        stem, ext = os.path.splitext(name)
        head, _, num = stem.partition("-")
        if ext == ".md" and head == prefix and num.isdigit():
            nums.append(int(num))
    return f"{prefix}-{max(nums, default=0) + 1:03d}"


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
    print("ok")
