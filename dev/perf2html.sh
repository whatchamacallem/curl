#!/usr/bin/env bash
# dev/perf2html.sh [--verbose] [--keep-raw] [--regenerate] [--report=DIR]
#     [cmake_flags...]
set -euo pipefail
SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$SCRIPT")"

BUILD_DIR=build-relwithdebinfo
TRACE_BUILD_DIR=build-instr
CPU=3
CALLGRIND_LOOPS=200
TIMING_LOOPS=10000
# UINT64_MAX: skip every event, making it a count-only run
TRACE_SKIP_ALL=18446744073709551615
REPORT_MANIFEST='curl/perf2html.sh v1'

REPO="$(cd .. && pwd)"
STAMP="$(date +%s)"

usage_show() {
  awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$SCRIPT"
}

log_say() { if [ "$VERBOSE" = 1 ]; then echo "$@"; fi; }

took() {
  local seconds=$((SECONDS - $1))
  if [ "$seconds" -ge 60 ]; then
    echo "$((seconds / 60))m$((seconds % 60))s"
  else
    echo "${seconds}s"
  fi
}

test_run() {
  if [ "$VERBOSE" = 1 ]; then
    "$@"
    return
  fi
  local exit_code=0 from
  printf '\n$ %s\n' "$*" >>"$RUN_LOG"
  from="$(wc -l <"$RUN_LOG")"
  "$@" >>"$RUN_LOG" 2>&1 || exit_code=$?
  if [ "$exit_code" != 0 ]; then
    {
      echo
      echo "error: exit $exit_code from: $*"
      tail -n +"$((from + 1))" "$RUN_LOG" | tail -n 40
      echo "(last 40 lines; everything this run printed: $RUN_LOG)"
    } >&2
    exit "$exit_code"
  fi
}

args_parse() {
  VERBOSE=0
  KEEP_RAW=0
  REGENERATE=0
  OUT_DIR=""
  while [ $# -gt 0 ]; do
    case "$1" in
      -h | --help)
        usage_show
        exit 0
        ;;
      --verbose)
        VERBOSE=1
        shift
        ;;
      --keep-raw)
        KEEP_RAW=1
        shift
        ;;
      --regenerate)
        REGENERATE=1
        KEEP_RAW=1
        shift
        ;;
      --report=*)
        OUT_DIR="${1#--report=}"
        shift
        ;;
      *) break ;;
    esac
  done
  CMAKE_FLAGS=("$@")
  if [ -z "$OUT_DIR" ]; then
    if [ $# -gt 0 ]; then
      OUT_DIR=perf2html_modified_report
    else
      OUT_DIR=perf2html_baseline_report
    fi
  fi
  case "$OUT_DIR" in
    "~/"*) OUT_DIR="$HOME/${OUT_DIR#"~/"}" ;;
    /*) ;;
    *) OUT_DIR="$PWD/$OUT_DIR" ;;
  esac
  local index seen=0 split=0 flag
  for index in "${!CMAKE_FLAGS[@]}"; do
    flag="${CMAKE_FLAGS[$index]}"
    if [ "$split" = 1 ]; then
      case "$flag" in
        CMAKE_C_FLAGS=*)
          CMAKE_FLAGS[$index]="CMAKE_C_FLAGS=-O2 -g ${flag#CMAKE_C_FLAGS=}"
          seen=1
          ;;
      esac
      split=0
      continue
    fi
    case "$flag" in
      -DCMAKE_C_FLAGS=*)
        CMAKE_FLAGS[$index]="-DCMAKE_C_FLAGS=-O2 -g ${flag#-DCMAKE_C_FLAGS=}"
        seen=1
        ;;
      -D) split=1 ;;
    esac
  done
  [ "$seen" = 1 ] || CMAKE_FLAGS+=("-DCMAKE_C_FLAGS=-O2 -g")
  TESTS=($(sed -n '/^TESTS_C *=/,/^$/p' "$REPO/tests/perf/Makefile.inc" \
    | grep -o '[A-Za-z0-9_]*\.c' | sed 's/\.c$//' | sort))
}

manifest_value() {
  sed -n "s/^$1=//p" "$OUT_DIR/MANIFEST.txt" | head -1
}

stamp_reuse() {
  local manifest="$OUT_DIR/MANIFEST.txt"
  [ -f "$manifest" ] || {
    echo "error: --regenerate needs a previous report at $OUT_DIR" \
      "(no MANIFEST.txt)" >&2
    exit 2
  }
  STAMP="$(manifest_value stamp)"
  [ -n "$STAMP" ] || {
    echo "error: $manifest has no stamp= row, so its raw data cannot" \
      "be identified" >&2
    echo "       (it predates --regenerate; re-run perf2html.sh" \
      "--keep-raw once)" >&2
    exit 2
  }
  local test_name loops missing=()
  for test_name in "${TESTS[@]}"; do
    loops=$CALLGRIND_LOOPS
    for file in "trace/callgrind.out.$test_name.$loops.$STAMP" \
      "trace/valgrind.$test_name.$loops.$STAMP.log" \
      "trace/perf-stat.$test_name.$STAMP.csv" \
      "trace/trace.$test_name.$loops.$STAMP.speedscope.json"; do
      [ -f "$file" ] || missing+=("$file")
    done
  done
  if [ "${#missing[@]}" != 0 ]; then
    {
      echo "error: --regenerate is missing ${#missing[@]} raw file(s)" \
        "for stamp $STAMP:"
      printf '       %s\n' "${missing[@]}"
      echo "       (dev/trace/ was cleaned; re-run perf2html.sh" \
        "--keep-raw to record them again)"
    } >&2
    exit 2
  fi
}

build_manifest() {
  if [ "$REGENERATE" = 1 ]; then
    SAMPLED="$(manifest_value sampled)"
    REVISION="$(manifest_value revision)"
    CPU_MODEL="$(manifest_value cpu)"
    return
  fi
  SAMPLED="$(date +'%Y/%m/%d %H:%M:%S %Z')"
  REVISION="$(cd "$REPO" \
    && git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  if [ "$REVISION" != unknown ] \
    && ! (cd "$REPO" && git diff --quiet HEAD -- 2>/dev/null); then
    REVISION="$REVISION-dirty"
  fi
  CPU_MODEL="$(lscpu | grep -E 'Model name' | head -1 \
    | sed 's/^Model name:[[:space:]]*//')"
}

