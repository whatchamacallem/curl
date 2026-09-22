#!/usr/bin/env bash

# No usage docs allowed here.

set -euo pipefail
SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$SCRIPT")"

. ./scripts/shared.sh

REPO="$(cd .. && pwd)"
TIMESTAMP="$(date +%s)"

usage_show() {
  cat <<'EOF'
perf2html_batch.sh [debug-flags] [--target-dir=DIR] [cmake-flags...]
    Profiles baseline, modified and then does a diff of them.
    --target-dir=DIR  holds the three default-named reports (default CWD). The
                      batch cannot rename them.
    cmake-flags       every argument not one of its own options, applied to the
                      modified build (default -D CMAKE_C_FLAGS=-Os).

  debug-flags:
    --artifacts=TMP   The profiler artifacts directory. Defaults to
                      perf2html_temporary_artifacts/ beside the report
                      directory (inside the target dir for a batch).
    --keep-artifacts  Do not delete the profiler artifacts directory after use.
                      Required for a later --regenerate.
    --regenerate      Rebuilds all pages from the last run's profiler
                      artifacts, re-measuring nothing. Implies
                      --keep-artifacts.
    --verbose         additive: whatever quiet prints, verbose prints too, plus
                      each child's output as produced.
EOF
}

# args_parse - reads the command line into the run's settings and $TESTS.
args_parse() {
  VERBOSE=0
  KEEP_ARTIFACTS=0
  REGENERATE=0
  OUT_DIR=""
  ARTIFACTS_DIR=""
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
      --keep-artifacts)
        KEEP_ARTIFACTS=1
        shift
        ;;
      --regenerate)
        REGENERATE=1
        KEEP_ARTIFACTS=1
        shift
        ;;
      --report=*)
        OUT_DIR="${1#--report=}"
        shift
        ;;
      --artifacts=*)
        ARTIFACTS_DIR="${1#--artifacts=}"
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
  OUT_DIR="$(absolute_path "$OUT_DIR")"
  if [ -z "$ARTIFACTS_DIR" ]; then
    ARTIFACTS_DIR="$(dirname "$OUT_DIR")/$ARTIFACTS_NAME"
  fi
  ARTIFACTS_DIR="$(absolute_path "$ARTIFACTS_DIR")"
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

# stamp_reuse - takes $TIMESTAMP back from a verified report, for --regenerate.
stamp_reuse() {
  local manifest="$OUT_DIR/MANIFEST.txt"
  # a report is only a report if its version line and its recorded
  # checksum both still hold, so --regenerate cannot read back a tree an
  # aborted run or a later edit left behind
  manifest_verify "$OUT_DIR" "$REPORT_MANIFEST" "--regenerate input"
  TIMESTAMP="$(manifest_value "$OUT_DIR" stamp)"
  [ -n "$TIMESTAMP" ] || {
    echo "error: $manifest has no stamp= row, so its recordings" \
      "cannot be identified" >&2
    echo "       (it predates --regenerate; re-run perf2html.sh" \
      "--keep-artifacts once)" >&2
    exit 2
  }
  local test_name loops missing=() dir="$ARTIFACTS_DIR"
  for test_name in "${TESTS[@]}"; do
    loops=$CALLGRIND_LOOPS
    for file in "$dir/callgrind.out.$test_name.$loops.$TIMESTAMP" \
      "$dir/valgrind.$test_name.$loops.$TIMESTAMP.log" \
      "$dir/perf-stat.$test_name.$TIMESTAMP.csv" \
      "$dir/trace.$test_name.$loops.$TIMESTAMP.speedscope.json"; do
      [ -f "$file" ] || missing+=("$file")
    done
  done
  if [ "${#missing[@]}" != 0 ]; then
    {
      echo "error: --regenerate is missing ${#missing[@]} recorded" \
        "file(s) for stamp $TIMESTAMP:"
      printf '       %s\n' "${missing[@]}"
      echo "       ($ARTIFACTS_DIR was cleaned; re-run" \
        "perf2html.sh --keep-artifacts to record them again)"
    } >&2
    exit 2
  fi
}

