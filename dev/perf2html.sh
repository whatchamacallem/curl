#!/usr/bin/env bash
# dev/perf2html.sh [--verbose] [--report=DIR] [cmake_flags...]
#
# Builds curl (-O2 -g, ccache), runs every perf test (tests/perf/*.c) under
# callgrind and then natively, each pinned to one core, and writes one HTML
# report:
#
#   DIR/index.html       overview: cross-test strip, test suites table
#   DIR/<test>/index.html    one test's summary: top functions, valgrind log, raw data
#   DIR/<test>/flame-graph/  speedscope, opens on the profile
#   DIR/<test>/heat-map/     per-line source heat map
#   DIR/<test>/perf-tool/    native timing output
#   DIR/<test>/raw/          the callgrind file
#   DIR/all/                 every test's callgrind data merged into one profile
#   DIR/README.md         help
#   DIR/MANIFEST.txt      "curl/perf2html.sh v1", then the overview's header rows
#                          as LABEL=VALUE lines, for perf2html_diff.sh
#
# DIR defaults to perf2html_baseline_report, or perf2html_modified_report when
# cmake_flags are given; a relative DIR is under dev/, ~/ is expanded. cmake_flags are passed
# to cmake as they are, after "-O2 -g" is prepended to a CMAKE_C_FLAGS setting
# among them (either spelling: -DCMAKE_C_FLAGS=... or -D CMAKE_C_FLAGS=...) or
# one is added. The build's CMake cache is reset every run, so
# only the flags given apply. --verbose streams every tool's output instead
# of logging it to dev/trace/profile.<ts>.log. The last line printed is the
# report's file:// URL. Nothing is validated here -- dev/perf2html_batch.sh runs
# validate_report.py over the finished report.
set -euo pipefail
SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$SCRIPT")"

BUILD_DIR=build-relwithdebinfo
CPU=3
MANIFEST_VERSION='curl/perf2html.sh v1'

REPO="$(cd .. && pwd)"
STAMP="$(date +%s)"
RUN_LOG="$PWD/trace/profile.$STAMP.log"

