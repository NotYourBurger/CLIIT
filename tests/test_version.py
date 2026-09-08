"""`issue --version`, and the packaging metadata a stranger's bug report needs.

The seam is the command line rather than a function returning a string: a
helper would pass while the flag was unwired, and the flag is the whole point
(ISS-046). The expected version is read out of pyproject.toml here and out of
importlib.metadata there, because asking the code for the answer it just
produced is a check that cannot fail.
"""

import os
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typer.testing import CliRunner

from cli_issue_tracker.cli import app
from helpers import REPO


def pyproject():
    with open(os.path.join(REPO, "pyproject.toml"), "rb") as file:
        return tomllib.load(file)["project"]


def demo():
    project = pyproject()

    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert project["version"] in result.output, result.output

    # The installed distribution, not just the source tree - importlib.metadata
    # reads what the build backend wrote, so a version bumped in one place and
    # not the other is exactly what this catches.
    from importlib.metadata import version

    assert version("cli-issue-tracker") == project["version"]

    # The other half of ISS-046, and the half with the legal consequence: a
    # repo with no LICENSE reads as all rights reserved however public it is.
    # Asserted here rather than left to a reader because a metadata key is
    # exactly the kind of thing a later edit drops without noticing.
    assert os.path.exists(os.path.join(REPO, "LICENSE"))
    assert project["license"] == "MIT"
    assert "LICENSE" in project["license-files"]
    assert "your description" not in project["description"]
    assert project["urls"]["Issues"], project["urls"]

    print("ok")


if __name__ == "__main__":
    demo()
