#!/usr/bin/env bash

# This comment intentionally blank. No documentation goes here.

usage_show() {
  cat <<'EOF'
perf2html.sh [debug-flags] [--report=DIR] [cmake-flags...]
    Builds RelWithDebInfo, profiles every TESTS_C test under callgrind plus a
    native perf stat timing run and a traced run for the flame graph,
    generates one report.
    --report=NAME     Defaults to perf2html_baseline_report, or
                      perf2html_modified_report when a cmake flag is given.
    --target-dir=DIR  Default directory for reports (default $PWD).
    --txz             Create .txz archives of all reports generated.
                      .txz files may also be used as inputs.
    cmake-flags       Everything else, e.g. -D CMAKE_C_FLAGS=-Os.

    The debug-flags are the same as the README.md documents.
    --artifacts=TMP   The profiler artifacts directory. Defaults to
                      perf2html_temporary_artifacts/ beside the report
                      directory (inside the target dir for a batch).
    --keep-artifacts  Flushes the report's stale artifacts subdirectory, then
                      keeps this run's recordings, which is what a later
                      --regenerate reuses.
    --regenerate      Rebuilds all pages from the last run's profiler
                      artifacts, re-measuring nothing and keeping them.
    --verbose         Enables diagnostic information in Markdown. Repeating it
                      (--verbose --verbose) increments the verbosity level.
EOF
}

set -euo pipefail

TIMESTAMP="$(date +%s)"
INVOKED_FROM="$PWD"
_SCRIPT="$(readlink -f "$0")"
PERF2HTML_DIR_="$(dirname "$_SCRIPT")"
cd "$PERF2HTML_DIR_"

. ./scripts/settings.sh
. ./scripts/utility.sh

_REPO="$(dirname "$PERF2HTML_DIR_")"

# args_parse - reads the command line into the run's settings and $_TESTS.
args_parse() {
  shared_options_parse "$@"
  # --report= is its one option of its own; every other argument left is a
  # cmake flag
  local _remaining_argument
  _OUT_DIR=""
  _CMAKE_FLAGS=()
  for _remaining_argument in "${REMAINING_ARGUMENTS[@]}"; do
    case "$_remaining_argument" in
      --report=*) _OUT_DIR="${_remaining_argument#--report=}" ;;
      *) _CMAKE_FLAGS+=("$_remaining_argument") ;;
    esac
  done
  if [ -z "$_OUT_DIR" ]; then
    if [ "${#_CMAKE_FLAGS[@]}" -gt 0 ]; then
      _OUT_DIR="$REPORT_MODIFIED_DIR_NAME"
    else
      _OUT_DIR="$REPORT_BASELINE_DIR_NAME"
    fi
  fi
  _OUT_DIR="$(report_path_of "$_OUT_DIR")"
  artifacts_dir_resolve "$(dirname "$_OUT_DIR")"
  # each report owns one subdirectory of the artifacts dir, so no run can
  # flush or keep a sibling report's recordings
  ARTIFACTS_DIR="$ARTIFACTS_DIR/$(basename "$_OUT_DIR")"
  # the run's rows, named after its report: what --regenerate reads back
  _HEADER_FILE="$ARTIFACTS_DIR/$HEADER_ROWS_NAME.$(basename "$_OUT_DIR").txt"
  # -O2 -g leads CMAKE_C_FLAGS because -O0 costs are not the shipped build's
  # (nothing inlined); a later -O the user passes, like -Os, still wins
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
  [ "${#_TESTS[@]}" -gt 0 ] || error_exit 1 \
    "error: no TESTS_C entry in $_REPO/tests/perf/Makefile.inc"
}

# header_row_of - one LABEL= row of the run's header rows file.
header_row_of() {
  sed -n "s/^$1=//p" "$_HEADER_FILE" | head -1
}

