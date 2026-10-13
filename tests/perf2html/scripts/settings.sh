# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

ARTIFACTS_NAME=perf2html_temporary_artifacts

ASSET_DEBUG_SCRIPT_NAME=debug.js

BUILD_CCACHE_NAMESPACE=perf2html

BUILD_DIR=build-relwithdebinfo

CACHE_ARCHIVE_BASE_URL=http://archive.ubuntu.com/ubuntu/pool/main

CACHE_EXTERNAL_PACKAGE=libc6

CACHE_ROOT_DIR=~/.cache/perf2html

CALLGRIND_FILE_DATA_NAME=0_file_data

CALLGRIND_LAST_LEVEL_CACHE=16777216,16,64

CALLGRIND_OUTPUT_FILE_EXTENSION=out

CALLGRIND_OUTPUT_TOOL_NAME=callgrind

declare -A CONTAINING_PACKAGES=(
  [cmake]=cmake
  [ninja]=ninja-build
  [ccache]=ccache
  [valgrind]=valgrind
  [taskset]=util-linux
  [python3]=python3
  [cksum]=coreutils
  [curl]=curl
  [tar]=tar
  [xz]=xz-utils
  ["dpkg-query"]=dpkg
)

DEFAULT_FLAGS=(-D CMAKE_C_FLAGS=-Os)

DIFF_CALLER_COUNTS_FILE_EXTENSION=json

DIFF_DELTA_TOOL_NAME=callgrind_diff

DIFF_EXTRACTED_ROOT_DISPLAY_NAME='$tmp'

DIFF_TOOL_NAME=perf2html_diff

FLAME_GRAPH_APP_DIR_NAME=flame-graph-app

FLAME_GRAPH_APP_FILE_GLOBS=('speedscope-*.js' 'speedscope-*.css' '*.woff2')

LOG_FAILURE_TAIL_LINES=40

PROFILE_PINNED_CPU=3

PROFILE_TIMING_TOOL_NAME=perf-stat

PROFILE_TOOL_NAME=perf2html

REPORT_SCRIPTS_DIR_NAME=scripts

REPORT_BASELINE_DIR_NAME=perf2html_baseline_report

REPORT_DIFF_DIR_NAME=perf2html_diff_report

REPORT_MANIFEST_CHECKSUM_LABEL=checksum

REPORT_MANIFEST_VERSION_DIFF='curl/perf2html_diff.sh v1'
REPORT_MANIFEST_VERSION_FULL='curl/perf2html.sh v1'
REPORT_MANIFEST_VERSION_LABEL=manifest

REPORT_MODIFIED_DIR_NAME=perf2html_modified_report

REPORT_RAW_ARCHIVE_SUFFIX=.txz

REPORT_SOURCES_DIR_NAME=sources

REPORT_TEST_SUITE_NAME=all

TEST_LOOPS=100

TEST_SAMPLES_SIZE=$((TEST_LOOPS * 4 * 1024))

TIMER_ARTIFACTS_NAME_PREFIX=timer-artifacts-

TRACE_BUILD_DIR=build-instr

TRACE_SKIP_ALL=18446744073709551615

TRACE_SPEEDSCOPE_TOOL_NAME=trace_to_speedscope

TRACE_TOOL_NAME=cyg_callback

VALGRIND_LOG_TOOL_NAME=valgrind

VERBOSE=0

VERBOSE_RAW_LEVEL=2

VERBOSE_TRACE_LEVEL=3
