#!/usr/bin/env bash
# dev/perf2html_diff.sh [--verbose] [baseline-dir modified-dir] [report-dir]
#
# Subtracts the callgrind data of two perf2html.sh reports (modified minus
# baseline, per function and source line) and writes the change as a report:
#
#   DIR/index.html    summary: top functions by change in self cost
#   DIR/heat-map/     per-line change heat map
#   DIR/raw/          the delta, a callgrind-format file
#   DIR/README.md     help
#
# With no directories, diff2html_baseline_report and diff2html_modified_report
# are compared into diff2html_diff_report. One directory given is the
# report-dir; two are the baseline and modified report-dirs; three are all of
# them, in that order. Relative paths are under dev/, ~/ is expanded. --verbose (first)
# streams every tool's output instead of logging it to dev/trace/diff.<ts>.log.
# The last line printed is the report's file:// URL.
set -euo pipefail
SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$SCRIPT")"

STAMP="$(date +%s)"
RUN_LOG="$PWD/trace/diff.$STAMP.log"

usage_show() { awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$SCRIPT"; }

log_say() { if [ "$VERBOSE" = 1 ]; then echo "$@"; fi; }

test_run() {
  if [ "$VERBOSE" = 1 ]; then "$@"; return; fi
  local exit_code=0 from
  printf '\n$ %s\n' "$*" >>"$RUN_LOG"
  from="$(wc -l <"$RUN_LOG")"
  "$@" >>"$RUN_LOG" 2>&1 || exit_code=$?
  if [ "$exit_code" != 0 ]; then
    { echo; echo "error: exit $exit_code from: $*"
      tail -n +"$((from + 1))" "$RUN_LOG" | tail -n 40
      echo "(last 40 lines; everything this run printed: $RUN_LOG)"; } >&2
    exit "$exit_code"
  fi
}

args_parse() {
  VERBOSE=0
  case "${1:-}" in
    -h|--help) usage_show; exit 0;;
    --verbose) VERBOSE=1; shift;;
  esac
  BASE_DIR=diff2html_baseline_report
  MOD_DIR=diff2html_modified_report
  OUT_DIR=diff2html_diff_report
  case $# in
    0) ;;
    1) OUT_DIR="$1";;
    2) BASE_DIR="$1"; MOD_DIR="$2";;
    3) BASE_DIR="$1"; MOD_DIR="$2"; OUT_DIR="$3";;
    *) usage_show >&2; exit 2;;
  esac
  local dir
  for dir in BASE_DIR MOD_DIR OUT_DIR; do
    case "${!dir}" in
      "~/"*) printf -v "$dir" '%s' "$HOME/${!dir#"~/"}";;
      /*) ;;
      *) printf -v "$dir" '%s' "$PWD/${!dir}";;
    esac
  done
}

profile_of() {
  local files=()
  shopt -s nullglob
  files=("$1"/raw/callgrind.out.*)
  shopt -u nullglob
  if [ "${#files[@]}" != 1 ]; then
    echo "error: expected one raw/callgrind.out.* (a perf2html.sh report) in $1, found ${#files[@]}" >&2
    exit 2
  fi
  echo "${files[0]}"
}

main() {
  args_parse "$@"
  command -v python3 >/dev/null 2>&1 || { echo "error: python3 not found on PATH" >&2; exit 1; }
  local base_file mod_file test name diff_file
  base_file="$(profile_of "$BASE_DIR")"
  mod_file="$(profile_of "$MOD_DIR")"
  test="$(basename "$base_file")"
  test="${test#callgrind.out.}"
  test="${test%%.*}"
  name="$test diff"
  diff_file="$PWD/trace/callgrind.diff.$test.$STAMP"
  mkdir -p "$OUT_DIR" trace
  [ "$VERBOSE" = 1 ] || echo "dev/perf2html_diff.sh $STAMP: $base_file -> $mod_file -> $OUT_DIR" >"$RUN_LOG"
  [ "$VERBOSE" = 1 ] || printf '%-11s%s -> %s\n' diff "$(basename "$BASE_DIR")" "$(basename "$MOD_DIR")"

  log_say "== 1: diff -> $diff_file =="
  test_run python3 scripts/callgrind_diff.py "$base_file" "$mod_file" -o "$diff_file"

  log_say "== 2: heat map -> $OUT_DIR/heat-map/index.html =="
  test_run python3 scripts/callgrind_to_heatmap.py "$diff_file" -o "$OUT_DIR/heat-map/index.html" \
    --title "$name / heat map" --diff

  log_say "== 3: index -> $OUT_DIR/index.html =="
  rm -rf "$OUT_DIR/raw"
  mkdir -p "$OUT_DIR/raw"
  cp "$diff_file" "$OUT_DIR/raw/"
  test_run python3 scripts/build_report.py test "$diff_file" -o "$OUT_DIR/index.html" --test "$name" --diff \
    --raw-data "$OUT_DIR/raw/$(basename "$diff_file")" --meta "baseline=$base_file" --meta "modified=$mod_file"
  cp README.md "$OUT_DIR/README.md"

  log_say "== 4: validate $OUT_DIR =="
  test_run python3 scripts/validate_report.py "$OUT_DIR" --diff
  echo "file://$OUT_DIR/index.html"
}

main "$@"
