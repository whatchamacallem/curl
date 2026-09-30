#!/usr/bin/env bash

# The rest of this comment is intentionally blank. No documentation goes here.

usage_show() {
  cat <<'EOF'
test_expected_behavior.sh [debug-flags] [--check-formatting]
    Formats, lints and scans the files scripts/test_whitelist.txt lists,
    runs perf2html_batch.sh over the three reports it cleared, then
    validates and screenshots what it wrote. Any fault stops the run where
    it happened.
    --check-formatting  Report what would change rather than writing it.

    The debug-flags are the same as the README.md documents.
EOF
}

set -euo pipefail

_SCRIPT="$(readlink -f "$0")"
_SCRIPTS="$(dirname "$_SCRIPT")"

# Where the caller stood. This takes no path argument of its own, but
# utility.sh's absolute_path reads it, so it is set before the cd below.
INVOKED_FROM="$PWD"
cd "$_SCRIPTS"

# dev/, which the whitelist's globs and the reports sit under, and the repo
# a report's executable= row is relative to, each as seen from scripts/.
_DIR_DEV=..
_DIR_REPO=../..

# the hard column limit every whitelisted file is checked against
_COLUMNS_MAX=79
_CLANG_FORMAT_CONFIG=../src/.clang-format
_PRETTIER_CONFIG=.prettierrc.json
_PYRIGHT_CONFIG=pyrightconfig.json

# pyright's all-clear summary, the line --verbose drops from its stdout
_PYRIGHT_ALL_CLEAR_LINE='0 errors, 0 warnings, 0 informations'

# spaces shfmt indents a shell block by
_SHELL_INDENT=2
_RUFF_CONFIG=ruff.toml

# the one list of what the source stages touch, beside this script
_WHITELIST_FILE=test_whitelist.txt

. ./settings.sh
. ./utility.sh
. ./test_utility.sh

# The batch this runs, and the shooter it runs after, each beside us.
_BATCH_SCRIPT_NAME=perf2html_batch.sh
_SCREENSHOT_SCRIPT_NAME=test_screenshot.py

# The reports the batch writes, in the order it writes them. The names are
# the batch's own settings, so this agrees with it by construction.
_DEFAULT_REPORTS=(
  "$_DIR_DEV/$REPORT_BASELINE_DIR_NAME"
  "$_DIR_DEV/$REPORT_MODIFIED_DIR_NAME"
  "$_DIR_DEV/$REPORT_DIFF_DIR_NAME"
)

# tools_resolve - find every tool the source stages run, before any work.
# SETS _SHFMT, _RUFF, _CLANG_FORMAT, _PRETTIER and _PYRIGHT.
tools_resolve() {
  # a tool that is not installed never checked its files, so the run would
  # be no verification: every missing one is named with its install command
  local _missing=()
  _SHFMT="$(tool_find shfmt)" || _missing+=(shfmt)
  _RUFF="$(tool_find ruff)" || _missing+=(ruff)
  _CLANG_FORMAT="$(tool_find clang-format)" || _missing+=(clang-format)
  _PRETTIER="$(tool_find prettier)" || _missing+=(prettier)
  _PYRIGHT="$(tool_find pyright)" || _missing+=(pyright)
  [ "${#_missing[@]}" = 0 ] || error_exit 1 \
    "error: ${#_missing[@]} tool(s) missing, so nothing is verified:" \
    "${_missing[*]}" \
    "  sudo apt-get install -y shfmt clang-format" \
    "  pip3 install --user --break-system-packages ruff" \
    "  npm install -g prettier pyright"
}

# subprocess_run - one child printed as an item. Its lines reach the
# terminal as they are, and a non-zero exit is a hard error naming it.
subprocess_run() {
  local _exit_code=0
  command_item_print "$*"
  "$@" || _exit_code=$?
  [ "$_exit_code" = 0 ] \
    || error_exit "$_exit_code" "error: exit $_exit_code from: $*"
}

