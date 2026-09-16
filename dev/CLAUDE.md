# curl urlparser perf work

## User settings (Do not modify)

Heatmap Colors = `["#3E4A89", "#31688E", "#26828E", "#1F9E89", "#35B779", "#6DCD59", "#B4DE2C", "#FDE725", "#FFC83B", "#FFA22C", "#FF7F21", "#F06142"]`

Theme Colors.
[
  "#00A8FF",
  "#0097E6",
  "#E84118",
  "#C23616",
  "#9C88FF",
  "#8C7AE6",
  "#F5F6FA",
  "#DCDDE1",
  "#FBC531",
  "#E1B12C",
  "#7F8FA6",
  "#718093",
  "#4CD137",
  "#44BD32",
  "#273C75",
  "#192A56",
  "#487EB0",
  "#40739E",
  "#353B48",
  "#2F3640"
]

## Working rules

1. Whenever there is more than one question, concern or option, present
   them as a terse numbered list, and proceed in that order.
2. Keep this file current. Any change to the tooling, the report layout,
   the theme or the findings updates CLAUDE.md in the same change.
3. No source line numbers in this file. They break silently with the next
   edit and churn every commit. Refer to a function, an identifier or a
   grep-able snippet instead.
4. Everything under `dev/` is throwaway profiling tooling, not upstream
   material: one shared parser, one shared theme, no dead code, no
   duplicate systems. Anything a script writes must open from `file://`
   with nothing fetched at view time.

## Goal

Optimize `tests/perf/urlparser.c` (and, as needed, the URL API code it
exercises in `lib/urlapi.c` / `lib/uint-table.c` / `lib/idn.c` etc.) to improve
the "urlparser" perf chart tracked at:

https://curl.se/perf/index.html#urlparser

Measure with the built perf harness:

```
./build/tests/perf/perf urlparser [loops]
```

Default `loops` is 10000 if omitted. Use a smaller loop count (e.g. 1000) for
quick iteration, and a larger one for stable final numbers.

## Build

Default CMake + Ninja build, from the repo root:

```
cmake -S . -B build -G Ninja -DCURL_USE_LIBPSL=OFF
cmake --build build --parallel
cmake --build build --target perf
```

`CURL_USE_LIBPSL=OFF` is the **one intentional deviation** from a stock
default build: `libpsl-dev` headers are not installed on this machine and
`CURL_USE_LIBPSL` is `REQUIRED` when ON, which otherwise hard-fails
configure. Everything else uses CMake defaults (OpenSSL, zlib, zstd, threaded
resolver, IPv6, alt-svc, HSTS, etc. all auto-detected and on). If libpsl-dev
gets installed later, drop that flag to go fully stock.

The `perf` test binary is `EXCLUDE_FROM_ALL` in the perf CMakeLists, so it
must be built explicitly with `--target perf` — it is not part of a plain
`cmake --build build`.

## Debugging

Open this `dev/` folder (or the repo root, since `dev/.vscode` is symlinked
to the top-level `.vscode`) in VS Code and use the "perf urlparser" launch
config. It rebuilds the `perf` target first, then runs
`./build/tests/perf/perf urlparser` under gdb.

## Profiling

The plain `./build` recipe above never sets `CMAKE_BUILD_TYPE`, so it's
`-O0`, no debug info, no `-DNDEBUG` — fine for correctness/debugging, but
**do not profile it**: under `-O0` functions like `badoctets`/`parseurl`/etc.
show as separate entries, while under `-O2` they get inlined away into
`parseurl_and_replace`, which alone becomes 37.6% of the program. Profiling
`-O0` attributes cost to the wrong function. Instead keep a second tree for
profiling:

```
cmake -S . -B build-relwithdebinfo -G Ninja -DCURL_USE_LIBPSL=OFF -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build-relwithdebinfo --parallel
cmake --build build-relwithdebinfo --target perf
```

Build type changes which *function* looks hot, not just speed: instruction
counts for the same workload differ ~43% between builds (3.48B vs 1.98B Ir
at `loops=200`, `-O0` vs `-O2`) — the line-level finding is the same either
way, but function-level attribution is not, so `-O0` profiles are actively
misleading, not just imprecise.