# recorded_reuse - takes $TIMESTAMP back from the recorded= row the last
# measuring run left in the artifacts dir, and proves every recording it names.
recorded_reuse() {
  [ -d "$ARTIFACTS_DIR" ] || error_exit 2 \
    "error: --regenerate: no recordings at $ARTIFACTS_DIR"
  [ -f "$_HEADER_FILE" ] || error_exit 2 \
    "error: --regenerate: $ARTIFACTS_DIR is missing $(basename \
      "$_HEADER_FILE"), the rows of the run to reuse"
  TIMESTAMP="$(header_row_of recorded)"
  TIMESTAMP="${TIMESTAMP%% *}"
  [ -n "$TIMESTAMP" ] || error_exit 2 \
    "error: --regenerate: no recorded= row in $_HEADER_FILE"
  local _test_name _loops _file _missing=() _dir="$ARTIFACTS_DIR"
  for _test_name in "${_TESTS[@]}"; do
    _loops=$CALLGRIND_LOOPS
    for _file in "$_dir/callgrind.out.$_test_name.$_loops.$TIMESTAMP" \
      "$_dir/valgrind.$_test_name.$_loops.$TIMESTAMP.log" \
      "$_dir/$PROFILE_TIMING_FILE_PREFIX.$_test_name.$TIMESTAMP.csv" \
      "$_dir/$PROFILE_TIMING_FILE_PREFIX.$_test_name.$TIMESTAMP.txt" \
      "$_dir/trace.$_test_name.$_loops.$TIMESTAMP.log" \
      "$_dir/trace.$_test_name.$_loops.$TIMESTAMP.speedscope.json"; do
      [ -f "$_file" ] || _missing+=("$_file")
    done
  done
  [ "${#_missing[@]}" != 0 ] || return 0
  local _lines=("error: --regenerate is missing ${#_missing[@]} file(s)")
  _lines[0]="${_lines[0]} recorded at $TIMESTAMP in $ARTIFACTS_DIR:"
  for _file in "${_missing[@]}"; do _lines+=("  $_file"); done
  error_exit 2 "${_lines[@]}"
}

# build_manifest - collects the rows describing what was measured and how.
build_manifest() {
  if [ "$REGENERATE" = 1 ]; then
    _REVISION="$(header_row_of revision)"
    _CPU_MODEL="$(header_row_of cpu)"
    # build_compile wants this one too: every read of the measuring run's
    # rows happens here, and an empty one is a torn file, never a value
    _BUILD_DESC="$(header_row_of build)"
    if [ -z "$_REVISION" ] || [ -z "$_CPU_MODEL" ] \
      || [ -z "$_BUILD_DESC" ]; then
      error_exit 2 "error: --regenerate: $_HEADER_FILE is missing one of its \
revision=, cpu= or build= rows"
    fi
    return
  fi
  _REVISION="$(revision_describe "$_REPO")"
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
  rm -f "$_dir/CMakeCache.txt"
  # ccache's own variable, exported to this function's two cmake children
  # alone: it tags every compile so clean.sh can evict ours by name
  local -x CCACHE_NAMESPACE="$BUILD_CCACHE_NAMESPACE"
  local _configure_command=(cmake -S "$_REPO" -B "$_dir" -G Ninja
    -DCURL_USE_LIBPSL=OFF -DCMAKE_C_COMPILER_LAUNCHER=ccache "$@")
  local _command_line _exit_code=0
  printf -v _command_line '%q ' "${_configure_command[@]}"
  _command_line="${_command_line% }"
  command_item_print "${_configure_command[*]}"
  # configure output is half the log, so only --verbose --verbose shows it;
  # below that, users can run the printed cmake command in its printed tree
  child_capture_noisy "${_configure_command[@]}" || _exit_code=$?
  [ "$_exit_code" = 0 ] \
    || error_exit "$_exit_code" "error: cmake failed to build $_command_line"
  command_run cmake --build "$_dir" --parallel --target perf
}

