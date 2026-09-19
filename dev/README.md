# README

The HTML will open straight from disk, with no server. If you start by opening
the top level `index.html` then bookmarks should work.

## The Scripts

```sh
dev/perf2html.sh [--verbose] [--report=DIR] [cmake_flags...]
dev/perf2html_diff.sh [--verbose] [baseline-dir] [modified-dir] [report-dir]
dev/perf2html_batch.sh [--verbose] [--keep] [cmake_flags...]
```

`perf2html.sh` builds curl twice (`-O2 -g`+ccache by default, the second tree
adds `-finstrument-functions` and exists only for the flame graph), runs every
perf test under each, and writes one HTML report:

```text
DIR/index.html            Open this.
DIR/README.md             You are reading this.
DIR/MANIFEST.txt          Metadata.
```

DIR defaults to `perf2html_baseline_report`, or `perf2html_modified_report`.

`perf2html_diff.sh` subtracts the callgrind data of two `perf2html.sh` reports
(modified minus baseline, per function and source line) and writes the change
as a with the same files as `perf2html.sh`.

Positional args default to `perf2html_baseline_report`,
`perf2html_modified_report`, and `perf2html_diff_report`.

`perf2html_batch.sh` runs every too and check the dev/ dir has, in one go:

```text
1 lint      pyright over dev/scripts (dev/pyrightconfig.json, must stay at
             0 errors) and node --check over theme.js plus the JS embedded
             in the generators (scripts/check_js.py)
2 baseline  perf2html.sh            -> perf2html_baseline_report
3 modified  perf2html.sh <flags>    -> perf2html_modified_report
4 diff      perf2html_diff.sh       -> perf2html_diff_report
5 validate  validate_report.py on all three reports
```

## Callgrind Events

These are the raw counters callgrind records and the derived ones this report
adds. They show up as column headers and event picker choices in the summary
and the heat map.

| Event | Meaning                                  |
| ----- | ---------------------------------------- |
| Ir    | Instructions executed (I cache reads)    |
| I1mr  | L1 instruction cache read misses         |
| ILmr  | Last level cache instruction read misses |
| Dr    | Memory reads (D cache reads)             |
| D1mr  | L1 data cache read misses                |
| DLmr  | Last level cache data read misses        |
| Dw    | Memory writes (D cache writes)           |
| D1mw  | L1 data cache write misses               |
| DLmw  | Last level cache data write misses       |
| Bc    | Conditional branches executed            |
| Bcm   | Conditional branches mispredicted        |
| Bi    | Indirect branches executed               |
| Bim   | Indirect branches mispredicted           |

Derived from the above: `D1m` is `D1mr + D1mw`, `DLm` is `DLmr + DLmw`, `L1m`
is every L1 miss, `LLm` is every last level miss, `Bm` is every mispredict, and
`CEst` is a rough cycle estimate.

See the [callgrind](https://valgrind.org/docs/manual/cl-manual.html) docs. GPL
Version 3, 29 June 2007.

## Diff Reports

A report built by `perf2html_diff.sh` compares two earlier reports, and every
number in it is a difference: the modified run minus the baseline. `+4.3K`
means four thousand more than the baseline, `-1,000` a thousand fewer. A share
like `+16%` is that function's part of everything that changed, not its part of
the program.

Tables are ranked by how large the change is, ignoring its direction, so the
biggest improvements and the biggest regressions sit together at the top. The
heat colours follow the same rule -- a large improvement is as bright as a
large regression, and only the sign tells them apart.

The differences are taken per source line, so the heat map's listing shows
exactly where a function got cheaper or dearer. The summary table's calls/
callers columns are synthesized separately (per-caller call count and cost
deltas), signed the same way as everything else. What a diff still does not
have is a flame graph or a perf log, because neither subtracts into a
meaningful single number.

## Flame Graph (speedscope)

The flame graph is a recording, not a model: every box is one call that
happened, as wide as it took. The test runs in a build with
`-finstrument-functions`, where a hook (`dev/cyg_callback.c`) reads the CPU's
time stamp counter at every function entry and exit. "Time Order" is the order
the calls were made in.

It shows up to 10 calls in a row, 10 KB at most, taken from the middle of the
run, when caches are warm. Times are nanoseconds since the start of the run.
Both hooks cost time too and that time is in the boxes, so a function of a few
instructions looks slower than it is, and the traced run is slower than the
perf log's native one. Use the perf log for speed and the flame graph for
shape: what calls what, in which order, and which call was the slow one. The
summary's "trace log" has the commands and the traced run's own output, and
"raw data" links the same profile as a speedscope JSON file.

The merged "all" report and a diff have no flame graph: recordings neither add
up nor subtract.

Scroll to pan and pinch or Cmd/Ctrl+scroll to zoom, on both the minimap and the
main view. Click a frame for its stats.

The keybindings are:

- +: zoom in
- -: zoom out
- 0: zoom out to see the entire profile
- w/a/s/d or arrow keys: pan around the profile
- 1: Switch to the "Time Order" view
- 2: Switch to the "Left Heavy" view
- 3: Switch to the "Sandwich" view
- r: Collapse recursion in the flamegraphs
- Cmd+S/Ctrl+S to save the current profile
- Cmd+O/Ctrl+O to open a new profile
- n: Go to next profile/thread if one is available
- p: Go to previous profile/thread if one is available
- t: Open the profile/thread selector if available
- Cmd+F/Ctrl+F: to open search. While open, Enter and Shift+Enter cycle through
  results

[speedscope](https://github.com/jlfwong/speedscope) is Copyright (c) 2018 Jamie
Wong
