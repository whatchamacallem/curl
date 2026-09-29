# dev/scripts/settings.sh

# the temporary artifacts directory's default name, beside the report
ARTIFACTS_NAME=perf2html_temporary_artifacts

# the assets/ script written last and counted by the checksum, whose one
# line names the manifest version, proving the run finished
ASSET_REPORT_COMPLETE_SCRIPT_NAME=report_complete.js

# the ccache namespace tree_build tags every compile with, so clean.sh
# evicts our entries and nobody else's
BUILD_CCACHE_NAMESPACE=perf2html

# dir at the repo root holding the trees profiling reads, one per set of
# cmake flags, named by build_paths
BUILD_DIR=build-relwithdebinfo

# where the archive serves source packages, joined with the source package
# name's pool letter, its name, and the orig tarball, by source_cache_sync
CACHE_ARCHIVE_BASE_URL=http://archive.ubuntu.com/ubuntu/pool/main

# the installed package whose source the heat map reads, and the one dpkg
# names its source package and version through
CACHE_EXTERNAL_PACKAGE=libc6

# the root every downloaded external source tree sits under, one directory
# per source package, one below that per version
CACHE_ROOT_DIR=~/.cache/perf2html

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
  [curl]=curl
  [tar]=tar
  [xz]=xz-utils
  ["dpkg-query"]=dpkg
)

# cmake flags the batch builds the modified tree with when given none
DEFAULT_FLAGS=(-D CMAKE_C_FLAGS=-Os)

# the report-root directory holding the one shared speedscope copy
FLAME_GRAPH_APP_DIR_NAME=flame-graph-app

# each glob must match exactly one file in the speedscope release. Quoted,
# so sourcing never expands one against the current directory
FLAME_GRAPH_APP_FILE_GLOBS=('speedscope-*.js' 'speedscope-*.css' '*.woff2')

# working file holding a measured run's LABEL=VALUE rows, named after its
# report: the overview reads it; --regenerate finds the run's recorded= in it
HEADER_ROWS_NAME=header.overview

# lines of a failed child's output reprinted on the terminal. The whole of
# it is in $RUN_LOG either way, which the same message names
LOG_FAILURE_TAIL_LINES=40

# the core every measured run is pinned to. Unpinned WSL2 noise is ~106%
PROFILE_PINNED_CPU=3

# what one test's native timing recording is named, before its test name,
# recorded time and .csv: what --regenerate dates the executable against
PROFILE_TIMING_FILE_PREFIX=perf-stat

# the report-root directory holding the shared copy of our own theme
REPORT_ASSETS_DIR_NAME=assets

# the batch's report directory name for the unmodified build
REPORT_BASELINE_DIR_NAME=perf2html_baseline_report

# the batch's report directory name for the subtraction of the two
REPORT_DIFF_DIR_NAME=perf2html_diff_report

# the LABEL= row a report's MANIFEST.txt records its checksum on. The shell
# writes and reads it; test_report.py and test_expected_behavior.sh read
REPORT_MANIFEST_CHECKSUM_LABEL=checksum

# the exact first line of a MANIFEST.txt, one per kind of report, and the only
# thing making a directory one. Bump one and older reports are all rejected
REPORT_MANIFEST_VERSION_DIFF='curl/perf2html_diff.sh v1'
REPORT_MANIFEST_VERSION_FULL='curl/perf2html.sh v1'

# the batch's report directory name for the build carrying the flags
REPORT_MODIFIED_DIR_NAME=perf2html_modified_report

# the extension of a report's raw-data archive, one per test, page-visible,
# and of the whole-report archive --txz writes and every script reads back
REPORT_RAW_ARCHIVE_SUFFIX=.txz

# loops one native timing run of a test does
TIMING_LOOPS=10000

# dir at the repo root holding the -finstrument-functions trees the flame
# graph's trace comes from, named as under BUILD_DIR
TRACE_BUILD_DIR=build-instr

# UINT64_MAX: skip every event, making it a count-only trace run
TRACE_SKIP_ALL=18446744073709551615

# the diagnostic level, one per --verbose given: 0 prints no diagnostics, 1
# the steps and their output as markdown, 2 raw text and cmake too, 3 xtrace
VERBOSE=0

# the level from which every line is plain text: no markdown, no filtering,
# and a child's output, cmake's configure included, reaches the terminal raw
VERBOSE_RAW_LEVEL=2

# the level from which a script turns on set -o xtrace, right after it has
# parsed its arguments
VERBOSE_TRACE_LEVEL=3
