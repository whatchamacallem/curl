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
5. When a single request bundles several distinct changes, track them as an
   explicit checklist for that turn (state it up front, work it in order)
   and close with a short report of what happened to each item -- done,
   changed from the ask, or found not to apply -- rather than a running
   narration of the work.

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

`dev/perf2html.sh [--verbose] [OUTDIR] [PERFTEST|all] [CFLAGS...]` automates
all of it; full option/output/environment reference lives in
`dev/perf2html.md` (a man-page-style doc, `dev/perf2html.sh --help` dumps
it), not repeated here:

```sh
dev/perf2html.sh                                   # -> dev/report, every perf test
dev/perf2html.sh ~/artifacts urlparser             # one test
dev/perf2html.sh ~/artifacts urlparser -DUSE_AVX512   # rebuild curl with that define first
dev/perf2html.sh --verbose ~/artifacts urlparser   # every tool's output, a banner per step
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
  dev/trace/profile.<ts>.log`), each test (`urlparser  callgrind loops=200000
  5s 133.94ns/loop`, or `urlparser  callgrind loops=200 2m14s 137.66ns/URL,
  Errors: 1240000` for urlparser specifically) and, with `all`, the merged
  report (`all  8 profiles merged | 63s wrote OUTDIR/index.html`); no
  per-test or per-page timing beyond the native run's own numbers --
  page rendering (flame graph, heat map, index) is fast enough not to
  warrant its own status fragment; a single-test run's last line ends
  with `-> OUTDIR/index.html`, "all"'s merged line already ends in
  `wrote OUTDIR/index.html` so nothing is appended after it. After that,
  `validate_report.py OUTDIR` runs as the final step and, in quiet mode,
  prints nothing on success --
  a broken report is a `test_run` failure like any other (nonzero exit,
  last 40 lines of its output shown) rather than a separate status line,
  since there is nothing to report when it passes. Ten lines
  for `all`, two for one test, before validation. Everything the tools print (cmake, ninja,
  the perf binary under callgrind and natively, the generators and their
  self-check ratios) goes to `dev/trace/profile.<ts>.log`, each command
  under a `$ ...` line, and a failing command's output (last 40 lines)
  is shown with the error. `--verbose` and `--top N` (top-N functions in
  each summary's table, default 50), recognised only before OUTDIR/PERFTEST
  and in either order, are shifted away by `args_parse` before the
  positional args; `--verbose` prints it all to the terminal instead under
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
C-identifier form of an object hierarchy, lowercase): `perf2html.sh`'s
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
`index_patch`, `flamegraph_main`; `validate_report.py`'s `validate_main`
(the `check_*`/`fail`/`repo_root_guess` helpers already fit unprefixed).
Scope: top-level Python/shell function
defs only -- `theme.js`'s `Theme.*` already fit the style and embedded JS
inside the generators' HTML/BODY string templates is untouched (comments
in that JS that name a Python function were kept in sync where they refer
to one of the renamed names above).

Report layout (`OUTDIR/`, or `OUTDIR/<test>/` with `all`), all plain
`file://`-openable, nothing fetched at view time:

