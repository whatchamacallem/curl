#!/usr/bin/env bash

# This comment intentionally blank. No documentation goes here.

set -euo pipefail

# usage_show - the one usage line, printed by -h and on any other argument
usage_show() {
  printf '%s %s\n' 'test_all.sh  no arguments: enforcer.sh --keep-artifacts,' \
    'then the failure tests'
}

_SCRIPT="$(readlink -f "$0")"
_SCRIPTS="$(dirname "$_SCRIPT")"
_DEV="$(dirname "$_SCRIPTS")"
_REPO="$(dirname "$_DEV")"
_ENFORCER="$_SCRIPTS/enforcer.sh"

# the enforcer's stdout, the run's markdown, and its stderr, both beside the
# reports it writes; dev/.gitignore names both
_ENFORCER_DOCUMENT="$_DEV/enforcer.md"
_ENFORCER_LOG="$_DEV/enforcer.log"

# the three reports the enforcer's batch writes, by its default names. The
# failure tests copy them; only the last one reads an original, touching it
_BASELINE_REPORT="$_DEV/perf2html_baseline_report"
_MODIFIED_REPORT="$_DEV/perf2html_modified_report"
_DIFF_REPORT="$_DEV/perf2html_diff_report"

# the row a report's MANIFEST.txt records its checksum on, re-recorded on a
# copy whose files a test changed on purpose
_MANIFEST_CHECKSUM_LABEL=checksum

# where every copy and captured output goes: made by main and deleted only
# once every test passed, so a failed run keeps its diagnostics
_SCRATCH=""

# path_shown - one path with $HOME/ written as ~/, for a printed line
path_shown() {
  printf '%s' "${1//"$HOME"\//"~/"}"
}

# test_fail - the failed test, why, and the output it captured in one txt
# fence, all on stderr, then stop: the scratch dir is kept for a reader.
test_fail() {
  local _name="$1" _reason="$2" _output="${3:-}"
  {
    printf '\nFAILED: %s: %s\n' "$_name" "$_reason"
    if [ -n "$_output" ]; then
      echo '```txt'
      cat "$_output"
      echo '```'
    fi
    echo "(kept: $(path_shown "$_SCRATCH"))"
  } >&2
  exit 1
}

# failure_expect - run a command that must refuse with the exit code given
# and the keyword in its output. Args: NAME CODE KEYWORD -- command...
failure_expect() {
  local _name="$1" _wanted_code="$2" _keyword="$3"
  shift 3
  [ "${1:-}" = -- ] || test_fail "$_name" "failure_expect wants -- first"
  shift
  local _output="$_SCRATCH/output.$_name.txt" _code=0
  "$@" >"$_output" 2>&1 || _code=$?
  if [ "$_code" != "$_wanted_code" ]; then
    test_fail "$_name" "exit $_code, expected $_wanted_code, from: $*" \
      "$_output"
  fi
  if ! grep -q -F -- "$_keyword" "$_output"; then
    test_fail "$_name" "no '$_keyword' in the output of: $*" "$_output"
  fi
  echo "ok $_name"
}

# report_copy - copy a report to the path given, under the scratch dir, and
# echo that path. Every test edits a copy, never a report.
report_copy() {
  cp -a "$2" "$1"
  echo "$1"
}

