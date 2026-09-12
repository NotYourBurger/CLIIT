import os
import secrets
import time

from cli_issue_tracker.storage import id_prefix


ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
EPOCH = 1577836800  # 2020-01-01T00:00:00Z


def generated_id() -> str:
    """One sortable, offline-unique id candidate.

    A directory can only describe the clone it belongs to. Time preserves the
    useful creation ordering and four random base36 characters distinguish
    independent clones; reservation below keeps the rare collision harmless."""
    seconds = int(time.time()) - EPOCH
    encoded = ""
    while seconds:
        seconds, digit = divmod(seconds, 36)
        encoded = ALPHABET[digit] + encoded
    timestamp = encoded.rjust(6, "0")
    random = "".join(secrets.choice(ALPHABET) for _ in range(4))
    return f"{id_prefix()}-{timestamp}{random}"


def reserve_id(issues_dir: str) -> str:
    """Allocate an id and claim its file in one step, so no other process can
    be handed the same one.

    The candidate is independent of its directory, so two offline clones do
    not allocate from the same observed state. O_EXCL makes its rare random
    collision retry instead of overwrite (ISS-039).

    What is left behind is a 0-byte `.md` until the caller writes the issue
    into it. Every reader here goes through `parse_issue`, which returns None
    for a file with no frontmatter, so an empty one is skipped rather than
    listed as a broken issue - the same answer they already give a stray file.
    A create that dies in that window leaves a burnt id and `issue check`
    reports the empty file, which is the visible half of the trade."""
    while True:
        id = generated_id()
        try:
            os.close(os.open(os.path.join(issues_dir, f"{id}.md"), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return id
        except FileExistsError:
            continue


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        first, second = reserve_id(d), reserve_id(d)
        assert first != second, "reservation handed out one id twice"
        assert first.split("-", 1)[1].islower(), first
        assert all(os.path.getsize(os.path.join(d, f"{id}.md")) == 0 for id in (first, second))
    print("ok")