```text
index.html               a strip across the top -- the page title as a
                         green badge cell, then its links as plain words
                         separated by extra space, "|"-delimited (see "Look
                         and feel") -- and
                         the summary under it: the valgrind log (minus its
                         9-line banner and each line's "==PID==" prefix, in
                         a panel-shaded box, no border) collapsed under a
                         chevron, then the
                         raw data (the callgrind trace file(s), as a plain
                         list of links relative to this page so OUTDIR can be
                         copied elsewhere) also collapsed under a chevron,
                         then "top N functions by self" (N is 50 by default,
                         `dev/perf2html.sh --top N`; #, % self, symbol, calls,
                         callers, in that column order; one line per
                         function, full page width (90% of the viewport at
                         first render, see "Look and feel"),
                         its callers column resizable at the right edge --
                         both the symbol and, now, each individual name in
                         the callers list link to the heat map at that
                         function's first line when the file is known, via
                         the same `entry_link()` helper in
                         `build_report.py`'s `functions_table`). The
                         valgrind log is omitted entirely on the
                         `all` page, since every test's log would otherwise
                         be concatenated there (build_report.py test's
                         `--no-log`, passed by perf2html.sh's report_render
                         only when rendering "all"). A strip link
                         loads that page into a frame under the strip, only
                         when picked; a symbol in the summary opens the heat
                         map at the function's first line. With `all`, the
                         top-level index.html is the same kind of page over
                         the tests (overview | all | base64dec | ...,
                         alphabetical), one row of native-run numbers per
                         test ("all" has the summed Time only), and all/ is
                         a full report over every test's profile merged.
flame-graph/index.html   speedscope bundle; the profile picker switches
                         between Ir, D1mr+D1mw, DLmr+DLmw, I1mr, Bcm, Bim
heat-map/index.html      per-line source heat map (event selector, miss columns)
perf-tool/index.html     native timing run output
README.md                a help screen, not a manual: the callgrind event
                         columns (Ir, Dr, Dw, D1mr, ...) and a couple of
                         sentences each on the flame graph and the heat map.
                         Copied from dev/README.md by perf2html.sh on every
                         run; opened by the top-level strip's "help" link,
                         plain (un-rendered, since there is no server)
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
- `callgrind_to_cgdiff.py BEFORE... -- AFTER... -o OUT.html` — a two-run
  regression diff, rendered as one `theme.table_render()` page (`cgdiff_render`),
  driven by `dev/profile_diff.sh` (see "Comparing two runs" below).
- `validate_report.py OUTDIR` — smoke test over a finished report
  directory: every expected page exists, isn't suspiciously small or a
  truncated/errored HTML document, the strip links and "top N functions"/
  "test suites" sections are present, each test's `raw/` holds at least
  one real callgrind file, `perf-tool/output.txt` has a timing line (plus
  `Errors:` for urlparser specifically -- the other perf tests don't print
  one), and no `raw/` file still contains the absolute repo root (the path
  the report-copy `sed` step is supposed to strip). Structural/size checks
  only, not a re-parse of the profile data -- it does not validate that
  the numbers are *correct*, only that the pipeline didn't silently drop
  a step. Handles both a single-test OUTDIR and an `all`/overview OUTDIR
  (detected from `index.html`'s content); `--test NAME` narrows an
  overview check to specific tests. `dev/perf2html.sh` runs it as the last
  step against the whole `OUTDIR` it just wrote, non-verbose failures
  going through the normal `test_run` error path (nonzero exit, last 40
  log lines shown).

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
dev/perf2html.sh dev/report urlparser   # regenerate everything (native timing included)
xdg-open dev/report/index.html
taskset -c 3 ./build-relwithdebinfo/tests/perf/perf urlparser 10000   # manual timing
```

### Comparing two runs

`dev/profile_diff.sh BEFORE_DIR AFTER_DIR [TEST] [OUTPUT.html]` diffs two
`dev/perf2html.sh` report directories using valgrind's own `cg_diff` (part of
the valgrind install; not this repo's tooling) and renders the result as one
page (`dev/scripts/callgrind_to_cgdiff.py`, same `theme.py` look as every
other report page). `TEST` picks which test to compare when a directory
covers more than one (an `all` overview OUTDIR); a single-test OUTDIR
(`raw/` directly under it) doesn't need it. `raw_dir_find` in the shell
script checks for a `*/raw` subdirectory shape before falling back to a bare
`raw/`, so an overview OUTDIR is never confused for a single-test one even
if the same path was previously used as one (a stale top-level `raw/` left
over from an earlier run at that path is not picked silently).

