#!/usr/bin/env bash
# curl perf report differencer. Full docs: dev/perf2html_diff.md (man
# dev/perf2html_diff.md, or dev/perf2html_diff.sh --help for a plain-text dump
# of the same file).
set -euo pipefail

MANIFEST_OURS='curl/perf2html_diff.sh v1'
MANIFEST_THEIRS='curl/perf2html.sh v1'

usage_show() { cat "$(dirname "$0")/perf2html_diff.md"; }

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
  TOP=50
  case "${1:-}" in -h|--help) usage_show; exit 0;; esac
  while true; do
    case "${1:-}" in
      --verbose) VERBOSE=1; shift;;
      --top) TOP="$2"; shift 2;;
      *) break;;
    esac
  done

  if [ $# -lt 2 ]; then
    echo "error: need a BASELINE and a CURRENT report directory (see --help)" >&2
    exit 2
  fi

  INVOKE_DIR="$(pwd)"
  cd "$(dirname "$0")/.."
  REPO_ROOT="$(pwd)"
  DEV_DIR="$REPO_ROOT/dev"

  BASE_DIR="$1"
  CUR_DIR="$2"
  OUT_DIR="${3:-$DEV_DIR/report-diff}"
  local dir
  for dir in BASE_DIR CUR_DIR OUT_DIR; do
    case "${!dir}" in /*) ;; *) printf -v "$dir" '%s' "$INVOKE_DIR/${!dir}";; esac
  done

  TRACE_DIR="$DEV_DIR/trace"
  STAMP="$(date +%s)"
  RUN_LOG="$TRACE_DIR/diff.$STAMP.log"
  EVENT="${DIFF_EVENT:-Ir}"
}

toolchain_check() {
  command -v python3 >/dev/null 2>&1 || { echo "error: python3 not found on PATH" >&2; exit 1; }
}

# A report directory is usable only if its top-level MANIFEST.txt is exactly
# the one newline-terminated line perf2html.sh writes. Our own output carries
# a different manifest: a diff cannot be used to make a diff.
manifest_check() {
  local dir="$1" role="$2" manifest="$1/MANIFEST.txt"
  if [ ! -f "$manifest" ]; then
    echo "error: $role report has no MANIFEST.txt, so it is not a recognized input: $dir" >&2
    echo "       (perf2html.sh writes one; reports made before it did must be regenerated)" >&2
    exit 2
  fi
  if printf '%s\n' "$MANIFEST_OURS" | cmp -s - "$manifest"; then
    echo "error: $role report was written by perf2html_diff.sh: $dir" >&2
    echo "       A diff cannot be used to make a diff." >&2
    exit 2
  fi
  if ! printf '%s\n' "$MANIFEST_THEIRS" | cmp -s - "$manifest"; then
    echo "error: $role report has an unrecognized MANIFEST.txt: $dir" >&2
    echo "       expected exactly one newline-terminated line: $MANIFEST_THEIRS" >&2
    exit 2
  fi
}

# Every <test>/raw/callgrind.out.* under a report directory, plus the top-level
# raw/ of a single-test report, printed as "<test> <file>[ <file>...]" lines.
# The test name is the directory the raw/ sits in ("." for a single-test
# report, renamed to that report's own title).
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
  cur_tests="$(profiles_list "$CUR_DIR" | cut -d' ' -f1 | sort -u)"
  if [ -z "$base_tests" ]; then
    echo "error: no */raw/callgrind.out.* files in the baseline report: $BASE_DIR" >&2
    exit 2
  fi
  if [ -z "$cur_tests" ]; then
    echo "error: no */raw/callgrind.out.* files in the current report: $CUR_DIR" >&2
    exit 2
  fi
  for name in $(comm -23 <(echo "$base_tests") <(echo "$cur_tests")); do
    echo "note: '$name' is only in the baseline report; skipped" >&2
  done
  for name in $(comm -13 <(echo "$base_tests") <(echo "$cur_tests")); do
    echo "note: '$name' is only in the current report; skipped" >&2
  done
  comm -12 <(echo "$base_tests") <(echo "$cur_tests")
}

profiles_of() {
  profiles_list "$1" | awk -v want="$2" 'found { next } $1 == want { $1 = ""; print substr($0, 2); found = 1 }'
}

