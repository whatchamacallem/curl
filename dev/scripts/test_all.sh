#!/usr/bin/env bash

# This comment intentionally blank. No documentation goes here.

set -euo pipefail

# usage_show - the one usage text, printed by -h and on a bad argument
usage_show() {
  cat <<'EOF'
test_all.sh [--help]
    Runs enforcer.sh --keep-artifacts --verbose into dev/enforcer.md, checks
    a --regenerate from the recordings it kept, runs the failure-mode tests
    on copies of its reports, then prettier --check over that markdown.
    --help is its only argument.
EOF
}

[ $# = 0 ] || { [[ $* =~ ^(-h|--help)$ ]] && usage_show && exit 0; } \
  || { echo "error: unknown option: $*" && usage_show && exit 22; } >&2

_SCRIPT="$(readlink -f "$0")"
_SCRIPTS="$(dirname "$_SCRIPT")"
_DEV="$(dirname "$_SCRIPTS")"
_REPO="$(dirname "$_DEV")"
_ENFORCER="$_SCRIPTS/enforcer.sh"

# for tool_find, so this finds the prettier the enforcer finds
. "$_SCRIPTS/shared.sh"

# the enforcer's stderr, its whole markdown and every refusal, beside the
# reports it writes; dev/.gitignore names it. Its stdout stays on the terminal
_ENFORCER_DOCUMENT="$_DEV/enforcer.md"

# the formatter proving that markdown valid: the one the enforcer runs, with
# its config, so the markdown is what prettier would print. Its install command
_MARKDOWN_FORMATTER=prettier
_MARKDOWN_FORMATTER_CONFIG="$_SCRIPTS/.prettierrc.json"
_MARKDOWN_FORMATTER_INSTALL="npm install -g prettier"

# the three reports the enforcer's batch writes, by its default names. The
# failure tests copy them; only the last one reads an original, touching it
_BASELINE_REPORT="$_DEV/perf2html_baseline_report"
_MODIFIED_REPORT="$_DEV/perf2html_modified_report"
_DIFF_REPORT="$_DEV/perf2html_diff_report"

# the recordings the enforcer's batch keeps, one subdirectory per report:
# what a --regenerate reads, and where the relink test reads a row from
_ARTIFACTS="$_DEV/perf2html_temporary_artifacts"

# the recordings' fixed name parts, spelled here on purpose: verification
# never reads the settings the code under test reads
_CALLGRIND_LOOPS=200
_TIMING_FILE_PREFIX=perf-stat

# the row a report's MANIFEST.txt records its checksum on, re-recorded on a
# copy whose files a test changed on purpose
_MANIFEST_CHECKSUM_LABEL=checksum

# every copy and fixture, under build/ as it is no output (dev/.gitignore):
# replaced by each run, deleted once every test passed, kept by a failed one
_TEST_ALL_SCRATCH="$_DEV/build/test_all_scratch"

# path_shown - one path with $HOME/ written as ~/, for a printed line
path_shown() {
  printf '%s' "${1//"$HOME"\//"~/"}"
}

# test_fail - the failed test and why, on stderr, then stop: the refusal
# streamed just above, and the scratch dir is kept for a reader.
test_fail() {
  {
    printf '\nFAILED: %s: %s\n' "$1" "$2"
    echo "(kept: $(path_shown "$_TEST_ALL_SCRATCH"))"
  } >&2
  exit 1
}

# failure_expect - run a command that must refuse with the exit code given.
# Nothing is captured: its refusal streams as it prints. Args: NAME CODE --
failure_expect() {
  local _name="$1" _wanted_code="$2" _code=0
  shift 2
  [ "${1:-}" = -- ] || test_fail "$_name" "failure_expect wants -- first"
  shift
  # stdin is closed: a delete prompt a test reaches gets no answer, a no,
  # instead of waiting on the terminal
  "$@" </dev/null || _code=$?
  [ "$_code" = "$_wanted_code" ] \
    || test_fail "$_name" "exit $_code, expected $_wanted_code, from: $*"
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
  local _tool="$1" _bin="$_TEST_ALL_SCRATCH/bin_without_$1" _dirs=() _dir
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

# markdown_formatter_check - find the last step's formatter, or refuse before
# the enforcer's minutes are spent, naming its install command. SETS _PRETTIER.
markdown_formatter_check() {
  _PRETTIER="$(tool_find "$_MARKDOWN_FORMATTER")" && return 0
  {
    echo "error: 1 tool(s) missing, so $(path_shown "$_ENFORCER_DOCUMENT")" \
      "is not checked: $_MARKDOWN_FORMATTER"
    echo "  $_MARKDOWN_FORMATTER_INSTALL"
  } >&2
  exit 1
}

# markdown_check_run - prettier --check over the enforcer's document, once
# every test passed: a failed run's error matters more. Exit 1 names the file.
markdown_check_run() {
  local _code=0
  # at log level warn prettier names only a file it would change
  "$_PRETTIER" --config "$_MARKDOWN_FORMATTER_CONFIG" \
    --log-level warn --check "$_ENFORCER_DOCUMENT" || _code=$?
  if [ "$_code" != 0 ]; then
    printf 'FAILED: %s --check exited %s on %s\n' "$_MARKDOWN_FORMATTER" \
      "$_code" "$(path_shown "$_ENFORCER_DOCUMENT")" >&2
    exit "$_code"
  fi
  echo "ok enforcer_markdown_check"
}

# enforcer_run - the one measuring run, verbose, its stderr redirected into
# the markdown and nothing else touched. Its failure is this script's.
enforcer_run() {
  local _code=0 _start=$SECONDS
  # stdin is closed: a delete prompt would sit unseen in the redirected
  # stderr, so it gets no answer, a no, and the markdown's tail names the dir
  "$_ENFORCER" --keep-artifacts --verbose 2>"$_ENFORCER_DOCUMENT" </dev/null \
    || _code=$?
  if [ "$_code" != 0 ]; then
    printf 'FAILED: enforcer.sh exited %s, see %s\n' "$_code" \
      "$(path_shown "$_ENFORCER_DOCUMENT")" >&2
    exit "$_code"
  fi
  printf 'enforcer.sh --keep-artifacts: %ss\n' "$((SECONDS - _start))"
}

# makefile_test_names - every TESTS_C test in tests/perf/Makefile.inc, one
# name per line: the inventory the cache must hold recordings for.
makefile_test_names() {
  # grep answers 1 on no match; the caller counts the names and refuses,
  # naming the file, instead of dying wordless under pipefail
  sed -n '/^TESTS_C *=/,/^$/p' "$_REPO/tests/perf/Makefile.inc" \
    | grep -o '[A-Za-z0-9_]*\.c' | sed 's/\.c$//' | sort || true
}

# cache_populated_check - after the measuring run, every recording a later
# --regenerate reads must sit in the kept artifacts dir, for both reports.
cache_populated_check() {
  local _tests=() _report _name _rows _recorded _test _file
  mapfile -t _tests < <(makefile_test_names)
  [ "${#_tests[@]}" -gt 0 ] || test_fail cache_populated \
    "no TESTS_C entry in $_REPO/tests/perf/Makefile.inc"
  for _report in "$_BASELINE_REPORT" "$_MODIFIED_REPORT"; do
    _name="$(basename "$_report")"
    _rows="$_ARTIFACTS/$_name/header.overview.$_name.txt"
    [ -f "$_rows" ] || test_fail cache_populated "no rows file $_rows"
    _recorded="$(sed -n 's/^recorded=//p' "$_rows" | head -n 1)"
    _recorded="${_recorded%% *}"
    [ -n "$_recorded" ] \
      || test_fail cache_populated "no recorded= row in $_rows"
    for _test in "${_tests[@]}"; do
      for _file in \
        "callgrind.out.$_test.$_CALLGRIND_LOOPS.$_recorded" \
        "valgrind.$_test.$_CALLGRIND_LOOPS.$_recorded.log" \
        "$_TIMING_FILE_PREFIX.$_test.$_recorded.csv" \
        "$_TIMING_FILE_PREFIX.$_test.$_recorded.txt" \
        "trace.$_test.$_CALLGRIND_LOOPS.$_recorded.log" \
        "trace.$_test.$_CALLGRIND_LOOPS.$_recorded.speedscope.json"; do
        [ -f "$_ARTIFACTS/$_name/$_file" ] || test_fail cache_populated \
          "no recording $_ARTIFACTS/$_name/$_file"
      done
    done
  done
}

# cache_snapshot_of - one line per file under the kept artifacts dir: its
# cksum, its size and its relative path, the whole listing sorted.
cache_snapshot_of() {
  (cd "$_ARTIFACTS" && find . -type f -print | LC_ALL=C sort \
    | LC_ALL=C tr '\n' '\0' | xargs -0 -r cksum -- | LC_ALL=C sort)
}

# regenerate_cache_check - the batch's --regenerate must run from the kept
# cache: no kept file changed or removed, and no new recording measured.
regenerate_cache_check() {
  local _before _after _gone _new _line _path _name _start=$SECONDS _code=0
  _before="$(cache_snapshot_of)"
  "$_DEV/perf2html_batch.sh" --regenerate "--target-dir=$_DEV" </dev/null \
    || _code=$?
  [ "$_code" = 0 ] || test_fail regenerate_from_cache \
    "perf2html_batch.sh --regenerate exited $_code"
  printf 'perf2html_batch.sh --regenerate: %ss\n' "$((SECONDS - _start))"
  _after="$(cache_snapshot_of)"
  _gone="$(comm -23 <(printf '%s\n' "$_before") <(printf '%s\n' "$_after"))"
  [ -z "$_gone" ] || test_fail regenerate_cache_unchanged \
    "$(grep -c . <<<"$_gone") kept file(s) changed: ${_gone%%$'\n'*}"
  _new="$(comm -13 <(printf '%s\n' "$_before") <(printf '%s\n' "$_after"))"
  # a recording-named file in a measured report's own subdirectory; the
  # diff's subdirectory re-extracts callgrind.out.* copies by design
  while IFS= read -r _line; do
    [ -n "$_line" ] || continue
    _path="${_line##* }"
    for _name in "$(basename "$_BASELINE_REPORT")" \
      "$(basename "$_MODIFIED_REPORT")"; do
      case "$_path" in
        "./$_name/callgrind.out."* | "./$_name/valgrind."* | \
          "./$_name/trace."* | "./$_name/$_TIMING_FILE_PREFIX".*)
          test_fail regenerate_no_new_recordings \
            "--regenerate recorded a new file: $_path"
          ;;
      esac
    done
  done <<<"$_new"
  echo "ok regenerate_cache_unchanged"
}

# unknown_option_tests - every script refusing an argument it does not know,
# before it does anything. Each one is cheap and writes nothing.
unknown_option_tests() {
  failure_expect enforcer_unknown_option 2 -- "$_ENFORCER" --bogus-option
  failure_expect test_all_unknown_option 2 -- "$_SCRIPT" --bogus-option

  # clean.sh once read no arguments and cleaned on any, so its refusal is
  # proved to be in its text before it is run with an argument at all
  grep -q 'unknown option' "$_DEV/clean.sh" \
    || test_fail clean_unknown_option "clean.sh holds no 'unknown option'"
  failure_expect clean_unknown_option 2 -- "$_DEV/clean.sh" --bogus-option

  # perf2html.sh and the batch take every unknown argument as a cmake flag,
  # by design, so only the diff among the three is asked
  failure_expect diff_unknown_option 2 -- \
    "$_DEV/perf2html_diff.sh" \
    "--artifacts=$_TEST_ALL_SCRATCH/artifacts_unknown" --bogus-option
}

# diff_tests - perf2html_diff.sh refusing an input, every one before it
# writes a page. Args: the clean copies of baseline, modified and diff.
diff_tests() {
  local _baseline="$1" _modified="$2" _diff="$3" _copy _archive
  local _tool="$_DEV/perf2html_diff.sh"

  failure_expect diff_of_a_diff 2 -- \
    "$_tool" "--artifacts=$_TEST_ALL_SCRATCH/artifacts_diff_of_a_diff" \
    "$_diff" "$_modified" "$_TEST_ALL_SCRATCH/out_diff_of_a_diff"

  failure_expect diff_missing_directory 2 -- \
    "$_tool" "--artifacts=$_TEST_ALL_SCRATCH/artifacts_missing" \
    "$_baseline" "$_TEST_ALL_SCRATCH/never_made" \
    "$_TEST_ALL_SCRATCH/out_missing"

  failure_expect diff_four_directories 2 -- \
    "$_tool" "--artifacts=$_TEST_ALL_SCRATCH/artifacts_four" \
    "$_baseline" "$_modified" "$_TEST_ALL_SCRATCH/out_four" \
    "$_TEST_ALL_SCRATCH/fourth"

  # the output is deleted first thing, so one naming an input must refuse
  _copy="$(report_copy "$_TEST_ALL_SCRATCH/modified_as_output" "$_modified")"
  failure_expect diff_output_is_an_input 2 -- \
    "$_tool" "--artifacts=$_TEST_ALL_SCRATCH/artifacts_output_input" \
    "$_baseline" "$_copy" "$_copy"

  _copy="$(report_copy "$_TEST_ALL_SCRATCH/modified_no_manifest" "$_modified")"
  rm "$_copy/MANIFEST.txt"
  failure_expect diff_no_manifest 2 -- \
    "$_tool" "--artifacts=$_TEST_ALL_SCRATCH/artifacts_no_manifest" \
    "$_baseline" "$_copy" "$_TEST_ALL_SCRATCH/out_no_manifest"

  _copy="$(report_copy "$_TEST_ALL_SCRATCH/modified_bad_version" "$_modified")"
  sed -i '1s/.*/edited by test_all.sh/' "$_copy/MANIFEST.txt"
  failure_expect diff_unrecognized_manifest 2 -- \
    "$_tool" "--artifacts=$_TEST_ALL_SCRATCH/artifacts_bad_version" \
    "$_baseline" "$_copy" "$_TEST_ALL_SCRATCH/out_bad_version"

  _copy="$(report_copy "$_TEST_ALL_SCRATCH/baseline_extra_file" "$_baseline")"
  echo 'added by test_all.sh' >"$_copy/extra_file.txt"
  failure_expect diff_checksum_added_file 2 -- \
    "$_tool" "--artifacts=$_TEST_ALL_SCRATCH/artifacts_added_file" \
    "$_copy" "$_modified" "$_TEST_ALL_SCRATCH/out_added_file"

  _copy="$(report_copy "$_TEST_ALL_SCRATCH/modified_edited_page" "$_modified")"
  echo >>"$_copy/index.html"
  failure_expect diff_checksum_edited_page 2 -- \
    "$_tool" "--artifacts=$_TEST_ALL_SCRATCH/artifacts_edited_page" \
    "$_baseline" "$_copy" "$_TEST_ALL_SCRATCH/out_edited_page"

  # one test's archive gone and the checksum re-recorded over what is left,
  # so the pairing, not the checksum, is what refuses
  _copy="$(report_copy "$_TEST_ALL_SCRATCH/modified_one_sided" "$_modified")"
  _archive="$(archive_first_of "$_copy")"
  rm "$_archive"
  manifest_checksum_rewrite "$_copy"
  failure_expect diff_one_sided_test 2 -- \
    "$_tool" "--artifacts=$_TEST_ALL_SCRATCH/artifacts_one_sided" \
    "$_baseline" "$_copy" "$_TEST_ALL_SCRATCH/out_one_sided"
}

# batch_tests - perf2html_batch.sh --regenerate refusing, before it deletes
# or writes anything, when the recordings are gone. Args: the target dir.
batch_tests() {
  failure_expect batch_regenerate_no_recordings 2 -- \
    "$_DEV/perf2html_batch.sh" --regenerate "--target-dir=$1" \
    "--artifacts=$_TEST_ALL_SCRATCH/artifacts_batch_none"
}

# toolchain_tests - perf2html.sh refusing before any build once one tool is
# off the PATH, shown a PATH of links minus that tool.
toolchain_tests() {
  local _bin
  _bin="$(path_without_tool valgrind)"
  failure_expect toolchain_missing_tool 1 -- \
    env PATH="$_bin" "$_DEV/perf2html.sh" \
    "--report=$_TEST_ALL_SCRATCH/report_no_valgrind" \
    "--artifacts=$_TEST_ALL_SCRATCH/artifacts_no_valgrind"
}

# report_dir_tests - perf2html.sh refusing a report or artifacts path, each
# before it builds anything. Args: the clean copy of the baseline.
report_dir_tests() {
  local _baseline="$1" _tool="$_DEV/perf2html.sh" _populated _file _empty

  # a populated dir with no MANIFEST.txt goes only on a typed y: with stdin
  # closed the prompt is a no, exit 1, and the dir is left as it was
  _populated="$_TEST_ALL_SCRATCH/populated_no_manifest"
  mkdir "$_populated"
  echo 'left by test_all.sh' >"$_populated/leftover.txt"
  failure_expect report_populated_no_manifest 1 -- \
    "$_tool" "--report=$_populated" \
    "--artifacts=$_TEST_ALL_SCRATCH/artifacts_populated"
  [ -f "$_populated/leftover.txt" ] || test_fail report_populated_kept \
    "$(path_shown "$_populated/leftover.txt") is gone after a refused prompt"
  echo "ok report_populated_kept"

  # a target that is no directory gets the same prompt: with stdin closed
  # that is a no, exit 1, and the file is left as it was
  _file="$_TEST_ALL_SCRATCH/report_is_a_file.txt"
  echo 'a file, not a directory' >"$_file"
  failure_expect report_is_a_file 1 -- \
    "$_tool" "--report=$_file" "--artifacts=$_TEST_ALL_SCRATCH/artifacts_file"
  [ -f "$_file" ] || test_fail report_file_kept \
    "$(path_shown "$_file") is gone after a refused prompt"
  echo "ok report_file_kept"

  failure_expect artifacts_inside_report 2 -- \
    "$_tool" "--report=$_baseline" "--artifacts=$_baseline/inside"

  _empty="$_TEST_ALL_SCRATCH/artifacts_empty"
  mkdir "$_empty"
  failure_expect regenerate_missing_recordings 2 -- \
    "$_tool" --regenerate "--report=$_baseline" "--artifacts=$_empty"
}

# enforcer_tests - enforcer.sh refusing before it clears the real reports:
# a stage's tool off the PATH, then perf re-linked.
enforcer_tests() {
  local _bin
  # both refusals come before the reports are cleared; the fake HOME is
  # because tool_find looks under it too, past the PATH
  _bin="$(path_without_tool shfmt)"
  mkdir "$_TEST_ALL_SCRATCH/home"
  failure_expect enforcer_missing_tool 1 -- \
    env PATH="$_bin" HOME="$_TEST_ALL_SCRATCH/home" "$_ENFORCER" --regenerate
  relink_test
}

# relink_test - enforcer.sh --regenerate against the real recordings,
# refusing once the baseline's perf binary is newer than they are.
relink_test() {
  local _row _rows _binary _reference="$_TEST_ALL_SCRATCH/mtime_reference"
  # the baseline's rows file in the artifacts dir names its executable: the
  # same file the enforcer's --regenerate reads, and no report
  _rows="$_ARTIFACTS/$(basename "$_BASELINE_REPORT")"
  _rows="$_rows/header.overview.$(basename "$_BASELINE_REPORT").txt"
  [ -f "$_rows" ] || test_fail regenerate_after_relink "no $_rows"
  _row="$(sed -n 's/^executable=//p' "$_rows" | head -n 1)"
  [ -n "$_row" ] || test_fail regenerate_after_relink \
    "no executable= row in $_rows"
  _binary="$_REPO/${_row%% *}"
  [ -f "$_binary" ] || test_fail regenerate_after_relink \
    "no executable at $_binary"
  failure_expect regenerate_after_relink 2 -- \
    relink_regenerate_run "$_binary" "$_reference"
}

# failure_tests_run - every failure mode, against copies in the scratch dir,
# stopping at the first that does not refuse as it must.
failure_tests_run() {
  local _target _baseline _modified _diff
  # a failed run left its fixtures here for a reader; this run's replace them
  rm -rf "$_TEST_ALL_SCRATCH"
  mkdir -p "$_TEST_ALL_SCRATCH"
  unknown_option_tests

  # the clean copies sit in one dir under the batch's own names, as the
  # batch wrote them, so its --regenerate can be asked about them too
  _target="$_TEST_ALL_SCRATCH/target"
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
  rm -rf "$_TEST_ALL_SCRATCH"
}

# main - the enforcer's measuring run, the cache checks over its recordings,
# the failure tests on copies of its reports, then the markdown check
main() {
  markdown_formatter_check
  enforcer_run
  cache_populated_check
  regenerate_cache_check
  failure_tests_run
  markdown_check_run
  printf 'test_all.sh: %ss total\n' "$SECONDS"
}

main
