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

# usage_show - the one usage text, printed by -h and on a bad argument
usage_show() {
  cat <<'EOF'
perf2html_diff.sh [debug-flags] [baseline] [modified] [diff]
    Measures nothing: Compares the counters in two profiling reports and
    generates a diff. Directories default to
    ./perf2html_{baseline,modified,diff}_report. Both baseline and modified
    must be a perf2html.sh report. A diff can't be diffed.

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

# args_parse - reads the flags and the three directories, all absolute
args_parse() {
  _KEEP_ARTIFACTS=0
  _REGENERATE=0
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
        shift
        ;;
      --regenerate)
        _REGENERATE=1
        _KEEP_ARTIFACTS=1
        shift
        ;;
      --artifacts=*)
        ARTIFACTS_DIR="${1#--artifacts=}"
        shift
        ;;
      *) break ;;
    esac
  done
  _BASE_DIR=perf2html_baseline_report
  _MOD_DIR=perf2html_modified_report
  _OUT_DIR=perf2html_diff_report
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
      usage_show >&2
      exit 2
      ;;
  esac
  local _dir
  for _dir in _BASE_DIR _MOD_DIR _OUT_DIR; do
    printf -v "$_dir" '%s' "$(absolute_path "${!_dir}")"
  done
  if [ -z "$ARTIFACTS_DIR" ]; then
    ARTIFACTS_DIR="$(dirname "$_OUT_DIR")/$ARTIFACTS_NAME"
  fi
  ARTIFACTS_DIR="$(absolute_path "$ARTIFACTS_DIR")"
}

# manifest_check - refuse an input whose version line is not exactly a
# perf2html.sh report's, which is how a diff is never read back as one.
manifest_check() {
  local _dir="$1" _role="$2" _manifest="$1/MANIFEST.txt"
  if [ -f "$_manifest" ] \
    && [ "$(head -1 "$_manifest")" = "$REPORT_MANIFEST_VERSION_DIFF" ]; then
    error_exit 2 "error: can't diff a diff -- the $_role report was" \
      "       written by perf2html_diff.sh: $_dir"
  fi
  manifest_verify "$_dir" "$_role" "$REPORT_MANIFEST_VERSION_FULL"
}

# header_file_of - writes one input's LABEL=VALUE rows for the overview
header_file_of() {
  local _dir="$1" _role="$2"
  local _out="$ARTIFACTS_DIR/header.$_role.$TIMESTAMP.txt"
  {
    echo "report=$(path_display "$_dir")"
    grep '=' "$_dir/MANIFEST.txt" \
      || error_exit 2 "error: no LABEL=VALUE row in $_dir/MANIFEST.txt"
  } >"$_out"
  echo "$_out"
}

