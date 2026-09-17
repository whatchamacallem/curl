#!/usr/bin/env bash
# curl perf profiling pipeline. Full docs: dev/perf2html.md (man dev/perf2html.md,
# or dev/perf2html.sh --help for a plain-text dump of the same file).
set -euo pipefail

usage_show() { cat "$(dirname "$0")/perf2html.md"; }

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
  CALLGRIND_FLAGS=(--cache-sim=yes --branch-sim=yes)
  # shellcheck disable=SC2206  # word-splitting CALLGRIND_OPTS is the point
  CALLGRIND_EXTRA_FLAGS=(${CALLGRIND_OPTS:-})
  # one speedscope profile per expression; ones whose events are missing are skipped
  SPEEDSCOPE_EVENTS=(Ir D1mr+D1mw DLmr+DLmw I1mr Bcm Bim)

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
  local start_seconds=$SECONDS
  # CMAKE_C_FLAGS is passed every time (possibly empty) so a previous run's
  # flags never linger in the cache.
  test_run cmake -S . -B "$BUILD_DIR" -G Ninja -DCURL_USE_LIBPSL=OFF -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    "${LAUNCHER[@]}" -DCMAKE_C_FLAGS="${CFLAGS_EXTRA[*]}"
  test_run cmake --build "$BUILD_DIR" --parallel
  test_run cmake --build "$BUILD_DIR" --target perf
  local elapsed=$(( SECONDS - start_seconds ))
  local took; if [ "$elapsed" -ge 60 ]; then took="$((elapsed / 60))m$((elapsed % 60))s"; else took="${elapsed}s"; fi
  [ "$VERBOSE" = 1 ] || printf ' %s | log %s\n' "$took" "${RUN_LOG#"$REPO_ROOT"/}"
  BIN="$BUILD_DIR/tests/perf/perf"
  BUILD_DESC="$BUILD_DIR, -O2 -g -DNDEBUG${CFLAGS_EXTRA[*]:+ ${CFLAGS_EXTRA[*]}}, $(${CC:-cc} --version | head -1)"
  GIT_DESC="$(git describe --always --dirty 2>/dev/null || echo unknown) on $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo ?)"
}

