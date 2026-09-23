#!/usr/bin/env bash

# Builds, profiles and generates one report. usage_show below is the only
# usage text here. It and README.md are kept in step by hand.

set -euo pipefail
_SCRIPT="$(readlink -f "$0")"
cd "$(dirname "$_SCRIPT")"

. ./scripts/settings.sh
. ./scripts/shared.sh

_REPO="$(cd .. && pwd)"

# usage_show - the one usage text, printed by -h and on a bad argument
usage_show() {
  cat <<'EOF'
perf2html.sh [debug-flags] [--report=DIR] [cmake-flags...]
    Builds RelWithDebInfo, profiles every TESTS_C test under callgrind plus a
    native perf stat timing run and a traced run for the flame graph,
    generates one report.
    --report=DIR      Defaults to perf2html_baseline_report, or
                      perf2html_modified_report when a cmake flag is given.
                      Pass it yourself after a source-only change.
    cmake-flags       Everything else, e.g. -D CMAKE_C_FLAGS=-Os.

  debug-flags:
    --artifacts=TMP   The profiler artifacts directory. Defaults to
                      perf2html_temporary_artifacts/ beside the report
                      directory (inside the target dir for a batch).
    --keep-artifacts  Do not delete the profiler artifacts directory after use.
                      Required for a later --regenerate.
    --regenerate      Rebuilds all pages from the last run's profiler
                      artifacts, re-measuring nothing. Implies
                      --keep-artifacts.
    --verbose         Enables diagnostic information.
EOF
}

# args_parse - reads the command line into the run's settings and $_TESTS.
args_parse() {
  _KEEP_ARTIFACTS=0
  _REGENERATE=0
  _OUT_DIR=""
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
        _KEEP_ARTIFACTS=1
        shift
        ;;
      --regenerate)
        _REGENERATE=1
        _KEEP_ARTIFACTS=1
        shift
        ;;
      --report=*)
        _OUT_DIR="${1#--report=}"
        shift
        ;;
      --artifacts=*)
        ARTIFACTS_DIR="${1#--artifacts=}"
        shift
        ;;
      *) break ;;
    esac
  done
  _CMAKE_FLAGS=("$@")
  if [ -z "$_OUT_DIR" ]; then
    if [ $# -gt 0 ]; then
      _OUT_DIR=perf2html_modified_report
    else
      _OUT_DIR=perf2html_baseline_report
    fi
  fi
  _OUT_DIR="$(absolute_path "$_OUT_DIR")"
  if [ -z "$ARTIFACTS_DIR" ]; then
    ARTIFACTS_DIR="$(dirname "$_OUT_DIR")/$ARTIFACTS_NAME"
  fi
  ARTIFACTS_DIR="$(absolute_path "$ARTIFACTS_DIR")"
  local _index _seen=0 _split=0 _flag
  for _index in "${!_CMAKE_FLAGS[@]}"; do
    _flag="${_CMAKE_FLAGS[$_index]}"
    if [ "$_split" = 1 ]; then
      case "$_flag" in
        CMAKE_C_FLAGS=*)
          _CMAKE_FLAGS[$_index]="CMAKE_C_FLAGS=-O2 -g ${_flag#CMAKE_C_FLAGS=}"
          _seen=1
          ;;
      esac
      _split=0
      continue
    fi
    case "$_flag" in
      -DCMAKE_C_FLAGS=*)
        _CMAKE_FLAGS[$_index]="-DCMAKE_C_FLAGS=-O2 -g \
${_flag#-DCMAKE_C_FLAGS=}"
        _seen=1
        ;;
      -D) _split=1 ;;
    esac
  done
  [ "$_seen" = 1 ] || _CMAKE_FLAGS+=("-DCMAKE_C_FLAGS=-O2 -g")
  # grep exits 1 on no match, which under pipefail would end the run with
  # no message at all, so the result is tested and named instead.
  mapfile -t _TESTS < <(sed -n '/^TESTS_C *=/,/^$/p' \
    "$_REPO/tests/perf/Makefile.inc" \
    | grep -o '[A-Za-z0-9_]*\.c' | sed 's/\.c$//' | sort || true)
  [ "${#_TESTS[@]}" -gt 0 ] || {
    echo "error: no TESTS_C entry in $_REPO/tests/perf/Makefile.inc" >&2
    exit 1
  }
}

