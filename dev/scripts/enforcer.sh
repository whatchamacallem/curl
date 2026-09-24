#!/usr/bin/env bash
# dev/scripts/enforcer.sh [--check] [--keep-artifacts] [--regenerate]
#     [--verbose]
#
# The one hook that verifies dev/ and its output. It clears the reports,
# formats, lints and scans dev/ source, runs the batch itself with default
# arguments, then validates and shoots the reports it wrote.
#
# --regenerate rebuilds the pages from the last run's recordings instead of
# measuring again, which is what a dev/ edit wants: nothing it changed can
# move a number. It is checked rather than trusted -- the recordings must
# still describe the executable on disk -- and a check that does not hold up
# is a hard error, never a silent hour of profiling. See regenerate_check.
#
# Any fault whatsoever is a hard error, reported where it happened: the run
# stops, and nothing downstream prints. Reading a consequence and mistaking
# it for the cause costs a reader more than a second run costs anyone.
#
# The stages run in ascending cost, so a formatting slip is reported in
# seconds rather than after the profiling run.
#
# It takes no report argument: the batch cannot be told where to write, so
# the three default names below are the only reports there are to verify.
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
# A report is output, not source: no stage above reaches inside one, so a
# generated page is neither formatted, linted, column-checked nor scanned
# for ASCII. Every one of those stages runs before the batch writes a
# report, and what a generator emits is that generator's own to get right.
#
# The screenshots stage shoots the modified and diff reports at each
# viewport, naming a file for its size and report. Shots land outside every
# report for the same reason: a checksum covers a report's own files only.
#
# Do not document what is being validated further. The validation
# code below and the generator code itself are the living standards
# for a correct report. They are checked for agreement, no more.

set -euo pipefail

_SCRIPT="$(readlink -f "$0")"
_SCRIPTS="$(dirname "$_SCRIPT")"

# Where the caller stood. This takes no path argument of its own, but
# shared.sh's absolute_path reads it, so it is set before the cd below.
INVOKED_FROM="$PWD"
cd "$_SCRIPTS"

# Where each kind of source lives, relative to scripts/, and the repo a
# report's executable= row is relative to.
_DIR_DEV=..
_DIR_REPO=../..
_DIR_SCRIPTS=.
_DIR_SRC=../src

# the hard column limit every kind of source is checked against
_COLUMNS_MAX=79
_CLANG_FORMAT_CONFIG=../src/.clang-format
_PRETTIER_CONFIG=.prettierrc.json
_PYRIGHT_CONFIG=pyrightconfig.json

# The one markdown file that is dev/ source. Every other .md under dev/ is
# the author's notes -- DECLAUDE.md and its kin -- and no stage reaches it.
_MARKDOWN_NAME=README.md

# spaces shfmt indents a shell block by
_SHELL_INDENT=2
_RUFF_CONFIG=ruff.toml

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

