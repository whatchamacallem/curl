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
#   *.c *.h           clang-format  --               yes   yes
#   *.md *.json       prettier      prettier         yes   yes(1)
#   scripts/*.py      ruff          pyright, ruff    yes   yes
#   scripts/*.js      prettier      prettier         yes   yes
#   scripts/*.css     prettier      prettier         yes   yes
#   scripts/*.html    prettier      prettier         yes   yes
#
#   (1) README.md only. No *.json is: json shares the row because
#       prettier handles both kinds.
#
# DECLAUDE.md is the author's own notes, not dev/ source: no formatter, no
# lint, no column check reaches it. SKIPPED_MARKDOWN_NAMES is what holds it
# out of every one of those, so adding a second such file is one name here.
#
# The dirs are fixed by convention: ".." is dev/ itself, where the shell
# scripts, the C recorder and the markdown live, and "." is scripts/, where
# every generator and page asset lives. There is no path argument.
#
# prettier both formats and lints its kinds: it reparses what it writes, so
# a syntax error cannot survive it. Each page asset is read verbatim into a
# generator constant (theme.theme_asset), so formatting the file on disk is
# what covers the string the generator ships. Settings live in
# dev/.prettierrc.json -- print width 79, so a line still over 79 columns
# after the formatters run is an error: it prints file:line, the width and
# the whole line, and exits 1. prettier cannot break a long template
# literal, so those few are split by hand.
#
# The "settings" stage reports every SCREAMING_SNAKE constant a generator
# assigns below its settings.load_into() call. It is a note, never a
# failure: the namespace rule is what puts them there. --verbose lists them.
#
# Validation runs validate_report.py over the report named as the argument,
# or over whichever default reports exist when none is named. A directory is
# a report by holding a MANIFEST.txt whose line 1 is a known version string;
# that line also decides --diff.
#
# --check reports what would change and exits 1 instead of writing.
# cwd-independent: it works in dev/scripts/, like the perf2html scripts.
set -uo pipefail
SCRIPT="$(readlink -f "$0")"
SCRIPTS="$(dirname "$SCRIPT")"

# Where the caller stood, so a relative report-dir still means what they
# typed after the cd below.
INVOKED_FROM="$PWD"
cd "$SCRIPTS"

# Where each kind of source lives, relative to scripts/.
DIR_DEV=..
DIR_SCRIPTS=.

COLUMNS_MAX=79
PRETTIER_CONFIG=../.prettierrc.json

# Markdown that is the author's notes rather than dev/ source. Nothing here
# is formatted, linted or column-checked.
SKIPPED_MARKDOWN_NAMES=(DECLAUDE.md)
SHELL_INDENT=2
RUFF_CONFIG=ruff.toml

# The reports validated when the argument names none, in the order the batch
# writes them.
DEFAULT_REPORTS=(
  ../perf2html_baseline_report
  ../perf2html_modified_report
  ../perf2html_diff_report
)

# MANIFEST.txt line 1 of a perf2html.sh report, and of a diff of two.
REPORT_MANIFEST='curl/perf2html.sh v1'
DIFF_MANIFEST='curl/perf2html_diff.sh v1'

usage_show() {
  cat <<'EOF'
scripts/reformat.sh [--check] [--verbose] [report-dir]
EOF
}

verbose() { if [ "$VERBOSE" = 1 ]; then echo "$@"; fi; }

tool_find() {
  local name="$1" found

  for found in "$name" "$HOME/.local/bin/$name" \
    "$HOME/.npm-global/bin/$name"; do
    if command -v "$found" >/dev/null 2>&1; then
      echo "$found"
      return 0
    fi
  done

  return 1
}

tool_run() {
  local name="$1" label="$2"
  shift 2
  local binary

  if ! binary="$(tool_find "$name")"; then
    printf '%-12s| skipped | not installed: %s\n' "$label" "$name"
    MISSING+=("$name")
    return 0
  fi

  if [ "$#" = 0 ]; then
    printf '%-12s| ok      | no files\n' "$label"
    return 0
  fi

  local output exit_code=0
  output="$("$binary" "${TOOL_ARGS[@]}" "$@" 2>&1)" || exit_code=$?

  if [ "$exit_code" = 0 ]; then
    printf '%-12s| ok      | %s file(s)\n' "$label" "$#"
    verbose "$output"
    return 0
  fi

  printf '%-12s| CHANGED | %s\n' "$label" "$(echo "$output" | head -n 1)"
  echo "$output" >&2
  STATUS=1
  return 0
}

# Every file of one kind under one directory, report dirs and raw data
# skipped, and so is every SKIPPED_MARKDOWN_NAMES file. This is the one
# door each stage collects its files through, so a name held out here is
# held out of formatting, linting and the column check alike.
files_of() {
  local dir="$1" pattern="$2" skipped=()

  local name
  for name in "${SKIPPED_MARKDOWN_NAMES[@]}"; do
    skipped+=(-not -name "$name")
  done

  find "$dir" -name "$pattern" -type f \
    -not -path '*/temporary_artifacts/*' \
    -not -path '*_report/*' -not -path '*/node_modules/*' \
    -not -path '*/__pycache__/*' "${skipped[@]}" | sort
}

