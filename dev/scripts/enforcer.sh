#!/usr/bin/env bash

#   source          format        lint           79 cols ascii
#   --------------- ------------- -------------- ------- ------
#   *.sh            shfmt         --             yes     yes
#   README.md       prettier      prettier       yes     yes
#   src/*.c *.h     clang-format  --             yes     yes
#   scripts/*.py    ruff          pyright, ruff  yes     yes
#   scripts/*.js    prettier      prettier       yes     yes
#   scripts/*.css   prettier      prettier       yes     yes
#   scripts/*.html  prettier      prettier       yes     yes
#
# The rest of this comment is intentionally blank. No documentation goes here.

set -euo pipefail

usage_show() {
  cat <<'EOF'
enforcer.sh [debug-flags] [--check-formatting]
    Formats, lints and scans the files scripts/enforcer_whitelist.txt lists,
    runs perf2html_batch.sh over the three reports it cleared, then
    validates and screenshots what it wrote. Any fault stops the run where
    it happened.
    --check-formatting  Report what would change rather than writing it.

  These are the same debug-flags as the README.md documents:
    --keep-artifacts    Measure as usual, but keep the recordings afterwards,
                        which is what a later --regenerate reuses. Flagless
                        runs delete them.
    --regenerate        Rebuild the three reports' pages from the last run's
                        recordings, re-measuring nothing. Pass it after every
                        dev/ edit; leave it off once perf has been re-linked.
                        Recordings that no longer describe the executable are
                        a hard error: re-run without the flag to measure.
    --verbose           Enables diagnostic information. Repeating it (--verbose
                        --verbose) increments the verbosity level.
EOF
}

_SCRIPT="$(readlink -f "$0")"
_SCRIPTS="$(dirname "$_SCRIPT")"

# Where the caller stood. This takes no path argument of its own, but
# shared.sh's absolute_path reads it, so it is set before the cd below.
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

# spaces shfmt indents a shell block by
_SHELL_INDENT=2
_RUFF_CONFIG=ruff.toml

# the one list of what the source stages touch, beside this script
_WHITELIST_FILE=enforcer_whitelist.txt

. ./settings.sh
. ./shared.sh

# The batch this runs, and the shooter it runs after, each beside us.
_BATCH_SCRIPT_NAME=perf2html_batch.sh
_SCREENSHOTS_SCRIPT_NAME=screenshots.py

# The reports the batch writes, in the order it writes them. The names are
# the batch's own settings, so this agrees with it by construction.
_DEFAULT_REPORTS=(
  "$_DIR_DEV/$REPORT_BASELINE_DIR_NAME"
  "$_DIR_DEV/$REPORT_MODIFIED_DIR_NAME"
  "$_DIR_DEV/$REPORT_DIFF_DIR_NAME"
)

# the headings of the stage table every row below sits in
_STAGE_TABLE_HEADINGS=('#' stage result detail)

# counts the stage rows printed, the number leading each row
_STAGE_NUMBER=0

# tool_find - echo a tool's path, searching the pip and npm user bins too.
tool_find() {
  local _name="$1" _found

  for _found in "$_name" "$HOME/.local/bin/$_name" \
    "$HOME/.npm-global/bin/$_name"; do
    if command -v "$_found" >/dev/null 2>&1; then
      echo "$_found"
      return 0
    fi
  done

  return 1
}

# child_stream - run one child, streaming it live as rows of the stage table.
# SETS STAGE_EXIT_CODE and STAGE_OUTPUT. Never $( ): that buffers the child.
child_stream() {
  # args: the row's stage label, then the command
  local _label="$1" _log _statuses=() _status
  shift
  _log="$(mktemp)"
  STAGE_EXIT_CODE=0

  # the tee is chosen before the child starts, so verbose watches the work
  # happen rather than reading it replayed once the child has exited
  if [ "$VERBOSE" -ge 1 ]; then
    if ! { "$@" 2>&1 | tee "$_log" | verbose_filter row "$_label"; }; then
      _statuses=("${PIPESTATUS[@]}")
    fi
  elif ! { "$@" 2>&1 | tee "$_log" >/dev/null; }; then
    _statuses=("${PIPESTATUS[@]}")
  fi

  STAGE_OUTPUT="$(cat "$_log")"
  rm -f "$_log"
  [ "${#_statuses[@]}" != 0 ] || return 0
  STAGE_EXIT_CODE="${_statuses[0]}"
  for _status in "${_statuses[@]:1}"; do
    [ "$_status" = 0 ] || error_exit 1 \
      "error: tee or verbose_filter exited $_status behind: $*"
  done
}

