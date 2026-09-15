#!/usr/bin/env bash
# curl perf profiling pipeline.
#
#   dev/profile.sh [OUTDIR] [PERFTEST|all] [COMPILER FLAGS...]
#
#   OUTDIR     where the HTML report goes (mkdir -p). Default: dev/report.
#              A relative path is taken relative to the caller's cwd.
#   PERFTEST   first argument to the perf binary: one of the tests in
#              tests/perf/Makefile.inc (urlparser, base64enc, ...), or "all"
#              to run every test into OUTDIR/<test>/. Default: all.
#   FLAGS...   everything else is passed to the compiler for a fresh curl
#              build (CMAKE_C_FLAGS), e.g. -DUSE_AVX512. The flags are
#              *reset* on every run, so omitting them builds plain again.
#
#   dev/profile.sh ~/artifacts urlparser -DUSE_AVX512
#
# For each test:
#   1. configure + build the RelWithDebInfo tree (-O2 -g; ccache when found)
#   2. run the test under callgrind with --cache-sim=yes --branch-sim=yes,
#      pinned to one core (unpinned runs on WSL2 vary ~2x)
#   3. run the test natively, pinned, for the real timing numbers
#   4. convert: speedscope flame graph (one profile per event), per-line
#      source heat map, the index page with totals and top-20 functions
#
# Layout of OUTDIR (or OUTDIR/<test>/ with "all"):
#   index.html            toolbar strip over the summary (meta, callgrind
#                         totals, top 20 functions with callers, valgrind
#                         log); the strip loads the pages below into a frame
#   flame-graph/index.html  speedscope, auto-loads the profile
#   heat-map/index.html   per-line heat map with cache-miss columns
#   perf-tool/index.html  native timing run output
# With "all", OUTDIR/index.html is the same kind of page over the tests.
# Raw callgrind data, valgrind log and speedscope JSON stay in dev/trace/.
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

usage() { sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; }
case "${1:-}" in -h|--help) usage; exit 0;; esac

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
CG_FLAGS=(--cache-sim=yes --branch-sim=yes)
# shellcheck disable=SC2206  # word-splitting CALLGRIND_OPTS is the point
CG_EXTRA=(${CALLGRIND_OPTS:-})
# one speedscope profile per expression; ones whose events are missing are skipped
SS_EVENTS=(Ir D1mr+D1mw DLmr+DLmw I1mr Bcm Bim)

all_tests() {
  sed -n '/^TESTS_C *=/,/^$/p' tests/perf/Makefile.inc | grep -o '[A-Za-z0-9_]*\.c' | sed 's/\.c$//'
}
cg_loops() {
  case "$1" in
    urlparser) echo "${CALLGRIND_LOOPS:-200}";;
    *) echo "${CALLGRIND_LOOPS:-200000}";;
  esac
}

if [ "$TEST" = all ]; then
  TESTS=($(all_tests))
else
  if ! all_tests | grep -qx -- "$TEST"; then
    echo "error: unknown perf test '$TEST'; known: $(all_tests | tr '\n' ' ')all" >&2
    exit 2
  fi
  TESTS=("$TEST")
fi

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

mkdir -p "$OUT_DIR" "$TRACE_DIR"

# ---------------------------------------------------------------------------
echo "== 1: configure + build $BUILD_DIR (RelWithDebInfo${CFLAGS_EXTRA[*]:+, CMAKE_C_FLAGS=\"${CFLAGS_EXTRA[*]}\"}) =="
LAUNCHER=()
if command -v ccache >/dev/null 2>&1; then
  LAUNCHER=(-DCMAKE_C_COMPILER_LAUNCHER=ccache)
else
  echo "   note: ccache not found; builds after a flag change will be full rebuilds"
fi
# CMAKE_C_FLAGS is passed every time (possibly empty) so a previous run's
# flags never linger in the cache.
cmake -S . -B "$BUILD_DIR" -G Ninja -DCURL_USE_LIBPSL=OFF -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  "${LAUNCHER[@]}" -DCMAKE_C_FLAGS="${CFLAGS_EXTRA[*]}"
cmake --build "$BUILD_DIR" --parallel
cmake --build "$BUILD_DIR" --target perf
BIN="$BUILD_DIR/tests/perf/perf"
BUILD_DESC="$BUILD_DIR, -O2 -g -DNDEBUG${CFLAGS_EXTRA[*]:+ ${CFLAGS_EXTRA[*]}}, $(${CC:-cc} --version | head -1)"
GIT_DESC="$(git describe --always --dirty 2>/dev/null || echo unknown) on $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo ?)"

