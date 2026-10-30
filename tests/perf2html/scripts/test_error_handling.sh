#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.
#
# This comment intentionally blank. No documentation goes here.

usage_show() {
  cat <<'EOF'
test_error_handling.sh [--help]
    Runs test_expected_behavior.sh --regenerate --keep-artifacts --verbose
    into test_verbose.md from the recordings a measuring run kept, checks
    that a perf2html_batch.sh --regenerate run leaves them unchanged, runs
    the failure-mode testcases on copies of its reports, then prettier
    --check over that markdown. Shots differing from screenshots-gold/ are
    no failure: every test still runs, then a note and an exit with
    SCREENSHOT_GOLD_DIFFERENCE_EXIT_CODE from settings.sh.
    --help is the only argument.
EOF
}

set -euo pipefail

[ $# = 0 ] || { [[ $* =~ ^(-h|--help)$ ]] && usage_show && exit 0; } \
  || { echo "error: unknown option: $*" && usage_show && exit 2; } >&2

_SCRIPT="$(readlink -f -- "$0")"
_SCRIPT_DIR="$(dirname -- "$_SCRIPT")"
_DIR_PERF2HTML="$(cd -P -- "$_SCRIPT_DIR/.." && pwd)"
_REPO="$(cd -P -- "$_DIR_PERF2HTML/../.." && pwd)"
_TEST_EXPECTED_BEHAVIOR="$_SCRIPT_DIR/test_expected_behavior.sh"

. "$_SCRIPT_DIR/utility.sh"
. "$_SCRIPT_DIR/test_utility.sh"

_TEST_VERBOSE_DOCUMENT="$_DIR_PERF2HTML/test_verbose.md"

_TEST_ERROR_MARKDOWN_FORMATTER=prettier
_PRETTIER_CONFIG="$_SCRIPT_DIR/.prettierrc.json"
_TEST_ERROR_MARKDOWN_FORMATTER_INSTALL="npm install -g prettier"

_TEST_ERROR_BASELINE_REPORT="$_DIR_PERF2HTML/perf2html_baseline_report"
_TEST_ERROR_MODIFIED_REPORT="$_DIR_PERF2HTML/perf2html_modified_report"
_TEST_ERROR_DIFF_REPORT="$_DIR_PERF2HTML/perf2html_diff_report"

_TEST_ERROR_ARTIFACTS="$_DIR_PERF2HTML/perf2html_temporary_artifacts"

_TEST_ERROR_ARCHIVE_SUFFIX=.txz
_TEST_ERROR_HEAT_MAP_DIR_NAME=heat-map
_TEST_ERROR_HEAT_MAP_MODEL_DIR_NAME=data
_TEST_ERROR_HEAT_MAP_MODEL_FILE_SUFFIX=.js
_TEST_ERROR_PROFILE_FILE_SUFFIX=.callgrind.out
_TEST_ERROR_ROWS_FILE_NAME=perf2html.txt
_TEST_ERROR_SOURCES_DIR_NAME=sources
_TEST_ERROR_TEST_LIST_FILE_NAME=test_list.txt
_TEST_ERROR_TRUNCATED_BYTES=1024
_TEST_ERROR_TIMER_ARTIFACTS_PREFIX=timer-artifacts-
_TEST_ERROR_VALGRIND_LOG_FILE_SUFFIX=.valgrind.log
_TEST_ERROR_VALGRIND_LOG_PURPOSE='the valgrind log'

_TEST_ERROR_RECORDING_FILE_SUFFIXES=("$_TEST_ERROR_PROFILE_FILE_SUFFIX"
  .cyg_callback.bin .cyg_callback.bin.maps .cyg_callback.log .perf-stat.json
  .perf-stat.txt .trace_to_speedscope.json
  "$_TEST_ERROR_VALGRIND_LOG_FILE_SUFFIX")

_TEST_ERROR_MANIFEST_CHECKSUM_LABEL=checksum

_TEST_ERROR_MANIFEST_VERSION_DIFF='curl/perf2html_diff.sh v0'

_TEST_ERROR_SCRATCH="$_DIR_PERF2HTML/build/test_error_handling_scratch"

_TEST_ERROR_SCREENSHOT_DIFF_DIR="$_DIR_PERF2HTML/screenshots-diff"
_TEST_ERROR_SCREENSHOT_GOLD_DIFFERENCE_EXIT_CODE=3
_TEST_ERROR_SCREENSHOT_GOLD_DIR="$_DIR_PERF2HTML/screenshots-gold"

test_error_path_without_tool() {
  local _tool="$1" _bin="$_TEST_ERROR_SCRATCH/bin_without_$1" _dirs=() _dir
  mkdir "$_bin"
  IFS=: read -r -a _dirs <<<"$PATH"
  for _dir in "${_dirs[@]}"; do
    case "$_dir" in /*) ;; *) continue ;; esac
    [ -d "$_dir" ] || continue
    # Links each directory's own entries, never a subtree with its modes.
    find "$_dir" -mindepth 1 -maxdepth 1 -not -xtype d \
      -exec cp -s --update=none -t "$_bin" {} +
  done
  [ -e "$_bin/$_tool" ] \
    || test_fail test_error_path_without_tool "no $_tool on PATH"
  rm "$_bin/$_tool"
  echo "$_bin"
}

test_error_manifest_checksum_rewrite() {
  local _dir="$1" _manifest="$1/MANIFEST.txt" _checksum _row
  grep -q "^$_TEST_ERROR_MANIFEST_CHECKSUM_LABEL=" "$_manifest" \
    || test_fail test_error_manifest_checksum_rewrite \
      "no $_TEST_ERROR_MANIFEST_CHECKSUM_LABEL= row in $_manifest"
  _checksum="$(checksum_compute "$_dir")"
  _row="$_TEST_ERROR_MANIFEST_CHECKSUM_LABEL=$_checksum"
  sed -i "s/^$_TEST_ERROR_MANIFEST_CHECKSUM_LABEL=.*/$_row/" "$_manifest"
}

# Prints the unix time the recorded row of a manifest or rows file holds.
test_error_recorded_time() {
  local _recorded
  _recorded="$(sed -n 's/^recorded=//p' "$1" | head -n 1)"
  [ -n "$_recorded" ] || test_fail test_error_recorded_time \
    "no recorded= row in $(path_shown "$1")"
  echo "${_recorded%% *}"
}

test_error_timer_artifacts() {
  local _recorded _archive
  _recorded="$(test_error_recorded_time "$1/MANIFEST.txt")" || exit
  _archive="$1/$_TEST_ERROR_TIMER_ARTIFACTS_PREFIX$_recorded"
  _archive+="$_TEST_ERROR_ARCHIVE_SUFFIX"
  [ -f "$_archive" ] || test_fail test_error_timer_artifacts \
    "no raw data archive $(path_shown "$_archive") at the top of $1"
  echo "$_archive"
}

# Rebuilds a raw data archive without its first test or without its list.
test_error_archive_rebuild() {
  local _archive="$1" _extracted_directory="$2" _dropped="$3" _root_name
  local _root _test_list _first_test _profile
  _root_name="$(basename "$_archive" "$_TEST_ERROR_ARCHIVE_SUFFIX")"
  _root="$_extracted_directory/$_root_name"
  _test_list="$_root/$_TEST_ERROR_TEST_LIST_FILE_NAME"
  mkdir "$_extracted_directory"
  tar -xJf "$_archive" -C "$_extracted_directory"
  [ -s "$_test_list" ] || test_fail test_error_archive_rebuild \
    "no $_TEST_ERROR_TEST_LIST_FILE_NAME in $(path_shown "$_archive")"
  case "$_dropped" in
    first-test)
      IFS= read -r _first_test <"$_test_list" \
        || test_fail test_error_archive_rebuild \
          "no whole first line in $_TEST_ERROR_TEST_LIST_FILE_NAME"
      _profile="$_root/$_first_test$_TEST_ERROR_PROFILE_FILE_SUFFIX"
      [ -f "$_profile" ] || test_fail test_error_archive_rebuild \
        "no ${_profile##*/} in $(path_shown "$_archive")"
      rm "$_profile"
      sed -i 1d "$_test_list"
      ;;
    test-list) rm "$_test_list" ;;
    *) test_fail test_error_archive_rebuild "no such drop: $_dropped" ;;
  esac
  tar -cJf "$_archive" -C "$_extracted_directory" "$_root_name"
}