# stamp_reuse - takes $TIMESTAMP back from a verified report, for --regenerate.
stamp_reuse() {
  local _manifest="$_OUT_DIR/MANIFEST.txt"
  # version line and checksum must both still hold, so --regenerate cannot
  # read back what an aborted run or a later edit left behind
  manifest_verify "$_OUT_DIR" "--regenerate input" \
    "$REPORT_MANIFEST_VERSION_FULL"
  TIMESTAMP="$(manifest_value "$_OUT_DIR" stamp)"
  [ -n "$TIMESTAMP" ] || {
    echo "error: $_manifest has no stamp= row, so its recordings" \
      "cannot be identified" >&2
    echo "       (it predates --regenerate; re-run perf2html.sh" \
      "--keep-artifacts once)" >&2
    exit 2
  }
  local _test_name _loops _file _missing=() _dir="$ARTIFACTS_DIR"
  for _test_name in "${_TESTS[@]}"; do
    _loops=$CALLGRIND_LOOPS
    for _file in "$_dir/callgrind.out.$_test_name.$_loops.$TIMESTAMP" \
      "$_dir/valgrind.$_test_name.$_loops.$TIMESTAMP.log" \
      "$_dir/perf-stat.$_test_name.$TIMESTAMP.csv" \
      "$_dir/trace.$_test_name.$_loops.$TIMESTAMP.speedscope.json"; do
      [ -f "$_file" ] || _missing+=("$_file")
    done
  done
  if [ "${#_missing[@]}" != 0 ]; then
    {
      echo "error: --regenerate is missing ${#_missing[@]} recorded" \
        "file(s) for stamp $TIMESTAMP:"
      printf '       %s\n' "${_missing[@]}"
      echo "       ($ARTIFACTS_DIR was cleaned; re-run" \
        "perf2html.sh --keep-artifacts to record them again)"
    } >&2
    exit 2
  fi
}

# build_manifest - collects the rows describing what was measured and how.
build_manifest() {
  if [ "$_REGENERATE" = 1 ]; then
    _SAMPLED="$(manifest_value "$_OUT_DIR" sampled)"
    _REVISION="$(manifest_value "$_OUT_DIR" revision)"
    _CPU_MODEL="$(manifest_value "$_OUT_DIR" cpu)"
    # build_compile wants this one, and runs after main has dropped the
    # manifest. Every read of the previous run's rows happens here.
    _BUILD_DESC="$(manifest_value "$_OUT_DIR" build)"
    return
  fi
  _SAMPLED="$(date +'%Y/%m/%d %H:%M:%S %Z')"
  _REVISION="$(cd "$_REPO" \
    && git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  if [ "$_REVISION" != unknown ] \
    && ! (cd "$_REPO" && git diff --quiet HEAD -- 2>/dev/null); then
    _REVISION="$_REVISION-dirty"
  fi
  # a box whose lscpu prints no model name is not a failure, so the grep
  # cannot be allowed to end the run under pipefail
  _CPU_MODEL="$(lscpu | grep -E 'Model name' | head -1 \
    | sed 's/^Model name:[[:space:]]*//' || true)"
  [ -n "$_CPU_MODEL" ] || _CPU_MODEL=unknown
}

# tree_build - configures and builds one tree's perf target from scratch.
tree_build() {
  local _dir="$1"
  shift
  rm -f "$_REPO/$_dir/CMakeCache.txt"
  command_run cmake -S "$_REPO" -B "$_REPO/$_dir" -G Ninja \
    -DCURL_USE_LIBPSL=OFF -DCMAKE_C_COMPILER_LAUNCHER=ccache "$@"
  command_run cmake --build "$_REPO/$_dir" --parallel --target perf
}