# whitelist_expand - expand _WHITELIST_FILE's globs against dev/, once. SETS
# _WHITELISTED_FILES, its canonical setter, sorted and without repeats.
whitelist_expand() {
  local _glob _match _line=0 _found=() _matches=()

  if [ ! -f "$_WHITELIST_FILE" ]; then
    error_exit 1 "error: $_WHITELIST_FILE: not found, so nothing is enforced"
  fi

  while IFS= read -r _glob || [ -n "$_glob" ]; do
    _line=$((_line + 1))
    if [[ -z "$_glob" || "$_glob" == '#'* || "$_glob" == *[[:space:]]* ]]; then
      error_exit 1 "error: $_WHITELIST_FILE:$_line: not one glob: '$_glob'"
    fi

    # a tool handed a directory walks it, which is what this list replaces
    mapfile -t _matches < <(compgen -G "$_DIR_DEV/$_glob")
    for _match in "${_matches[@]}"; do
      if [ ! -f "$_match" ]; then
        error_exit 1 \
          "error: $_WHITELIST_FILE:$_line: $_glob matches $_match, not a file"
      fi
    done
    _found+=("${_matches[@]}")
  done <"$_WHITELIST_FILE"

  if [ "${#_found[@]}" = 0 ]; then
    error_exit 1 \
      "error: $_WHITELIST_FILE: matches no file, so nothing is enforced"
  fi

  mapfile -t _WHITELISTED_FILES < <(printf '%s\n' "${_found[@]}" \
    | LC_ALL=C sort -u)
  log_verbose "whitelist: ${#_WHITELISTED_FILES[@]} file(s)"
}

# files_of - echo each whitelisted file ending in one of the extensions
# given. The one door a stage choosing files by kind collects them through.
files_of() {
  local _file _extension

  for _file in "${_WHITELISTED_FILES[@]}"; do
    for _extension in "$@"; do
      if [[ "$_file" == *"$_extension" ]]; then
        printf '%s\n' "$_file"
        break
      fi
    done
  done
}

# format_shell - shfmt over the whitelisted shell, writing or, under
# --check-formatting, diffing.
format_shell() {
  local _files
  mapfile -t _files < <(files_of .sh)

  heading_print shfmt
  if [ "${#_files[@]}" = 0 ]; then
    log_verbose "shfmt: no files"
    return 0
  fi

  if [ "$_CHECK" = 1 ]; then
    subprocess_run "$_SHFMT" -i "$_SHELL_INDENT" -bn -ci -ln bash -d \
      "${_files[@]}"
  else
    subprocess_run "$_SHFMT" -i "$_SHELL_INDENT" -bn -ci -ln bash -w \
      "${_files[@]}"
  fi
}

# format_python - ruff format, then ruff check, over the whitelisted python.
format_python() {
  local _files
  mapfile -t _files < <(files_of .py)

  heading_print ruff
  if [ "${#_files[@]}" = 0 ]; then
    log_verbose "ruff: no files"
    return 0
  fi

  # --quiet prints diagnostics and nothing else: no good news unless
  # --verbose, when ruff's own summary line streams like any child's
  quiet_switch_set ruff
  if [ "$_CHECK" = 1 ]; then
    subprocess_run "$_RUFF" format --config "$_RUFF_CONFIG" \
      "${QUIET_SWITCH[@]}" --diff "${_files[@]}"
  else
    subprocess_run "$_RUFF" format --config "$_RUFF_CONFIG" \
      "${QUIET_SWITCH[@]}" "${_files[@]}"
  fi

  # check mode is plain "ruff check": --diff implies --fix-only, which
  # passes lints that have no fix (F821) and then fails the write run
  if [ "$_CHECK" = 1 ]; then
    subprocess_run "$_RUFF" check --config "$_RUFF_CONFIG" \
      "${QUIET_SWITCH[@]}" "${_files[@]}"
  else
    subprocess_run "$_RUFF" check --config "$_RUFF_CONFIG" \
      "${QUIET_SWITCH[@]}" --fix "${_files[@]}"
  fi
}