toolchain_check() {
  local tool
  for tool in cmake ninja ccache cc valgrind perf taskset python3 \
    addr2line readelf speedscope; do
    command -v "$tool" >/dev/null 2>&1 || {
      echo "error: $tool not found on PATH" >&2
      exit 1
    }
  done
  SPEEDSCOPE_RELEASE="$(dirname \
    "$(dirname "$(readlink -f "$(command -v speedscope)")")")/dist/release"
  [ -f "$SPEEDSCOPE_RELEASE/index.html" ] || {
    echo "error: no speedscope bundle at $SPEEDSCOPE_RELEASE" >&2
    exit 1
  }
}

tree_build() {
  local dir="$1"
  shift
  rm -f "$REPO/$dir/CMakeCache.txt"
  test_run cmake -S "$REPO" -B "$REPO/$dir" -G Ninja -DCURL_USE_LIBPSL=OFF \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache "$@"
  test_run cmake --build "$REPO/$dir" --parallel --target perf
}

build_paths() {
  BIN="$REPO/$BUILD_DIR/tests/perf/perf"
  BIN_REL="${BIN#"$REPO"/}"
  TRACE_BIN="$REPO/$TRACE_BUILD_DIR/tests/perf/perf"
  TRACE_BIN_REL="${TRACE_BIN#"$REPO"/}"
}