# build_manifest - collects the rows describing what was measured and how.
build_manifest() {
  if [ "$REGENERATE" = 1 ]; then
    SAMPLED="$(manifest_value "$OUT_DIR" sampled)"
    REVISION="$(manifest_value "$OUT_DIR" revision)"
    CPU_MODEL="$(manifest_value "$OUT_DIR" cpu)"
    # build_compile wants this one, and runs after main has dropped the
    # manifest. Every read of the previous run's rows happens here.
    BUILD_DESC="$(manifest_value "$OUT_DIR" build)"
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

# tree_build - configures and builds one tree's perf target from scratch.
tree_build() {
  local dir="$1"
  shift
  rm -f "$REPO/$dir/CMakeCache.txt"
  command_run cmake -S "$REPO" -B "$REPO/$dir" -G Ninja -DCURL_USE_LIBPSL=OFF \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache "$@"
  command_run cmake --build "$REPO/$dir" --parallel --target perf
}

# build_paths - the two perf binaries, absolute and repo-relative.
build_paths() {
  BIN="$REPO/$BUILD_DIR/tests/perf/perf"
  BIN_REL="${BIN#"$REPO"/}"
  TRACE_BIN="$REPO/$TRACE_BUILD_DIR/tests/perf/perf"
  TRACE_BIN_REL="${TRACE_BIN#"$REPO"/}"
}

# build_compile - builds both trees, the traced one with the hook linked in.
build_compile() {
  if [ "$REGENERATE" = 1 ]; then
    build_paths
    printf '%-11s%s | reused\n' build "${CMAKE_FLAGS[*]}"
    return
  fi
  log_verbose "== 1: cmake + build $BUILD_DIR and $TRACE_BUILD_DIR:" \
    "${CMAKE_FLAGS[*]} =="
  local line
  line="$(printf '%-11s%s' build "${CMAKE_FLAGS[*]}")"
  local start flag trace_flags=()
  start="$(clock_microseconds)"
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
  command_run cc -O2 -fcf-protection=none -c cyg_callback.c \
    -o "$REPO/$TRACE_BUILD_DIR/cyg_callback.o"
  rm -f "$REPO/$TRACE_BUILD_DIR/tests/perf/perf"
  local hook="$REPO/$TRACE_BUILD_DIR/cyg_callback.o"
  tree_build "$TRACE_BUILD_DIR" "${trace_flags[@]}" \
    "-DCMAKE_EXE_LINKER_FLAGS=$hook -Wl,--export-dynamic"
  printf '%s | %s\n' "$line" "$(duration_format "$start")"
  build_paths
  BUILD_DESC="$BUILD_DIR, ${CMAKE_FLAGS[*]}, $(cc --version | head -1)"
}

# trace_record - one pinned run of the traced binary, writing a trace file.
trace_record() {
  local test="$1" loops="$2" trace_file="$3" skip="$4"
  echo "\$ PERF_TRACE_OUT=$(basename "${trace_file/.$TIMESTAMP/}")" \
    "PERF_TRACE_SKIP=$skip taskset -c $CPU $TRACE_BIN_REL $test $loops"
  PERF_TRACE_OUT="$trace_file" PERF_TRACE_SKIP="$skip" \
    taskset -c "$CPU" "$TRACE_BIN" "$test" "$loops" 2>&1
}

# flame_app_install - copies the speedscope files a page loads, one per glob.
flame_app_install() {
  local out="$1"
  local pattern found=()
  rm -rf "$out/$FLAME_APP_DIR"
  mkdir -p "$out/$FLAME_APP_DIR"
  for pattern in "${FLAME_APP_FILES[@]}"; do
    # shellcheck disable=SC2206  # the glob is the point
    found=($SPEEDSCOPE_RELEASE/$pattern)
    [ "${#found[@]}" = 1 ] && [ -e "${found[0]}" ] || {
      echo "error: $pattern matched ${#found[@]} files in" \
        "$SPEEDSCOPE_RELEASE, expected exactly 1" >&2
      exit 1
    }
    cp "${found[@]}" "$out/$FLAME_APP_DIR"/
    case "$pattern" in
      *.js) FLAME_APP_JS="$(basename "${found[0]}")" ;;
      *.css) FLAME_APP_CSS="$(basename "${found[0]}")" ;;
    esac
  done
}

