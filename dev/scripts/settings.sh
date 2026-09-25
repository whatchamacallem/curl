# dev/scripts/settings.sh

# the temporary artifacts directory's default name, beside the report
ARTIFACTS_NAME=perf2html_temporary_artifacts

# the assets/ script an error page reads the manifest rows back from
ASSET_REPORT_MANIFEST_SCRIPT_NAME=report_manifest.js

# dir at the repo root holding the trees profiling reads, one per set of
# cmake flags, named by build_paths
BUILD_DIR=build-relwithdebinfo

# loops one callgrind run of a test does
CALLGRIND_LOOPS=200

# the apt package each tool ships in, where tool and package differ.
# install_command_of() reads it
declare -A CONTAINING_PACKAGES=(
  [cmake]=cmake
  [ninja]=ninja-build
  [ccache]=ccache
  [valgrind]=valgrind
  [taskset]=util-linux
  [python3]=python3
  [cksum]=coreutils
)

# cmake flags the batch builds the modified tree with when given none
DEFAULT_FLAGS=(-D CMAKE_C_FLAGS=-Os)

# the report-root directory holding the one shared speedscope copy
FLAME_GRAPH_APP_DIR_NAME=flame-graph-app

# each glob must match exactly one file in the speedscope release. Quoted,
# so sourcing never expands one against the current directory
FLAME_GRAPH_APP_FILE_GLOBS=('speedscope-*.js' 'speedscope-*.css' '*.woff2')

# working file the overview reads its LABEL=VALUE rows from. MANIFEST.txt
# cannot be it, being written after every page exists
HEADER_ROWS_NAME=header.overview

# lines of a failed child's output reprinted on the terminal. The whole of
# it is in $RUN_LOG either way, which the same message names
LOG_FAILURE_TAIL_LINES=40

# the core every measured run is pinned to. Unpinned WSL2 noise is ~106%
PROFILE_PINNED_CPU=3

# what one test's native timing recording is named, before its test name,
# stamp and .csv. It is the artifact --regenerate dates the executable against
PROFILE_TIMING_FILE_PREFIX=perf-stat

# the report-root directory holding the shared copy of our own theme
REPORT_ASSETS_DIR_NAME=assets

# the batch's report directory name for the unmodified build
REPORT_BASELINE_DIR_NAME=perf2html_baseline_report

# the batch's report directory name for the subtraction of the two
REPORT_DIFF_DIR_NAME=perf2html_diff_report

# the LABEL= row a report's MANIFEST.txt records its checksum on. The shell
# writes and reads it; validate_report.py and enforcer.sh check it
REPORT_MANIFEST_CHECKSUM_LABEL=checksum

# the exact first line of a MANIFEST.txt, one per kind of report, and the only
# thing making a directory one. Bump one and older reports are all rejected
REPORT_MANIFEST_VERSION_DIFF='curl/perf2html_diff.sh v1'
REPORT_MANIFEST_VERSION_FULL='curl/perf2html.sh v1'

# the batch's report directory name for the build carrying the flags
REPORT_MODIFIED_DIR_NAME=perf2html_modified_report

# the extension of a report's raw-data archive, one per test, page-visible
REPORT_RAW_ARCHIVE_SUFFIX=.txz

# loops one native timing run of a test does
TIMING_LOOPS=10000

# dir at the repo root holding the -finstrument-functions trees the flame
# graph's trace comes from, named as under BUILD_DIR
TRACE_BUILD_DIR=build-instr

# UINT64_MAX: skip every event, making it a count-only trace run
TRACE_SKIP_ALL=18446744073709551615

# the diagnostic level, one per --verbose given: 0 prints no diagnostics, 1
# the steps and their output, 2 cmake's configure output too
VERBOSE=0

# the column every --verbose line wraps at, the markdown's own hard max
VERBOSE_LINE_WIDTH_CHARS=79