build_compile() {
  if [ "$REGENERATE" = 1 ]; then
    build_paths
    BUILD_DESC="$(manifest_value build)"
    [ "$VERBOSE" = 1 ] || printf '%-11s%s | reused\n' build "${CMAKE_FLAGS[*]}"
    return
  fi
  log_say "== 1: cmake + build $BUILD_DIR and $TRACE_BUILD_DIR:" \
    "${CMAKE_FLAGS[*]} =="
  [ "$VERBOSE" = 1 ] || printf '%-11s%s' build "${CMAKE_FLAGS[*]}"
  local start=$SECONDS flag trace_flags=()
  tree_build "$BUILD_DIR" "${CMAKE_FLAGS[@]}"
  for flag in "${CMAKE_FLAGS[@]}"; do
    case "$flag" in
      -DCMAKE_C_FLAGS=* | CMAKE_C_FLAGS=*)
        flag="$flag -finstrument-functions"
        ;;
    esac
    trace_flags+=("$flag")
  done
  mkdir -p "$REPO/$TRACE_BUILD_DIR"
  test_run cc -O2 -fcf-protection=none -c cyg_callback.c \
    -o "$REPO/$TRACE_BUILD_DIR/cyg_callback.o"
  rm -f "$REPO/$TRACE_BUILD_DIR/tests/perf/perf"
  local hook="$REPO/$TRACE_BUILD_DIR/cyg_callback.o"
  tree_build "$TRACE_BUILD_DIR" "${trace_flags[@]}" \
    "-DCMAKE_EXE_LINKER_FLAGS=$hook -Wl,--export-dynamic"
  [ "$VERBOSE" = 1 ] || printf ' | %s\n' "$(took "$start")"
  build_paths
  BUILD_DESC="$BUILD_DIR, ${CMAKE_FLAGS[*]}, $(cc --version | head -1)"
}

trace_record() {
  local test="$1" loops="$2" trace_file="$3" skip="$4"
  echo "\$ PERF_TRACE_OUT=$(basename "${trace_file/.$STAMP/}")" \
    "PERF_TRACE_SKIP=$skip taskset -c $CPU $TRACE_BIN_REL $test $loops"
  PERF_TRACE_OUT="$trace_file" PERF_TRACE_SKIP="$skip" \
    taskset -c "$CPU" "$TRACE_BIN" "$test" "$loops" 2>&1
}

trace_render() {
  local test="$1" out="$2" loops="$3"
  local trace_file="$PWD/trace/trace.$test.$loops.$STAMP.bin" seen
  local log="$out/flame-graph/output.txt"
  TRACE_JSON="$PWD/trace/trace.$test.$loops.$STAMP.speedscope.json"

  log_say "== [$test]: native trace, pinned to CPU $CPU, loops=$loops" \
    "-> $out/flame-graph/index.html =="
  if [ "$REGENERATE" = 1 ]; then
    local saved
    saved="$(mktemp)"
    cp "$log" "$saved"
    rm -rf "$out/flame-graph"
    mkdir -p "$out/flame-graph"
    cp -r "$SPEEDSCOPE_RELEASE"/. "$out/flame-graph"/
    cp "$saved" "$log"
    rm -f "$saved"
    test_run python3 scripts/build_flame_graph.py \
      --speedscope-dir "$out/flame-graph" --profile-json "$TRACE_JSON"
    return
  fi
  rm -rf "$out/flame-graph"
  mkdir -p "$out/flame-graph"
  cp -r "$SPEEDSCOPE_RELEASE"/. "$out/flame-graph"/
  {
    echo "# $TRACE_BUILD_DIR = this report's build flags +"
    echo "# -finstrument-functions, linked with dev/cyg_callback.c, which"
    echo "# reads rdtsc at every function enter and exit. Run 1 counts events,"
    echo "# run 2 keeps the ones right after the run's midpoint"
    echo "# (CYG_CALLBACKS_MAX_REC in dev/cyg_callback.c)."
    trace_record "$test" "$loops" "$trace_file" "$TRACE_SKIP_ALL" \
      && seen="$(python3 scripts/trace_to_speedscope.py \
        --seen "$trace_file")" \
      && trace_record "$test" "$loops" "$trace_file" "$((seen / 2))" \
      && python3 scripts/trace_to_speedscope.py "$trace_file" \
        -o "$TRACE_JSON" --name "$test (loops=$loops)" 2>&1 \
      | sed "s#$PWD/trace/##g; s#\\.$STAMP##g"
  } >"$log" || {
    echo "error: the native trace of $test failed; its output is in $log" >&2
    exit 1
  }
  if [ "$VERBOSE" = 1 ]; then cat "$log"; else cat "$log" >>"$RUN_LOG"; fi
  test_run python3 scripts/build_flame_graph.py \
    --speedscope-dir "$out/flame-graph" --profile-json "$TRACE_JSON"
}