# build_paths - the two perf binaries, absolute and repo-relative.
build_paths() {
  _BIN="$_REPO/$BUILD_DIR/tests/perf/perf"
  _BIN_REL="${_BIN#"$_REPO"/}"
  _TRACE_BIN="$_REPO/$TRACE_BUILD_DIR/tests/perf/perf"
  _TRACE_BIN_REL="${_TRACE_BIN#"$_REPO"/}"
}

# build_compile - builds both trees, the traced one with the hook linked in.
build_compile() {
  if [ "$_REGENERATE" = 1 ]; then
    build_paths
    printf '%-11s%s | reused\n' build "${_CMAKE_FLAGS[*]}"
    return
  fi
  log_verbose "== 1: cmake + build $BUILD_DIR and $TRACE_BUILD_DIR:" \
    "${_CMAKE_FLAGS[*]} =="
  local _line
  _line="$(printf '%-11s%s' build "${_CMAKE_FLAGS[*]}")"
  local _start _flag _trace_flags=()
  _start="$(clock_microseconds)"
  tree_build "$BUILD_DIR" "${_CMAKE_FLAGS[@]}"
  for _flag in "${_CMAKE_FLAGS[@]}"; do
    case "$_flag" in
      -DCMAKE_C_FLAGS=* | CMAKE_C_FLAGS=*)
        _flag="$_flag -finstrument-functions"
        ;;
    esac
    _trace_flags+=("$_flag")
  done
  mkdir -p "$_REPO/$TRACE_BUILD_DIR"
  command_run cc -O2 -fcf-protection=none -c src/cyg_callback.c \
    -o "$_REPO/$TRACE_BUILD_DIR/cyg_callback.o"
  rm -f "$_REPO/$TRACE_BUILD_DIR/tests/perf/perf"
  local _hook="$_REPO/$TRACE_BUILD_DIR/cyg_callback.o"
  tree_build "$TRACE_BUILD_DIR" "${_trace_flags[@]}" \
    "-DCMAKE_EXE_LINKER_FLAGS=$_hook -Wl,--export-dynamic"
  printf '%s | %s\n' "$_line" "$(duration_format "$_start")"
  build_paths
  _BUILD_DESC="$BUILD_DIR, ${_CMAKE_FLAGS[*]}, $(cc --version | head -1)"
}

# trace_record - one pinned run of the traced binary, writing a trace file.
trace_record() {
  local _test="$1" _loops="$2" _trace_file="$3" _skip="$4"
  echo "\$ PERF_TRACE_OUT=$(basename "${_trace_file/.$TIMESTAMP/}")" \
    "PERF_TRACE_SKIP=$_skip taskset -c $PROFILE_PINNED_CPU" \
    "$_TRACE_BIN_REL $_test $_loops"
  PERF_TRACE_OUT="$_trace_file" PERF_TRACE_SKIP="$_skip" \
    taskset -c "$PROFILE_PINNED_CPU" "$_TRACE_BIN" "$_test" "$_loops" 2>&1
}

# flame_app_install - copies the speedscope files a page loads, one per glob.
flame_app_install() {
  local _out="$1"
  local _pattern
  local -a _found
  rm -rf "$_out/$FLAME_GRAPH_APP_DIR_NAME"
  mkdir -p "$_out/$FLAME_GRAPH_APP_DIR_NAME"
  for _pattern in "${FLAME_GRAPH_APP_FILE_GLOBS[@]}"; do
    # find, not a bare glob: a release directory holding a space would be
    # word-split by the expansion and match nothing that exists.
    mapfile -t _found < <(find "$SPEEDSCOPE_RELEASE" -maxdepth 1 \
      -name "$_pattern" | sort)
    [ "${#_found[@]}" = 1 ] || {
      echo "error: $_pattern matched ${#_found[@]} files in" \
        "$SPEEDSCOPE_RELEASE, expected exactly 1" >&2
      exit 1
    }
    cp "${_found[0]}" "$_out/$FLAME_GRAPH_APP_DIR_NAME"/
    case "$_pattern" in
      *.js) _FLAME_APP_JS="$(basename "${_found[0]}")" ;;
      *.css) _FLAME_APP_CSS="$(basename "${_found[0]}")" ;;
    esac
  done
}

