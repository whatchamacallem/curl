#!/usr/bin/env bash
# dev/perf2html_batch.sh [--verbose] [--keep] [--keep-raw] [--regenerate]
#     [cmake_flags...]
set -uo pipefail
SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$SCRIPT")"

BASE_DIR=perf2html_baseline_report
MOD_DIR=perf2html_modified_report
DIFF_DIR=perf2html_diff_report
DEFAULT_FLAGS=(-D CMAKE_C_FLAGS=-Os)

STAMP="$(date +%s)"
RUN_LOG="$PWD/temporary_artifacts/perf2html_batch.$STAMP.log"

usage_show() {
  awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$SCRIPT"
}

# now_us - wall clock in whole microseconds, from the EPOCHREALTIME builtin
# (its separator is the locale's, so every non-digit is dropped).
now_us() {
  local now="${EPOCHREALTIME}"
  echo "${now//[!0-9]/}"
}

# elapsed_show - seconds since START_US, two decimals, for the [Ns] prefix.
elapsed_show() {
  local delta=$(($(now_us) - START_US))
  printf '%d.%02d' "$((delta / 1000000))" "$((delta % 1000000 / 10000))"
}

# say - one whole line on stdout, prefixed with the elapsed time.
say() {
  printf '[%ss] %s\n' "$(elapsed_show)" "$*"
}

# say_error - the same line, on stderr.
say_error() {
  printf '[%ss] %s\n' "$(elapsed_show)" "$*" >&2
}

# took - a step's own duration, 1m23s or 12s, from its start microseconds.
took() {
  local seconds=$((($(now_us) - $1) / 1000000))
  if [ "$seconds" -ge 60 ]; then
    echo "$((seconds / 60))m$((seconds % 60))s"
  else
    echo "${seconds}s"
  fi
}

step_run() {
  local number="$1" name="$2"
  shift 2
  local exit_code=0 from start
  start="$(now_us)"
  if [ "$VERBOSE" = 1 ]; then
    printf '== %s %s: %s ==\n' "$number" "$name" "$*"
    "$@" || exit_code=$?
  else
    say "running step $number $name: $*"
    printf '\n$ %s\n' "$*" >>"$RUN_LOG"
    from="$(wc -l <"$RUN_LOG")"
    "$@" >>"$RUN_LOG" 2>&1 || exit_code=$?
  fi
  if [ "$exit_code" = 0 ]; then
    if [ "$VERBOSE" = 1 ]; then
      printf '== %s %s: done in %s ==\n' "$number" "$name" "$(took "$start")"
    else
      say "done: step $number $name in $(took "$start")"
    fi
    return 0
  fi
  STATUS=1
  FAILED+=("$number $name")
  if [ "$VERBOSE" = 1 ]; then
    printf '== %s %s: FAILED (exit %s) after %s ==\n' \
      "$number" "$name" "$exit_code" "$(took "$start")"
    return 0
  fi
  say_error "FAILED: step $number $name, exit $exit_code," \
    "after $(took "$start")"
  {
    echo "error: exit $exit_code from: $*"
    tail -n +"$((from + 1))" "$RUN_LOG" | tail -n 40
    echo "(last 40 lines; everything this run printed: $RUN_LOG)"
  } >&2
  return 0
}

args_parse() {
  VERBOSE=0
  KEEP=0
  PASS_ARGS=()
  while [ $# -gt 0 ]; do
    case "$1" in
      -h | --help)
        usage_show
        exit 0
        ;;
      --verbose)
        VERBOSE=1
        shift
        ;;
      --keep)
        KEEP=1
        shift
        ;;
      --keep-raw)
        PASS_ARGS+=(--keep-raw)
        shift
        ;;
      --regenerate)
        PASS_ARGS+=(--regenerate)
        KEEP=1
        shift
        ;;
      *) break ;;
    esac
  done
  CMAKE_FLAGS=("$@")
  [ "${#CMAKE_FLAGS[@]}" -gt 0 ] || CMAKE_FLAGS=("${DEFAULT_FLAGS[@]}")
}

reports_clean() {
  rm -rf "$BASE_DIR" "$MOD_DIR" "$DIFF_DIR"
}

main() {
  args_parse "$@"
  local child_args=("${PASS_ARGS[@]}")
  RAW_KEEP=1
  case " ${PASS_ARGS[*]} " in
    *" --keep-raw "* | *" --regenerate "*) ;;
    *)
      RAW_KEEP=0
      [ "$VERBOSE" = 1 ] || say "removing stale dev/temporary_artifacts/"
      rm -rf temporary_artifacts
      child_args+=(--keep-raw)
      ;;
  esac
  mkdir -p temporary_artifacts
  START_US="$(now_us)"
  STATUS=0
  FAILED=()
  local verbose_args=()
  [ "$VERBOSE" = 1 ] && verbose_args=(--verbose)
  if [ "$VERBOSE" = 1 ]; then
    echo "dev/perf2html_batch.sh $STAMP:" \
      "modified build flags: ${CMAKE_FLAGS[*]}"
  else
    echo "dev/perf2html_batch.sh $STAMP: ${CMAKE_FLAGS[*]}" >"$RUN_LOG"
    say "dev/perf2html_batch.sh $STAMP:" \
      "modified build flags: ${CMAKE_FLAGS[*]}"
  fi

  if [ "$KEEP" != 1 ]; then
    [ "$VERBOSE" = 1 ] || say "removing previous reports"
    reports_clean
  fi
  step_run 1 baseline ./perf2html.sh "${verbose_args[@]}" \
    "${child_args[@]}" "--report=$BASE_DIR"
  step_run 2 modified ./perf2html.sh "${verbose_args[@]}" \
    "${child_args[@]}" "--report=$MOD_DIR" "${CMAKE_FLAGS[@]}"
  step_run 3 diff ./perf2html_diff.sh "${verbose_args[@]}" \
    "${child_args[@]}" "$BASE_DIR" "$MOD_DIR" "$DIFF_DIR"

  if [ "$STATUS" != 0 ]; then
    local failed="perf2html_batch: ${#FAILED[@]} step(s) failed:"
    local kept="perf2html_batch: dev/temporary_artifacts/ kept for"
    kept="$kept diagnosis (a clean run deletes it)"
    if [ "$VERBOSE" = 1 ]; then
      echo "$failed ${FAILED[*]}" >&2
      [ "$RAW_KEEP" = 0 ] && echo "$kept" >&2
    else
      say_error "$failed ${FAILED[*]}"
      [ "$RAW_KEEP" = 0 ] && say_error "$kept"
    fi
    return 1
  fi
  if [ "$RAW_KEEP" = 0 ]; then
    [ "$VERBOSE" = 1 ] || say "removing dev/temporary_artifacts/"
    rm -rf temporary_artifacts
  fi
  if [ "$VERBOSE" = 1 ]; then
    echo "file://$PWD/$DIFF_DIR/index.html"
  else
    say "file://$PWD/$DIFF_DIR/index.html"
  fi
  return 0
}

main "$@"
exit "$?"
