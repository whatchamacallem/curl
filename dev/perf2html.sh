#!/usr/bin/env bash
# dev/perf2html.sh [--verbose] [--report=DIR] [cmake_flags...]
#
# Builds curl (-O2 -g, ccache), runs the urlparser perf test under callgrind
# and then natively, both pinned to one core, and writes an HTML report:
#
#   DIR/index.html    summary: top functions, valgrind log, raw data
#   DIR/flame-graph/  speedscope, opens on the profile
#   DIR/heat-map/     per-line source heat map
#   DIR/perf-tool/    native timing output
#   DIR/raw/          the callgrind file
#   DIR/README.md     help
#
# DIR defaults to diff2html_baseline_report, or diff2html_modified_report when
# cmake_flags are given; a relative DIR is under dev/, ~/ is expanded. cmake_flags are passed
# to cmake as they are, after "-O2 -g" is prepended to a -DCMAKE_C_FLAGS=
# among them or one is added. The build's CMake cache is reset every run, so
# only the flags given apply. --verbose streams every tool's output instead
# of logging it to dev/trace/profile.<ts>.log. The last line printed is the
# report's file:// URL.
set -euo pipefail
SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$SCRIPT")"

BUILD_DIR=build-relwithdebinfo
CPU=3
LOOPS=200
TEST=urlparser

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
    if [ $# -gt 0 ]; then OUT_DIR=diff2html_modified_report; else OUT_DIR=diff2html_baseline_report; fi
  fi
  case "$OUT_DIR" in "~/"*) OUT_DIR="$HOME/${OUT_DIR#"~/"}";; /*) ;; *) OUT_DIR="$PWD/$OUT_DIR";; esac
  local index seen=0
  for index in "${!CMAKE_FLAGS[@]}"; do
    case "${CMAKE_FLAGS[$index]}" in
      -DCMAKE_C_FLAGS=*) CMAKE_FLAGS[$index]="-DCMAKE_C_FLAGS=-O2 -g ${CMAKE_FLAGS[$index]#-DCMAKE_C_FLAGS=}"; seen=1;;
    esac
  done
  [ "$seen" = 1 ] || CMAKE_FLAGS+=("-DCMAKE_C_FLAGS=-O2 -g")
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

profile_run() {
  local start
  CG_FILE="$PWD/trace/callgrind.out.$TEST.$LOOPS.$STAMP"
  LOG_FILE="$PWD/trace/valgrind.$TEST.$LOOPS.$STAMP.log"
  log_say "== 2: callgrind, pinned to CPU $CPU, loops=$LOOPS -> $CG_FILE =="
  [ "$VERBOSE" = 1 ] || printf '%-11sloops=%s' callgrind "$LOOPS"
  start=$SECONDS
  test_run taskset -c "$CPU" valgrind --tool=callgrind --cache-sim=yes --branch-sim=yes \
    --callgrind-out-file="$CG_FILE" --log-file="$LOG_FILE" "$BIN" "$TEST" "$LOOPS"
  [ "$VERBOSE" = 1 ] || printf ' | %s\n' "$(took "$start")"

  log_say "== 3: native timing, pinned to CPU $CPU -> $PERF_OUT =="
  mkdir -p "$OUT_DIR/perf-tool"
  { echo "\$ taskset -c $CPU $BIN $TEST"; taskset -c "$CPU" "$BIN" "$TEST" 2>&1; } >"$PERF_OUT" \
    || { echo "error: $BIN $TEST failed; its output is in $PERF_OUT" >&2; exit 1; }
  if [ "$VERBOSE" = 1 ]; then
    cat "$PERF_OUT"
  else
    cat "$PERF_OUT" >>"$RUN_LOG"
    printf '%-11s%s\n' native "$(awk '
      /^Time\/[A-Za-z]+:/ { unit = $1; sub(/^Time\//, "", unit); sub(/:$/, "", unit); t = $2 " " $3; sub(/ /, "", t); s = t "/" unit }
      /^Errors:/ { $1 = $1; s = s (s ? ", " : "") $0 }
      END { print s }' "$PERF_OUT")"
  fi
}

report_render() {
  local json="$PWD/trace/$TEST.$LOOPS.$STAMP.speedscope.json"
  log_say "== 4: flame graph -> $OUT_DIR/flame-graph/index.html =="
  test_run python3 scripts/callgrind_to_speedscope.py "$CG_FILE" -o "$json"
  rm -rf "$OUT_DIR/flame-graph"
  mkdir -p "$OUT_DIR/flame-graph"
  cp -r "$SPEEDSCOPE_RELEASE"/. "$OUT_DIR/flame-graph"/
  test_run python3 scripts/build_flame_graph.py --speedscope-dir "$OUT_DIR/flame-graph" --profile-json "$json"

  log_say "== 5: heat map -> $OUT_DIR/heat-map/index.html =="
  test_run python3 scripts/callgrind_to_heatmap.py "$CG_FILE" -o "$OUT_DIR/heat-map/index.html" \
    --title "$TEST / heat map"

  log_say "== 6: index -> $OUT_DIR/index.html =="
  test_run python3 scripts/build_report.py timing -o "$OUT_DIR/perf-tool/index.html" --test "$TEST" \
    --output-file "$PERF_OUT" --meta "binary=$BIN" --meta "pinned to=CPU $CPU" --meta "build=$BUILD_DESC"
  rm -rf "$OUT_DIR/raw"
  mkdir -p "$OUT_DIR/raw"
  cp "$CG_FILE" "$OUT_DIR/raw/"
  sed -i "s#$REPO/##g" "$OUT_DIR/raw/"*
  test_run python3 scripts/build_report.py test "$CG_FILE" -o "$OUT_DIR/index.html" --test "$TEST" \
    --log "$LOG_FILE" --raw-data "$OUT_DIR/raw/$(basename "$CG_FILE")"
  cp README.md "$OUT_DIR/README.md"

  log_say "== 7: validate $OUT_DIR =="
  test_run python3 scripts/validate_report.py "$OUT_DIR"
}

main() {
  args_parse "$@"
  toolchain_check
  mkdir -p "$OUT_DIR" trace
  PERF_OUT="$OUT_DIR/perf-tool/output.txt"
  [ "$VERBOSE" = 1 ] || echo "dev/perf2html.sh $STAMP: ${CMAKE_FLAGS[*]} -> $OUT_DIR" >"$RUN_LOG"
  build_compile
  profile_run
  report_render
  echo "file://$OUT_DIR/index.html"
}

main "$@"
