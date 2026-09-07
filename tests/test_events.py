"""Checks for `issue event` and the append-only run event log.

The property this exists for is that a process killed mid-write can lose at
most the line it was writing, never one already on disk - so this checks that
an append never rewrites what came before it, that a malformed line does not
take the rest of the file down with it, and that `issue check` notices both a
stray log and a line that will not parse. It also checks the two entry points
that do not go through a normal argument: `--stdin`, and reading the log back
by omitting TEXT.

Run: uv run python tests/test_events.py
"""

import io
import json
import os
import sys
import tempfile

from helpers import run
from cli_issue_tracker.check import check
from cli_issue_tracker.events import append_event
from cli_issue_tracker.events import event_command
from cli_issue_tracker.events import events_path
from cli_issue_tracker.events import read_events
from cli_issue_tracker.issues import create_issue


def raw_bytes(path):
    with open(path, "rb") as file:
        return file.read()


def with_stdin(text, function, *args, **kwargs):
    """Run a command with sys.stdin replaced, the way `run` replaces the two
    output streams - `--stdin` is the one path here that reads instead of
    printing, so it needs the input side faked instead."""
    original = sys.stdin
    sys.stdin = io.StringIO(text)
    try:
        return run(function, *args, **kwargs)
    finally:
        sys.stdin = original


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ISSUES_DIR"] = tmp
        try:
            run(create_issue, "Claim race probe", "...", "medium")

            # Appending writes nothing to stdout - the point is the file, and
            # a command that also prints on the write path is one an agent
            # has to remember to ignore in a script.
            code, out, err = run(event_command, "ISS-001", "worker started", "lifecycle")
            assert code is None and out == "" and err == "", (code, out, err)

            path = events_path("ISS-001")
            assert os.path.isfile(path), path
            assert b"\r" not in raw_bytes(path), "an appended event is CRLF"

            entries = read_events("ISS-001")
            assert len(entries) == 1, entries
            assert entries[0]["type"] == "lifecycle", entries
            assert entries[0]["text"] == "worker started", entries
            assert "at" in entries[0], entries

            # A second append lands after the first rather than replacing it -
            # the whole property this log exists for.
            run(event_command, "ISS-001", "worker killed", "lifecycle")
            entries = read_events("ISS-001")
            assert [entry["text"] for entry in entries] == [
                "worker started",
                "worker killed",
            ], entries

            # --type defaults to "note", and any value at all is accepted -
            # there is no closed vocabulary to reject against.
            run(event_command, "ISS-001", "a plain note")
            assert read_events("ISS-001")[-1]["type"] == "note", read_events("ISS-001")

            # --stdin reads TEXT from standard input instead of the argument,
            # so a probe's real multi-line stdout goes in whole rather than
            # through shell quoting.
            probe_output = "line one\nline two\n"
            code, out, err = with_stdin(
                probe_output, event_command, "ISS-001", None, "probe", False, True
            )
            assert code is None, (code, out, err)
            piped = read_events("ISS-001")[-1]
            assert piped["type"] == "probe" and piped["text"] == probe_output, piped

            # TEXT and --stdin together is refused before anything is written -
            # ambiguous intent must not silently pick one.
            before = read_events("ISS-001")
            code, out, err = run(
                event_command, "ISS-001", "text", "note", False, True
            )
            assert code == 1, (code, out, err)
            assert read_events("ISS-001") == before, "a rejected call still wrote"

            # An unknown issue writes nothing - the same "validate before
            # writing" rule every other command follows.
            code, out, err = run(event_command, "ISS-404", "text")
            assert code == 1 and "ISS-404" in err, (code, out, err)
            assert not os.path.isfile(events_path("ISS-404")), "a refused call still wrote"

            # No TEXT and no --stdin reads the log back instead of appending
            # to it.
            code, out, err = run(event_command, "ISS-001")
            assert code is None, (code, out, err)
            assert "worker started" in out, out
            assert "probe" in out, out
            assert read_events("ISS-001") == before, "reading the log appended to it"

            # --json exposes the same entries structurally.
            code, out, err = run(event_command, "ISS-001", None, "note", True)
            assert json.loads(out) == before, out

            # A log that does not exist yet reads back empty, not an error -
            # "absent means absent", same as a missing plan section.
            run(create_issue, "Never started", "...", "low")
            assert read_events("ISS-002") == [], read_events("ISS-002")
            code, out, err = run(event_command, "ISS-002")
            assert code is None and out == "", (code, out, err)

            # A malformed line does not take the rest of the file with it -
            # the reader skips it and keeps every entry that does parse.
            with open(events_path("ISS-001"), "a", encoding="utf-8", newline="\n") as log_file:
                log_file.write("not json at all\n")
            run(event_command, "ISS-001", "after the bad line", "note")
            entries = read_events("ISS-001")
            assert entries[-1]["text"] == "after the bad line", entries
            assert len(entries) == len(before) + 1, entries

            # `issue check` finds what the silent reader will not: the
            # malformed line by number, and an event log left behind for an
            # issue that no longer has a file beside it.
            code, out, err = run(check)
            assert code == 1, (code, out, err)
            assert "not valid JSON" in err, err

            # ISS-002 never had a log; write one directly, the way a renamed
            # or deleted issue file would leave one behind.
            os.remove(os.path.join(tmp, "ISS-002.md"))
            append_event("ISS-002", "orphaned")
            code, out, err = run(check)
            assert code == 1, (code, out, err)
            assert "no issue beside it" in err, err
        finally:
            os.environ.pop("ISSUES_DIR", None)
    print("ok")


if __name__ == "__main__":
    demo()