# path_without_tool - a PATH holding every command on this one but the tool
# named: links in the scratch dir, the tool's removed. Echoes the dir.
path_without_tool() {
  local _tool="$1" _bin="$_SCRATCH/bin_without_$1" _dirs=() _dir
  mkdir "$_bin"
  IFS=: read -r -a _dirs <<<"$PATH"
  for _dir in "${_dirs[@]}"; do
    case "$_dir" in /*) ;; *) continue ;; esac
    [ -d "$_dir" ] || continue
    cp -rs --update=none "$_dir"/. "$_bin"/
  done
  [ -e "$_bin/$_tool" ] || test_fail path_without_tool "no $_tool on PATH"
  rm "$_bin/$_tool"
  echo "$_bin"
}

# manifest_checksum_rewrite - re-record a copy's checksum row after a test
# changed its files on purpose, so the check after the checksum is reached.
manifest_checksum_rewrite() {
  local _dir="$1" _manifest="$1/MANIFEST.txt" _checksum _row
  grep -q "^$_MANIFEST_CHECKSUM_LABEL=" "$_manifest" \
    || test_fail manifest_checksum_rewrite \
      "no $_MANIFEST_CHECKSUM_LABEL= row in $_manifest"
  _checksum="$(cd "$_dir" && find . -type f ! -name MANIFEST.txt -print \
    | LC_ALL=C sort | LC_ALL=C tr '\n' '\0' | xargs -0 -r cksum -- \
    | LC_ALL=C sort | cksum)"
  _row="$_MANIFEST_CHECKSUM_LABEL=$_checksum"
  sed -i "s/^$_MANIFEST_CHECKSUM_LABEL=.*/$_row/" "$_manifest"
}

# archive_first_of - the first raw archive under a report, sorted, echoed:
# the one a test removes, so no test name is ever spelled here.
archive_first_of() {
  local _archive
  _archive="$(find "$1" -mindepth 3 -maxdepth 3 -type f \
    -path '*/raw/*.txz' | LC_ALL=C sort | head -n 1)"
  [ -n "$_archive" ] || test_fail archive_first_of "no */raw/*.txz under $1"
  echo "$_archive"
}

# relink_regenerate_run - touch the baseline's perf binary, run enforcer.sh
# --regenerate, restore the binary's mtime, return the enforcer's code.
relink_regenerate_run() {
  local _binary="$1" _reference="$2" _code=0
  touch -r "$_binary" "$_reference"
  touch "$_binary"
  "$_ENFORCER" --regenerate || _code=$?
  touch -r "$_reference" "$_binary"
  return "$_code"
}

# enforcer_run - the one measuring run, verbose, its stdout teed into the
# markdown and its stderr into the log. Its failure is this script's.
enforcer_run() {
  local _code=0
  "$_ENFORCER" --keep-artifacts --verbose 2>"$_ENFORCER_LOG" \
    | tee "$_ENFORCER_DOCUMENT" || _code=$?
  if [ "$_code" != 0 ]; then
    printf 'FAILED: enforcer.sh exited %s, see %s\n' "$_code" \
      "$(path_shown "$_ENFORCER_LOG")" >&2
    exit "$_code"
  fi
}

# unknown_option_tests - every script refusing an argument it does not know,
# before it does anything. Each one is cheap and writes nothing.
unknown_option_tests() {
  failure_expect enforcer_unknown_option 2 'unknown option' -- \
    "$_ENFORCER" --bogus-option
  failure_expect test_all_unknown_option 2 'unknown option' -- \
    "$_SCRIPT" --bogus-option

  # clean.sh once read no arguments and cleaned on any, so its refusal is
  # proved to be in its text before it is run with an argument at all
  grep -q 'unknown option' "$_DEV/clean.sh" \
    || test_fail clean_unknown_option "clean.sh holds no 'unknown option'"
  failure_expect clean_unknown_option 2 'unknown option' -- \
    "$_DEV/clean.sh" --bogus-option

  # perf2html.sh and the batch take every unknown argument as a cmake flag,
  # by design, so only the diff among the three is asked
  failure_expect diff_unknown_option 2 'unknown option' -- \
    "$_DEV/perf2html_diff.sh" "--artifacts=$_SCRATCH/artifacts_unknown" \
    --bogus-option
}