# format_c - clang-format over the whitelisted C, with src/'s own style.
format_c() {
  local _files
  mapfile -t _files < <(files_of .c .h)

  heading_print clang-format
  if [ "${#_files[@]}" = 0 ]; then
    log_verbose "clang-format: no files"
    return 0
  fi

  if [ "$_CHECK" = 1 ]; then
    subprocess_run "$_CLANG_FORMAT" --style=file:"$_CLANG_FORMAT_CONFIG" \
      --dry-run --Werror "${_files[@]}"
  else
    subprocess_run "$_CLANG_FORMAT" --style=file:"$_CLANG_FORMAT_CONFIG" \
      -i "${_files[@]}"
  fi
}

# format_prettier - every whitelisted markdown file and page asset. prettier
# reparses what it writes, so it is these kinds' lint as well.
format_prettier() {
  local _files
  mapfile -t _files < <(files_of .md .js .css .html)

  heading_print prettier
  if [ "${#_files[@]}" = 0 ]; then
    log_verbose "prettier: no files"
    return 0
  fi

  # at log level warn prettier names no file it formatted: no good news
  # unless --verbose, when its per-file lines stream like any child's
  quiet_switch_set prettier
  if [ "$_CHECK" = 1 ]; then
    subprocess_run "$_PRETTIER" --config "$_PRETTIER_CONFIG" \
      "${QUIET_SWITCH[@]}" --check "${_files[@]}"
  else
    subprocess_run "$_PRETTIER" --config "$_PRETTIER_CONFIG" \
      "${QUIET_SWITCH[@]}" --write "${_files[@]}"
  fi
}

# lint_run - pyright over the whitelisted python. pyrightconfig.json names
# no files: the ones given here, from the whitelist, are its whole list.
lint_run() {
  local _files
  mapfile -t _files < <(files_of .py)

  heading_print pyright
  # named no file, pyright would check its whole project directory instead
  if [ "${#_files[@]}" = 0 ]; then
    log_verbose "pyright: no files"
    return 0
  fi

  # pyright has no quiet switch: a quiet run prints its all-clear summary on
  # stdout, the one success line left; --verbose pipes it out
  if [ "$VERBOSE" -ge 1 ]; then
    pyright_filtered_run "$_PYRIGHT" --project "$_PYRIGHT_CONFIG" \
      "${_files[@]}"
  else
    subprocess_run "$_PYRIGHT" --project "$_PYRIGHT_CONFIG" "${_files[@]}"
  fi
}

# pyright_filtered_run - the pyright command given, its stdout through
# grep -v, the user's one exception to this script reformatting no output.
pyright_filtered_run() {
  local _statuses=(0 0)
  local _filter=(grep --line-buffered -v -x)
  local _filter_shown="${_filter[*]} '$_PYRIGHT_ALL_CLEAR_LINE'"
  command_item_print "$* | $_filter_shown"
  "$@" | "${_filter[@]}" "$_PYRIGHT_ALL_CLEAR_LINE" \
    || _statuses=("${PIPESTATUS[@]}")
  # pyright's code is the verdict; grep's 1 only says it printed nothing
  [ "${_statuses[0]}" = 0 ] || error_exit "${_statuses[0]}" \
    "error: exit ${_statuses[0]} from: $*"
  [ "${_statuses[1]}" -le 1 ] || error_exit "${_statuses[1]}" \
    "error: exit ${_statuses[1]} from: $_filter_shown"
}

# long_lines_report - fail on any whitelisted line still over _COLUMNS_MAX
# once the formatters have run.
long_lines_report() {
  local _over _count
  _over="$(awk -v max="$_COLUMNS_MAX" \
    'length > max { print FILENAME ":" FNR ": " length " cols\n  " $0 }' \
    "${_WHITELISTED_FILES[@]}")"

  if [ -z "$_over" ]; then
    log_verbose "columns: none over $_COLUMNS_MAX"
    return 0
  fi

  _count="$(echo "$_over" | grep -c ' cols$')"
  error_exit 1 "error: $_count line(s) over $_COLUMNS_MAX columns:" "$_over"
}