# trace_render - counting run, then sampling run, then the flame graph page.
trace_render() {
  local test="$1" out="$2" loops="$3"
  local seen
  local trace_file="$ARTIFACTS_DIR/trace.$test.$loops.$TIMESTAMP.bin"
  local log="$out/flame-graph/output.txt"
  TRACE_JSON="$ARTIFACTS_DIR/trace.$test.$loops"
  TRACE_JSON="$TRACE_JSON.$TIMESTAMP.speedscope.json"

  log_verbose "== [$test]: native trace, pinned to CPU $CPU, loops=$loops" \
    "-> $out/flame-graph/index.html =="
  if [ "$REGENERATE" = 1 ]; then
    local saved
    saved="$(mktemp)"
    cp "$log" "$saved"
    rm -rf "$out/flame-graph"
    mkdir -p "$out/flame-graph"
    cp "$saved" "$log"
    rm -f "$saved"
    command_run python3 scripts/build_flame_graph.py \
      --flame-graph-dir "$out/flame-graph" --profile-json "$TRACE_JSON" \
      --app-href "../../$FLAME_APP_DIR" \
      --app-js "$FLAME_APP_JS" --app-css "$FLAME_APP_CSS"
    return
  fi
  rm -rf "$out/flame-graph"
  mkdir -p "$out/flame-graph"
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
      | sed "s#$ARTIFACTS_DIR/##g; s#\\.$TIMESTAMP##g"
  } >"$log" || {
    echo "error: the native trace of $test failed; its output is in $log" >&2
    exit 1
  }
  cat "$log" >>"$RUN_LOG"
  if [ "$VERBOSE" = 1 ]; then cat "$log"; fi
  command_run python3 scripts/build_flame_graph.py \
    --flame-graph-dir "$out/flame-graph" --profile-json "$TRACE_JSON" \
    --app-href "../../$FLAME_APP_DIR" \
    --app-js "$FLAME_APP_JS" --app-css "$FLAME_APP_CSS"
}

# report_render - one test's heat map, summary page and raw archive.
report_render() {
  local name="$1" out="$2" json="$3"
  local log_args=() raw_args=() help_args=() log_file

  log_verbose "== [$name]: heat map -> $out/heat-map/index.html =="
  command_run python3 scripts/callgrind_to_heatmap.py "${CALLGRIND_FILES[@]}" \
    -o "$out/heat-map/index.html" \
    --title "$name / heat map"

  log_verbose "== [$name]: index -> $out/index.html =="
  rm -rf "$out/raw"
  for log_file in "${LOG_FILES[@]}"; do log_args+=(--log "$log_file"); done
  local perf_log_args=(--perf-log "$out/perf-tool/output.txt"
    --trace-log "$out/flame-graph/output.txt")
  if [ "$name" = all ]; then
    log_args+=(--no-log)
    perf_log_args=()
  else
    archive_write "$name" "$out" "$REPO" \
      "${CALLGRIND_FILES[@]}" "$json"
    raw_args+=(--raw-data "$out/raw/$name$ARCHIVE_SUFFIX")
  fi
  [ "${#TESTS[@]}" -gt 1 ] && help_args=(--help-href ../README.md)
  command_run python3 scripts/build_report.py test "${CALLGRIND_FILES[@]}" \
    -o "$out/index.html" --test "$name" \
    "${perf_log_args[@]}" "${log_args[@]}" "${raw_args[@]}" "${help_args[@]}"
}

# run_one - one test end to end: callgrind, native timing, trace, pages.
run_one() {
  local test="$1" out="$2"
  local loops cg_file log start line timing
  local stat_file="$ARTIFACTS_DIR/perf-stat.$test.$TIMESTAMP.csv"
  loops=$CALLGRIND_LOOPS
  cg_file="$ARTIFACTS_DIR/callgrind.out.$test.$loops.$TIMESTAMP"
  log="$ARTIFACTS_DIR/valgrind.$test.$loops.$TIMESTAMP.log"
  mkdir -p "$out/perf-tool"

  if [ "$REGENERATE" = 1 ]; then
    trace_render "$test" "$out" "$loops"
    CALLGRIND_FILES=("$cg_file")
    LOG_FILES=("$log")
    report_render "$test" "$out" "$TRACE_JSON"
    printf '%-13sloops=%s | reused\n' "$test" "$loops"
    return
  fi

  log_verbose "== [$test]: callgrind, pinned to CPU $CPU, loops=$loops" \
    "-> $cg_file =="
  line="$(printf '%-13sloops=%s' "$test" "$loops")"
  start="$(clock_microseconds)"
  command_run taskset -c "$CPU" valgrind --tool=callgrind --cache-sim=yes \
    --branch-sim=yes \
    --callgrind-out-file="$cg_file" --log-file="$log" "$BIN" "$test" "$loops"
  line="$line | $(duration_format "$start")"

  log_verbose "== [$test]: native timing, pinned to CPU $CPU," \
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
  cat "$out/perf-tool/output.txt" >>"$RUN_LOG"
  if [ "$VERBOSE" = 1 ]; then cat "$out/perf-tool/output.txt"; fi
  timing="$(awk '
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
  printf '%s | %s\n' "$line" "$timing"

  trace_render "$test" "$out" "$loops"
  CALLGRIND_FILES=("$cg_file")
  LOG_FILES=("$log")
  report_render "$test" "$out" "$TRACE_JSON"
}