# stage_row_print - one stage's row of the table, numbered on: label,
# verdict, detail.
stage_row_print() {
  _STAGE_NUMBER=$((_STAGE_NUMBER + 1))
  table_row_print "$_STAGE_NUMBER" "$1" "$2" "$3"
}

# stage_row_fail - a failed stage's row, on stderr whatever the verbosity:
# it is the verdict a reader acts on.
stage_row_fail() {
  _STAGE_NUMBER=$((_STAGE_NUMBER + 1))
  printf '\n| %s | %s | %s | %s |\n' "$_STAGE_NUMBER" "$1" "$2" "$3" \
    | verbose_filter paths >&2
}

# stage_fail - print one stage's verdict and output, then stop the run. The
# first fault is the one a reader must act on, so nothing follows it.
stage_fail() {
  local _label="$1" _verdict="$2" _summary="$3" _output="$4"

  stage_row_fail "$_label" "$_verdict" "$_summary"
  [ -n "$_output" ] || _output="$_label: $_verdict, and it printed nothing"
  error_exit 1 "$_output"
}

# tool_missing_fail - a tool that is not installed never checked its files,
# so the run is not a verification and stops here with how to install it.
tool_missing_fail() {
  local _label="$1" _name="$2"

  stage_row_fail "$_label" MISSING "not installed: $_name"
  error_exit 1 "error: $_name is not installed, so $_label never ran" \
    "  sudo apt-get install -y shfmt clang-format" \
    "  pip3 install --user --break-system-packages ruff" \
    "  npm install -g prettier pyright"
}

# tool_run - run one tool with _TOOL_ARGS over the files, printing a status
# row. Any fault at all stops the run where it happened.
tool_run() {
  local _name="$1" _label="$2"
  shift 2
  local _binary

  if ! _binary="$(tool_find "$_name")"; then
    tool_missing_fail "$_label" "$_name"
  fi

  if [ "$#" = 0 ]; then
    stage_row_print "$_label" ok "no files"
    return 0
  fi

  child_stream "$_label" "$_binary" "${_TOOL_ARGS[@]}" "$@"

  if [ "$STAGE_EXIT_CODE" = 0 ]; then
    stage_row_print "$_label" ok "$# file(s)"
    return 0
  fi

  stage_fail "$_label" CHANGED "$(echo "$STAGE_OUTPUT" | head -n 1)" \
    "$STAGE_OUTPUT"
}

# whitelist_refuse - say why the whitelist cannot be enforced and stop.
whitelist_refuse() {
  error_exit 1 "error: $_WHITELIST_FILE: $1"
}

