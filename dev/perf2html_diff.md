# PERF2HTML_DIFF.SH 1 "dev tooling" "curl perf"

## NAME

perf2html_diff.sh - compare two perf2html.sh reports and render the
differences as an HTML report

## SYNOPSIS

`dev/perf2html_diff.sh` [`--verbose`] [`--top` *N*] *BASELINE* *CURRENT*
[*OUTDIR*]

## DESCRIPTION

Takes two directories written by `dev/perf2html.sh`, subtracts the
callgrind data each one kept in its `raw/` subdirectories line by line, and
writes a report of the *changes* in the same shape and theme as a normal
one -- a summary page and a heat map per test, an overview across the
tests -- that opens straight from disk with nothing fetched at view time.

Every number in the output is a delta: *CURRENT* minus *BASELINE*.
`+16%` means the symbol took 16% more of the change than anything else
did, not that it ate 16% of the program; `-1,000` cache misses means a
thousand fewer than the baseline.

Tests are matched by name: each report's `raw/` directories are listed, the
names they sit under are intersected, and every test both reports have is
compared, `all` against `all` and the rest against the rest, using whatever
each side's own `raw/` holds. Overlap between `all` and the individual
tests is not considered. A test only one side has is reported on stderr and
skipped.

A diff report has no flame graph and no native timing. A delta has no call
graph for speedscope to draw, and two runs' wall clocks do not subtract
into one meaningful number.

## OPTIONS

`--verbose`
: Show everything the tools print (the differ, the page generators) under
  a `== N: ...` banner per step. Without it the run is one status line per
  test; everything the tools print goes to `dev/trace/diff.<ts>.log`
  instead and a failing command's output is shown with the error.

`--top` *N*
: Functions listed in each summary's "top N functions by change in self"
  table (default: 50).

`--verbose` and `--top` are recognized only before *BASELINE*, in either
order.

*BASELINE*
: The "before" report directory. Required.

*CURRENT*
: The "after" report directory. Required.

*OUTDIR*
: Where the diff report goes (`mkdir -p`). Default: `dev/report-diff`. A
  relative path is taken relative to the caller's cwd.

## INPUTS

A report directory is accepted only if its top-level `MANIFEST.txt` holds
exactly the one line `curl/perf2html.sh v1`. A missing, longer or different
manifest is rejected as an unrecognized input; reports made before
perf2html.sh wrote one must be regenerated.

This tool writes `curl/perf2html_diff.sh v1` into its own *OUTDIR*
instead, and refuses a directory carrying that line: a diff cannot be used
to make a diff.

## OUTPUT LAYOUT

Layout of *OUTDIR* (or *OUTDIR*/*test*/ when both reports hold several
tests):

```
index.html                     strip (title, summary | heat map) over the
                               summary (what was compared, raw data, top-N
                               functions by change in self)
heat-map/index.html            per-line change heat map
raw/callgrind.diff.<test>.<ts> the delta the pages were built from, a
                               plain callgrind-format file
```

With several tests, *OUTDIR*/index.html is an overview over them, one row
per test (change in the event, that change as a percentage of the
baseline's total, how many functions changed at all). README.md is copied
next to it from `dev/README.md`; `help` opens it.

The delta also stays in `dev/trace/` as `callgrind.diff.<test>.<ts>`, with
the quiet run's `diff.<ts>.log` next to it.

## RANKING

The summary's top-N table and both heat-map home tables ("Most changed
lines by ...", "Most changed functions by ...") rank by *absolute* change,
so the biggest wins and the biggest regressions sort to the top together.
Shares are taken against the sum of every change's magnitude, not against
the near-zero sum of the signed deltas. Heat intensity follows the same
absolute value, so a large improvement is as hot as a large regression;
the sign is in the number.

## HOW IT DIFFS

Both sides are parsed with the report's own callgrind parser
(`dev/scripts/callgrind.py`), each side's files merged into one profile,
and the two subtracted per function, file and line. Doing it per line
alone would be wrong: under `-O2` the same source line is charged to every
function it was inlined into, and only the function context tells them
apart. The result is written as an ordinary callgrind-format file, which
the page generators read like any other profile.

What a delta cannot carry, accepted rather than worked around:

- **No call counts and no callers.** Two call graphs do not subtract into
  one, so none is written. The summary's top-N table has no
  `calls`/`callers` columns, the heat map has no `calls`/`incl` columns and
  its popups have no caller list.
- A function's "defined at" line is its first executed line, the same one
  callgrind records as a call target; a function no one calls in either run
  is placed the same way.
- Functions are keyed by name, so a symbol present in two objects is one
  function on both sides; a line only one side executed is a change of its
  whole cost.

## ENVIRONMENT

`DIFF_EVENT`
: Event the overview's columns and the summary tables are ranked by
  (default `Ir`). Any event the profiles recorded, or a derived one
  (`D1m`, `DLm`, `L1m`, `LLm`, `Bm`, `CEst`).

## EXAMPLES

Two reports, into the default `dev/report-diff`:

    dev/perf2html.sh ~/before urlparser
    # ... make a change, rebuild ...
    dev/perf2html.sh ~/after urlparser
    dev/perf2html_diff.sh ~/before ~/after

Into a chosen directory, ranked by estimated cycles:

    DIFF_EVENT=CEst dev/perf2html_diff.sh ~/before ~/after ~/delta

Every tool's own output, a banner per step:

    dev/perf2html_diff.sh --verbose ~/before ~/after

## SEE ALSO

`dev/perf2html.md`(1), `dev/lint.sh`(1), `CLAUDE.md`
