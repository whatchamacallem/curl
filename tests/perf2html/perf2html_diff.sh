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
      _EXTRACTED_ROOT="$(mktemp -d)" || error_exit 1 \
        "error: mktemp could not make the extraction directory"
      ;;
    *) return 0 ;;
  esac
  case "$_BASE_DIR" in
    *"$REPORT_RAW_ARCHIVE_SUFFIX")
      _BASE_DIR="$(archive_extract "$_BASE_DIR" baseline "$_EXTRACTED_ROOT")"
      log_verbose "baseline archive: $_BASE_DIR"
      ;;
  esac
  case "$_MOD_DIR" in
    *"$REPORT_RAW_ARCHIVE_SUFFIX")
      _MOD_DIR="$(archive_extract "$_MOD_DIR" modified "$_EXTRACTED_ROOT")"
      log_verbose "modified archive: $_MOD_DIR"
      ;;
  esac
}

input_archives_clean() {
  [ -n "$_EXTRACTED_ROOT" ] || return 0
  rm -rf "$_EXTRACTED_ROOT" || error_exit 1 \
    "error: could not remove the extracted input at $_EXTRACTED_ROOT"
}

temporary_directories_clean() {
  [ "$KEEP_ARTIFACTS" = 1 ] || artifacts_clean
  input_archives_clean
}

input_path_display() {
  local _dir="$1" _inside="${1#"$_EXTRACTED_ROOT/"}"
  if [ -z "$_EXTRACTED_ROOT" ] || [ "$_inside" = "$_dir" ]; then
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
  ARTIFACTS_DIR="$ARTIFACTS_DIR/$(basename "$_OUT_DIR")"
  _EXTRACTED_ROOT=""
  trap temporary_directories_clean EXIT
  input_archives_extract
}

recorded_reuse() {
  [ -d "$ARTIFACTS_DIR" ] || error_exit 2 \
    "error: --regenerate: no recordings at $ARTIFACTS_DIR"
  local _log_pattern="$DIFF_TOOL_NAME.*.log" _found_names
  local -a _found_logs
  mapfile -t _found_logs < <(find "$ARTIFACTS_DIR" -mindepth 1 -maxdepth 1 \
    -type f -name "$_log_pattern" | sort)
  _found_names="${_found_logs[*]##*/}"
  [ "${#_found_logs[@]}" = 1 ] || error_exit 2 "error: --regenerate: \
$ARTIFACTS_DIR holds ${#_found_logs[@]} $_log_pattern, the log of the run to \
reuse, expected 1${_found_names:+: $_found_names}"
  TIMESTAMP="${_found_names#"$DIFF_TOOL_NAME".}"
  TIMESTAMP="${TIMESTAMP%.log}"
}

manifest_check() {
  local _dir="$1" _role="$2" _manifest="$1/MANIFEST.txt" _reason
  if [ -f "$_manifest" ] \
    && [ "$(head -1 "$_manifest")" = "$REPORT_MANIFEST_VERSION_DIFF" ]; then
    _reason="error: can't diff a diff: the $_role report was written by"
    error_exit 2 "$_reason perf2html_diff.sh: $_dir"
  fi
  manifest_recorded "$_dir" "$_role" "$REPORT_MANIFEST_VERSION_FULL" \
    >/dev/null
  manifest_value "$_dir" recorded
}

sources_match_check() {
  local _baseline_sources="$_BASE_DIR/$REPORT_SOURCES_DIR_NAME"
  local _modified_sources="$_MOD_DIR/$REPORT_SOURCES_DIR_NAME"
  local _sources _baseline_checksum _modified_checksum _reason
  for _sources in "$_baseline_sources" "$_modified_sources"; do
    [ -d "$_sources" ] || error_exit 2 "error: no source directory: $_sources"
  done
  _baseline_checksum="$(checksum_compute "$_baseline_sources")"
  _modified_checksum="$(checksum_compute "$_modified_sources")"
  _reason="error: the two reports show different source code: checksum"
  _reason+=" $_baseline_checksum of $_baseline_sources vs $_modified_checksum"
  [ "$_baseline_checksum" = "$_modified_checksum" ] || error_exit 2 \
    "$_reason of $_modified_sources"
}

