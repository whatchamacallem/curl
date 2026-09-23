#!/usr/bin/env bash

# Runs baseline, modified and diff in one go. usage_show below is the only
# usage text here. It and README.md are kept in step by hand.

set -euo pipefail

_SCRIPT="$(readlink -f "$0")"
INVOKED_FROM="$PWD"
cd "$(dirname "$_SCRIPT")"

. ./scripts/settings.sh
. ./scripts/shared.sh

# usage_show - the one usage text, printed by -h and on a bad argument
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
    --verbose         Enables diagnostic information.
EOF
}

# step_run - run one numbered step, logging it. SETS _STATUS and _FAILED,
# their canonical setter, rather than returning non-zero: later steps run.
step_run() {
  local _number="$1" _name="$2"
  shift 2
  local _exit_code _start
  _start="$(clock_microseconds)"
  printf '[%ss] running step %s %s: %s\n' "$(elapsed_format)" \
    "$_number" "$_name" "$*"
  log_verbose "$(printf '== %s %s ==' "$_number" "$_name")"
  child_capture "$@"
  _exit_code="$CHILD_EXIT_CODE"
  log_verbose "$(printf '== %s %s: end ==' "$_number" "$_name")"
  if [ "$_exit_code" = 0 ]; then
    printf '[%ss] done: step %s %s in %s\n' "$(elapsed_format)" \
      "$_number" "$_name" "$(duration_format "$_start")"
    return 0
  fi
  _STATUS=1
  _FAILED+=("$_number $_name")
  printf '[%ss] FAILED: step %s %s, exit %s, after %s\n' \
    "$(elapsed_format)" "$_number" "$_name" "$_exit_code" \
    "$(duration_format "$_start")" >&2
  failure_tail_print "$_exit_code" "$@"
  return 0
}

# args_parse - read the command line, deriving every absolute *_DIR and
# RUN_LOG from the target dir. Every argument it does not name is a cmake flag.
args_parse() {
  _KEEP_ARTIFACTS=0
  _REGENERATE=0
  _PASS_ARGS=()
  _CMAKE_FLAGS=()
  _TARGET_DIR=""
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
        _KEEP_ARTIFACTS=1
        _PASS_ARGS+=(--keep-artifacts)
        shift
        ;;
      --regenerate)
        _REGENERATE=1
        _KEEP_ARTIFACTS=1
        _PASS_ARGS+=(--regenerate)
        shift
        ;;
      --artifacts=*)
        ARTIFACTS_DIR="${1#--artifacts=}"
        shift
        ;;
      --target-dir=*)
        _TARGET_DIR="${1#--target-dir=}"
        shift
        ;;
      *)
        _CMAKE_FLAGS+=("$1")
        shift
        ;;
    esac
  done
  [ "${#_CMAKE_FLAGS[@]}" -gt 0 ] || _CMAKE_FLAGS=("${DEFAULT_FLAGS[@]}")
  [ -n "$_TARGET_DIR" ] || _TARGET_DIR="$PWD"
  _TARGET_DIR="$(absolute_path "$_TARGET_DIR")"
  if [ -z "$ARTIFACTS_DIR" ]; then
    ARTIFACTS_DIR="$_TARGET_DIR/$ARTIFACTS_NAME"
  fi
  ARTIFACTS_DIR="$(absolute_path "$ARTIFACTS_DIR")"
  _BASE_DIR="$_TARGET_DIR/$REPORT_BASELINE_DIR_NAME"
  _MOD_DIR="$_TARGET_DIR/$REPORT_MODIFIED_DIR_NAME"
  _DIFF_DIR="$_TARGET_DIR/$REPORT_DIFF_DIR_NAME"
  RUN_LOG="$ARTIFACTS_DIR/perf2html_batch.$TIMESTAMP.log"
}

# reports_clean - deletes the three report directories
reports_clean() {
  rm -rf "$_BASE_DIR" "$_MOD_DIR" "$_DIFF_DIR" || {
    echo "error: could not remove previous reports under $_TARGET_DIR" >&2
    exit 1
  }
}

# main - runs baseline, modified and diff, each step even after a failure,
# and owns every deletion of the artifacts directory.
main() {
  args_parse "$@"
  START_US="$(clock_microseconds)"
  local _child_args=("${_PASS_ARGS[@]}" "--artifacts=$ARTIFACTS_DIR")
  if [ "$_KEEP_ARTIFACTS" = 0 ]; then
    printf '[%ss] removing stale %s/\n' \
      "$(elapsed_format)" "$ARTIFACTS_DIR"
    rm -rf "$ARTIFACTS_DIR" || {
      echo "error: could not remove stale $ARTIFACTS_DIR/" >&2
      exit 1
    }
    # children keep it whatever the batch was asked, so neither unlinks the
    # batch log mid-run: only the batch deletes the dir, at end of main()
    _child_args+=(--keep-artifacts)
  fi
  mkdir -p "$ARTIFACTS_DIR" || {
    echo "error: could not create $ARTIFACTS_DIR/" >&2
    exit 1
  }
  _STATUS=0
  _FAILED=()
  local _verbose_args=()
  mapfile -t _verbose_args < <(verbose_flags_of)
  echo "dev/perf2html_batch.sh $TIMESTAMP: ${_CMAKE_FLAGS[*]}" >"$RUN_LOG"
  printf '[%ss] dev/perf2html_batch.sh %s: modified build flags: %s\n' \
    "$(elapsed_format)" "$TIMESTAMP" "${_CMAKE_FLAGS[*]}"

  # --regenerate rebuilds pages from the kept recordings and reads each
  # MANIFEST.txt back to find them, so it must not delete them
  if [ "$_REGENERATE" = 0 ]; then
    printf '[%ss] removing previous reports\n' "$(elapsed_format)"
    reports_clean
  fi
  step_run 1 baseline ./perf2html.sh "${_verbose_args[@]}" \
    "${_child_args[@]}" "--report=$_BASE_DIR"
  step_run 2 modified ./perf2html.sh "${_verbose_args[@]}" \
    "${_child_args[@]}" "--report=$_MOD_DIR" "${_CMAKE_FLAGS[@]}"
  step_run 3 diff ./perf2html_diff.sh "${_verbose_args[@]}" \
    "${_child_args[@]}" "$_BASE_DIR" "$_MOD_DIR" "$_DIFF_DIR"

  if [ "$_STATUS" != 0 ]; then
    printf '[%ss] perf2html_batch: %s step(s) failed: %s\n' \
      "$(elapsed_format)" "${#_FAILED[@]}" "${_FAILED[*]}" >&2
    if [ "$_KEEP_ARTIFACTS" = 0 ]; then
      printf '[%ss] perf2html_batch: %s/ kept for %s\n' \
        "$(elapsed_format)" "$ARTIFACTS_DIR" \
        "diagnosis (a clean run deletes it)" >&2
    fi
    return 1
  fi
  if [ "$_KEEP_ARTIFACTS" = 0 ]; then
    printf '[%ss] removing %s/\n' "$(elapsed_format)" "$ARTIFACTS_DIR"
    rm -rf "$ARTIFACTS_DIR" || {
      echo "error: could not remove $ARTIFACTS_DIR/" >&2
      exit 1
    }
  fi
  printf '[%ss] file://%s/index.html\n' "$(elapsed_format)" "$_DIFF_DIR"
  return 0
}

main "$@"
exit "$?"
