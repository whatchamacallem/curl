# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

path_shown() {
  printf '%s' "${1//"$HOME"\//"~/"}"
}

test_fail() {
  {
    printf '\nFAILED: %s: %s\n' "$1" "$2"
    echo "(kept: $(path_shown "$_TEST_ERROR_SCRATCH"))"
  } >&2
  exit 1
}

test_failure_expect() {
  local _name="$1" _wanted_code="$2" _code=0
  shift 2
  [ "${1:-}" = -- ] || test_fail "$_name" \
    "test_failure_expect wants -- first"
  shift
  "$@" </dev/null || _code=$?
  [ "$_code" = "$_wanted_code" ] \
    || test_fail "$_name" "exit $_code, expected $_wanted_code, from: $*"
  echo "ok $_name"
}

test_report_copy() {
  cp -a "$2" "$1"
  echo "$1"
}

tool_find() {
  local name="$1" found
  for found in "$name" "$HOME/.local/bin/$name" \
    "$HOME/.npm-global/bin/$name"; do
    if command -v "$found" >/dev/null 2>&1; then
      echo "$found"
      return 0
    fi
  done
  return 1
}