# build_paths - this run's two trees and perf binaries, one tree per cmake
# command line under each of the repo's two build dirs, so none is shared.
build_paths() {
  local _flag_string="${_CMAKE_FLAGS[*]}"
  # the flags' length, then their alphanumerics: 22_DCMAKECFLAGSO2g
  _TREE_NAME="${#_flag_string}_${_flag_string//[^[:alnum:]]/}"
  _BUILD_TREE="$_REPO/$BUILD_DIR/$_TREE_NAME"
  _TRACE_TREE="$_REPO/$TRACE_BUILD_DIR/$_TREE_NAME"
  _BIN="$_BUILD_TREE/tests/perf/perf"
  _BIN_REL="$(path_display "$_BIN" "$_REPO")"
  _TRACE_BIN="$_TRACE_TREE/tests/perf/perf"
  _TRACE_BIN_REL="$(path_display "$_TRACE_BIN" "$_REPO")"
}

# build_compile - builds both trees, the traced one with the hook linked in.
build_compile() {
  build_paths
  local _line
  _line="$(printf '%-11s%s' build "${_CMAKE_FLAGS[*]}")"
  if [ "$REGENERATE" = 1 ]; then
    log_verbose "$_line | reused"
    return
  fi
  heading_print "cmake -B {$BUILD_DIR,$TRACE_BUILD_DIR}/$_TREE_NAME"
  local _start _flag _trace_flags=()
  _start="$(clock_microseconds)"
  tree_build "$_BUILD_TREE" "${_CMAKE_FLAGS[@]}"
  for _flag in "${_CMAKE_FLAGS[@]}"; do
    case "$_flag" in
      -DCMAKE_C_FLAGS=* | CMAKE_C_FLAGS=*)
        _flag="$_flag -finstrument-functions"
        ;;
    esac
    _trace_flags+=("$_flag")
  done
  mkdir -p "$_TRACE_TREE"
  command_run cc -O2 -fcf-protection=none \
    -c "$PERF2HTML_DIR_/src/cyg_callback.c" -o "$_TRACE_TREE/cyg_callback.o"
  rm -f "$_TRACE_BIN"
  local _hook="$_TRACE_TREE/cyg_callback.o"
  tree_build "$_TRACE_TREE" "${_trace_flags[@]}" \
    "-DCMAKE_EXE_LINKER_FLAGS=$_hook -Wl,--export-dynamic"
  log_verbose "$_line | $(duration_format "$_start")"
  _BUILD_DESC="$(path_display "$_BUILD_TREE" "$_REPO"), ${_CMAKE_FLAGS[*]},"
  _BUILD_DESC="$_BUILD_DESC $(cc --version | head -1)"
}

# trace_record - one pinned run of the traced binary, writing a trace file.
trace_record() {
  local _test="$1" _loops="$2" _trace_file="$3" _skip="$4"
  PERF_TRACE_OUT="$_trace_file" PERF_TRACE_SKIP="$_skip" \
    taskset -c "$PROFILE_PINNED_CPU" "$_TRACE_BIN" "$_test" "$_loops"
}

# trace_run - trace_record as page content: the page's own command line
# first, then the run. Args: test, loops, trace file, skip count, page.
trace_run() {
  local _test="$1" _loops="$2" _trace_file="$3" _skip="$4" _page="$5"
  local _name _pinned
  _name="$(basename "${_trace_file/.$TIMESTAMP/}")"
  _pinned="PERF_TRACE_SKIP=$_skip taskset -c $PROFILE_PINNED_CPU"
  echo "\$ PERF_TRACE_OUT=$_name $_pinned $_TRACE_BIN_REL $_test $_loops" \
    >>"$_page"
  page_command_run "$_page" \
    "PERF_TRACE_OUT=$_trace_file $_pinned $_TRACE_BIN $_test $_loops" \
    trace_record "$_test" "$_loops" "$_trace_file" "$_skip"
}

# trace_convert - the trace file to speedscope JSON, its lines written the
# way the page reads them: no artifacts dir or time. Args: bin, json, name.
trace_convert() {
  python3 "$PERF2HTML_DIR_/scripts/trace_to_speedscope.py" "$1" -o "$2" \
    --name "$3" 2>&1 | sed "s#$ARTIFACTS_DIR/##g; s#\\.$TIMESTAMP##g"
}

