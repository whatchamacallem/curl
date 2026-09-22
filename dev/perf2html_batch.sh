#!/usr/bin/env bash

# No usage docs allowed here.

set -uo pipefail
SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$SCRIPT")"

. ./scripts/shared.sh

TIMESTAMP="$(date +%s)"

# Must be kept in sync with the README.txt and no other usage docs allowed.
usage_show() {
  cat <<'EOF'
perf2html_batch.sh [debug-flags] [--target-dir=DIR] [cmake-flags...]
    Profiles baseline, modified and then does a diff of them.
    --target-dir=DIR  holds the three default-named reports (default CWD). The
                      batch cannot rename them.
    cmake-flags       every argument not one of its own options, applied to the
                      modified build (default -D CMAKE_C_FLAGS=-Os).

  debug-flags:
    --artifacts=TMP   The profiler artifacts directory. Defaults to
                      perf2html_temporary_artifacts/ beside the report
                      directory (inside the target dir for a batch).
    --keep-artifacts  Do not delete the profiler artifacts directory after use.
                      Required for a later --regenerate.
    --regenerate      Rebuilds all pages from the last run's profiler
                      artifacts, re-measuring nothing. Implies
                      --keep-artifacts.
    --verbose         additive: whatever quiet prints, verbose prints too, plus
                      each child's output as produced.
EOF
}

# step_run - runs one numbered step, logging it, and records a failure
# in STATUS and FAILED instead of returning non-zero. SETS those two
# caller globals, and is their canonical setter: main() initializes them
# and reads them back once every step has run.
step_run() {
  local number="$1" name="$2"
  shift 2
  local exit_code=0 from start
  start="$(clock_microseconds)"
  printf '[%ss] running step %s %s: %s\n' "$(elapsed_format)" \
    "$number" "$name" "$*"
  log_verbose "$(printf '== %s %s ==' "$number" "$name")"
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
  log_verbose "$(printf '== %s %s: end ==' "$number" "$name")"
  if [ "$exit_code" = 0 ]; then
    printf '[%ss] done: step %s %s in %s\n' "$(elapsed_format)" \
      "$number" "$name" "$(duration_format "$start")"
    return 0
  fi
  STATUS=1
  FAILED+=("$number $name")
  printf '[%ss] FAILED: step %s %s, exit %s, after %s\n' \
    "$(elapsed_format)" "$number" "$name" "$exit_code" \
    "$(duration_format "$start")" >&2
  {
    echo "error: exit $exit_code from: $*"
    tail -n +"$((from + 1))" "$RUN_LOG" | tail -n 40
    echo "(last 40 lines; everything this run printed: $RUN_LOG)"
  } >&2
  return 0
}

# args_parse - reads the command line into the globals, and derives every
# absolute *_DIR and RUN_LOG path from the target directory. Every
# argument it does not name is a cmake flag, which is why no value of a
# separated "-D NAME=VALUE" pair can be mistaken for anything else.
args_parse() {
  VERBOSE=0
  KEEP_ARTIFACTS=0
  REGENERATE=0
  PASS_ARGS=()
  CMAKE_FLAGS=()
  TARGET_DIR=""
  ARTIFACTS_DIR=""
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
      --keep-artifacts)
        KEEP_ARTIFACTS=1
        PASS_ARGS+=(--keep-artifacts)
        shift
        ;;
      --regenerate)
        REGENERATE=1
        KEEP_ARTIFACTS=1
        PASS_ARGS+=(--regenerate)
        shift
        ;;
      --artifacts=*)
        ARTIFACTS_DIR="${1#--artifacts=}"
        shift
        ;;
      --target-dir=*)
        TARGET_DIR="${1#--target-dir=}"
        shift
        ;;
      *)
        CMAKE_FLAGS+=("$1")
        shift
        ;;
    esac
  done
  [ "${#CMAKE_FLAGS[@]}" -gt 0 ] || CMAKE_FLAGS=("${DEFAULT_FLAGS[@]}")
  [ -n "$TARGET_DIR" ] || TARGET_DIR="$PWD"
  TARGET_DIR="$(absolute_path "$TARGET_DIR")"
  if [ -z "$ARTIFACTS_DIR" ]; then
    ARTIFACTS_DIR="$TARGET_DIR/$ARTIFACTS_NAME"
  fi
  ARTIFACTS_DIR="$(absolute_path "$ARTIFACTS_DIR")"
  BASE_DIR="$TARGET_DIR/$BASE_NAME"
  MOD_DIR="$TARGET_DIR/$MOD_NAME"
  DIFF_DIR="$TARGET_DIR/$DIFF_NAME"
  RUN_LOG="$ARTIFACTS_DIR/perf2html_batch.$TIMESTAMP.log"
}