usage_show() {
  cat <<'EOF'
scripts/enforcer.sh [--check] [--keep-artifacts] [--regenerate] [--verbose]
    Formats and lints dev/, runs perf2html_batch.sh over the three reports
    it cleared, then validates and screenshots what it wrote and scans the
    tree for non-ASCII. Any fault stops the run where it happened.
    --check           Report what would change rather than writing it.
    --keep-artifacts  Measure as usual, but keep the recordings afterwards,
                      which is what a later --regenerate reuses. Flagless
                      runs delete them.
    --regenerate      Rebuild the three reports' pages from the last run's
                      recordings, re-measuring nothing. Pass it after every
                      dev/ edit; leave it off once perf has been re-linked.
                      Recordings that no longer describe the executable are
                      a hard error: re-run without the flag to measure.
    --verbose         Enables diagnostic information.
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

# child_stream - run one child, streaming it live. SETS STAGE_EXIT_CODE and
# STAGE_OUTPUT, their canonical setter. Never $( ): that buffers the child.
child_stream() {
  local _log
  _log="$(mktemp)"
  STAGE_EXIT_CODE=0

  # the tee is chosen before the child starts, so verbose watches the work
  # happen rather than reading it replayed once the child has exited
  if [ "$VERBOSE" = 1 ]; then
    if ! { "$@" 2>&1 | tee "$_log"; }; then
      STAGE_EXIT_CODE="${PIPESTATUS[0]}"
    fi
  else
    "$@" >"$_log" 2>&1 || STAGE_EXIT_CODE=$?
  fi

  STAGE_OUTPUT="$(cat "$_log")"
  rm -f "$_log"
}

# stage_fail - print one stage's verdict and output, then stop the run. The
# first fault is the one a reader must act on, so nothing follows it.
stage_fail() {
  local _label="$1" _verdict="$2" _summary="$3" _output="$4"

  printf '%-12s| %-7s| %s\n' "$_label" "$_verdict" "$_summary"
  if [ -n "$_output" ]; then echo "$_output" >&2; fi
  exit 1
}

# tool_missing_fail - a tool that is not installed never checked its files,
# so the run is not a verification and stops here with how to install it.
tool_missing_fail() {
  local _label="$1" _name="$2"

  printf '%-12s| MISSING| not installed: %s\n' "$_label" "$_name"
  {
    echo "error: $_name is not installed, so $_label never ran"
    echo "  sudo apt-get install -y shfmt clang-format"
    echo "  pip3 install --user --break-system-packages ruff"
    echo "  npm install -g prettier pyright"
  } >&2
  exit 1
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
    log_verbose "$(printf '%-12s| ok      | no files' "$_label")"
    return 0
  fi

  child_stream "$_binary" "${_TOOL_ARGS[@]}" "$@"

  if [ "$STAGE_EXIT_CODE" = 0 ]; then
    log_verbose "$(printf '%-12s| ok      | %s file(s)' "$_label" "$#")"
    return 0
  fi

  stage_fail "$_label" CHANGED "$(echo "$STAGE_OUTPUT" | head -n 1)" \
    "$STAGE_OUTPUT"
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

  _TOOL_ARGS=(--style=file:"$_CLANG_FORMAT_CONFIG")
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
    tool_missing_fail lint pyright
  fi

  child_stream "$_binary" --project "$_PYRIGHT_CONFIG"

  if [ "$STAGE_EXIT_CODE" = 0 ]; then
    log_verbose "$(printf '%-12s| ok      | pyright' "lint")"
    return 0
  fi

  stage_fail lint FAILED pyright "$STAGE_OUTPUT"
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
    log_verbose "$(printf '%-12s| ok      | none over %s' \
      "columns" "$_COLUMNS_MAX")"
    return 0
  fi

  stage_fail columns TOO_LONG \
    "$(echo "$_over" | grep -c ' cols$') line(s) over $_COLUMNS_MAX" "$_over"
}

# Line 1 of a directory's MANIFEST.txt, or empty when it has none.
report_version() {
  head -n 1 "$1/MANIFEST.txt" 2>/dev/null
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

    child_stream python3 validate_report.py "${_args[@]}"

    if [ "$STAGE_EXIT_CODE" = 0 ]; then
      log_verbose "$(printf '%-12s| ok      | %s' \
        "validate" "$(basename "$_path")")"
      continue
    fi

    stage_fail validate FAILED "$(basename "$_path")" "$STAGE_OUTPUT"
  done
}

# comment_block_run - the dev/ tree's comment length check, once, for the
# same reason the ASCII scan runs once: the sources are one tree.
comment_block_run() {
  child_stream python3 comment_block_scan.py

  # the limit is the scanner's own and is never spelled here: it prints the
  # number in both the ok line and every fault, so there is one to keep.
  if [ "$STAGE_EXIT_CODE" = 0 ]; then
    log_verbose "$(printf '%-12s| ok      | %s' "comments" "$STAGE_OUTPUT")"
    return 0
  fi

  stage_fail comments TOO_LONG "$(echo "$STAGE_OUTPUT" | tail -n 1)" \
    "$STAGE_OUTPUT"
}

# source_scan_run - the non-ASCII scan over dev/ source. It runs with the
# other source stages, so no report or build tree is in its walk.
source_scan_run() {
  child_stream python3 validate_report.py --source-scan-only

  if [ "$STAGE_EXIT_CODE" = 0 ]; then
    log_verbose "$(printf '%-12s| ok      | dev/ is ASCII' "ascii")"
    return 0
  fi

  stage_fail ascii FAILED dev/ "$STAGE_OUTPUT"
}

# batch_run - write the three reports this run verifies. Its own steps stop
# at their first failure, and so does this: there is nothing left to check.
batch_run() {
  local _output _exit_code=0 _flags=()
  mapfile -t _flags < <(verbose_flags_of)

  # regenerate_check held this back unless the recordings still describe the
  # executable, so the batch is never asked to reuse a stale one
  if [ "$_REGENERATE" = 1 ]; then _flags+=(--regenerate); fi

  # a measuring run that keeps its recordings is what a later --regenerate
  # reuses, and the batch owns every deletion of them
  if [ "$_KEEP_ARTIFACTS" = 1 ]; then _flags+=(--keep-artifacts); fi

  child_stream "$_DIR_DEV/$_BATCH_SCRIPT_NAME" "${_flags[@]}" \
    "--target-dir=$_DIR_DEV"

  if [ "$STAGE_EXIT_CODE" = 0 ]; then
    log_verbose "$(printf '%-12s| ok      | %s' "batch" "$_BATCH_SCRIPT_NAME")"
    return 0
  fi

  stage_fail batch FAILED "$_BATCH_SCRIPT_NAME" "$STAGE_OUTPUT"
}

# screenshots_run - shoot the modified and diff reports at every viewport
# screenshots.py names. Both exist: the batch wrote them or exited.
screenshots_run() {
  local _name _path _prefix _output _exit_code

  for _name in "$REPORT_MODIFIED_DIR_NAME" "$REPORT_DIFF_DIR_NAME"; do
    _path="$_DIR_DEV/$_name"

    # perf2html_modified_report -> modified_, the prefix naming which of the
    # two a file came from and nothing else
    _prefix="${_name#perf2html_}"
    _prefix="${_prefix%_report}_"

    _exit_code=0
    _output="$(python3 "$_SCREENSHOTS_SCRIPT_NAME" "$_path" \
      "$_prefix" 2>&1)" || _exit_code=$?

    if [ "$_exit_code" = 0 ]; then
      log_verbose "$(printf '%-12s| ok      | %s' "screenshots" "$_name")"
      log_verbose "$_output"
      continue
    fi

    stage_fail screenshots FAILED "$_name" "$_output"
  done
}

# regenerate_refuse - say why the recordings cannot be reused and stop. The
# flag is the developer loop, and measuring instead costs an hour nobody asked
regenerate_refuse() {
  echo "error: --regenerate cannot reuse the recordings: $1" >&2
  echo "       re-run without --regenerate to measure from scratch" >&2
  exit 1
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

  # the artifacts dir the batch defaults to, holding every recording the
  # three reports were generated from
  local _artifacts="$_DIR_DEV/$ARTIFACTS_NAME"
  if [ ! -d "$_artifacts" ]; then
    regenerate_refuse "no recordings at $_artifacts"
  fi

  # all three are this run's input, and manifest_verify is the one policy
  # saying why one is not a report -- it exits, so this fails at the first
  local _name
  manifest_verify "$_DIR_DEV/$REPORT_BASELINE_DIR_NAME" \
    "--regenerate input" "$REPORT_MANIFEST_VERSION_FULL"
  manifest_verify "$_DIR_DEV/$REPORT_MODIFIED_DIR_NAME" \
    "--regenerate input" "$REPORT_MANIFEST_VERSION_FULL"
  manifest_verify "$_DIR_DEV/$REPORT_DIFF_DIR_NAME" \
    "--regenerate input" "$REPORT_MANIFEST_VERSION_DIFF"

  # each measured report names its own recordings by stamp. The diff has no
  # recordings of its own: it is subtracted from these two.
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
  done

  # the modified run built that tree last, so its recordings are the ones
  # the executable still on disk wrote; the baseline's binary is gone
  _name="$REPORT_MODIFIED_DIR_NAME"
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
    -name "$PROFILE_TIMING_FILE_PREFIX.*.${_stamps[-1]}.csv" \
    -printf '%T@ %p\n' | sort -rn | head -1)"
  _newest="${_newest#* }"
  if [ -n "$(find "$_binary" -newer "$_newest" -print -quit)" ]; then
    regenerate_refuse "$_name: perf was re-linked after its recordings"
  fi

  log_verbose "$(printf '%-12s| ok      | reusing stamp %s and %s' \
    "regenerate" "${_stamps[0]}" "${_stamps[1]}")"
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
    log_verbose "$(printf '%-12s| ok      | %s report(s) reused' \
      "surface" "${#_DEFAULT_REPORTS[@]}")"
    return 0
  fi

  for _path in "${_DEFAULT_REPORTS[@]}"; do
    rm -rf "$_path" || {
      echo "error: could not remove the previous report: $_path" >&2
      exit 1
    }
  done
  log_verbose "$(printf '%-12s| ok      | %s report(s) cleared' \
    "surface" "${#_DEFAULT_REPORTS[@]}")"
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
      --check)
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
        VERBOSE=1
        shift
        ;;
      *)
        echo "unknown option: $1" >&2
        usage_show >&2
        exit 2
        ;;
    esac
  done
}

# main - the stages in ascending cost, each one stopping the run where it
# fails, so the first fault a reader sees is the one that happened first.
main() {
  args_parse "$@"

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
  comment_block_run
  source_scan_run
  lint_run

  # the profiling run, which writes the three reports, then what they hold
  batch_run
  validate_run
  screenshots_run
}

main "$@"