usage_show() { awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$SCRIPT"; }

log_say() { if [ "$VERBOSE" = 1 ]; then echo "$@"; fi; }

took() {
  local seconds=$(( SECONDS - $1 ))
  if [ "$seconds" -ge 60 ]; then echo "$((seconds / 60))m$((seconds % 60))s"; else echo "${seconds}s"; fi
}

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
  OUT_DIR=""
  while [ $# -gt 0 ]; do
    case "$1" in
      -h|--help) usage_show; exit 0;;
      --verbose) VERBOSE=1; shift;;
      --report=*) OUT_DIR="${1#--report=}"; shift;;
      *) break;;
    esac
  done
  CMAKE_FLAGS=("$@")
  if [ -z "$OUT_DIR" ]; then
    if [ $# -gt 0 ]; then OUT_DIR=perf2html_modified_report; else OUT_DIR=perf2html_baseline_report; fi
  fi
  case "$OUT_DIR" in "~/"*) OUT_DIR="$HOME/${OUT_DIR#"~/"}";; /*) ;; *) OUT_DIR="$PWD/$OUT_DIR";; esac
  # cmake takes a cache entry as one word (-DCMAKE_C_FLAGS=-Os) or two
  # (-D CMAKE_C_FLAGS=-Os); both spellings get "-O2 -g" prepended in place,
  # keeping whichever spelling was written.
  local index seen=0 split=0 flag
  for index in "${!CMAKE_FLAGS[@]}"; do
    flag="${CMAKE_FLAGS[$index]}"
    if [ "$split" = 1 ]; then
      case "$flag" in
        CMAKE_C_FLAGS=*) CMAKE_FLAGS[$index]="CMAKE_C_FLAGS=-O2 -g ${flag#CMAKE_C_FLAGS=}"; seen=1;;
      esac
      split=0
      continue
    fi
    case "$flag" in
      -DCMAKE_C_FLAGS=*) CMAKE_FLAGS[$index]="-DCMAKE_C_FLAGS=-O2 -g ${flag#-DCMAKE_C_FLAGS=}"; seen=1;;
      -D) split=1;;
    esac
  done
  [ "$seen" = 1 ] || CMAKE_FLAGS+=("-DCMAKE_C_FLAGS=-O2 -g")
  TESTS=($(sed -n '/^TESTS_C *=/,/^$/p' "$REPO/tests/perf/Makefile.inc" | grep -o '[A-Za-z0-9_]*\.c' | sed 's/\.c$//' | sort))
}

toolchain_check() {
  local tool
  for tool in cmake ninja ccache valgrind taskset python3 speedscope; do
    command -v "$tool" >/dev/null 2>&1 || { echo "error: $tool not found on PATH" >&2; exit 1; }
  done
  SPEEDSCOPE_RELEASE="$(dirname "$(dirname "$(readlink -f "$(command -v speedscope)")")")/dist/release"
  [ -f "$SPEEDSCOPE_RELEASE/index.html" ] || { echo "error: no speedscope bundle at $SPEEDSCOPE_RELEASE" >&2; exit 1; }
}

build_compile() {
  log_say "== 1: cmake + build $BUILD_DIR: ${CMAKE_FLAGS[*]} =="
  [ "$VERBOSE" = 1 ] || printf '%-11s%s' build "${CMAKE_FLAGS[*]}"
  local start=$SECONDS
  rm -f "$REPO/$BUILD_DIR/CMakeCache.txt"
  test_run cmake -S "$REPO" -B "$REPO/$BUILD_DIR" -G Ninja -DCURL_USE_LIBPSL=OFF \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache "${CMAKE_FLAGS[@]}"
  test_run cmake --build "$REPO/$BUILD_DIR" --parallel --target perf
  [ "$VERBOSE" = 1 ] || printf ' | %s\n' "$(took "$start")"
  BIN="$REPO/$BUILD_DIR/tests/perf/perf"
  BUILD_DESC="$BUILD_DIR, ${CMAKE_FLAGS[*]}, $(cc --version | head -1)"
}

# One test's pages: flame graph, heat map, native timing, index -- from the
# callgrind file(s) in CALLGRIND_FILES, the valgrind log(s) in LOG_FILES and
# the native output already written to $out/perf-tool/output.txt.
report_render() {
  local name="$1" out="$2" json="$3" speedscope_name="$4"
  local log_args=() raw_args=() help_args=() log_file cg_file raw_name

  log_say "== [$name]: flame graph -> $out/flame-graph/index.html =="
  test_run python3 scripts/callgrind_to_speedscope.py "${CALLGRIND_FILES[@]}" -o "$json" --name "$speedscope_name"
  rm -rf "$out/flame-graph"
  mkdir -p "$out/flame-graph"
  cp -r "$SPEEDSCOPE_RELEASE"/. "$out/flame-graph"/
  test_run python3 scripts/build_flame_graph.py --speedscope-dir "$out/flame-graph" --profile-json "$json"

  log_say "== [$name]: heat map -> $out/heat-map/index.html =="
  test_run python3 scripts/callgrind_to_heatmap.py "${CALLGRIND_FILES[@]}" -o "$out/heat-map/index.html" \
    --title "$name / heat map"

  log_say "== [$name]: index -> $out/index.html =="
  test_run python3 scripts/build_report.py timing -o "$out/perf-tool/index.html" --test "$name" \
    --output-file "$out/perf-tool/output.txt" \
    --header "binary=$BIN" --header "pinned to=CPU $CPU" --header "build=$BUILD_DESC"
  rm -rf "$out/raw"
  mkdir -p "$out/raw"
  for cg_file in "${CALLGRIND_FILES[@]}"; do
    raw_name="$(basename "$cg_file")"
    raw_name="${raw_name%.*}"
    cp "$cg_file" "$out/raw/$raw_name"
    raw_args+=(--raw-data "$out/raw/$raw_name")
  done
  sed -i "s#$REPO/##g" "$out"/raw/*
  for log_file in "${LOG_FILES[@]}"; do log_args+=(--log "$log_file"); done
  [ "$name" = all ] && log_args+=(--no-log)
  [ "${#TESTS[@]}" -gt 1 ] && help_args=(--help-href ../README.md)
  test_run python3 scripts/build_report.py test "${CALLGRIND_FILES[@]}" -o "$out/index.html" --test "$name" \
    "${log_args[@]}" "${raw_args[@]}" "${help_args[@]}"
}

run_one() {
  local test="$1" out="$2"
  local loops cg_file log start
  case "$test" in
    urlparser) loops=200;;
    *) loops=200000;;
  esac
  cg_file="$PWD/trace/callgrind.out.$test.$loops.$STAMP"
  log="$PWD/trace/valgrind.$test.$loops.$STAMP.log"
  mkdir -p "$out/perf-tool"

  log_say "== [$test]: callgrind, pinned to CPU $CPU, loops=$loops -> $cg_file =="
  [ "$VERBOSE" = 1 ] || printf '%-13sloops=%s' "$test" "$loops"
  start=$SECONDS
  test_run taskset -c "$CPU" valgrind --tool=callgrind --cache-sim=yes --branch-sim=yes \
    --callgrind-out-file="$cg_file" --log-file="$log" "$BIN" "$test" "$loops"
  [ "$VERBOSE" = 1 ] || printf ' | %s' "$(took "$start")"

  log_say "== [$test]: native timing, pinned to CPU $CPU -> $out/perf-tool/output.txt =="
  { echo "\$ taskset -c $CPU $BIN $test"; taskset -c "$CPU" "$BIN" "$test" 2>&1; } >"$out/perf-tool/output.txt" \
    || { echo "error: $BIN $test failed; its output is in $out/perf-tool/output.txt" >&2; exit 1; }
  if [ "$VERBOSE" = 1 ]; then
    cat "$out/perf-tool/output.txt"
  else
    cat "$out/perf-tool/output.txt" >>"$RUN_LOG"
    printf ' | %s\n' "$(awk '
      /^Time\/[A-Za-z]+:/ { unit = $1; sub(/^Time\//, "", unit); sub(/:$/, "", unit); t = $2 " " $3; sub(/ /, "", t); s = t "/" unit }
      /^Errors:/ { $1 = $1; s = s (s ? ", " : "") $0 }
      END { print s }' "$out/perf-tool/output.txt")"
  fi

  CALLGRIND_FILES=("$cg_file")
  LOG_FILES=("$log")
  report_render "$test" "$out" "$PWD/trace/$test.$loops.$STAMP.speedscope.json" "curl perf $test (loops=$loops)"
}

# Every test's callgrind run merged into one profile, native timing summed
# (the per-test pages have already been built), then the overview index.
run_all() {
  local out="$1"
  local test_name loops usecs total=0 rows="" args
  mkdir -p "$out/perf-tool"
  CALLGRIND_FILES=()
  LOG_FILES=()
  for test_name in "${TESTS[@]}"; do
    case "$test_name" in
      urlparser) loops=200;;
      *) loops=200000;;
    esac
    CALLGRIND_FILES+=("$PWD/trace/callgrind.out.$test_name.$loops.$STAMP")
    LOG_FILES+=("$PWD/trace/valgrind.$test_name.$loops.$STAMP.log")
  done

  log_say "== [all]: native timing, every test's run above summed =="
  for test_name in "${TESTS[@]}"; do
    usecs="$(awk '/^Time:/ { print $2; exit }' "$OUT_DIR/$test_name/perf-tool/output.txt")"
    rows+="$(printf '%-14s %12s usecs' "$test_name:" "${usecs:-?}")"$'\n'
    total=$(( total + ${usecs:-0} ))
  done
  {
    echo "\$ taskset -c $CPU $BIN <test>   for every test, one after the other (each test's page has its full output)"
    printf '%s' "$rows"
    echo "Time:     $total usecs"
  } >"$out/perf-tool/output.txt"
  [ "$VERBOSE" = 1 ] && cat "$out/perf-tool/output.txt"

  report_render all "$out" "$PWD/trace/all.$STAMP.speedscope.json" "curl perf all"

  log_say "== overview -> $OUT_DIR/index.html =="
  { printf '%s\n' "$MANIFEST_VERSION"
    echo "build=$BUILD_DESC"
    echo "timed=$BIN <test>  (native, pinned to CPU $CPU)"; } >"$OUT_DIR/MANIFEST.txt"
  args=(-o "$OUT_DIR/index.html" --header-file "$OUT_DIR/MANIFEST.txt")
  for test_name in "${TESTS[@]}"; do args+=(--test "$test_name"); done
  test_run python3 scripts/build_report.py overview "${args[@]}"
  [ "$VERBOSE" = 1 ] || printf '%-13s%d profiles merged -> %s\n' all "${#TESTS[@]}" "${OUT_DIR#"$REPO"/}/index.html"
}

main() {
  args_parse "$@"
  toolchain_check
  mkdir -p "$OUT_DIR" trace
  cp README.md "$OUT_DIR/README.md"
  [ "$VERBOSE" = 1 ] || echo "dev/perf2html.sh $STAMP: ${CMAKE_FLAGS[*]} -> $OUT_DIR" >"$RUN_LOG"
  build_compile

  local test_name
  for test_name in "${TESTS[@]}"; do
    run_one "$test_name" "$OUT_DIR/$test_name"
  done
  run_all "$OUT_DIR/all"

  echo "file://$OUT_DIR/index.html"
}

main "$@"