# whitelist_expand - expand _WHITELIST_FILE's globs against dev/, once. SETS
# _WHITELISTED_FILES, its canonical setter, sorted and without repeats.
whitelist_expand() {
  local _glob _match _line=0 _found=() _matches=()

  if [ ! -f "$_WHITELIST_FILE" ]; then
    whitelist_refuse "not found beside enforcer.sh, so nothing is enforced"
  fi

  while IFS= read -r _glob || [ -n "$_glob" ]; do
    _line=$((_line + 1))
    if [[ -z "$_glob" || "$_glob" == '#'* || "$_glob" == *[[:space:]]* ]]; then
      whitelist_refuse "line $_line is not one glob: '$_glob'"
    fi

    # a tool handed a directory walks it, which is what this list replaces
    mapfile -t _matches < <(compgen -G "$_DIR_DEV/$_glob")
    for _match in "${_matches[@]}"; do
      if [ ! -f "$_match" ]; then
        whitelist_refuse "line $_line, $_glob, matches $_match, not a file"
      fi
    done
    _found+=("${_matches[@]}")
  done <"$_WHITELIST_FILE"

  if [ "${#_found[@]}" = 0 ]; then
    whitelist_refuse "matches no file, so nothing would be enforced"
  fi

  mapfile -t _WHITELISTED_FILES < <(printf '%s\n' "${_found[@]}" \
    | LC_ALL=C sort -u)
  stage_row_print whitelist ok "${#_WHITELISTED_FILES[@]} file(s)"
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

format_shell() {
  local _files
  mapfile -t _files < <(files_of .sh)

  _TOOL_ARGS=(-i "$_SHELL_INDENT" -bn -ci -ln bash)
  if [ "$_CHECK" = 1 ]; then
    _TOOL_ARGS+=(-d)
  else
    _TOOL_ARGS+=(-w)
  fi

  tool_run shfmt shell "${_files[@]}"
}

format_python() {
  local _files
  mapfile -t _files < <(files_of .py)

  _TOOL_ARGS=(format --config "$_RUFF_CONFIG")
  if [ "$_CHECK" = 1 ]; then _TOOL_ARGS+=(--diff); fi
  tool_run ruff python "${_files[@]}"

  # check mode is plain "ruff check": --diff implies --fix-only, which
  # passes lints that have no fix (F821) and then fails the write run
  _TOOL_ARGS=(check --config "$_RUFF_CONFIG")
  if [ "$_CHECK" != 1 ]; then _TOOL_ARGS+=(--fix); fi
  tool_run ruff "python lint" "${_files[@]}"
}

format_c() {
  local _files
  mapfile -t _files < <(files_of .c .h)

  _TOOL_ARGS=(--style=file:"$_CLANG_FORMAT_CONFIG")
  if [ "$_CHECK" = 1 ]; then
    _TOOL_ARGS+=(--dry-run --Werror)
  else
    _TOOL_ARGS+=(-i)
  fi

  tool_run clang-format c "${_files[@]}"
}

# format_prettier - every whitelisted markdown file and page asset. prettier
# reparses what it writes, so it is these kinds' lint as well.
format_prettier() {
  local _files
  mapfile -t _files < <(files_of .md .js .css .html)

  _TOOL_ARGS=(--config "$_PRETTIER_CONFIG" --log-level warn)
  if [ "$_CHECK" = 1 ]; then
    _TOOL_ARGS+=(--check)
  else
    _TOOL_ARGS+=(--write)
  fi

  tool_run prettier prettier "${_files[@]}"
}

# pyright over the whitelisted generators. pyrightconfig.json names no
# files: the ones given here, from the whitelist, are pyright's whole list.
lint_run() {
  local _binary _files
  mapfile -t _files < <(files_of .py)

  if ! _binary="$(tool_find pyright)"; then
    tool_missing_fail lint pyright
  fi

  # named no file, pyright would check its whole project directory instead
  if [ "${#_files[@]}" = 0 ]; then
    stage_row_print lint ok "no files"
    return 0
  fi

  child_stream lint "$_binary" --project "$_PYRIGHT_CONFIG" "${_files[@]}"

  if [ "$STAGE_EXIT_CODE" = 0 ]; then
    stage_row_print lint ok pyright
    return 0
  fi

  stage_fail lint FAILED pyright "$STAGE_OUTPUT"
}

# long_lines_report - fail on any whitelisted line still over _COLUMNS_MAX
# once the formatters have run.
long_lines_report() {
  local _over
  _over="$(awk -v max="$_COLUMNS_MAX" \
    'length > max { print FILENAME ":" FNR ": " length " cols\n  " $0 }' \
    "${_WHITELISTED_FILES[@]}")"

  if [ -z "$_over" ]; then
    stage_row_print columns ok "none over $_COLUMNS_MAX"
    return 0
  fi

  stage_fail columns TOO_LONG \
    "$(echo "$_over" | grep -c ' cols$') line(s) over $_COLUMNS_MAX" "$_over"
}

# Line 1 of a directory's MANIFEST.txt, which manifest_verify has proved.
report_version() {
  head -n 1 "$1/MANIFEST.txt"
}

# validate_run - validate each report the batch wrote, in its order. Every
# one must be there: the batch stops at its first failure, so all three are.
validate_run() {
  local _path _args _output _exit_code

  for _path in "${_DEFAULT_REPORTS[@]}"; do
    # shared.sh's hard-error policy, taking both version strings so either
    # kind of report is accepted and anything else stops the run
    manifest_verify "$_path" "$(basename "$_path")" \
      "$REPORT_MANIFEST_VERSION_FULL" "$REPORT_MANIFEST_VERSION_DIFF"

    _args=("$(cd "$_path" && pwd)")
    if [ "$(report_version "$_path")" = "$REPORT_MANIFEST_VERSION_DIFF" ]; then
      _args+=(--diff)
    fi

    child_stream validate python3 validate_report.py "${_args[@]}"

    if [ "$STAGE_EXIT_CODE" = 0 ]; then
      stage_row_print validate ok "$(basename "$_path")"
      continue
    fi

    stage_fail validate FAILED "$(basename "$_path")" "$STAGE_OUTPUT"
  done
}

# source_scan_run - source_scan.py's comment block and ASCII checks, over
# every whitelisted file and in one read of each.
source_scan_run() {
  child_stream "source scan" python3 source_scan.py "${_WHITELISTED_FILES[@]}"

  # the limit and the allowed set are the scanner's own and never spelled
  # here: its ok line and every fault it prints carry them
  if [ "$STAGE_EXIT_CODE" = 0 ]; then
    stage_row_print "source scan" ok "$STAGE_OUTPUT"
    return 0
  fi

  stage_fail "source scan" FAILED "$(echo "$STAGE_OUTPUT" | head -n 1)" \
    "$STAGE_OUTPUT"
}

# batch_run - write the three reports this run verifies. Its own steps stop
# at their first failure, and so does this: there is nothing left to check.
batch_run() {
  local _flags=()
  mapfile -t _flags < <(verbose_flags_of)

  # regenerate_check held this back unless the recordings still describe the
  # executable, so the batch is never asked to reuse a stale one
  if [ "$_REGENERATE" = 1 ]; then _flags+=(--regenerate); fi

  # a measuring run that keeps its recordings is what a later --regenerate
  # reuses, and the batch owns every deletion of them
  if [ "$_KEEP_ARTIFACTS" = 1 ]; then _flags+=(--keep-artifacts); fi

  # our own script: its lines are already formatted and relayed as they are,
  # and on failure its report climbs through failure_relay
  script_capture "$_DIR_DEV/$_BATCH_SCRIPT_NAME" "${_flags[@]}" \
    "--target-dir=$(cd "$_DIR_DEV" && pwd)"

  if [ "$CHILD_EXIT_CODE" = 0 ]; then
    heading_print "$_SCRIPT, after the batch"
    table_head_print "${_STAGE_TABLE_HEADINGS[@]}"
    stage_row_print batch ok "$_BATCH_SCRIPT_NAME"
    return 0
  fi

  stage_row_fail batch FAILED "$_BATCH_SCRIPT_NAME"
  failure_relay
  exit 1
}

# screenshots_run - shoot the modified and diff reports at every viewport
# screenshots.py names. Both exist: the batch wrote them or exited.
screenshots_run() {
  local _name _path _prefix

  for _name in "$REPORT_MODIFIED_DIR_NAME" "$REPORT_DIFF_DIR_NAME"; do
    _path="$_DIR_DEV/$_name"

    # perf2html_modified_report -> modified_, the prefix naming which of the
    # two a file came from and nothing else
    _prefix="${_name#perf2html_}"
    _prefix="${_prefix%_report}_"

    child_stream screenshots python3 "$_SCREENSHOTS_SCRIPT_NAME" "$_path" \
      "$_prefix"

    if [ "$STAGE_EXIT_CODE" = 0 ]; then
      stage_row_print screenshots ok "$_name"
      continue
    fi

    stage_fail screenshots FAILED "$_name" "$STAGE_OUTPUT"
  done
}

# regenerate_refuse - say why the recordings cannot be reused and stop. The
# flag is the developer loop, and measuring instead costs an hour nobody asked
regenerate_refuse() {
  error_exit 2 "error: --regenerate cannot reuse the recordings: $1" \
    "       re-run without --regenerate to measure from scratch"
}

# regenerate_stamp_of - echo one report's unix stamp, or exit 1 having echoed
# why it has none. The caller withdraws on that reason, so neither prints here.
regenerate_stamp_of() {
  local _path="$1" _name _stamp
  _name="$(basename "$_path")"

  if [ ! -f "$_path/MANIFEST.txt" ]; then
    echo "$_name is not a finished report"
    return 1
  fi

  # the row carries a human date after the unix time, and an artifact is
  # named by the unix time alone, so the tail must not reach a find glob
  _stamp="$(manifest_value "$_path" stamp)"
  _stamp="${_stamp%% *}"
  if [ -z "$_stamp" ]; then
    echo "$_name records no stamp= row"
    return 1
  fi
  echo "$_stamp"
}

# regenerate_check - reuse the last run's recordings only while they still
# describe the executable on disk, else refuse. See DECLAUDE.md 3.
regenerate_check() {
  [ "$_REGENERATE" = 1 ] || return 0

  # all three are this run's input, and manifest_verify is the one policy
  # saying why one is not a report -- it exits, so this fails at the first
  local _name
  manifest_verify "$_DIR_DEV/$REPORT_BASELINE_DIR_NAME" \
    "--regenerate input" "$REPORT_MANIFEST_VERSION_FULL"
  manifest_verify "$_DIR_DEV/$REPORT_MODIFIED_DIR_NAME" \
    "--regenerate input" "$REPORT_MANIFEST_VERSION_FULL"
  manifest_verify "$_DIR_DEV/$REPORT_DIFF_DIR_NAME" \
    "--regenerate input" "$REPORT_MANIFEST_VERSION_DIFF"

  # the artifacts dir the batch defaults to, holding every recording the
  # three reports were generated from
  local _artifacts="$_DIR_DEV/$ARTIFACTS_NAME"
  if [ ! -d "$_artifacts" ]; then
    regenerate_refuse "no recordings at $_artifacts"
  fi

  # each measured report names its own recordings by stamp and its own tree
  # by executable=. The diff has neither: it is subtracted from these two.
  local _stamp _binary _newest _recorded=() _stamps=()
  for _name in "$REPORT_BASELINE_DIR_NAME" "$REPORT_MODIFIED_DIR_NAME"; do
    if ! _stamp="$(regenerate_stamp_of "$_DIR_DEV/$_name")"; then
      regenerate_refuse "$_stamp"
    fi

    # one timing recording dates the pass: perf2html.sh checks for every
    # file it wants, per test, before it reuses any of them
    mapfile -t _recorded < <(find "$_artifacts" -maxdepth 1 -type f \
      -name "$PROFILE_TIMING_FILE_PREFIX.*.$_stamp.csv" | sort)
    if [ "${#_recorded[@]}" = 0 ]; then
      regenerate_refuse "$_name has no recordings left under stamp $_stamp"
    fi
    _stamps+=("$_stamp")

    _binary="$(manifest_value "$_DIR_DEV/$_name" executable)"
    if [ -z "$_binary" ]; then
      regenerate_refuse "$_name records no executable= row"
    fi
    _binary="$_DIR_REPO/${_binary%% *}"
    if [ ! -f "$_binary" ]; then
      regenerate_refuse "$_name has no executable at $_binary"
    fi

    # a recording written in the link's own second is still that link's, so
    # only a strictly newer binary means perf was re-linked after them
    _newest="$(find "$_artifacts" -maxdepth 1 -type f \
      -name "$PROFILE_TIMING_FILE_PREFIX.*.$_stamp.csv" \
      -printf '%T@ %p\n' | sort -rn | head -1)"
    _newest="${_newest#* }"
    if [ -n "$(find "$_binary" -newer "$_newest" -print -quit)" ]; then
      regenerate_refuse "$_name: perf was re-linked after its recordings"
    fi
  done

  stage_row_print regenerate ok \
    "reusing stamp ${_stamps[0]} and ${_stamps[1]}"
}

# clear_overwritten_folders - delete the three reports before anything runs, so
# every stage below reads this run's output and never a previous one's.
clear_overwritten_folders() {
  # the artifacts directory is not ours to delete: the batch owns every
  # deletion of it, and being flagless below is what makes it do one
  local _path

  # a regenerated run reads each report's manifest back for the stamp and
  # rows its pages are rebuilt from, so those reports are its input
  if [ "$_REGENERATE" = 1 ]; then
    stage_row_print surface ok "${#_DEFAULT_REPORTS[@]} report(s) reused"
    return 0
  fi

  for _path in "${_DEFAULT_REPORTS[@]}"; do
    rm -rf "$_path" \
      || error_exit 1 "error: could not remove the previous report: $_path"
  done
  stage_row_print surface ok "${#_DEFAULT_REPORTS[@]} report(s) cleared"
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
        error_exit 2 "unknown option: $1" "$(usage_show)"
        ;;
    esac
  done
}

# main - the stages in ascending cost, each one stopping the run where it
# fails, so the first fault a reader sees is the one that happened first.
main() {
  args_parse "$@"
  verbose_begin
  title_print "$_SCRIPT" "$@"

  # the batch's lines pass through this log on their way up, and a failed
  # batch is reprinted from it; no report keeps it, so it is a temporary
  RUN_LOG="$(mktemp)"
  trap 'rm -f "$RUN_LOG"' EXIT
  table_head_print "${_STAGE_TABLE_HEADINGS[@]}"

  # the cheapest input to prove, and proved before a report is read or
  # deleted: the one list every source stage below takes its files from
  whitelist_expand

  # before the clear, which reads its answer: a regenerated run's input is
  # the three reports themselves
  regenerate_check
  clear_overwritten_folders

  # dev/ source, seconds each and measuring nothing. A fault here would
  # otherwise be found after the profiling run, an hour further on
  format_shell
  format_python
  format_c
  format_prettier
  long_lines_report
  source_scan_run
  lint_run

  # the profiling run, which writes the three reports, then what they hold
  batch_run
  validate_run
  screenshots_run
}

main "$@"