# flame_graph_profile_write - one test's flame graph profile script, from
# the trace's speedscope JSON, beside the one flame graph page. Args: test.
flame_graph_profile_write() {
  local _test="$1"
  command_run python3 "$PERF2HTML_DIR_/scripts/build_flame_graph.py" \
    profile --report-dir "$_OUT_DIR" --test "$_test" \
    --profile-json "$_TRACE_JSON"
}

# flame_app_install - copies the speedscope files a page loads, one per glob.
flame_app_install() {
  local _out="$1"
  local _pattern
  local -a _found
  mkdir -p "$_out/$FLAME_GRAPH_APP_DIR_NAME"
  for _pattern in "${FLAME_GRAPH_APP_FILE_GLOBS[@]}"; do
    # find, not a bare glob: a release directory holding a space would be
    # word-split by the expansion and match nothing that exists.
    mapfile -t _found < <(find "$SPEEDSCOPE_RELEASE" -maxdepth 1 \
      -name "$_pattern" | sort)
    local _reason="error: $_pattern matched ${#_found[@]} files in"
    [ "${#_found[@]}" = 1 ] || error_exit 1 \
      "$_reason $SPEEDSCOPE_RELEASE, expected exactly 1"
    cp "${_found[0]}" "$_out/$FLAME_GRAPH_APP_DIR_NAME"/
    case "$_pattern" in
      *.js) _FLAME_APP_JS="$(basename "${_found[0]}")" ;;
      *.css) _FLAME_APP_CSS="$(basename "${_found[0]}")" ;;
    esac
  done
}

# flame_graph_page_write - the one flame graph page, loading the profile
# script its address names and the shared bundle flame_app_install copied.
flame_graph_page_write() {
  heading_print "python3 build_flame_graph.py page"
  command_run python3 "$PERF2HTML_DIR_/scripts/build_flame_graph.py" page \
    --report-dir "$_OUT_DIR" --app-js "$_FLAME_APP_JS" \
    --app-css "$_FLAME_APP_CSS"
}

# trace_render - counting run, then sampling run, then the flame graph's
# profile script. SETS _TRACE_JSON and _TRACE_LOG, what the pages read.
trace_render() {
  local _test="$1" _loops="$2"
  local _seen _tree_display _name
  local _trace_file="$ARTIFACTS_DIR/trace.$_test.$_loops.$TIMESTAMP.bin"
  _TRACE_LOG="$ARTIFACTS_DIR/trace.$_test.$_loops.$TIMESTAMP.log"
  _TRACE_JSON="$ARTIFACTS_DIR/trace.$_test.$_loops"
  _TRACE_JSON="$_TRACE_JSON.$TIMESTAMP.speedscope.json"

  if [ "$REGENERATE" = 1 ]; then
    heading_print "python3 build_flame_graph.py profile $_test"
    flame_graph_profile_write "$_test"
    return
  fi
  _name="$(basename "${_trace_file/.$TIMESTAMP/}")"
  heading_print "PERF_TRACE_OUT=$_name perf $_test $_loops"
  _tree_display="$(path_display "$_TRACE_TREE" "$_REPO")"
  {
    echo "# $_tree_display = this report's build flags +"
    echo "# -finstrument-functions, linked with dev/src/cyg_callback.c, which"
    echo "# reads rdtsc at every function enter and exit. Run 1 counts events,"
    echo "# run 2 keeps the ones right after the run's midpoint"
    echo "# (CYG_CALLBACKS_MAX_REC in dev/src/cyg_callback.c)."
  } >"$_TRACE_LOG"
  # run 1 counts every event; run 2 keeps the ones after the midpoint
  trace_run "$_test" "$_loops" "$_trace_file" "$TRACE_SKIP_ALL" "$_TRACE_LOG"
  _seen="$(python3 "$PERF2HTML_DIR_/scripts/trace_to_speedscope.py" --seen \
    "$_trace_file")"
  [ -n "$_seen" ] || error_exit 1 "error: no --seen count for $_trace_file"
  trace_run "$_test" "$_loops" "$_trace_file" "$((_seen / 2))" "$_TRACE_LOG"
  local _shown="python3 $PERF2HTML_DIR_/scripts/trace_to_speedscope.py"
  _shown="$_shown $_trace_file -o $_TRACE_JSON"
  _shown="$_shown --name \"$_test (loops=$_loops)\""
  page_command_run "$_TRACE_LOG" "$_shown" \
    trace_convert "$_trace_file" "$_TRACE_JSON" "$_test (loops=$_loops)"
  flame_graph_profile_write "$_test"
}

