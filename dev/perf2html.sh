#!/usr/bin/env bash
# dev/perf2html.sh [--verbose] [--keep-raw] [--regenerate] [--report=DIR]
#     [--artifacts=DIR] [cmake_flags...]
#
# Raw recordings are written to a temporary artifacts directory. It sits
# beside the report by default -- the parent directory of --report=DIR,
# holding perf2html_temporary_artifacts/ -- so a read-only checkout still
# profiles. --artifacts=DIR overrides that, and --regenerate reads the
# recordings back from the same resolved directory.
#
# MANIFEST.txt is written last, once every page, asset and raw archive is
# in place, so a report holding one is a run that finished. --regenerate
# refuses a report whose version line or recorded checksum disagrees.
set -euo pipefail
SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$SCRIPT")"

# MANIFEST.txt is written by report_manifest.sh, which also supplies
# REPORT_MANIFEST, the checksum and every check that reads a report back.
# shellcheck source=report_manifest.sh
. ./report_manifest.sh

# the extension of a raw-data archive, page-visible
ARCHIVE_SUFFIX=.txz
# the artifacts directory's default name, beside the report
ARTIFACTS_NAME=perf2html_temporary_artifacts
ASSETS_DIR=assets
# the tree profiling reads. -O0 attributes cost to the wrong lines
BUILD_DIR=build-relwithdebinfo
FLAME_APP_DIR=flame-graph-app
# each glob must match exactly one file in the speedscope release
FLAME_APP_FILES=(speedscope-*.js speedscope-*.css *.woff2)
# the -finstrument-functions tree the flame graph's trace comes from
TRACE_BUILD_DIR=build-instr
# the core every measured run is pinned to. Unpinned WSL2 noise is ~106%
CPU=3
CALLGRIND_LOOPS=200
TIMING_LOOPS=10000
# UINT64_MAX: skip every event, making it a count-only run
TRACE_SKIP_ALL=18446744073709551615

# working file the overview reads its LABEL=VALUE rows from. MANIFEST.txt
# cannot be it, being written after every page exists
HEADER_ROWS_NAME=header.overview

# The apt package each tool ships in, where the tool and the package are
# not spelled the same. install_command_of() reads it.
declare -A CONTAINING_PACKAGES=(
  [cmake]=cmake
  [ninja]=ninja-build
  [ccache]=ccache
  [valgrind]=valgrind
  [taskset]=util-linux
  [python3]=python3
  [cksum]=coreutils
)

# the curl checkout this script sits under
REPO="$(cd .. && pwd)"
# names every raw file this run records. --regenerate reads it back
STAMP="$(date +%s)"

# usage_show - prints the banner at the top of this file.
usage_show() {
  cat <<'EOF'
perf2html.sh [--verbose] [--keep-raw] [--regenerate] [--report=DIR]
    [--artifacts=DIR] [cmake_flags...]

--artifacts=DIR holds the raw recordings; it defaults to
perf2html_temporary_artifacts/ beside the report directory.
EOF
}

# verbose - the one function testing $VERBOSE. Verbose adds to quiet.
verbose() { if [ "$VERBOSE" = 1 ]; then echo "$@"; fi; }

# took - a duration, counted from a saved $SECONDS, as 12s or 3m04s.
took() {
  local seconds=$((SECONDS - $1))
  if [ "$seconds" -ge 60 ]; then
    echo "$((seconds / 60))m$((seconds % 60))s"
  else
    echo "${seconds}s"
  fi
}

