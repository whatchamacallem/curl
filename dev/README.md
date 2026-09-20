# perf2html README



The HTML will open straight from disk, with no server. If you start by opening
the top level `index.html` in the report then bookmarks should work.

## The Scripts

```sh
dev/perf2html.sh [--verbose] [--report=DIR] [cmake-flags...]
dev/perf2html_diff.sh [--verbose] [baseline-dir] [modified-dir] [report-dir]
dev/perf2html_batch.sh [--verbose] [cmake-flags...]
```

`perf2html.sh` builds curl twice (`-O2 -g`+ccache by default, the second tree
adds `-finstrument-functions` and exists only for the flame graph), runs every
perf test under each, and writes one HTML report:

```text
DIR/index.html            Open this.
DIR/README.md             You are reading this.
DIR/MANIFEST.txt          Describes contents.
```

DIR defaults to `perf2html_baseline_report`, or `perf2html_modified_report`.

`perf2html_diff.sh` subtracts the callgrind data of two `perf2html.sh` reports
(modified minus baseline, per function and source line) and creates a diff
report. The positional args default to `perf2html_baseline_report`,
`perf2html_modified_report`, and `perf2html_diff_report`.

`perf2html_batch.sh` generates the baseline, modified and diff reports in one
run using the default report directory names.

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
number in it is a difference: the modified run minus the baseline. `4.3K`
means four thousand more than the baseline, `-1,000` a thousand fewer. A share
is relative to that function or line's previous cost, and leads with `▲` when
it grew or `▼` when it shrank. A drop keeps its minus sign as well, so going
from 1 call to 0 calls reads `▼-100%`, 100 to 90 reads `▼-10%`, 90 to 100
reads `▲11.1%`, and no change at all is blank. Something the baseline never
had is `▲100%`, all of it new. A change too small to print at two decimals
reads `▲≈0.00%` or `▼≈0.00%`, which says the direction and that the size is
marginal.

A drop bottoms out at `▼-100%`: once something costs nothing there is nothing
left to remove. A rise has no such limit, so past 100% it is written as a
multiple instead, and a line that cost 10 and now costs 130 reads `▲1.30x`.
Anything past `99.99x` just reads `▲>1000x` -- the amount next to it is the
number that still means something. Cheap lines make enormous shares: half the
lines in a run cost under 20 instructions, so one that cost 1 and moved
200,000 is millions of percent, true but useless. For the same reason the
colours stop at 100%: any change at least as large as what the thing cost
before is painted at full brightness, and a 90% change still looks different
from a 10,000% one.

Tables are ranked by how large the change is, ignoring its direction, so the
biggest improvements and the biggest regressions sit together at the top. The
heat colours follow the same rule -- a large improvement is as bright as a
large regression, and only the arrow and the colour tell them apart.

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