# reports_clean - deletes the three report directories
reports_clean() {
  rm -rf "$BASE_DIR" "$MOD_DIR" "$DIFF_DIR" || {
    echo "error: could not remove previous reports under $TARGET_DIR" >&2
    exit 1
  }
}

# main - runs baseline, modified and diff, each step even after a failure,
# and owns every deletion of the artifacts directory.
main() {
  args_parse "$@"
  START_US="$(clock_microseconds)"
  local child_args=("${PASS_ARGS[@]}" "--artifacts=$ARTIFACTS_DIR")
  if [ "$KEEP_ARTIFACTS" = 0 ]; then
    printf '[%ss] removing stale %s/\n' \
      "$(elapsed_format)" "$ARTIFACTS_DIR"
    rm -rf "$ARTIFACTS_DIR" || {
      echo "error: could not remove stale $ARTIFACTS_DIR/" >&2
      exit 1
    }
    # the children keep it whatever the batch was asked, so neither can
    # unlink the batch log out from under this run. The batch is the one
    # thing that deletes the directory, at the end of main().
    child_args+=(--keep-artifacts)
  fi
  mkdir -p "$ARTIFACTS_DIR" || {
    echo "error: could not create $ARTIFACTS_DIR/" >&2
    exit 1
  }
  STATUS=0
  FAILED=()
  local verbose_args=()
  if [ "$VERBOSE" = 1 ]; then verbose_args=(--verbose); fi
  echo "dev/perf2html_batch.sh $TIMESTAMP: ${CMAKE_FLAGS[*]}" >"$RUN_LOG"
  printf '[%ss] dev/perf2html_batch.sh %s: modified build flags: %s\n' \
    "$(elapsed_format)" "$TIMESTAMP" "${CMAKE_FLAGS[*]}"

  # --regenerate rebuilds each report's pages out of the recordings the
  # last run kept, and reads each report's own MANIFEST.txt back to find
  # them, so it is the one mode that must not start by deleting them.
  if [ "$REGENERATE" = 0 ]; then
    printf '[%ss] removing previous reports\n' "$(elapsed_format)"
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
      "$(elapsed_format)" "${#FAILED[@]}" "${FAILED[*]}" >&2
    if [ "$KEEP_ARTIFACTS" = 0 ]; then
      printf '[%ss] perf2html_batch: %s/ kept for %s\n' \
        "$(elapsed_format)" "$ARTIFACTS_DIR" \
        "diagnosis (a clean run deletes it)" >&2
    fi
    return 1
  fi
  if [ "$KEEP_ARTIFACTS" = 0 ]; then
    printf '[%ss] removing %s/\n' "$(elapsed_format)" "$ARTIFACTS_DIR"
    rm -rf "$ARTIFACTS_DIR" || {
      echo "error: could not remove $ARTIFACTS_DIR/" >&2
      exit 1
    }
  fi
  printf '[%ss] file://%s/index.html\n' "$(elapsed_format)" "$DIFF_DIR"
  return 0
}

main "$@"
exit "$?"
