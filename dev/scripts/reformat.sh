#!/usr/bin/env bash
# dev/scripts/reformat.sh [--check] [--verbose] [report-dir]
#
# The one hook that verifies dev/ and its output. Three things in order:
# lint, format, validate. Every stage runs even after an earlier one failed.
#
# What runs over what:
#
#   source            format        lint             cols  ascii
#   ----------------- ------------- ---------------- ----- ------
#   *.sh              shfmt         --               yes   yes
#   README.md         prettier      prettier         yes   yes
#   src/*.c *.h       clang-format  --               yes   yes
#   scripts/*.py      ruff          pyright, ruff    yes   yes
#   scripts/*.js      prettier      prettier         yes   yes
#   scripts/*.css     prettier      prettier         yes   yes
#   scripts/*.html    prettier      prettier         yes   yes
#
# Nothing else is touched at all. A config file -- .json, .yml, .toml, and
# the dotfiles beside them -- is this tooling's own settings rather than
# dev/ source, so no stage formats, lints or column-checks one.
#
# The ASCII scan runs once over the whole tree, not once per report.
#
# Do not document what is being validated further. The validation
# code below and the generator code itself are the living standards
# for a correct report. They are checked for agreement, no more.
_SCRIPT="$(readlink -f "$0")"
_SCRIPTS="$(dirname "$_SCRIPT")"

# Where the caller stood, so a relative report-dir still means what they
# typed after the cd below.
_INVOKED_FROM="$PWD"
cd "$_SCRIPTS"

# Where each kind of source lives, relative to scripts/.
_DIR_DEV=..
_DIR_SCRIPTS=.
_DIR_SRC=../src

# the hard column limit every kind of source is checked against
_COLUMNS_MAX=79
_PRETTIER_CONFIG=.prettierrc.json
_PYRIGHT_CONFIG=../src/pyrightconfig.json

# The one markdown file that is dev/ source. Every other .md under dev/ is
# the author's notes -- DECLAUDE.md and its kin -- and no stage reaches it.
_MARKDOWN_NAME=README.md

# spaces shfmt indents a shell block by
_SHELL_INDENT=2
_RUFF_CONFIG=ruff.toml

# The reports validated when the argument names none, in the order the batch
# writes them.
_DEFAULT_REPORTS=(
  ../perf2html_baseline_report
  ../perf2html_modified_report
  ../perf2html_diff_report
)

. ./settings.sh
. ./shared.sh

usage_show() {
  cat <<'EOF'
scripts/reformat.sh [--check] [--verbose] [report-dir]
EOF
}

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

# tool_run - run one tool with _TOOL_ARGS over the files, printing a status
# row. It sets _STATUS on failure and always returns 0, so later stages run.
tool_run() {
  local _name="$1" _label="$2"
  shift 2
  local _binary

  if ! _binary="$(tool_find "$_name")"; then
    printf '%-12s| skipped | not installed: %s\n' "$_label" "$_name"
    _MISSING+=("$_name")
    return 0
  fi

  if [ "$#" = 0 ]; then
    printf '%-12s| ok      | no files\n' "$_label"
    return 0
  fi

  local _output _exit_code=0
  _output="$("$_binary" "${_TOOL_ARGS[@]}" "$@" 2>&1)" || _exit_code=$?

  if [ "$_exit_code" = 0 ]; then
    printf '%-12s| ok      | %s file(s)\n' "$_label" "$#"
    log_verbose "$_output"
    return 0
  fi

  printf '%-12s| CHANGED | %s\n' "$_label" "$(echo "$_output" | head -n 1)"
  echo "$_output" >&2
  _STATUS=1
  return 0
}

# files_of - the one door every stage collects files through, so a name
# held out here is out of format, lint and the column check alike.
files_of() {
  local _dir="$1" _pattern="$2"

  # .vscode/ and .claude/ are this box's editor settings, not dev/ source
  find "$_dir" -name "$_pattern" -type f \
    -not -path "*/$ARTIFACTS_NAME/*" \
    -not -path '*_report/*' -not -path '*/node_modules/*' \
    -not -path '*/__pycache__/*' -not -path '*/.*/*' | sort
}

format_shell() {
  local _files
  mapfile -t _files < <(files_of "$_DIR_DEV" '*.sh')

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
  mapfile -t _files < <(files_of "$_DIR_SCRIPTS" '*.py')

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
  local _files _extra
  mapfile -t _files < <(files_of "$_DIR_SRC" '*.c')
  mapfile -t _extra < <(files_of "$_DIR_SRC" '*.h')
  _files+=("${_extra[@]}")

  _TOOL_ARGS=(--style=file)
  if [ "$_CHECK" = 1 ]; then
    _TOOL_ARGS+=(--dry-run --Werror)
  else
    _TOOL_ARGS+=(-i)
  fi

  tool_run clang-format c "${_files[@]}"
}