# report_version - line 1 of a report's MANIFEST.txt, once manifest_verify
# has proved it is one.
report_version() {
  head -n 1 "$1/MANIFEST.txt"
}

# test_expected_report_check_run - check each report the batch wrote, in
# its order. Every one must be there: the batch stops at its first failure.
test_expected_report_check_run() {
  local _path _args _flags=()
  mapfile -t _flags < <(verbose_flags_of)

  heading_print test_report.py
  for _path in "${_DEFAULT_REPORTS[@]}"; do
    # utility.sh's hard-error policy, taking both version strings so either
    # kind of report is accepted and anything else stops the run
    manifest_verify "$_path" "$(basename "$_path")" \
      "$REPORT_MANIFEST_VERSION_FULL" "$REPORT_MANIFEST_VERSION_DIFF"

    _args=("$(cd "$_path" && pwd)")
    if [ "$(report_version "$_path")" = "$REPORT_MANIFEST_VERSION_DIFF" ]; then
      _args+=(--diff)
    fi

    subprocess_run python3 test_report.py "${_flags[@]}" "${_args[@]}"
  done
}

# test_expected_archive_check_run - read back every archive --txz wrote,
# through the one extraction door that every reader of one goes through.
test_expected_archive_check_run() {
  local _path _archive _root _name _extracted

  heading_print "$REPORT_RAW_ARCHIVE_SUFFIX archives"

  # one mktemp -d for this check, authorized for archive extraction, holding
  # every report read back and removed whole below
  _root="$(mktemp -d)" || error_exit 1 \
    "error: mktemp could not make the archive check directory"

  for _path in "${_DEFAULT_REPORTS[@]}"; do
    _name="$(basename "$_path")"
    _archive="$_path$REPORT_RAW_ARCHIVE_SUFFIX"
    [ -f "$_archive" ] || error_exit 1 \
      "error: --txz wrote no archive for $_name: $_archive"

    # the extracted copy is a report or nothing: manifest_verify is the one
    # door, so a truncated or mis-rooted archive stops the run here
    _extracted="$(archive_extract "$_archive" "$_name" "$_root")"
    manifest_verify "$_extracted" "$_name" \
      "$REPORT_MANIFEST_VERSION_FULL" "$REPORT_MANIFEST_VERSION_DIFF"
    log_verbose "$_archive -> $_extracted"
  done

  rm -rf "$_root" || error_exit 1 \
    "error: could not remove the archive check directory: $_root"
}

# test_source_scan_run - test_source_scan.py's comment block, ASCII and
# tag checks, over every whitelisted file and in one read of each.
test_source_scan_run() {
  local _flags=()
  mapfile -t _flags < <(verbose_flags_of)

  # the limit and the allowed set are the scanner's own and never spelled
  # here: every fault it prints, and its --verbose ok line, carry them
  heading_print test_source_scan.py
  subprocess_run python3 test_source_scan.py "${_flags[@]}" \
    "${_WHITELISTED_FILES[@]}"
}

# batch_run - write the three reports this run verifies. Its own steps stop
# at their first failure, and so does this: there is nothing left to check.
batch_run() {
  local _flags=() _target _shown _exit_code=0
  mapfile -t _flags < <(verbose_flags_of)
  _target="$(cd "$_DIR_DEV" && pwd)"

  # regenerate_check held this back unless the recordings still describe the
  # executable, so the batch is never asked to reuse a stale one
  if [ "$_REGENERATE" = 1 ]; then _flags+=(--regenerate); fi

  # a measuring run that keeps its recordings is what a later --regenerate
  # reuses, and the batch owns every deletion of them
  if [ "$_KEEP_ARTIFACTS" = 1 ]; then _flags+=(--keep-artifacts); fi

  # every run writes the archives too, so the suite verifies the writer and
  # test_expected_archive_check_run has an archive of each report to read
  _flags+=(--txz)
  _shown="$_BATCH_SCRIPT_NAME ${_flags[*]} --target-dir=$_target"

  # a paragraph of its own: the batch's first line is its title, which a
  # parent leads with a blank line
  log_verbose "$_shown"

  # a plain child, nothing captured: its lines reach the terminal as they
  # are, and a failed batch has printed its own refusal before this one
  "$_DIR_DEV/$_BATCH_SCRIPT_NAME" "${_flags[@]}" "--target-dir=$_target" \
    || _exit_code=$?
  [ "$_exit_code" = 0 ] \
    || error_exit "$_exit_code" "error: exit $_exit_code from: $_shown"
}

