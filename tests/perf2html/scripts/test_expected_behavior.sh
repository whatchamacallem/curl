#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.
#
# This comment intentionally blank. No documentation goes here.

usage_show() {
  cat <<'EOF'
test_expected_behavior.sh [debug-flags] [--check-formatting]
    Formats, lints and scans the files scripts/test_whitelist.txt lists,
    runs perf2html_batch.sh over the three reports it cleared, then
    validates and screenshots what it wrote. When screenshots-gold/
    exists, each shot is compared with its same named gold shot and a
    compare_ image of each difference goes to screenshots-diff/, which
    every run clears and only a difference makes. Any fault stops the run
    where it happened.
    --check-formatting  Report what would change rather than writing it.

    The debug-flags are the same as the README.md documents.
EOF
}

set -euo pipefail

_SCRIPT="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
_SCRIPTS="$(dirname "$_SCRIPT")"

INVOKED_FROM="$PWD"
cd "$_SCRIPTS"

_DIR_PERF2HTML=..
_DIR_REPO="$(cd ../../.. && pwd)"

_COLUMNS_MAX=79
_CLANG_FORMAT_CONFIG=../src/.clang-format
_PRETTIER_CONFIG=.prettierrc.json
_PYRIGHT_CONFIG=pyrightconfig.json

_PYRIGHT_ALL_CLEAR_LINE='0 errors, 0 warnings, 0 informations'

_SHELL_INDENT=2
_RUFF_CONFIG=ruff.toml

_WHITELIST_FILE=test_whitelist.txt

. ./settings.sh
. ./utility.sh
. ./test_utility.sh

_BATCH_SCRIPT_NAME=perf2html_batch.sh
_SCREENSHOT_DIFF_DIR="$_DIR_PERF2HTML/screenshots-diff"
_SCREENSHOT_GOLD_DIR="$_DIR_PERF2HTML/screenshots-gold"
_SCREENSHOT_SCRIPT_NAME=test_screenshot.py

_DEFAULT_REPORTS=(
  "$_DIR_PERF2HTML/$REPORT_BASELINE_DIR_NAME"
  "$_DIR_PERF2HTML/$REPORT_MODIFIED_DIR_NAME"
  "$_DIR_PERF2HTML/$REPORT_DIFF_DIR_NAME"
)

