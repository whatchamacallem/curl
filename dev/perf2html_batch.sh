#!/usr/bin/env bash
# dev/perf2html_batch.sh [--verbose] [--keep] [--keep-raw] [--regenerate]
#     [--artifacts=DIR] [target-dir] [cmake_flags...]
#
# The three reports keep their default names and are created in target-dir
# (the current directory when it is not given). The batch cannot rename
# them: call perf2html.sh or perf2html_diff.sh directly for that.
#
# Raw recordings are written to a temporary artifacts directory. It sits
# beside the reports by default -- target-dir holding
# perf2html_temporary_artifacts/ -- so a read-only checkout still
# profiles. --artifacts=DIR overrides that and is forwarded to both
# children, so all three stages share one directory.
set -uo pipefail
SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$SCRIPT")"

# directory name holding the raw recordings, inside target-dir
ARTIFACTS_NAME=perf2html_temporary_artifacts
# report directory name for the unmodified build
BASE_NAME=perf2html_baseline_report
# report directory name for the build carrying the cmake flags
MOD_NAME=perf2html_modified_report
# report directory name for the subtraction of the two
DIFF_NAME=perf2html_diff_report
# cmake flags for the modified build when the caller gives none
DEFAULT_FLAGS=(-D CMAKE_C_FLAGS=-Os)

# seconds since the epoch, naming this run's log
STAMP="$(date +%s)"

# usage_show - the help text, for -h and --help
usage_show() {
  cat <<'EOF'
perf2html_batch.sh [--verbose] [--keep] [--keep-raw] [--regenerate]
    [--artifacts=DIR] [target-dir] [cmake_flags...]

target-dir is where the three default-named reports are created:
perf2html_baseline_report, perf2html_modified_report and
perf2html_diff_report. It defaults to the current directory. The batch
cannot rename them -- call perf2html.sh or perf2html_diff.sh directly.

The first argument that does not start with "-" is target-dir; every
argument after it, and every unrecognized argument starting with "-",
is a cmake flag. A bare "-D" or "-U" claims the argument after it as
its value, so "-D CMAKE_C_FLAGS=-Os" still reads as one cmake flag.

--artifacts=DIR holds the raw recordings; it defaults to
perf2html_temporary_artifacts/ inside target-dir.
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

# verbose - the one function testing $VERBOSE, printing only when set
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

# step_run - runs one numbered step, logging it, and records a failure
# in STATUS and FAILED instead of returning non-zero.
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

# args_parse - reads the command line into the globals, and derives every
# absolute *_DIR and RUN_LOG path from target-dir.
args_parse() {
  VERBOSE=0
  KEEP=0
  PASS_ARGS=()
  CMAKE_FLAGS=()
  TARGET_DIR=""
  ARTIFACTS_DIR=""
  local target_seen=0 value_wanted=0
  while [ $# -gt 0 ]; do
    # a bare -D takes the next argument as its value, so that value is
    # never read as target-dir
    if [ "$target_seen" = 1 ] || [ "$value_wanted" = 1 ]; then
      CMAKE_FLAGS+=("$1")
      value_wanted=0
      shift
      continue
    fi
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
      --artifacts=*)
        ARTIFACTS_DIR="${1#--artifacts=}"
        shift
        ;;
      -D | -U)
        CMAKE_FLAGS+=("$1")
        value_wanted=1
        shift
        ;;
      -*)
        CMAKE_FLAGS+=("$1")
        shift
        ;;
      *)
        TARGET_DIR="$1"
        target_seen=1
        shift
        ;;
    esac
  done
  [ "${#CMAKE_FLAGS[@]}" -gt 0 ] || CMAKE_FLAGS=("${DEFAULT_FLAGS[@]}")
  [ -n "$TARGET_DIR" ] || TARGET_DIR="$PWD"
  case "$TARGET_DIR" in
    "~/"*) TARGET_DIR="$HOME/${TARGET_DIR#"~/"}" ;;
    /*) ;;
    *) TARGET_DIR="$PWD/$TARGET_DIR" ;;
  esac
  if [ -z "$ARTIFACTS_DIR" ]; then
    ARTIFACTS_DIR="$TARGET_DIR/$ARTIFACTS_NAME"
  fi
  case "$ARTIFACTS_DIR" in
    "~/"*) ARTIFACTS_DIR="$HOME/${ARTIFACTS_DIR#"~/"}" ;;
    /*) ;;
    *) ARTIFACTS_DIR="$PWD/$ARTIFACTS_DIR" ;;
  esac
  BASE_DIR="$TARGET_DIR/$BASE_NAME"
  MOD_DIR="$TARGET_DIR/$MOD_NAME"
  DIFF_DIR="$TARGET_DIR/$DIFF_NAME"
  RUN_LOG="$ARTIFACTS_DIR/perf2html_batch.$STAMP.log"
}

# reports_clean - deletes the three report directories
reports_clean() {
  rm -rf "$BASE_DIR" "$MOD_DIR" "$DIFF_DIR"
}

# main - runs baseline, modified and diff, each step even after a failure,
# and owns every deletion of the artifacts directory.
main() {
  args_parse "$@"
  START_US="$(now_us)"
  local child_args=("${PASS_ARGS[@]}" "--artifacts=$ARTIFACTS_DIR")
  RAW_KEEP=1
  case " ${PASS_ARGS[*]} " in
    *" --keep-raw "* | *" --regenerate "*) ;;
    *)
      RAW_KEEP=0
      printf '[%ss] removing stale %s/\n' \
        "$(elapsed_show)" "$ARTIFACTS_DIR"
      rm -rf "$ARTIFACTS_DIR"
      child_args+=(--keep-raw)
      ;;
  esac
  mkdir -p "$ARTIFACTS_DIR"
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
      printf '[%ss] perf2html_batch: %s/ kept for %s\n' \
        "$(elapsed_show)" "$ARTIFACTS_DIR" \
        "diagnosis (a clean run deletes it)" >&2
    fi
    return 1
  fi
  if [ "$RAW_KEEP" = 0 ]; then
    printf '[%ss] removing %s/\n' "$(elapsed_show)" "$ARTIFACTS_DIR"
    rm -rf "$ARTIFACTS_DIR"
  fi
  printf '[%ss] file://%s/index.html\n' "$(elapsed_show)" "$DIFF_DIR"
  return 0
}

main "$@"
exit "$?"