# screenshots_run - shoot the modified and diff reports at every viewport
# test_screenshot.py names. Both exist: the batch wrote them or exited.
screenshots_run() {
  local _name _path _prefix _flags=()
  mapfile -t _flags < <(verbose_flags_of)

  heading_print "$_SCREENSHOT_SCRIPT_NAME"
  for _name in "$REPORT_MODIFIED_DIR_NAME" "$REPORT_DIFF_DIR_NAME"; do
    _path="$_DIR_DEV/$_name"

    # perf2html_modified_report -> modified_, the prefix naming which of the
    # two a file came from and nothing else
    _prefix="${_name#perf2html_}"
    _prefix="${_prefix%_report}_"

    subprocess_run python3 "$_SCREENSHOT_SCRIPT_NAME" "${_flags[@]}" \
      "$_path" "$_prefix"
  done
}

# regenerate_refuse - say why the recordings cannot be reused and stop. The
# flag is the developer loop, and measuring instead costs an hour nobody asked
regenerate_refuse() {
  error_exit 2 "error: --regenerate cannot reuse the recordings: $1"
}

# header_row_of - one LABEL= row of a measuring run's header rows file.
header_row_of() {
  sed -n "s/^$2=//p" "$1" | head -1
}

# regenerate_check - reuse the last run's recordings only while they still
# describe the executable on disk, else refuse.
regenerate_check() {
  [ "$_REGENERATE" = 1 ] || return 0

  # the artifacts dir the batch defaults to, one subdirectory of recordings
  # per report; the reports themselves are output
  local _artifacts="$_DIR_DEV/$ARTIFACTS_NAME"
  if [ ! -d "$_artifacts" ]; then
    regenerate_refuse "no recordings at $_artifacts"
  fi

  # each measuring run left its rows in its report's subdirectory: recorded=
  # names its recordings, executable= its tree. The diff has neither.
  local _name _report_artifacts _rows _recorded _binary _newest
  local _timing_files=() _recorded_times=()
  for _name in "$REPORT_BASELINE_DIR_NAME" "$REPORT_MODIFIED_DIR_NAME"; do
    _report_artifacts="$_artifacts/$_name"
    if [ ! -d "$_report_artifacts" ]; then
      regenerate_refuse "$_name has no recordings at $_report_artifacts"
    fi
    _rows="$_report_artifacts/$HEADER_ROWS_NAME.$_name.txt"
    if [ ! -f "$_rows" ]; then
      regenerate_refuse "$_name has no recordings, $_rows is missing"
    fi

    # the row carries a human date after the unix time, and an artifact is
    # named by the unix time alone, so the tail must not reach a find glob
    _recorded="$(header_row_of "$_rows" recorded)"
    _recorded="${_recorded%% *}"
    if [ -z "$_recorded" ]; then
      regenerate_refuse "$_name records no recorded= row in $_rows"
    fi

    # one timing recording dates the pass: perf2html.sh checks for every
    # file it wants, per test, before it reuses any of them
    mapfile -t _timing_files < <(find "$_report_artifacts" -maxdepth 1 \
      -type f -name "$PROFILE_TIMING_FILE_PREFIX.*.$_recorded.csv" | sort)
    if [ "${#_timing_files[@]}" = 0 ]; then
      regenerate_refuse "$_name has no recordings left from $_recorded"
    fi
    _recorded_times+=("$_recorded")

    _binary="$(header_row_of "$_rows" executable)"
    if [ -z "$_binary" ]; then
      regenerate_refuse "$_name records no executable= row in $_rows"
    fi
    _binary="$_DIR_REPO/${_binary%% *}"
    if [ ! -f "$_binary" ]; then
      regenerate_refuse "$_name has no executable at $_binary"
    fi

    # a recording written in the link's own second is still that link's, so
    # only a strictly newer binary means perf was re-linked after them
    _newest="$(find "$_report_artifacts" -maxdepth 1 -type f \
      -name "$PROFILE_TIMING_FILE_PREFIX.*.$_recorded.csv" \
      -printf '%T@ %p\n' | sort -rn | head -1)"
    _newest="${_newest#* }"
    if [ -n "$(find "$_binary" -newer "$_newest" -print -quit)" ]; then
      regenerate_refuse "$_name: perf was re-linked after its recordings"
    fi
  done

  log_verbose "regenerate: reusing the runs recorded at" \
    "${_recorded_times[0]} and ${_recorded_times[1]}"
}

