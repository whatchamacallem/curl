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

PS4='\e[38;5;208m[${SECONDS}s] ${BASH_SOURCE}:${LINENO}: \e[0m'
set -o xtrace

"$_SCRIPTS/test_expected_behavior.sh" --keep-artifacts

"$_SCRIPTS/test_error_handling.sh"

set +o xtrace
echo "perf2html test_all.sh all_tests_pass"
