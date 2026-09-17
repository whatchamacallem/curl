#!/usr/bin/env bash
# Checks for the dev/ profiling tooling: type-check the Python, syntax-check
# the JS (standalone and the chunks embedded in Python strings), and smoke-run
# the generators. Nothing here builds or profiles curl -- see perf2html.sh.
#
#   dev/test.sh            # every check
#   dev/test.sh py         # one group: py | js
#   dev/test.sh --list     # what the groups are
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$HERE/scripts"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
bold() { printf '\033[1m%s\033[0m\n' "$*"; }

FAILED=()
run_group() {  # run_group NAME CMD...
  local name="$1"; shift
  bold "== $name"
  if "$@"; then grn "-- $name ok"; else red "-- $name FAILED"; FAILED+=("$name"); fi
  echo
}

# The checker is pyright (`pip3 install --user --break-system-packages
# pyright` -> ~/.local/bin/pyright). Pylance is a VS Code extension, not a
# CLI: its bundled pyright.bundle.js speaks LSP only and ignores argv, so it
# cannot be used here. npx is a fallback for a machine without the PyPI one.
pyright_run() {
  if command -v pyright >/dev/null 2>&1; then
    pyright --project "$HERE" "$@"
  elif npx --offline pyright --version >/dev/null 2>&1; then
    npx --offline pyright --project "$HERE" "$@"
  else
    echo "note: no pyright; install with" \
         "pip3 install --user --break-system-packages pyright" >&2
    npx --yes pyright --project "$HERE" "$@"
  fi
}

check_py()     { pyright_run; }
check_js()     { python3 "$SCRIPTS/check_js.py"; }

case "${1:-all}" in
  --list) printf '%s\n' "py      pyright type check (dev/pyrightconfig.json)" \
                        "js      node --check theme.js + JS embedded in generators"; exit 0 ;;
  py)     run_group py     check_py ;;
  js)     run_group js     check_js ;;
  all)    run_group py     check_py
          run_group js     check_js ;;
  *)      red "unknown group: $1 (see --list)"; exit 2 ;;
esac

if [ ${#FAILED[@]} -eq 0 ]; then grn "all checks passed"; exit 0; fi
red "failed: ${FAILED[*]}"; exit 1
