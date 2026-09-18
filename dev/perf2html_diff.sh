#!/usr/bin/env bash
# dev/perf2html_diff.sh [--verbose] [baseline-dir modified-dir] [report-dir]
#
# Subtracts the callgrind data of two perf2html.sh reports (modified minus
# baseline, per function and source line) and writes the change as a report:
#
#   DIR/index.html        summary: top functions by change in self cost, or
#                          (two multi-test reports) an overview across tests
#   DIR/<test>/            one test's diff, same shape, under a multi-test diff
#   DIR/heat-map/          per-line change heat map
#   DIR/raw/               the delta, a callgrind-format file
#   DIR/README.md          help
#   DIR/MANIFEST.txt       "curl/perf2html_diff.sh v1", then this run's header
#                           rows as LABEL=VALUE lines
#
# With no directories, perf2html_baseline_report and perf2html_modified_report
# are compared into perf2html_diff_report. One directory given is the
# report-dir; two are the baseline and modified report-dirs; three are all of
# them, in that order. Relative paths are under dev/, ~/ is expanded. --verbose (first)
# streams every tool's output instead of logging it to dev/trace/diff.<ts>.log.
# The last line printed is the report's file:// URL. Nothing is validated
# here -- dev/perf2html_batch.sh runs validate_report.py over the finished report.
set -euo pipefail
SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$SCRIPT")"

MANIFEST_OURS='curl/perf2html_diff.sh v1'
MANIFEST_THEIRS='curl/perf2html.sh v1'

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
  BASE_DIR=perf2html_baseline_report
  MOD_DIR=perf2html_modified_report
  OUT_DIR=perf2html_diff_report
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

# A report directory is usable only if the first line of its top-level
# MANIFEST.txt is the version string perf2html.sh writes. The LABEL=VALUE
# header rows below that line are not our business here. Our own output carries
# a different version: a diff cannot be used to make a diff.
manifest_check() {
  local dir="$1" role="$2" manifest="$1/MANIFEST.txt" version
  if [ ! -f "$manifest" ]; then
    echo "error: $role report has no MANIFEST.txt, so it is not a recognized input: $dir" >&2
    echo "       (perf2html.sh writes one; reports made before it did must be regenerated)" >&2
    exit 2
  fi
  version="$(head -1 "$manifest")"
  if [ "$version" = "$MANIFEST_OURS" ]; then
    echo "error: can't diff a diff -- the $role report was written by perf2html_diff.sh: $dir" >&2
    exit 2
  fi
  if [ "$version" != "$MANIFEST_THEIRS" ]; then
    echo "error: unrecognized file type -- $role report has an unrecognized MANIFEST.txt: $dir" >&2
    echo "       expected its first line to be: $MANIFEST_THEIRS" >&2
    exit 2
  fi
}

# One side's header rows, as a file of LABEL=VALUE lines for --header-block:
# the source report's own overview rows, which perf2html.sh writes below the
# version line of its MANIFEST.txt, under the directory they came from. A
# report whose manifest is the version line alone contributes the directory.
header_file_of() {
  local dir="$1" role="$2"
  local out="$PWD/trace/header.$role.$STAMP.txt"
  { echo "report=$dir"
    grep '=' "$dir/MANIFEST.txt" || true; } >"$out"
  echo "$out"
}

# Every <test>/raw/callgrind.out.* under a report directory, plus the top-level
# raw/ of a single-test report, printed as "<test> <file>[ <file>...]" lines.
# The test name is the directory the raw/ sits in ("." for a single-test
# report).
profiles_list() {
  local dir="$1" raw test files
  for raw in "$dir"/raw "$dir"/*/raw; do
    [ -d "$raw" ] || continue
    files=$(find "$raw" -maxdepth 1 -type f -name 'callgrind.out.*' | sort | tr '\n' ' ')
    [ -n "$files" ] || continue
    test="$(basename "$(dirname "$raw")")"
    [ "$test" = "$(basename "$dir")" ] && test=.
    echo "$test $files"
  done
}

# The tests both reports have, as "<name>" lines; a test only one side has is
# reported and skipped.
tests_pair() {
  local base_tests cur_tests name
  base_tests="$(profiles_list "$BASE_DIR" | cut -d' ' -f1 | sort -u)"
  cur_tests="$(profiles_list "$MOD_DIR" | cut -d' ' -f1 | sort -u)"
  if [ -z "$base_tests" ]; then
    echo "error: no */raw/callgrind.out.* files in the baseline report: $BASE_DIR" >&2
    exit 2
  fi
  if [ -z "$cur_tests" ]; then
    echo "error: no */raw/callgrind.out.* files in the modified report: $MOD_DIR" >&2
    exit 2
  fi
  for name in $(comm -23 <(echo "$base_tests") <(echo "$cur_tests")); do
    echo "note: '$name' is only in the baseline report; skipped" >&2
  done
  for name in $(comm -13 <(echo "$base_tests") <(echo "$cur_tests")); do
    echo "note: '$name' is only in the modified report; skipped" >&2
  done
  comm -12 <(echo "$base_tests") <(echo "$cur_tests")
}

