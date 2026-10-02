#!/usr/bin/env bash

# This comment intentionally blank. No documentation goes here.

usage_show() {
  cat <<'EOF'
test_error_handling.sh [--help]
    Runs test_expected_behavior.sh --keep-artifacts --verbose into
    test_expected_behavior.md, checks a --regenerate run from the
    recordings kept, runs the failure-mode testcases on copies of its
    reports, then prettier --check over that markdown.
    --help is the only argument.
EOF
}

set -euo pipefail

[ $# = 0 ] || { [[ $* =~ ^(-h|--help)$ ]] && usage_show && exit 0; } \
  || { echo "error: unknown option: $*" && usage_show && exit 2; } >&2

_SCRIPT="$(readlink -f "$0")"
_SCRIPTS="$(dirname "$_SCRIPT")"
_DEV="$(dirname "$_SCRIPTS")"
_REPO="$(dirname "$_DEV")"
_TEST_EXPECTED_BEHAVIOR="$_SCRIPTS/test_expected_behavior.sh"

. "$_SCRIPTS/utility.sh"
. "$_SCRIPTS/test_utility.sh"

_TEST_EXPECTED_BEHAVIOR_DOCUMENT="$_DEV/test_expected_behavior.md"

_TEST_ERROR_MARKDOWN_FORMATTER=prettier
_PRETTIER_CONFIG="$_SCRIPTS/.prettierrc.json"
_TEST_ERROR_MARKDOWN_FORMATTER_INSTALL="npm install -g prettier"

_TEST_ERROR_BASELINE_REPORT="$_DEV/perf2html_baseline_report"
_TEST_ERROR_MODIFIED_REPORT="$_DEV/perf2html_modified_report"
_TEST_ERROR_DIFF_REPORT="$_DEV/perf2html_diff_report"

_TEST_ERROR_ARTIFACTS="$_DEV/perf2html_temporary_artifacts"

_TEST_ERROR_ARCHIVE_SUFFIX=.txz
_TEST_ERROR_CALLGRIND_LOOPS=200
_TEST_ERROR_TRUNCATED_BYTES=1024
_TEST_ERROR_TIMER_ARTIFACTS_PREFIX=timer-artifacts-
_TEST_ERROR_TIMING_FILE_PREFIX=perf-stat

_TEST_ERROR_MANIFEST_CHECKSUM_LABEL=checksum

_TEST_ERROR_MANIFEST_VERSION_DIFF='curl/perf2html_diff.sh v1'

_TEST_ERROR_SCRATCH="$_DEV/build/test_error_handling_scratch"

test_error_path_without_tool() {
  local _tool="$1" _bin="$_TEST_ERROR_SCRATCH/bin_without_$1" _dirs=() _dir
  mkdir "$_bin"
  IFS=: read -r -a _dirs <<<"$PATH"
  for _dir in "${_dirs[@]}"; do
    case "$_dir" in /*) ;; *) continue ;; esac
    [ -d "$_dir" ] || continue
    cp -rs --update=none "$_dir"/. "$_bin"/
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

test_error_timer_artifacts_of() {
  local _found_archives=()
  local _archive_pattern="$_TEST_ERROR_TIMER_ARTIFACTS_PREFIX*"
  _archive_pattern+="$_TEST_ERROR_ARCHIVE_SUFFIX"
  mapfile -t _found_archives < <(find "$1" -mindepth 1 -maxdepth 1 -type f \
    -name "$_archive_pattern" | LC_ALL=C sort)
  [ "${#_found_archives[@]}" = 1 ] || test_fail test_error_timer_artifacts_of \
    "${#_found_archives[@]} $_archive_pattern at the top of $1, expected 1"
  echo "${_found_archives[0]}"
}

test_error_first_profile_drop() {
  local _archive="$1" _extracted_directory="$2" _root_name _first_profile
  _root_name="$(basename "$_archive" "$_TEST_ERROR_ARCHIVE_SUFFIX")"
  mkdir "$_extracted_directory"
  tar -xJf "$_archive" -C "$_extracted_directory"
  _first_profile="$(find "$_extracted_directory/$_root_name" -maxdepth 1 \
    -type f -name 'callgrind.out.*' | LC_ALL=C sort | head -n 1)"
  [ -n "$_first_profile" ] || test_fail test_error_first_profile_drop \
    "no callgrind.out.* in $(path_shown "$_archive")"
  rm "$_first_profile"
  tar -cJf "$_archive" -C "$_extracted_directory" "$_root_name"
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
      "$(path_shown "$_TEST_EXPECTED_BEHAVIOR_DOCUMENT") is not checked:" \
      "$_TEST_ERROR_MARKDOWN_FORMATTER"
    echo "  $_TEST_ERROR_MARKDOWN_FORMATTER_INSTALL"
  } >&2
  exit 1
}

test_error_markdown_check_run() {
  local _code=0
  "$_PRETTIER" --config "$_PRETTIER_CONFIG" \
    --log-level warn --check "$_TEST_EXPECTED_BEHAVIOR_DOCUMENT" || _code=$?
  if [ "$_code" != 0 ]; then
    printf 'FAILED: %s --check exited %s on %s\n' \
      "$_TEST_ERROR_MARKDOWN_FORMATTER" "$_code" \
      "$(path_shown "$_TEST_EXPECTED_BEHAVIOR_DOCUMENT")" >&2
    exit "$_code"
  fi
  echo "ok test_error_markdown_check"
}

test_error_expected_behavior_run() {
  local _code=0 _start=$SECONDS
  "$_TEST_EXPECTED_BEHAVIOR" --keep-artifacts --verbose \
    2>"$_TEST_EXPECTED_BEHAVIOR_DOCUMENT" </dev/null || _code=$?
  if [ "$_code" != 0 ]; then
    printf 'FAILED: test_expected_behavior.sh exited %s, see %s\n' "$_code" \
      "$(path_shown "$_TEST_EXPECTED_BEHAVIOR_DOCUMENT")" >&2
    exit "$_code"
  fi
  printf 'test_expected_behavior.sh --keep-artifacts: %ss\n' \
    "$((SECONDS - _start))"
}

test_error_makefile_test_names() {
  sed -n '/^TESTS_C *=/,/^$/p' "$_REPO/tests/perf/Makefile.inc" \
    | grep -o '[A-Za-z0-9_]*\.c' | sed 's/\.c$//' | sort || true
}

test_error_cache_populated_check() {
  local _tests=() _report _name _rows _recorded _test _file
  local _loops="$_TEST_ERROR_CALLGRIND_LOOPS"
  local _prefix="$_TEST_ERROR_TIMING_FILE_PREFIX"
  mapfile -t _tests < <(test_error_makefile_test_names)
  [ "${#_tests[@]}" -gt 0 ] || test_fail cache_populated \
    "no TESTS_C entry in $_REPO/tests/perf/Makefile.inc"
  for _report in "$_TEST_ERROR_BASELINE_REPORT" \
    "$_TEST_ERROR_MODIFIED_REPORT"; do
    _name="$(basename "$_report")"
    _rows="$_TEST_ERROR_ARTIFACTS/$_name/header.overview.$_name.txt"
    [ -f "$_rows" ] || test_fail cache_populated "no rows file $_rows"
    _recorded="$(sed -n 's/^recorded=//p' "$_rows" | head -n 1)"
    _recorded="${_recorded%% *}"
    [ -n "$_recorded" ] \
      || test_fail cache_populated "no recorded= row in $_rows"
    for _test in "${_tests[@]}"; do
      for _file in \
        "callgrind.out.$_test.$_loops.$_recorded" \
        "valgrind.$_test.$_loops.$_recorded.log" \
        "$_prefix.$_test.$_recorded.csv" \
        "$_prefix.$_test.$_recorded.txt" \
        "trace.$_test.$_loops.$_recorded.log" \
        "trace.$_test.$_loops.$_recorded.speedscope.json"; do
        [ -f "$_TEST_ERROR_ARTIFACTS/$_name/$_file" ] \
          || test_fail cache_populated \
            "no recording $_TEST_ERROR_ARTIFACTS/$_name/$_file"
      done
    done
  done
}

test_error_cache_snapshot_of() {
  (cd "$_TEST_ERROR_ARTIFACTS" && find . -type f -print | LC_ALL=C sort \
    | LC_ALL=C tr '\n' '\0' | xargs -0 -r cksum -- | LC_ALL=C sort)
}

test_error_regenerate_cache_check() {
  local _before _after _gone _new _line _path _name _start=$SECONDS _code=0
  _before="$(test_error_cache_snapshot_of)"
  "$_DEV/perf2html_batch.sh" --regenerate "--target-dir=$_DEV" </dev/null \
    || _code=$?
  [ "$_code" = 0 ] || test_fail regenerate_from_cache \
    "perf2html_batch.sh --regenerate exited $_code"
  printf 'perf2html_batch.sh --regenerate: %ss\n' "$((SECONDS - _start))"
  _after="$(test_error_cache_snapshot_of)"
  _gone="$(comm -23 <(printf '%s\n' "$_before") <(printf '%s\n' "$_after"))"
  [ -z "$_gone" ] || test_fail regenerate_cache_unchanged \
    "$(grep -c . <<<"$_gone") kept file(s) changed: ${_gone%%$'\n'*}"
  _new="$(comm -13 <(printf '%s\n' "$_before") <(printf '%s\n' "$_after"))"
  while IFS= read -r _line; do
    [ -n "$_line" ] || continue
    _path="${_line##* }"
    for _name in "$(basename "$_TEST_ERROR_BASELINE_REPORT")" \
      "$(basename "$_TEST_ERROR_MODIFIED_REPORT")"; do
      case "$_path" in
        "./$_name/callgrind.out."* | "./$_name/valgrind."* | \
          "./$_name/trace."* | \
          "./$_name/$_TEST_ERROR_TIMING_FILE_PREFIX".*)
          test_fail regenerate_no_new_recordings \
            "--regenerate recorded a new file: $_path"
          ;;
      esac
    done
  done <<<"$_new"
  echo "ok regenerate_cache_unchanged"
}

test_error_unknown_option_tests() {
  test_failure_expect test_expected_behavior_unknown_option 2 -- \
    "$_TEST_EXPECTED_BEHAVIOR" --bogus-option
  test_failure_expect test_error_handling_unknown_option 2 -- \
    "$_SCRIPT" --bogus-option

  grep -q 'unknown option' "$_DEV/clean.sh" \
    || test_fail clean_unknown_option \
      "clean.sh holds no 'unknown option'"
  test_failure_expect clean_unknown_option 2 -- \
    "$_DEV/clean.sh" --bogus-option

  test_failure_expect diff_unknown_option 2 -- \
    "$_DEV/perf2html_diff.sh" \
    "--artifacts=$_TEST_ERROR_SCRATCH/artifacts_unknown" --bogus-option
}

test_error_diff_uncached_test() {
  local _baseline="$1" _modified="$2" _manifest_fault _raw_data
  local _diff_report="$_TEST_ERROR_SCRATCH/out_uncached"
  local _checksum_label="$_TEST_ERROR_MANIFEST_CHECKSUM_LABEL"
  test_failure_expect diff_uncached 0 -- \
    "$_DEV/perf2html_diff.sh" \
    "--artifacts=$_TEST_ERROR_SCRATCH/artifacts_uncached" \
    "$_baseline" "$_modified" "$_diff_report"
  _manifest_fault="$(REPORT_MANIFEST_CHECKSUM_LABEL="$_checksum_label" \
    manifest_fault_of "$_diff_report" "$_TEST_ERROR_MANIFEST_VERSION_DIFF")"
  [ -z "$_manifest_fault" ] \
    || test_fail diff_uncached_manifest "$_manifest_fault"
  echo "ok diff_uncached_manifest"
  _raw_data="$(find "$_diff_report" \( -name raw \
    -o -name "*$_TEST_ERROR_ARCHIVE_SUFFIX" \) -print -quit)"
  [ -z "$_raw_data" ] || test_fail diff_uncached_no_raw_data \
    "a diff report holds raw data: $(path_shown "$_raw_data")"
  echo "ok diff_uncached_no_raw_data"
}

test_error_diff_tests() {
  local _baseline="$1" _modified="$2" _diff="$3" _copy _archive
  local _second_archive
  local _tool="$_DEV/perf2html_diff.sh"
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

  _copy="$(test_report_copy "$_scratch/modified_one_sided" \
    "$_modified")"
  _archive="$(test_error_timer_artifacts_of "$_copy")"
  test_error_first_profile_drop "$_archive" "$_scratch/one_sided_unpacked"
  test_error_manifest_checksum_rewrite "$_copy"
  test_failure_expect diff_one_sided_test 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_one_sided" \
    "$_baseline" "$_copy" "$_scratch/out_one_sided"

  _copy="$(test_report_copy "$_scratch/modified_no_timer_artifacts" \
    "$_modified")"
  _archive="$(test_error_timer_artifacts_of "$_copy")"
  rm "$_archive"
  test_error_manifest_checksum_rewrite "$_copy"
  test_failure_expect diff_no_timer_artifacts 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_no_timer_artifacts" \
    "$_baseline" "$_copy" "$_scratch/out_no_timer_artifacts"

  _copy="$(test_report_copy "$_scratch/modified_two_timer_artifacts" \
    "$_modified")"
  _archive="$(test_error_timer_artifacts_of "$_copy")"
  _second_archive="${_archive%"$_TEST_ERROR_ARCHIVE_SUFFIX"}.second"
  cp "$_archive" "$_second_archive$_TEST_ERROR_ARCHIVE_SUFFIX"
  test_error_manifest_checksum_rewrite "$_copy"
  test_failure_expect diff_two_timer_artifacts 2 -- \
    "$_tool" "--artifacts=$_scratch/artifacts_two_timer_artifacts" \
    "$_baseline" "$_copy" "$_scratch/out_two_timer_artifacts"
}

test_error_txz_tests() {
  local _baseline="$1" _wrong _kept _whole _truncated
  local _tool="$_DEV/perf2html_diff.sh"
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
      "$(path_shown "$_kept$_TEST_ERROR_ARCHIVE_SUFFIX") is gone or" \
      "overwritten after a refused run"
  echo "ok txz_previous_archive_kept"
}

test_error_batch_tests() {
  test_failure_expect batch_regenerate_no_recordings 2 -- \
    "$_DEV/perf2html_batch.sh" --regenerate "--target-dir=$1" \
    "--artifacts=$_TEST_ERROR_SCRATCH/artifacts_batch_none"
}

test_error_toolchain_tests() {
  local _bin
  _bin="$(test_error_path_without_tool valgrind)"
  test_failure_expect toolchain_missing_tool 1 -- \
    env PATH="$_bin" "$_DEV/perf2html.sh" \
    "--report=$_TEST_ERROR_SCRATCH/report_no_valgrind" \
    "--artifacts=$_TEST_ERROR_SCRATCH/artifacts_no_valgrind"
}

test_error_report_dir_tests() {
  local _baseline="$1" _tool="$_DEV/perf2html.sh" _populated _file _empty
  local _scratch="$_TEST_ERROR_SCRATCH"

  _populated="$_scratch/populated_no_manifest"
  mkdir "$_populated"
  echo 'left by test_error_handling.sh' >"$_populated/leftover.txt"
  test_failure_expect report_populated_no_manifest 1 -- \
    "$_tool" "--report=$_populated" \
    "--artifacts=$_scratch/artifacts_populated"
  [ -f "$_populated/leftover.txt" ] \
    || test_fail report_populated_kept \
      "$(path_shown "$_populated/leftover.txt") is gone after a" \
      "refused prompt"
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
}

test_error_expected_behavior_tests() {
  local _bin
  _bin="$(test_error_path_without_tool shfmt)"
  mkdir "$_TEST_ERROR_SCRATCH/home"
  test_failure_expect test_expected_behavior_missing_tool 1 -- \
    env PATH="$_bin" HOME="$_TEST_ERROR_SCRATCH/home" \
    "$_TEST_EXPECTED_BEHAVIOR" --regenerate
  test_error_relink_test
}

test_error_relink_test() {
  local _row _rows _binary
  local _reference="$_TEST_ERROR_SCRATCH/mtime_reference"
  _rows="$_TEST_ERROR_ARTIFACTS/$(basename "$_TEST_ERROR_BASELINE_REPORT")"
  _rows="$_rows/header.overview"
  _rows="$_rows.$(basename "$_TEST_ERROR_BASELINE_REPORT").txt"
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
  test_error_diff_tests "$_baseline" "$_modified" "$_diff"
  test_error_txz_tests "$_baseline"
  test_error_batch_tests "$_target"
  test_error_report_dir_tests "$_baseline"
  test_error_toolchain_tests
  test_error_expected_behavior_tests
  rm -rf "$_TEST_ERROR_SCRATCH"
}

main() {
  test_error_markdown_formatter_check
  test_error_expected_behavior_run
  test_error_cache_populated_check
  test_error_regenerate_cache_check
  test_error_failure_tests_run
  test_error_markdown_check_run
  printf 'test_error_handling.sh: %ss total\n' "$SECONDS"
}

main
