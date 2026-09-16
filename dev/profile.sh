#!/usr/bin/env bash
# curl perf profiling pipeline.
#
#   dev/profile.sh [--verbose] [OUTDIR] [PERFTEST|all] [COMPILER FLAGS...]
#
#   --verbose  show everything the tools print (cmake, ninja, valgrind, the
#              perf binary, the page generators) under a "== N: ..." banner
#              per step. Recognized as the first argument only. Without it
#              the run is one status line per thing -- the build, each test,
#              with "all" the merged report -- built up as its steps finish
#              (ten lines for "all"), the last one ending in the report to
#              open; everything the tools print goes to
#              dev/trace/profile.<ts>.log instead and a failing command's
#              output is shown with the error.
#   OUTDIR     where the HTML report goes (mkdir -p). Default: dev/report.
#              A relative path is taken relative to the caller's cwd.
#   PERFTEST   first argument to the perf binary: one of the tests in
#              tests/perf/Makefile.inc (urlparser, base64enc, ...), or "all"
#              to run every test into OUTDIR/<test>/ plus a combined report
#              over all of them into OUTDIR/all/. Default: all.
#   FLAGS...   everything else is passed to the compiler for a fresh curl
#              build (CMAKE_C_FLAGS), e.g. -DUSE_AVX512. The flags are
#              *reset* on every run, so omitting them builds plain again.
#
#   dev/profile.sh ~/artifacts urlparser -DUSE_AVX512
#   dev/profile.sh --verbose
#
# For each test:
#   1. configure + build the RelWithDebInfo tree (-O2 -g; ccache when found)
#   2. run the test under callgrind with --cache-sim=yes --branch-sim=yes,
#      pinned to one core (unpinned runs on WSL2 vary ~2x)
#   3. run the test natively, pinned, for the real timing numbers
#   4. convert: speedscope flame graph (one profile per event), per-line
#      source heat map, the index page with the top-20 functions
# With "all", the same pages are then built once more over every test's
# callgrind file merged into one profile (the perf binary runs one test per
# process, so the combined profile is the sum of the runs above) and the
# native times summed, into OUTDIR/all/.
#
# Layout of OUTDIR (or OUTDIR/<test>/ with "all"):
#   index.html            strip (title, [summary] [flame graph] [heat map]
#                         [native timing] [reset columns]) over the summary
#                         (meta, top 20 functions with callers, valgrind
#                         log); the strip loads the pages below into a frame
#   flame-graph/index.html  speedscope, auto-loads the profile
#   heat-map/index.html   per-line heat map with cache-miss columns
#   perf-tool/index.html  native timing run output
# With "all", OUTDIR/index.html is the same kind of page over the tests
# ([overview] [all] [base64dec] ... alphabetical, [curl.se/perf] far right).
# Raw callgrind data, valgrind log and speedscope JSON stay in dev/trace/,
# with the quiet run's profile.<ts>.log next to them (same <ts>).
#
# Environment:
#   CALLGRIND_CPU    core to pin to (default 3)
#   CALLGRIND_LOOPS  loop count for the callgrind run (default: 200 for
#                    urlparser, 200000 for the others; callgrind is ~50x
#                    slower than native, so this is not the tool's default)
#   CALLGRIND_OPTS   extra valgrind options, e.g. "--simulate-hwpref=yes
#                    --simulate-wb=yes --cacheuse=yes"
#   PROFILE_BUILD_DIR  build tree (default build-relwithdebinfo)
set -euo pipefail

