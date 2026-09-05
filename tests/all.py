"""Every check, one command: uv run python tests/all.py

A subprocess each, rather than importing them, because these tests chdir and
set ISSUES_DIR - in one process the first one to skip its cleanup would break
the next and the traceback would point at the wrong file. It also means one
failure does not stop the rest.
"""

import glob
import os
import subprocess
import sys

failed = []
for path in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_*.py"))):
    name = os.path.basename(path)
    print(f"{name}: ", end="", flush=True)
    # Output is inherited, so a failing assert prints its own traceback here.
    if subprocess.run([sys.executable, path]).returncode:
        failed.append(name)

sys.exit(f"{len(failed)} failed: {', '.join(failed)}" if failed else 0)
