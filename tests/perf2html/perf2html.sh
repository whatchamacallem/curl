#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.
#
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
_SCRIPT="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
PERF2HTML_DIR_="$(dirname "$_SCRIPT")"
cd "$PERF2HTML_DIR_"

. ./scripts/settings.sh
. ./scripts/utility.sh

_REPO="$(dirname "$(dirname "$PERF2HTML_DIR_")")"

args_parse() {
  options_parse "$@"
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
  ARTIFACTS_DIR="$ARTIFACTS_DIR/$(basename "$_OUT_DIR")"
  _HEADER_FILE="$(artifact_path_of header-rows "$(basename "$_OUT_DIR")")"
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
  mapfile -t _TESTS < <(sed -n '/^TESTS_C *=/,/^$/p' \
    "$_REPO/tests/perf/Makefile.inc" \
    | grep -o '[A-Za-z0-9_]*\.c' | sed 's/\.c$//' | sort || true)
  [ "${#_TESTS[@]}" -gt 0 ] || error_exit 1 \
    "error: no TESTS_C entry in $_REPO/tests/perf/Makefile.inc"
}

header_row_of() {
  sed -n "s/^$1=//p" "$_HEADER_FILE" | head -1
}

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
  local _test_name _kind _file _missing=()
  for _test_name in "${_TESTS[@]}"; do
    for _kind in callgrind valgrind-log timing-csv timing-page trace-log \
      trace-speedscope; do
      _file="$(artifact_path_of "$_kind" "$_test_name")"
      [ -f "$_file" ] || _missing+=("$_file")
    done
  done
  [ "${#_missing[@]}" != 0 ] || return 0
  local _lines=("error: --regenerate is missing ${#_missing[@]} file(s)")
  _lines[0]="${_lines[0]} recorded at $TIMESTAMP in $ARTIFACTS_DIR:"
  for _file in "${_missing[@]}"; do _lines+=("  $_file"); done
  error_exit 2 "${_lines[@]}"
}

build_manifest() {
  if [ "$REGENERATE" = 1 ]; then
    _REVISION="$(header_row_of revision)"
    _CPU_MODEL="$(header_row_of cpu)"
    _BUILD_DESC="$(header_row_of build)"
    if [ -z "$_REVISION" ] || [ -z "$_CPU_MODEL" ] \
      || [ -z "$_BUILD_DESC" ]; then
      error_exit 2 "error: --regenerate: $_HEADER_FILE is missing one of its \
revision=, cpu= or build= rows"
    fi
    return
  fi
  _REVISION="$(revision_describe "$_REPO")"
  _CPU_MODEL="$(lscpu | grep -E 'Model name' | head -1 \
    | sed 's/^Model name:[[:space:]]*//' || true)"
  [ -n "$_CPU_MODEL" ] || _CPU_MODEL=unknown
}

tree_build() {
  local _dir="$1"
  shift
  rm -f "$_dir/CMakeCache.txt"
  local -x CCACHE_NAMESPACE="$BUILD_CCACHE_NAMESPACE"
  local _configure_command=(cmake -S "$_REPO" -B "$_dir" -G Ninja
    -DCURL_USE_LIBPSL=OFF -DCMAKE_C_COMPILER_LAUNCHER=ccache "$@")
  local _command_line _exit_code=0
  printf -v _command_line '%q ' "${_configure_command[@]}"
  _command_line="${_command_line% }"
  command_item_print "${_configure_command[*]}"
  child_capture_noisy "${_configure_command[@]}" || _exit_code=$?
  [ "$_exit_code" = 0 ] \
    || error_exit "$_exit_code" "error: cmake failed to build $_command_line"
  command_run cmake --build "$_dir" --parallel --target perf
}

build_paths() {
  local _flag_string="${_CMAKE_FLAGS[*]}"
  _TREE_NAME="${#_flag_string}_${_flag_string//[^[:alnum:]]/}"
  _BUILD_TREE="$_REPO/$BUILD_DIR/$_TREE_NAME"
  _TRACE_TREE="$_REPO/$TRACE_BUILD_DIR/$_TREE_NAME"
  _BIN="$_BUILD_TREE/tests/perf/perf"
  _BIN_REL="$(path_display "$_BIN" "$_REPO")"
  _TRACE_BIN="$_TRACE_TREE/tests/perf/perf"
  _TRACE_BIN_REL="$(path_display "$_TRACE_BIN" "$_REPO")"
}

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