# Copies the kept report artifacts dir of the same base name to the path.
test_error_kept_copy() {
  local _kept="$_TEST_ERROR_ARTIFACTS/${1##*/}"
  [ -d "$_kept" ] || test_fail test_error_kept_copy \
    "no kept directory $(path_shown "$_kept")"
  mkdir "$(dirname "$1")"
  cp -a "$_kept" "$1"
}

test_error_relink_regenerate_run() {
  local _binary="$1" _reference="$2" _code=0
  touch -r "$_binary" "$_reference"
  touch "$_binary"
  "$_TEST_EXPECTED_BEHAVIOR" --regenerate || _code=$?
  touch -r "$_reference" "$_binary"
  return "$_code"
}

test_error_markdown_formatter_check() {
  _PRETTIER="$(tool_find "$_TEST_ERROR_MARKDOWN_FORMATTER")" && return 0
  {
    echo "error: 1 tool(s) missing, so" \
      "$(path_shown "$_TEST_VERBOSE_DOCUMENT") is not checked:" \
      "$_TEST_ERROR_MARKDOWN_FORMATTER"
    echo "  $_TEST_ERROR_MARKDOWN_FORMATTER_INSTALL"
  } >&2
  exit 127
}

test_error_markdown_check_run() {
  local _code=0
  "$_PRETTIER" --config "$_PRETTIER_CONFIG" \
    --log-level warn --check "$_TEST_VERBOSE_DOCUMENT" || _code=$?
  if [ "$_code" != 0 ]; then
    printf 'FAILED: %s --check exited %s on %s\n' \
      "$_TEST_ERROR_MARKDOWN_FORMATTER" "$_code" \
      "$(path_shown "$_TEST_VERBOSE_DOCUMENT")" >&2
    exit "$_code"
  fi
  echo "ok test_error_markdown_check"
}