report_render() {
  local name="$1" out="$2" json="$3"
  local log_args=() raw_args=() help_args=() log_file cg_file raw_name

  log_say "== [$name]: heat map -> $out/heat-map/index.html =="
  test_run python3 scripts/callgrind_to_heatmap.py "${CALLGRIND_FILES[@]}" \
    -o "$out/heat-map/index.html" \
    --title "$name / heat map"

  log_say "== [$name]: index -> $out/index.html =="
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
  local perf_log_args=(--perf-log "$out/perf-tool/output.txt"
    --trace-log "$out/flame-graph/output.txt")
  if [ "$name" = all ]; then
    log_args+=(--no-log)
    raw_args=()
    perf_log_args=()
  else
    raw_name="$(basename "$json")"
    raw_name="${raw_name/.$STAMP/}"
    cp "$json" "$out/raw/$raw_name"
    raw_args+=(--raw-data "$out/raw/$raw_name")
  fi
  [ "${#TESTS[@]}" -gt 1 ] && help_args=(--help-href ../README.md)
  test_run python3 scripts/build_report.py test "${CALLGRIND_FILES[@]}" \
    -o "$out/index.html" --test "$name" \
    "${perf_log_args[@]}" "${log_args[@]}" "${raw_args[@]}" "${help_args[@]}"
}

