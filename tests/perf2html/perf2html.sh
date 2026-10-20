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
    cmake-flags       Everything else is passed directly to cmake.

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
_SCRIPT="$(readlink -f -- "$0")"
cd -P -- "$(dirname -- "$_SCRIPT")"
PERF2HTML_DIR_="$PWD"

. ./scripts/settings.sh
. ./scripts/utility.sh

_REPO="$(cd -P -- ../.. && pwd)"

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
  _OUT_DIR="$(report_path "$_OUT_DIR")"
  artifacts_dir_resolve "$(dirname "$_OUT_DIR")"
  report_artifacts_dir REPORT_ARTIFACTS_DIR "$_OUT_DIR"
  local _index _seen=0 _split=0 _flag
  _COMPILER_COMMAND="${CC:-cc}"
  for _index in "${!_CMAKE_FLAGS[@]}"; do
    _flag="${_CMAKE_FLAGS[$_index]}"
    if [ "$_split" = 1 ]; then
      case "$_flag" in
        CMAKE_C_FLAGS=*)
          _CMAKE_FLAGS[$_index]="CMAKE_C_FLAGS=-O2 -g ${_flag#CMAKE_C_FLAGS=}"
          _seen=1
          ;;
        CMAKE_C_COMPILER=* | CMAKE_C_COMPILER:*=*)
          _COMPILER_COMMAND="${_flag#*=}"
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
      -DCMAKE_C_COMPILER=* | -DCMAKE_C_COMPILER:*=*)
        _COMPILER_COMMAND="${_flag#*=}"
        ;;
      -D) _split=1 ;;
    esac
  done
  [ "$_seen" = 1 ] || _CMAKE_FLAGS+=("-DCMAKE_C_FLAGS=-O2 -g")
  mapfile -t _TESTS < <(sed -n '/^TESTS_C *=/,/^$/p' \
    "$_REPO/tests/perf/Makefile.inc" \
    | grep -o '[A-Za-z0-9_]*\.c' | sed 's/\.c$//' | LC_ALL=C sort || true)
  [ "${#_TESTS[@]}" -gt 0 ] || error_exit 1 \
    "error: no TESTS_C entry in $_REPO/tests/perf/Makefile.inc"
}

recordings_check() {
  [ "$REGENERATE" = 1 ] || return 0
  local _test_list _header_rows
  [ -d "$REPORT_ARTIFACTS_DIR" ] || error_exit 2 \
    "error: --regenerate: no recordings at $REPORT_ARTIFACTS_DIR"
  test_list_read "$REPORT_ARTIFACTS_DIR"
  artifact_path _test_list "$REPORT_ARTIFACTS_DIR" test-list
  [ "${TEST_LIST[*]}" = "${_TESTS[*]}" ] || error_exit 2 "error: \
--regenerate: $_test_list names ${TEST_LIST[*]}, TESTS_C names ${_TESTS[*]}"
  artifacts_verify recorded
  artifact_path _header_rows "$REPORT_ARTIFACTS_DIR" header-rows
  recorded_time_read TIMESTAMP "$_header_rows"
}

compiler_identify() {
  command -v "$_COMPILER_COMMAND" >/dev/null || error_exit 127 \
    "error: no C compiler $_COMPILER_COMMAND on PATH"
  _COMPILER_NAME="$("$_COMPILER_COMMAND" -dM -E -x c /dev/null | awk '
    { macro[$2] = $3 }
    END {
      if ("__clang__" in macro) {
        printf "clang %s.%s.%s\n", macro["__clang_major__"],
          macro["__clang_minor__"], macro["__clang_patchlevel__"]
      } else if ("__GNUC__" in macro) {
        printf "gcc %s.%s.%s\n", macro["__GNUC__"], macro["__GNUC_MINOR__"],
          macro["__GNUC_PATCHLEVEL__"]
      } else {
        exit 1
      }
    }')" || error_exit 1 "error: C compiler $_COMPILER_COMMAND predefines \
neither __clang__ nor __GNUC__"
}

