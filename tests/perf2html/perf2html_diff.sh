#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.
#
# This comment intentionally blank. No documentation goes here.

usage_show() {
  cat <<'EOF'
perf2html_diff.sh [debug-flags] [--target-dir=DIR] [baseline] [modified] [diff]
    Measures nothing: Compares the counters in two profiling reports and
    generates a diff. Report names default to
    ./perf2html_{baseline,modified,diff}_report. Both baseline and modified
    must be a perf2html.sh report, and both must show the same source code.
    And a diff can't be re-diffed. Reads nothing but the two reports.
    --target-dir=DIR  Default directory for reports (default $PWD).
    --txz             Create .txz archives of all reports generated.
                      .txz files may also be used as inputs.

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
_SCRIPT="$(readlink -f -- "$0")"
cd -P -- "$(dirname -- "$_SCRIPT")"
PERF2HTML_DIR_="$PWD"

. ./scripts/settings.sh
. ./scripts/utility.sh

input_archives_extract() {
  case "$_BASE_DIR$_MOD_DIR" in
    *"$REPORT_RAW_ARCHIVE_SUFFIX"*)
      EXTRACTED_ROOT="$(mktemp -d)" || error_exit 1 \
        "error: mktemp could not make the extraction directory"
      ;;
    *) return 0 ;;
  esac
  case "$_BASE_DIR" in
    *"$REPORT_RAW_ARCHIVE_SUFFIX")
      _BASE_DIR="$(archive_extract "$_BASE_DIR" baseline "$EXTRACTED_ROOT")"
      log_verbose "baseline archive: $_BASE_DIR"
      ;;
  esac
  case "$_MOD_DIR" in
    *"$REPORT_RAW_ARCHIVE_SUFFIX")
      _MOD_DIR="$(archive_extract "$_MOD_DIR" modified "$EXTRACTED_ROOT")"
      log_verbose "modified archive: $_MOD_DIR"
      ;;
  esac
}

input_path_display() {
  local _dir="$1" _inside="${1#"$EXTRACTED_ROOT/"}"
  if [ -z "$EXTRACTED_ROOT" ] || [ "$_inside" = "$_dir" ]; then
    path_display "$_dir"
  else
    echo "$DIFF_EXTRACTED_ROOT_DISPLAY_NAME/$_inside"
  fi
}

args_parse() {
  options_parse "$@"
  local _remaining_argument _report_names=()
  for _remaining_argument in "${REMAINING_ARGUMENTS[@]}"; do
    case "$_remaining_argument" in
      -*) error_exit 2 "error: unknown option: $_remaining_argument" ;;
      *) _report_names+=("$_remaining_argument") ;;
    esac
  done
  set -- "${_report_names[@]}"
  _BASE_DIR="$REPORT_BASELINE_DIR_NAME"
  _MOD_DIR="$REPORT_MODIFIED_DIR_NAME"
  _OUT_DIR="$REPORT_DIFF_DIR_NAME"
  case $# in
    0) ;;
    1) _BASE_DIR="$1" ;;
    2)
      _BASE_DIR="$1"
      _MOD_DIR="$2"
      ;;
    3)
      _BASE_DIR="$1"
      _MOD_DIR="$2"
      _OUT_DIR="$3"
      ;;
    *)
      error_exit 2 \
        "error: unknown argument: $4, at most 3 directories are taken"
      ;;
  esac
  _BASE_DIR="$(report_path "$_BASE_DIR")"
  _MOD_DIR="$(report_path "$_MOD_DIR")"
  _OUT_DIR="$(report_path "$_OUT_DIR")"
  artifacts_dir_resolve "$(dirname "$_OUT_DIR")"
  report_artifacts_dir REPORT_ARTIFACTS_DIR "$_OUT_DIR"
  input_archives_extract
}

