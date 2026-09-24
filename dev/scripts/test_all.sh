#!/usr/bin/env bash
# dev/scripts/test_all.sh [--verbose]
#
# Runs enforcer.sh all three ways, in the one order that proves the
# handoffs: flagless (measure cold, delete the recordings), then
# --keep-artifacts (measure cold, leave the recordings), then --regenerate
# (measure nothing and reuse what the second left).
#

set -euo pipefail

_SCRIPT="$(readlink -f "$0")"
_SCRIPTS="$(dirname "$_SCRIPT")"
_ENFORCER="$_SCRIPTS/enforcer.sh"

# each mode's flags, in the order they must run. An empty word is the
# flagless run, and read back with no quoting so it becomes no argument
_MODES=("" "--keep-artifacts" "--regenerate")

_VERBOSE=0

# set by mode_run, read by main: the seconds that mode took
_MODE_SECONDS=0

usage_show() {
  cat <<'EOF'
scripts/test_all.sh [--verbose]
    Runs enforcer.sh three ways in order -- no flags, --keep-artifacts,
    --regenerate -- so each mode's precondition is the one before it.
    --verbose         Enables diagnostic information, passed down to
                      enforcer.sh and on to the perf2* scripts.
EOF
}

# args_parse - reads the one flag this takes, refusing anything else.
args_parse() {
  local _argument
  for _argument in "$@"; do
    case "$_argument" in
      --verbose)
        _VERBOSE=1
        ;;
      -h | --help)
        usage_show
        exit 0
        ;;
      *)
        printf 'unknown option: %s\n' "$_argument" >&2
        usage_show >&2
        exit 2
        ;;
    esac
  done
}

# mode_fail - prints why the sequence stopped and leaves with that code.
mode_fail() {
  printf '\n' >&2
  printf 'FAILED: enforcer.sh %s exited %s after %ss\n' "$1" "$2" "$3" >&2
  printf 'The sequence stops here: the modes after it verify handoffs\n' >&2
  printf 'from this one, and would report noise instead of a fault.\n' >&2
  exit "$2"
}

# mode_run - runs one mode, setting _MODE_SECONDS. A fault leaves instead.
# The global is because a $( ) here would swallow the child's verbose spew.
mode_run() {
  local _mode="$1" _name="$2"
  local _flags=() _start _end _code=0

  if [ -n "$_mode" ]; then _flags+=("$_mode"); fi
  if [ "$_VERBOSE" = 1 ]; then _flags+=(--verbose); fi

  _start="$(date +%s)"
  "$_ENFORCER" "${_flags[@]}" || _code="$?"
  _end="$(date +%s)"
  _MODE_SECONDS="$((_end - _start))"

  if [ "$_code" != 0 ]; then
    mode_fail "$_name" "$_code" "$_MODE_SECONDS"
  fi
}

# main - runs the three modes in order, timing each, stopping at a fault.
main() {
  args_parse "$@"

  if [ ! -x "$_ENFORCER" ]; then
    printf 'no executable enforcer.sh at %s\n' "$_ENFORCER" >&2
    exit 1
  fi

  local _mode _name
  local _timings=()

  for _mode in "${_MODES[@]}"; do
    _name="${_mode:-(no flags)}"
    mode_run "$_mode" "$_name"
    _timings+=("$(printf 'enforcer.sh %-18s %ss' "$_name" "$_MODE_SECONDS")")
  done

  printf '%s\n' "${_timings[@]}"
}

main "$@"
