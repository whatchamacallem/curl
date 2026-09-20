#!/usr/bin/env bash
# dev/scripts/reformat.sh [--check] [--verbose] [path...]
#
# Formats every dev/ source to 79 columns: *.sh with shfmt, scripts/*.py with
# ruff, *.c/*.h with clang-format, *.md with mdformat. No path = all of dev/.
# Any line still over 79 after that is an error: it prints file:line, the
# width and the whole line, and exits 1. No formatter reaches those -- a
# heredoc, an embedded JS/CSS string, a fenced block -- so they are rewritten
# by hand.
# --check reports what would change and exits 1 instead of writing.
# cwd-independent: paths are relative to dev/, like the perf2html scripts.
set -uo pipefail
SCRIPT="$(readlink -f "$0")"
DEV="$(dirname "$(dirname "$SCRIPT")")"
cd "$DEV"

COLUMNS_MAX=79
SHELL_INDENT=2
RUFF_CONFIG=scripts/ruff.toml

usage_show() {
  awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$SCRIPT"
}

log_say() { if [ "$VERBOSE" = 1 ]; then echo "$@"; fi; }

tool_find() {
  local name="$1" found
  for found in "$name" "$HOME/.local/bin/$name"; do
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
    log_say "$output"
    return 0
  fi
  printf '%-12s| CHANGED | %s\n' "$label" "$(echo "$output" | head -n 1)"
  echo "$output" >&2
  STATUS=1
  return 0
}

files_of() {
  local pattern="$1"
  shift
  local path
  if [ "$#" = 0 ]; then set -- .; fi
  for path in "$@"; do
    if [ -f "$path" ]; then
      case "$path" in
        $pattern) echo "$path" ;;
      esac
    else
      find "$path" -name "$pattern" -type f -not -path '*/trace/*' \
        -not -path '*_report/*' -not -path '*/node_modules/*' | sort
    fi
  done
}

format_shell() {
  local files
  mapfile -t files < <(files_of '*.sh' "$@")
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
  mapfile -t files < <(files_of '*.py' "$@")
  if [ "${#files[@]}" = 0 ]; then
    tool_run ruff python
    return 0
  fi
  TOOL_ARGS=(format --config "$RUFF_CONFIG")
  if [ "$CHECK" = 1 ]; then TOOL_ARGS+=(--diff); fi
  tool_run ruff python "${files[@]}"
  TOOL_ARGS=(check --config "$RUFF_CONFIG")
  if [ "$CHECK" = 1 ]; then TOOL_ARGS+=(--diff); else TOOL_ARGS+=(--fix); fi
  tool_run ruff "python lint" "${files[@]}"
}

format_c() {
  local files extra
  mapfile -t files < <(files_of '*.c' "$@")
  mapfile -t extra < <(files_of '*.h' "$@")
  files+=("${extra[@]}")
  TOOL_ARGS=(--style=file)
  if [ "$CHECK" = 1 ]; then
    TOOL_ARGS+=(--dry-run --Werror)
  else
    TOOL_ARGS+=(-i)
  fi
  tool_run clang-format c "${files[@]}"
}

format_markdown() {
  local files
  mapfile -t files < <(files_of '*.md' "$@")
  TOOL_ARGS=(--wrap "$COLUMNS_MAX" --end-of-line lf)
  if [ "$CHECK" = 1 ]; then TOOL_ARGS+=(--check); fi
  tool_run mdformat markdown "${files[@]}"
}

long_lines_report() {
  local files=() kind
  for kind in '*.sh' '*.py' '*.c' '*.h' '*.md'; do
    mapfile -t -O "${#files[@]}" files < <(files_of "$kind" "$@")
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

args_parse() {
  CHECK=0
  VERBOSE=0
  PATHS=()
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
        PATHS+=("$1")
        shift
        ;;
    esac
  done
}

main() {
  args_parse "$@"
  STATUS=0
  MISSING=()
  format_shell "${PATHS[@]}"
  format_python "${PATHS[@]}"
  format_c "${PATHS[@]}"
  format_markdown "${PATHS[@]}"
  long_lines_report "${PATHS[@]}"
  if [ "${#MISSING[@]}" != 0 ]; then
    {
      echo
      echo "not installed: ${MISSING[*]}"
      echo "  sudo apt-get install -y shfmt clang-format"
      echo "  pip3 install --user --break-system-packages ruff mdformat" \
        "mdformat-gfm"
    } >&2
    STATUS=1
  fi
  return "$STATUS"
}

main "$@"