manifest_check() {
  local _dir="$1" _role="$2" _manifest="$1/MANIFEST.txt" _reason
  if [ -f "$_manifest" ] \
    && [ "$(head -1 "$_manifest")" = "$REPORT_MANIFEST_VERSION_DIFF" ]; then
    _reason="error: can't diff a diff: the $_role report was written by"
    error_exit 2 "$_reason perf2html_diff.sh: $_dir"
  fi
  manifest_verify "$_dir" "$_role" "$REPORT_MANIFEST_VERSION_FULL"
  recorded_time_read "$3" "$_manifest"
  printf -v "$4" '%s' "$(manifest_value "$_manifest" recorded)"
}

sources_match_check() {
  local _baseline_sources="$_BASE_DIR/$REPORT_SOURCES_DIR_NAME"
  local _modified_sources="$_MOD_DIR/$REPORT_SOURCES_DIR_NAME"
  local _sources _source _twin
  for _sources in "$_baseline_sources" "$_modified_sources"; do
    [ -d "$_sources" ] || error_exit 2 "error: no source directory: $_sources"
  done
  for _source in "$_baseline_sources"/*; do
    _twin="$_modified_sources/${_source##*/}"
    [ ! -f "$_twin" ] || cmp -s "$_source" "$_twin" || error_exit 2 \
      "error: the two reports show different source code: $_source vs $_twin"
  done
}

timer_artifacts_check() {
  local _dir="$1" _role="$2" _recorded_time="$3" _archive
  raw_data_archive_path _archive "$_dir" "$_recorded_time"
  [ -f "$_archive" ] || error_exit 2 \
    "error: the $_role report holds no raw data archive: $_archive"
  printf -v "$4" '%s' "$_archive"
}

inputs_check() {
  manifest_check "$_BASE_DIR" baseline _BASELINE_RECORDED_TIME \
    _BASELINE_RECORDED
  manifest_check "$_MOD_DIR" modified _MODIFIED_RECORDED_TIME \
    _MODIFIED_RECORDED
  sources_match_check
  timer_artifacts_check "$_BASE_DIR" baseline "$_BASELINE_RECORDED_TIME" \
    _BASELINE_TIMER_ARTIFACTS_ARCHIVE
  timer_artifacts_check "$_MOD_DIR" modified "$_MODIFIED_RECORDED_TIME" \
    _MODIFIED_TIMER_ARTIFACTS_ARCHIVE
  path_overlap_check "$_OUT_DIR" "diff report" \
    "$_BASE_DIR" "baseline report" \
    "$_MOD_DIR" "modified report" \
    "$REPORT_ARTIFACTS_DIR" "artifacts dir"
}

report_prepare() {
  if [ "$REGENERATE" = 1 ]; then
    [ -d "$REPORT_ARTIFACTS_DIR" ] || error_exit 2 \
      "error: --regenerate: no recordings at $REPORT_ARTIFACTS_DIR"
  fi
  report_delete "$_OUT_DIR"
  [ "$REGENERATE" = 1 ] || artifacts_clean
  local _log_kind=diff-log _log_file
  if [ "$REGENERATE" = 1 ]; then
    _log_kind=diff-regenerate-log
  fi
  artifact_path _log_file "$REPORT_ARTIFACTS_DIR" "$_log_kind"
  report_begin "$_OUT_DIR" "$_log_file" \
    "tests/perf2html/perf2html_diff.sh $TIMESTAMP: $_BASE_DIR: $_MOD_DIR: \
$_OUT_DIR"
}

profiles_extract() {
  local _archive="$1" _kind="$2" _into
  artifact_path _into "$REPORT_ARTIFACTS_DIR" "$_kind"
  rm -rf "$_into"
  mkdir "$_into"
  command_run tar xJf "$_archive" --strip-components=1 -C "$_into"
  artifacts_verify archive "$_into"
}

header_block_write() {
  local _dir="$1" _kind="$2" _header_block
  artifact_path _header_block "$REPORT_ARTIFACTS_DIR" "$_kind"
  {
    echo "report=$(input_path_display "$_dir")"
    grep '=' "$_dir/MANIFEST.txt" \
      || error_exit 2 "error: no LABEL=VALUE row in $_dir/MANIFEST.txt"
  } >"$_header_block"
}

