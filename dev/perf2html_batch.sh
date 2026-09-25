#!/usr/bin/env bash

# This comment intentionally blank. No documentation goes here.

set -euo pipefail

TIMESTAMP="$(date +%s)"
INVOKED_FROM="$PWD"
_SCRIPT="$(readlink -f "$0")"
PERF2HTML_DIR_="$(dirname "$_SCRIPT")"
cd "$PERF2HTML_DIR_"

. ./scripts/settings.sh
. ./scripts/shared.sh

_REPO="$(dirname "$PERF2HTML_DIR_")"

# usage_show - the one usage text, printed by -h and on a bad argument
usage_show() {
  cat <<'EOF'
perf2html_batch.sh [debug-flags] [--target-dir=DIR] [cmake-flags...]
    Profiles baseline, modified and then does a diff of them.
    --target-dir=DIR  Holds the three default-named reports (default CWD). The
                      batch cannot rename them.
    cmake-flags:      Every argument not one of its own options, applied to the
                      modified build (default -D CMAKE_C_FLAGS=-Os).

    These are the same debug-flags as the README.md documents:
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

# step_run - run one numbered step, its output reaching the terminal as it
# is. A failed step is a hard error: one line here, then the child's code.
step_run() {
  local _number="$1" _name="$2"
  shift 2
  local _exit_code=0 _start
  _start="$(clock_microseconds)"
  log_verbose "== $_number $_name =="
  # the child prints its own title, every line under it and its own
  # refusal; nothing here captures, buffers or reprints any of it
  "$@" || _exit_code=$?
  _STEP_NAMES+=("$_name")
  _STEP_SECONDS+=("$((($(clock_microseconds) - _start) / 1000000))s")
  log_verbose "== $_number $_name: end =="
  if [ "$_exit_code" = 0 ]; then
    log_verbose "[$(elapsed_format)s] done: step $_number $_name in" \
      "$(duration_format "$_start")"
    return 0
  fi
  printf '\n[%ss] FAILED: step %s %s, exit %s, after %s\n\n' \
    "$(elapsed_format)" "$_number" "$_name" "$_exit_code" \
    "$(duration_format "$_start")" >&2
  exit "$_exit_code"
}

# header_table_print - under --verbose, the one-row table naming what this
# run measures on: when, which revision, toolchain, kernel and pinned core.
header_table_print() {
  # every value first: a fault in one ends the run instead of an empty cell
  local _revision _cmake_version _cc_version _curl_version
  _revision="$(revision_describe "$_REPO")"
  _cmake_version="$(cmake --version | head -1)"
  _cc_version="$(cc --version | head -1)"
  _curl_version="$(sed -n 's/^#define LIBCURL_VERSION "\(.*\)"/\1/p' \
    "$_REPO/include/curl/curlver.h")"
  [ -n "$_curl_version" ] || error_exit 1 \
    "error: no LIBCURL_VERSION define in $_REPO/include/curl/curlver.h"
  table_head_print started git cmake cc curl kernel "pinned cpu"
  table_row_print "$(date '+%F %T %z')" "$_revision" "$_cmake_version" \
    "$_cc_version" "$_curl_version" "$(uname -r)" "$PROFILE_PINNED_CPU"
}

# args_parse - read the command line, deriving every absolute *_DIR from
# the target dir. Every argument it does not name is a cmake flag.
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
}

# regenerate_inputs_verify - --regenerate's first step: all three reports
# and the recordings must be there before anything is created or deleted.
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
  header_table_print
  if [ "$_REGENERATE" = 1 ]; then regenerate_inputs_verify; fi
  local _child_args=("${_PASS_ARGS[@]}" "--artifacts=$ARTIFACTS_DIR")
  if [ "$_KEEP_ARTIFACTS" = 0 ]; then
    log_verbose "[$(elapsed_format)s] removing stale $ARTIFACTS_DIR/"
    rm -rf "$ARTIFACTS_DIR" \
      || error_exit 1 "error: could not remove stale $ARTIFACTS_DIR/"
    # children keep it whatever the batch was asked: only the batch deletes
    # the dir, at the end of main(), so a failed run leaves its recordings
    _child_args+=(--keep-artifacts)
  fi
  mkdir -p "$ARTIFACTS_DIR" \
    || error_exit 1 "error: could not create $ARTIFACTS_DIR/"
  local _verbose_args=()
  mapfile -t _verbose_args < <(verbose_flags_of)
  log_verbose "[$(elapsed_format)s] $_SCRIPT $TIMESTAMP: modified build" \
    "flags: ${_CMAKE_FLAGS[*]}"

  # --regenerate rebuilds pages from the kept recordings and reads each
  # MANIFEST.txt back to find them, so it must not delete them
  if [ "$_REGENERATE" = 0 ]; then
    log_verbose "[$(elapsed_format)s] removing previous reports"
    reports_clean
  fi
  _STEP_NAMES=()
  _STEP_SECONDS=()
  step_run 1 baseline ./perf2html.sh "${_verbose_args[@]}" \
    "${_child_args[@]}" "--report=$_BASE_DIR"
  step_run 2 modified ./perf2html.sh "${_verbose_args[@]}" \
    "${_child_args[@]}" "--report=$_MOD_DIR" "${_CMAKE_FLAGS[@]}"
  step_run 3 diff ./perf2html_diff.sh "${_verbose_args[@]}" \
    "${_child_args[@]}" "$_BASE_DIR" "$_MOD_DIR" "$_DIFF_DIR"
  heading_print "$_SCRIPT, after the three steps"
  table_head_print "${_STEP_NAMES[@]}"
  table_row_print "${_STEP_SECONDS[@]}"

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