build_manifest() {
  if [ "$REGENERATE" = 1 ]; then
    local _header_rows
    artifact_path _header_rows "$REPORT_ARTIFACTS_DIR" header-rows
    _REVISION="$(manifest_value "$_header_rows" revision)"
    _CPU_MODEL="$(manifest_value "$_header_rows" cpu)"
    _MEMORY_USAGE="$(manifest_value "$_header_rows" memory)"
    _OPERATING_SYSTEM="$(manifest_value "$_header_rows" os)"
    _COMPILER_NAME="$(manifest_value "$_header_rows" compiler)"
    _BUILD_DESC="$(manifest_value "$_header_rows" build)"
    if [ -z "$_REVISION" ] || [ -z "$_CPU_MODEL" ] \
      || [ -z "$_MEMORY_USAGE" ] || [ -z "$_OPERATING_SYSTEM" ] \
      || [ -z "$_COMPILER_NAME" ] || [ -z "$_BUILD_DESC" ]; then
      error_exit 2 "error: --regenerate: $_header_rows is missing one of its \
revision=, cpu=, memory=, os=, compiler= or build= rows"
    fi
    return
  fi
  _REVISION="$(revision_describe "$_REPO")"
  _CPU_MODEL="$(lscpu | grep -E 'Model name' | head -1 \
    | sed 's/^Model name:[[:space:]]*//' || true)"
  [ -n "$_CPU_MODEL" ] || _CPU_MODEL=unknown
  _MEMORY_USAGE="$(awk '
    $1 == "MemTotal:" { total = $2 }
    $1 == "MemAvailable:" { available = $2 }
    END {
      if (total == 0 || available == "") exit 1
      printf "%.2f GiB (%.0f%% use)\n", total / 1048576,
        (total - available) * 100 / total
    }' /proc/meminfo)" || error_exit 1 \
    "error: no MemTotal: and MemAvailable: rows in /proc/meminfo"
  _OPERATING_SYSTEM="$(sed -n 's/^PRETTY_NAME="*\([^"]*\)"*$/\1/p' \
    /etc/os-release)"
  [ -n "$_OPERATING_SYSTEM" ] || error_exit 1 \
    "error: no PRETTY_NAME= row in /etc/os-release"
  compiler_identify
}

report_prepare() {
  report_delete "$_OUT_DIR"
  [ "$REGENERATE" = 1 ] || artifacts_clean
  local _log_kind=profile-log _log_file
  if [ "$REGENERATE" = 1 ]; then
    _log_kind=profile-regenerate-log
  fi
  artifact_path _log_file "$REPORT_ARTIFACTS_DIR" "$_log_kind"
  report_begin "$_OUT_DIR" "$_log_file" \
    "tests/perf2html/perf2html.sh $TIMESTAMP: ${_CMAKE_FLAGS[*]}: $_OUT_DIR"
  [ "$REGENERATE" = 1 ] \
    || test_list_write "$REPORT_ARTIFACTS_DIR" "${_TESTS[@]}"
  source_cache_fill
}

tree_build() {
  local _dir="$1"
  shift
  rm -f "$_dir/CMakeCache.txt"
  local -x CCACHE_NAMESPACE="$BUILD_CCACHE_NAMESPACE"
  local _configure_command=(cmake -S "$_REPO" -B "$_dir" -G Ninja
    -DCURL_USE_LIBPSL=OFF -DCMAKE_C_COMPILER_LAUNCHER=ccache "$@"
    "-DCMAKE_C_COMPILER=$_COMPILER_COMMAND")
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
  _TREE_NAME="${_COMPILER_NAME//[^[:alnum:]]/-}-${#_flag_string}_"
  _TREE_NAME+="${_flag_string//[^[:alnum:]]/}"
  _BUILD_TREE="$_REPO/$BUILD_DIR/$_TREE_NAME"
  _TRACE_TREE="$_REPO/$TRACE_BUILD_DIR/$_TREE_NAME"
  _BIN="$_BUILD_TREE/tests/perf/perf"
  _BIN_REL="$(path_display "$_BIN" "$_REPO")"
  _TRACE_BIN="$_TRACE_TREE/tests/perf/perf"
  _TRACE_BIN_REL="$(path_display "$_TRACE_BIN" "$_REPO")"
}

trees_compile() {
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
  command_run "$_COMPILER_COMMAND" -O2 -fcf-protection=none \
    -DTEST_SAMPLES_SIZE="$TEST_SAMPLES_SIZE" \
    -c "$PERF2HTML_DIR_/src/cyg_callback.c" -o "$_TRACE_TREE/cyg_callback.o"
  rm -f "$_TRACE_BIN"
  local _hook="$_TRACE_TREE/cyg_callback.o"
  tree_build "$_TRACE_TREE" "${_trace_flags[@]}" \
    "-DCMAKE_EXE_LINKER_FLAGS=$_hook -Wl,--export-dynamic"
  log_verbose "$_line | $(duration_format "$_start")"
  _BUILD_DESC="${_CMAKE_FLAGS[*]}"
}

header_rows_write() {
  local _header_rows
  _HEADER_ROWS=(
    "revision=$_REVISION"
    "cpu=$_CPU_MODEL"
    "memory=$_MEMORY_USAGE"
    "os=$_OPERATING_SYSTEM"
    "compiler=$_COMPILER_NAME"
    "build=$_BUILD_DESC"
    "executable=$_BIN_REL"
    "$(manifest_recorded_row)"
  )
  [ "$REGENERATE" = 0 ] || return 0
  artifact_path _header_rows "$REPORT_ARTIFACTS_DIR" header-rows
  printf '%s\n' "${_HEADER_ROWS[@]}" >"$_header_rows"
}

build_compile() {
  step_run 1 paths build_paths
  step_run 2 trees trees_compile
  step_run 3 "header rows" header_rows_write
}

trace_record() {
  local _test="$1" _loops="$2" _trace_file="$3" _skip="$4"
  PERF_TRACE_OUT="$_trace_file" PERF_TRACE_SKIP="$_skip" \
    taskset -c "$PROFILE_PINNED_CPU" "$_TRACE_BIN" "$_test" "$_loops"
}

trace_run() {
  local _test="$1" _loops="$2" _trace_file="$3" _skip="$4" _page="$5"
  local _name="${_trace_file##*/}" _pinned
  _pinned="PERF_TRACE_SKIP=$_skip taskset -c $PROFILE_PINNED_CPU"
  echo "\$ PERF_TRACE_OUT=$_name $_pinned $_TRACE_BIN_REL $_test $_loops" \
    >>"$_page"
  page_command_run "$_page" \
    "PERF_TRACE_OUT=$_trace_file $_pinned $_TRACE_BIN $_test $_loops" \
    trace_record "$_test" "$_loops" "$_trace_file" "$_skip"
}

trace_convert() {
  python3 "$PERF2HTML_DIR_/scripts/trace_to_speedscope.py" convert \
    "--artifacts=$ARTIFACTS_DIR" "--report=$_OUT_DIR" "--test=$1" \
    "--loops=$2" 2>&1 | sed "s#$REPORT_ARTIFACTS_DIR/##g"
}

flame_app_name_read() {
  local _variable="$1" _document="$2" _role="$3" _line _rest _name=""
  local _pattern="${FLAME_GRAPH_APP_NAME_PATTERNS[$_role]}" _found=0
  while IFS= read -r _line; do
    _rest="$_line"
    while [[ "$_rest" =~ $_pattern ]]; do
      _found=$((_found + 1))
      _name="${BASH_REMATCH[1]}"
      _rest="${_rest#*"${BASH_REMATCH[0]}"}"
    done
  done <"$_document"
  [ "$_found" = 1 ] || error_exit 1 "error: $_document names $_found \
$_role file(s) matching $_pattern, expected exactly 1"
  printf -v "$_variable" '%s' "$_name"
}

flame_app_install() {
  local _out="$1" _font
  flame_app_name_read _FLAME_APP_JS "$SPEEDSCOPE_RELEASE/index.html" script
  flame_app_name_read _FLAME_APP_CSS "$SPEEDSCOPE_RELEASE/index.html" \
    stylesheet
  flame_app_name_read _font "$SPEEDSCOPE_RELEASE/$_FLAME_APP_CSS" font
  mkdir -p "$_out/$FLAME_GRAPH_APP_DIR_NAME"
  cp "$SPEEDSCOPE_RELEASE/$_FLAME_APP_JS" \
    "$SPEEDSCOPE_RELEASE/$_FLAME_APP_CSS" "$SPEEDSCOPE_RELEASE/$_font" \
    "$_out/$FLAME_GRAPH_APP_DIR_NAME"/
}

trace_render() {
  local _test="$1" _loops="$2"
  local _seen _seen_file _tree_display _trace_file _trace_log _shown
  artifact_path _seen_file "$REPORT_ARTIFACTS_DIR" trace-seen "$_test"
  artifact_path _trace_file "$REPORT_ARTIFACTS_DIR" trace-binary "$_test"
  artifact_path _trace_log "$REPORT_ARTIFACTS_DIR" trace-log "$_test"

  heading_print "PERF_TRACE_OUT=${_trace_file##*/} perf $_test $_loops"
  _tree_display="$(path_display "$_TRACE_TREE" "$_REPO")"
  {
    echo "# $_tree_display = this report's build flags +"
    echo "# -finstrument-functions, linked with"
    echo "# tests/perf2html/src/cyg_callback.c, which reads rdtsc at every"
    echo "# function enter and exit. Run 1 counts events, run 2 keeps up to"
    echo "# $TEST_SAMPLES_SIZE samples, an enter and exit pair each, right"
    echo "# after the run's midpoint (TEST_SAMPLES_SIZE in"
    echo "# tests/perf2html/scripts/settings.sh)."
  } >"$_trace_log"
  trace_run "$_test" "$_loops" "$_trace_file" "$TRACE_SKIP_ALL" "$_trace_log"
  command_run python3 "$PERF2HTML_DIR_/scripts/trace_to_speedscope.py" seen \
    "--artifacts=$ARTIFACTS_DIR" "--report=$_OUT_DIR" "--test=$_test"
  read -r _seen <"$_seen_file" && [[ "$_seen" =~ ^[0-9]+$ ]] || error_exit 1 \
    "error: $_seen_file holds no event count: $_seen"
  trace_run "$_test" "$_loops" "$_trace_file" "$((_seen / 2))" "$_trace_log"
  _shown="python3 $PERF2HTML_DIR_/scripts/trace_to_speedscope.py convert"
  _shown+=" --artifacts=$ARTIFACTS_DIR --report=$_OUT_DIR --test=$_test"
  _shown+=" --loops=$_loops"
  page_command_run "$_trace_log" "$_shown" \
    trace_convert "$_test" "$_loops"
}

callgrind_measure() {
  local _test="$1" _cg_file _log _start
  artifact_path _cg_file "$REPORT_ARTIFACTS_DIR" callgrind "$_test"
  artifact_path _log "$REPORT_ARTIFACTS_DIR" valgrind-log "$_test"
  heading_print "valgrind --tool=callgrind perf $_test $TEST_LOOPS"
  _start="$(clock_microseconds)"
  command_run taskset -c "$PROFILE_PINNED_CPU" valgrind --tool=callgrind \
    --cache-sim=yes --branch-sim=yes --trace-redir=yes \
    --LL="$CALLGRIND_LAST_LEVEL_CACHE" \
    --callgrind-out-file="$_cg_file" --log-file="$_log" \
    "$_BIN" "$_test" "$TEST_LOOPS"
  _CALLGRIND_DURATION="$(duration_format "$_start")"
}

symbols_resolve() {
  local _test="$1"
  heading_print "python3 callgrind_symbols.py $_test"
  command_run python3 "$PERF2HTML_DIR_/scripts/callgrind_symbols.py" \
    "--artifacts=$ARTIFACTS_DIR" "--report=$_OUT_DIR" "--test=$_test"
}

timing_record() {
  local _counter_value _counter_unit _counter_name _remaining_fields
  perf stat -x, -o "$2" -e cycles:u,instructions:u \
    taskset -c "$PROFILE_PINNED_CPU" "$_BIN" "$1" "$TEST_LOOPS" \
    && while IFS=, read -r _counter_value _counter_unit _counter_name \
      _remaining_fields; do
      case "$_counter_name" in
        *cycles*) printf 'Cycles:    %s\n' "$_counter_value" ;;
        *instructions*) printf 'Instructions: %s\n' "$_counter_value" ;;
      esac
    done <"$2"
}