profiles_of() {
  profiles_list "$1" | awk -v want="$2" 'found { next } $1 == want { $1 = ""; print substr($0, 2); found = 1 }'
}

# One test's pages: the per-line delta (a callgrind-format file), its heat map
# and its summary. No flame graph (a delta has no call graph) and no native
# timing (two runs' wall clocks do not subtract).
diff_one() {
  local test="$1" out="$2" name="$3"
  local diff_file base_files cur_files args help_args=() raw_name
  diff_file="$PWD/trace/callgrind.diff.$name.$STAMP"
  base_files="$(profiles_of "$BASE_DIR" "$test")"
  cur_files="$(profiles_of "$MOD_DIR" "$test")"

  log_say "== [$name]: diff -> $diff_file =="
  [ "$VERBOSE" = 1 ] || printf '%-13sdiff' "$name"
  args=(python3 scripts/callgrind_diff.py -o "$diff_file")
  # shellcheck disable=SC2086  # the file lists are deliberately word-split
  for file in $base_files; do args+=(--baseline "$file"); done
  # shellcheck disable=SC2086
  for file in $cur_files; do args+=(--current "$file"); done
  test_run "${args[@]}"

  log_say "== [$name]: heat map -> $out/heat-map/index.html =="
  test_run python3 scripts/callgrind_to_heatmap.py "$diff_file" -o "$out/heat-map/index.html" \
    --title "$name / heat map" --diff

  log_say "== [$name]: index -> $out/index.html =="
  rm -rf "$out/raw"
  mkdir -p "$out/raw"
  raw_name="$(basename "$diff_file")"
  raw_name="${raw_name%.*}"
  cp "$diff_file" "$out/raw/$raw_name"
  [ "$MULTI" = 1 ] && help_args=(--help-href ../README.md)
  test_run python3 scripts/build_report.py test "$diff_file" -o "$out/index.html" --test "$name" --diff \
    --raw-data "$out/raw/$raw_name" \
    --header "baseline=$(printf '%s' "${base_files% }")" --header "modified=$(printf '%s' "${cur_files% }")" \
    "${help_args[@]}"
  [ "$VERBOSE" = 1 ] || printf ' -> %s\n' "${out#"$PWD"/}/index.html"
}

main() {
  args_parse "$@"
  command -v python3 >/dev/null 2>&1 || { echo "error: python3 not found on PATH" >&2; exit 1; }

  manifest_check "$BASE_DIR" baseline
  manifest_check "$MOD_DIR" modified

  mkdir -p "$OUT_DIR" trace
  cp README.md "$OUT_DIR/README.md"
  { printf '%s\n' "$MANIFEST_OURS"
    echo "baseline=$BASE_DIR"
    echo "modified=$MOD_DIR"; } >"$OUT_DIR/MANIFEST.txt"
  [ "$VERBOSE" = 1 ] || echo "dev/perf2html_diff.sh $STAMP: $BASE_DIR -> $MOD_DIR -> $OUT_DIR" >"$RUN_LOG"

  local tests test_name args
  tests="$(tests_pair)"
  [ -n "$tests" ] || { echo "error: the two reports have no test in common" >&2; exit 2; }
  MULTI=1
  [ "$tests" = "." ] && MULTI=0

  [ "$VERBOSE" = 1 ] || echo "dev/perf2html_diff.sh $STAMP: $(basename "$BASE_DIR") -> $(basename "$MOD_DIR")"
  if [ "$MULTI" = 0 ]; then
    local base_file test_name
    base_file="$(profiles_of "$BASE_DIR" .)"
    test_name="$(basename "${base_file%% *}")"
    test_name="${test_name#callgrind.out.}"
    test_name="${test_name%%.*}"
    diff_one . "$OUT_DIR" "$test_name diff"
  else
    args=(-o "$OUT_DIR/index.html" --diff
          --header-block "baseline=$(header_file_of "$BASE_DIR" baseline)"
          --header-block "modified=$(header_file_of "$MOD_DIR" modified)")
    for test_name in $tests; do
      diff_one "$test_name" "$OUT_DIR/$test_name" "$test_name"
      args+=(--test "$test_name")
    done
    log_say "== overview -> $OUT_DIR/index.html =="
    test_run python3 scripts/build_report.py overview "${args[@]}"
    [ "$VERBOSE" = 1 ] || printf '%-13s%s\n' overview "${OUT_DIR#"$PWD"/}/index.html"
  fi

  echo "file://$OUT_DIR/index.html"
}

main "$@"
