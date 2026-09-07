"""Every byte this tool reads or writes is spelled out, checked by reading the source.

The default encoding on this machine is cp1252 and the default line ending is
CRLF. Four separate bugs have been the same mistake: a call that touches text
and takes the platform default instead of being told. Each was fixed where it
was found, which does nothing about the fifth. This walks the source and fails
on any new one.

ast rather than grep: "encoding" appears in comments and in the fix messages,
and a grep counts those as guarded.

Run: uv run python tests/test_encoding.py
"""

import ast
import os
import tempfile

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
        if not isinstance(node, ast.Call):
            continue
        said_encoding = keyword(node, "encoding") is not None

        # open() in text mode. Binary mode has no encoding to get wrong, and
        # the mode is the second positional argument or the `mode` keyword.
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            mode = node.args[1] if len(node.args) > 1 else keyword(node, "mode")
            mode = mode.value if isinstance(mode, ast.Constant) else "r"
            if "b" not in mode:
                if not said_encoding:
                    yield node.lineno, "open() without encoding="

                # The same shape of bug one layer down, and the reason ISS-033
                # exists: text mode also translates "\n" on the way out, so on
                # this machine every write was CRLF while every agent editing
                # the same file wrote LF. Writes only. A read left translated
                # is what lets a hand-edited CRLF file still parse, and the
                # two places that must see the bytes ask for newline="" by
                # name.
                if any(letter in mode for letter in "wax") and keyword(node, "newline") is None:
                    yield node.lineno, "open() for writing without newline="

        # subprocess with text=True: same trap, and the one that bit ISS-013.
        # Bytes mode is fine - nothing is being decoded.
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("run", "check_output", "Popen"):
            if not said_encoding and (
                is_true(keyword(node, "text")) or is_true(keyword(node, "universal_newlines"))
            ):
                yield node.lineno, f"subprocess {node.func.attr}(text=True) without encoding="


# What the walker has to catch, one call per line, so the assertion below can
# name the line it expected. A walker that quietly stopped firing would pass
# `assert not found` on every file in the repo and say "ok" - the check that
# matters is that it still says no to something.
BAD = '''\
open(a, "w", encoding="utf-8")
open(a, "a", encoding="utf-8")
open(a, mode="x", encoding="utf-8")
open(a, "w", newline="\\n")
open(a)
subprocess.run(cmd, text=True)
'''

# And what it must stay quiet about: reads keep their translation, binary has
# neither to get wrong, and a spelled-out write is the whole point.
GOOD = '''\
open(a, "r", encoding="utf-8")
open(a, encoding="utf-8", newline="")
open(a, "wb")
open(a, "w", encoding="utf-8", newline="\\n")
subprocess.run(cmd, text=True, encoding="utf-8")
subprocess.run(cmd, capture_output=True)
'''


def walk_source(text):
    """`unguarded` over a string. It takes a path because every real caller has
    one; a fixture on disk is cheaper than a second entry point into it."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "fixture.py")
        with open(path, "w", encoding="utf-8", newline="\n") as file:
            file.write(text)
        return sorted(unguarded(path))


def demo():
    # 1. The walker fires. Line by line, because "it found something" would
    #    pass while it was catching the wrong half.
    assert walk_source(BAD) == [
        (1, "open() for writing without newline="),
        (2, "open() for writing without newline="),
        (3, "open() for writing without newline="),
        (4, "open() without encoding="),
        (5, "open() without encoding="),
        (6, "subprocess run(text=True) without encoding="),
    ], walk_source(BAD)
    assert walk_source(GOOD) == [], walk_source(GOOD)

    # 2. And nothing in the repo trips it.
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
