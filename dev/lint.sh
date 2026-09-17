#!/usr/bin/env bash
# dev/lint.sh -- checks for the dev/ tooling itself: pyright over dev/scripts
# (dev/pyrightconfig.json; must stay at 0 errors) and node --check over
# theme.js plus the JS embedded in the generators (scripts/check_js.py).
# Builds and profiles nothing.
set -uo pipefail
cd "$(dirname "$0")"
command -v pyright >/dev/null 2>&1 \
  || { echo "error: pyright not found (pip3 install --user --break-system-packages pyright)" >&2; exit 1; }
status=0
pyright --project . || status=1
python3 scripts/check_js.py || status=1
exit "$status"
