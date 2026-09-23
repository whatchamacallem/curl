# dev/scripts/settings.sh - every setting the shell reads, and nothing
# else. shared.sh sources it, and settings.py parses it at import, binding
# every name here as a setting of its own under the same spelling, so this
# file stays pure: no function, no command, no $ expansion, no logic.
#
# The grammar settings.py accepts, and rejects anything else:
#   - a blank line, or a # comment line
#   - NAME=value, the value one word: bare (letters, digits and _-./,:=+%@),
#     'single-quoted', or "double-quoted" with no $, backtick or backslash
#   - NAME=(word word ...), over one or more lines up to the closing ")",
#     each element a word as above -> tuple[str, ...]
#   - declare -A NAME=([key]=word ...), over one or more lines -> dict
# A scalar matching -?[0-9]+ is an int in Python, every other scalar a str,
# and container elements stay str. A name is SCREAMING_SNAKE and must not
# already be bound in settings.py.

# the temporary artifacts directory's default name, beside the report
ARTIFACTS_NAME=perf2html_temporary_artifacts

# the assets/ script an error page reads the manifest rows back from
ASSET_REPORT_MANIFEST_SCRIPT_NAME=report_manifest.js

# the tree profiling reads. -O0 attributes cost to the wrong lines
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

# each glob must match exactly one file in the speedscope release: the
# engine, its stylesheet and the font the stylesheet names. Quoted, so
# sourcing never expands one against the current directory
FLAME_GRAPH_APP_FILE_GLOBS=('speedscope-*.js' 'speedscope-*.css' '*.woff2')

# working file the overview reads its LABEL=VALUE rows from. MANIFEST.txt
# cannot be it, being written after every page exists
HEADER_ROWS_NAME=header.overview

# lines of a failed child's output reprinted on the terminal. The whole of
# it is in $RUN_LOG either way, which the same message names
LOG_FAILURE_TAIL_LINES=40

# the core every measured run is pinned to. Unpinned WSL2 noise is ~106%
PROFILE_PINNED_CPU=3

# the report-root directory holding the shared copy of our own theme
REPORT_ASSETS_DIR_NAME=assets

# the batch's report directory name for the unmodified build
REPORT_BASELINE_DIR_NAME=perf2html_baseline_report

# the batch's report directory name for the subtraction of the two
REPORT_DIFF_DIR_NAME=perf2html_diff_report

# the LABEL= row a report's MANIFEST.txt records its checksum on. The shell
# writes that row and reads it back, validate_report.py and reformat.sh
# check it
REPORT_MANIFEST_CHECKSUM_LABEL=checksum

# the exact first line of a MANIFEST.txt, one per kind of report. It is the
# only thing that makes a directory a report, and a diff names
# perf2html_diff.sh, which is how a diff can never be read back as a diff
# input. Bump one and every tool rejects the reports written before it
REPORT_MANIFEST_VERSION_DIFF='curl/perf2html_diff.sh v1'
REPORT_MANIFEST_VERSION_FULL='curl/perf2html.sh v1'

# the batch's report directory name for the build carrying the flags
REPORT_MODIFIED_DIR_NAME=perf2html_modified_report

# the extension of a report's raw-data archive, one per test, page-visible
REPORT_RAW_ARCHIVE_SUFFIX=.txz

# When the profiler run started, the way __DATE__ is when the compiler
# ran. Do not move.
TIMESTAMP="$(date +%s)"

# loops one native timing run of a test does
TIMING_LOOPS=10000

# the -finstrument-functions tree the flame graph's trace comes from
TRACE_BUILD_DIR=build-instr

# UINT64_MAX: skip every event, making it a count-only trace run
TRACE_SKIP_ALL=18446744073709551615

# Debug logging flag.
VERBOSE=0