# report_render - one test's heat map model script and callers page. Args:
# name, dir, perf log, trace log; "all" has only the two.
report_render() {
  local _name="$1" _out="$2" _perf_log="$3" _trace_log="$4"
  local _log_args=() _perf_log_args=() _log_file

  heading_print "python3 callgrind_to_heatmap.py data $_name"
  command_run python3 "$PERF2HTML_DIR_/scripts/callgrind_to_heatmap.py" data \
    "${_CALLGRIND_FILES[@]}" --report-dir "$_OUT_DIR" --test "$_name"

  heading_print "python3 build_report.py test $_name"
  for _log_file in "${_LOG_FILES[@]}"; do _log_args+=(--log "$_log_file"); done
  if [ "$_name" = all ]; then
    _log_args+=(--no-log)
  else
    _perf_log_args=(--perf-log "$_perf_log" --trace-log "$_trace_log")
  fi
  command_run python3 "$PERF2HTML_DIR_/scripts/build_report.py" test \
    "${_CALLGRIND_FILES[@]}" -o "$_out/index.html" --test "$_name" \
    "${_perf_log_args[@]}" "${_log_args[@]}"
}

# timing_record - the pinned perf stat run of one test, its csv named
# second, then the cycles and instructions read back from that csv.
timing_record() {
  perf stat -x, -o "$2" -e cycles:u,instructions:u \
    taskset -c "$PROFILE_PINNED_CPU" "$_BIN" "$1" "$TIMING_LOOPS" \
    && awk -F, '
      $3 ~ /cycles/ { printf "Cycles:    %s\n", $1 }
      $3 ~ /instructions/ { printf "Instructions: %s\n", $1 }' "$2"
}

# perf_page_of - the timing run's page text of one test, or of "all", a
# recording in the artifacts dir: what the callers page and the overview read.
perf_page_of() {
  echo "$ARTIFACTS_DIR/$PROFILE_TIMING_FILE_PREFIX.$1.$TIMESTAMP.txt"
}

# run_one - one test end to end: callgrind, native timing, trace, pages.
run_one() {
  local _test="$1" _out="$2"
  local _loops _cg_file _log _start _line _timing _shown
  local _stat_file _page
  _stat_file="$ARTIFACTS_DIR/$PROFILE_TIMING_FILE_PREFIX"
  _stat_file="$_stat_file.$_test.$TIMESTAMP.csv"
  _page="$(perf_page_of "$_test")"
  _loops=$CALLGRIND_LOOPS
  _cg_file="$ARTIFACTS_DIR/callgrind.out.$_test.$_loops.$TIMESTAMP"
  _log="$ARTIFACTS_DIR/valgrind.$_test.$_loops.$TIMESTAMP.log"

  if [ "$REGENERATE" = 1 ]; then
    trace_render "$_test" "$_loops"
    _CALLGRIND_FILES=("$_cg_file")
    _LOG_FILES=("$_log")
    report_render "$_test" "$_out" "$_page" "$_TRACE_LOG"
    log_verbose "$(printf '%-13sloops=%s | reused' "$_test" "$_loops")"
    return
  fi

  heading_print "valgrind --tool=callgrind perf $_test $_loops"
  _line="$(printf '%-13sloops=%s' "$_test" "$_loops")"
  _start="$(clock_microseconds)"
  command_run taskset -c "$PROFILE_PINNED_CPU" valgrind --tool=callgrind \
    --cache-sim=yes --branch-sim=yes \
    --callgrind-out-file="$_cg_file" --log-file="$_log" \
    "$_BIN" "$_test" "$_loops"
  _line="$_line | $(duration_format "$_start")"

  heading_print "perf stat -e cycles:u,instructions:u perf $_test" \
    "$TIMING_LOOPS"
  # the page's own command line, then the run whose lines are page content
  echo "\$ perf stat -e cycles:u,instructions:u taskset -c" \
    "$PROFILE_PINNED_CPU $_BIN_REL $_test $TIMING_LOOPS" >"$_page"
  _shown="perf stat -x, -o $_stat_file -e cycles:u,instructions:u taskset"
  page_command_run "$_page" \
    "$_shown -c $PROFILE_PINNED_CPU $_BIN $_test $TIMING_LOOPS" \
    timing_record "$_test" "$_stat_file"
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
    END { print s }' "$_page")"
  [ -n "$_timing" ] || error_exit 1 "error: no Time/<unit>: line in $_page"
  log_verbose "$_line | $_timing"

  trace_render "$_test" "$_loops"
  _CALLGRIND_FILES=("$_cg_file")
  _LOG_FILES=("$_log")
  report_render "$_test" "$_out" "$_page" "$_TRACE_LOG"
}

