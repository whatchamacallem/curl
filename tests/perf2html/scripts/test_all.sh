#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.
#
# This comment intentionally blank. No documentation goes here.

usage_show() {
  cat <<'EOF'
test_all.sh [--help]
    Runs test_expected_behavior.sh --keep-artifacts, then
    test_error_handling.sh expecting test artifacts to have been generated.
    --help is the only argument.
EOF
}

set -euo pipefail

[ $# = 0 ] || { [[ $* =~ ^(-h|--help)$ ]] && usage_show && exit 0; } \
  || { echo "error: unknown option: $*" && usage_show && exit 2; } >&2

_SCRIPT="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
_SCRIPTS="$(dirname "$_SCRIPT")"
_PERF2HTML="$(dirname "$_SCRIPTS")"
_DIFF_DIR="$_PERF2HTML/screenshots-diff"
_GOLD_DIR="$_PERF2HTML/screenshots-gold"

PS4='\e[38;5;208m[${SECONDS}s] ${BASH_SOURCE}:${LINENO}: \e[0m'
set -o xtrace

"$_SCRIPTS/test_expected_behavior.sh" --keep-artifacts

"$_SCRIPTS/test_error_handling.sh"

# The diff directory holds this run's differing shots alone.
rm -rf "$_DIFF_DIR"

# The golden screenshots are a developer's own and optional.
if [ -d "$_GOLD_DIR" ]; then
  _SHOTS_DIFFER=0
  python3 "$_SCRIPTS/test_screenshot.py" \
    "$_PERF2HTML/perf2html_modified_report" modified_ \
    --compare-gold "$_GOLD_DIR" --compare-out "$_DIFF_DIR" || _SHOTS_DIFFER=1
  python3 "$_SCRIPTS/test_screenshot.py" \
    "$_PERF2HTML/perf2html_diff_report" diff_ --diff \
    --compare-gold "$_GOLD_DIR" --compare-out "$_DIFF_DIR" || _SHOTS_DIFFER=1
  [ "$_SHOTS_DIFFER" = 0 ] || {
    echo "error: shots differ from $_GOLD_DIR, see $_DIFF_DIR" >&2
    exit 1
  }
else
  echo "warning: no $_GOLD_DIR, golden screenshots not compared" >&2
fi

{ set +o xtrace; } 2>/dev/null
echo "perf2html test_all.sh all_tests_pass"