trace_record() {
  local _test="$1" _loops="$2" _trace_file="$3" _skip="$4"
  PERF_TRACE_OUT="$_trace_file" PERF_TRACE_SKIP="$_skip" \
    taskset -c "$PROFILE_PINNED_CPU" "$_TRACE_BIN" "$_test" "$_loops"
}

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

trace_convert() {
  python3 "$PERF2HTML_DIR_/scripts/trace_to_speedscope.py" "$1" -o "$2" \
    --name "$3" 2>&1 | sed "s#$ARTIFACTS_DIR/##g; s#\\.$TIMESTAMP##g"
}

flame_graph_profile_write() {
  local _test="$1"
  command_run python3 "$PERF2HTML_DIR_/scripts/build_flame_graph.py" \
    profile --report-dir "$_OUT_DIR" --test "$_test" \
    --profile-json "$_TRACE_JSON"
}

flame_app_install() {
  local _out="$1"
  local _pattern
  local -a _found
  mkdir -p "$_out/$FLAME_GRAPH_APP_DIR_NAME"
  for _pattern in "${FLAME_GRAPH_APP_FILE_GLOBS[@]}"; do
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

flame_graph_page_write() {
  heading_print "python3 build_flame_graph.py page"
  command_run python3 "$PERF2HTML_DIR_/scripts/build_flame_graph.py" page \
    --report-dir "$_OUT_DIR" --app-js "$_FLAME_APP_JS" \
    --app-css "$_FLAME_APP_CSS"
}

trace_render() {
  local _test="$1" _loops="$2"
  local _seen _tree_display _name _trace_file
  _trace_file="$(artifact_path_of trace-binary "$_test")"
  _TRACE_LOG="$(artifact_path_of trace-log "$_test")"
  _TRACE_JSON="$(artifact_path_of trace-speedscope "$_test")"

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
    echo "# -finstrument-functions, linked with"
    echo "# tests/perf2html/src/cyg_callback.c, which reads rdtsc at every"
    echo "# function enter and exit. Run 1 counts events, run 2 keeps the ones"
    echo "# right after the run's midpoint (CYG_CALLBACKS_MAX_REC in"
    echo "# tests/perf2html/src/cyg_callback.c)."
  } >"$_TRACE_LOG"
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

report_render() {
  local _name="$1" _out="$2"

  heading_print "python3 callgrind_to_heatmap.py data $_name"
  command_run python3 "$PERF2HTML_DIR_/scripts/callgrind_to_heatmap.py" data \
    "${_CALLGRIND_FILES[@]}" --report-dir "$_OUT_DIR" --test "$_name"

  heading_print "python3 build_report.py test $_name"
  command_run python3 "$PERF2HTML_DIR_/scripts/build_report.py" test \
    "${_CALLGRIND_FILES[@]}" -o "$_out/index.html" --test "$_name"
}

timing_record() {
  local _counter_value _counter_unit _counter_name _remaining_fields
  perf stat -x, -o "$2" -e cycles:u,instructions:u \
    taskset -c "$PROFILE_PINNED_CPU" "$_BIN" "$1" "$TIMING_LOOPS" \
    && while IFS=, read -r _counter_value _counter_unit _counter_name \
      _remaining_fields; do
      case "$_counter_name" in
        *cycles*) printf 'Cycles:    %s\n' "$_counter_value" ;;
        *instructions*) printf 'Instructions: %s\n' "$_counter_value" ;;
      esac
    done <"$2"
}

