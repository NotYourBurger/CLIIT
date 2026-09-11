"""Make a tracker here, and tell the agent how to work in it.

The rule is the second half on purpose. A tool whose whole guarantee is a
sentence an agent has to follow has to put that sentence where the agent
actually reads - and `init` is the one moment this tool is allowed to write
outside `.issues/`."""

import os
import sys

from cli_issue_tracker.plan import rule_text
from cli_issue_tracker.storage import issues_dir
from cli_issue_tracker.storage import local_issues_dir

# Whichever of these the repo keeps. Both when it keeps both - two agents
# reading two files is exactly the case one of them exists for.
PROJECT_FILES = ("CLAUDE.md", "AGENTS.md")

# Claude Code does not discover AGENTS.md itself. When --agents asks us to
# establish the convention from scratch, this import keeps AGENTS.md as the
# single shared copy while putting it on Claude's documented discovery path.
CLAUDE_IMPORT = "@AGENTS.md\n"
AGENTS_POINTER = """# Agent instructions

Read `CLAUDE.md` before working in this repository. It contains the shared
project instructions and issue workflow.
"""

HEADING = "## Work plans"

TOOLS_HEADING = "## Issue tracker"

# The rule is a procedure; this is the way to run it. Deliberately not part of
# `RULE`, which is shared with every seeded plan through `RULE[4:8]` - a line
# about which command to type would leak into the reminder in each one, where
# the reader is already inside the tool. Four verbs and no more: the ones an
# agent needs to get from "there is work" to "it is closed", with `--help` for
# a list this file has no business keeping in sync.
TOOLS = """The issues are the Markdown files in `.issues/`, one per issue, read
and written with the `issue` command:

- `issue next` - the one issue to work on now, with where its plan stands
- `issue start ISS-NNN` - claim it and seed `.issues/work/ISS-NNN.md`
- `issue check` - what is wrong with the files on disk
- `issue close ISS-NNN --completed -m "what changed" --verified "how you know"`

`issue --help` lists the rest."""


def write_rule(agents=False):
    """Append the workflow rule and the tool block to the project files, once.

    Appended rather than written: these files are the repo's, not ours, and the
    one thing worse than not writing the rule is truncating the instructions
    already in there. The check is each block's own first line - re-running
    `init` after a pull is normal, and a rule that stacks up nine times is a
    file nobody finishes reading.

    Nothing is created unless --agents asks for the convention. In that case
    AGENTS.md carries the shared instructions and CLAUDE.md imports it: Codex
    discovers the former, while Claude Code documents only the latter. The
    import is the seam between the two names and leaves one body to maintain.

    Existing files remain authoritative. We append to whichever ones a repo
    already keeps, and --agents fills in a missing discovery file without
    replacing or redirecting instructions that were already there."""
    names = [name for name in PROJECT_FILES if os.path.isfile(os.path.join(os.getcwd(), name))]
    if not names:
        if not agents:
            print(
                "No CLAUDE.md or AGENTS.md here, so the agent instructions were not written"
                " - `issue init --agents` configures Codex and Claude Code",
                file=sys.stderr,
            )
            return
        names = ["AGENTS.md"]

    if agents:
        claude_path = os.path.join(os.getcwd(), "CLAUDE.md")
        agents_path = os.path.join(os.getcwd(), "AGENTS.md")
        if names == ["CLAUDE.md"]:
            # The repo already chose CLAUDE.md as its source. Point Codex at
            # it rather than copying the body into a second file that drifts.
            with open(agents_path, "w", encoding="utf-8", newline="\n") as file:
                file.write(AGENTS_POINTER)
            print("Codex pointer added to AGENTS.md")
        elif "AGENTS.md" not in names:
            names.append("AGENTS.md")
        if not os.path.isfile(claude_path):
            with open(claude_path, "w", encoding="utf-8", newline="\n") as file:
                file.write(CLAUDE_IMPORT)
            print("Claude Code import added to CLAUDE.md")
        elif "CLAUDE.md" not in names:
            names.append("CLAUDE.md")

    for name in names:
        path = os.path.join(os.getcwd(), name)
        # Not `open(path)`: --agents names a file that is not there yet, and
        # the append below is what creates it.
        text = ""
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as file:
                text = file.read()
        # A CLAUDE.md created above already imports the blocks from AGENTS.md.
        # Repeating them below the import would put the same instructions in
        # Claude's context twice and bring the drift problem back.
        if name == "CLAUDE.md" and text == CLAUDE_IMPORT:
            continue
        for heading, body in ((HEADING, rule_text()), (TOOLS_HEADING, TOOLS)):
            if body.splitlines()[0] in text:
                continue
            # A blank line between us and whatever was there - but not at
            # the top of a file `--agents` has just brought into being.
            block = ("\n" if text else "") + f"{heading}\n\n{body}\n"
            with open(path, "a", encoding="utf-8", newline="\n") as file:
                file.write(block)
            text += block
            print(f"{heading[3:].capitalize()} added to {name}")


def init(agents=False):
    # The one command that does not walk up: `issue init` means "make one here".
    path = local_issues_dir()
    if os.path.isdir(path):
        print("Project is already Initialized")
        # Still the rule: re-running `init` is how a repo that predates it gets
        # the rule, and there is no second command to remember.
        write_rule(agents)
        return

    # But say so if there is one above us. Two trackers allocate ids
    # independently, so both hand out the same ISS-NNN and neither half ever
    # sees the other - the point is that it is never silent.
    found = issues_dir()
    if os.path.isdir(found):
        print(f"Warning: an existing tracker at {found} - making a second one here", file=sys.stderr)

    os.mkdir(path)
    print("Feel free to explore .issues folder")
    write_rule(agents)