# trace_render - counting run, then sampling run, then the flame graph page.
trace_render() {
  local _test="$1" _out="$2" _loops="$3"
  local _seen
  local _trace_file="$ARTIFACTS_DIR/trace.$_test.$_loops.$TIMESTAMP.bin"
  local _log="$_out/flame-graph/output.txt"
  _TRACE_JSON="$ARTIFACTS_DIR/trace.$_test.$_loops"
  _TRACE_JSON="$_TRACE_JSON.$TIMESTAMP.speedscope.json"

  log_verbose "== [$_test]: native trace, pinned to CPU" \
    "$PROFILE_PINNED_CPU, _loops=$_loops -> $_out/flame-graph/index.html =="
  if [ "$_REGENERATE" = 1 ]; then
    local _saved
    _saved="$(mktemp)"
    cp "$_log" "$_saved"
    rm -rf "$_out/flame-graph"
    mkdir -p "$_out/flame-graph"
    cp "$_saved" "$_log"
    rm -f "$_saved"
    command_run python3 scripts/build_flame_graph.py \
      --flame-graph-dir "$_out/flame-graph" --profile-json "$_TRACE_JSON" \
      --app-href "../../$FLAME_GRAPH_APP_DIR_NAME" \
      --app-js "$_FLAME_APP_JS" --app-css "$_FLAME_APP_CSS"
    return
  fi
  rm -rf "$_out/flame-graph"
  mkdir -p "$_out/flame-graph"
  {
    echo "# $TRACE_BUILD_DIR = this report's build flags +"
    echo "# -finstrument-functions, linked with dev/src/cyg_callback.c, which"
    echo "# reads rdtsc at every function enter and exit. Run 1 counts events,"
    echo "# run 2 keeps the ones right after the run's midpoint"
    echo "# (CYG_CALLBACKS_MAX_REC in dev/src/cyg_callback.c)."
    trace_record "$_test" "$_loops" "$_trace_file" "$TRACE_SKIP_ALL" \
      && _seen="$(python3 scripts/trace_to_speedscope.py \
        --seen "$_trace_file")" \
      && trace_record "$_test" "$_loops" "$_trace_file" "$((_seen / 2))" \
      && python3 scripts/trace_to_speedscope.py "$_trace_file" \
        -o "$_TRACE_JSON" --name "$_test (loops=$_loops)" 2>&1 \
      | sed "s#$ARTIFACTS_DIR/##g; s#\\.$TIMESTAMP##g"
  } >"$_log" || {
    echo "error: the native trace of $_test failed; its output is in $_log" >&2
    exit 1
  }
  log_verbose_file "$_log"
  command_run python3 scripts/build_flame_graph.py \
    --flame-graph-dir "$_out/flame-graph" --profile-json "$_TRACE_JSON" \
    --app-href "../../$FLAME_GRAPH_APP_DIR_NAME" \
    --app-js "$_FLAME_APP_JS" --app-css "$_FLAME_APP_CSS"
}

# report_render - one test's heat map, summary page and raw archive.
report_render() {
  local _name="$1" _out="$2" _json="$3"
  local _log_args=() _raw_args=() _help_args=() _log_file

  log_verbose "== [$_name]: heat map -> $_out/heat-map/index.html =="
  command_run python3 scripts/callgrind_to_heatmap.py \
    "${_CALLGRIND_FILES[@]}" \
    -o "$_out/heat-map/index.html" \
    --title "$_name / heat map"

  log_verbose "== [$_name]: index -> $_out/index.html =="
  rm -rf "$_out/raw"
  for _log_file in "${_LOG_FILES[@]}"; do _log_args+=(--log "$_log_file"); done
  local _perf_log_args=(--perf-log "$_out/perf-tool/output.txt"
    --trace-log "$_out/flame-graph/output.txt")
  if [ "$_name" = all ]; then
    _log_args+=(--no-log)
    _perf_log_args=()
  else
    archive_write "$_name" "$_out" "$_REPO" \
      "${_CALLGRIND_FILES[@]}" "$_json"
    _raw_args+=(--raw-data "$_out/raw/$_name$REPORT_RAW_ARCHIVE_SUFFIX")
  fi
  [ "${#_TESTS[@]}" -gt 1 ] && _help_args=(--help-href ../README.md)
  command_run python3 scripts/build_report.py test "${_CALLGRIND_FILES[@]}" \
    -o "$_out/index.html" --test "$_name" \
    "${_perf_log_args[@]}" "${_log_args[@]}" "${_raw_args[@]}" \
    "${_help_args[@]}"
}