# One test's pages: the per-line delta (a callgrind-format file), its heat map
# and its summary. No flame graph (a delta has no call graph) and no native
# timing (two runs' wall clocks do not subtract into one).
diff_one() {
  local test="$1" out="$2" name="$3"
  local diff_file base_files cur_files args
  diff_file="$TRACE_DIR/callgrind.diff.$name.$STAMP"
  base_files="$(profiles_of "$BASE_DIR" "$test")"
  cur_files="$(profiles_of "$CUR_DIR" "$test")"

  log_say "== 1 [$name]: diff -> $diff_file =="
  [ "$VERBOSE" = 1 ] || printf '%-13sdiff' "$name"
  args=(python3 dev/scripts/callgrind_diff.py -o "$diff_file" --repo-root "$REPO_ROOT")
  # shellcheck disable=SC2086  # the file lists are deliberately word-split
  for file in $base_files; do args+=(--baseline "$file"); done
  # shellcheck disable=SC2086
  for file in $cur_files; do args+=(--current "$file"); done
  test_run "${args[@]}"

  log_say "== 2 [$name]: heat map -> $out/heat-map/index.html =="
  test_run python3 dev/scripts/callgrind_to_heatmap.py "$diff_file" -o "$out/heat-map/index.html" \
    --title "$name / heat map" --diff

  log_say "== 3 [$name]: index -> $out/index.html =="
  rm -rf "$out/raw"
  mkdir -p "$out/raw"
  cp "$diff_file" "$out/raw/"
  local help_args=()
  [ "$MULTI" = 1 ] && help_args=(--help-href ../README.md)
  test_run python3 dev/scripts/build_report.py test "$diff_file" -o "$out/index.html" --test "$name" --top "$TOP" \
    --diff --event "$EVENT" --raw-data "$out/raw/$(basename "$diff_file")" \
    --meta "baseline=$(printf '%s' "${base_files% }")" \
    --meta "current=$(printf '%s' "${cur_files% }")" \
    "${help_args[@]}"
  [ "$VERBOSE" = 1 ] || printf ' -> %s\n' "${out#"$REPO_ROOT"/}/index.html"
}

main() {
  args_parse "$@"
  toolchain_check

  manifest_check "$BASE_DIR" baseline
  manifest_check "$CUR_DIR" current

  mkdir -p "$OUT_DIR" "$TRACE_DIR"
  cp "$DEV_DIR/README.md" "$OUT_DIR/README.md"
  printf '%s\n' "$MANIFEST_OURS" >"$OUT_DIR/MANIFEST.txt"
  [ "$VERBOSE" = 1 ] || echo "dev/perf2html_diff.sh $STAMP: BASELINE=$BASE_DIR CURRENT=$CUR_DIR OUTDIR=$OUT_DIR" >"$RUN_LOG"

  local tests test_name args
  tests="$(tests_pair)"
  [ -n "$tests" ] || { echo "error: the two reports have no test in common" >&2; exit 2; }
  MULTI=1
  [ "$tests" = "." ] && MULTI=0

  [ "$VERBOSE" = 1 ] || echo "dev/perf2html_diff.sh $STAMP: $(basename "$BASE_DIR") -> $(basename "$CUR_DIR")"
  if [ "$MULTI" = 0 ]; then
    diff_one . "$OUT_DIR" "$(basename "$CUR_DIR")"
  else
    args=(-o "$OUT_DIR/index.html" --diff --event "$EVENT"
          --meta "generated=$(date '+%Y-%m-%d %H:%M:%S %Z') on $(hostname)"
          --meta "baseline=$BASE_DIR" --meta "current=$CUR_DIR")
    for test_name in $tests; do
      diff_one "$test_name" "$OUT_DIR/$test_name" "$test_name"
      args+=(--test "$test_name")
    done
    log_say "== 4: overview -> $OUT_DIR/index.html =="
    test_run python3 dev/scripts/build_report.py overview "${args[@]}"
    [ "$VERBOSE" = 1 ] || printf '%-13s%s\n' overview "${OUT_DIR#"$REPO_ROOT"/}/index.html"
  fi

  log_say "== 5: validate -> $OUT_DIR =="
  test_run python3 dev/scripts/validate_report.py "$OUT_DIR"

  log_say
  log_say "Done: $OUT_DIR/index.html"
}

main "$@"