header_file() {
  local _dir="$1" _role="$2" _out
  _out="$(artifact_path header-block "$_role")"
  {
    echo "report=$(input_path_display "$_dir")"
    grep '=' "$_dir/MANIFEST.txt" \
      || error_exit 2 "error: no LABEL=VALUE row in $_dir/MANIFEST.txt"
  } >"$_out"
  echo "$_out"
}

timer_artifacts_find() {
  local _dir="$1" _role="$2" _archive_pattern _found_names _reason
  local -a _found_archives
  _archive_pattern="$TIMER_ARTIFACTS_NAME_PREFIX*$REPORT_RAW_ARCHIVE_SUFFIX"
  mapfile -t _found_archives < <(find "$_dir" -mindepth 1 -maxdepth 1 -type f \
    -name "$_archive_pattern" | sort)
  _found_names="${_found_archives[*]##*/}"
  _reason="error: the $_role report holds ${#_found_archives[@]}"
  _reason+=" $_archive_pattern at its top, expected 1: $_dir"
  [ "${#_found_archives[@]}" = 1 ] || error_exit 2 \
    "$_reason${_found_names:+: $_found_names}"
  printf -v "$3" '%s' "${_found_archives[0]}"
}

profiles_extract() {
  local _archive="$1" _role="$2" _into _root_name _recorded _profiles
  local -a _files
  _into="$(artifact_path extracted-profiles "$_role")"
  _root_name="$(basename "$_archive" "$REPORT_RAW_ARCHIVE_SUFFIX")"
  _recorded="${_root_name#"$TIMER_ARTIFACTS_NAME_PREFIX"}"
  rm -rf "$_into"
  mkdir -p "$_into"
  command_run tar xJf "$_archive" -C "$_into"
  [ -d "$_into/$_root_name" ] || error_exit 2 \
    "error: $_archive holds no $_root_name directory"
  _profiles="$(basename "$(artifact_path callgrind '*' "$_recorded")")"
  mapfile -t _files < <(find "$_into/$_root_name" -maxdepth 1 -type f \
    -name "$_profiles")
  [ "${#_files[@]}" != 0 ] || error_exit 2 \
    "error: no $_profiles file in $_archive"
  printf -v "$3" '%s' "$_into/$_root_name/$_profiles"
  printf -v "$4" '%s' "$_into/$_root_name/$(basename "$(artifact_path \
    callgrind-file-data "" "$_recorded")")"
}

tests_names() {
  local _profiles _tail _file
  _profiles="$(basename "$1")"
  _tail="${_profiles#*\*}"
  {
    echo "$REPORT_TEST_SUITE_NAME"
    find "$(dirname "$1")" -maxdepth 1 -type f -name "$_profiles" \
      -printf '%f\n' | while IFS= read -r _file; do
      echo "${_file%"$_tail"}"
    done
  } | sort
}

tests_pair() {
  local _base_tests _cur_tests _name
  _base_tests="$(tests_names "$_BASELINE_PROFILES")"
  _cur_tests="$(tests_names "$_MODIFIED_PROFILES")"
  local _one_sided="is in only one of the two reports, so it has no delta:"
  for _name in $(comm -3 <(echo "$_base_tests") <(echo "$_cur_tests")); do
    error_exit 2 "error: '$_name' $_one_sided $_BASE_DIR vs $_MOD_DIR"
  done
  comm -12 <(echo "$_base_tests") <(echo "$_cur_tests")
}