# Regenerates every report from the recordings a measuring run kept.
test_error_expected_behavior_run() {
  local _code=0 _start=$SECONDS
  "$_TEST_EXPECTED_BEHAVIOR" --regenerate --keep-artifacts --verbose \
    2>"$_TEST_VERBOSE_DOCUMENT" </dev/null || _code=$?
  # A gold difference lets every other test run, noted again at the end.
  case "$_code" in
    0 | "$_TEST_ERROR_SCREENSHOT_GOLD_DIFFERENCE_EXIT_CODE") ;;
    *)
      printf 'FAILED: test_expected_behavior.sh exited %s, see %s\n' \
        "$_code" "$(path_shown "$_TEST_VERBOSE_DOCUMENT")" >&2
      exit "$_code"
      ;;
  esac
  printf 'test_expected_behavior.sh --regenerate --keep-artifacts: %ss\n' \
    "$((SECONDS - _start))"
}

test_error_makefile_test_names() {
  sed -n '/^TESTS_C *=/,/^$/p' "$_REPO/tests/perf/Makefile.inc" \
    | grep -o '[A-Za-z0-9_]*\.c' | sed 's/\.c$//' | LC_ALL=C sort || true
}

test_error_cache_populated_check() {
  local _tests=() _kept_tests=() _report _kept _rows _test_list _test _suffix
  mapfile -t _tests < <(test_error_makefile_test_names)
  [ "${#_tests[@]}" -gt 0 ] || test_fail cache_populated \
    "no TESTS_C entry in $_REPO/tests/perf/Makefile.inc"
  for _report in "$_TEST_ERROR_BASELINE_REPORT" \
    "$_TEST_ERROR_MODIFIED_REPORT"; do
    _kept="$_TEST_ERROR_ARTIFACTS/$(basename "$_report")"
    _rows="$_kept/$_TEST_ERROR_ROWS_FILE_NAME"
    [ -f "$_rows" ] || test_fail cache_populated "no rows file $_rows"
    test_error_recorded_time "$_rows" >/dev/null
    _test_list="$_kept/$_TEST_ERROR_TEST_LIST_FILE_NAME"
    [ -f "$_test_list" ] || test_fail cache_populated \
      "no test list $_test_list"
    mapfile -t _kept_tests <"$_test_list"
    [ "${_kept_tests[*]}" = "${_tests[*]}" ] || test_fail cache_populated \
      "$_test_list lists ${_kept_tests[*]}, expected TESTS_C ${_tests[*]}"
    for _test in "${_kept_tests[@]}"; do
      for _suffix in "${_TEST_ERROR_RECORDING_FILE_SUFFIXES[@]}"; do
        [ -f "$_kept/$_test$_suffix" ] || test_fail cache_populated \
          "no recording $_kept/$_test$_suffix"
      done
    done
  done
}

test_error_cache_snapshot() {
  (cd "$_TEST_ERROR_ARTIFACTS" && find . -type f -print | LC_ALL=C sort \
    | LC_ALL=C tr '\n' '\0' | xargs -0 -r cksum -- | LC_ALL=C sort)
}