inputs_extract() {
  profiles_extract "$_BASELINE_TIMER_ARTIFACTS_ARCHIVE" baseline-profiles
  profiles_extract "$_MODIFIED_TIMER_ARTIFACTS_ARCHIVE" modified-profiles
  header_block_write "$_BASE_DIR" baseline-header
  header_block_write "$_MOD_DIR" modified-header
}

tests_pair() {
  local _profiles _kept_list _name
  local -a _paired_tests _modified_tests
  local -A _baseline_named=() _modified_named=()
  local _one_sided="is in only one of the two reports, so it has no delta:"
  artifact_path _profiles "$REPORT_ARTIFACTS_DIR" baseline-profiles
  test_list_read "$_profiles"
  _paired_tests=("${TEST_LIST[@]}")
  artifact_path _profiles "$REPORT_ARTIFACTS_DIR" modified-profiles
  test_list_read "$_profiles"
  _modified_tests=("${TEST_LIST[@]}")
  for _name in "${_paired_tests[@]}"; do _baseline_named[$_name]=1; done
  for _name in "${_modified_tests[@]}"; do _modified_named[$_name]=1; done
  for _name in "${_paired_tests[@]}" "${_modified_tests[@]}"; do
    [[ -v _baseline_named[$_name] && -v _modified_named[$_name] ]] \
      || error_exit 2 "error: '$_name' $_one_sided $_BASE_DIR vs $_MOD_DIR"
  done
  if [ "$REGENERATE" = 1 ]; then
    test_list_read "$REPORT_ARTIFACTS_DIR"
    artifact_path _kept_list "$REPORT_ARTIFACTS_DIR" test-list
    [ "${TEST_LIST[*]}" = "${_paired_tests[*]}" ] || error_exit 2 "error: \
--regenerate: $_kept_list names ${TEST_LIST[*]}, the two reports pair \
${_paired_tests[*]}"
  fi
  test_list_write "$REPORT_ARTIFACTS_DIR" "${_paired_tests[@]}"
}

deltas_write() {
  log_verbose "$_SCRIPT $TIMESTAMP: $(basename "$_BASE_DIR"):" \
    "$(basename "$_MOD_DIR")"
  heading_print "python3 callgrind_diff.py"
  command_run python3 "$PERF2HTML_DIR_/scripts/callgrind_diff.py" \
    "--artifacts=$ARTIFACTS_DIR" "--report=$_OUT_DIR"
  artifacts_verify diffed
}

pages_write() {
  local _flags=("--artifacts=$ARTIFACTS_DIR" "--report=$_OUT_DIR" --diff)
  page_tool_run callgrind_to_heatmap.py data "${_flags[@]}" \
    "--baseline=$_BASE_DIR" "--modified=$_MOD_DIR"
  page_tool_run build_report.py callers "${_flags[@]}"
  page_tool_run build_report.py call-graph "${_flags[@]}"
  page_tool_run callgrind_to_heatmap.py page "--report=$_OUT_DIR"
  page_tool_run build_report.py overview "${_flags[@]}" \
    "${README_HTML_FLAGS[@]}"
  log_verbose "$(printf '%-13s%s' overview "$_OUT_DIR/$OVERVIEW_PAGE_PATH")"
  report_finish "$_OUT_DIR" "$REPORT_MANIFEST_VERSION_DIFF" \
    "baseline=$(input_path_display "$_BASE_DIR")" \
    "modified=$(input_path_display "$_MOD_DIR")" \
    "baseline_recorded=$_BASELINE_RECORDED" \
    "modified_recorded=$_MODIFIED_RECORDED"
}

main() {
  args_parse "$@"
  verbose_begin
  title_print "$_SCRIPT" "$@"
  step_run 1 inputs inputs_check
  step_run 2 report report_prepare
  step_run 3 extract inputs_extract
  step_run 4 pair tests_pair
  step_run 5 deltas deltas_write
  step_run 6 pages pages_write
  heading_print "$_SCRIPT, after the six steps"
  table_print "${#STEP_NAMES[@]}" "${STEP_NAMES[@]}" "${STEP_SECONDS[@]}"
}

main "$@"