# format_prettier - README.md and every page asset. prettier reparses what
# it writes, so it is these kinds' lint as well.
format_prettier() {
  local _files=() _extra _kind

  mapfile -t _files < <(files_of "$_DIR_DEV" "$_MARKDOWN_NAME")
  for _kind in '*.js' '*.css' '*.html'; do
    mapfile -t _extra < <(files_of "$_DIR_SCRIPTS" "$_kind")
    _files+=("${_extra[@]}")
  done

  _TOOL_ARGS=(--config "$_PRETTIER_CONFIG" --log-level warn)
  if [ "$_CHECK" = 1 ]; then
    _TOOL_ARGS+=(--check)
  else
    _TOOL_ARGS+=(--write)
  fi

  tool_run prettier prettier "${_files[@]}"
}

# pyright over the generators. The page assets are prettier's, which parses
# every one of them.
lint_run() {
  local _binary

  if ! _binary="$(tool_find pyright)"; then
    printf '%-12s| skipped | not installed: %s\n' "lint" "pyright"
    _MISSING+=(pyright)
    return 0
  fi

  local _output _exit_code=0
  _output="$("$_binary" --project "$_PYRIGHT_CONFIG" 2>&1)" || _exit_code=$?

  if [ "$_exit_code" = 0 ]; then
    printf '%-12s| ok      | pyright\n' "lint"
    log_verbose "$_output"
    return 0
  fi

  printf '%-12s| FAILED  | pyright\n' "lint"
  echo "$_output" >&2
  _STATUS=1
}

# long_lines_report - fail on any line still over _COLUMNS_MAX afterwards.
long_lines_report() {
  local _files=() _extra _kind

  # 79 columns is every language dev/ is written in. A config file is not
  # one of them: it is this tooling's settings, and no stage reads it here.
  mapfile -t _files < <(files_of "$_DIR_DEV" '*.sh')
  mapfile -t _extra < <(files_of "$_DIR_DEV" "$_MARKDOWN_NAME")
  _files+=("${_extra[@]}")
  for _kind in '*.c' '*.h'; do
    mapfile -t _extra < <(files_of "$_DIR_SRC" "$_kind")
    _files+=("${_extra[@]}")
  done
  for _kind in '*.py' '*.js' '*.css' '*.html'; do
    mapfile -t _extra < <(files_of "$_DIR_SCRIPTS" "$_kind")
    _files+=("${_extra[@]}")
  done

  if [ "${#_files[@]}" = 0 ]; then return 0; fi

  local _over
  _over="$(awk -v max="$_COLUMNS_MAX" \
    'length > max { print FILENAME ":" FNR ": " length " cols\n  " $0 }' \
    "${_files[@]}")"

  if [ -z "$_over" ]; then
    printf '%-12s| ok      | none over %s\n' "columns" "$_COLUMNS_MAX"
    return 0
  fi

  printf '%-12s| TOO_LONG| %s line(s) over %s\n' \
    "columns" "$(echo "$_over" | grep -c ' cols$')" "$_COLUMNS_MAX"
  echo "$_over" >&2
  _STATUS=1
}

# report_error_add - collect one reason a directory is not a report. SETS
# _REPORT_ERRORS, and is its canonical setter: every reason is kept, so a
# valid report later in the list cannot hide a broken one before it.
report_error_add() {
  _REPORT_ERRORS+=("$1")
}

# Line 1 of a directory's MANIFEST.txt, or empty when it has none.
report_version() {
  head -n 1 "$1/MANIFEST.txt" 2>/dev/null
}

# report_claim - accept a directory that holds up as either kind of
# report, else append shared.sh's reason to _REPORT_ERRORS. SETS that
# caller global, and is its canonical setter: main() initializes it and
# validate_run reads every entry back. Collecting rather than exiting is
# the whole difference from manifest_verify: a broken report must not
# stop the reports after it from being validated.
report_claim() {
  local _path="$1" _fault

  _fault="$(manifest_fault_of "$_path" \
    "$REPORT_MANIFEST_VERSION_FULL" "$REPORT_MANIFEST_VERSION_DIFF")"
  if [ -n "$_fault" ]; then
    report_error_add "$_fault"
    return 1
  fi

  _REPORTS+=("$_path")
  return 0
}