# Refuses a kept file the regenerate runs since the snapshot changed.
test_error_regenerate_cache_check() {
  local _before="$1" _after _gone _new _line _path _name _suffix
  local _start=$SECONDS _code=0
  "$_DIR_PERF2HTML/perf2html_batch.sh" --regenerate \
    "--target-dir=$_DIR_PERF2HTML" </dev/null || _code=$?
  [ "$_code" = 0 ] || test_fail regenerate_from_cache \
    "perf2html_batch.sh --regenerate exited $_code"
  printf 'perf2html_batch.sh --regenerate: %ss\n' "$((SECONDS - _start))"
  _after="$(test_error_cache_snapshot)"
  _gone="$(comm -23 <(printf '%s\n' "$_before") <(printf '%s\n' "$_after"))"
  [ -z "$_gone" ] || test_fail regenerate_cache_unchanged \
    "$(grep -c . <<<"$_gone") kept file(s) changed: ${_gone%%$'\n'*}"
  _new="$(comm -13 <(printf '%s\n' "$_before") <(printf '%s\n' "$_after"))"
  while IFS= read -r _line; do
    [ -n "$_line" ] || continue
    _path="${_line##* }"
    for _name in "$(basename "$_TEST_ERROR_BASELINE_REPORT")" \
      "$(basename "$_TEST_ERROR_MODIFIED_REPORT")"; do
      for _suffix in "${_TEST_ERROR_RECORDING_FILE_SUFFIXES[@]}"; do
        case "$_path" in
          "./$_name/"*"$_suffix")
            test_fail regenerate_no_new_recordings \
              "--regenerate recorded a new file: $_path"
            ;;
        esac
      done
    done
  done <<<"$_new"
  echo "ok regenerate_cache_unchanged"
}

test_error_unknown_option_tests() {
  test_failure_expect test_expected_behavior_unknown_option 2 -- \
    "$_TEST_EXPECTED_BEHAVIOR" --bogus-option
  test_failure_expect test_error_handling_unknown_option 2 -- \
    "$_SCRIPT" --bogus-option

  grep -q 'unknown option' "$_DIR_PERF2HTML/clean.sh" \
    || test_fail clean_unknown_option \
      "clean.sh holds no 'unknown option'"
  test_failure_expect clean_unknown_option 2 -- \
    "$_DIR_PERF2HTML/clean.sh" --bogus-option

  test_failure_expect diff_unknown_option 2 -- \
    "$_DIR_PERF2HTML/perf2html_diff.sh" \
    "--artifacts=$_TEST_ERROR_SCRATCH/artifacts_unknown" --bogus-option
}

test_error_diff_uncached_test() {
  local _baseline="$1" _modified="$2" _manifest_fault _raw_data _report
  local _archive _diff_report="$_TEST_ERROR_SCRATCH/out_uncached"
  local _checksum_label="$_TEST_ERROR_MANIFEST_CHECKSUM_LABEL"
  test_failure_expect diff_uncached 0 -- \
    "$_DIR_PERF2HTML/perf2html_diff.sh" \
    "--artifacts=$_TEST_ERROR_SCRATCH/artifacts_uncached" \
    "$_baseline" "$_modified" "$_diff_report"
  _manifest_fault="$(REPORT_MANIFEST_CHECKSUM_LABEL="$_checksum_label" \
    manifest_fault "$_diff_report" "$_TEST_ERROR_MANIFEST_VERSION_DIFF")"
  [ -z "$_manifest_fault" ] \
    || test_fail diff_uncached_manifest "$_manifest_fault"
  echo "ok diff_uncached_manifest"
  for _report in "$_baseline" "$_modified"; do
    _archive="$(test_error_timer_artifacts "$_report")"
    _raw_data="$_diff_report/${_archive##*/}"
    [ ! -e "$_raw_data" ] || test_fail diff_uncached_no_raw_data \
      "a diff report holds raw data: $(path_shown "$_raw_data")"
  done
  [ ! -e "$_diff_report/raw" ] || test_fail diff_uncached_no_raw_data \
    "a diff report holds raw data: $(path_shown "$_diff_report/raw")"
  echo "ok diff_uncached_no_raw_data"
}