# The pages of one report directory: flame graph, heat map, native timing
# page and index, from the callgrind file(s) in CALLGRIND_FILES, the valgrind
# log(s) in LOG_FILES and the native output at $out/perf-tool/output.txt.
report_render() {
  local name="$1" out="$2" json="$3" speedscope_name="$4"
  local event_args=() log_args=() raw_args=() help_args=() event log_file cg_file

  log_say "== 4 [$name]: flame graph -> $out/flame-graph/index.html =="
  for event in "${SPEEDSCOPE_EVENTS[@]}"; do event_args+=(--event "$event"); done
  test_run python3 dev/scripts/callgrind_to_speedscope.py "${CALLGRIND_FILES[@]}" -o "$json" "${event_args[@]}" --name "$speedscope_name"
  rm -rf "$out/flame-graph"
  mkdir -p "$out/flame-graph"
  cp -r "$SPEEDSCOPE_RELEASE"/. "$out/flame-graph"/
  test_run python3 dev/scripts/build_flame_graph.py --speedscope-dir "$out/flame-graph" --profile-json "$json"

  log_say "== 5 [$name]: heat map -> $out/heat-map/index.html =="
  test_run python3 dev/scripts/callgrind_to_heatmap.py "${CALLGRIND_FILES[@]}" -o "$out/heat-map/index.html" \
    --title "$name / heat map"

  log_say "== 6 [$name]: index -> $out/index.html =="
  test_run python3 dev/scripts/build_report.py timing -o "$out/perf-tool/index.html" --test "$name" \
    --output-file "$out/perf-tool/output.txt" \
    --meta "binary=$BIN" --meta "pinned to=CPU $CPU" --meta "build=$BUILD_DESC"
  for log_file in "${LOG_FILES[@]}"; do log_args+=(--log "$log_file"); done

  rm -rf "$out/raw"
  mkdir -p "$out/raw"
  cp "${CALLGRIND_FILES[@]}" "$out/raw/"
  sed -i "s#$REPO_ROOT/##g" "$out"/raw/*
  for cg_file in "${CALLGRIND_FILES[@]}"; do raw_args+=(--raw-data "$out/raw/$(basename "$cg_file")"); done
  [ "$name" = all ] && log_args+=(--no-log)
  # under `all` every test's page sits one directory down from the copy of
  # README.md its strip's "help" link opens
  [ "$TEST" = all ] && help_args=(--help-href ../README.md)
  test_run python3 dev/scripts/build_report.py test "${CALLGRIND_FILES[@]}" -o "$out/index.html" --test "$name" --top "$TOP" \
    "${log_args[@]}" "${raw_args[@]}" "${help_args[@]}"
  log_say "   raw data: ${CALLGRIND_FILES[*]}"
}

run_one() {
  local test="$1" out="$2"
  local loops cg_file log start_seconds elapsed took perf_out="$out/perf-tool/output.txt"
  case "$test" in
    urlparser) loops="${CALLGRIND_LOOPS:-200}";;
    *) loops="${CALLGRIND_LOOPS:-200000}";;
  esac
  cg_file="$TRACE_DIR/callgrind.out.$test.$loops.$STAMP"
  log="$TRACE_DIR/valgrind.$test.$loops.$STAMP.log"
  mkdir -p "$out/perf-tool"

  log_say "== 2 [$test]: callgrind ${CALLGRIND_FLAGS[*]} ${CALLGRIND_EXTRA_FLAGS[*]:-} (pinned to CPU $CPU, loops=$loops) =="
  log_say "   callgrind simulates every instruction (~30-50x slower than native); its"
  log_say "   wall-clock is not a perf number -- the native run below is."
  [ "$VERBOSE" = 1 ] || printf '%-13scallgrind loops=%s' "$test" "$loops"
  start_seconds=$SECONDS
  test_run "${TASKSET[@]}" valgrind --tool=callgrind "${CALLGRIND_FLAGS[@]}" "${CALLGRIND_EXTRA_FLAGS[@]}" \
    --callgrind-out-file="$cg_file" --log-file="$log" \
    "$BIN" "$test" "$loops"
  elapsed=$(( SECONDS - start_seconds ))
  if [ "$elapsed" -ge 60 ]; then took="$((elapsed / 60))m$((elapsed % 60))s"; else took="${elapsed}s"; fi
  [ "$VERBOSE" = 1 ] || printf ' %s' "$took"

  log_say "== 3 [$test]: native timing run (pinned to CPU $CPU) =="
  {
    echo "\$ ${TASKSET[*]:-} $BIN $test"
    "${TASKSET[@]}" "$BIN" "$test" 2>&1
  } | { if [ "$VERBOSE" = 1 ]; then tee "$perf_out"; else tee "$perf_out" >>"$RUN_LOG"; fi; } \
    || { { [ "$VERBOSE" = 1 ] || echo; echo "error: $BIN $test failed; its output is in $perf_out"; } >&2; exit 1; }
  # a native run's Time/<unit> line collapsed to "133.94ns/loop" (or "/URL"),
  # with any Errors: line (urlparser only) appended as ", Errors: 1240000"
  [ "$VERBOSE" = 1 ] || printf ' %s' "$(awk '
    /^Time\/[A-Za-z]+:/ { unit = $1; sub(/^Time\//, "", unit); sub(/:$/, "", unit); t = $2 " " $3; sub(/ /, "", t); s = t "/" unit }
    /^Errors:/ { $1 = $1; s = s (s ? ", " : "") $0 }
    END { print s }' "$perf_out")"

  CALLGRIND_FILES=("$cg_file")
  LOG_FILES=("$log")
  report_render "$test" "$out" "$TRACE_DIR/$test.$loops.$STAMP.speedscope.json" \
    "curl perf $test (loops=$loops, $STAMP)"
}

# Every test's callgrind run merged into one profile, every native time
# summed (the per-test pages have already been built), then the overview
# index over every test.
run_all() {
  local out="$1"
  local test_name loops usecs total=0 rows="" args perf_out="$out/perf-tool/output.txt" start_seconds elapsed took
  start_seconds=$SECONDS
  mkdir -p "$out/perf-tool"
  CALLGRIND_FILES=()
  LOG_FILES=()
  for test_name in "${TESTS[@]}"; do
    case "$test_name" in
      urlparser) loops="${CALLGRIND_LOOPS:-200}";;
      *) loops="${CALLGRIND_LOOPS:-200000}";;
    esac
    CALLGRIND_FILES+=("$TRACE_DIR/callgrind.out.$test_name.$loops.$STAMP")
    LOG_FILES+=("$TRACE_DIR/valgrind.$test_name.$loops.$STAMP.log")
  done

  log_say "== 3 [all]: native timing, every test's run above summed =="
  # "<test>: <n> usecs" -- a "label: value" line, the one shape the report's
  # time_humanize()/value_humanize() rewrite into 5.59s-style durations
  for test_name in "${TESTS[@]}"; do
    usecs="$(awk '/^Time:/ { print $2; exit }' "$OUT_DIR/$test_name/perf-tool/output.txt")"
    rows+="$(printf '%-14s %12s usecs' "$test_name:" "${usecs:-?}")"$'\n'
    total=$(( total + ${usecs:-0} ))
  done
  {
    echo "\$ ${TASKSET[*]:-} $BIN <test>   for every test, one after the other (each test's page has its full output)"
    printf '%s' "$rows"
    echo "Time:     $total usecs"
  } | { if [ "$VERBOSE" = 1 ]; then tee "$perf_out"; else tee "$perf_out" >>"$RUN_LOG"; fi; }

  report_render all "$out" "$TRACE_DIR/all.$STAMP.speedscope.json" \
    "curl perf all ($STAMP)"

  log_say "== 7: overview -> $OUT_DIR/index.html =="
  args=(-o "$OUT_DIR/index.html"
        --meta "generated=$(date '+%Y-%m-%d %H:%M:%S %Z') on $(hostname)"
        --meta "source=$GIT_DESC" --meta "build=$BUILD_DESC"
        --meta "timed=$BIN <test>  (native, pinned to CPU $CPU)"
        --test all)
  for test_name in "${TESTS[@]}"; do args+=(--test "$test_name"); done
  test_run python3 dev/scripts/build_report.py overview "${args[@]}"
  elapsed=$(( SECONDS - start_seconds ))
  if [ "$elapsed" -ge 60 ]; then took="$((elapsed / 60))m$((elapsed % 60))s"; else took="${elapsed}s"; fi
  [ "$VERBOSE" = 1 ] || printf '%-13s%d profiles merged | %s wrote %s' all "${#TESTS[@]}" "$took" "$OUT_DIR/index.html"
}

main() {
  args_parse "$@"
  toolchain_check

  mkdir -p "$OUT_DIR" "$TRACE_DIR"
  cp "$DEV_DIR/README.md" "$OUT_DIR/README.md"
  [ "$VERBOSE" = 1 ] || echo "dev/perf2html.sh $STAMP: OUTDIR=$OUT_DIR PERFTEST=$TEST${CFLAGS_EXTRA[*]:+ CFLAGS=${CFLAGS_EXTRA[*]}}" >"$RUN_LOG"

  build_compile

  local test_name
  for test_name in "${TESTS[@]}"; do
    if [ "$TEST" = all ]; then run_one "$test_name" "$OUT_DIR/$test_name"; [ "$VERBOSE" = 1 ] || printf '\n'
    else run_one "$test_name" "$OUT_DIR"; fi
  done
  if [ "$TEST" = all ]; then
    run_all "$OUT_DIR/all"
    [ "$VERBOSE" = 1 ] || printf '\n'
  else
    [ "$VERBOSE" = 1 ] || printf ' -> %s\n' "$OUT_DIR/index.html"
  fi

  log_say "== 8: validate -> $OUT_DIR =="
  test_run python3 dev/scripts/validate_report.py "$OUT_DIR"

  log_say
  log_say "Done: $OUT_DIR/index.html"
}

main "$@"