run_one() {
  local test="$1" out="$2"
  local loops cg_file log start
  local stat_file="$PWD/trace/perf-stat.$test.$STAMP.csv"
  loops=$CALLGRIND_LOOPS
  cg_file="$PWD/trace/callgrind.out.$test.$loops.$STAMP"
  log="$PWD/trace/valgrind.$test.$loops.$STAMP.log"
  mkdir -p "$out/perf-tool"

  if [ "$REGENERATE" = 1 ]; then
    [ "$VERBOSE" = 1 ] || printf '%-13sloops=%s | reused' "$test" "$loops"
    trace_render "$test" "$out" "$loops"
    CALLGRIND_FILES=("$cg_file")
    LOG_FILES=("$log")
    report_render "$test" "$out" "$TRACE_JSON"
    [ "$VERBOSE" = 1 ] || printf '\n'
    return
  fi

  log_say "== [$test]: callgrind, pinned to CPU $CPU, loops=$loops" \
    "-> $cg_file =="
  [ "$VERBOSE" = 1 ] || printf '%-13sloops=%s' "$test" "$loops"
  start=$SECONDS
  test_run taskset -c "$CPU" valgrind --tool=callgrind --cache-sim=yes \
    --branch-sim=yes \
    --callgrind-out-file="$cg_file" --log-file="$log" "$BIN" "$test" "$loops"
  [ "$VERBOSE" = 1 ] || printf ' | %s' "$(took "$start")"

  log_say "== [$test]: native timing, pinned to CPU $CPU," \
    "loops=$TIMING_LOOPS -> $out/perf-tool/output.txt =="
  {
    echo "\$ perf stat -e cycles:u,instructions:u taskset -c $CPU" \
      "$BIN_REL $test $TIMING_LOOPS"
    perf stat -x, -o "$stat_file" -e cycles:u,instructions:u \
      taskset -c "$CPU" "$BIN" "$test" "$TIMING_LOOPS" 2>&1 \
      && awk -F, '
        $3 ~ /cycles/ { printf "Cycles:    %s\n", $1 }
        $3 ~ /instructions/ { printf "Instructions: %s\n", $1 }' \
        "$stat_file"
  } >"$out/perf-tool/output.txt" \
    || {
      echo "error: $BIN $test failed; its output is in" \
        "$out/perf-tool/output.txt" >&2
      exit 1
    }
  if [ "$VERBOSE" = 1 ]; then
    cat "$out/perf-tool/output.txt"
  else
    cat "$out/perf-tool/output.txt" >>"$RUN_LOG"
    printf ' | %s\n' "$(awk '
      /^Time\/[A-Za-z]+:/ {
        unit = $1
        sub(/^Time\//, "", unit)
        sub(/:$/, "", unit)
        t = $2 " " $3
        sub(/ /, "", t)
        s = t "/" unit
      }
      /^Errors:/ { $1 = $1; s = s (s ? ", " : "") $0 }
      END { print s }' "$out/perf-tool/output.txt")"
  fi

  trace_render "$test" "$out" "$loops"
  CALLGRIND_FILES=("$cg_file")
  LOG_FILES=("$log")
  report_render "$test" "$out" "$TRACE_JSON"
}

run_all() {
  local out="$1"
  local test_name loops usecs total=0 rows="" args
  mkdir -p "$out/perf-tool"
  CALLGRIND_FILES=()
  LOG_FILES=()
  for test_name in "${TESTS[@]}"; do
    loops=$CALLGRIND_LOOPS
    CALLGRIND_FILES+=("$PWD/trace/callgrind.out.$test_name.$loops.$STAMP")
    LOG_FILES+=("$PWD/trace/valgrind.$test_name.$loops.$STAMP.log")
  done

  log_say "== [all]: native timing, every test's run above summed =="
  for test_name in "${TESTS[@]}"; do
    usecs="$(awk '/^Time:/ { print $2; exit }' \
      "$OUT_DIR/$test_name/perf-tool/output.txt")"
    rows+="$(printf '  %-14s %12s usecs' "$test_name:" "${usecs:-?}")"$'\n'
    total=$((total + ${usecs:-0}))
  done
  {
    echo "\$ taskset -c $CPU $BIN_REL <test>"
    echo "#   for every test, one after the other"
    echo "#   (each test's page has its full output)"
    printf '%s' "$rows"
    echo "Time:     $total usecs"
  } >"$out/perf-tool/output.txt"
  [ "$VERBOSE" = 1 ] && cat "$out/perf-tool/output.txt"

  rm -rf "$out/flame-graph"
  report_render all "$out" ""

  log_say "== overview -> $OUT_DIR/index.html =="
  {
    printf '%s\n' "$REPORT_MANIFEST"
    echo "sampled=$SAMPLED"
    echo "revision=$REVISION"
    echo "cpu=$CPU_MODEL"
    echo "build=$BUILD_DESC"
    echo "executable=$BIN_REL <test>  (native, pinned to CPU $CPU)"
    echo "stamp=$STAMP"
  } >"$OUT_DIR/MANIFEST.txt"
  args=(-o "$OUT_DIR/index.html" --header-file "$OUT_DIR/MANIFEST.txt")
  for test_name in "${TESTS[@]}" all; do args+=(--test "$test_name"); done
  test_run python3 scripts/build_report.py overview "${args[@]}"
  [ "$VERBOSE" = 1 ] \
    || printf '%-13s%d profiles merged -> %s\n' all "${#TESTS[@]}" \
      "${OUT_DIR#"$REPO"/}/index.html"
}

main() {
  args_parse "$@"
  toolchain_check
  [ "$KEEP_RAW" = 1 ] || rm -rf trace
  if [ "$REGENERATE" = 1 ]; then stamp_reuse; fi
  build_manifest
  mkdir -p "$OUT_DIR" trace
  if [ "$REGENERATE" = 1 ]; then
    RUN_LOG="$PWD/trace/regenerate.$STAMP.$(date +%s).log"
  else
    RUN_LOG="$PWD/trace/profile.$STAMP.log"
  fi
  cp README.md "$OUT_DIR/README.md"
  [ "$VERBOSE" = 1 ] \
    || echo "dev/perf2html.sh $STAMP: ${CMAKE_FLAGS[*]} -> $OUT_DIR" \
      >"$RUN_LOG"
  build_compile

  local test_name
  for test_name in "${TESTS[@]}"; do
    run_one "$test_name" "$OUT_DIR/$test_name"
  done
  run_all "$OUT_DIR/all"

  if [ "$KEEP_RAW" != 1 ]; then rm -rf trace; fi
  echo "file://$OUT_DIR/index.html"
}

main "$@"