tools_resolve() {
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

subprocess_run() {
  local _exit_code=0
  command_item_print "$*"
  "$@" || _exit_code=$?
  [ "$_exit_code" = 0 ] \
    || error_exit "$_exit_code" "error: exit $_exit_code from: $*"
}

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

    mapfile -t _matches < <(compgen -G "$_DIR_PERF2HTML/$_glob")
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

format_python() {
  local _files
  mapfile -t _files < <(files_of .py)

  heading_print ruff
  if [ "${#_files[@]}" = 0 ]; then
    log_verbose "ruff: no files"
    return 0
  fi

  quiet_switch_set ruff
  if [ "$_CHECK" = 1 ]; then
    subprocess_run "$_RUFF" format --config "$_RUFF_CONFIG" \
      "${QUIET_SWITCH[@]}" --diff "${_files[@]}"
  else
    subprocess_run "$_RUFF" format --config "$_RUFF_CONFIG" \
      "${QUIET_SWITCH[@]}" "${_files[@]}"
  fi

  if [ "$_CHECK" = 1 ]; then
    subprocess_run "$_RUFF" check --config "$_RUFF_CONFIG" \
      "${QUIET_SWITCH[@]}" "${_files[@]}"
  else
    subprocess_run "$_RUFF" check --config "$_RUFF_CONFIG" \
      "${QUIET_SWITCH[@]}" --fix "${_files[@]}"
  fi
}

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

format_prettier() {
  local _files
  mapfile -t _files < <(files_of .md .js .css .html)

  heading_print prettier
  if [ "${#_files[@]}" = 0 ]; then
    log_verbose "prettier: no files"
    return 0
  fi

  quiet_switch_set prettier
  if [ "$_CHECK" = 1 ]; then
    subprocess_run "$_PRETTIER" --config "$_PRETTIER_CONFIG" \
      "${QUIET_SWITCH[@]}" --check "${_files[@]}"
  else
    subprocess_run "$_PRETTIER" --config "$_PRETTIER_CONFIG" \
      "${QUIET_SWITCH[@]}" --write "${_files[@]}"
  fi
}

lint_run() {
  local _files
  mapfile -t _files < <(files_of .py)

  heading_print pyright
  if [ "${#_files[@]}" = 0 ]; then
    log_verbose "pyright: no files"
    return 0
  fi

  if [ "$VERBOSE" -ge 1 ] && [ "$VERBOSE" -lt "$VERBOSE_RAW_LEVEL" ]; then
    pyright_filtered_run "$_PYRIGHT" --project "$_PYRIGHT_CONFIG" \
      "${_files[@]}"
  else
    subprocess_run "$_PYRIGHT" --project "$_PYRIGHT_CONFIG" "${_files[@]}"
  fi
}

pyright_filtered_run() {
  local _statuses=(0 0)
  local _filter=(grep --line-buffered -v -x)
  local _filter_shown="${_filter[*]} '$_PYRIGHT_ALL_CLEAR_LINE'"
  command_item_print "$* | $_filter_shown"
  "$@" | "${_filter[@]}" "$_PYRIGHT_ALL_CLEAR_LINE" \
    || _statuses=("${PIPESTATUS[@]}")
  [ "${_statuses[0]}" = 0 ] || error_exit "${_statuses[0]}" \
    "error: exit ${_statuses[0]} from: $*"
  [ "${_statuses[1]}" -le 1 ] || error_exit "${_statuses[1]}" \
    "error: exit ${_statuses[1]} from: $_filter_shown"
}

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

report_version() {
  head -n 1 "$1/MANIFEST.txt"
}

test_expected_report_check_run() {
  local _path _args _flags=()
  mapfile -t _flags < <(verbose_flags_of)

  heading_print test_report.py
  for _path in "${_DEFAULT_REPORTS[@]}"; do
    manifest_verify "$_path" "$(basename "$_path")" \
      "$REPORT_MANIFEST_VERSION_FULL" "$REPORT_MANIFEST_VERSION_DIFF"

    _args=("$(cd "$_path" && pwd)")
    if [ "$(report_version "$_path")" = "$REPORT_MANIFEST_VERSION_DIFF" ]; then
      _args+=(--diff)
    fi

    subprocess_run python3 "$_SCRIPTS/test_report.py" "${_flags[@]}" \
      "${_args[@]}"
  done
}

test_expected_archive_check_run() {
  local _path _archive _root _name _extracted

  heading_print "$REPORT_RAW_ARCHIVE_SUFFIX archives"

  _root="$(mktemp -d)" || error_exit 1 \
    "error: mktemp could not make the archive check directory"

  for _path in "${_DEFAULT_REPORTS[@]}"; do
    _name="$(basename "$_path")"
    _archive="$_path$REPORT_RAW_ARCHIVE_SUFFIX"
    [ -f "$_archive" ] || error_exit 1 \
      "error: --txz wrote no archive for $_name: $_archive"

    _extracted="$(archive_extract "$_archive" "$_name" "$_root")"
    manifest_verify "$_extracted" "$_name" \
      "$REPORT_MANIFEST_VERSION_FULL" "$REPORT_MANIFEST_VERSION_DIFF"
    log_verbose "$_archive -> $_extracted"
  done

  rm -rf "$_root" || error_exit 1 \
    "error: could not remove the archive check directory: $_root"
}

test_source_scan_run() {
  local _flags=()
  mapfile -t _flags < <(verbose_flags_of)

  heading_print test_source_scan.py
  subprocess_run python3 "$_SCRIPTS/test_source_scan.py" "${_flags[@]}" \
    "${_WHITELISTED_FILES[@]}"
}

batch_run() {
  local _flags=() _target _shown _exit_code=0
  mapfile -t _flags < <(verbose_flags_of)
  _target="$(cd "$_DIR_PERF2HTML" && pwd)"

  if [ "$_REGENERATE" = 1 ]; then _flags+=(--regenerate); fi

  if [ "$_KEEP_ARTIFACTS" = 1 ]; then _flags+=(--keep-artifacts); fi

  _flags+=(--txz)
  _shown="$_BATCH_SCRIPT_NAME ${_flags[*]} --target-dir=$_target"

  log_verbose "$_shown"

  "$_DIR_PERF2HTML/$_BATCH_SCRIPT_NAME" "${_flags[@]}" \
    "--target-dir=$_target" || _exit_code=$?
  [ "$_exit_code" = 0 ] \
    || error_exit "$_exit_code" "error: exit $_exit_code from: $_shown"
}

# Sets `_SCREENSHOT_COMMAND` to the screenshot script command for one report.
screenshot_command_set() {
  local _name="$1" _path _prefix _args _flags=()
  shift
  mapfile -t _flags < <(verbose_flags_of)
  _path="$_DIR_PERF2HTML/$_name"

  _prefix="${_name#perf2html_}"
  _prefix="${_prefix%_report}_"

  _args=("$_path" "$_prefix")
  if [ "$(report_version "$_path")" = "$REPORT_MANIFEST_VERSION_DIFF" ]; then
    _args+=(--diff)
  fi

  _SCREENSHOT_COMMAND=(python3 "$_SCRIPTS/$_SCREENSHOT_SCRIPT_NAME"
    "${_flags[@]}" "${_args[@]}" "$@")
}

screenshots_run() {
  local _name _exit_code _failure_code=0 _exit_codes=()

  heading_print "$_SCREENSHOT_SCRIPT_NAME"
  for _name in "$REPORT_MODIFIED_DIR_NAME" "$REPORT_DIFF_DIR_NAME"; do
    screenshot_command_set "$_name"
    subprocess_run "${_SCREENSHOT_COMMAND[@]}"
  done

  # A measuring run changes the recorded values the golden screenshots show.
  if [ "$_REGENERATE" != 1 ]; then
    log_verbose "screenshots: measured, not compared without --regenerate"
    return 0
  fi

  # The golden screenshots are a developer's own and optional.
  if [ -d "$_SCREENSHOT_GOLD_DIR" ]; then
    # Both reports are compared before either exit code fails the run.
    for _name in "$REPORT_MODIFIED_DIR_NAME" "$REPORT_DIFF_DIR_NAME"; do
      screenshot_command_set "$_name" --compare-only \
        --compare-gold "$_SCREENSHOT_GOLD_DIR" \
        --compare-out "$_SCREENSHOT_DIFF_DIR"
      _exit_code=0
      command_item_print "${_SCREENSHOT_COMMAND[*]}"
      "${_SCREENSHOT_COMMAND[@]}" || _exit_code=$?
      _exit_codes+=("$_name=$_exit_code")
      if [ "$_failure_code" = 0 ]; then
        _failure_code="$_exit_code"
      fi
    done
    [ "$_failure_code" = 0 ] || error_exit "$_failure_code" \
      "error: $_SCREENSHOT_SCRIPT_NAME exit codes: ${_exit_codes[*]}"
  else
    log_verbose "screenshots: no $_SCREENSHOT_GOLD_DIR, not compared"
  fi
}

regenerate_refuse() {
  error_exit 2 "error: --regenerate cannot reuse the recordings: $1"
}

header_row_of() {
  sed -n "s/^$2=//p" "$1" | head -1
}

regenerate_check() {
  [ "$_REGENERATE" = 1 ] || return 0

  local _artifacts="$_DIR_PERF2HTML/$ARTIFACTS_NAME"
  if [ ! -d "$_artifacts" ]; then
    regenerate_refuse "no recordings at $_artifacts"
  fi

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

    _recorded="$(header_row_of "$_rows" recorded)"
    _recorded="${_recorded%% *}"
    if [ -z "$_recorded" ]; then
      regenerate_refuse "$_name records no recorded= row in $_rows"
    fi

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

clear_overwritten_folders() {
  local _path _archive

  for _path in "${_DEFAULT_REPORTS[@]}"; do
    rm -rf "$_path" \
      || error_exit 1 "error: could not remove the previous report: $_path"

    _archive="$_path$REPORT_RAW_ARCHIVE_SUFFIX"
    rm -f "$_archive" || error_exit 1 \
      "error: could not remove the previous archive: $_archive"
  done
  log_verbose "cleared ${#_DEFAULT_REPORTS[@]} report(s)"

  rm -rf "$_SCREENSHOT_DIFF_DIR" || error_exit 1 \
    "error: could not remove the previous shot diffs: $_SCREENSHOT_DIFF_DIR"
}

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

main() {
  args_parse "$@"
  verbose_begin
  title_print "$_SCRIPT" "$@"
  whitelist_expand
  regenerate_check
  tools_resolve
  clear_overwritten_folders
  format_shell
  format_python
  format_c
  format_prettier
  long_lines_report
  test_source_scan_run
  lint_run
  batch_run
  test_expected_report_check_run
  test_expected_archive_check_run
  screenshots_run
}

main "$@"