# diff_tests - perf2html_diff.sh refusing an input, every one before it
# writes a page. Args: the clean copies of baseline, modified and diff.
diff_tests() {
  local _baseline="$1" _modified="$2" _diff="$3" _copy _archive
  local _tool="$_DEV/perf2html_diff.sh"

  failure_expect diff_of_a_diff 2 "can't diff a diff" -- \
    "$_tool" "--artifacts=$_SCRATCH/artifacts_diff_of_a_diff" \
    "$_diff" "$_modified" "$_SCRATCH/out_diff_of_a_diff"

  failure_expect diff_missing_directory 2 'no such directory' -- \
    "$_tool" "--artifacts=$_SCRATCH/artifacts_missing" \
    "$_baseline" "$_SCRATCH/never_made" "$_SCRATCH/out_missing"

  failure_expect diff_four_directories 2 'unknown argument' -- \
    "$_tool" "--artifacts=$_SCRATCH/artifacts_four" \
    "$_baseline" "$_modified" "$_SCRATCH/out_four" "$_SCRATCH/fourth"

  _copy="$(report_copy "$_SCRATCH/modified_no_manifest" "$_modified")"
  rm "$_copy/MANIFEST.txt"
  failure_expect diff_no_manifest 2 'no MANIFEST.txt' -- \
    "$_tool" "--artifacts=$_SCRATCH/artifacts_no_manifest" \
    "$_baseline" "$_copy" "$_SCRATCH/out_no_manifest"

  _copy="$(report_copy "$_SCRATCH/modified_bad_version" "$_modified")"
  sed -i '1s/.*/edited by test_all.sh/' "$_copy/MANIFEST.txt"
  failure_expect diff_unrecognized_manifest 2 'unrecognized MANIFEST.txt' -- \
    "$_tool" "--artifacts=$_SCRATCH/artifacts_bad_version" \
    "$_baseline" "$_copy" "$_SCRATCH/out_bad_version"

  _copy="$(report_copy "$_SCRATCH/baseline_extra_file" "$_baseline")"
  echo 'added by test_all.sh' >"$_copy/extra_file.txt"
  failure_expect diff_checksum_added_file 2 checksum -- \
    "$_tool" "--artifacts=$_SCRATCH/artifacts_added_file" \
    "$_copy" "$_modified" "$_SCRATCH/out_added_file"

  _copy="$(report_copy "$_SCRATCH/modified_edited_page" "$_modified")"
  echo >>"$_copy/index.html"
  failure_expect diff_checksum_edited_page 2 checksum -- \
    "$_tool" "--artifacts=$_SCRATCH/artifacts_edited_page" \
    "$_baseline" "$_copy" "$_SCRATCH/out_edited_page"

  # one test's archive gone and the checksum re-recorded over what is left,
  # so the pairing, not the checksum, is what refuses
  _copy="$(report_copy "$_SCRATCH/modified_one_sided" "$_modified")"
  _archive="$(archive_first_of "$_copy")"
  rm "$_archive"
  manifest_checksum_rewrite "$_copy"
  failure_expect diff_one_sided_test 2 'only one of the two reports' -- \
    "$_tool" "--artifacts=$_SCRATCH/artifacts_one_sided" \
    "$_baseline" "$_copy" "$_SCRATCH/out_one_sided"
}

# batch_tests - perf2html_batch.sh --regenerate refusing, before it deletes
# or writes anything, when the recordings are gone. Args: the target dir.
batch_tests() {
  failure_expect batch_regenerate_no_recordings 2 'no recordings' -- \
    "$_DEV/perf2html_batch.sh" --regenerate "--target-dir=$1" \
    "--artifacts=$_SCRATCH/artifacts_batch_none"
}

# toolchain_tests - perf2html.sh refusing before any build once one tool is
# off the PATH, shown a PATH of links minus that tool.
toolchain_tests() {
  local _bin
  _bin="$(path_without_tool valgrind)"
  failure_expect toolchain_missing_tool 1 'not found on PATH' -- \
    env PATH="$_bin" "$_DEV/perf2html.sh" \
    "--report=$_SCRATCH/report_no_valgrind" \
    "--artifacts=$_SCRATCH/artifacts_no_valgrind"
}

