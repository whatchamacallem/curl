# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

path_shown() {
  printf '%s' "${1//"$HOME"\//"~/"}"
}

# Tells the agent reading a run that shots differing from gold are no failure.
screenshot_gold_notice() {
  local _gold _diff
  _gold="$(cd "$1" && pwd)"
  _diff="$(cd "$2" && pwd)"
  cat <<EOF

Note: Some shots differ from their gold twins. This is not a failure of the
test suite during development: every other stage passed and change is expected.

Gold: $(path_shown "$_gold")
Diff: $(path_shown "$_diff")
EOF
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

# Expects an exit code and one whole output line, the output shown as it runs.
test_failure_message_expect() {
  local _name="$1" _wanted_code="$2" _wanted_line="$3" _statuses=(0 0 0)
  shift 3
  [ "${1:-}" = -- ] || test_fail "$_name" \
    "test_failure_message_expect wants -- first"
  shift
  "$@" </dev/null 2>&1 | tee -a /dev/stderr \
    | grep -c -x -F -e "$_wanted_line" >/dev/null \
    || _statuses=("${PIPESTATUS[@]}")
  [ "${_statuses[0]}" = "$_wanted_code" ] || test_fail "$_name" \
    "exit ${_statuses[0]}, expected $_wanted_code, from: $*"
  [ "${_statuses[1]}" = 0 ] || test_fail "$_name" \
    "tee exited ${_statuses[1]} behind: $*"
  [ "${_statuses[2]}" = 0 ] || test_fail "$_name" \
    "no line '$_wanted_line' from: $*"
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