timing_measure() {
  local _test="$1" _stat_file _page _shown _page_words
  local _summary_headers _summary_values
  artifact_path _stat_file "$REPORT_ARTIFACTS_DIR" timing-csv "$_test"
  artifact_path _page "$REPORT_ARTIFACTS_DIR" timing-page "$_test"
  heading_print "perf stat -e cycles:u,instructions:u perf $_test" \
    "$TEST_LOOPS"
  echo "\$ perf stat -e cycles:u,instructions:u taskset -c" \
    "$PROFILE_PINNED_CPU $_BIN_REL $_test $TEST_LOOPS" >"$_page"
  _shown="perf stat -x, -o $_stat_file -e cycles:u,instructions:u taskset"
  page_command_run "$_page" \
    "$_shown -c $PROFILE_PINNED_CPU $_BIN $_test $TEST_LOOPS" \
    timing_record "$_test" "$_stat_file"
  _summary_headers=(Test Loops Callgrind)
  _summary_values=("$_test" "$TEST_LOOPS" "$_CALLGRIND_DURATION")
  while read -r -a _page_words; do
    case "${_page_words[0]-}" in
      Time/*: | Errors:)
        _summary_headers+=("${_page_words[0]%:}")
        _summary_values+=("${_page_words[*]:1}")
        ;;
    esac
  done <"$_page"
  [[ "${_summary_headers[*]}" == *" Time/"* ]] \
    || error_exit 1 "error: no Time/<unit>: line in $_page"
  table_print "${#_summary_headers[@]}" "${_summary_headers[@]}" \
    "${_summary_values[@]}"
}

run_one() {
  local _test="$1"
  if [ "$REGENERATE" = 1 ]; then
    log_verbose "$(printf '%-13sloops=%s | reused' "$_test" "$TEST_LOOPS")"
    return
  fi
  step_run 1 callgrind callgrind_measure "$_test"
  step_run 2 symbols symbols_resolve "$_test"
  step_run 3 timing timing_measure "$_test"
  step_run 4 trace trace_render "$_test" "$TEST_LOOPS"
}

tests_record() {
  local _index
  for _index in "${!_TESTS[@]}"; do
    step_run "$((_index + 1))" "${_TESTS[_index]}" run_one "${_TESTS[_index]}"
  done
  [ "$REGENERATE" = 1 ] || artifacts_verify recorded
}

timer_artifacts_write() {
  local _root_directory _root_name _archive _test_name _kind _member _source
  printf -v _root_directory "$TIMER_ARTIFACTS_ROOT_FORMAT" \
    "$REPORT_ARTIFACTS_DIR" "$TIMESTAMP"
  raw_data_archive_path _archive "$_OUT_DIR" "$TIMESTAMP"
  _root_name="${_root_directory##*/}"

  heading_print "tar ${_archive##*/}"
  rm -rf "$_root_directory"
  mkdir "$_root_directory"
  for _test_name in "${_TESTS[@]}"; do
    artifact_path _source "$REPORT_ARTIFACTS_DIR" callgrind "$_test_name"
    artifact_path _member "$_root_directory" callgrind "$_test_name"
    cp "$_source" "$_member"
    sed -i "s#$_REPO/##g" "$_member"
  done
  for _kind in file-data test-list; do
    artifact_path _source "$REPORT_ARTIFACTS_DIR" "$_kind"
    artifact_path _member "$_root_directory" "$_kind"
    cp "$_source" "$_member"
  done
  command_run tar --sort=name --mtime=@0 --owner=0 --group=0 \
    --numeric-owner -cJf "$_archive" -C "$REPORT_ARTIFACTS_DIR" "$_root_name"
  rm -r "$_root_directory"
}

