"""Checks generated IDs work without a shared issue directory.

Run: uv run python tests/test_id_scheme.py
"""

import os
import re
import tempfile

from cli_issue_tracker import convert_id
from cli_issue_tracker.convert_id import reserve_id
from cli_issue_tracker.storage import require_id


def demo():
    with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
        first_id, second_id = reserve_id(first), reserve_id(second)
        assert first_id != second_id, (first_id, second_id)
        assert re.fullmatch(r"ISS-[0-9a-z]{10}", first_id), first_id
        assert first_id.split("-", 1)[1] == first_id.split("-", 1)[1].lower(), first_id
        assert os.path.isfile(os.path.join(first, f"{first_id}.md"))
        assert os.path.isfile(os.path.join(second, f"{second_id}.md"))
    original_time = convert_id.time.time
    try:
        convert_id.time.time = lambda: convert_id.EPOCH + 1
        earlier = convert_id.generated_id()
        convert_id.time.time = lambda: convert_id.EPOCH + 2
        later = convert_id.generated_id()
    finally:
        convert_id.time.time = original_time
    assert earlier < later, (earlier, later)
    assert require_id("ISS-001") == "ISS-001"
    assert require_id("BUG-001") == "BUG-001"
    print("ok")


if __name__ == "__main__":
    demo()