# report_dir_tests - perf2html.sh refusing a report or artifacts path, each
# before it builds anything. Args: the clean copy of the baseline.
report_dir_tests() {
  local _baseline="$1" _tool="$_DEV/perf2html.sh" _populated _file _empty

  _populated="$_SCRATCH/populated_no_manifest"
  mkdir "$_populated"
  echo 'left by test_all.sh' >"$_populated/leftover.txt"
  failure_expect report_populated_no_manifest 2 \
    'holds files but no MANIFEST.txt' -- \
    "$_tool" "--report=$_populated" \
    "--artifacts=$_SCRATCH/artifacts_populated"

  _file="$_SCRATCH/report_is_a_file.txt"
  echo 'a file, not a directory' >"$_file"
  failure_expect report_is_a_file 2 'not a directory' -- \
    "$_tool" "--report=$_file" "--artifacts=$_SCRATCH/artifacts_file"

  failure_expect artifacts_inside_report 2 'inside the report' -- \
    "$_tool" "--report=$_baseline" "--artifacts=$_baseline/inside"

  _empty="$_SCRATCH/artifacts_empty"
  mkdir "$_empty"
  failure_expect regenerate_missing_recordings 2 missing -- \
    "$_tool" --regenerate "--report=$_baseline" "--artifacts=$_empty"
}

# enforcer_tests - enforcer.sh refusing, reading the real reports and
# writing nothing: a stage's tool off the PATH, then perf re-linked.
enforcer_tests() {
  local _bin
  # --regenerate reads the reports rather than clearing them; the fake HOME
  # is because tool_find looks under it too, past the PATH
  _bin="$(path_without_tool shfmt)"
  mkdir "$_SCRATCH/home"
  failure_expect enforcer_missing_tool 1 missing -- \
    env PATH="$_bin" HOME="$_SCRATCH/home" "$_ENFORCER" --regenerate
  relink_test
}

# relink_test - enforcer.sh --regenerate against the real reports, refusing
# once the baseline's perf binary is newer than its recordings.
relink_test() {
  local _row _binary _reference="$_SCRATCH/mtime_reference"
  _row="$(sed -n 's/^executable=//p' "$_BASELINE_REPORT/MANIFEST.txt" \
    | head -n 1)"
  [ -n "$_row" ] || test_fail regenerate_after_relink \
    "no executable= row in $_BASELINE_REPORT/MANIFEST.txt"
  _binary="$_REPO/${_row%% *}"
  [ -f "$_binary" ] || test_fail regenerate_after_relink \
    "no executable at $_binary"
  failure_expect regenerate_after_relink 2 --regenerate -- \
    relink_regenerate_run "$_binary" "$_reference"
}

# failure_tests_run - every failure mode, against copies in the scratch dir,
# stopping at the first that does not refuse as it must.
failure_tests_run() {
  local _target _baseline _modified _diff
  _SCRATCH="$(mktemp -d)"
  unknown_option_tests

  # the clean copies sit in one dir under the batch's own names, as the
  # batch wrote them, so its --regenerate can be asked about them too
  _target="$_SCRATCH/target"
  mkdir "$_target"
  _baseline="$(report_copy "$_target/$(basename "$_BASELINE_REPORT")" \
    "$_BASELINE_REPORT")"
  _modified="$(report_copy "$_target/$(basename "$_MODIFIED_REPORT")" \
    "$_MODIFIED_REPORT")"
  _diff="$(report_copy "$_target/$(basename "$_DIFF_REPORT")" \
    "$_DIFF_REPORT")"

  diff_tests "$_baseline" "$_modified" "$_diff"
  batch_tests "$_target"
  report_dir_tests "$_baseline"
  toolchain_tests
  enforcer_tests
  rm -rf "$_SCRATCH"
}

# args_check - -h prints the usage line; any other argument, however many,
# is refused before anything runs.
args_check() {
  local _argument
  for _argument in "$@"; do
    if [ "$_argument" != -h ] && [ "$_argument" != --help ]; then
      {
        echo "error: unknown option: $_argument"
        usage_show
      } >&2
      exit 2
    fi
  done
  [ $# = 0 ] || {
    usage_show
    exit 0
  }
}

# main - the enforcer's measuring run, then the failure tests on its reports
main() {
  args_check "$@"
  enforcer_run
  failure_tests_run
}

main "$@"