pages_write() {
  local _flags=("--artifacts=$ARTIFACTS_DIR" "--report=$_OUT_DIR")
  step_run 1 "flame graph app" flame_app_install "$_OUT_DIR"
  step_run 2 "flame graph page" page_tool_run build_flame_graph.py page \
    "--report=$_OUT_DIR" "--app-js=$_FLAME_APP_JS" \
    "--app-css=$_FLAME_APP_CSS"
  step_run 3 "flame graph profiles" page_tool_run build_flame_graph.py \
    profiles "${_flags[@]}"
  step_run 4 "heat map data" page_tool_run callgrind_to_heatmap.py data \
    "${_flags[@]}"
  step_run 5 callers page_tool_run build_report.py callers "${_flags[@]}"
  step_run 6 "call graph" page_tool_run build_report.py call-graph \
    "${_flags[@]}"
  step_run 7 "timer artifacts" timer_artifacts_write
  step_run 8 overview page_tool_run build_report.py overview "${_flags[@]}" \
    "${README_HTML_FLAGS[@]}"
  step_run 9 "heat map page" page_tool_run callgrind_to_heatmap.py page \
    "--report=$_OUT_DIR"
  step_run 10 finish report_finish "$_OUT_DIR" \
    "$REPORT_MANIFEST_VERSION_FULL" "${_HEADER_ROWS[@]}"
}

main() {
  args_parse "$@"
  verbose_begin
  title_print "$_SCRIPT" "$@"
  recordings_check
  step_run 1 toolchain toolchain_check
  step_run 2 "source cache" source_cache_sync
  step_run 3 manifest build_manifest
  step_run 4 report report_prepare
  step_run 5 build build_compile
  step_run 6 tests tests_record
  step_run 7 pages pages_write
  heading_print "$_SCRIPT, after the seven steps"
  table_print "${#STEP_NAMES[@]}" "${STEP_NAMES[@]}" "${STEP_SECONDS[@]}"
}

main "$@"