format_shell() {
  local files
  mapfile -t files < <(files_of "$DIR_DEV" '*.sh')

  TOOL_ARGS=(-i "$SHELL_INDENT" -bn -ci -ln bash)
  if [ "$CHECK" = 1 ]; then
    TOOL_ARGS+=(-d)
  else
    TOOL_ARGS+=(-w)
  fi

  tool_run shfmt shell "${files[@]}"
}

format_python() {
  local files
  mapfile -t files < <(files_of "$DIR_SCRIPTS" '*.py')

  TOOL_ARGS=(format --config "$RUFF_CONFIG")
  if [ "$CHECK" = 1 ]; then TOOL_ARGS+=(--diff); fi
  tool_run ruff python "${files[@]}"

  TOOL_ARGS=(check --config "$RUFF_CONFIG")
  if [ "$CHECK" = 1 ]; then TOOL_ARGS+=(--diff); else TOOL_ARGS+=(--fix); fi
  tool_run ruff "python lint" "${files[@]}"
}

format_c() {
  local files extra
  mapfile -t files < <(files_of "$DIR_DEV" '*.c')
  mapfile -t extra < <(files_of "$DIR_DEV" '*.h')
  files+=("${extra[@]}")

  TOOL_ARGS=(--style=file)
  if [ "$CHECK" = 1 ]; then
    TOOL_ARGS+=(--dry-run --Werror)
  else
    TOOL_ARGS+=(-i)
  fi

  tool_run clang-format c "${files[@]}"
}

# Markdown, JSON and YAML under dev/, and every page asset under scripts/.
# prettier reparses what it writes, so this is the lint for these kinds too:
# a stray </div> or a bad backslash fails here rather than shipping into
# every generated page.
format_prettier() {
  local files=() extra kind

  for kind in '*.md' '*.json' '*.yml' '*.yaml'; do
    mapfile -t extra < <(files_of "$DIR_DEV" "$kind")
    files+=("${extra[@]}")
  done
  for kind in '*.js' '*.css' '*.html'; do
    mapfile -t extra < <(files_of "$DIR_SCRIPTS" "$kind")
    files+=("${extra[@]}")
  done

  TOOL_ARGS=(--config "$PRETTIER_CONFIG" --log-level warn)
  if [ "$CHECK" = 1 ]; then TOOL_ARGS+=(--check); else TOOL_ARGS+=(--write); fi

  tool_run prettier prettier "${files[@]}"
}

# pyright over the generators. The page assets are prettier's, which parses
# every one of them.
lint_run() {
  local binary

  if ! binary="$(tool_find pyright)"; then
    printf '%-12s| skipped | not installed: %s\n' "lint" "pyright"
    MISSING+=(pyright)
    return 0
  fi

  local output exit_code=0
  output="$("$binary" --project "$DIR_DEV" 2>&1)" || exit_code=$?

  if [ "$exit_code" = 0 ]; then
    printf '%-12s| ok      | pyright\n' "lint"
    verbose "$output"
    return 0
  fi

  printf '%-12s| FAILED  | pyright\n' "lint"
  echo "$output" >&2
  STATUS=1
}

# Every SCREAMING_SNAKE constant a generator assigns below its
# settings.load_into() call. The namespace rule puts them there, so this is
# a report and never a failure: it is the list of constants a reader of a
# file's head does not see, which is what to check when a value seems to
# have no definition.
lost_settings_report() {
  local files output
  mapfile -t files < <(files_of "$DIR_SCRIPTS" '*.py')

  if [ "${#files[@]}" = 0 ]; then return 0; fi

  output="$(python3 -c '
import sys, settings
for path in sys.argv[1:]:
    for row in settings.lost_settings(path):
        print(f"{row.path}:{row.line}: {row.name}")
' "${files[@]}" 2>&1)"

  if [ -z "$output" ]; then
    printf '%-12s| ok      | none below load_into()\n' "settings"
    return 0
  fi

  printf '%-12s| note    | %s below load_into()\n' \
    "settings" "$(echo "$output" | grep -c ':')"
  verbose "$output"
}

long_lines_report() {
  local files=() extra kind

  for kind in '*.sh' '*.c' '*.h' '*.md'; do
    mapfile -t extra < <(files_of "$DIR_DEV" "$kind")
    files+=("${extra[@]}")
  done
  for kind in '*.py' '*.js' '*.css' '*.html'; do
    mapfile -t extra < <(files_of "$DIR_SCRIPTS" "$kind")
    files+=("${extra[@]}")
  done

  if [ "${#files[@]}" = 0 ]; then return 0; fi

  local over
  over="$(awk -v max="$COLUMNS_MAX" \
    'length > max { print FILENAME ":" FNR ": " length " cols\n  " $0 }' \
    "${files[@]}")"

  if [ -z "$over" ]; then
    printf '%-12s| ok      | none over %s\n' "columns" "$COLUMNS_MAX"
    return 0
  fi

  printf '%-12s| TOO_LONG| %s line(s) over %s\n' \
    "columns" "$(echo "$over" | grep -c ' cols$')" "$COLUMNS_MAX"
  echo "$over" >&2
  STATUS=1
}