usage_show() { awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$0"; }

log_say() { if [ "$VERBOSE" = 1 ]; then echo "$@"; fi; }

test_run() {
  if [ "$VERBOSE" = 1 ]; then "$@"; return; fi
  local rc=0 from
  printf '\n$ %s\n' "$*" >>"$RUN_LOG"
  from="$(wc -l <"$RUN_LOG")"
  "$@" >>"$RUN_LOG" 2>&1 || rc=$?
  if [ "$rc" != 0 ]; then
    { echo; echo "error: exit $rc from: $*"
      tail -n +"$((from + 1))" "$RUN_LOG" | tail -n 40
      echo "(last 40 lines; everything this run printed: $RUN_LOG)"; } >&2
    exit "$rc"
  fi
}

args_parse() {
  VERBOSE=0
  case "${1:-}" in --verbose) VERBOSE=1; shift;; esac
  case "${1:-}" in -h|--help) usage_show; exit 0;; esac

  INVOKE_DIR="$(pwd)"
  cd "$(dirname "$0")/.."
  REPO_ROOT="$(pwd)"
  DEV_DIR="$REPO_ROOT/dev"

  OUT_DIR="${1:-$DEV_DIR/report}"
  TEST="${2:-all}"
  shift $(( $# >= 2 ? 2 : $# ))
  CFLAGS_EXTRA=("$@")
  case "$OUT_DIR" in /*) ;; *) OUT_DIR="$INVOKE_DIR/$OUT_DIR";; esac

  CPU="${CALLGRIND_CPU:-3}"
  BUILD_DIR="${PROFILE_BUILD_DIR:-build-relwithdebinfo}"
  TRACE_DIR="$DEV_DIR/trace"
  STAMP="$(date +%s)"
  RUN_LOG="$TRACE_DIR/profile.$STAMP.log"
  CG_FLAGS=(--cache-sim=yes --branch-sim=yes)
  # shellcheck disable=SC2206  # word-splitting CALLGRIND_OPTS is the point
  CG_EXTRA=(${CALLGRIND_OPTS:-})
  # one speedscope profile per expression; ones whose events are missing are skipped
  SS_EVENTS=(Ir D1mr+D1mw DLmr+DLmw I1mr Bcm Bim)

  if [ "$TEST" = all ]; then
    TESTS=($(sed -n '/^TESTS_C *=/,/^$/p' tests/perf/Makefile.inc | grep -o '[A-Za-z0-9_]*\.c' | sed 's/\.c$//' | sort))
  else
    if ! sed -n '/^TESTS_C *=/,/^$/p' tests/perf/Makefile.inc | grep -o '[A-Za-z0-9_]*\.c' | sed 's/\.c$//' | sort | grep -qx -- "$TEST"; then
      echo "error: unknown perf test '$TEST'; known: $(sed -n '/^TESTS_C *=/,/^$/p' tests/perf/Makefile.inc | grep -o '[A-Za-z0-9_]*\.c' | sed 's/\.c$//' | sort | tr '\n' ' ')all" >&2
      exit 2
    fi
    TESTS=("$TEST")
  fi
}

toolchain_check() {
  local tool
  for tool in cmake ninja valgrind python3; do
    command -v "$tool" >/dev/null 2>&1 || { echo "error: $tool not found on PATH" >&2; exit 1; }
  done
  if ! command -v speedscope >/dev/null 2>&1; then
    echo "error: speedscope not found on PATH (npm i -g speedscope)" >&2
    exit 1
  fi
  # speedscope's CLI shim resolves to .../node_modules/speedscope/bin/cli.mjs;
  # its bundled app lives two directories up, at dist/release.
  SPEEDSCOPE_CLI="$(readlink -f "$(command -v speedscope)")"
  SPEEDSCOPE_RELEASE="$(dirname "$(dirname "$SPEEDSCOPE_CLI")")/dist/release"
  if [ ! -f "$SPEEDSCOPE_RELEASE/index.html" ]; then
    echo "error: could not locate speedscope's dist/release directory (looked at: $SPEEDSCOPE_RELEASE)" >&2
    exit 1
  fi
  TASKSET=()
  if command -v taskset >/dev/null 2>&1; then TASKSET=(taskset -c "$CPU"); fi
}

build_compile() {
  log_say "== 1: configure + build $BUILD_DIR (RelWithDebInfo${CFLAGS_EXTRA[*]:+, CMAKE_C_FLAGS=\"${CFLAGS_EXTRA[*]}\"}) =="
  LAUNCHER=()
  CCACHE="no ccache (a flag change is a full rebuild)"
  if command -v ccache >/dev/null 2>&1; then
    LAUNCHER=(-DCMAKE_C_COMPILER_LAUNCHER=ccache)
    CCACHE=ccache
  else
    log_say "   note: ccache not found; builds after a flag change will be full rebuilds"
  fi
  [ "$VERBOSE" = 1 ] || printf '%-13s%s -O2 -g%s, %s' build "$BUILD_DIR" "${CFLAGS_EXTRA[*]:+ ${CFLAGS_EXTRA[*]}}" "$CCACHE"
  local t0=$SECONDS
  # CMAKE_C_FLAGS is passed every time (possibly empty) so a previous run's
  # flags never linger in the cache.
  test_run cmake -S . -B "$BUILD_DIR" -G Ninja -DCURL_USE_LIBPSL=OFF -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    "${LAUNCHER[@]}" -DCMAKE_C_FLAGS="${CFLAGS_EXTRA[*]}"
  test_run cmake --build "$BUILD_DIR" --parallel
  test_run cmake --build "$BUILD_DIR" --target perf
  local elapsed=$(( SECONDS - t0 ))
  local took; if [ "$elapsed" -ge 60 ]; then took="$((elapsed / 60))m$((elapsed % 60))s"; else took="${elapsed}s"; fi
  [ "$VERBOSE" = 1 ] || printf ' %s | log %s\n' "$took" "${RUN_LOG#"$REPO_ROOT"/}"
  BIN="$BUILD_DIR/tests/perf/perf"
  BUILD_DESC="$BUILD_DIR, -O2 -g -DNDEBUG${CFLAGS_EXTRA[*]:+ ${CFLAGS_EXTRA[*]}}, $(${CC:-cc} --version | head -1)"
  GIT_DESC="$(git describe --always --dirty 2>/dev/null || echo unknown) on $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo ?)"
}

# The pages of one report directory: flame graph, heat map, native timing
# page and index, from the callgrind file(s) in CG_FILES, the valgrind
# log(s) in LOG_FILES and the native output at $out/perf-tool/output.txt.
report_render() {
  local name="$1" out="$2" json="$3" ss_name="$4"
  local ev_args=() log_args=() raw_args=() x

  log_say "== 4 [$name]: flame graph -> $out/flame-graph/index.html =="
  for x in "${SS_EVENTS[@]}"; do ev_args+=(--event "$x"); done
  test_run python3 dev/scripts/callgrind_to_speedscope.py "${CG_FILES[@]}" -o "$json" "${ev_args[@]}" --name "$ss_name"
  rm -rf "$out/flame-graph"
  mkdir -p "$out/flame-graph"
  cp -r "$SPEEDSCOPE_RELEASE"/. "$out/flame-graph"/
  test_run python3 dev/scripts/build_flame_graph.py --speedscope-dir "$out/flame-graph" --profile-json "$json"

  log_say "== 5 [$name]: heat map -> $out/heat-map/index.html =="
  test_run python3 dev/scripts/callgrind_to_heatmap.py "${CG_FILES[@]}" -o "$out/heat-map/index.html" \
    --title "$name / heat map"

  log_say "== 6 [$name]: index -> $out/index.html =="
  test_run python3 dev/scripts/build_report.py timing -o "$out/perf-tool/index.html" --test "$name" \
    --output-file "$out/perf-tool/output.txt" \
    --meta "binary=$BIN" --meta "pinned to=CPU $CPU" --meta "build=$BUILD_DESC"
  for x in "${LOG_FILES[@]}"; do log_args+=(--log "$x"); done

  rm -rf "$out/raw"
  mkdir -p "$out/raw"
  cp "${CG_FILES[@]}" "$out/raw/"
  sed -i "s#$REPO_ROOT/##g" "$out"/raw/*
  for x in "${CG_FILES[@]}"; do raw_args+=(--raw-data "$out/raw/$(basename "$x")"); done
  test_run python3 dev/scripts/build_report.py test "${CG_FILES[@]}" -o "$out/index.html" --test "$name" "${log_args[@]}" "${raw_args[@]}" \
    --meta "generated=$(date '+%Y-%m-%d %H:%M:%S %Z') on $(hostname)"
  log_say "   raw data: ${CG_FILES[*]}"
}

run_one() {
  local test="$1" out="$2"
  local loops cg_out log t0 elapsed took perf_out="$out/perf-tool/output.txt"
  case "$test" in
    urlparser) loops="${CALLGRIND_LOOPS:-200}";;
    *) loops="${CALLGRIND_LOOPS:-200000}";;
  esac
  cg_out="$TRACE_DIR/callgrind.out.$test.$loops.$STAMP"
  log="$TRACE_DIR/valgrind.$test.$loops.$STAMP.log"
  mkdir -p "$out/perf-tool"

  log_say "== 2 [$test]: callgrind ${CG_FLAGS[*]} ${CG_EXTRA[*]:-} (pinned to CPU $CPU, loops=$loops) =="
  log_say "   callgrind simulates every instruction (~30-50x slower than native); its"
  log_say "   wall-clock is not a perf number -- the native run below is."
  [ "$VERBOSE" = 1 ] || printf '%-13scallgrind loops=%s' "$test" "$loops"
  t0=$SECONDS
  test_run "${TASKSET[@]}" valgrind --tool=callgrind "${CG_FLAGS[@]}" "${CG_EXTRA[@]}" \
    --callgrind-out-file="$cg_out" --log-file="$log" \
    "$BIN" "$test" "$loops"
  elapsed=$(( SECONDS - t0 ))
  if [ "$elapsed" -ge 60 ]; then took="$((elapsed / 60))m$((elapsed % 60))s"; else took="${elapsed}s"; fi
  [ "$VERBOSE" = 1 ] || printf ' %s | native' "$took"

  log_say "== 3 [$test]: native timing run (pinned to CPU $CPU) =="
  {
    echo "\$ ${TASKSET[*]:-} $BIN $test"
    "${TASKSET[@]}" "$BIN" "$test" 2>&1
  } | { if [ "$VERBOSE" = 1 ]; then tee "$perf_out"; else tee "$perf_out" >>"$RUN_LOG"; fi; } \
    || { { [ "$VERBOSE" = 1 ] || echo; echo "error: $BIN $test failed; its output is in $perf_out"; } >&2; exit 1; }
  # a native run's lines worth a status line, as "Time/URL: 137.66 ns, Errors: 1240000"
  [ "$VERBOSE" = 1 ] || printf ' %s | pages' "$(awk '/^(Time\/[A-Za-z]+|Errors):/ { $1 = $1; s = s (s ? ", " : "") $0 } END { print s }' "$perf_out")"

  CG_FILES=("$cg_out")
  LOG_FILES=("$log")
  t0=$SECONDS
  report_render "$test" "$out" "$TRACE_DIR/$test.$loops.$STAMP.speedscope.json" \
    "curl perf $test (loops=$loops, $STAMP)"
  elapsed=$(( SECONDS - t0 ))
  if [ "$elapsed" -ge 60 ]; then took="$((elapsed / 60))m$((elapsed % 60))s"; else took="${elapsed}s"; fi
  [ "$VERBOSE" = 1 ] || printf ' %s' "$took"
}

# Every test's callgrind run merged into one profile, every native time
# summed (the per-test pages have already been built), then the overview
# index over every test.
run_all() {
  local out="$1"
  local t loops usecs total=0 rows="" args perf_out="$out/perf-tool/output.txt"
  mkdir -p "$out/perf-tool"
  CG_FILES=()
  LOG_FILES=()
  for t in "${TESTS[@]}"; do
    case "$t" in
      urlparser) loops="${CALLGRIND_LOOPS:-200}";;
      *) loops="${CALLGRIND_LOOPS:-200000}";;
    esac
    CG_FILES+=("$TRACE_DIR/callgrind.out.$t.$loops.$STAMP")
    LOG_FILES+=("$TRACE_DIR/valgrind.$t.$loops.$STAMP.log")
  done

  log_say "== 3 [all]: native timing, every test's run above summed =="
  for t in "${TESTS[@]}"; do
    usecs="$(awk '/^Time:/ { print $2; exit }' "$OUT_DIR/$t/perf-tool/output.txt")"
    rows+="$(printf '%-14s %12s usecs' "$t" "${usecs:-?}")"$'\n'
    total=$(( total + ${usecs:-0} ))
  done
  {
    echo "\$ ${TASKSET[*]:-} $BIN <test>   for every test, one after the other (each test's page has its full output)"
    printf '%s' "$rows"
    echo "Time:     $total usecs"
  } | { if [ "$VERBOSE" = 1 ]; then tee "$perf_out"; else tee "$perf_out" >>"$RUN_LOG"; fi; }
  [ "$VERBOSE" = 1 ] || printf '%-13s%d profiles merged | Time: %s usecs' all "${#TESTS[@]}" "$total"

  report_render all "$out" "$TRACE_DIR/all.$STAMP.speedscope.json" \
    "curl perf all ($STAMP)"

  log_say "== 7: overview -> $OUT_DIR/index.html =="
  args=(-o "$OUT_DIR/index.html"
        --meta "generated=$(date '+%Y-%m-%d %H:%M:%S %Z') on $(hostname)"
        --meta "source=$GIT_DESC" --meta "build=$BUILD_DESC"
        --meta "timed=$BIN <test>  (native, pinned to CPU $CPU)"
        --test all)
  for t in "${TESTS[@]}"; do args+=(--test "$t"); done
  test_run python3 dev/scripts/build_report.py overview "${args[@]}"
}

script_main() {
  args_parse "$@"
  toolchain_check

  mkdir -p "$OUT_DIR" "$TRACE_DIR"
  [ "$VERBOSE" = 1 ] || echo "dev/profile.sh $STAMP: OUTDIR=$OUT_DIR PERFTEST=$TEST${CFLAGS_EXTRA[*]:+ CFLAGS=${CFLAGS_EXTRA[*]}}" >"$RUN_LOG"

  build_compile

  local t
  for t in "${TESTS[@]}"; do
    if [ "$TEST" = all ]; then run_one "$t" "$OUT_DIR/$t"; [ "$VERBOSE" = 1 ] || printf '\n'
    else run_one "$t" "$OUT_DIR"; fi
  done
  if [ "$TEST" = all ]; then run_all "$OUT_DIR/all"; fi
  [ "$VERBOSE" = 1 ] || printf ' -> %s\n' "$OUT_DIR/index.html"

  log_say
  log_say "Done: $OUT_DIR/index.html"
}

script_main "$@"
