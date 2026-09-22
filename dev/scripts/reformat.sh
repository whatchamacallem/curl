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
# Do not document what is being validated further. The validation
# code below and the generator code itself are the living standards
# for a correct report. They are checked for agreement, no more.
SCRIPT="$(readlink -f "$0")"
SCRIPTS="$(dirname "$SCRIPT")"

# Where the caller stood, so a relative report-dir still means what they
# typed after the cd below.
INVOKED_FROM="$PWD"
cd "$SCRIPTS"

# Where each kind of source lives, relative to scripts/.
DIR_DEV=..
DIR_SCRIPTS=.

# the hard column limit every kind of source is checked against
COLUMNS_MAX=79
PRETTIER_CONFIG=../.prettierrc.json

# Markdown that is the author's notes rather than dev/ source. Nothing here
# is formatted, linted or column-checked.
SKIPPED_MARKDOWN_NAMES=(DECLAUDE.md)

# spaces shfmt indents a shell block by
SHELL_INDENT=2
RUFF_CONFIG=ruff.toml

# The reports validated when the argument names none, in the order the batch
# writes them.
DEFAULT_REPORTS=(
  ../perf2html_baseline_report
  ../perf2html_modified_report
  ../perf2html_diff_report
)

. ./shared.sh

usage_show() {
  cat <<'EOF'
scripts/reformat.sh [--check] [--verbose] [report-dir]
EOF
}

# tool_find - echo a tool's path, searching the pip and npm user bins too.
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

# tool_run - run one tool with TOOL_ARGS over the files, printing a status
# row. It sets STATUS on failure and always returns 0, so later stages run.
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
    log_verbose "$output"
    return 0
  fi

  printf '%-12s| CHANGED | %s\n' "$label" "$(echo "$output" | head -n 1)"
  echo "$output" >&2
  STATUS=1
  return 0
}

# files_of - the one door every stage collects files through, so a name
# held out here is out of format, lint and the column check alike.
files_of() {
  local dir="$1" pattern="$2" skipped=()

  local name
  for name in "${SKIPPED_MARKDOWN_NAMES[@]}"; do
    skipped+=(-not -name "$name")
  done

  find "$dir" -name "$pattern" -type f \
    -not -path "*/$ARTIFACTS_NAME/*" \
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

# format_prettier - markdown, JSON, YAML and every page asset. prettier
# reparses what it writes, so it is these kinds' lint as well.
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
    log_verbose "$output"
    return 0
  fi

  printf '%-12s| FAILED  | pyright\n' "lint"
  echo "$output" >&2
  STATUS=1
}

# long_lines_report - fail on any line still over COLUMNS_MAX afterwards.
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

# report_claim - accept a directory whose MANIFEST.txt line 1 is a version
# string and whose checksum still matches, else set REPORT_ERROR saying so.
report_claim() {
  local path="$1" version recorded found

  if [ ! -d "$path" ]; then
    REPORT_ERROR="no such directory: $path -- a report is a directory"
    REPORT_ERROR="$REPORT_ERROR whose MANIFEST.txt line 1 reads"
    REPORT_ERROR="$REPORT_ERROR \"$REPORT_MANIFEST\""
    REPORT_ERROR="$REPORT_ERROR or \"$DIFF_MANIFEST\""
    return 1
  fi

  version="$(report_version "$path")"
  case "$version" in
    "$REPORT_MANIFEST" | "$DIFF_MANIFEST") ;;
    "")
      REPORT_ERROR="$path has no MANIFEST.txt, so it is not a finished"
      REPORT_ERROR="$REPORT_ERROR report; expected line 1 to read"
      REPORT_ERROR="$REPORT_ERROR \"$REPORT_MANIFEST\""
      REPORT_ERROR="$REPORT_ERROR or \"$DIFF_MANIFEST\""
      return 1
      ;;
    *)
      REPORT_ERROR="$path/MANIFEST.txt line 1 found \"$version\";"
      REPORT_ERROR="$REPORT_ERROR expected \"$REPORT_MANIFEST\""
      REPORT_ERROR="$REPORT_ERROR or \"$DIFF_MANIFEST\""
      return 1
      ;;
  esac

  recorded="$(manifest_value "$path" "$CHECKSUM_LABEL")"
  if [ -z "$recorded" ]; then
    REPORT_ERROR="$path/MANIFEST.txt has no $CHECKSUM_LABEL= row, so its"
    REPORT_ERROR="$REPORT_ERROR files cannot be verified; expected one"
    REPORT_ERROR="$REPORT_ERROR beside the version line \"$version\""
    return 1
  fi
  found="$(checksum_compute "$path")"
  if [ "$found" != "$recorded" ]; then
    REPORT_ERROR="$path does not match its recorded $CHECKSUM_LABEL:"
    REPORT_ERROR="$REPORT_ERROR found \"$found\", expected \"$recorded\""
    REPORT_ERROR="$REPORT_ERROR -- a file was added, removed or edited"
    REPORT_ERROR="$REPORT_ERROR after the report was written"
    return 1
  fi

  REPORTS+=("$path")
  return 0
}

# Claim the named report, or every default report that is present.
report_find() {
  local path

  if [ -n "$REPORT_ARG" ]; then
    report_claim "$REPORT_ARG"
    return 0
  fi

  for path in "${DEFAULT_REPORTS[@]}"; do
    if [ -e "$path/MANIFEST.txt" ]; then report_claim "$path"; fi
  done

  if [ "${#REPORTS[@]}" = 0 ] && [ -z "$REPORT_ERROR" ]; then
    REPORT_ERROR="no report was named, and the default location"
    REPORT_ERROR="$REPORT_ERROR dev/${DEFAULT_REPORTS[0]#../} is absent"
    REPORT_ERROR="$REPORT_ERROR or has no MANIFEST.txt reading"
    REPORT_ERROR="$REPORT_ERROR \"$REPORT_MANIFEST\""
  fi
}

# validate_run - run validate_report.py over every claimed report.
validate_run() {
  local path args output exit_code

  # a directory that is not a report is its own failure, and the reports
  # that are still get validated
  if [ -n "$REPORT_ERROR" ]; then
    printf '%-12s| FAILED  | %s\n' "validate" "not a report"
    {
      echo "error: $REPORT_ERROR"
      echo "       name a report directory as the argument, or run" \
        "dev/perf2html_batch.sh to write the three default ones"
    } >&2
    STATUS=1
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
      log_verbose "$output"
      continue
    fi

    printf '%-12s| FAILED  | %s\n' "validate" "$(basename "$path")"
    echo "$output" >&2
    STATUS=1
  done
}

# args_parse - read the flags and resolve REPORT_ARG against INVOKED_FROM.
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

  settings_load

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