# clear_overwritten_folders - delete the three reports before anything runs, so
# every stage below reads this run's output and never a previous one's.
clear_overwritten_folders() {
  # the artifacts directory is not ours to delete: the batch owns every
  # deletion of it, and being flagless below is what makes it do one
  local _path _archive

  for _path in "${_DEFAULT_REPORTS[@]}"; do
    rm -rf "$_path" \
      || error_exit 1 "error: could not remove the previous report: $_path"

    # --txz names the archive after the report, so that archive is this
    # run's output too and never a previous run's left beside a new report
    _archive="$_path$REPORT_RAW_ARCHIVE_SUFFIX"
    rm -f "$_archive" || error_exit 1 \
      "error: could not remove the previous archive: $_archive"
  done
  log_verbose "cleared ${#_DEFAULT_REPORTS[@]} report(s)"
}

# args_parse - read the flags. There is no report argument: this runs the
# batch, and the batch writes the three default names and no others.
args_parse() {
  _CHECK=0
  _KEEP_ARTIFACTS=0
  _REGENERATE=0

  while [ $# -gt 0 ]; do
    case "$1" in
      -h | --help)
        usage_show
        exit 0
        ;;
      --check-formatting)
        _CHECK=1
        shift
        ;;
      --keep-artifacts)
        _KEEP_ARTIFACTS=1
        shift
        ;;
      --regenerate)
        _REGENERATE=1
        shift
        ;;
      --verbose)
        VERBOSE=$((VERBOSE + 1))
        shift
        ;;
      *)
        error_exit 2 "error: unknown option: $1"
        ;;
    esac
  done
}

# main - Timing data is temporary.
main() {
  # read the flags: -h prints the usage, an unknown one refuses
  args_parse "$@"
  # start the run's one clock, which the batch inherits, and the header depth
  verbose_begin
  # the run's own heading: this script's path and its arguments
  title_print "$_SCRIPT" "$@"
  # expand test_whitelist.txt once into _WHITELISTED_FILES
  whitelist_expand
  # 0.07s under --regenerate only.
  regenerate_check
  # find every formatter and linter, before anything is deleted or written
  tools_resolve
  # delete the three reports: every stage below reads this run's output
  clear_overwritten_folders
  # 0.02s shfmt over shell
  format_shell
  # 0.04s Ruff over Python
  format_python
  # 0.03s clang-format over C
  format_c
  # 0.61s prettier over .md, .js, .css and .html
  format_prettier
  # 0.01s 79 column check
  long_lines_report
  # 0.04s test_source_scan.py check comment sizes, ASCII and tags.
  test_source_scan_run
  # 2.61s Pyright over the Python
  lint_run
  # [100.35/97.42/12.01s] perf2html_batch.sh: baseline, modified and diff,
  # under dev/
  batch_run
  # 0.59s test_report.py over each of the three reports
  test_expected_report_check_run
  # 0.80s read back every --txz archive the batch wrote
  test_expected_archive_check_run
  # 40.40s test_screenshot.py over the modified and diff reports
  screenshots_run
}

main "$@"