# timer_artifacts_write - every test's callgrind file and speedscope JSON in
# one archive at the report's top. SETS _TIMER_ARTIFACTS_ARCHIVE, its path.
timer_artifacts_write() {
  local _root_name="$TIMER_ARTIFACTS_NAME_PREFIX$TIMESTAMP" _test_name
  local _root_directory="$ARTIFACTS_DIR/$_root_name" _file_name
  _TIMER_ARTIFACTS_ARCHIVE="$_OUT_DIR/$_root_name$REPORT_RAW_ARCHIVE_SUFFIX"

  heading_print "tar $_root_name$REPORT_RAW_ARCHIVE_SUFFIX"
  # replaced whole, as a failed run may leave it: each file is named as its
  # recording less the time, a callgrind copy stripped, a JSON as a link
  rm -rf "$_root_directory"
  mkdir "$_root_directory"
  for _test_name in "${_TESTS[@]}"; do
    _file_name="callgrind.out.$_test_name.$CALLGRIND_LOOPS"
    cp "$ARTIFACTS_DIR/$_file_name.$TIMESTAMP" "$_root_directory/$_file_name"
    sed -i "s#$_REPO/##g" "$_root_directory/$_file_name"
    _file_name="trace.$_test_name.$CALLGRIND_LOOPS"
    ln -s "$ARTIFACTS_DIR/$_file_name.$TIMESTAMP.speedscope.json" \
      "$_root_directory/$_file_name.speedscope.json"
  done
  # --dereference packs each link as the file it names, under the one root
  # entry the archive is named after
  command_run tar --dereference --sort=name --mtime=@0 --owner=0 --group=0 \
    --numeric-owner -cJf "$_TIMER_ARTIFACTS_ARCHIVE" -C "$ARTIFACTS_DIR" \
    "$_root_name"
  rm -r "$_root_directory"
}

