#!/usr/bin/env bash

# This comment intentionally blank. No documentation goes here.

set -euo pipefail

usage_show() {
  cat <<'EOF'
test_all.sh [forwarded-args]
  test_all.sh runs a series of tests passing [forwarded-args] to all of them.
  First enforcer.sh is run. Then a series of failure modes in the perf2html*sh
  scripts are checked. The error handling tests go here. It is the release
  script.
EOF
}

_SCRIPT="$(readlink -f "$0")"
_SCRIPTS="$(dirname "$_SCRIPT")"
_ENFORCER="$_SCRIPTS/enforcer.sh"
_REPO="$(dirname "$(dirname "$_SCRIPTS")")"

# where a bare run keeps the whole of its verbose output: the snapshot of
# one build, for a reader or an AI. dev/docs/ is ignored and never enforced
_DOCUMENT="$(dirname "$_SCRIPTS")/docs/test_all.md"

# each mode's flags, in the order they must run. An empty word is the
# flagless run, and read back with no quoting so it becomes no argument
_MODES=("" "--keep-artifacts" "--regenerate")

# Do not use shared.sh here, validation is separate. settings.sh is read
# for the one value the header names, the pinned CPU.
. "$_SCRIPTS/settings.sh"

# this script's own clock, in microseconds, for its [Ns] headings
_START_US="${EPOCHREALTIME//[!0-9]/}"

# the heading depth enforcer.sh prints at: one below this script's title
export PERF2HTML_HEADER_DEPTH=2

# set by mode_run, read by main: the seconds that mode took
_MODE_SECONDS=0

# elapsed_format - seconds since _START_US, two decimals
elapsed_format() {
  local _delta=$((${EPOCHREALTIME//[!0-9]/} - _START_US))
  printf '%d.%02d' "$((_delta / 1000000))" "$((_delta % 1000000 / 10000))"
}

# path_shown - one path with $HOME/ written as ~/, as every line prints it
path_shown() {
  printf '%s' "${1//"$HOME"\//"~/"}"
}

# header_print - the run's title and the table naming what it ran on
header_print() {
  local _revision _dirty=0
  _revision="$(git -C "$_REPO" rev-parse --short HEAD)"
  # git diff --quiet answers 1 for a dirty tree; any other code is a fault
  git -C "$_REPO" diff --quiet HEAD -- || _dirty=$?
  if [ "$_dirty" = 1 ]; then
    _revision="$_revision-dirty"
  elif [ "$_dirty" != 0 ]; then
    printf 'error: git diff --quiet exited %s in %s\n' "$_dirty" "$_REPO" >&2
    exit 1
  fi
  printf '# `[%ss] %s %s`\n\n' "$(elapsed_format)" "$(path_shown "$_SCRIPT")" \
    "$*"
  echo '| started | git | cmake | cc | curl | kernel | pinned cpu |'
  echo '| --- | --- | --- | --- | --- | --- | --- |'
  printf '| %s | %s | %s | %s | %s | %s | %s |\n\n' \
    "$(date '+%F %T %z')" "$_revision" "$(cmake --version | head -1)" \
    "$(cc --version | head -1)" \
    "$(sed -n 's/^#define LIBCURL_VERSION "\(.*\)"/\1/p' \
      "$_REPO/include/curl/curlver.h")" \
    "$(uname -r)" "$PROFILE_PINNED_CPU"
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
  shift 2
  local _flags=() _start _end _code=0

  if [ -n "$_mode" ]; then _flags+=("$_mode"); fi

  # every argument this was given goes to every mode, parsed by none here
  _start="$(date +%s)"
  "$_ENFORCER" "${_flags[@]}" "$@" || _code="$?"
  _end="$(date +%s)"
  _MODE_SECONDS="$((_end - _start))"

  if [ "$_code" != 0 ]; then
    mode_fail "$_name" "$_code" "$_MODE_SECONDS"
  fi
}

# main - runs the three modes in order, timing each, stopping at a fault.
main() {
  # the one argument read here; everything else is forwarded untouched
  local _argument
  for _argument in "$@"; do
    if [ "$_argument" = -h ] || [ "$_argument" = --help ]; then
      usage_show
      exit 0
    fi
  done

  if [ ! -x "$_ENFORCER" ]; then
    printf 'no executable enforcer.sh at %s\n' "$_ENFORCER" >&2
    exit 1
  fi

  header_print "$@"

  local _mode _name
  local _names=() _timings=()

  for _mode in "${_MODES[@]}"; do
    _name="${_mode:-(no flags)}"
    mode_run "$_mode" "$_name" "$@"
    _names+=("enforcer.sh $_name")
    _timings+=("${_MODE_SECONDS}s")
  done

  printf '\n## `[%ss] %s, after the three modes`\n\n' "$(elapsed_format)" \
    "$(path_shown "$_SCRIPT")"
  printf '| %s | %s | %s |\n' "${_names[@]}"
  echo '| --- | --- | --- |'
  printf '| %s | %s | %s |\n' "${_timings[@]}"
}

# a bare run is verbose and keeps every line as the document; any flag at
# all is someone watching, and then nothing is written
if [ $# = 0 ]; then
  mkdir -p "$(dirname "$_DOCUMENT")"
  main --verbose 2>&1 | tee "$_DOCUMENT"
else
  main "$@"
fi
