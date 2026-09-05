"""Every byte this tool reads or writes is UTF-8, checked by reading the source.

The default encoding on this machine is cp1252. Three separate bugs have been
the same mistake: a call that touches text and takes the locale default instead
of being told UTF-8. Each was fixed where it was found, which does nothing about
the fourth. This walks the source and fails on any new one.

ast rather than grep: "encoding" appears in comments and in the fix messages,
and a grep counts those as guarded.

Run: uv run python tests/test_encoding.py
"""

import ast
import os

from helpers import REPO


def sources():
    for root, dirs, names in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__")]
        for name in names:
            if name.endswith(".py"):
                yield os.path.join(root, name)


def keyword(call, name):
    return next((k.value for k in call.keywords if k.arg == name), None)


def is_true(node):
    return isinstance(node, ast.Constant) and node.value is True


def unguarded(path):
    """Calls in one file that decode or encode text without saying how."""
    with open(path, "r", encoding="utf-8") as file:
        tree = ast.parse(file.read(), path)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or keyword(node, "encoding") is not None:
            continue

        # open() in text mode. Binary mode has no encoding to get wrong, and
        # the mode is the second positional argument or the `mode` keyword.
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            mode = node.args[1] if len(node.args) > 1 else keyword(node, "mode")
            binary = isinstance(mode, ast.Constant) and "b" in mode.value
            if not binary:
                yield node.lineno, "open() without encoding="

        # subprocess with text=True: same trap, and the one that bit ISS-013.
        # Bytes mode is fine - nothing is being decoded.
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("run", "check_output", "Popen"):
            if is_true(keyword(node, "text")) or is_true(keyword(node, "universal_newlines")):
                yield node.lineno, f"subprocess {node.func.attr}(text=True) without encoding="


def demo():
    found = [
        f"{os.path.relpath(path, REPO)}:{line}: {why}"
        for path in sources()
        for line, why in unguarded(path)
    ]
    assert not found, "locale default will be used here:\n" + "\n".join(found)

    # The console is the fourth way in: both streams have to be told, and
    # stderr is the one that was missed - it mangles quietly rather than
    # raising, so nothing else would catch it.
    with open(os.path.join(REPO, "src", "cli_issue_tracker", "cli.py"), encoding="utf-8") as file:
        cli = file.read()
    for stream in ("stdout", "stderr"):
        assert f'sys.{stream}.reconfigure(encoding="utf-8")' in cli, f"sys.{stream} not set to UTF-8"

    print("ok")


if __name__ == "__main__":
    demo()