Also pin to a core for any timing run. Timer resolution is not the noise
source (`clock_getres` confirms 1ns kernel resolution, stored truncated to
1us — irrelevant at ~40M-call aggregate windows); the real cause is CPU
scheduling under WSL2, which can't be inspected directly since `cpufreq`
sysfs isn't exposed inside WSL2, only worked around. On this machine (AMD
Ryzen AI 9 HX 370, WSL2) unpinned `-O2` runs vary **~106%** run to run
(183-377 ns/URL); `taskset -c 3` cuts that to <1-3%:

```
taskset -c 3 ./build-relwithdebinfo/tests/perf/perf urlparser 10000
```

`dev/profile.sh [--verbose] [OUTDIR] [PERFTEST|all] [CFLAGS...]` automates
all of it:

```sh
dev/profile.sh                                   # -> dev/report, every perf test
dev/profile.sh ~/artifacts urlparser             # one test
dev/profile.sh ~/artifacts urlparser -DUSE_AVX512   # rebuild curl with that define first
dev/profile.sh --verbose ~/artifacts urlparser   # every tool's output, a banner per step
```

- `OUTDIR` defaults to `dev/report` (gitignored); a relative path is
  relative to the caller's cwd. `PERFTEST` is the perf binary's first
  argument (a test name from `tests/perf/Makefile.inc`) or `all`, the
  default, which writes one report per test into `OUTDIR/<test>/`, a
  combined report over every test into `OUTDIR/all/` and a top-level
  `OUTDIR/index.html`. The perf binary runs one test per process (there is
  no all-tests mode in `tests/perf/first.c`), so `all/` is the per-test
  callgrind files merged into one profile by `callgrind.py`'s `load()`
  (each test weighted by its own loop count, 200 vs 200000) and the
  per-test native `Time:` values summed. Everything after that goes into
  `CMAKE_C_FLAGS` for a fresh build; the flags are passed on *every* run
  (empty when omitted) so a previous run's flags never linger in the cache.
- Build: `build-relwithdebinfo`, `-O2 -g`, with `ccache` as
  `CMAKE_C_COMPILER_LAUNCHER` when it is on PATH, so a flag change is a
  ~1 min first rebuild and cached afterwards.
- Profile: `valgrind --tool=callgrind --cache-sim=yes --branch-sim=yes`
  (valgrind 3.26 spells it `--cache-sim`; `--simulate-cache` is the old
  name), pinned with `taskset -c $CALLGRIND_CPU` (default 3), loop count
  `CALLGRIND_LOOPS` (default 200 for urlparser, 200000 for the others —
  callgrind is ~50x slower than native, so the tool's own 10M defaults
  are not used). `CALLGRIND_OPTS` appends extra valgrind options
  (`--simulate-hwpref=yes --simulate-wb=yes --cacheuse=yes` are the
  useful ones). Events recorded: `Ir Dr Dw I1mr D1mr D1mw ILmr DLmr DLmw
  Bc Bcm Bi Bim`. Callgrind auto-detects the cache geometry from cpuid;
  on this machine that gives I1 32K/8-way and D1 48K/12-way (right for
  Zen 5) but LL "16777216 B, direct-mapped" with a "L3 cache found, using
  its data for the LL simulation" warning — the simulator fell back to
  direct-mapped, which overstates LL conflict misses. The geometry used
  is in the `desc:` lines at the top of the callgrind file; override with
  `CALLGRIND_OPTS="--LL=16777216,16,64"` when LL numbers matter.
- Timing: a second, native, pinned run of the same test (`perf <test>`,
  default loops) — the only valid speed number in the report. Callgrind's
  own wall-clock is never a perf number.
- Output: one status line per thing, built up as its steps finish -- the
  build (`build  build-relwithdebinfo -O2 -g, ccache 3s | log
  dev/trace/profile.<ts>.log`), each test (`urlparser  callgrind loops=200
  2m14s | native Time/URL: 137.66 ns, Errors: 1240000 | pages 4s`) and,
  with `all`, the merged report (`all  8 profiles merged | Time: ... usecs`,
  no per-page timing -- building the overview from already-rendered
  per-test pages is fast enough not to warrant one); the last line ends
  with `-> OUTDIR/index.html`. Ten lines
  for `all`, two for one test. Everything the tools print (cmake, ninja,
  the perf binary under callgrind and natively, the generators and their
  self-check ratios) goes to `dev/trace/profile.<ts>.log`, each command
  under a `$ ...` line, and a failing command's output (last 40 lines)
  is shown with the error. `--verbose`, recognised as the first argument
  only (it is shifted away), prints it all to the terminal instead under
  a `== N [test]: ...` banner per step and writes no log. In the script:
  `log_say` is verbose-only text; `test_run` routes a command's output by
  mode; each quiet-mode status fragment is its own inline
  `[ "$VERBOSE" = 1 ] || printf ...` at the call site rather than a shared
  `log_status` helper -- those fragments only cohere as one line in quiet
  mode (verbose mode already has `test_run`'s interleaved command spew to
  match against instead), so the two modes are not one behavior behind a
  common name, and a shared function for it was not a real abstraction.
  Everything else that used to be a one-line helper (capturing stdout to
  `RUN_LOG`, elapsed-time formatting, the perf-tool summary line,
  listing/validating perf tests) is inlined at each call site instead of
  factored out -- those were each a one-off wrapper around a single
  command with no shared behavior worth naming, and named separately from
  their call site they read as spooky action at a distance.