test_error_diff_remote_test() {
  local _baseline="$1" _modified="$2" _report _part _archives=()
  local _remote="$_TEST_ERROR_SCRATCH/remote"
  local _tool_dir="$_remote/tests/perf2html"
  mkdir -p "$_tool_dir" "$_remote/home"
  cp -a "$_DIR_PERF2HTML/perf2html_diff.sh" "$_DIR_PERF2HTML/README.md" \
    "$_SCRIPT_DIR" "$_tool_dir/"
  for _report in "$_baseline" "$_modified"; do
    _archives+=("$_remote/$(basename "$_report")$_TEST_ERROR_ARCHIVE_SUFFIX")
    tar -cJf "${_archives[-1]}" -C "$(dirname "$_report")" \
      "$(basename "$_report")"
  done
  test_failure_expect diff_remote 0 -- \
    env HOME="$_remote/home" GIT_CEILING_DIRECTORIES="$_remote" \
    "$_tool_dir/perf2html_diff.sh" "--artifacts=$_remote/artifacts" \
    "${_archives[@]}" "$_remote/out"
  for _part in "$_TEST_ERROR_HEAT_MAP_DIR_NAME" \
    "$_TEST_ERROR_SOURCES_DIR_NAME"; do
    diff -r "$_TEST_ERROR_SCRATCH/out_uncached/$_part" "$_remote/out/$_part" \
      || test_fail diff_remote_same "a diff made outside the repository \
writes another $_part/ than one made inside it"
  done
  echo "ok diff_remote_same"
}

test_error_diff_tests() {
  local _baseline="$1" _modified="$2" _diff="$3" _copy _archive _kept
  local _test_list _first_test _model_path _model_text _source
  local _source_pattern='"source":"([^"]+)"'
  local _tool="$_DIR_PERF2HTML/perf2html_diff.sh"
  local _scratch="$_TEST_ERROR_SCRATCH"

  test_failure_expect diff_of_a_diff 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_diff_of_a_diff" \
    "$_diff" "$_modified" "$_scratch/out_diff_of_a_diff"

  test_failure_expect diff_missing_directory 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_missing" \
    "$_baseline" "$_scratch/never_made" \
    "$_scratch/out_missing"

  test_failure_expect diff_four_directories 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_four" \
    "$_baseline" "$_modified" "$_scratch/out_four" \
    "$_scratch/fourth"

  mkdir "$_scratch/artifacts_diff_no_recordings"
  test_failure_expect diff_regenerate_no_recordings 2 -- "$_tool" \
    --regenerate "--artifacts=$_scratch/artifacts_diff_no_recordings" \
    "$_baseline" "$_modified" "$_scratch/out_diff_no_recordings"

  _kept="$_scratch/artifacts_diff_tests_changed"
  _kept+="/$(basename "$_TEST_ERROR_DIFF_REPORT")"
  test_error_kept_copy "$_kept"
  sed -i 1d "$_kept/$_TEST_ERROR_TEST_LIST_FILE_NAME"
  test_failure_expect diff_regenerate_tests_changed 2 -- "$_tool" \
    --regenerate "--artifacts=$_scratch/artifacts_diff_tests_changed" \
    "$_baseline" "$_modified" "$_scratch/diff_tests_changed/${_kept##*/}"

  _copy="$(test_report_copy "$_scratch/modified_as_output" \
    "$_modified")"
  test_failure_expect diff_output_is_an_input 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_output_input" \
    "$_baseline" "$_copy" "$_copy"

  _copy="$(test_report_copy "$_scratch/modified_no_manifest" \
    "$_modified")"
  rm "$_copy/MANIFEST.txt"
  test_failure_expect diff_no_manifest 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_no_manifest" \
    "$_baseline" "$_copy" "$_scratch/out_no_manifest"

  _copy="$(test_report_copy "$_scratch/modified_bad_version" \
    "$_modified")"
  sed -i '1s/.*/edited by test_error_handling.sh/' "$_copy/MANIFEST.txt"
  test_failure_expect diff_unrecognized_manifest 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_bad_version" \
    "$_baseline" "$_copy" "$_scratch/out_bad_version"

  _copy="$(test_report_copy "$_scratch/baseline_extra_file" \
    "$_baseline")"
  echo 'added by test_error_handling.sh' >"$_copy/extra_file.txt"
  test_failure_expect diff_checksum_added_file 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_added_file" \
    "$_copy" "$_modified" "$_scratch/out_added_file"

  _copy="$(test_report_copy "$_scratch/modified_edited_page" \
    "$_modified")"
  echo >>"$_copy/index.html"
  test_failure_expect diff_checksum_edited_page 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_edited_page" \
    "$_baseline" "$_copy" "$_scratch/out_edited_page"

  _copy="$(test_report_copy "$_scratch/modified_other_source" \
    "$_modified")"
  _test_list="$_TEST_ERROR_ARTIFACTS/${_modified##*/}"
  _test_list+="/$_TEST_ERROR_TEST_LIST_FILE_NAME"
  IFS= read -r _first_test <"$_test_list" || test_fail diff_sources_mismatch \
    "no whole first line in $(path_shown "$_test_list")"
  _model_path="$_copy/$_TEST_ERROR_HEAT_MAP_DIR_NAME"
  _model_path+="/$_TEST_ERROR_HEAT_MAP_MODEL_DIR_NAME/$_first_test"
  _model_path+="$_TEST_ERROR_HEAT_MAP_MODEL_FILE_SUFFIX"
  [ -f "$_model_path" ] || test_fail diff_sources_mismatch \
    "no $(path_shown "$_model_path")"
  _model_text="$(<"$_model_path")"
  [[ "$_model_text" =~ $_source_pattern ]] \
    || test_fail diff_sources_mismatch \
      "no file with a source in $(path_shown "$_model_path")"
  _source="$_copy/$_TEST_ERROR_SOURCES_DIR_NAME/${BASH_REMATCH[1]}"
  [ -f "$_source" ] || test_fail diff_sources_mismatch \
    "no source $(path_shown "$_source")"
  echo '// edited by test_error_handling.sh' >>"$_source"
  test_error_manifest_checksum_rewrite "$_copy"
  test_failure_expect diff_sources_mismatch 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_other_source" \
    "$_baseline" "$_copy" "$_scratch/out_other_source"

  _copy="$(test_report_copy "$_scratch/modified_one_sided" \
    "$_modified")"
  _archive="$(test_error_timer_artifacts "$_copy")"
  test_error_archive_rebuild "$_archive" "$_scratch/one_sided_unpacked" \
    first-test
  test_error_manifest_checksum_rewrite "$_copy"
  test_failure_expect diff_one_sided_test 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_one_sided" \
    "$_baseline" "$_copy" "$_scratch/out_one_sided"

  _copy="$(test_report_copy "$_scratch/modified_no_test_list" \
    "$_modified")"
  _archive="$(test_error_timer_artifacts "$_copy")"
  test_error_archive_rebuild "$_archive" "$_scratch/no_test_list_unpacked" \
    test-list
  test_error_manifest_checksum_rewrite "$_copy"
  test_failure_expect diff_archive_no_test_list 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_no_test_list" \
    "$_baseline" "$_copy" "$_scratch/out_no_test_list"

  _copy="$(test_report_copy "$_scratch/modified_no_timer_artifacts" \
    "$_modified")"
  _archive="$(test_error_timer_artifacts "$_copy")"
  rm "$_archive"
  test_error_manifest_checksum_rewrite "$_copy"
  test_failure_expect diff_no_timer_artifacts 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_no_timer_artifacts" \
    "$_baseline" "$_copy" "$_scratch/out_no_timer_artifacts"
}