# test_run - runs a child, logs it, and exits printing its last 40 lines.
test_run() {
  local exit_code=0 from
  printf '\n$ %s\n' "$*" >>"$RUN_LOG"
  from="$(wc -l <"$RUN_LOG")"
  verbose "\$ $*"
  if [ "$VERBOSE" = 1 ]; then
    if ! { "$@" 2>&1 | tee -a "$RUN_LOG"; }; then
      exit_code="${PIPESTATUS[0]}"
    fi
  else
    "$@" >>"$RUN_LOG" 2>&1 || exit_code=$?
  fi
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

# args_parse - reads the command line into the run's settings and $TESTS.
args_parse() {
  VERBOSE=0
  KEEP_RAW=0
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
  case "$OUT_DIR" in
    "~/"*) OUT_DIR="$HOME/${OUT_DIR#"~/"}" ;;
    /*) ;;
    *) OUT_DIR="$PWD/$OUT_DIR" ;;
  esac
  if [ -z "$ARTIFACTS_DIR" ]; then
    ARTIFACTS_DIR="$(dirname "$OUT_DIR")/$ARTIFACTS_NAME"
  fi
  case "$ARTIFACTS_DIR" in
    "~/"*) ARTIFACTS_DIR="$HOME/${ARTIFACTS_DIR#"~/"}" ;;
    /*) ;;
    *) ARTIFACTS_DIR="$PWD/$ARTIFACTS_DIR" ;;
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

# stamp_reuse - takes $STAMP back from a verified report, for --regenerate.
stamp_reuse() {
  local manifest="$OUT_DIR/MANIFEST.txt"
  # a report is only a report if its version line and its recorded
  # checksum both still hold, so --regenerate cannot read back a tree an
  # aborted run or a later edit left behind
  manifest_verify "$OUT_DIR" "$REPORT_MANIFEST" "--regenerate input"
  STAMP="$(manifest_value "$OUT_DIR" stamp)"
  [ -n "$STAMP" ] || {
    echo "error: $manifest has no stamp= row, so its raw data cannot" \
      "be identified" >&2
    echo "       (it predates --regenerate; re-run perf2html.sh" \
      "--keep-raw once)" >&2
    exit 2
  }
  local test_name loops missing=() raw="$ARTIFACTS_DIR"
  for test_name in "${TESTS[@]}"; do
    loops=$CALLGRIND_LOOPS
    for file in "$raw/callgrind.out.$test_name.$loops.$STAMP" \
      "$raw/valgrind.$test_name.$loops.$STAMP.log" \
      "$raw/perf-stat.$test_name.$STAMP.csv" \
      "$raw/trace.$test_name.$loops.$STAMP.speedscope.json"; do
      [ -f "$file" ] || missing+=("$file")
    done
  done
  if [ "${#missing[@]}" != 0 ]; then
    {
      echo "error: --regenerate is missing ${#missing[@]} raw file(s)" \
        "for stamp $STAMP:"
      printf '       %s\n' "${missing[@]}"
      echo "       ($ARTIFACTS_DIR was cleaned; re-run" \
        "perf2html.sh --keep-raw to record them again)"
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

# install_command_of - one tool's official install command. Nothing
# hand-rolled and no PPA belongs here.
install_command_of() {
  case "$1" in
    cmake | ninja | ccache | valgrind | taskset | python3 | cksum)
      echo "sudo apt-get install -y ${CONTAINING_PACKAGES[$1]}"
      ;;
    cc) echo "sudo apt-get install -y build-essential" ;;
    addr2line | readelf) echo "sudo apt-get install -y binutils" ;;
    perf) echo "sudo apt-get install -y linux-perf" ;;
    speedscope) echo "npm install -g speedscope" ;;
    *) echo "(no official install command is recorded for this tool)" ;;
  esac
}

# toolchain_check - the only toolchain check the user-facing scripts have.
# Collects every missing tool before exiting, so one run names them all.
toolchain_check() {
  local tool missing=()
  for tool in cmake ninja ccache cc valgrind perf taskset python3 \
    addr2line readelf speedscope cksum; do
    command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
  done
  if [ "${#missing[@]}" != 0 ]; then
    {
      echo "error: ${#missing[@]} tool(s) not found on PATH:"
      for tool in "${missing[@]}"; do
        printf '  %-12s -> %s\n' "$tool" "$(install_command_of "$tool")"
      done
      case " ${missing[*]} " in
        *" perf "*)
          echo "  note: linux-tools-generic is built against an Ubuntu"
          echo "        kernel WSL does not run. linux-perf is the"
          echo "        kernel-independent build."
          ;;
      esac
    } >&2
    exit 1
  fi
  SPEEDSCOPE_RELEASE="$(dirname \
    "$(dirname "$(readlink -f "$(command -v speedscope)")")")/dist/release"
  [ -f "$SPEEDSCOPE_RELEASE/index.html" ] || {
    echo "error: no speedscope bundle at $SPEEDSCOPE_RELEASE" >&2
    echo "       (reinstall it: npm install -g speedscope)" >&2
    exit 1
  }
}

# tree_build - configures and builds one tree's perf target from scratch.
tree_build() {
  local dir="$1"
  shift
  rm -f "$REPO/$dir/CMakeCache.txt"
  test_run cmake -S "$REPO" -B "$REPO/$dir" -G Ninja -DCURL_USE_LIBPSL=OFF \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache "$@"
  test_run cmake --build "$REPO/$dir" --parallel --target perf
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
    BUILD_DESC="$(manifest_value "$OUT_DIR" build)"
    printf '%-11s%s | reused\n' build "${CMAKE_FLAGS[*]}"
    return
  fi
  verbose "== 1: cmake + build $BUILD_DIR and $TRACE_BUILD_DIR:" \
    "${CMAKE_FLAGS[*]} =="
  local line
  line="$(printf '%-11s%s' build "${CMAKE_FLAGS[*]}")"
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
  printf '%s | %s\n' "$line" "$(took "$start")"
  build_paths
  BUILD_DESC="$BUILD_DIR, ${CMAKE_FLAGS[*]}, $(cc --version | head -1)"
}

# trace_record - one pinned run of the traced binary, writing a trace file.
trace_record() {
  local test="$1" loops="$2" trace_file="$3" skip="$4"
  echo "\$ PERF_TRACE_OUT=$(basename "${trace_file/.$STAMP/}")" \
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
  local trace_file="$ARTIFACTS_DIR/trace.$test.$loops.$STAMP.bin"
  local log="$out/flame-graph/output.txt"
  TRACE_JSON="$ARTIFACTS_DIR/trace.$test.$loops"
  TRACE_JSON="$TRACE_JSON.$STAMP.speedscope.json"

  verbose "== [$test]: native trace, pinned to CPU $CPU, loops=$loops" \
    "-> $out/flame-graph/index.html =="
  if [ "$REGENERATE" = 1 ]; then
    local saved
    saved="$(mktemp)"
    cp "$log" "$saved"
    rm -rf "$out/flame-graph"
    mkdir -p "$out/flame-graph"
    cp "$saved" "$log"
    rm -f "$saved"
    test_run python3 scripts/build_flame_graph.py \
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
      | sed "s#$ARTIFACTS_DIR/##g; s#\\.$STAMP##g"
  } >"$log" || {
    echo "error: the native trace of $test failed; its output is in $log" >&2
    exit 1
  }
  cat "$log" >>"$RUN_LOG"
  if [ "$VERBOSE" = 1 ]; then cat "$log"; fi
  test_run python3 scripts/build_flame_graph.py \
    --flame-graph-dir "$out/flame-graph" --profile-json "$TRACE_JSON" \
    --app-href "../../$FLAME_APP_DIR" \
    --app-js "$FLAME_APP_JS" --app-css "$FLAME_APP_CSS"
}

# raw_archive_write - one reproducible tar.xz of a test's recordings.
raw_archive_write() {
  local name="$1" out="$2"
  shift 2
  local stage file staged
  stage="$ARTIFACTS_DIR/stage.$name.$STAMP"
  rm -rf "$stage"
  mkdir -p "$stage" "$out/raw"
  for file in "$@"; do
    staged="$(basename "$file")"
    staged="${staged/.$STAMP/}"
    cp "$file" "$stage/$staged"
  done
  sed -i "s#$REPO/##g" "$stage"/*
  test_run tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner \
    -cJf "$out/raw/$name$ARCHIVE_SUFFIX" -C "$stage" .
  rm -rf "$stage"
}

# report_render - one test's heat map, summary page and raw archive.
report_render() {
  local name="$1" out="$2" json="$3"
  local log_args=() raw_args=() help_args=() log_file

  verbose "== [$name]: heat map -> $out/heat-map/index.html =="
  test_run python3 scripts/callgrind_to_heatmap.py "${CALLGRIND_FILES[@]}" \
    -o "$out/heat-map/index.html" \
    --title "$name / heat map"

  verbose "== [$name]: index -> $out/index.html =="
  rm -rf "$out/raw"
  for log_file in "${LOG_FILES[@]}"; do log_args+=(--log "$log_file"); done
  local perf_log_args=(--perf-log "$out/perf-tool/output.txt"
    --trace-log "$out/flame-graph/output.txt")
  if [ "$name" = all ]; then
    log_args+=(--no-log)
    perf_log_args=()
  else
    raw_archive_write "$name" "$out" "${CALLGRIND_FILES[@]}" "$json"
    raw_args+=(--raw-data "$out/raw/$name$ARCHIVE_SUFFIX")
  fi
  [ "${#TESTS[@]}" -gt 1 ] && help_args=(--help-href ../README.md)
  test_run python3 scripts/build_report.py test "${CALLGRIND_FILES[@]}" \
    -o "$out/index.html" --test "$name" \
    "${perf_log_args[@]}" "${log_args[@]}" "${raw_args[@]}" "${help_args[@]}"
}

# run_one - one test end to end: callgrind, native timing, trace, pages.
run_one() {
  local test="$1" out="$2"
  local loops cg_file log start line timing
  local stat_file="$ARTIFACTS_DIR/perf-stat.$test.$STAMP.csv"
  loops=$CALLGRIND_LOOPS
  cg_file="$ARTIFACTS_DIR/callgrind.out.$test.$loops.$STAMP"
  log="$ARTIFACTS_DIR/valgrind.$test.$loops.$STAMP.log"
  mkdir -p "$out/perf-tool"

  if [ "$REGENERATE" = 1 ]; then
    trace_render "$test" "$out" "$loops"
    CALLGRIND_FILES=("$cg_file")
    LOG_FILES=("$log")
    report_render "$test" "$out" "$TRACE_JSON"
    printf '%-13sloops=%s | reused\n' "$test" "$loops"
    return
  fi

  verbose "== [$test]: callgrind, pinned to CPU $CPU, loops=$loops" \
    "-> $cg_file =="
  line="$(printf '%-13sloops=%s' "$test" "$loops")"
  start=$SECONDS
  test_run taskset -c "$CPU" valgrind --tool=callgrind --cache-sim=yes \
    --branch-sim=yes \
    --callgrind-out-file="$cg_file" --log-file="$log" "$BIN" "$test" "$loops"
  line="$line | $(took "$start")"

  verbose "== [$test]: native timing, pinned to CPU $CPU," \
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
      "$ARTIFACTS_DIR/callgrind.out.$test_name.$loops.$STAMP"
    )
    LOG_FILES+=(
      "$ARTIFACTS_DIR/valgrind.$test_name.$loops.$STAMP.log"
    )
  done

  verbose "== [all]: native timing, every test's run above summed =="
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

  verbose "== overview -> $OUT_DIR/index.html =="
  # the rows the overview renders, in a working file: MANIFEST.txt cannot
  # be it, because the manifest is written after every page exists
  HEADER_ROWS=(
    "sampled=$SAMPLED"
    "revision=$REVISION"
    "cpu=$CPU_MODEL"
    "build=$BUILD_DESC"
    "executable=$BIN_REL <test>  (native, pinned to CPU $CPU)"
    "stamp=$STAMP"
  )
  local header_file="$ARTIFACTS_DIR/$HEADER_ROWS_NAME.$STAMP.txt"
  printf '%s\n' "${HEADER_ROWS[@]}" >"$header_file"
  args=(-o "$OUT_DIR/index.html" --header-file "$header_file")
  for test_name in "${TESTS[@]}" all; do args+=(--test "$test_name"); done
  test_run python3 scripts/build_report.py overview "${args[@]}"
  printf '%-13s%d profiles merged -> %s\n' all "${#TESTS[@]}" \
    "${OUT_DIR#"$REPO"/}/index.html"
}

# main - the whole run, ending with the manifest and the report's URL.
main() {
  args_parse "$@"
  toolchain_check
  [ "$KEEP_RAW" = 1 ] || rm -rf "$ARTIFACTS_DIR"
  if [ "$REGENERATE" = 1 ]; then stamp_reuse; fi
  build_manifest
  mkdir -p "$OUT_DIR" "$ARTIFACTS_DIR"
  # build_manifest above is the last reader of the previous run's
  # manifest. Drop it now, so a run that aborts from here on leaves a
  # directory no tool will open.
  HEADER_ROWS=()
  rm -f "$OUT_DIR/MANIFEST.txt"
  if [ "$REGENERATE" = 1 ]; then
    RUN_LOG="$ARTIFACTS_DIR/regenerate.$STAMP.$(date +%s).log"
  else
    RUN_LOG="$ARTIFACTS_DIR/profile.$STAMP.log"
  fi
  cp README.md "$OUT_DIR/README.md"
  echo "dev/perf2html.sh $STAMP: ${CMAKE_FLAGS[*]} -> $OUT_DIR" >"$RUN_LOG"
  build_compile
  flame_app_install "$OUT_DIR"
  test_run python3 scripts/build_report.py assets \
    -o "$OUT_DIR/$ASSETS_DIR"

  local test_name
  for test_name in "${TESTS[@]}"; do
    run_one "$test_name" "$OUT_DIR/$test_name"
  done
  run_all "$OUT_DIR/all"

  # last of all, once every page, asset and raw archive is in place: the
  # manifest is what says this run finished, and its checksum covers the
  # finished tree
  verbose "== manifest -> $OUT_DIR/MANIFEST.txt =="
  manifest_write "$REPORT_MANIFEST" "$OUT_DIR" "${HEADER_ROWS[@]}"
  printf '%-13s%s\n' manifest \
    "$(manifest_value "$OUT_DIR" "$CHECKSUM_LABEL")"

  if [ "$KEEP_RAW" != 1 ]; then rm -rf "$ARTIFACTS_DIR"; fi
  echo "file://$OUT_DIR/index.html"
}

main "$@"