# run_one - one test end to end: callgrind, native timing, trace, pages.
run_one() {
  local _test="$1" _out="$2"
  local _loops _cg_file _log _start _line _timing
  local _stat_file="$ARTIFACTS_DIR/perf-stat.$_test.$TIMESTAMP.csv"
  _loops=$CALLGRIND_LOOPS
  _cg_file="$ARTIFACTS_DIR/callgrind.out.$_test.$_loops.$TIMESTAMP"
  _log="$ARTIFACTS_DIR/valgrind.$_test.$_loops.$TIMESTAMP.log"
  mkdir -p "$_out/perf-tool"

  if [ "$_REGENERATE" = 1 ]; then
    trace_render "$_test" "$_out" "$_loops"
    _CALLGRIND_FILES=("$_cg_file")
    _LOG_FILES=("$_log")
    report_render "$_test" "$_out" "$_TRACE_JSON"
    printf '%-13sloops=%s | reused\n' "$_test" "$_loops"
    return
  fi

  log_verbose "== [$_test]: callgrind, pinned to CPU $PROFILE_PINNED_CPU," \
    "loops=$_loops -> $_cg_file =="
  _line="$(printf '%-13sloops=%s' "$_test" "$_loops")"
  _start="$(clock_microseconds)"
  command_run taskset -c "$PROFILE_PINNED_CPU" valgrind --tool=callgrind \
    --cache-sim=yes --branch-sim=yes \
    --callgrind-out-file="$_cg_file" --log-file="$_log" \
    "$_BIN" "$_test" "$_loops"
  _line="$_line | $(duration_format "$_start")"

  log_verbose "== [$_test]: native timing, pinned to CPU" \
    "$PROFILE_PINNED_CPU, loops=$TIMING_LOOPS ->" \
    "$_out/perf-tool/output.txt =="
  {
    echo "\$ perf stat -e cycles:u,instructions:u taskset -c" \
      "$PROFILE_PINNED_CPU $_BIN_REL $_test $TIMING_LOOPS"
    perf stat -x, -o "$_stat_file" -e cycles:u,instructions:u \
      taskset -c "$PROFILE_PINNED_CPU" "$_BIN" "$_test" "$TIMING_LOOPS" 2>&1 \
      && awk -F, '
        $3 ~ /cycles/ { printf "Cycles:    %s\n", $1 }
        $3 ~ /instructions/ { printf "Instructions: %s\n", $1 }' \
        "$_stat_file"
  } >"$_out/perf-tool/output.txt" \
    || {
      echo "error: $_BIN $_test failed; its output is in" \
        "$_out/perf-tool/output.txt" >&2
      exit 1
    }
  log_verbose_file "$_out/perf-tool/output.txt"
  _timing="$(awk '
    /^Time\/[A-Za-z]+:/ {
      unit = $1
      sub(/^Time\//, "", unit)
      sub(/:$/, "", unit)
      t = $2 " " $3
      sub(/ /, "", t)
      s = t "/" unit
    }
    /^Errors:/ { $1 = $1; s = s (s ? ", " : "") $0 }
    END { print s }' "$_out/perf-tool/output.txt")"
  printf '%s | %s\n' "$_line" "$_timing"

  trace_render "$_test" "$_out" "$_loops"
  _CALLGRIND_FILES=("$_cg_file")
  _LOG_FILES=("$_log")
  report_render "$_test" "$_out" "$_TRACE_JSON"
}

# run_all - the synthetic "all" test's pages, then the overview page.
run_all() {
  local _out="$1"
  local _test_name _loops _usecs _total=0 _rows="" _args
  mkdir -p "$_out/perf-tool"
  _CALLGRIND_FILES=()
  _LOG_FILES=()
  for _test_name in "${_TESTS[@]}"; do
    _loops=$CALLGRIND_LOOPS
    _CALLGRIND_FILES+=(
      "$ARTIFACTS_DIR/callgrind.out.$_test_name.$_loops.$TIMESTAMP"
    )
    _LOG_FILES+=(
      "$ARTIFACTS_DIR/valgrind.$_test_name.$_loops.$TIMESTAMP.log"
    )
  done

  log_verbose "== [all]: native timing, every test's run above summed =="
  for _test_name in "${_TESTS[@]}"; do
    _usecs="$(awk '/^Time:/ { print $2; exit }' \
      "$_OUT_DIR/$_test_name/perf-tool/output.txt")"
    _rows+="$(printf '  %-14s %12s usecs' "$_test_name:" "${_usecs:-?}")"$'\n'
    _total=$((_total + ${_usecs:-0}))
  done
  {
    echo "\$ taskset -c $PROFILE_PINNED_CPU $_BIN_REL <test>"
    echo "#   for every test, one after the other"
    echo "#   (each test's page has its full output)"
    printf '%s' "$_rows"
    echo "Time:     $_total usecs"
  } >"$_out/perf-tool/output.txt"
  log_verbose_file "$_out/perf-tool/output.txt"

  rm -rf "$_out/flame-graph"
  report_render all "$_out" ""

  log_verbose "== overview -> $_OUT_DIR/index.html =="
  # the rows the overview renders, in a working file: MANIFEST.txt cannot
  # be it, because the manifest is written after every page exists
  _HEADER_ROWS=(
    "sampled=$_SAMPLED"
    "revision=$_REVISION"
    "cpu=$_CPU_MODEL"
    "build=$_BUILD_DESC"
    "executable=$_BIN_REL <test>  (native, pinned to CPU $PROFILE_PINNED_CPU)"
    "stamp=$TIMESTAMP"
  )
  local _header_file="$ARTIFACTS_DIR/$HEADER_ROWS_NAME.$TIMESTAMP.txt"
  printf '%s\n' "${_HEADER_ROWS[@]}" >"$_header_file"
  _args=(-o "$_OUT_DIR/index.html" --header-file "$_header_file")
  for _test_name in "${_TESTS[@]}" all; do _args+=(--test "$_test_name"); done
  command_run python3 scripts/build_report.py overview "${_args[@]}"
  printf '%-13s%d profiles merged -> %s\n' all "${#_TESTS[@]}" \
    "${_OUT_DIR#"$_REPO"/}/index.html"
}

# main - the whole run, ending with the manifest and the report's URL.
main() {
  args_parse "$@"
  toolchain_check
  [ "$_KEEP_ARTIFACTS" = 1 ] || artifacts_clean
  if [ "$_REGENERATE" = 1 ]; then stamp_reuse; fi
  # the last reader of the previous run's manifest: report_begin below
  # drops it, and clears the report unless this is a --regenerate
  build_manifest
  _HEADER_ROWS=()
  local _log_name="profile.$TIMESTAMP.log"
  # --regenerate rebuilds the pages from the artifacts dir and reads the
  # report back to find them, so it is the one mode that must not clear it
  if [ "$_REGENERATE" = 1 ]; then
    _log_name="regenerate.$TIMESTAMP.$(date +%s).log"
  fi
  report_begin "$_OUT_DIR" "$_log_name" \
    "dev/perf2html.sh $TIMESTAMP: ${_CMAKE_FLAGS[*]} -> $_OUT_DIR" \
    "$_REGENERATE"
  build_compile
  flame_app_install "$_OUT_DIR"

  local _test_name
  for _test_name in "${_TESTS[@]}"; do
    run_one "$_test_name" "$_OUT_DIR/$_test_name"
  done
  run_all "$_OUT_DIR/all"

  report_finish "$_OUT_DIR" "$REPORT_MANIFEST_VERSION_FULL" \
    "${_HEADER_ROWS[@]}"
  if [ "$_KEEP_ARTIFACTS" != 1 ]; then artifacts_clean; fi
}

main "$@"