diff_one() {
  local _name="$1" _diff_file _callers_file
  local _baseline_profiles="$_BASELINE_PROFILES"
  local _modified_profiles="$_MODIFIED_PROFILES"
  local -a _derive
  _diff_file="$(artifact_path delta "$_name")"
  _callers_file="$(artifact_path caller-counts "$_name")"
  if [ "$_name" != "$REPORT_TEST_SUITE_NAME" ]; then
    _baseline_profiles="${_baseline_profiles/\*/$_name}"
    _modified_profiles="${_modified_profiles/\*/$_name}"
  fi
  _derive=(--baseline-paths "$_BASELINE_PATHS"
    --modified-paths "$_MODIFIED_PATHS")

  heading_print "python3 callgrind_diff.py $_name"
  command_run python3 "$PERF2HTML_DIR_/scripts/callgrind_diff.py" \
    -o "$_diff_file" --callers-output "$_callers_file" \
    --baseline "$_baseline_profiles" --current "$_modified_profiles" \
    "${_derive[@]}"

  heading_print "python3 callgrind_to_heatmap.py data $_name --diff"
  command_run python3 "$PERF2HTML_DIR_/scripts/callgrind_to_heatmap.py" data \
    "$_diff_file" --report-dir "$_OUT_DIR" --test "$_name" --diff \
    --baseline-data "$_callers_file" "${_derive[@]}" \
    --sources-dir "$_BASE_DIR/$REPORT_SOURCES_DIR_NAME"

  heading_print "python3 build_report.py test $_name"
  command_run python3 "$PERF2HTML_DIR_/scripts/build_report.py" test \
    "$_diff_file" -o "$_OUT_DIR" --test "$_name" --diff \
    --callers-data "$_callers_file"
  log_verbose "$(printf '%-13sdiff: %s' "$_name" "$_OUT_DIR")"
}

main() {
  args_parse "$@"
  verbose_begin
  title_print "$_SCRIPT" "$@"

  local _base_recorded _mod_recorded
  _base_recorded="$(manifest_check "$_BASE_DIR" baseline)"
  _mod_recorded="$(manifest_check "$_MOD_DIR" modified)"
  sources_match_check
  timer_artifacts_find "$_BASE_DIR" baseline _BASELINE_TIMER_ARTIFACTS_ARCHIVE
  timer_artifacts_find "$_MOD_DIR" modified _MODIFIED_TIMER_ARTIFACTS_ARCHIVE

  path_overlap_check "$_OUT_DIR" "diff report" \
    "$_BASE_DIR" "baseline report" \
    "$_MOD_DIR" "modified report" \
    "$ARTIFACTS_DIR" "artifacts dir"

  if [ "$REGENERATE" = 1 ]; then recorded_reuse; fi

  report_delete "$_OUT_DIR"
  [ "$REGENERATE" = 1 ] || artifacts_clean
  local _log_kind=diff-log _log_file
  if [ "$REGENERATE" = 1 ]; then
    _log_kind=diff-regenerate-log
  fi
  _log_file="$(artifact_path "$_log_kind" "")"
  report_begin "$_OUT_DIR" "$_log_file" \
    "tests/perf2html/perf2html_diff.sh $TIMESTAMP: $_BASE_DIR: $_MOD_DIR: \
$_OUT_DIR"

  local _tests _test_name
  local -a _args
  profiles_extract "$_BASELINE_TIMER_ARTIFACTS_ARCHIVE" baseline \
    _BASELINE_PROFILES _BASELINE_PATHS
  profiles_extract "$_MODIFIED_TIMER_ARTIFACTS_ARCHIVE" modified \
    _MODIFIED_PROFILES _MODIFIED_PATHS
  _tests="$(tests_pair)"
  log_verbose "$_SCRIPT $TIMESTAMP: $(basename "$_BASE_DIR"):" \
    "$(basename "$_MOD_DIR")"
  _args=(-o "$_OUT_DIR/index.html" --diff
    --header-block "baseline=$(header_file "$_BASE_DIR" baseline)"
    --header-block "modified=$(header_file "$_MOD_DIR" modified)"
    --diff-profile "$(artifact_path delta '*')")
  for _test_name in $_tests; do
    diff_one "$_test_name"
  done
  heading_print "python3 callgrind_to_heatmap.py page"
  command_run python3 "$PERF2HTML_DIR_/scripts/callgrind_to_heatmap.py" page \
    --report-dir "$_OUT_DIR"
  heading_print "python3 build_report.py overview --diff"
  command_run python3 "$PERF2HTML_DIR_/scripts/build_report.py" overview \
    "${_args[@]}"
  log_verbose "$(printf '%-13s%s' overview "$_OUT_DIR/index.html")"

  report_finish "$_OUT_DIR" "$REPORT_MANIFEST_VERSION_DIFF" \
    "baseline=$(input_path_display "$_BASE_DIR")" \
    "modified=$(input_path_display "$_MOD_DIR")" \
    "baseline_recorded=$_base_recorded" \
    "modified_recorded=$_mod_recorded"
}

main "$@"
