"""`issue --version`, and the packaging metadata a stranger's bug report needs.

The seam is the command line rather than a function returning a string: a
helper would pass while the flag was unwired, and the flag is the whole point
(ISS-046). The expected version is read out of pyproject.toml here and out of
importlib.metadata there, because asking the code for the answer it just
produced is a check that cannot fail.
"""

import os
import sys

try:
    import tomllib
except ModuleNotFoundError:  # 3.10, the floor - see demo()
    tomllib = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typer.testing import CliRunner

from cli_issue_tracker.cli import app
from helpers import REPO


def pyproject():
    with open(os.path.join(REPO, "pyproject.toml"), "rb") as file:
        return tomllib.load(file)["project"]


def demo():
    # The installed distribution, not just the source tree - importlib.metadata
    # reads what the build backend wrote, so a version bumped in one place and
    # not the other is exactly what this catches.
    from importlib.metadata import version

    installed = version("cliit")

    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert installed in result.output, result.output

    # pyproject is the second, independent source. tomllib is 3.11 and the
    # floor is 3.10 (ISS-048), so on the floor there is no TOML reader in the
    # stdlib. What is above is what an interpreter can be wrong about - the
    # flag wired to the metadata the build wrote - and what is below is a
    # question about the file, which the other three rows of the matrix
    # answer. Cheaper than this file growing a TOML parser to ask it a fourth
    # time.
    if tomllib is None:
        print("ok (no tomllib)")
        return

    project = pyproject()
    assert installed == project["version"]

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
