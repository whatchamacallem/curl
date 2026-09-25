# perf2html README

The HTML will open straight from disk, with no server. If you start by opening
the top level `index.html` in the report then bookmarks should work.

## The Scripts

These are the scripts for using `perf2html`. While the scripts directory does
contain a few more interesting files, none of them should be needed to use the
generators.

- `perf2html.sh` : Capture timing data and generate a report.
- `perf2html_diff.sh` : Generate a report about the difference between two
  `perf2html.sh` reports.
- `perf2html_batch.sh` : Generate 3 reports, a baseline version, a modified
  version, and a diff.

```txt
perf2html.sh [debug-flags] [--report=DIR] [cmake-flags...]
    Builds RelWithDebInfo, profiles every TESTS_C test under callgrind plus a
    native perf stat timing run and a traced run for the flame graph,
    generates one report.
    --report=DIR      Defaults to perf2html_baseline_report, or
                      perf2html_modified_report when a cmake flag is given.
                      Pass it yourself after a source-only change.
    cmake-flags       Everything else, e.g. -D CMAKE_C_FLAGS=-Os.

perf2html_diff.sh [debug-flags] [baseline] [modified] [diff]
    Measures nothing: Compares the counters in two profiling reports and
    generates a diff. Directories default to
    ./perf2html_{baseline,modified,diff}_report. Both baseline and modified
    must be a perf2html.sh report. A diff can't be diffed.

perf2html_batch.sh [debug-flags] [--target-dir=DIR] [cmake-flags...]
    Profiles baseline, modified and then does a diff of them.
    --target-dir=DIR  Holds the three default-named reports (default CWD). The
                      batch cannot rename them.
    cmake-flags       Every argument not one of its own options, applied to the
                      modified build (default -D CMAKE_C_FLAGS=-Os).
```

These are developer flags for the iterative development of `perf2html` itself.

```txt
    --artifacts=TMP   The profiler artifacts directory. Defaults to
                      perf2html_temporary_artifacts/ beside the report
                      directory (inside the target dir for a batch).
    --keep-artifacts  Do not delete the profiler artifacts directory after use.
                      Required for a later --regenerate.
    --regenerate      Rebuilds all pages from the last run's profiler
                      artifacts, re-measuring nothing. Implies
                      --keep-artifacts.
    --verbose         Enables diagnostic information. Repeating it (--verbose
                      --verbose) increments the verbosity level.
```

## Callgrind Counters

These are the raw counters `callgrind` records and the derived ones this report
adds up from them. They show up as column headers and counter picker choices in
the heat map, under these same names.

| Counter | Meaning                             | Derived from            |
| ------- | ----------------------------------- | ----------------------- |
| `Ir`    | instructions executed               |                         |
| `Dr`    | data reads                          |                         |
| `Dw`    | data writes                         |                         |
| `I1mr`  | L1 instruction cache misses         |                         |
| `D1mr`  | L1 data cache read misses           |                         |
| `D1mw`  | L1 data cache write misses          |                         |
| `ILmr`  | last level instruction cache misses |                         |
| `DLmr`  | last level data cache read misses   |                         |
| `DLmw`  | last level data cache write misses  |                         |
| `Bc`    | conditional branches executed       |                         |
| `Bcm`   | conditional branches mispredicted   |                         |
| `Bi`    | indirect branches executed          |                         |
| `Bim`   | indirect branches mispredicted      |                         |
| `D1m`   | L1 data cache misses                | `D1mr + D1mw`           |
| `DLm`   | last level data cache misses        | `DLmr + DLmw`           |
| `L1m`   | L1 cache misses, all                | `I1mr + D1mr + D1mw`    |
| `LLm`   | last level cache misses, all        | `ILmr + DLmr + DLmw`    |
| `Bm`    | branches mispredicted, all          | `Bcm + Bim`             |
| `CEst`  | cycle estimate                      | `Ir + 10 L1m + 100 LLm` |

`CEst` weights a miss by roughly what it costs and is used by default.

See the [callgrind](https://valgrind.org/docs/manual/cl-manual.html) docs. GPL
Version 3, 29 June 2007.

## Reading a Diff Report

### Regular report

A regular report shows you a percentage of a total as you might expect. In most
places it is a percentage of a global total cycle count, however in the source
view it may also be a percentage of a file or function if selected.

| example     |      % |
| ----------- | -----: |
| 1 / 50000   | <0.01% |
| 1 / 5000    |  0.02% |
| 500 / 5000  |  10.0% |
| 5000 / 5000 | 100.0% |

### Diff report

A diff report uses percentages the same way a stock market ticker does. Every
number in it is the modified profile minus the baseline one, per function, file
and line, and every share divides that difference by the same thing's own
baseline count. So a share says how much this line moved against what it used
to cost, not what part of the report it is. Half as long is `▼-50.0%`, twice as
long is `▲100.0%`, and smaller is better.

| example            |        % |
| ------------------ | -------: |
| 1000 -> 1000       |          |
| 1000 -> 1000000    | ▲999.00x |
| 1000 -> 1001000    |  ▲>1000x |
| 1000 -> 101000     | ▲100.00x |
| 1000 -> 2000       |  ▲100.0% |
| 1000 -> 2010       |   ▲1.01x |
| 1000 -> 900        |  ▼-10.0% |
| 5000 -> 0          | ▼-100.0% |
| 5000000 -> 4999999 |  ▼≈0.00% |
| 5000000 -> 5000001 |  ▲≈0.00% |
| 90 -> 100          |   ▲11.1% |

## Flame Graph (speedscope)

The flame graph is a recording, not a model: every box is one call that
happened, as wide as it took. The test runs in a build with
`-finstrument-functions`, where a hook (`dev/src/cyg_callback.c`) reads the
CPU's time stamp counter at every function entry and exit. "Time Order" is the
order the calls were made in.

It shows up to 200 top-level calls in a row, taken from the middle of the run,
when caches are warm. Times are nanoseconds since the start of the run. Both
hooks cost time too and that time is in the boxes, so a function of a few
instructions looks slower than it is, and the traced run is slower than the
perf log's native one. Use the perf log for speed and the flame graph for
shape: what calls what, in which order, and which call was the slow one. The
summary's "trace log" has the commands and the traced run's own output, and
"raw data" links the same profile as a speedscope JSON file.

The merged "all" report and a diff have no flame graph: a trace neither adds up
nor subtracts.

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
