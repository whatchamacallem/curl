#!/usr/bin/env bash

# This comment intentionally blank. No documentation goes here.

set -euo pipefail

TIMESTAMP="$(date +%s)"
INVOKED_FROM="$PWD"
_SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$_SCRIPT")"

. ./scripts/settings.sh
. ./scripts/shared.sh

# usage_show - the one usage text, printed by -h and on a bad argument
usage_show() {
  cat <<'EOF'
perf2html_batch.sh [debug-flags] [--target-dir=DIR] [cmake-flags...]
    Profiles baseline, modified and then does a diff of them.
    --target-dir=DIR  Holds the three default-named reports (default CWD). The
                      batch cannot rename them.
    cmake-flags       Every argument not one of its own options, applied to the
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
    --verbose         Enables diagnostic information. Repeating it (--verbose
                      --verbose) increments the verbosity level.
EOF
}

# step_run - run one numbered step, logging it. A failed step is a hard
# error: nothing downstream of a bad report is worth a reader's time.
step_run() {
  local _number="$1" _name="$2"
  shift 2
  local _exit_code _start
  _start="$(clock_microseconds)"
  log_verbose "== $_number $_name =="
  # the child prints its own title and every line under it, so nothing is
  # announced here: its output is relayed as it is
  script_capture "$@"
  _exit_code="$CHILD_EXIT_CODE"
  log_verbose "== $_number $_name: end =="
  if [ "$_exit_code" = 0 ]; then
    log_verbose "[$(elapsed_format)s] done: step $_number $_name in" \
      "$(duration_format "$_start")"
    return 0
  fi
  printf '\n[%ss] FAILED: step %s %s, exit %s, after %s\n\n' \
    "$(elapsed_format)" "$_number" "$_name" "$_exit_code" \
    "$(duration_format "$_start")" >&2
  failure_relay
  exit "$_exit_code"
}

# args_parse - read the command line, deriving every absolute *_DIR and
# RUN_LOG from the target dir. Every argument it does not name is a cmake flag.
args_parse() {
  _KEEP_ARTIFACTS=0
  _REGENERATE=0
  _PASS_ARGS=()
  _CMAKE_FLAGS=()
  _TARGET_DIR="."
  ARTIFACTS_DIR=""
  while [ $# -gt 0 ]; do
    case "$1" in
      -h | --help)
        usage_show
        exit 0
        ;;
      --verbose)
        VERBOSE=$((VERBOSE + 1))
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

regenerate_inputs_verify() {
  manifest_verify "$_BASE_DIR" "--regenerate input" \
    "$REPORT_MANIFEST_VERSION_FULL"
  manifest_verify "$_MOD_DIR" "--regenerate input" \
    "$REPORT_MANIFEST_VERSION_FULL"
  manifest_verify "$_DIFF_DIR" "--regenerate input" \
    "$REPORT_MANIFEST_VERSION_DIFF"
  [ -d "$ARTIFACTS_DIR" ] || error_exit 2 \
    "error: --regenerate input: no recordings at $ARTIFACTS_DIR"
}

# reports_clean - deletes the three report directories
reports_clean() {
  rm -rf "$_BASE_DIR" "$_MOD_DIR" "$_DIFF_DIR" || error_exit 1 \
    "error: could not remove previous reports under $_TARGET_DIR"
}

# main - runs baseline, modified and diff, stopping at the first failure,
# and owns every deletion of the artifacts directory.
main() {
  args_parse "$@"
  verbose_begin
  title_print "$_SCRIPT" "$@"
  if [ "$_REGENERATE" = 1 ]; then regenerate_inputs_verify; fi
  local _child_args=("${_PASS_ARGS[@]}" "--artifacts=$ARTIFACTS_DIR")
  if [ "$_KEEP_ARTIFACTS" = 0 ]; then
    log_verbose "[$(elapsed_format)s] removing stale $ARTIFACTS_DIR/"
    rm -rf "$ARTIFACTS_DIR" \
      || error_exit 1 "error: could not remove stale $ARTIFACTS_DIR/"
    # children keep it whatever the batch was asked, so neither unlinks the
    # batch log mid-run: only the batch deletes the dir, at end of main()
    _child_args+=(--keep-artifacts)
  fi
  mkdir -p "$ARTIFACTS_DIR" \
    || error_exit 1 "error: could not create $ARTIFACTS_DIR/"
  local _verbose_args=()
  mapfile -t _verbose_args < <(verbose_flags_of)
  echo "dev/perf2html_batch.sh $TIMESTAMP: ${_CMAKE_FLAGS[*]}" >"$RUN_LOG"
  log_verbose "[$(elapsed_format)s] $_SCRIPT $TIMESTAMP: modified build" \
    "flags: ${_CMAKE_FLAGS[*]}"

  # --regenerate rebuilds pages from the kept recordings and reads each
  # MANIFEST.txt back to find them, so it must not delete them
  if [ "$_REGENERATE" = 0 ]; then
    log_verbose "[$(elapsed_format)s] removing previous reports"
    reports_clean
  fi
  step_run 1 baseline ./perf2html.sh "${_verbose_args[@]}" \
    "${_child_args[@]}" "--report=$_BASE_DIR"
  step_run 2 modified ./perf2html.sh "${_verbose_args[@]}" \
    "${_child_args[@]}" "--report=$_MOD_DIR" "${_CMAKE_FLAGS[@]}"
  step_run 3 diff ./perf2html_diff.sh "${_verbose_args[@]}" \
    "${_child_args[@]}" "$_BASE_DIR" "$_MOD_DIR" "$_DIFF_DIR"

  # only a run reaching here succeeded, so a failed one leaves its
  # recordings behind for diagnosis without being told to
  if [ "$_KEEP_ARTIFACTS" = 0 ]; then
    log_verbose "[$(elapsed_format)s] removing $ARTIFACTS_DIR/"
    rm -rf "$ARTIFACTS_DIR" \
      || error_exit 1 "error: could not remove $ARTIFACTS_DIR/"
  else
    log_verbose "[$(elapsed_format)s] artifacts kept"
  fi
  log_verbose "[$(elapsed_format)s] $_DIFF_DIR/index.html"
  return 0
}

main "$@"
exit "$?"