# profiles_extract - unpack one report's archives once into the named
# listing, synthesizing "all". Never $(...): command_run's tee lands in it.
profiles_extract() {
  # a row is "<test>", then one profile path per line, blank-line
  # terminated, so a path holding a space survives
  local _dir="$1" _role="$2" _listing="$3"
  local _archive _test _into _every=()
  local -a _files
  : >"$_listing"
  for _archive in "$_dir"/*/raw/*"$REPORT_RAW_ARCHIVE_SUFFIX"; do
    [ -f "$_archive" ] || continue
    _test="$(basename "$(dirname "$(dirname "$_archive")")")"
    _into="$ARTIFACTS_DIR/$_role.$_test.$TIMESTAMP"
    rm -rf "$_into"
    mkdir -p "$_into"
    command_run tar xJf "$_archive" -C "$_into"
    mapfile -t _files < <(find "$_into" -maxdepth 1 -type f \
      -name 'callgrind.out.*' | sort)
    [ "${#_files[@]}" != 0 ] \
      || error_exit 2 "error: no callgrind.out.* file in $_archive"
    listing_row_write "$_listing" "$_test" "${_files[@]}"
    _every+=("${_files[@]}")
  done
  [ "${#_every[@]}" -eq 0 ] \
    || listing_row_write "$_listing" all "${_every[@]}"
}

# listing_row_write - appends one "<test>" row and its profile paths, one
# per line, to a listing
listing_row_write() {
  local _listing="$1" _test="$2" _file
  shift 2
  {
    echo "$_test"
    for _file in "$@"; do echo "$_file"; done
    echo
  } >>"$_listing"
}

# tests_names_of - every test name a listing holds, sorted and unique
tests_names_of() {
  awk 'head { print; head = 0; next }
       /^$/ { head = 1 }
       BEGIN { head = 1 }' "$1" | sort -u
}

# tests_pair - the tests both reports hold; a one-sided name is a hard error
tests_pair() {
  local _base_tests _cur_tests _name
  _base_tests="$(tests_names_of "$_BASE_LISTING")"
  _cur_tests="$(tests_names_of "$_MODIFIED_LISTING")"
  local _holding="error: no */raw/*$REPORT_RAW_ARCHIVE_SUFFIX archive holding"
  [ -n "$_base_tests" ] || error_exit 2 \
    "$_holding callgrind.out.* in the baseline report: $_BASE_DIR"
  [ -n "$_cur_tests" ] || error_exit 2 \
    "$_holding callgrind.out.* in the modified report: $_MOD_DIR"
  for _name in $(comm -3 <(echo "$_base_tests") <(echo "$_cur_tests")); do
    error_exit 2 "error: '$_name' is in only one of the two reports, so" \
      "       it has no delta: $_BASE_DIR vs $_MOD_DIR"
  done
  comm -12 <(echo "$_base_tests") <(echo "$_cur_tests")
}

# profiles_of - one test's profile files, one per line, out of a listing
profiles_of() {
  awk -v want="$2" \
    'BEGIN { head = 1 }
     head { head = 0; taking = ($0 == want); next }
     /^$/ { head = 1; if(taking) { exit }; next }
     taking { print }' "$1"
}

# diff_one - subtracts one test and generates its summary and heat map
diff_one() {
  local _test="$1" _out="$2" _name="$3"
  local _diff_file _callers_file _file
  local _archive
  local -a _base_files _cur_files _args
  _diff_file="$ARTIFACTS_DIR/callgrind.diff.$_name.$TIMESTAMP"
  _callers_file="$_diff_file.callers.json"
  mapfile -t _base_files < <(profiles_of "$_BASE_LISTING" "$_test")
  mapfile -t _cur_files < <(profiles_of "$_MODIFIED_LISTING" "$_test")

  heading_print "python3 callgrind_diff.py $_name"
  _args=(python3 "$PERF2HTML_DIR_/scripts/callgrind_diff.py" -o "$_diff_file"
    --callers-output "$_callers_file")
  for _file in "${_base_files[@]}"; do _args+=(--baseline "$_file"); done
  for _file in "${_cur_files[@]}"; do _args+=(--current "$_file"); done
  command_run "${_args[@]}"

  heading_print "python3 callgrind_to_heatmap.py $_name --diff"
  command_run python3 "$PERF2HTML_DIR_/scripts/callgrind_to_heatmap.py" \
    "$_diff_file" -o "$_out/heat-map/index.html" \
    --title "$_name / heat map" --diff \
    --baseline-data "$_callers_file"

  heading_print "python3 build_report.py test $_name"
  rm -rf "$_out/raw"
  _archive="$_out/raw/$(basename "$_out")$REPORT_RAW_ARCHIVE_SUFFIX"
  archive_write "$(basename "$_out")" "$_out" "" \
    "$_diff_file" "$_callers_file"
  command_run python3 "$PERF2HTML_DIR_/scripts/build_report.py" test \
    "$_diff_file" -o "$_out/index.html" --test "$_name" --diff \
    --callers-data "$_callers_file" --raw-data "$_archive"
  log_verbose "$(printf '%-13sdiff -> %s' "$_name" "$_out/index.html")"
}

# main - checks both inputs, diffs every shared test, stamps the report
main() {
  args_parse "$@"
  verbose_begin
  title_print "$_SCRIPT" "$@"

  manifest_check "$_BASE_DIR" baseline
  manifest_check "$_MOD_DIR" modified
  if [ "$_REGENERATE" = 1 ]; then
    # a regenerated report keeps the stamp of the run that measured it, so
    # its own stamp= row never claims a measurement this run did not take
    TIMESTAMP="$(manifest_stamp_of "$_OUT_DIR" "--regenerate input" \
      "$REPORT_MANIFEST_VERSION_DIFF")"
  fi

  [ "$_KEEP_ARTIFACTS" = 1 ] || artifacts_clean
  report_begin "$_OUT_DIR" "diff.$TIMESTAMP.log" \
    "dev/perf2html_diff.sh $TIMESTAMP: $_BASE_DIR -> $_MOD_DIR -> $_OUT_DIR" \
    "$_REGENERATE"

  local _tests _test_name
  local -a _args
  _BASE_LISTING="$ARTIFACTS_DIR/profiles.baseline.$TIMESTAMP.txt"
  _MODIFIED_LISTING="$ARTIFACTS_DIR/profiles.modified.$TIMESTAMP.txt"
  profiles_extract "$_BASE_DIR" baseline "$_BASE_LISTING"
  profiles_extract "$_MOD_DIR" modified "$_MODIFIED_LISTING"
  _tests="$(tests_pair)"
  [ -n "$_tests" ] \
    || error_exit 2 "error: the two reports have no test in common"
  log_verbose "$_SCRIPT $TIMESTAMP: $(basename "$_BASE_DIR") ->" \
    "$(basename "$_MOD_DIR")"
  _args=(-o "$_OUT_DIR/index.html" --diff
    --header-block "baseline=$(header_file_of "$_BASE_DIR" baseline)"
    --header-block "modified=$(header_file_of "$_MOD_DIR" modified)")
  for _test_name in $_tests; do
    diff_one "$_test_name" "$_OUT_DIR/$_test_name" "$_test_name"
    _args+=(--test "$_test_name" --diff-profile
      "$_test_name=$ARTIFACTS_DIR/callgrind.diff.$_test_name.$TIMESTAMP")
  done
  heading_print "python3 build_report.py overview --diff"
  command_run python3 "$PERF2HTML_DIR_/scripts/build_report.py" overview \
    "${_args[@]}"
  log_verbose "$(printf '%-13s%s' overview "$_OUT_DIR/index.html")"

  report_finish "$_OUT_DIR" "$REPORT_MANIFEST_VERSION_DIFF" \
    "baseline=$(path_display "$_BASE_DIR")" \
    "modified=$(path_display "$_MOD_DIR")" \
    "$(manifest_stamp_row)"
  if [ "$_KEEP_ARTIFACTS" != 1 ]; then artifacts_clean; fi
}

main "$@"