Functions across `dev/` follow an `object_method`-style naming scheme (a
C-identifier form of an object hierarchy, lowercase): `profile.sh`'s
`args_parse`, `toolchain_check`, `build_compile`, `report_render`,
`usage_show`, `script_main`, the `log_*`/`test_*` helpers, and `run_one`/
`run_all` (already fit unprefixed); `theme.py`'s `theme_css`/`theme_js`/
`theme_runtime`, `html_esc`, `table_render`, `page_document`, `num_human`/
`num_pct` (`heat_t`/`heat_style` already fit); `callgrind.py`'s `Profile`
class keeps its own methods as-is and its module-level functions are
`profile_parse`/`profile_self_check`/`profile_merge`/`profile_load`;
`build_report.py`'s `report_test`/`report_timing`/`report_overview`/
`report_main`, `strip_render`, `rawdata_list`, `path_display`,
`meta_parse_pairs`, `file_read_text`, `page_write` (`functions_table`/
`log_block` already fit); `callgrind_to_heatmap.py`'s `path_norm`,
`source_read`, `repo_tracked_files`, `vec_trim`, `model_build`,
`heatmap_render`, `heatmap_main`; `callgrind_to_speedscope.py`'s `Graph`
class keeps its own methods and its free functions are `path_display`,
`expr_resolve`, `graph_build_profile`, `document_build`,
`speedscope_main` (`expr_label` already fits); `build_flame_graph.py`'s
`index_patch`, `flamegraph_main`. Scope: top-level Python/shell function
defs only -- `theme.js`'s `Theme.*` already fit the style and embedded JS
inside the generators' HTML/BODY string templates is untouched (comments
in that JS that name a Python function were kept in sync where they refer
to one of the renamed names above).

Report layout (`OUTDIR/`, or `OUTDIR/<test>/` with `all`), all plain
`file://`-openable, nothing fetched at view time:

```text
index.html               a strip across the top -- the page title, then
                         [bracketed] links -- and the summary under it: meta
                         (just "generated"), the raw data (the callgrind
                         trace file(s), as a plain list of links relative to
                         this page, so OUTDIR can be copied elsewhere),
                         "top 20 functions by self" (% self, symbol, calls,
                         callers; one line per function) and the valgrind
                         log minus its 9-line banner. A strip link
                         loads that page into a frame under the strip, only
                         when picked; a symbol in the summary opens the heat
                         map at the function's first line. With `all`, the
                         top-level index.html is the same kind of page over
                         the tests ([overview] [all] [base64dec] ...,
                         alphabetical), one row of native-run numbers per
                         test ("all" has the summed Time only), and all/ is
                         a full report over every test's profile merged.
flame-graph/index.html   speedscope bundle; the profile picker switches
                         between Ir, D1mr+D1mw, DLmr+DLmw, I1mr, Bcm, Bim
heat-map/index.html      per-line source heat map (event selector, miss columns)
perf-tool/index.html     native timing run output
raw/                     the callgrind file(s) this report was built from,
                         copied in (see "raw data" above) with the repo
                         root prefix stripped from every ob=/fl=/fi= line
                         (callgrind records it as an absolute path; the
                         original in dev/trace/ is untouched)
```

