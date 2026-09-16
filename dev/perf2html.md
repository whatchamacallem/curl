# PERF2HTML.SH 1 "dev tooling" "curl perf"

## NAME

perf2html.sh - profile a curl perf test under callgrind and render an HTML report

## SYNOPSIS

`dev/perf2html.sh` [`--verbose`] [`--top` *N*] [*OUTDIR*] [*PERFTEST*|`all`] [*CFLAGS*...]

## DESCRIPTION

Runs one or every test in `tests/perf/Makefile.inc` under callgrind and
natively, pinned to one core, and writes a self-contained HTML report (a
flame graph, a per-line source heat map, the native timing output, and an
index page with the top-N hottest functions) that opens straight from disk
with nothing fetched at view time.

For each test:

1. configure + build the RelWithDebInfo tree (`-O2 -g`; ccache when found)
2. run the test under callgrind with `--cache-sim=yes --branch-sim=yes`,
   pinned to one core (unpinned runs on WSL2 vary approximately 2x)
3. run the test natively, pinned, for the real timing numbers
4. convert: speedscope flame graph (one profile per event), per-line
   source heat map, the index page with the top-N functions (`--top`)

With `all`, the same pages are then built once more over every test's
callgrind file merged into one profile (the perf binary runs one test per
process, so the combined profile is the sum of the runs above) and the
native times summed, into *OUTDIR*/all/.

## OPTIONS

`--verbose`
: Show everything the tools print (cmake, ninja, valgrind, the perf
  binary, the page generators) under a `== N: ...` banner per step.
  Without it the run is one status line per thing -- the build, each
  test, with `all` the merged report -- built up as its steps finish (ten
  lines for `all`), the last one ending in the report to open; everything
  the tools print goes to `dev/trace/profile.<ts>.log` instead and a
  failing command's output is shown with the error.

`--top` *N*
: Functions listed in each summary's "top N functions by self" table
  (default: 50).

`--verbose` and `--top` are recognized only before *OUTDIR*/*PERFTEST*, in
either order.

*OUTDIR*
: Where the HTML report goes (`mkdir -p`). Default: `dev/report`. A
  relative path is taken relative to the caller's cwd.

*PERFTEST*
: First argument to the perf binary: one of the tests in
  `tests/perf/Makefile.inc` (urlparser, base64enc, ...), or `all` to run
  every test into *OUTDIR*/*test*/ plus a combined report over all of
  them into *OUTDIR*/all/. Default: `all`.

*CFLAGS*...
: Everything else is passed to the compiler for a fresh curl build
  (`CMAKE_C_FLAGS`), e.g. `-DUSE_AVX512`. The flags are *reset* on every
  run, so omitting them builds plain again.

## OUTPUT LAYOUT

Layout of *OUTDIR* (or *OUTDIR*/*test*/ with `all`):

```
index.html              strip (title, summary | flame graph | heat map |
                        native timing) over the summary (raw data, top-N
                        functions with callers, valgrind log); the strip
                        loads the pages below into a frame
flame-graph/index.html  speedscope, auto-loads the profile
heat-map/index.html     per-line heat map with cache-miss columns
perf-tool/index.html    native timing run output
```

With `all`, *OUTDIR*/index.html is the same kind of page over the tests
(`overview | all | base64dec | ...` alphabetical, `help | curl.se/perf` far
right). README.md (a help screen for the callgrind event columns and the
flame graph/heat map, copied from `dev/README.md`) sits next to that
top-level index.html; `help` opens it.

Raw callgrind data, the valgrind log and the speedscope JSON stay in
`dev/trace/`, with the quiet run's `profile.<ts>.log` next to them (same
`<ts>`).

See `dev/CLAUDE.md` for the full report layout, the shared theme, and the
heat map / flame graph internals -- this page covers only the command
line.

## ENVIRONMENT

`CALLGRIND_CPU`
: Core to pin to (default 3).

`CALLGRIND_LOOPS`
: Loop count for the callgrind run (default: 200 for urlparser, 200000
  for the others; callgrind is approximately 50x slower than native, so
  this is not the tool's own default).

`CALLGRIND_OPTS`
: Extra valgrind options, e.g. `--simulate-hwpref=yes --simulate-wb=yes
  --cacheuse=yes`.

`PROFILE_BUILD_DIR`
: Build tree (default `build-relwithdebinfo`).

## EXAMPLES

Every perf test, into the default `dev/report`:

    dev/perf2html.sh

One test, into a chosen directory:

    dev/perf2html.sh ~/artifacts urlparser

Rebuild curl with a define first:

    dev/perf2html.sh ~/artifacts urlparser -DUSE_AVX512

Every tool's own output, a banner per step, instead of the quiet status
lines:

    dev/perf2html.sh --verbose ~/artifacts urlparser

## SEE ALSO

`dev/profile_diff.sh`(1), `dev/CLAUDE.md`
