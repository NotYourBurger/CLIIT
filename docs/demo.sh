#!/usr/bin/env bash
# The README demo, as a script, so the recording can be regenerated instead of
# re-performed. Records to docs/demo.cast:
#
#   asciinema rec docs/demo.cast --cols 100 --rows 26 --overwrite -c docs/demo.sh
#   agg --theme monokai --font-size 15 docs/demo.cast docs/demo.gif
#
# It runs in a throwaway git repo under $TMPDIR and never touches this one.
set -euo pipefail

# git opens a pager on a tty and clears the screen when it exits, which takes
# the payoff shot of the recording with it.
export GIT_PAGER=cat PAGER=cat

TYPE=${DEMO_TYPE_DELAY:-0.022}   # seconds per character
BEAT=${DEMO_BEAT:-1.1}           # pause after a command's output

say() { printf '\033[2m# %s\033[0m\n' "$1"; sleep "$BEAT"; }

run() {
  printf '\033[32m$\033[0m '
  # Typing one character at a time is the only part of this that is theatre.
  # It is also what makes the viewer read the command instead of skipping it.
  printf '%s' "$1" | while IFS= read -r -N1 c; do printf '%s' "$c"; sleep "$TYPE"; done
  printf '\n'
  sleep 0.25
  eval "$1" || true
  sleep "$BEAT"
}

demo=$(mktemp -d)
trap 'rm -rf "$demo"' EXIT
cd "$demo"
git init -q .
git config user.name  "Alex"
git config user.email "alex@example.com"
printf 'def login():\n    ...\n' > login.py
git add -A && git commit -qm "app"
clear

say "An issue tracker whose whole database is Markdown files in your repo."
run 'issue init --agents'
run 'issue create "Fix login redirect" "The session cookie disappears after sign-in." -p high -l bug'

say "issue next picks the one thing to work on. --claim takes it."
run 'issue next --claim'

say "start seeds a work plan the agent keeps current while it works."
run 'issue start ISS-001'

# The agent commits the claimed issue and its plan the way it would in a real
# repo, so the close below shows up as a reviewable diff and not as a new file.
git add -A && git commit -qm "ISS-001: start"
sed -i 's/^    \.\.\./    set_cookie(response, session)/' login.py
say "...work happens..."
run 'issue close ISS-001 --completed -m "Set the session cookie before redirecting." --test "pytest tests/test_login.py" --verified "Signed in; the session survives the redirect."'

say "No server was involved. The issue is a file:"
run 'cat .issues/ISS-001.md'
clear
say "...so closing it is a diff your team reviews like any other."
run 'git diff --stat'
run 'git diff .issues/ISS-001.md'
sleep 2.5
