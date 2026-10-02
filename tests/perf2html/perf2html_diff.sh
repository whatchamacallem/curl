#!/usr/bin/env bash

# This comment intentionally blank. No documentation goes here.

usage_show() {
  cat <<'EOF'
perf2html_diff.sh [debug-flags] [--target-dir=DIR] [baseline] [modified] [diff]
    Measures nothing: Compares the counters in two profiling reports and
    generates a diff. Report names default to
    ./perf2html_{baseline,modified,diff}_report. Both baseline and modified
    must be a perf2html.sh report. And a diff can't be re-diffed.
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
_SCRIPT="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
PERF2HTML_DIR_="$(dirname "$_SCRIPT")"
cd "$PERF2HTML_DIR_"

. ./scripts/settings.sh
. ./scripts/utility.sh

input_archives_extract() {
  _EXTRACTED_ROOT=""
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

args_parse() {
  shared_options_parse "$@"
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
  _BASE_DIR="$(report_path_of "$_BASE_DIR")"
  _MOD_DIR="$(report_path_of "$_MOD_DIR")"
  _OUT_DIR="$(report_path_of "$_OUT_DIR")"
  input_archives_extract
  artifacts_dir_resolve "$(dirname "$_OUT_DIR")"
  ARTIFACTS_DIR="$ARTIFACTS_DIR/$(basename "$_OUT_DIR")"
}

manifest_check() {
  local _dir="$1" _role="$2" _manifest="$1/MANIFEST.txt" _reason
  if [ -f "$_manifest" ] \
    && [ "$(head -1 "$_manifest")" = "$REPORT_MANIFEST_VERSION_DIFF" ]; then
    _reason="error: can't diff a diff: the $_role report was written by"
    error_exit 2 "$_reason perf2html_diff.sh: $_dir"
  fi
  manifest_recorded_of "$_dir" "$_role" "$REPORT_MANIFEST_VERSION_FULL" \
    >/dev/null
  manifest_value "$_dir" recorded
}

header_file_of() {
  local _dir="$1" _role="$2" _out
  _out="$(artifact_path_of header-block "$_role")"
  {
    echo "report=$(path_display "$_dir")"
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
  local _archive="$1" _role="$2" _listing="$3"
  local _into _root_directory _file _test
  local -a _files
  _into="$(artifact_path_of extracted-profiles "$_role")"
  _root_directory="$(basename "$_archive" "$REPORT_RAW_ARCHIVE_SUFFIX")"
  _root_directory="$_into/$_root_directory"
  rm -rf "$_into"
  mkdir -p "$_into"
  command_run tar xJf "$_archive" -C "$_into"
  [ -d "$_root_directory" ] || error_exit 2 \
    "error: $_archive holds no $(basename "$_root_directory") directory"
  mapfile -t _files < <(find "$_root_directory" -maxdepth 1 -type f \
    -name "$CALLGRIND_OUTPUT_FILE_PREFIX.*" | sort)
  [ "${#_files[@]}" != 0 ] || error_exit 2 \
    "error: no $CALLGRIND_OUTPUT_FILE_PREFIX.* file in $_archive"
  : >"$_listing"
  for _file in "${_files[@]}"; do
    _test="$(basename "$_file")"
    _test="${_test#"$CALLGRIND_OUTPUT_FILE_PREFIX".}"
    listing_row_write "$_listing" "${_test%.*}" "$_file"
  done
  listing_row_write "$_listing" all "${_files[@]}"
}

listing_row_write() {
  local _listing="$1" _test="$2" _file
  shift 2
  {
    echo "$_test"
    for _file in "$@"; do echo "$_file"; done
    echo
  } >>"$_listing"
}

tests_names_of() {
  awk 'head { print; head = 0; next }
       /^$/ { head = 1 }
       BEGIN { head = 1 }' "$1" | sort -u
}

tests_pair() {
  local _base_tests _cur_tests _name
  _base_tests="$(tests_names_of "$_BASE_LISTING")"
  _cur_tests="$(tests_names_of "$_MODIFIED_LISTING")"
  local _one_sided="is in only one of the two reports, so it has no delta:"
  for _name in $(comm -3 <(echo "$_base_tests") <(echo "$_cur_tests")); do
    error_exit 2 "error: '$_name' $_one_sided $_BASE_DIR vs $_MOD_DIR"
  done
  comm -12 <(echo "$_base_tests") <(echo "$_cur_tests")
}

profiles_of() {
  awk -v want="$2" \
    'BEGIN { head = 1 }
     head { head = 0; taking = ($0 == want); next }
     /^$/ { head = 1; if(taking) { exit }; next }
     taking { print }' "$1"
}

diff_one() {
  local _test="$1" _out="$2" _name="$3"
  local _diff_file _callers_file _file
  local -a _base_files _cur_files _args
  _diff_file="$(artifact_path_of delta "$_name")"
  _callers_file="$(artifact_path_of caller-counts "$_name")"
  mapfile -t _base_files < <(profiles_of "$_BASE_LISTING" "$_test")
  mapfile -t _cur_files < <(profiles_of "$_MODIFIED_LISTING" "$_test")

  heading_print "python3 callgrind_diff.py $_name"
  _args=(python3 "$PERF2HTML_DIR_/scripts/callgrind_diff.py" -o "$_diff_file"
    --callers-output "$_callers_file")
  for _file in "${_base_files[@]}"; do _args+=(--baseline "$_file"); done
  for _file in "${_cur_files[@]}"; do _args+=(--current "$_file"); done
  command_run "${_args[@]}"

  heading_print "python3 callgrind_to_heatmap.py data $_name --diff"
  command_run python3 "$PERF2HTML_DIR_/scripts/callgrind_to_heatmap.py" data \
    "$_diff_file" --report-dir "$_OUT_DIR" --test "$_name" --diff \
    --baseline-data "$_callers_file"

  heading_print "python3 build_report.py test $_name"
  command_run python3 "$PERF2HTML_DIR_/scripts/build_report.py" test \
    "$_diff_file" -o "$_out/index.html" --test "$_name" --diff \
    --callers-data "$_callers_file"
  log_verbose "$(printf '%-13sdiff: %s' "$_name" "$_out/index.html")"
}

main() {
  args_parse "$@"
  verbose_begin
  title_print "$_SCRIPT" "$@"

  source_cache_sync

  local _base_recorded _mod_recorded
  _base_recorded="$(manifest_check "$_BASE_DIR" baseline)"
  _mod_recorded="$(manifest_check "$_MOD_DIR" modified)"
  timer_artifacts_find "$_BASE_DIR" baseline _BASELINE_TIMER_ARTIFACTS_ARCHIVE
  timer_artifacts_find "$_MOD_DIR" modified _MODIFIED_TIMER_ARTIFACTS_ARCHIVE

  path_overlap_check "$_OUT_DIR" "diff report" \
    "$_BASE_DIR" "baseline report" \
    "$_MOD_DIR" "modified report" \
    "$ARTIFACTS_DIR" "artifacts dir"

  if [ "$REGENERATE" = 1 ] && [ ! -d "$ARTIFACTS_DIR" ]; then
    error_exit 2 "error: --regenerate: no recordings at $ARTIFACTS_DIR"
  fi

  report_delete "$_OUT_DIR"
  [ "$REGENERATE" = 1 ] || artifacts_clean
  local _log_file
  _log_file="$(artifact_path_of diff-log "")"
  report_begin "$_OUT_DIR" "$_log_file" \
    "tests/perf2html/perf2html_diff.sh $TIMESTAMP: $_BASE_DIR: $_MOD_DIR: \
$_OUT_DIR"
  source_cache_fill

  local _tests _test_name _delta_file
  local -a _args
  _BASE_LISTING="$(artifact_path_of profile-listing baseline)"
  _MODIFIED_LISTING="$(artifact_path_of profile-listing modified)"
  profiles_extract "$_BASELINE_TIMER_ARTIFACTS_ARCHIVE" baseline \
    "$_BASE_LISTING"
  profiles_extract "$_MODIFIED_TIMER_ARTIFACTS_ARCHIVE" modified \
    "$_MODIFIED_LISTING"
  _tests="$(tests_pair)"
  log_verbose "$_SCRIPT $TIMESTAMP: $(basename "$_BASE_DIR"):" \
    "$(basename "$_MOD_DIR")"
  _args=(-o "$_OUT_DIR/index.html" --diff
    --header-block "baseline=$(header_file_of "$_BASE_DIR" baseline)"
    --header-block "modified=$(header_file_of "$_MOD_DIR" modified)")
  for _test_name in $_tests; do
    diff_one "$_test_name" "$_OUT_DIR/$_test_name" "$_test_name"
    _delta_file="$(artifact_path_of delta "$_test_name")"
    _args+=(--test "$_test_name" --diff-profile "$_test_name=$_delta_file")
  done
  heading_print "python3 callgrind_to_heatmap.py page"
  command_run python3 "$PERF2HTML_DIR_/scripts/callgrind_to_heatmap.py" page \
    --report-dir "$_OUT_DIR"
  heading_print "python3 build_report.py overview --diff"
  command_run python3 "$PERF2HTML_DIR_/scripts/build_report.py" overview \
    "${_args[@]}"
  log_verbose "$(printf '%-13s%s' overview "$_OUT_DIR/index.html")"

  report_finish "$_OUT_DIR" "$REPORT_MANIFEST_VERSION_DIFF" \
    "baseline=$(path_display "$_BASE_DIR")" \
    "modified=$(path_display "$_MOD_DIR")" \
    "baseline_recorded=$_base_recorded" \
    "modified_recorded=$_mod_recorded"
  if [ "$KEEP_ARTIFACTS" != 1 ]; then artifacts_clean; fi
  input_archives_clean
}

main "$@"
