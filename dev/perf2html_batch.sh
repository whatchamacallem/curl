#!/usr/bin/env bash
# dev/perf2html_batch.sh [--verbose] [--keep] [cmake_flags...]
#
# Every check the dev/ tooling has, in one run:
#
#   1 lint      pyright over dev/scripts (dev/pyrightconfig.json, must stay at
#                0 errors) and node --check over theme.js plus the JS embedded
#                in the generators (scripts/check_js.py)
#   2 baseline  perf2html.sh            -> perf2html_baseline_report
#   3 modified  perf2html.sh <flags>    -> perf2html_modified_report
#   4 diff      perf2html_diff.sh       -> perf2html_diff_report
#   5 validate  validate_report.py on all three reports
#
# The three report directories are deleted before step 2, so a stale page from
# an earlier run can never be validated instead of a fresh one; --keep skips
# that. cmake_flags are the modified build's flags, passed to perf2html.sh as
# they are; without any, -D CMAKE_C_FLAGS=-Os is used. --verbose streams every
# tool's output instead of logging it to dev/trace/perf2html_batch.<ts>.log.
#
# This is where the dev/ tooling is tested. The two generators run no checks of
# their own -- being driven here, over all three of their output directories,
# is their coverage -- and step 5 is the only validate_report.py run anywhere,
# so one failure list covers the lot. Every step runs even if an earlier one
# failed; the exit status is 1 if any of them did.
set -uo pipefail
SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$SCRIPT")"

BASE_DIR=perf2html_baseline_report
MOD_DIR=perf2html_modified_report
DIFF_DIR=perf2html_diff_report
DEFAULT_FLAGS=(-D CMAKE_C_FLAGS=-Os)

STAMP="$(date +%s)"
RUN_LOG="$PWD/trace/perf2html_batch.$STAMP.log"

usage_show() { awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$SCRIPT"; }

took() {
  local seconds=$(( SECONDS - $1 ))
  if [ "$seconds" -ge 60 ]; then echo "$((seconds / 60))m$((seconds % 60))s"; else echo "${seconds}s"; fi
}

# Runs one step, prints "<n> <name> | ok|FAILED | <time>" and remembers a
# failure without stopping the run. Quiet mode logs the step's output and
# shows the last 40 lines of a failing one.
step_run() {
  local number="$1" name="$2"; shift 2
  local exit_code=0 from start=$SECONDS
  printf '%-2s%-11s' "$number" "$name"
  if [ "$VERBOSE" = 1 ]; then
    printf '\n== %s %s: %s ==\n' "$number" "$name" "$*"
    "$@" || exit_code=$?
    printf '%-2s%-11s' "$number" "$name"
  else
    printf '\n$ %s\n' "$*" >>"$RUN_LOG"
    from="$(wc -l <"$RUN_LOG")"
    "$@" >>"$RUN_LOG" 2>&1 || exit_code=$?
  fi
  if [ "$exit_code" = 0 ]; then
    printf '| ok     | %s\n' "$(took "$start")"
    return 0
  fi
  printf '| FAILED | %s\n' "$(took "$start")"
  STATUS=1
  FAILED+=("$number $name")
  if [ "$VERBOSE" != 1 ]; then
    { echo; echo "error: exit $exit_code from: $*"
      tail -n +"$((from + 1))" "$RUN_LOG" | tail -n 40
      echo "(last 40 lines; everything this run printed: $RUN_LOG)"; } >&2
  fi
  return 0
}

args_parse() {
  VERBOSE=0
  KEEP=0
  while [ $# -gt 0 ]; do
    case "$1" in
      -h|--help) usage_show; exit 0;;
      --verbose) VERBOSE=1; shift;;
      --keep) KEEP=1; shift;;
      *) break;;
    esac
  done
  CMAKE_FLAGS=("$@")
  [ "${#CMAKE_FLAGS[@]}" -gt 0 ] || CMAKE_FLAGS=("${DEFAULT_FLAGS[@]}")
}

lint_run() {
  command -v pyright >/dev/null 2>&1 \
    || { echo "error: pyright not found (pip3 install --user --break-system-packages pyright)" >&2; return 1; }
  local status=0
  pyright --project . || status=1
  python3 scripts/check_js.py || status=1
  return "$status"
}

reports_clean() {
  rm -rf "$BASE_DIR" "$MOD_DIR" "$DIFF_DIR"
}

validate_all() {
  local status=0
  python3 scripts/validate_report.py "$PWD/$BASE_DIR" || status=1
  python3 scripts/validate_report.py "$PWD/$MOD_DIR" || status=1
  python3 scripts/validate_report.py "$PWD/$DIFF_DIR" --diff || status=1
  return "$status"
}

main() {
  args_parse "$@"
  mkdir -p trace
  STATUS=0
  FAILED=()
  local verbose_args=()
  [ "$VERBOSE" = 1 ] && verbose_args=(--verbose)
  [ "$VERBOSE" = 1 ] || echo "dev/perf2html_batch.sh $STAMP: ${CMAKE_FLAGS[*]}" >"$RUN_LOG"
  echo "dev/perf2html_batch.sh $STAMP: modified build flags: ${CMAKE_FLAGS[*]}"

  [ "$KEEP" = 1 ] || reports_clean
  step_run 1 lint lint_run
  step_run 2 baseline ./perf2html.sh "${verbose_args[@]}" "--report=$BASE_DIR"
  step_run 3 modified ./perf2html.sh "${verbose_args[@]}" "--report=$MOD_DIR" "${CMAKE_FLAGS[@]}"
  step_run 4 diff ./perf2html_diff.sh "${verbose_args[@]}" "$BASE_DIR" "$MOD_DIR" "$DIFF_DIR"
  step_run 5 validate validate_all

  if [ "$STATUS" != 0 ]; then
    echo "perf2html_batch: ${#FAILED[@]} step(s) failed: ${FAILED[*]}" >&2
    return 1
  fi
  echo "file://$PWD/$DIFF_DIR/index.html"
  return 0
}

main "$@"
exit "$?"
