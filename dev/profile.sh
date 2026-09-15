#!/usr/bin/env bash
# curl perf profiling pipeline.
#
#   dev/profile.sh [OUTDIR] [PERFTEST|all] [COMPILER FLAGS...]
#
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

usage() { awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$0"; }
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
  sed -n '/^TESTS_C *=/,/^$/p' tests/perf/Makefile.inc | grep -o '[A-Za-z0-9_]*\.c' | sed 's/\.c$//' | sort
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
# The pages of one report directory: flame graph, heat map, native timing
# page and index, from the callgrind file(s) in CG_FILES, the valgrind
# log(s) in LOG_FILES and the native output at $out/perf-tool/output.txt.
CG_FILES=()
LOG_FILES=()
build_pages() {
  local name="$1" out="$2" json="$3" ss_name="$4"
  local ev_args=() log_args=() raw_args=() x

  echo "== 4 [$name]: flame graph -> $out/flame-graph/index.html =="
  for x in "${SS_EVENTS[@]}"; do ev_args+=(--event "$x"); done
  python3 dev/scripts/callgrind_to_speedscope.py "${CG_FILES[@]}" -o "$json" "${ev_args[@]}" --name "$ss_name"
  rm -rf "$out/flame-graph"
  mkdir -p "$out/flame-graph"
  cp -r "$SPEEDSCOPE_RELEASE"/. "$out/flame-graph"/
  python3 dev/scripts/build_flame_graph.py --speedscope-dir "$out/flame-graph" --profile-json "$json"

  echo "== 5 [$name]: heat map -> $out/heat-map/index.html =="
  python3 dev/scripts/callgrind_to_heatmap.py "${CG_FILES[@]}" -o "$out/heat-map/index.html" \
    --title "$name / heat map"

  echo "== 6 [$name]: index -> $out/index.html =="
  python3 dev/scripts/build_report.py timing -o "$out/perf-tool/index.html" --test "$name" \
    --output-file "$out/perf-tool/output.txt" \
    --meta "binary=$BIN" --meta "pinned to=CPU $CPU" --meta "build=$BUILD_DESC"
  for x in "${LOG_FILES[@]}"; do log_args+=(--log "$x"); done
  
  rm -rf "$out/raw"
  mkdir -p "$out/raw"
  cp "${CG_FILES[@]}" "$out/raw/"
  sed -i "s#$REPO_ROOT/##g" "$out"/raw/*
  for x in "${CG_FILES[@]}"; do raw_args+=(--raw-data "$out/raw/$(basename "$x")"); done
  python3 dev/scripts/build_report.py test "${CG_FILES[@]}" -o "$out/index.html" --test "$name" "${log_args[@]}" "${raw_args[@]}" \
    --meta "generated=$(date '+%Y-%m-%d %H:%M:%S %Z') on $(hostname)"
  echo "   raw data: ${CG_FILES[*]}"
}

run_one() {
  local test="$1" out="$2"
  local loops cg_out log
  loops="$(cg_loops "$test")"
  cg_out="$TRACE_DIR/callgrind.out.$test.$loops.$STAMP"
  log="$TRACE_DIR/valgrind.$test.$loops.$STAMP.log"
  mkdir -p "$out/perf-tool"

  echo "== 2 [$test]: callgrind ${CG_FLAGS[*]} ${CG_EXTRA[*]:-} (pinned to CPU $CPU, loops=$loops) =="
  echo "   callgrind simulates every instruction (~30-50x slower than native); its"
  echo "   wall-clock is not a perf number -- the native run below is."
  "${TASKSET[@]}" valgrind --tool=callgrind "${CG_FLAGS[@]}" "${CG_EXTRA[@]}" \
    --callgrind-out-file="$cg_out" --log-file="$log" \
    "$BIN" "$test" "$loops"

  echo "== 3 [$test]: native timing run (pinned to CPU $CPU) =="
  {
    echo "\$ ${TASKSET[*]:-} $BIN $test"
    "${TASKSET[@]}" "$BIN" "$test" 2>&1
  } | tee "$out/perf-tool/output.txt"

  CG_FILES=("$cg_out")
  LOG_FILES=("$log")
  build_pages "$test" "$out" "$TRACE_DIR/$test.$loops.$STAMP.speedscope.json" \
    "curl perf $test (loops=$loops, $STAMP)"
}

# Every test's callgrind run merged into one profile, every native time
# summed; the per-test pages have already been built.
run_all() {
  local out="$1" t loops usecs total=0
  mkdir -p "$out/perf-tool"
  CG_FILES=()
  LOG_FILES=()
  for t in "${TESTS[@]}"; do
    loops="$(cg_loops "$t")"
    CG_FILES+=("$TRACE_DIR/callgrind.out.$t.$loops.$STAMP")
    LOG_FILES+=("$TRACE_DIR/valgrind.$t.$loops.$STAMP.log")
  done

  echo "== 3 [all]: native timing, every test's run above summed =="
  {
    echo "\$ ${TASKSET[*]:-} $BIN <test>   for every test, one after the other (each test's page has its full output)"
    for t in "${TESTS[@]}"; do
      usecs="$(awk '/^Time:/ { print $2; exit }' "$OUT_DIR/$t/perf-tool/output.txt")"
      printf '%-14s %12s usecs\n' "$t" "${usecs:-?}"
      total=$(( total + ${usecs:-0} ))
    done
    echo "Time:     $total usecs"
  } | tee "$out/perf-tool/output.txt"

  build_pages all "$out" "$TRACE_DIR/all.$STAMP.speedscope.json" \
    "curl perf all ($STAMP)"
}

for t in "${TESTS[@]}"; do
  if [ "$TEST" = all ]; then run_one "$t" "$OUT_DIR/$t"; else run_one "$t" "$OUT_DIR"; fi
done

if [ "$TEST" = all ]; then
  run_all "$OUT_DIR/all"
  echo "== 7: overview -> $OUT_DIR/index.html =="
  args=(-o "$OUT_DIR/index.html"
        --meta "generated=$(date '+%Y-%m-%d %H:%M:%S %Z') on $(hostname)"
        --meta "source=$GIT_DESC" --meta "build=$BUILD_DESC"
        --meta "timed=$BIN <test>  (native, pinned to CPU $CPU)"
        --test all)
  for t in "${TESTS[@]}"; do args+=(--test "$t"); done
  python3 dev/scripts/build_report.py overview "${args[@]}"
fi

echo
echo "Done: $OUT_DIR/index.html"