test_error_txz_tests() {
  local _baseline="$1" _wrong _kept _whole _truncated
  local _tool="$_DIR_PERF2HTML/perf2html_diff.sh"
  local _scratch="$_TEST_ERROR_SCRATCH"

  test_failure_expect txz_input_missing 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_txz_missing" \
    "$_baseline" "$_scratch/never_made$_TEST_ERROR_ARCHIVE_SUFFIX" \
    "$_scratch/out_txz_missing"

  echo 'not a tar, written by test_error_handling.sh' \
    >"$_scratch/not_a_tar$_TEST_ERROR_ARCHIVE_SUFFIX"
  test_failure_expect txz_input_not_a_tar 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_txz_not_a_tar" \
    "$_baseline" "$_scratch/not_a_tar$_TEST_ERROR_ARCHIVE_SUFFIX" \
    "$_scratch/out_txz_not_a_tar"

  : >"$_scratch/empty$_TEST_ERROR_ARCHIVE_SUFFIX"
  test_failure_expect txz_input_empty 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_txz_empty" \
    "$_baseline" "$_scratch/empty$_TEST_ERROR_ARCHIVE_SUFFIX" \
    "$_scratch/out_txz_empty"

  _whole="$_scratch/whole$_TEST_ERROR_ARCHIVE_SUFFIX"
  tar -cJf "$_whole" -C "$(dirname "$_baseline")" "$(basename "$_baseline")"
  _truncated="$_scratch/truncated$_TEST_ERROR_ARCHIVE_SUFFIX"
  head -c "$_TEST_ERROR_TRUNCATED_BYTES" "$_whole" >"$_truncated"
  test_failure_expect txz_input_truncated 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_txz_truncated" \
    "$_baseline" "$_truncated" "$_scratch/out_txz_truncated"

  mkdir "$_scratch/a_directory$_TEST_ERROR_ARCHIVE_SUFFIX"
  test_failure_expect txz_input_is_a_directory 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_txz_directory" \
    "$_baseline" "$_scratch/a_directory$_TEST_ERROR_ARCHIVE_SUFFIX" \
    "$_scratch/out_txz_directory"

  mkdir -p "$_scratch/other_name"
  echo 'packed by test_error_handling.sh' >"$_scratch/other_name/a_file.txt"
  _wrong="$_scratch/wrong_name$_TEST_ERROR_ARCHIVE_SUFFIX"
  tar -cJf "$_wrong" -C "$_scratch" other_name
  test_failure_expect txz_input_wrong_report_name 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_txz_wrong_name" \
    "$_baseline" "$_wrong" "$_scratch/out_txz_wrong_name"

  _kept="$_scratch/out_txz_kept"
  echo 'the previous archive' >"$_kept$_TEST_ERROR_ARCHIVE_SUFFIX"
  test_failure_expect txz_output_refused 2 -- \
    "$_tool" --txz "--artifacts=$_scratch/artifacts_txz_kept" \
    "$_baseline" "$_scratch/never_made" "$_kept"
  grep -q 'the previous archive' "$_kept$_TEST_ERROR_ARCHIVE_SUFFIX" \
    || test_fail txz_previous_archive_kept \
      "$(path_shown "$_kept$_TEST_ERROR_ARCHIVE_SUFFIX") is gone or \
overwritten after a refused run"
  echo "ok txz_previous_archive_kept"
}