`cg_diff` only understands plain Cachegrind-format text -- no compressed
`fn=`/`fl=` IDs, no call graph, no `ob=`, and its own header parser is
strict about line order (`desc:`* lines, then exactly one `cmd:` line, then
exactly one `events:` line, nothing else interleaved) -- so raw callgrind
files can't be handed to it directly (attempted; `cg_diff` rejects them,
first on the header shape and then, past that, on the first `ob=`/compressed
`fn=(N)` line in the body: "malformed line"). `cgdump_write` in
`callgrind_to_cgdiff.py` reduces each side to that minimal shape from the
already-parsed `callgrind.py` `Profile` (`fn_self`/`fn_home`, one `fl=`/
`fn=`/cost-line triple per function, no call graph) before handing both to
the real `cg_diff` binary via `subprocess`, and parses its output back
(`cgdiff_run`). This also means the diff is at **function**, not line,
granularity: `cg_diff` always emits line `0` for every row ("we don't try to
give line-level CCs, due to the possibility of code changes causing line
numbers to move around" -- its own comment), so a line-level regression diff
isn't something `cg_diff` itself can produce; `cgdiff_render` sorts the
result by `|Δ event|` descending and heat-colors growth (`--bad`) separately
from shrinkage (`--good`).

```sh
dev/profile_diff.sh dev/report-before dev/report-after urlparser
# or, from two single-test OUTDIRs:
dev/profile_diff.sh ~/before ~/after
```

### Line-level view

The speedscope bundle and the top-N table in the report index are
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
folded away; per-line colored source on the right; click anywhere on a
line's row (not just the line number) to see every event for that line,
what it calls (inclusive cost, links to the callee) and, on a function's
first line, who calls it -- only rows that actually carry a recorded event
get the click affordance (`tr.clickable` in `callgrind_to_heatmap.py`'s
`emitRow`; hovering one of those rows turns just its line number blue via
`table.src tr.clickable:hover td.ln`, nothing else in the row changes, and
a row with no events neither highlights nor opens anything). The detail
popup has a `[X]` close link at its top right (`.dclose`, absolutely
positioned in `.dbox`) alongside the existing toggle-by-reclicking-the-row
behavior, and, styled as plain links at the bottom of the popup's own text
(`.dactions`, below the callees/callers tables), "copy" (`.dcopy`, copies
the popup's own text -- summary line plus any callees/callers headings --
to the clipboard via `navigator.clipboard.writeText`, skipping the `.dclose`
link and the `.dactions` row itself so neither "close" nor a stray button
label ends up in the copied text) and a second "close" (`.dclose2`, same
effect as `.dclose`, just reachable without moving back up to the top-right
corner).

The popup's own callees/caller tables (built by the page's local `table()`
helper, not `theme.table_render()`) are nested `table.cols` elements inside
the source table's `tr.detail > td`. A real bug lived here: the CSS rule
meant to relax that one wrapper `<td>` (`white-space: normal; overflow:
visible; padding: 0`, needed so the popup's own boxes aren't forced onto
one `nowrap` line) was written as the descendant selector `table.src
tr.detail td` with no `>`, so it also matched every `<td>` *inside* the
popup's own nested tables -- and at three classes+types it out-specifies
`table.cols th, table.cols td`'s two, so it silently won over the nested
table's own `overflow: hidden; text-overflow: ellipsis; white-space:
nowrap`. Symptom: a long "callee"/"caller" function name (e.g.
`base64_encode.part.0.constprop.0`) rendered at full width and visibly
overlapped the "defined at" column's link text instead of clipping with an
ellipsis -- confirmed with a byte-for-byte minimal repro (same markup, same
two rules, nothing else) before the fix, and gone after. Fixed by scoping
the selector to `table.src tr.detail > td` (direct child only); the same
tightening was applied to the neighboring `table.src td { padding-top: 0;
padding-bottom: 0 }` (now `table.src > tbody > tr > td`), which had the
same descendant-selector shape and was compressing the popup's own row
padding, though it never broke layout the way the unscoped `overflow`
override did. General lesson for anything nested inside `table.src`: a
bare `table.src ... td` selector reaches into whatever table is nested
inside that cell too, not just the outer row it was written for.

The header's *event* selector re-colors and re-sorts everything
by any raw event (Ir, Dr, Dw, I1mr, D1mr, ...) or derived one (D1m, DLm,
L1m, LLm, Bm, CEst); it opens on CEst (cycle estimate) by default, not Ir
(`--event CEst` in `callgrind_to_heatmap.py`'s argparse default and
`model_build`'s `default_event`), since CEst is the more actionable
single number. Independent of the selected event, every source line shows
`L1 cache / D1m`, `L3 cache / DLm` and `misprediction / Bcm` columns
(share of that event's total, each heat-colored on its own scale) so a
line that is cheap in Ir but hurts in misses is visible without switching.
Every bare event-key label across the page (these three miss columns, the
"Hottest lines/functions by ..." headings, the per-file stat line, the
per-line detail summary and its "calls from this line" heading) is written
`short / KEY` via `evLabel()`/`EVENT_SHORT` in `callgrind_to_heatmap.py`,
one short name per event callgrind can emit (mirrors `callgrind.py`'s
`EVENT_LONG` / `DERIVED_DEFAULTS`), so the meaning never has to be looked
up. One spot is left as the bare key on purpose, since it already carries
the long name right next to it: the event picker's own dropdown text.
There is no more `[legend]` toggle anywhere on this page or any other
report page (see "Look and feel" below) -- each column's meaning is still
a header tooltip, and the callgrind event glossary lives in `README.md`
behind the top-level `[help]` link instead of being restated per table.
The per-line detail popup dropped its old "all events on this line" table
and its `[manual]` link entirely (not just the per-row "meaning" column),
along with the "no calls recorded from this line" fallback message -- a
line's self/calls numbers are already on the summary line above the
popup's tables, so a popup with only callees and/or callers, or neither,
reads fine without a placeholder. The header strip no longer shows the old
`#hmeta` line (the merged command/loop counts/generated timestamp that sat
between `[home]` and the event dropdown) -- it was metadata nobody read
inline, not documentation, so it was dropped outright rather than moved.
The header's search box is labelled "search", not "find", sits last
in the header row (event, scale, tree, search) rather than second, and is
36ch wide (double the original 18ch -- `#hdr input` in
`callgrind_to_heatmap.py`'s CSS). The
home view carries the 60 hottest lines and the 60 hottest functions, both
tables led by `#, self, function, defined at, source/calls`, then whatever
event/miss columns follow (`callgrind_to_heatmap.py`'s `renderHome`; the
"location" column was renamed "defined at" and moved up front along with
`#`, not appended after it as in an earlier pass -- there is no cols-added-
or-removed rule broken here since `#` was already a column, just not the
first one). Both tables are `fill: true` (see "Look and feel" for what
that does to their width) and every row is a click target
(`table()`'s `opts.rowHref`, and the delegated click handler on `#main`
that checks `tr.rowlink` before the older `tr.clickable` per-line handler)
that jumps straight to the line/function in the file view -- only the
"defined at" cell visibly reacts to hover (its own `<a>`), since a plain
data cell has nothing else to click on and repeating link styling on every
cell in the row would wrongly suggest each one opens something different.
There is no "home"
button and no permanent "cold ... hot" gradient swatch in the header (the
per-cell heat coloring speaks for itself); the header strip is just the
event/scale/tree/search controls. Getting back to the home view from a file
listing is the outer strip's job: re-picking the already-active
"heat map" link there posts a `theme:home` message into the iframe
(`FRAME_JS` in `build_report.py`) instead of reloading it, and the heat
map resets its own `location.hash` on receiving it. Event, scale, tree
order and tree width are remembered in localStorage; table column widths
are not (see "Look and feel" -- dragging a column is a one-visit
convenience only, it never persists). Clicking a filename in the tree
jumps the newly opened file view straight to its hottest line, vertically
centered, rather than opening at the top
of the file (`renderFile`'s `first`-render branch, reusing the same
already-computed hottest-line list the chips row shows).

A file listing also gets a minimap (`#minimap`, VS Code style) after
`#main`, at the far right of the layout (not between the splitter and
`#main` as in an earlier pass -- VS Code's own minimap sits to the right
of the editor, not between a file tree and the editor): a fixed 110px-wide
band, never user-resizable, that
gives a bird's-eye view of the whole current file so the viewer can jump
around without repeated scrolling. Its background is `--bg`, the same
variable `#main` itself is now explicitly given (rather than left to
inherit from `body`), so the two are indistinguishable outside the heat
coloring -- deliberately: like VS Code's own minimap, it should blend into
the editor tonally, and there is no border between them (see "Look and
feel" for why there are no decorative borders anywhere on this page).
`minimapBuild()` (called once per
`renderFile`, same lifecycle as the rest of that function's DOM) clones
each row of the live `table.src`, keeping only its `td.code` cell -- per-line
heat coloring lives on the `<tr>` itself (`tr.heat td { color: inherit }`),
so cloning the row's `style`/`class` with just that one cell reproduces the
coloring exactly with no second, independent render to drift out of sync.
`minimapLayout()` then fits the clone with a plain CSS `transform: scale()`
rather than re-laying out text at a smaller font, and is also what a
120ms-debounced `resize` listener calls to reflow on window resize
(mirroring theme.js's own debounced `relayout()` pattern, kept as its own
listener since the minimap only needs to reposition/rescale existing DOM,
never re-snapshot it) -- so a resize never re-clones the source, only the
next `renderFile` does. The scale factor is `bandWidth / (mmMaxCols *
chPx)`, where `mmMaxCols` is the actual longest source line in the file
(measured character count, from the same clone loop in `minimapBuild()`),
floored at `MM_MIN_COLS` (80) so a file of only short lines still zooms no
closer than that. This used to be a flat `80 * chPx` regardless of the
real file width, which left `mmBox` sized wider than its actual content
for any file with lines shorter than 80 columns -- that leftover space
inside the scaled box showed up as right-side padding whose size tracked
`mmScale`, and therefore the window width, instead of always being zero;
narrow windows (large `mmScale`, close to the `Math.min(1, ...)` clamp)
showed little to none, wide windows showed a visibly uneven gap. Measuring
the real content width and using that for both the scale factor and
`mmBox`'s own explicit width fixes it at every window size. Files under
`MM_MIN_LINES` (40) lines omit the minimap entirely --
`minimapBuild()` checks the line count itself and calls `minimapClear()`
instead (the same function `renderHome` calls, to hide the minimap for the
overview page, which has no single file/`table.src` to snapshot) -- since a
file that short can't have content scrolled off-screen for the minimap to
navigate to.

`#minimap`'s own height is never touched by script -- it is always the
full band the flex layout (`#layout`'s default `align-items: stretch`)
gives it, and that is deliberate: an earlier version had
`minimapLayout()` shorten `#minimap` itself (top-aligned) whenever the
scaled content was shorter than the band, to avoid dead space below the
content that looked clickable but wasn't. That broke two things at once,
both from the same cause -- every later read of "the band height"
(`minimapEl.clientHeight`, used by both `minimapLayout()` on the next call
and by `minimapSync()`) was reading back a value `minimapLayout()` had
itself just shrunk, not the true available height: (1) after viewing one
short file, the band stayed capped at that file's shorter height even
after a resize or switching to a longer file, i.e. the minimap stopped
reaching the bottom of the pane; (2) `minimapSync()`'s viewport-box height
is `bandH * (visible fraction of the document)` -- computed against that
same corrupted `bandH` instead of the actual scaled content height, so the
box's proportions (and therefore its aspect ratio relative to the content
it overlays) were wrong too, most visibly on short files where the true
content height and the corrupted band height differed most. Fixed by
leaving `#minimap` alone and doing the "shorter than the band" case
differently: `mmBox` simply doesn't fill the space below it (nothing
stretches to cover that area), and every place that used to reason about
"the band" -- the click-to-jump math, the drag math, `minimapSync()`'s
viewport-box sizing -- was changed to reason about `min(scaledContentHeight,
bandHeight)` instead, so a click or the viewport box's own proportions
are always relative to the real content, never to a self-mutated element
size. A translucent `#mmViewport` box overlays the portion of the
source currently visible in `#main`'s scroll viewport, exactly like VS
Code's minimap; `minimapSync()` repositions it on every `#main` scroll
event (and after every `minimapLayout()`), moving only the overlay element,
never touching the cloned content. Two independent interaction paths both
end up scrolling `#main`: clicking the bare minimap background computes the
parametric vertical offset and jumps `#main` straight there (guarded so a
click that lands on `#mmViewport` itself is a no-op here); dragging
`#mmViewport` (pointerdown/move/up, the same capture pattern as
`theme.js`'s `splitter()`/column-resize drag) scrubs `#main`'s scroll
position to match the drag instead, and does not touch the snapshotted
content underneath.

`dev/perf2html.sh` writes it to `OUTDIR/heat-map/index.html`. Standalone:

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
are offset from the current source; re-run `dev/perf2html.sh` to get a
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
  the dark background (`#F5F6FA`, `#00A8FF`, `#FBC531`). The raw pair
  values above are the literal "User settings" ones and are what
  `--<name>-l` (the light member) still resolves to; `--<name>` (the dark
  member) is *not* the raw value used directly -- `theme.py`'s `_pair_darken`
  subtracts a fixed amount (`_DARKEN = 0.08`) from its HSL lightness before
  `PAIR` is built, because at the raw values every pair's light/dark
  contrast was barely visible (a relative-luminance ratio of ~1.1-1.35
  across the board) and alternating table columns / panel-vs-background
  read as nearly flat. A multiplicative darken was tried first and
  rejected: navy and slate are already near-black, so a multiplier leaves
  them almost unchanged while blowing out the lighter pairs; a flat HSL
  subtraction moves every pair by roughly the same visible amount. This
  touches every `--<name>` role (`--bg`, `--panel`, `--bar`, `--good`,
  `--bad`, ...) but not the `HEAT` ramp, which is unrelated and untouched.
- Monaco for everything (`--font`, with monospace fallbacks). Because every
  glyph is one `ch` wide, table column widths are set in characters from
  the longest cell (or a fixed 20 for function names, or a clip) and are
  exact; `theme.PAD` adds 1ch padding each side plus 1ch of slack.
- Heat colors are the 12-stop ramp, blended over `--bg` with an alpha that
  grows with the share (log scale from 0.001% to the hottest line), and
  the text on a colored cell is picked by the result's luminance
  (`theme.heat_style()`, the same math in the heat map's `heatStyle()`).
  Speedscope is the exception and keeps its own colors.
- No decorative borders anywhere in this UI -- not on tables, boxes, strips,
  form controls, chips or panes. The *only* lines drawn anywhere are on
  elements the mouse can actually drag: a column-resize bar (`.bar`) and a
  pane splitter (`.split`), both double the width they were originally
  (`.bar::before` 4px, `.split`'s resting/active line 2px/4px) so they read
  clearly as interactive, not as page furniture. Everywhere else, adjacent
  panels/panes/columns are told apart purely by background shading
  (`--panel` vs `--bg` vs `--bg-alt` vs `--nav`) -- the strip's own
  `--nav` background, a table's alternating `col.alt` columns, a chip's
  `--bg-alt` fill, `.dbox`/`.fhead`/`.chips`' `--panel` fill. `select`/
  `input` lose their native browser border the same way (`border: 0`, with
  `border-radius: 0` to also drop a native rounded corner) and get an
  explicit `--bg` background instead so they still read as controls
  against a `--nav`/`--panel` strip (`--panel` and `--nav` are the same
  color, so a control drawn in `--panel` on a strip would be invisible).
  A column boundary that is not being dragged has *no* line at all --
  neighboring columns are told apart only by `col.alt` shading, same as a
  row would be in a striped table.
- Scrollbars are themed the same way, everywhere (`theme.css`, a plain `*`
  selector plus `::-webkit-scrollbar*`, since Firefox's `scrollbar-color`
  and Chromium's `::-webkit-scrollbar` are the only two mechanisms and
  they don't overlap): a square, unrounded thumb in `--blue` (the darker
  of the two "blue" pair members) over a `--gray-l` (the lighter of the
  two "gray" pair members) track, old-fashioned classic-scrollbar sizing
  (14px), no arrow buttons or corner piece drawn beyond the plain
  `::-webkit-scrollbar-corner` fill. It hides entirely when a pane has
  nothing to scroll (native overlay behavior on this size scrollbar, not
  scripted). Hovering the thumb without dragging it lightens it to
  `--blue-l`; starting a drag reverts it to `--blue` -- the same
  resting/active contrast idea as `.bar`/`.split`, just with hover and
  drag swapped, since a thumb mid-drag is already unambiguous from the
  cursor without also needing the lighter color.
- Every table is `theme.table()` (or the heat map's `table()`): a
  full-height bar at each column boundary, which the mouse can drag
  anywhere along its length to resize the column on its left. Column
  widths are **not** persisted -- dragging a bar is a one-visit
  convenience only, and every table opens at its default width on the
  next load or reload. (This used to be backed by a per-table,
  per-column-label localStorage scheme under `cols.*` keys, with its own
  viewport-width bookkeeping (`_vw`) to decide when a saved width still
  applied, a `resize`-triggered purge of stale entries, and a
  `[reset columns]` strip link to force every table back to default. That
  whole mechanism turned out broken in practice and was removed outright
  rather than debugged further -- simpler and more predictable for a
  throwaway profiling tool to just never remember a dragged width than to
  keep chasing edge cases in when a remembered one should still apply.
  `theme.js`'s `store` object survives -- it is the generic localStorage
  wrapper the heat map's own preferences (`heat.event`, `heat.scale`,
  `heat.sort`) and the tree-pane splitter width (`split.<key>`, see
  `Theme.splitter()`) still use; only the table-column-width layer on top
  of it is gone.) A `fill` table (the summary's
  functions table, the heat map's two home tables, `cgdiff.table`) starts
  at exactly 90% of the viewport width, computed once at first render by
  giving the open-ended trailing column an explicit pixel width
  (`theme.js`'s `initTable`/`fillBaseline`) and is never revisited after
  that: dragging any bar, including the trailing one, only ever changes
  that one column's own width for the rest of that page view, growing or
  shrinking the table's total width with it, and the page (or the nearest
  scrolling ancestor) picks up a scrollbar rather than the table clipping
  itself. Every
  column boundary gets a drag bar, including the last column's trailing
  edge (`theme.js`'s `initTable` puts a bar after every column, not just
  `cols.length - 1` of them) -- dragging a `fill` table's last column
  (the summary's callers column, the heat map's per-line detail tables)
  gives that column an explicit width same as any other, so the table may
  stop exactly filling the page width, which is expected. `.tbl`'s own
  14px margin (every side but the top) keeps the trailing bar's grab area
  reachable even against the page's own edge, rather than flush against
  it -- this is margin outside the table box, not padding inside it, so
  it doesn't count as part of the table's own 90%-of-viewport width.
  Each column's
  full meaning is a tooltip on its header cell; there is no "legend"
  link anywhere any more (dropped from `theme.table_render()`, the heat
  map's own `table()`, and the always-visible banner `renderFile()` used
  to print above the per-line source table) -- the callgrind event
  glossary lives once, in `README.md` behind "help", rather than being
  restated per table. A table box never scrolls on
  its own: it is as long as its rows and as wide as its columns, or with
  `fill` 90% of the viewport at first render and then whatever dragging
  has made it since (see above); the page (or the nearest scrolling
  ancestor, e.g. the heat map's `#main`) is what scrolls once a table
  grows past its container, never the table itself. In the heat map's two
  home tables and the summary's functions table, the *entire row* is a
  click target, not just the "defined at"/symbol link in it
  (`table()`'s `opts.rowHref` in `callgrind_to_heatmap.py`, wired through
  a `tr.rowlink` delegated click handler on `#main` that defers to a real
  `<a>` inside the row first) -- only that one cell's own link visibly
  reacts to hover, since a plain data cell has nothing else to click and
  giving every cell the same hover style would wrongly suggest each one
  opens something different. `lines` (the summary's functions table,
  `cgdiff.table`) no longer underlines rows with a divider line (see the
  no-decorative-borders rule above); rows are told apart the same way
  columns are, by `col.alt` shading, and `lines` today only affects
  whether the class is present for future styling, not whether a line is
  drawn.
- Numbers are written for reading: `theme.human()` and the heat map's
  `fmtH()` give `2.1K`, `21K`, `210K`, `2.1M`, `2.0G` -- at least two
  meaningful digits, never `200,000×` -- with the exact value as the
  cell's tooltip; shares go through `theme.pct()` / `fmtP()`: `63.2%`,
  `5.12%`, `<0.01%`.
- The index page is a frame: a strip (`.strip`) with the title, then its
  links as plain words -- no brackets -- generously spaced and
  `|`-separated ("summary  |  flame graph  |  heat map  |  native timing",
  `.strip a + a::before { content: "|" }` with margin on both sides rather
  than a literal space character in the markup), and the summary under it,
  left-aligned and full width; sub-pages are loaded into an iframe only
  when picked. A strip never wraps to a second row: `.strip` is
  `flex-wrap: nowrap` with `overflow: hidden`, each link is `flex: none`
  (its own natural width, never squeezed to make room for a neighbor) with
  its own `max-width: 40ch` and `text-overflow: ellipsis` in case a single
  label is ever pathologically long, and if the full row still doesn't fit
  the trailing links are clipped off at the strip's edge -- the same
  "cut off cleanly, don't wrap" behavior as any overflowing cell in this
  UI, just applied to a whole link instead of to text inside one. The
  currently-picked link (and the picked view generally -- the title badge,
  a strip's "on" link) is highlighted at 100% of the hottest heat-ramp
  color as its background (`--hot`, the last stop in the `HEAT` list) with
  a matching high-contrast foreground (`--hot-fg`, `theme.py` picks
  `--bg` or `--fg` by the same luminance test `heat_style()` uses)
  computed once in `theme.theme_css()` and exposed as those two CSS
  variables, rather than the old plain `color: var(--accent)` treatment.
  The title is the picked view -- `urlparser`,
  `urlparser / heat map` -- and it is the only title anywhere: the pages
  have no heading of their own, and a frame page loaded inside another
  frame hides its title and posts it up (a `{theme: "title"}` message;
  the parent asks with `theme:title?` when it re-shows a frame it already
  loaded), so the top-level strip reads `urlparser / heat map` while the
  nested strip shows only its links. Unlike every other strip entry, the
  title is not an inline colored word: `.strip .title` renders it as its
  own cell, flush with the strip's edges (a negative margin cancels the
  strip's own padding on that side) with a `--good` (green) background and
  `--bg` (dark) text for contrast, so the current navigation choice reads
  as a badge rather than blending into the link row. "help" and
  "curl.se/perf" are on the top-level (overview)
  strip only, in that order, pushed to the far right by `.strip .sp`'s
  flex spacer; see "Every table is `theme.table()`" above for why table
  column widths (and, with them, the old `[reset columns]` link that used
  to sit here) are no longer a thing at all -- there is nothing left on
  this strip for a nested per-test strip to omit other than help/perf,
  so it omits just those two. "help" opens
  `README.md` (plain, un-rendered markdown -- no server, so no renderer)
  in a new tab; `dev/perf2html.sh` copies `dev/README.md` to `OUTDIR/README.md`
  on every run, next to the overview `index.html`. The file is a short
  glossary of the callgrind event columns (Ir, Dr, Dw, D1mr, ...) plus a
  couple of sentences each on using the flame graph (speedscope's "Time
  Order" view is the one worth pointing at) and the heat map -- a help
  screen, not a manual. The heat map's header is the same kind of strip,
  minus a title -- see "Source heatmap (browser)" above for how it gets
  back to its home view without a "home" button.
- The outer frame page itself (`body.frame`) never scrolls -- only its
  `main`/`iframe` children do, each owning its own inner scrolling --
  which is enforced explicitly (`html:has(body.frame), body.frame {
  overflow: hidden }` in `theme.css`) rather than left implicit, because a
  sub-pixel rounding gap between `100vh` and the sum of the strip's and
  the main/iframe's own heights is real under a real (non-overlay)
  scrollbar even though it never reproduces in headless Chrome, and used
  to surface as a spurious near-zero-range vertical scrollbar on the
  frame page on top of the iframe's own legitimate one.

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
2. Profile if needed (`perf record`/`perf report`, `dev/perf2html.sh`,
   gdb, or just read the hot path) to find where time goes in
   `curl_url_set()` for `CURLUPART_URL`. Always profile the RelWithDebInfo
   tree — see "Profiling" above for why. `dev/perf2html.sh` runs
   `dev/scripts/validate_report.py` on its own output as its last step, so
   a report that finishes without error is already known to have every
   expected page.
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
