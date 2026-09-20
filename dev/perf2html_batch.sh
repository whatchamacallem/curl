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
  cat <<'EOF'
perf2html_batch.sh [--verbose] [--keep] [--keep-raw] [--regenerate]
    [cmake_flags...]
EOF
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

verbose() { if [ "$VERBOSE" = 1 ]; then echo "$@"; fi; }

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
  printf '[%ss] running step %s %s: %s\n' "$(elapsed_show)" \
    "$number" "$name" "$*"
  verbose "$(printf '== %s %s ==' "$number" "$name")"
  printf '\n$ %s\n' "$*" >>"$RUN_LOG"
  from="$(wc -l <"$RUN_LOG")"
  if [ "$VERBOSE" = 1 ]; then
    # tee so a step's output arrives as it is produced. The `if !` is what
    # keeps pipefail's failure from reaching PIPESTATUS's reader.
    if ! { "$@" 2>&1 | tee -a "$RUN_LOG"; }; then
      exit_code="${PIPESTATUS[0]}"
    fi
  else
    "$@" >>"$RUN_LOG" 2>&1 || exit_code=$?
  fi
  verbose "$(printf '== %s %s: end ==' "$number" "$name")"
  if [ "$exit_code" = 0 ]; then
    printf '[%ss] done: step %s %s in %s\n' "$(elapsed_show)" \
      "$number" "$name" "$(took "$start")"
    return 0
  fi
  STATUS=1
  FAILED+=("$number $name")
  printf '[%ss] FAILED: step %s %s, exit %s, after %s\n' "$(elapsed_show)" \
    "$number" "$name" "$exit_code" "$(took "$start")" >&2
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
  START_US="$(now_us)"
  local child_args=("${PASS_ARGS[@]}")
  RAW_KEEP=1
  case " ${PASS_ARGS[*]} " in
    *" --keep-raw "* | *" --regenerate "*) ;;
    *)
      RAW_KEEP=0
      printf '[%ss] removing stale dev/temporary_artifacts/\n' \
        "$(elapsed_show)"
      rm -rf temporary_artifacts
      child_args+=(--keep-raw)
      ;;
  esac
  mkdir -p temporary_artifacts
  STATUS=0
  FAILED=()
  local verbose_args=()
  if [ "$VERBOSE" = 1 ]; then verbose_args=(--verbose); fi
  echo "dev/perf2html_batch.sh $STAMP: ${CMAKE_FLAGS[*]}" >"$RUN_LOG"
  printf '[%ss] dev/perf2html_batch.sh %s: modified build flags: %s\n' \
    "$(elapsed_show)" "$STAMP" "${CMAKE_FLAGS[*]}"

  if [ "$KEEP" != 1 ]; then
    printf '[%ss] removing previous reports\n' "$(elapsed_show)"
    reports_clean
  fi
  step_run 1 baseline ./perf2html.sh "${verbose_args[@]}" \
    "${child_args[@]}" "--report=$BASE_DIR"
  step_run 2 modified ./perf2html.sh "${verbose_args[@]}" \
    "${child_args[@]}" "--report=$MOD_DIR" "${CMAKE_FLAGS[@]}"
  step_run 3 diff ./perf2html_diff.sh "${verbose_args[@]}" \
    "${child_args[@]}" "$BASE_DIR" "$MOD_DIR" "$DIFF_DIR"

  if [ "$STATUS" != 0 ]; then
    printf '[%ss] perf2html_batch: %s step(s) failed: %s\n' \
      "$(elapsed_show)" "${#FAILED[@]}" "${FAILED[*]}" >&2
    if [ "$RAW_KEEP" = 0 ]; then
      printf '[%ss] perf2html_batch: dev/temporary_artifacts/ kept for %s\n' \
        "$(elapsed_show)" "diagnosis (a clean run deletes it)" >&2
    fi
    return 1
  fi
  if [ "$RAW_KEEP" = 0 ]; then
    printf '[%ss] removing dev/temporary_artifacts/\n' "$(elapsed_show)"
    rm -rf temporary_artifacts
  fi
  printf '[%ss] file://%s/%s/index.html\n' "$(elapsed_show)" \
    "$PWD" "$DIFF_DIR"
  return 0
}

main "$@"
exit "$?"