test_error_batch_tests() {
  test_failure_expect batch_regenerate_no_recordings 2 -- \
    "$_DIR_PERF2HTML/perf2html_batch.sh" --regenerate "--target-dir=$1" \
    "--artifacts=$_TEST_ERROR_SCRATCH/artifacts_batch_none"
}

test_error_toolchain_tests() {
  local _bin
  _bin="$(test_error_path_without_tool valgrind)"
  test_failure_expect toolchain_missing_tool 127 -- \
    env PATH="$_bin" "$_DIR_PERF2HTML/perf2html.sh" \
    "--report=$_TEST_ERROR_SCRATCH/report_no_valgrind" \
    "--artifacts=$_TEST_ERROR_SCRATCH/artifacts_no_valgrind"
}

test_error_report_dir_tests() {
  local _baseline="$1" _tool="$_DIR_PERF2HTML/perf2html.sh" _populated _file
  local _scratch="$_TEST_ERROR_SCRATCH" _empty _kept _first_test _missing
  local _line

  _populated="$_scratch/populated_no_manifest"
  mkdir "$_populated"
  echo 'left by test_error_handling.sh' >"$_populated/leftover.txt"
  test_failure_expect report_populated_no_manifest 1 -- \
    "$_tool" "--report=$_populated" \
    "--artifacts=$_scratch/artifacts_populated"
  [ -f "$_populated/leftover.txt" ] \
    || test_fail report_populated_kept \
      "$(path_shown "$_populated/leftover.txt") is gone after a refused run"
  echo "ok report_populated_kept"

  _file="$_scratch/report_is_a_file.txt"
  echo 'a file, not a directory' >"$_file"
  test_failure_expect report_is_a_file 1 -- \
    "$_tool" "--report=$_file" "--artifacts=$_scratch/artifacts_file"
  [ -f "$_file" ] || test_fail report_file_kept \
    "$(path_shown "$_file") is gone after a refused prompt"
  echo "ok report_file_kept"

  test_failure_expect artifacts_inside_report 2 -- \
    "$_tool" "--report=$_baseline" "--artifacts=$_baseline/inside"

  _empty="$_scratch/artifacts_empty"
  mkdir "$_empty"
  test_failure_expect regenerate_missing_recordings 2 -- \
    "$_tool" --regenerate "--report=$_baseline" "--artifacts=$_empty"

  _kept="$_scratch/artifacts_tests_changed/${_baseline##*/}"
  test_error_kept_copy "$_kept"
  sed -i 1d "$_kept/$_TEST_ERROR_TEST_LIST_FILE_NAME"
  test_failure_expect regenerate_tests_changed 2 -- \
    "$_tool" --regenerate "--report=$_baseline" "--artifacts=${_kept%/*}"

  _kept="$_scratch/artifacts_missing_recording/${_baseline##*/}"
  test_error_kept_copy "$_kept"
  IFS= read -r _first_test <"$_kept/$_TEST_ERROR_TEST_LIST_FILE_NAME" \
    || test_fail regenerate_missing_recording \
      "no whole first line in $_kept/$_TEST_ERROR_TEST_LIST_FILE_NAME"
  _missing="$_first_test$_TEST_ERROR_VALGRIND_LOG_FILE_SUFFIX"
  rm "$_kept/$_missing"
  _line="error: $_kept is missing $_missing,"
  _line+=" $_TEST_ERROR_VALGRIND_LOG_PURPOSE of $_first_test"
  test_failure_message_expect regenerate_missing_recording 2 "$_line" -- \
    "$_tool" --regenerate "--report=$_baseline" "--artifacts=${_kept%/*}"
}