# run_all - the synthetic "all" test's pages, then the overview page.
run_all() {
  local out="$1"
  local test_name loops usecs total=0 rows="" args
  mkdir -p "$out/perf-tool"
  CALLGRIND_FILES=()
  LOG_FILES=()
  for test_name in "${TESTS[@]}"; do
    loops=$CALLGRIND_LOOPS
    CALLGRIND_FILES+=(
      "$ARTIFACTS_DIR/callgrind.out.$test_name.$loops.$TIMESTAMP"
    )
    LOG_FILES+=(
      "$ARTIFACTS_DIR/valgrind.$test_name.$loops.$TIMESTAMP.log"
    )
  done

  log_verbose "== [all]: native timing, every test's run above summed =="
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
  if [ "$VERBOSE" = 1 ]; then cat "$out/perf-tool/output.txt"; fi

  rm -rf "$out/flame-graph"
  report_render all "$out" ""

  log_verbose "== overview -> $OUT_DIR/index.html =="
  # the rows the overview renders, in a working file: MANIFEST.txt cannot
  # be it, because the manifest is written after every page exists
  HEADER_ROWS=(
    "sampled=$SAMPLED"
    "revision=$REVISION"
    "cpu=$CPU_MODEL"
    "build=$BUILD_DESC"
    "executable=$BIN_REL <test>  (native, pinned to CPU $CPU)"
    "stamp=$TIMESTAMP"
  )
  local header_file="$ARTIFACTS_DIR/$HEADER_ROWS_NAME.$TIMESTAMP.txt"
  printf '%s\n' "${HEADER_ROWS[@]}" >"$header_file"
  args=(-o "$OUT_DIR/index.html" --header-file "$header_file")
  for test_name in "${TESTS[@]}" all; do args+=(--test "$test_name"); done
  command_run python3 scripts/build_report.py overview "${args[@]}"
  printf '%-13s%d profiles merged -> %s\n' all "${#TESTS[@]}" \
    "${OUT_DIR#"$REPO"/}/index.html"
}

# main - the whole run, ending with the manifest and the report's URL.
main() {
  args_parse "$@"
  settings_load
  toolchain_check
  [ "$KEEP_ARTIFACTS" = 1 ] || rm -rf "$ARTIFACTS_DIR"
  if [ "$REGENERATE" = 1 ]; then stamp_reuse; fi
  build_manifest
  mkdir -p "$OUT_DIR" "$ARTIFACTS_DIR"
  # build_manifest above is the last reader of the previous run's
  # manifest. Drop it now, so a run that aborts from here on leaves a
  # directory no tool will open.
  HEADER_ROWS=()
  rm -f "$OUT_DIR/MANIFEST.txt"
  if [ "$REGENERATE" = 1 ]; then
    RUN_LOG="$ARTIFACTS_DIR/regenerate.$TIMESTAMP.$(date +%s).log"
  else
    RUN_LOG="$ARTIFACTS_DIR/profile.$TIMESTAMP.log"
  fi
  cp README.md "$OUT_DIR/README.md"
  echo "dev/perf2html.sh $TIMESTAMP: ${CMAKE_FLAGS[*]} -> $OUT_DIR" >"$RUN_LOG"
  build_compile
  flame_app_install "$OUT_DIR"
  command_run python3 scripts/build_report.py assets \
    -o "$OUT_DIR/$ASSETS_NAME"

  local test_name
  for test_name in "${TESTS[@]}"; do
    run_one "$test_name" "$OUT_DIR/$test_name"
  done
  run_all "$OUT_DIR/all"

  # last of all, once every page, asset and raw archive is in place: the
  # manifest is what says this run finished, and its checksum covers the
  # finished tree
  log_verbose "== manifest -> $OUT_DIR/MANIFEST.txt =="
  manifest_write "$REPORT_MANIFEST" "$OUT_DIR" "${HEADER_ROWS[@]}"
  printf '%-13s%s\n' manifest \
    "$(manifest_value "$OUT_DIR" "$CHECKSUM_LABEL")"

  if [ "$KEEP_ARTIFACTS" != 1 ]; then rm -rf "$ARTIFACTS_DIR"; fi
  echo "file://$OUT_DIR/index.html"
}

main "$@"
