import os


def next_id(issues_dir: str) -> str:
    """Next free ISS-NNN id: one past the highest already in issues_dir."""
    nums = []
    for name in os.listdir(issues_dir):
        stem, ext = os.path.splitext(name)
        prefix, _, num = stem.partition("-")
        if ext == ".md" and prefix == "ISS" and num.isdigit():
            nums.append(int(num))
    return f"ISS-{max(nums, default=0) + 1:03d}"


if __name__ == "__main__":
    import tempfile

    def touch(d, name):
        open(os.path.join(d, name), "w").close()

    with tempfile.TemporaryDirectory() as d:
        assert next_id(d) == "ISS-001", "empty dir starts at 001"
        touch(d, "ISS-001.md")
        assert next_id(d) == "ISS-002"
        touch(d, "ISS-009.md")
        assert next_id(d) == "ISS-010", "counts from the max, not the file count"
        touch(d, "notes.txt")
        touch(d, "ISS-abc.md")
        assert next_id(d) == "ISS-010", "non-issue files are ignored"
    print("ok")