test_error_expected_behavior_tests() {
  local _bin
  _bin="$(test_error_path_without_tool shfmt)"
  mkdir "$_TEST_ERROR_SCRATCH/home"
  test_failure_expect test_expected_behavior_missing_tool 127 -- \
    env PATH="$_bin" HOME="$_TEST_ERROR_SCRATCH/home" \
    "$_TEST_EXPECTED_BEHAVIOR" --regenerate
  test_error_relink_test
}

test_error_relink_test() {
  local _row _rows _binary
  local _reference="$_TEST_ERROR_SCRATCH/mtime_reference"
  _rows="$_TEST_ERROR_ARTIFACTS/$(basename "$_TEST_ERROR_BASELINE_REPORT")"
  _rows="$_rows/$_TEST_ERROR_ROWS_FILE_NAME"
  [ -f "$_rows" ] || test_fail regenerate_after_relink "no $_rows"
  _row="$(sed -n 's/^executable=//p' "$_rows" | head -n 1)"
  [ -n "$_row" ] || test_fail regenerate_after_relink \
    "no executable= row in $_rows"
  _binary="$_REPO/${_row%% *}"
  [ -f "$_binary" ] || test_fail regenerate_after_relink \
    "no executable at $_binary"
  test_failure_expect regenerate_after_relink 2 -- \
    test_error_relink_regenerate_run "$_binary" "$_reference"
}

test_error_failure_tests_run() {
  local _target _baseline _modified _diff
  rm -rf "$_TEST_ERROR_SCRATCH"
  mkdir -p "$_TEST_ERROR_SCRATCH"
  test_error_unknown_option_tests

  _target="$_TEST_ERROR_SCRATCH/target"
  mkdir "$_target"
  _baseline="$(test_report_copy \
    "$_target/$(basename "$_TEST_ERROR_BASELINE_REPORT")" \
    "$_TEST_ERROR_BASELINE_REPORT")"
  _modified="$(test_report_copy \
    "$_target/$(basename "$_TEST_ERROR_MODIFIED_REPORT")" \
    "$_TEST_ERROR_MODIFIED_REPORT")"
  _diff="$(test_report_copy \
    "$_target/$(basename "$_TEST_ERROR_DIFF_REPORT")" \
    "$_TEST_ERROR_DIFF_REPORT")"

  test_error_diff_uncached_test "$_baseline" "$_modified"
  test_error_diff_remote_test "$_baseline" "$_modified"
  test_error_diff_tests "$_baseline" "$_modified" "$_diff"
  test_error_txz_tests "$_baseline"
  test_error_batch_tests "$_target"
  test_error_report_dir_tests "$_baseline"
  test_error_toolchain_tests
  test_error_expected_behavior_tests
  rm -rf "$_TEST_ERROR_SCRATCH"
}

main() {
  local _cache_before
  test_error_markdown_formatter_check
  test_error_cache_populated_check
  _cache_before="$(test_error_cache_snapshot)"
  test_error_expected_behavior_run
  test_error_regenerate_cache_check "$_cache_before"
  test_error_failure_tests_run
  test_error_markdown_check_run
  printf 'test_error_handling.sh: %ss total\n' "$SECONDS"
  if [ -d "$_TEST_ERROR_SCREENSHOT_DIFF_DIR" ]; then
    screenshot_gold_notice "$_TEST_ERROR_SCREENSHOT_GOLD_DIR" \
      "$_TEST_ERROR_SCREENSHOT_DIFF_DIR"
    exit "$_TEST_ERROR_SCREENSHOT_GOLD_DIFFERENCE_EXIT_CODE"
  fi
}

main
