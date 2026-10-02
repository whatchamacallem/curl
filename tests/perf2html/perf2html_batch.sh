#!/usr/bin/env bash

# This comment intentionally blank. No documentation goes here.

usage_show() {
  cat <<'EOF'
perf2html_batch.sh [debug-flags] [--target-dir=DIR] [cmake-flags...]
    Profiles baseline, modified and then does a diff of them.
    --target-dir=DIR  Holds the three default-named reports (default $PWD). The
                      batch cannot rename them.
    --txz             Create .txz archives of all reports generated.
                      .txz files may also be used as inputs.
    cmake-flags:      Every argument not one of its own options, applied to the
                      modified build (default -D CMAKE_C_FLAGS=-Os).

    The debug-flags are the same as the README.md documents.
    --artifacts=TMP   The profiler artifacts directory. Defaults to
                      perf2html_temporary_artifacts/ beside the report
                      directory (inside the target dir for a batch).
    --keep-artifacts  Flushes the report's stale artifacts subdirectory, then
                      keeps this run's recordings, which is what a later
                      --regenerate reuses.
    --regenerate      Rebuilds all pages from the last run's profiler
                      artifacts, re-measuring nothing and keeping them.
    --verbose         Enables diagnostic information in Markdown. Repeating it
                      (--verbose --verbose) increments the verbosity level.
EOF
}

set -euo pipefail

TIMESTAMP="$(date +%s)"
INVOKED_FROM="$PWD"
_SCRIPT="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
PERF2HTML_DIR_="$(dirname "$_SCRIPT")"
cd "$PERF2HTML_DIR_"

. ./scripts/settings.sh
. ./scripts/utility.sh

_REPO="$(dirname "$(dirname "$PERF2HTML_DIR_")")"

step_run() {
  local _number="$1" _name="$2"
  shift 2
  local _exit_code=0 _start
  _start="$(clock_microseconds)"
  log_verbose "Starting: $_number $_name..."
  "$@" || _exit_code=$?
  _STEP_NAMES+=("$_name")
  _STEP_SECONDS+=("$((($(clock_microseconds) - _start) / 1000000))s")
  if [ "$_exit_code" = 0 ]; then
    log_verbose "[$(elapsed_format)s] Done: step $_number $_name in" \
      "$(duration_format "$_start")."
    return 0
  fi
  printf '\n[%ss] FAILED: step %s %s, exit %s, after %s\n\n' \
    "$(elapsed_format)" "$_number" "$_name" "$_exit_code" \
    "$(duration_format "$_start")" >&2
  exit "$_exit_code"
}

header_table_print() {
  local _revision _cmake_version _cc_version _curl_version
  _revision="$(revision_describe "$_REPO")"
  _cmake_version="$(cmake --version | head -1)"
  _cc_version="$(cc --version | head -1)"
  _curl_version="$(sed -n 's/^#define LIBCURL_VERSION "\(.*\)"/\1/p' \
    "$_REPO/include/curl/curlver.h")"
  [ -n "$_curl_version" ] || error_exit 1 \
    "error: no LIBCURL_VERSION define in $_REPO/include/curl/curlver.h"
  table_print 7 started git cmake cc curl kernel "pinned cpu" \
    "$(date '+%F %T %z')" "$_revision" "$_cmake_version" "$_cc_version" \
    "$_curl_version" "$(uname -r)" "$PROFILE_PINNED_CPU"
}

args_parse() {
  shared_options_parse "$@"
  local _remaining_argument
  for _remaining_argument in "${REMAINING_ARGUMENTS[@]}"; do
    case "$_remaining_argument" in
      --report=*)
        error_exit 2 \
          "error: the batch takes no --report=: $_remaining_argument"
        ;;
    esac
  done
  _CMAKE_FLAGS=("${REMAINING_ARGUMENTS[@]}")
  [ "${#_CMAKE_FLAGS[@]}" -gt 0 ] || _CMAKE_FLAGS=("${DEFAULT_FLAGS[@]}")
  artifacts_dir_resolve "$TARGET_DIR"
  _BASE_DIR="$(report_path_of "$REPORT_BASELINE_DIR_NAME")"
  _MOD_DIR="$(report_path_of "$REPORT_MODIFIED_DIR_NAME")"
  _DIFF_DIR="$(report_path_of "$REPORT_DIFF_DIR_NAME")"
}

main() {
  args_parse "$@"
  verbose_begin
  title_print "$_SCRIPT" "$@"
  header_table_print

  local _dir _cache
  path_overlap_check "$ARTIFACTS_DIR" "artifacts dir" \
    "$_BASE_DIR" "baseline report" \
    "$_MOD_DIR" "modified report" \
    "$_DIFF_DIR" "diff report"
  if [ "$REGENERATE" = 1 ]; then
    for _dir in "$_BASE_DIR" "$_MOD_DIR" "$_DIFF_DIR"; do
      _cache="$ARTIFACTS_DIR/$(basename "$_dir")"
      [ -d "$_cache" ] || error_exit 2 \
        "error: --regenerate: no recordings at $_cache"
    done
  fi
  local _child_args=("--target-dir=$TARGET_DIR" "--artifacts=$ARTIFACTS_DIR")
  if [ "$REGENERATE" = 1 ]; then
    _child_args+=(--regenerate)
  else
    _child_args+=(--keep-artifacts)
  fi
  [ "$WRITE_REPORT_ARCHIVE" = 0 ] || _child_args+=(--txz)
  local _verbose_args=()
  mapfile -t _verbose_args < <(verbose_flags_of)
  log_verbose "[$(elapsed_format)s] $_SCRIPT $TIMESTAMP: modified build" \
    "flags: ${_CMAKE_FLAGS[*]}"

  log_verbose "[$(elapsed_format)s] removing previous reports"
  for _dir in "$_BASE_DIR" "$_MOD_DIR" "$_DIFF_DIR"; do
    report_delete "$_dir"
  done

  _STEP_NAMES=()
  _STEP_SECONDS=()
  step_run 1 baseline ./perf2html.sh "${_verbose_args[@]}" "${_child_args[@]}"
  step_run 2 modified ./perf2html.sh "${_verbose_args[@]}" \
    "${_child_args[@]}" "${_CMAKE_FLAGS[@]}"
  step_run 3 diff ./perf2html_diff.sh "${_verbose_args[@]}" \
    "${_child_args[@]}"

  heading_print "$_SCRIPT, after the three steps"
  table_print "${#_STEP_NAMES[@]}" "${_STEP_NAMES[@]}" "${_STEP_SECONDS[@]}"

  if [ "$KEEP_ARTIFACTS" = 0 ]; then
    log_verbose "[$(elapsed_format)s] removing $ARTIFACTS_DIR/"
    rm -rf "$ARTIFACTS_DIR" \
      || error_exit 1 "error: could not remove $ARTIFACTS_DIR/"
  else
    log_verbose "[$(elapsed_format)s] keeping $ARTIFACTS_DIR/"
  fi
  log_verbose "[$(elapsed_format)s] $_DIFF_DIR/index.html"
}

main "$@"
