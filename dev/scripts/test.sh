#!/usr/bin/env bash

# This comment intentionally blank. No documentation goes here.

set -euo pipefail

# usage_show - the one usage text, printed by -h and on a bad argument
usage_show() {
  cat <<'EOF'
test.sh [--help]
    Runs test_expected_behavior.sh --keep-artifacts, then
    test_error_handling.sh. --help is its only argument.
EOF
}

[ $# = 0 ] || { [[ $* =~ ^(-h|--help)$ ]] && usage_show && exit 0; } \
  || { echo "error: unknown option: $*" && usage_show && exit 2; } >&2

_SCRIPT="$(readlink -f "$0")"
_SCRIPTS="$(dirname "$_SCRIPT")"

# Logs every command in orange with the time and script name prepended.
PS4='\e[38;5;208m[${SECONDS}s] ${BASH_SOURCE}:${LINENO}: \e[0m'

"$_SCRIPTS/test_expected_behavior.sh" --keep-artifacts

# This step expects the artifacts from the last step. No check needed here.
"$_SCRIPTS/test_error_handling.sh"

# echo ensures the script returns 1.
echo "perf2html all_tests_pass"
