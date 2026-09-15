#!/usr/bin/env bash
# curl perf profiling pipeline.
#
#   dev/profile.sh [--verbose] [OUTDIR] [PERFTEST|all] [COMPILER FLAGS...]
#
#   --verbose  show everything the tools print (cmake, ninja, valgrind, the
#              perf binary, the page generators) under a "== N: ..." banner
#              per step. Recognised as the first argument only. Without it
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

# ---------------------------------------------------------------------------
# Output. --verbose: `log_say` prints the step banners and every command prints
# as it does. Otherwise `log_status` builds one line per thing -- the build, each
# test, the merged report -- as its steps finish, `log_run` and `log_capture` send
# what the commands print to RUN_LOG, and only a failing command's output
# reaches the terminal.
log_say() { if [ "$VERBOSE" = 1 ]; then echo "$@"; fi; }
# shellcheck disable=SC2059  # status FORMAT ARGS...
log_status() { if [ "$VERBOSE" != 1 ]; then local fmt="$1"; shift; printf "$fmt" "$@"; fi; }

log_run() {
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

log_capture() { if [ "$VERBOSE" = 1 ]; then tee "$1"; else tee "$1" >>"$RUN_LOG"; fi; }  # stdin -> FILE
log_fail() { { [ "$VERBOSE" = 1 ] || echo; echo "error: $*"; } >&2; exit 1; }
log_took() { local s=$(( SECONDS - $1 )); if [ "$s" -ge 60 ]; then echo "$((s / 60))m$((s % 60))s"; else echo "${s}s"; fi; }
# a native run's lines worth a status line, as "Time/URL: 137.66 ns, Errors: 1240000"
log_perf_summary() { awk '/^(Time\/[A-Za-z]+|Errors):/ { $1 = $1; s = s (s ? ", " : "") $0 } END { print s }' "$1"; }

test_all() {
  sed -n '/^TESTS_C *=/,/^$/p' tests/perf/Makefile.inc | grep -o '[A-Za-z0-9_]*\.c' | sed 's/\.c$//' | sort
}

test_loops() {
  case "$1" in
    urlparser) echo "${CALLGRIND_LOOPS:-200}";;
    *) echo "${CALLGRIND_LOOPS:-200000}";;
  esac
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
    TESTS=($(test_all))
  else
    if ! test_all | grep -qx -- "$TEST"; then
      echo "error: unknown perf test '$TEST'; known: $(test_all | tr '\n' ' ')all" >&2
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
  log_status '%-13s%s -O2 -g%s, %s' build "$BUILD_DIR" "${CFLAGS_EXTRA[*]:+ ${CFLAGS_EXTRA[*]}}" "$CCACHE"
  local t0=$SECONDS
  # CMAKE_C_FLAGS is passed every time (possibly empty) so a previous run's
  # flags never linger in the cache.
  log_run cmake -S . -B "$BUILD_DIR" -G Ninja -DCURL_USE_LIBPSL=OFF -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    "${LAUNCHER[@]}" -DCMAKE_C_FLAGS="${CFLAGS_EXTRA[*]}"
  log_run cmake --build "$BUILD_DIR" --parallel
  log_run cmake --build "$BUILD_DIR" --target perf
  log_status ' %s | log %s\n' "$(log_took "$t0")" "${RUN_LOG#"$REPO_ROOT"/}"
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
  log_run python3 dev/scripts/callgrind_to_speedscope.py "${CG_FILES[@]}" -o "$json" "${ev_args[@]}" --name "$ss_name"
  rm -rf "$out/flame-graph"
  mkdir -p "$out/flame-graph"
  cp -r "$SPEEDSCOPE_RELEASE"/. "$out/flame-graph"/
  log_run python3 dev/scripts/build_flame_graph.py --speedscope-dir "$out/flame-graph" --profile-json "$json"

  log_say "== 5 [$name]: heat map -> $out/heat-map/index.html =="
  log_run python3 dev/scripts/callgrind_to_heatmap.py "${CG_FILES[@]}" -o "$out/heat-map/index.html" \
    --title "$name / heat map"

  log_say "== 6 [$name]: index -> $out/index.html =="
  log_run python3 dev/scripts/build_report.py timing -o "$out/perf-tool/index.html" --test "$name" \
    --output-file "$out/perf-tool/output.txt" \
    --meta "binary=$BIN" --meta "pinned to=CPU $CPU" --meta "build=$BUILD_DESC"
  for x in "${LOG_FILES[@]}"; do log_args+=(--log "$x"); done

  rm -rf "$out/raw"
  mkdir -p "$out/raw"
  cp "${CG_FILES[@]}" "$out/raw/"
  sed -i "s#$REPO_ROOT/##g" "$out"/raw/*
  for x in "${CG_FILES[@]}"; do raw_args+=(--raw-data "$out/raw/$(basename "$x")"); done
  log_run python3 dev/scripts/build_report.py test "${CG_FILES[@]}" -o "$out/index.html" --test "$name" "${log_args[@]}" "${raw_args[@]}" \
    --meta "generated=$(date '+%Y-%m-%d %H:%M:%S %Z') on $(hostname)"
  log_say "   raw data: ${CG_FILES[*]}"
}

run_one() {
  local test="$1" out="$2"
  local loops cg_out log t0
  loops="$(test_loops "$test")"
  cg_out="$TRACE_DIR/callgrind.out.$test.$loops.$STAMP"
  log="$TRACE_DIR/valgrind.$test.$loops.$STAMP.log"
  mkdir -p "$out/perf-tool"

  log_say "== 2 [$test]: callgrind ${CG_FLAGS[*]} ${CG_EXTRA[*]:-} (pinned to CPU $CPU, loops=$loops) =="
  log_say "   callgrind simulates every instruction (~30-50x slower than native); its"
  log_say "   wall-clock is not a perf number -- the native run below is."
  log_status '%-13scallgrind loops=%s' "$test" "$loops"
  t0=$SECONDS
  log_run "${TASKSET[@]}" valgrind --tool=callgrind "${CG_FLAGS[@]}" "${CG_EXTRA[@]}" \
    --callgrind-out-file="$cg_out" --log-file="$log" \
    "$BIN" "$test" "$loops"
  log_status ' %s | native' "$(log_took "$t0")"

  log_say "== 3 [$test]: native timing run (pinned to CPU $CPU) =="
  {
    echo "\$ ${TASKSET[*]:-} $BIN $test"
    "${TASKSET[@]}" "$BIN" "$test" 2>&1
  } | log_capture "$out/perf-tool/output.txt" || log_fail "$BIN $test failed; its output is in $out/perf-tool/output.txt"
  log_status ' %s | pages' "$(log_perf_summary "$out/perf-tool/output.txt")"

  CG_FILES=("$cg_out")
  LOG_FILES=("$log")
  t0=$SECONDS
  report_render "$test" "$out" "$TRACE_DIR/$test.$loops.$STAMP.speedscope.json" \
    "curl perf $test (loops=$loops, $STAMP)"
  log_status ' %s' "$(log_took "$t0")"
}

# Every test's callgrind run merged into one profile, every native time
# summed (the per-test pages have already been built), then the overview
# index over every test.
run_all() {
  local out="$1" t loops usecs total=0 rows="" args t0
  mkdir -p "$out/perf-tool"
  CG_FILES=()
  LOG_FILES=()
  for t in "${TESTS[@]}"; do
    loops="$(test_loops "$t")"
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
  } | log_capture "$out/perf-tool/output.txt"
  log_status '%-13s%d profiles merged | Time: %s usecs | pages' all "${#TESTS[@]}" "$total"

  t0=$SECONDS
  report_render all "$out" "$TRACE_DIR/all.$STAMP.speedscope.json" \
    "curl perf all ($STAMP)"

  log_say "== 7: overview -> $OUT_DIR/index.html =="
  args=(-o "$OUT_DIR/index.html"
        --meta "generated=$(date '+%Y-%m-%d %H:%M:%S %Z') on $(hostname)"
        --meta "source=$GIT_DESC" --meta "build=$BUILD_DESC"
        --meta "timed=$BIN <test>  (native, pinned to CPU $CPU)"
        --test all)
  for t in "${TESTS[@]}"; do args+=(--test "$t"); done
  log_run python3 dev/scripts/build_report.py overview "${args[@]}"
  log_status ' %s' "$(log_took "$t0")"
}

script_main() {
  args_parse "$@"
  toolchain_check

  mkdir -p "$OUT_DIR" "$TRACE_DIR"
  [ "$VERBOSE" = 1 ] || echo "dev/profile.sh $STAMP: OUTDIR=$OUT_DIR PERFTEST=$TEST${CFLAGS_EXTRA[*]:+ CFLAGS=${CFLAGS_EXTRA[*]}}" >"$RUN_LOG"

  build_compile

  local t
  for t in "${TESTS[@]}"; do
    if [ "$TEST" = all ]; then run_one "$t" "$OUT_DIR/$t"; log_status '\n'
    else run_one "$t" "$OUT_DIR"; fi
  done
  if [ "$TEST" = all ]; then run_all "$OUT_DIR/all"; fi
  log_status ' -> %s\n' "$OUT_DIR/index.html"

  log_say
  log_say "Done: $OUT_DIR/index.html"
}

script_main "$@"
