# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

ARTIFACTS_NAME=perf2html_temporary_artifacts

ARTIFACT_ARCHIVE_KINDS=(callgrind)

ARTIFACT_DIFFED_KINDS=(caller-counts delta)

declare -A ARTIFACT_FILE_PURPOSES=(
  ["baseline-header"]="the baseline report's header block"
  ["baseline-profiles"]="the baseline report's raw data archive, extracted"
  [callgrind]="the callgrind recording"
  ["caller-counts"]="the callers diff with the baseline costs"
  [delta]="the callgrind delta, modified minus baseline"
  ["diff-log"]="the diff run's log"
  ["diff-regenerate-log"]="the last diff --regenerate run's log"
  ["file-data"]="the paths document, each path's code"
  ["header-rows"]="the manifest rows of the measuring run"
  ["modified-header"]="the modified report's header block"
  ["modified-profiles"]="the modified report's raw data archive, extracted"
  ["profile-log"]="the measuring run's log"
  ["profile-regenerate-log"]="the last --regenerate run's log"
  ["test-list"]="the test names, one per line, sorted"
  ["timing-json"]="the perf stat counters, one JSON line per event"
  ["timing-page"]="the timing page, the command and the curl perf tool's runs"
  ["timing-summary"]="the timing summary rows, one label=value each"
  ["trace-binary"]="the function trace of the sampled run"
  ["trace-log"]="the trace page, both runs and the conversion"
  ["trace-maps"]="the traced process's mappings"
  ["trace-speedscope"]="the speedscope profile of the sampled run"
  ["valgrind-log"]="the valgrind log with the objects loaded"
)

ARTIFACT_RECORDED_KINDS=(callgrind timing-json timing-page trace-log
  trace-speedscope valgrind-log)

declare -A ARTIFACT_RUN_FILE_FORMATS=(
  ["baseline-header"]='%s/baseline.txt'
  ["baseline-profiles"]='%s/baseline'
  ["diff-log"]='%s/perf2html_diff.log'
  ["diff-regenerate-log"]='%s/perf2html_diff.regenerate.log'
  ["file-data"]='%s/0_file_data.json'
  ["header-rows"]='%s/perf2html.txt'
  ["modified-header"]='%s/modified.txt'
  ["modified-profiles"]='%s/modified'
  ["profile-log"]='%s/perf2html.log'
  ["profile-regenerate-log"]='%s/perf2html.regenerate.log'
  ["test-list"]='%s/test_list.txt'
)

declare -A ARTIFACT_TEST_FILE_FORMATS=(
  [callgrind]='%s/%s.callgrind.out'
  ["caller-counts"]='%s/%s.callgrind_diff.json'
  [delta]='%s/%s.callgrind_diff.out'
  ["timing-json"]='%s/%s.perf-stat.json'
  ["timing-page"]='%s/%s.perf-stat.txt'
  ["timing-summary"]='%s/%s.perf-stat.summary'
  ["trace-binary"]='%s/%s.cyg_callback.bin'
  ["trace-log"]='%s/%s.cyg_callback.log'
  ["trace-maps"]='%s/%s.cyg_callback.bin.maps'
  ["trace-speedscope"]='%s/%s.trace_to_speedscope.json'
  ["valgrind-log"]='%s/%s.valgrind.log'
)

ASSET_DEBUG_SCRIPT_NAME=debug.js

BUILD_CCACHE_NAMESPACE=perf2html

BUILD_DIR=build-relwithdebinfo

CACHE_ARCHIVE_BASE_URL=http://archive.ubuntu.com/ubuntu/pool/main

CACHE_EXTERNAL_PACKAGE=libc6

CACHE_ROOT_DIR=~/.cache/perf2html

CALLGRIND_LAST_LEVEL_CACHE=16777216,16,64

declare -A CONTAINING_PACKAGES=(
  [cmake]=cmake
  [ninja]=ninja-build
  [ccache]=ccache
  [cc]=build-essential
  [valgrind]=valgrind
  [perf]=linux-perf
  [taskset]=util-linux
  [python3]=python3
  [addr2line]=binutils
  [objdump]=binutils
  [readelf]=binutils
  [cksum]=coreutils
  [curl]=curl
  [tar]=tar
  [xz]=xz-utils
  ["dpkg-query"]=dpkg
)

DEFAULT_FLAGS=(-D CMAKE_C_FLAGS=-Os)

DIFF_EXTRACTED_ROOT_DISPLAY_NAME='$tmp'

FLAME_GRAPH_APP_DIR_NAME=flame-graph-app

declare -A FLAME_GRAPH_APP_NAME_PATTERNS=(
  [font]='url\("\./([^"]+\.woff2)"\)'
  [script]='<script src="([^"]+)"'
  [stylesheet]='<link rel="stylesheet" href="([^"]+)"'
)

LOG_FAILURE_TAIL_LINES=40

OVERVIEW_PAGE_PATH=index.html

PACKAGE_INSTALL_COMMAND='sudo apt-get install -y'

PROFILE_PINNED_CPU=3

PROFILE_START_FUNCTION_NAME=main
PROFILE_STOP_FUNCTION_NAME=exit

README_HTML_BUILD_PATH=build/README.html
README_HTML_NAME=README.html
README_MARKDOWN_NAME=README.md

REPORT_ARTIFACTS_DIR_FORMAT='%s/%s'

REPORT_BASELINE_DIR_NAME=perf2html_baseline_report

REPORT_DIFF_DIR_NAME=perf2html_diff_report

REPORT_MANIFEST_CHECKSUM_LABEL=checksum

REPORT_MANIFEST_VERSION_DIFF='curl/perf2html_diff.sh v0'
REPORT_MANIFEST_VERSION_FULL='curl/perf2html.sh v0'
REPORT_MANIFEST_VERSION_LABEL=manifest

REPORT_MODIFIED_DIR_NAME=perf2html_modified_report

REPORT_RAW_ARCHIVE_SUFFIX=.txz

REPORT_SCRIPTS_DIR_NAME=scripts

REPORT_SOURCES_DIR_NAME=sources

TEST_LOOPS=100

TEST_SAMPLES_SIZE=$((TEST_LOOPS * 4 * 1024))

TIMER_ARTIFACTS_ROOT_FORMAT='%s/timer-artifacts-%s'

TIMING_PERF_STAT_EVENTS=(cycles:u instructions:u branches:u branch-misses:u
  L1-dcache-loads:u L1-dcache-load-misses:u)

TIMING_PERF_STAT_RUNS=5

declare -A TOOL_INSTALL_COMMANDS=(
  [speedscope]='npm install -g speedscope'
)

TRACE_BUILD_DIR=build-instr

TRACE_OUT_VARIABLE=PERF_TRACE_OUT

# 0xABCDEF0123456000. Uses json compatible precision.
TRACE_SKIP_ALL=9223372036854775808
TRACE_SKIP_VARIABLE=PERF_TRACE_SKIP

VERBOSE=0

VERBOSE_RAW_LEVEL=2

VERBOSE_TRACE_LEVEL=3