# ---------------------------------------------------------------------------
run_one() {
  local test="$1" out="$2"
  local loops cg_out log json native_out
  loops="$(cg_loops "$test")"
  cg_out="$TRACE_DIR/callgrind.out.$test.$loops.$STAMP"
  log="$TRACE_DIR/valgrind.$test.$loops.$STAMP.log"
  json="$TRACE_DIR/$test.$loops.$STAMP.speedscope.json"
  mkdir -p "$out/perf-tool" "$out/heat-map"

  echo "== 2 [$test]: callgrind ${CG_FLAGS[*]} ${CG_EXTRA[*]:-} (pinned to CPU $CPU, loops=$loops) =="
  echo "   callgrind simulates every instruction (~30-50x slower than native); its"
  echo "   wall-clock is not a perf number -- the native run below is."
  "${TASKSET[@]}" valgrind --tool=callgrind "${CG_FLAGS[@]}" "${CG_EXTRA[@]}" \
    --callgrind-out-file="$cg_out" --log-file="$log" \
    "$BIN" "$test" "$loops"

  echo "== 3 [$test]: native timing run (pinned to CPU $CPU) =="
  native_out="$out/perf-tool/output.txt"
  {
    echo "\$ ${TASKSET[*]:-} $BIN $test"
    "${TASKSET[@]}" "$BIN" "$test" 2>&1
  } | tee "$native_out"

  echo "== 4 [$test]: flame graph -> $out/flame-graph/index.html =="
  local ev_args=()
  for e in "${SS_EVENTS[@]}"; do ev_args+=(--event "$e"); done
  python3 dev/scripts/callgrind_to_speedscope.py "$cg_out" -o "$json" "${ev_args[@]}" \
    --name "curl perf $test (loops=$loops, $STAMP)"
  rm -rf "$out/flame-graph"
  mkdir -p "$out/flame-graph"
  cp -r "$SPEEDSCOPE_RELEASE"/. "$out/flame-graph"/
  python3 dev/scripts/build_flame_graph.py --speedscope-dir "$out/flame-graph" --profile-json "$json"

  echo "== 5 [$test]: heat map -> $out/heat-map/index.html =="
  python3 dev/scripts/callgrind_to_heatmap.py "$cg_out" -o "$out/heat-map/index.html" \
    --title "curl perf $test heatmap"

  echo "== 6 [$test]: index -> $out/index.html =="
  python3 dev/scripts/build_report.py timing -o "$out/perf-tool/index.html" --test "$test" \
    --output-file "$native_out" \
    --meta "binary=$BIN" --meta "pinned to=CPU $CPU" --meta "build=$BUILD_DESC"
  python3 dev/scripts/build_report.py test "$cg_out" -o "$out/index.html" --test "$test" --log "$log" \
    --meta "generated=$(date '+%Y-%m-%d %H:%M:%S %Z') on $(hostname)" \
    --meta "source=$GIT_DESC" \
    --meta "build=$BUILD_DESC" \
    --meta "profiled=$BIN $test $loops  (callgrind ${CG_FLAGS[*]} ${CG_EXTRA[*]:-}, pinned to CPU $CPU)" \
    --meta "timed=$BIN $test  (native, pinned to CPU $CPU; the only valid speed number here)" \
    --meta "flame graph=one speedscope profile per event: ${SS_EVENTS[*]}" \
    --meta "raw data=$cg_out"
  echo "   raw data: $cg_out"
}

for t in "${TESTS[@]}"; do
  if [ "$TEST" = all ]; then run_one "$t" "$OUT_DIR/$t"; else run_one "$t" "$OUT_DIR"; fi
done

if [ "$TEST" = all ]; then
  echo "== 7: overview -> $OUT_DIR/index.html =="
  args=(-o "$OUT_DIR/index.html"
        --meta "generated=$(date '+%Y-%m-%d %H:%M:%S %Z') on $(hostname)"
        --meta "source=$GIT_DESC" --meta "build=$BUILD_DESC"
        --meta "timed=$BIN <test>  (native, pinned to CPU $CPU)")
  for t in "${TESTS[@]}"; do args+=(--test "$t"); done
  python3 dev/scripts/build_report.py overview "${args[@]}"
fi

echo
echo "Done: $OUT_DIR/index.html"