# Claim the named report, or every default report directory that exists.
report_find() {
  local _path _error

  if [ -n "$_REPORT_ARG" ]; then
    report_claim "$_REPORT_ARG"
    return 0
  fi

  # a directory that is there but holds no MANIFEST.txt is an aborted run,
  # which is a failure to report, not a directory to walk past: testing
  # for the manifest here let a broken report hide behind a valid one.
  for _path in "${_DEFAULT_REPORTS[@]}"; do
    if [ -d "$_path" ]; then report_claim "$_path"; fi
  done

  if [ "${#_REPORTS[@]}" = 0 ] && [ "${#_REPORT_ERRORS[@]}" = 0 ]; then
    _error="no report was named, and the default location"
    _error="$_error dev/${_DEFAULT_REPORTS[0]#../} is absent"
    _error="$_error or has no MANIFEST.txt reading"
    _error="$_error \"$REPORT_MANIFEST_VERSION_FULL\""
    report_error_add "$_error"
  fi
}

# validate_run - run validate_report.py over every claimed report.
validate_run() {
  local _path _args _output _exit_code

  # a directory that is not a report is its own failure, and the reports
  # that are still get validated
  if [ "${#_REPORT_ERRORS[@]}" != 0 ]; then
    printf '%-12s| FAILED  | %s not a report\n' \
      "validate" "${#_REPORT_ERRORS[@]}"
    {
      local _reason
      for _reason in "${_REPORT_ERRORS[@]}"; do echo "error: $_reason"; done
      echo "       name a report directory as the argument, or run" \
        "dev/perf2html_batch.sh to write the three default ones"
    } >&2
    _STATUS=1
  fi

  for _path in "${_REPORTS[@]}"; do
    _args=("$(cd "$_path" && pwd)")
    if [ "$(report_version "$_path")" = "$REPORT_MANIFEST_VERSION_DIFF" ]; then
      _args+=(--diff)
    fi

    _exit_code=0
    _output="$(python3 validate_report.py "${_args[@]}" 2>&1)" || _exit_code=$?

    if [ "$_exit_code" = 0 ]; then
      printf '%-12s| ok      | %s\n' "validate" "$(basename "$_path")"
      log_verbose "$_output"
      continue
    fi

    printf '%-12s| FAILED  | %s\n' "validate" "$(basename "$_path")"
    echo "$_output" >&2
    _STATUS=1
  done
}

# source_scan_run - the dev/ tree's non-ASCII scan, once. The sources are
# one tree, not a property of any report: running it inside the validator
# scanned them once per report found, or not at all when none was.
source_scan_run() {
  local _output _exit_code=0
  _output="$(python3 validate_report.py --source-scan-only 2>&1)" \
    || _exit_code=$?

  if [ "$_exit_code" = 0 ]; then
    printf '%-12s| ok      | dev/ is ASCII\n' "ascii"
    log_verbose "$_output"
    return 0
  fi

  printf '%-12s| FAILED  | dev/\n' "ascii"
  echo "$_output" >&2
  _STATUS=1
}

# args_parse - read the flags and resolve _REPORT_ARG against _INVOKED_FROM.
args_parse() {
  _CHECK=0
  _REPORT_ARG=""

  while [ $# -gt 0 ]; do
    case "$1" in
      -h | --help)
        usage_show
        exit 0
        ;;
      --check)
        _CHECK=1
        shift
        ;;
      --verbose)
        VERBOSE=1
        shift
        ;;
      -*)
        echo "unknown option: $1" >&2
        exit 2
        ;;
      *)
        if [ -n "$_REPORT_ARG" ]; then
          echo "error: one report directory at most, got: $_REPORT_ARG $1" >&2
          exit 2
        fi
        _REPORT_ARG="$1"
        shift
        ;;
    esac
  done

  case "$_REPORT_ARG" in
    "" | /*) ;;
    *) _REPORT_ARG="$_INVOKED_FROM/$_REPORT_ARG" ;;
  esac
}

main() {
  args_parse "$@"

  _STATUS=0
  _MISSING=()
  _REPORTS=()
  _REPORT_ERRORS=()

  report_find

  lint_run

  format_shell
  format_python
  format_c
  format_prettier

  long_lines_report
  source_scan_run
  validate_run

  if [ "${#_MISSING[@]}" != 0 ]; then
    {
      echo
      echo "not installed: ${_MISSING[*]}"
      echo "  sudo apt-get install -y shfmt clang-format"
      echo "  pip3 install --user --break-system-packages ruff"
      echo "  npm install -g prettier"
    } >&2
    _STATUS=1
  fi

  return "$_STATUS"
}

main "$@"
