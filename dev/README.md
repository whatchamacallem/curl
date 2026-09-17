# README

The HTML will open straight from disk, with no server.

## Callgrind Events

These are the raw counters callgrind records and the derived ones this report
adds. They show up as column headers and event picker choices in the summary and
the heat map.

| Event | Meaning                                  |
|-------|------------------------------------------|
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

Derived from the above: `D1m` is `D1mr + D1mw`, `DLm` is `DLmr + DLmw`,
`L1m` is every L1 miss, `LLm` is every last level miss, `Bm` is every
mispredict, and `CEst` is a rough cycle estimate.

See the [callgrind](https://valgrind.org/docs/manual/cl-manual.html) docs.
GPL Version 3, 29 June 2007.

## Colors

One ramp, the same rule everywhere: a cell is colored by its own metric's
share of that metric's total, on a log scale from 0.001% up to the largest
share seen for that metric. A cost cell (self, incl, calls) is a share of the
selected event; a miss cell (D1m, DLm, Bcm) a share of that event's own
total; a call count a share of every call the profile recorded, scaled to the
most-called function. In the source listing the event, line and source cells
all carry the line's own (self) cost; "calls" carries the cost of the calls
made from that line.

## Links

The address bar always spells out what is on screen, so it can be bookmarked
or copied at any point and reopened later. After the view name comes that
view's own state: `#heat-map/f=lib/urlapi.c&l=1343&e=Ir` is the heat map at
that line of that file with that event, `fn=parseurl_and_replace` a function
(its file, opened on the function's first line), `f=lib/urlapi.c` a file, and
nothing after the view name is the view's start page. An `all` report puts
the test first: `#urlparser/heat-map/...`. Closing a line's detail box moves
the selection to its file; back and forward walk through every step.

## Flame Graph Bindings (speedscope)

Open the flame graph and remain with "Time Order" in the view menu. The
other views require familiarity with the tool.

Scroll to pan and pinch or Cmd/Ctrl+scroll to zoom, on both the minimap
and the main view. Click a frame for its stats.

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
- Cmd+F/Ctrl+F: to open search. While open, Enter and Shift+Enter cycle through results

[speedscope](https://github.com/jlfwong/speedscope) is Copyright (c) 2018 Jamie Wong