Raw data stays in `dev/trace/` (gitignored): `callgrind.out.<test>.<loops>.<ts>`,
`valgrind.<test>.<loops>.<ts>.log`, a run without `--verbose` adds
`profile.<ts>.log` (everything the tools printed, same `<ts>` as its
traces) and the speedscope JSON (`all.<ts>.speedscope.json`
for the merged one; there is no merged callgrind file, the generators take
several and merge on read). The callgrind file(s) behind each report are
also copied into `OUTDIR/<test>/raw/` and the summary's "raw data" list
links to that local copy (path relative to the page), not to `dev/trace/`,
so `OUTDIR` is a self-contained directory that can be copied elsewhere on
its own and still open correctly from `file://` -- every file path embedded
in a generated page (heat map, flame graph, raw data) is relative, never
an absolute host path.

Scripts (`dev/scripts/`):

- `callgrind.py` — the one parser (per-line/per-function cost *vectors*
  over all events, call graph, `desc:` lines); `load(paths)` parses one
  or more files and `merge()`s them into one profile (every cost summed,
  call graphs united, summaries added; the events must match). Every
  other script imports it and takes one or more callgrind files on the
  command line. Derived events `D1m`, `DLm`, `L1m`, `LLm`,
  `Bm`, `CEst` (= Ir + 10·L1m + 100·LLm, KCachegrind's cycle estimate)
  are added when their inputs exist. Functions are keyed by name, so a
  symbol callgrind saw in two objects (PLT stub + libc, a function linked
  into both libcurl and the test binary) is one function here.
- `theme.py` + `theme.css` + `theme.js` — the shared look and behaviour
  (see "Look and feel"); every generator inlines them.
- `build_report.py` — `test` (a test's index.html), `timing`
  (perf-tool/index.html), `overview` (the `all` index).
- `callgrind_to_heatmap.py` — heat-map/index.html.
- `callgrind_to_speedscope.py` (`--event` repeatable; `A+B` sums columns;
  one speedscope profile per expression; `--repo-root` relativizes frame
  file paths, same as the heat map) and `build_flame_graph.py` (patches a
  copy of speedscope's `dist/release` to auto-load it) — flame-graph/.

Validated baseline (RelWithDebInfo, pinned, `loops=10000`, median of 7 runs):
**137.66 ns/URL**, **~7.26M URLs/sec**, `Errors: 1240000` constant across
every run/build.

Full hot-spot breakdown as of the last profile (`loops=200` → 807,800
`curl_url_set()` calls, 1,977,194,203 Ir total, callgrind, `-O2 -g` build):

```text
742,854,400 (37.57%)  parseurl_and_replace
152,353,600 ( 7.71%)  Curl_is_absolute_url
124,513,450 ( 6.30%)  __memchr_avx2
123,037,864 ( 6.22%)  free
110,494,000 ( 5.59%)  parse_authority
 76,728,000 ( 3.88%)  hostname_check
 73,738,107 ( 3.73%)  malloc
 71,317,600 ( 3.61%)  dyn_nappend
 60,431,677 ( 3.06%)  __strlen_avx2
 50,547,800 ( 2.56%)  curl_url_set
```

The single hottest *line* in the whole benchmark is the inlined
`badoctets()` control-character test in `lib/urlapi.c`
(`if(*p <= control || *p == 127)`) — **236,011,200 Ir, 11.94% of total
instructions** on its own (plus 95.4M for the loop's `while(n--)` and
47.2M for its `p++`, so the whole loop is ~19% of the program), a scalar
byte-by-byte scan called on path/query/fragment/user/password/options for
effectively every URL (grep `badoctets(` in `lib/urlapi.c` for the call
sites). Most corpus paths/queries are "clean" and pay the full length for a
boolean answer — a chunked/SIMD scan there is the obvious next thing to try
and has not yet been attempted (no `lib/urlapi.c` changes made in the
profiling session that produced these numbers).

`free`/`malloc` combined ~10%: every `curl_url_set(CURLUPART_URL,...)` call
tears down and rebuilds the whole internal representation
(`free_urlhandle()` in `lib/urlapi.c`), so allocator overhead is a real
fraction of cost independent of parsing logic.

### Callgrind/speedscope tooling notes

No existing Callgrind→speedscope converter was available (pip blocked by
PEP 668 externally-managed-environment; declined `--break-system-packages`),
so `dev/scripts/callgrind_to_speedscope.py` builds the flame graph from
`callgrind.py`'s call graph. Three things it has to get right, each caught
by a self-check ratio printed to stderr on every run (the parser's
`sum(self-cost lines) / summary`, which must be exactly 1.0000 or nothing
is written, and the walk's `emitted weight / raw self total` per profile,
which must be ~1.0):

1. Callgrind's `calls=` line inclusive cost is **not** additive on top of
   the callee's own `fn=` self-cost lines — it already covers them. Treating
   it as additive gave 10x over-counting (20.2B vs true 1.98B). Fix: use
   `calls=` edges only to build the caller→callee graph structure; walk from
   root frames and distribute each frame's self-cost proportionally across
   its incoming edges by inclusive-cost share (KCachegrind's "callee map"
   approach).
2. Function identity in Callgrind is scoped to its **compressed-ID
   namespace** (`fn=`/`cfn=` share one ID space per the spec), not to
   `(file, name)`: a function's cost-line block can reopen far later in the
   file as a bare `fn=(ID)` while an unrelated `fl=` is "currently active"
   from interleaved callee traversal. `callgrind.py` resolves IDs to names
   and keys by name, which is immune to that.
3. Keying by name merges a symbol that lives in two objects, and the call
   between the two halves then loops: `_start → (below main) →
   __libc_start_main → (below main) → main` is a cycle once both
   `(below main)` IDs are one frame, and proportional attribution hands
   half of everything to the back edge (ratio 0.5003). Fix: collapse every
   strongly connected component into one frame first (Tarjan; the frame is
   named `A + B`), as KCachegrind's cycle detection does; the walk then
   runs on a DAG and the ratio is exactly 1.0000. Direct recursion is
   dropped the same way (the function's self cost already covers every
   level). A depth limit remains only as the guarantee of termination.

Validated end state: both ratios 1.0000 exactly; converted JSON's
`parseurl_and_replace` self-weight (37.82%) matches `callgrind_annotate`'s
independent flat-profile number (37.57%) within rounding. With several
`--event` expressions the converter emits one profile per expression into
the same document (same frames), printing the walk ratio for each;
speedscope shows a profile picker in its toolbar when a file has more than
one.

`dev/scripts/build_flame_graph.py` — speedscope's app only defines
`window.speedscope.loadFileFromBase64` after seeing a truthy
`localProfilePath` in the URL hash (reverse-engineered from `bin/cli.mjs` +
the minified bundle; the CLI's own mechanism injects
`<script src="file:///<absolute-tmp-path>">`, which doesn't survive moving
the bundle). Instead: set the hash to a harmless placeholder to trip the
same gate, then a sibling `profile.js` (relative path, portable) polls for
`window.speedscope` and calls `loadFileFromBase64` directly with the
profile embedded as base64. Verified against real Chrome (see "Checking
the pages") loading correctly via a plain `file://` path, no server.
Speedscope keeps its own look; it is the one page the theme does not touch.

### Reproducing a profile

```sh
dev/profile.sh dev/report urlparser   # regenerate everything (native timing included)
xdg-open dev/report/index.html
taskset -c 3 ./build-relwithdebinfo/tests/perf/perf urlparser 10000   # manual timing
```

### Line-level view

The speedscope bundle and the top-20 table in the report index are
*function*-level, and under `-O2`
most of `urlapi.c` is inlined into `parseurl_and_replace` (only
`curl_url_set`, `parseurl_and_replace`, `parse_authority`, `hostname_check`,
`ipv6_parse`, `free_urlhandle` survive as symbols — check with `nm -C
build-relwithdebinfo/lib/libcurl.so.4`). Callgrind charges inlined code to
the enclosing symbol, so to see what is hot *inside* that 37.8% you need the
per-source-line view: the heat map (below), or as an independent
cross-check the same numbers from callgrind's own tool:

```sh
callgrind_annotate --show-percs=yes dev/trace/callgrind.out.urlparser.200.<ts> lib/urlapi.c
```

`=> file:func (Nx)` rows in that annotation are inclusive cost of calls made
from the line above, not source lines. The heat map's per-line numbers were
verified to match it line for line.

### Source heatmap (browser)

`dev/scripts/callgrind_to_heatmap.py` renders the whole per-line profile as
one self-contained explorer page (no server, no CDN, works from `file://`):
directory tree on the left (a draggable splitter sets its width), colored
and sorted by share of the selected event with files that have no samples
folded away; per-line colored source on the right; click a line number to
see every event for that line, what it calls (inclusive cost, links to the
callee) and, on a function's first line, who calls it. The header's *event*
selector re-colors and re-sorts everything by any raw event (Ir, Dr, Dw,
I1mr, D1mr, ...) or derived one (D1m, DLm, L1m, LLm, Bm, CEst);
independent of that, every source line shows `D1m`, `DLm` and `Bcm`
columns (share of that event's total, each heat-colored on its own scale)
so a line that is cheap in Ir but hurts in misses is visible without
switching. The home view carries the 60 hottest lines and the 60 hottest
functions; `[home]` in the header strip returns to it. Event, scale, tree
order, tree width and column widths are remembered in localStorage. `dev/profile.sh` writes it to
`OUTDIR/heat-map/index.html`. Standalone:

```sh
python3 dev/scripts/callgrind_to_heatmap.py \
  dev/trace/callgrind.out.urlparser.200.<ts> -o dev/report/heat-map/index.html
```

Only files that carry cost get their source embedded (~0.9 MB page);
`--all-sources` embeds every tracked `.c/.h` under the `--tree` dirs
(default `lib include src tests/perf`) too. Parsing lives in
`dev/scripts/callgrind.py` and follows `callgrind_annotate`'s attribution
rules exactly (`fi=`/`fe=` switch the file for inlined lines, the cost line
after `calls=` is inclusive and is charged to the call site separately,
`calls=` targets decode relative to the last cost line) and prints the
same self-check ratio as the speedscope converter, which must be 1.0000.
There was no off-the-shelf tool for this:
KCachegrind has per-line heat but is a desktop app with no directory view,
pprof/Firefox Profiler have source views but no explorer and do not read
callgrind, and coverage-style HTML (lcov, gcovr) has the explorer shape but
only binary hit/miss coloring.

The 20 hottest lines are also marked in-source in `lib/urlapi.c` with
`/* perf #N: X.XX% */` comments on the line above each (rank, share of
total Ir). Those comments are dev annotations, not upstream material: drop
them before submitting anything. Line numbers in profiles taken before the
comments were added (`callgrind.out.urlparser.200.1789436338` and earlier)
are offset from the current source; re-run `dev/profile.sh` to get a
profile whose line numbers match.

### Look and feel

`dev/scripts/theme.py` holds the two palettes from "User settings" above
(keep them identical) and the semantic roles built on them; `theme.css`
and `theme.js` are the shared stylesheet and script. Every generator
inlines them (`theme.css()` / `theme.js()`), because the pages are opened
from `file://` and may not fetch anything. Rules the pages follow:

- One dark theme. The dark member of each theme pair is the default
  (`--bg` `#2F3640`, toolbar and panels `#192A56`, divider bars `#40739E`);
  the light member shades every other table column (`#353B48`) and is used
  for text, links and the title where the dark member would not read on
  the dark background (`#F5F6FA`, `#00A8FF`, `#FBC531`).
- Monaco for everything (`--font`, with monospace fallbacks). Because every
  glyph is one `ch` wide, table column widths are set in characters from
  the longest cell (or a fixed 20 for function names, or a clip) and are
  exact; `theme.PAD` adds 1ch padding each side plus 1ch of slack.
- Heat colors are the 12-stop ramp, blended over `--bg` with an alpha that
  grows with the share (log scale from 0.001% to the hottest line), and
  the text on a colored cell is picked by the result's luminance
  (`theme.heat_style()`, the same math in the heat map's `heatStyle()`).
  Speedscope is the exception and keeps its own colors.
- Every table is `theme.table()` (or the heat map's `table()`): no borders
  except a full-height bar at each column boundary, which the mouse can
  drag anywhere along its length to resize the column on its left; widths
  are remembered in localStorage per table and column label, under
  `cols.*` keys, and so is the heat map's tree width. Nothing on a bar
  resets it: the frame's `[reset columns]` link is the one way back,
  `Theme.reset()` drops every `cols.*` key and re-applies the defaults on
  the page, and the frame posts `theme:reset` into its iframe so the
  loaded page does the same (it is another `file://` origin, so the frame
  cannot reach into it directly). A legend banner above the table spells
  out every abbreviated column; the banner and the header row stay put
  while the page scrolls past the table (`theme.js` stacks them, since
  two sticky elements at `top: 0` overlap). A table box never scrolls on
  its own: it is as long as its rows and as wide as its columns, or with
  `fill` as wide as the page with the last column cut off at the edge
  (the summary's callers column; hover for the whole text); the page is
  what scrolls. `lines` underlines every row with the divider color (the
  summary's functions table). The divider is the cells' 1px right border
  in `--bar`; while the mouse is on it or dragging it is drawn 2px wide
  in the same color, and nothing else changes (the heat map's splitter
  does the same).
- Numbers are written for reading: `theme.human()` and the heat map's
  `fmtH()` give `2.1K`, `21K`, `210K`, `2.1M`, `2.0G` -- at least two
  meaningful digits, never `200,000×` -- with the exact value as the
  cell's tooltip; shares go through `theme.pct()` / `fmtP()`: `63.2%`,
  `5.12%`, `<0.01%`.
- The index page is a frame: a strip (`.strip`) with the title, then
  `[summary] [flame graph] [heat map] [native timing] [reset columns]`,
  and the summary under it, left-aligned and full width; sub-pages are
  loaded into an iframe only when picked. The title is the picked view --
  `urlparser`, `urlparser / heat map` -- in the accent color, and it is
  the only title anywhere: the pages have no heading of their own, and a
  frame page loaded inside another frame hides its title and posts it up
  (a `{theme: "title"}` message; the parent asks with `theme:title?`
  when it re-shows a frame it already loaded), so the top-level strip
  reads `urlparser / heat map` while the nested strip shows only its
  links. `[curl.se/perf]` is on the top-level (overview) strip only,
  hugging the right. The heat map's header is the same kind of strip
  with `[home]` in place of a title.

### Checking the pages

No browser runs inside WSL2, but the Windows Chrome does, through interop,
and it reads `\\wsl.localhost\<distro>\...` paths (`$WSL_DISTRO_NAME`):

```sh
"/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --disable-gpu \
  --window-size=1366,768 --screenshot="\\\\wsl.localhost\\$WSL_DISTRO_NAME\\tmp\\x.png" \
  "file://wsl.localhost/$WSL_DISTRO_NAME/home/t/curl/dev/report/index.html#heat-map"
```

`--dump-dom` instead of `--screenshot` prints the DOM after scripts ran,
so a probe `<script>` appended to a copy of a page (run it on `load`, after
`theme.js` has initialised) can report real layout numbers: divider bar
positions against column edges, sticky offsets after scrolling, cells
whose text is cut. Node + jsdom (`npm install jsdom` into a scratch dir;
no system packages) runs the pages' scripts for interaction tests (click
through the toolbar, open a line's detail, drag a bar) and catches runtime
errors, but its layout is all zeros and its `localStorage` throws on
`file://` origins — give it an `http://localhost/` URL, and use Chrome for
anything geometric. Check at 1366×768: the target is a medium-sized
laptop, and the pages must not assume more.

## Workflow

1. Baseline: run `./build/tests/perf/perf urlparser` a few times, note
   URLs/sec and ns/URL (some run-to-run noise is normal — prefer median of
   3-5 runs). For real timing numbers use the pinned RelWithDebInfo build
   above, not the plain `-O0` `./build` tree.
2. Profile if needed (`perf record`/`perf report`, `dev/profile.sh`,
   gdb, or just read the hot path) to find where time goes in
   `curl_url_set()` for `CURLUPART_URL`. Always profile the RelWithDebInfo
   tree — see "Profiling" above for why.
3. Make a focused change.
4. Rebuild (`cmake --build build --target perf`, and the main lib if you
   touched `lib/`) and re-run the benchmark.
5. Compare against baseline. Keep changes that measurably help; discard ones
   that don't or that regress correctness (`ecount` in the test output, and
   the normal `tests/` suite, must stay consistent).
6. Record what was tried and the before/after numbers as you go.

## Notes

- The test data (`urls[]` in `tests/perf/urlparser.c`) is a fixed corpus of
  ~577 real-world-ish URLs from a public dataset; it is looped and cross
  multiplied by 7 different `CURLU_*` option combinations per URL. Don't
  change the corpus or option list — that would invalidate comparisons
  against the public chart.
- `Errors:` in the output is the count of URLs that failed to parse under a
  given option combination. This is expected to be nonzero (some URLs are
  intentionally malformed test cases) — track it stays *constant* across
  your changes, since a change that "speeds up" parsing by silently
  rejecting more URLs is not a valid optimization.
- Keep correctness first: run the full test suite (`tests/runtests.pl` or
  `ctest` from `build/`, if built with `-DBUILD_TESTING=ON`) before
  considering a change final, since this perf test alone doesn't validate
  parsing correctness.