# run_all - the synthetic "all" test's pages, then the overview page.
run_all() {
  local _out="$1"
  local _test_name _loops _usecs _total=0 _rows="" _args _timing_lines=()
  local _page _test_page _perf_log_args=()
  _page="$(perf_page_of all)"
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

  heading_print "taskset -c $PROFILE_PINNED_CPU perf <test>"
  for _test_name in "${_TESTS[@]}"; do
    _test_page="$(perf_page_of "$_test_name")"
    _usecs="$(awk '/^Time:/ { print $2; exit }' "$_test_page")"
    [ -n "$_usecs" ] || error_exit 1 "error: no Time: line in $_test_page"
    _rows+="$(printf '  %-14s %12s usecs' "$_test_name:" "$_usecs")"$'\n'
    _timing_lines+=("$_test_name: $_usecs usecs")
    _total=$((_total + _usecs))
    _perf_log_args+=(--perf-log "$_test_name=$_test_page")
  done
  {
    echo "\$ taskset -c $PROFILE_PINNED_CPU $_BIN_REL <test>"
    echo "#   for every test, one after the other"
    echo "#   (each test's page has its full output)"
    printf '%s' "$_rows"
    echo "Time:     $_total usecs"
  } >"$_page"
  # the sum is arithmetic on each test's page, not a run: shown as the
  # page's command line with its rows nested the way a run's lines are
  command_item_print "taskset -c $PROFILE_PINNED_CPU $_BIN <test>"
  item_output_print "${_timing_lines[@]}" "Time: $_total usecs"
  _perf_log_args+=(--perf-log "all=$_page")

  report_render all "$_out" "" ""

  heading_print "python3 build_report.py overview"
  # the rows the overview renders, in the run's header rows file, which a
  # later --regenerate reads back: MANIFEST.txt is written after every page
  _HEADER_ROWS=(
    "revision=$_REVISION"
    "cpu=$_CPU_MODEL"
    "build=$_BUILD_DESC"
    "executable=$_BIN_REL <test>  (native, pinned to CPU $PROFILE_PINNED_CPU)"
    "$(manifest_recorded_row)"
  )
  printf '%s\n' "${_HEADER_ROWS[@]}" >"$_HEADER_FILE"
  _args=(-o "$_OUT_DIR/index.html" --header-file "$_HEADER_FILE"
    --raw-data "$_TIMER_ARTIFACTS_ARCHIVE" "${_perf_log_args[@]}")
  for _test_name in "${_TESTS[@]}" all; do _args+=(--test "$_test_name"); done
  command_run python3 "$PERF2HTML_DIR_/scripts/build_report.py" overview \
    "${_args[@]}"
  log_verbose "$(printf '%-13s%d profiles merged:  %s' all \
    "${#_TESTS[@]}" "$_OUT_DIR/index.html")"
}

# main - the whole run, ending with the manifest and the report's entry page.
main() {
  args_parse "$@"
  verbose_begin
  title_print "$_SCRIPT" "$@"
  # the recordings are --regenerate's whole input: nothing is created or
  # deleted before a missing one stops the run
  if [ "$REGENERATE" = 1 ]; then recorded_reuse; fi
  toolchain_check
  # the external sources the heat map reads are kept in step here, being one
  # of the two scripts a report is generated from
  source_cache_sync
  build_manifest
  # the report is output only, deleted whatever the mode, and before the
  # flush below: a refused delete leaves the last run's recordings standing
  report_delete "$_OUT_DIR"
  # --keep-artifacts flushes stale recordings first; only --regenerate reuses
  [ "$REGENERATE" = 1 ] || artifacts_clean
  _HEADER_ROWS=()
  local _log_name="profile.$TIMESTAMP.log"
  if [ "$REGENERATE" = 1 ]; then
    _log_name="regenerate.$TIMESTAMP.$(date +%s).log"
  fi
  report_begin "$_OUT_DIR" "$_log_name" \
    "dev/perf2html.sh $TIMESTAMP: ${_CMAKE_FLAGS[*]}: $_OUT_DIR"
  build_compile
  flame_app_install "$_OUT_DIR"
  flame_graph_page_write

  local _test_name
  for _test_name in "${_TESTS[@]}"; do
    run_one "$_test_name" "$_OUT_DIR/$_test_name"
  done
  # every test's recordings are made: their archive, which the overview links
  timer_artifacts_write
  run_all "$_OUT_DIR/all"
  # every test's model script has written the sources that test shows, and
  # the one heat map page links each of them
  heading_print "python3 callgrind_to_heatmap.py page"
  command_run python3 "$PERF2HTML_DIR_/scripts/callgrind_to_heatmap.py" page \
    --report-dir "$_OUT_DIR"

  report_finish "$_OUT_DIR" "$REPORT_MANIFEST_VERSION_FULL" \
    "${_HEADER_ROWS[@]}"
  if [ "$KEEP_ARTIFACTS" != 1 ]; then artifacts_clean; fi
}

main "$@"