# Line 1 of a directory's MANIFEST.txt, or empty when it has none.
report_version() {
  head -n 1 "$1/MANIFEST.txt" 2>/dev/null
}

# Claim the named report, or every default report that exists. Anything
# wrong is reported here, naming the version string that was expected.
report_find() {
  local path version

  if [ -n "$REPORT_ARG" ]; then
    if [ ! -d "$REPORT_ARG" ]; then
      REPORT_ERROR="no such directory: $REPORT_ARG -- a report is a"
      REPORT_ERROR="$REPORT_ERROR directory whose MANIFEST.txt line 1 reads"
      REPORT_ERROR="$REPORT_ERROR \"$REPORT_MANIFEST\""
      REPORT_ERROR="$REPORT_ERROR or \"$DIFF_MANIFEST\""
      return 0
    fi
    version="$(report_version "$REPORT_ARG")"
    case "$version" in
      "$REPORT_MANIFEST" | "$DIFF_MANIFEST")
        REPORTS=("$REPORT_ARG")
        ;;
      "")
        REPORT_ERROR="$REPORT_ARG has no MANIFEST.txt, so it is not"
        REPORT_ERROR="$REPORT_ERROR dev/perf2html.sh output; its line 1"
        REPORT_ERROR="$REPORT_ERROR must read \"$REPORT_MANIFEST\""
        REPORT_ERROR="$REPORT_ERROR or \"$DIFF_MANIFEST\""
        ;;
      *)
        REPORT_ERROR="$REPORT_ARG/MANIFEST.txt line 1 reads \"$version\";"
        REPORT_ERROR="$REPORT_ERROR expected \"$REPORT_MANIFEST\""
        REPORT_ERROR="$REPORT_ERROR or \"$DIFF_MANIFEST\""
        ;;
    esac
    return 0
  fi

  for path in "${DEFAULT_REPORTS[@]}"; do
    if [ -n "$(report_version "$path")" ]; then REPORTS+=("$path"); fi
  done

  if [ "${#REPORTS[@]}" = 0 ]; then
    REPORT_ERROR="no report was named, and the default location"
    REPORT_ERROR="$REPORT_ERROR dev/${DEFAULT_REPORTS[0]#../} is absent"
    REPORT_ERROR="$REPORT_ERROR or has no MANIFEST.txt reading"
    REPORT_ERROR="$REPORT_ERROR \"$REPORT_MANIFEST\""
  fi
}

validate_run() {
  local path args output exit_code

  if [ -n "$REPORT_ERROR" ]; then
    printf '%-12s| FAILED  | no report to validate\n' "validate"
    {
      echo "error: $REPORT_ERROR"
      echo "       name a report directory as the argument, or run" \
        "dev/perf2html_batch.sh to write the three default ones"
    } >&2
    STATUS=1
    return 0
  fi

  for path in "${REPORTS[@]}"; do
    args=("$(cd "$path" && pwd)")
    if [ "$(report_version "$path")" = "$DIFF_MANIFEST" ]; then
      args+=(--diff)
    fi

    exit_code=0
    output="$(python3 validate_report.py "${args[@]}" 2>&1)" || exit_code=$?

    if [ "$exit_code" = 0 ]; then
      printf '%-12s| ok      | %s\n' "validate" "$(basename "$path")"
      verbose "$output"
      continue
    fi

    printf '%-12s| FAILED  | %s\n' "validate" "$(basename "$path")"
    echo "$output" >&2
    STATUS=1
  done
}

args_parse() {
  CHECK=0
  VERBOSE=0
  REPORT_ARG=""

  while [ $# -gt 0 ]; do
    case "$1" in
      -h | --help)
        usage_show
        exit 0
        ;;
      --check)
        CHECK=1
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
        if [ -n "$REPORT_ARG" ]; then
          echo "error: one report directory at most, got: $REPORT_ARG $1" >&2
          exit 2
        fi
        REPORT_ARG="$1"
        shift
        ;;
    esac
  done

  case "$REPORT_ARG" in
    "" | /*) ;;
    *) REPORT_ARG="$INVOKED_FROM/$REPORT_ARG" ;;
  esac
}

main() {
  args_parse "$@"

  STATUS=0
  MISSING=()
  REPORTS=()
  REPORT_ERROR=""

  report_find

  lint_run

  format_shell
  format_python
  format_c
  format_prettier

  lost_settings_report
  long_lines_report
  validate_run

  if [ "${#MISSING[@]}" != 0 ]; then
    {
      echo
      echo "not installed: ${MISSING[*]}"
      echo "  sudo apt-get install -y shfmt clang-format"
      echo "  pip3 install --user --break-system-packages ruff"
      echo "  npm install -g prettier"
    } >&2
    STATUS=1
  fi

  return "$STATUS"
}

main "$@"