run_one() {
  local _test="$1" _out="$2"
  local _loops _cg_file _log _start _line _timing _shown _page_words
  local _stat_file _page
  _stat_file="$(artifact_path_of timing-csv "$_test")"
  _page="$(artifact_path_of timing-page "$_test")"
  _loops=$CALLGRIND_LOOPS
  _cg_file="$(artifact_path_of callgrind "$_test")"
  _log="$(artifact_path_of valgrind-log "$_test")"

  if [ "$REGENERATE" = 1 ]; then
    trace_render "$_test" "$_loops"
    _CALLGRIND_FILES=("$_cg_file")
    report_render "$_test" "$_out"
    log_verbose "$(printf '%-13sloops=%s | reused' "$_test" "$_loops")"
    return
  fi

  heading_print "valgrind --tool=callgrind perf $_test $_loops"
  _line="$(printf '%-13sloops=%s' "$_test" "$_loops")"
  _start="$(clock_microseconds)"
  command_run taskset -c "$PROFILE_PINNED_CPU" valgrind --tool=callgrind \
    --cache-sim=yes --branch-sim=yes --trace-redir=yes \
    --LL="$CALLGRIND_LAST_LEVEL_CACHE" \
    --callgrind-out-file="$_cg_file" --log-file="$_log" \
    "$_BIN" "$_test" "$_loops"
  _line="$_line | $(duration_format "$_start")"

  heading_print "python3 callgrind_symbols.py $_test"
  command_run python3 "$PERF2HTML_DIR_/scripts/callgrind_symbols.py" \
    --valgrind-log "$_log" --callgrind-file "$_cg_file"

  heading_print "perf stat -e cycles:u,instructions:u perf $_test" \
    "$TIMING_LOOPS"
  echo "\$ perf stat -e cycles:u,instructions:u taskset -c" \
    "$PROFILE_PINNED_CPU $_BIN_REL $_test $TIMING_LOOPS" >"$_page"
  _shown="perf stat -x, -o $_stat_file -e cycles:u,instructions:u taskset"
  page_command_run "$_page" \
    "$_shown -c $PROFILE_PINNED_CPU $_BIN $_test $TIMING_LOOPS" \
    timing_record "$_test" "$_stat_file"
  _timing=""
  while read -r -a _page_words; do
    case "${_page_words[0]-}" in
      Time/*:)
        _timing="${_page_words[1]-}${_page_words[2]-}"
        _timing+="/${_page_words[0]:5:-1}"
        ;;
      Errors:*) _timing+="${_timing:+, }${_page_words[*]}" ;;
    esac
  done <"$_page"
  [ -n "$_timing" ] || error_exit 1 "error: no Time/<unit>: line in $_page"
  log_verbose "$_line | $_timing"

  trace_render "$_test" "$_loops"
  _CALLGRIND_FILES=("$_cg_file")
  report_render "$_test" "$_out"
}

timer_artifacts_write() {
  local _root_directory _root_name _test_name _member _recording
  _root_directory="$(artifact_path_of timer-artifacts "")"
  _root_name="$(basename "$_root_directory")"
  _TIMER_ARTIFACTS_ARCHIVE="$_OUT_DIR/$_root_name$REPORT_RAW_ARCHIVE_SUFFIX"

  heading_print "tar $_root_name$REPORT_RAW_ARCHIVE_SUFFIX"
  rm -rf "$_root_directory"
  mkdir "$_root_directory"
  for _test_name in "${_TESTS[@]}"; do
    _recording="$(artifact_path_of callgrind "$_test_name")"
    _member="$(artifact_path_of callgrind-member "$_test_name")"
    cp "$_recording" "$_member"
    sed -i "s#$_REPO/##g" "$_member"
    _recording="$(artifact_path_of trace-speedscope "$_test_name")"
    _member="$(artifact_path_of trace-speedscope-member "$_test_name")"
    ln -s "$_recording" "$_member"
  done
  command_run tar --dereference --sort=name --mtime=@0 --owner=0 --group=0 \
    --numeric-owner -cJf "$_TIMER_ARTIFACTS_ARCHIVE" -C "$ARTIFACTS_DIR" \
    "$_root_name"
  rm -r "$_root_directory"
}

run_all() {
  local _out="$1"
  local _test_name _time_label _time_value _time_suffix _suite_suffix
  local _remaining_fields _total=0 _row _rows="" _page _test_page _recording
  local _log_args=() _args _timing_lines=()
  _page="$(artifact_path_of timing-page "$REPORT_TEST_SUITE_NAME")"
  _CALLGRIND_FILES=()
  for _test_name in "${_TESTS[@]}"; do
    _recording="$(artifact_path_of callgrind "$_test_name")"
    _CALLGRIND_FILES+=("$_recording")
    _recording="$(artifact_path_of valgrind-log "$_test_name")"
    _log_args+=(--valgrind-log "$_test_name=$_recording")
    _recording="$(artifact_path_of trace-log "$_test_name")"
    _log_args+=(--trace-log "$_test_name=$_recording")
  done

  heading_print "taskset -c $PROFILE_PINNED_CPU perf <test>"
  for _test_name in "${_TESTS[@]}"; do
    _test_page="$(artifact_path_of timing-page "$_test_name")"
    while read -r _time_label _time_value _time_suffix _remaining_fields; do
      [ "$_time_label" != Time: ] || break
    done <"$_test_page"
    [ "$_time_label" = Time: ] && [ -n "$_time_suffix" ] || error_exit 1 \
      "error: no Time: <value> <suffix> line in $_test_page"
    if [ "$_test_name" = "${_TESTS[0]}" ]; then
      _suite_suffix="$_time_suffix"
    fi
    [ "$_time_suffix" = "$_suite_suffix" ] || error_exit 1 \
      "error: $_test_page Time: suffix $_time_suffix, expected $_suite_suffix"
    printf -v _row '  %-14s %12s %s\n' "$_test_name:" "$_time_value" \
      "$_suite_suffix"
    _rows+="$_row"
    _timing_lines+=("$_test_name: $_time_value $_suite_suffix")
    _total=$((_total + _time_value))
    _log_args+=(--perf-log "$_test_name=$_test_page")
  done
  {
    echo "\$ taskset -c $PROFILE_PINNED_CPU $_BIN_REL <test>"
    echo "#   for every test, one after the other"
    echo "#   (the perf log of each test follows)"
    printf '%s' "$_rows"
    echo "Time:     $_total $_suite_suffix"
  } >"$_page"
  command_item_print "taskset -c $PROFILE_PINNED_CPU $_BIN <test>"
  item_output_print "${_timing_lines[@]}" "Time: $_total $_suite_suffix"
  _log_args+=(--perf-log "$REPORT_TEST_SUITE_NAME=$_page")

  report_render "$REPORT_TEST_SUITE_NAME" "$_out"

  heading_print "python3 build_report.py overview"
  _HEADER_ROWS=(
    "revision=$_REVISION"
    "cpu=$_CPU_MODEL"
    "build=$_BUILD_DESC"
    "executable=$_BIN_REL <test>  (native, pinned to CPU $PROFILE_PINNED_CPU)"
    "$(manifest_recorded_row)"
  )
  printf '%s\n' "${_HEADER_ROWS[@]}" >"$_HEADER_FILE"
  _args=(-o "$_OUT_DIR/index.html" --header-file "$_HEADER_FILE"
    --raw-data "$_TIMER_ARTIFACTS_ARCHIVE" "${_log_args[@]}")
  for _test_name in "${_TESTS[@]}" "$REPORT_TEST_SUITE_NAME"; do
    _args+=(--test "$_test_name")
  done
  command_run python3 "$PERF2HTML_DIR_/scripts/build_report.py" overview \
    "${_args[@]}"
  log_verbose "$(printf '%-13s%d profiles merged: %s' \
    "$REPORT_TEST_SUITE_NAME" "${#_TESTS[@]}" "$_OUT_DIR/index.html")"
}

main() {
  args_parse "$@"
  verbose_begin
  title_print "$_SCRIPT" "$@"
  if [ "$REGENERATE" = 1 ]; then recorded_reuse; fi
  toolchain_check
  source_cache_sync
  build_manifest
  report_delete "$_OUT_DIR"
  [ "$REGENERATE" = 1 ] || artifacts_clean
  _HEADER_ROWS=()
  local _log_kind=profile-log _log_file
  if [ "$REGENERATE" = 1 ]; then
    _log_kind=regenerate-log
  fi
  _log_file="$(artifact_path_of "$_log_kind" "")"
  report_begin "$_OUT_DIR" "$_log_file" \
    "tests/perf2html/perf2html.sh $TIMESTAMP: ${_CMAKE_FLAGS[*]}: $_OUT_DIR"
  source_cache_fill
  build_compile
  flame_app_install "$_OUT_DIR"
  flame_graph_page_write

  local _test_name
  for _test_name in "${_TESTS[@]}"; do
    run_one "$_test_name" "$_OUT_DIR/$_test_name"
  done
  timer_artifacts_write
  run_all "$_OUT_DIR/$REPORT_TEST_SUITE_NAME"
  heading_print "python3 callgrind_to_heatmap.py page"
  command_run python3 "$PERF2HTML_DIR_/scripts/callgrind_to_heatmap.py" page \
    --report-dir "$_OUT_DIR"

  report_finish "$_OUT_DIR" "$REPORT_MANIFEST_VERSION_FULL" \
    "${_HEADER_ROWS[@]}"
  if [ "$KEEP_ARTIFACTS" != 1 ]; then artifacts_clean; fi
}

main "$@"
