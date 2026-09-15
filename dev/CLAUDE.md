# curl urlparser perf work

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

`dev/callgrind-profile.sh [loops]` (default 200, `CALLGRIND_CPU` env var to
change the pinned core from the default 3) automates this: builds the
RelWithDebInfo tree, runs a pinned callgrind profile, converts it with
`dev/scripts/callgrind_to_speedscope.py`, and drops a viewable bundle at
`~/Downloads/curlscope/index.html` (override with `CURLSCOPE_DEST`).
Callgrind's own wall-clock is never a valid perf number (30-50x slowdown
from instruction simulation) — use it only for profile shape, and the
pinned direct-binary run above for actual timing.

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
`badoctets()` control-char check at `lib/urlapi.c:274`
(`if(*p <= control || *p == 127)`) — **236,011,200 Ir, 11.94% of total
instructions** on its own (plus 95.4M for the `while(n--)` on line 272 and
47.2M for the `p++` on 277, so the whole loop is ~19% of the program), a
scalar byte-by-byte scan called on
path/query/fragment/user/password/options for effectively every URL (call
sites: `lib/urlapi.c:367,369,371,1157,1183,1216`). Most corpus paths/queries
are "clean" and pay the full length for a boolean answer — a chunked/SIMD
scan there is the obvious next thing to try and has not yet been attempted
(no `lib/urlapi.c` changes made in the profiling session that produced these
numbers).

`free`/`malloc` combined ~10%: every `curl_url_set(CURLUPART_URL,...)` call
tears down and rebuilds the whole internal representation
(`free_urlhandle`, `lib/urlapi.c:74-93`), so allocator overhead is a real
fraction of cost independent of parsing logic.

### Callgrind/speedscope tooling notes

No existing Callgrind→speedscope converter was available (pip blocked by
PEP 668 externally-managed-environment; declined `--break-system-packages`),
so `dev/scripts/callgrind_to_speedscope.py` is written from the Callgrind
format spec directly. Two non-obvious correctness bugs it had to get past,
both caught by a self-check ratio (`sum(emitted weights) / sum(raw
self-cost lines)`, should be exactly 1.0000, printed to stderr on every
run):

1. Callgrind's `calls=` line inclusive cost is **not** additive on top of
   the callee's own `fn=` self-cost lines — it already covers them. Treating
   it as additive gave 10x over-counting (20.2B vs true 1.98B). Fix: use
   `calls=` edges only to build the caller→callee graph structure; walk from
   root frames and distribute each frame's self-cost proportionally across
   its incoming edges by inclusive-cost share (KCachegrind's "callee map"
   approach). Recursion cycles capped at depth 200, folded into the frame
   where detected rather than dropped.
2. Function identity in Callgrind is scoped to its **compressed-ID
   namespace** (`fn=`/`cfn=` share one ID space per the spec), not to
   `(file, name)`. A function's cost-line block can reopen far later in the
   file as a bare `fn=(ID)` while an unrelated `fl=` is "currently active"
   from interleaved callee traversal — keying by `(file,name)` silently
   created a duplicate zero-cost "ghost" frame for `parseurl_and_replace`
   (ratio stuck at 0.9077, 0% self cost shown for the actual hottest
   function). Fixed by keying frames by ID.

Validated end state: ratio 1.0000 exactly; converted JSON's
`parseurl_and_replace` self-weight (37.82%) matches `callgrind_annotate`'s
independent flat-profile number (37.57%) within rounding.

`dev/scripts/build_curlscope_bundle.py` — speedscope's app only defines
`window.speedscope.loadFileFromBase64` after seeing a truthy
`localProfilePath` in the URL hash (reverse-engineered from `bin/cli.mjs` +
the minified bundle; the CLI's own mechanism injects
`<script src="file:///<absolute-tmp-path>">`, which doesn't survive moving
the bundle). Instead: set the hash to a harmless placeholder to trip the
same gate, then a sibling `curlscope-profile.js` (relative path, portable)
polls for `window.speedscope` and calls `loadFileFromBase64` directly with
the profile embedded as base64. Verified against real Chrome (WSL2→Windows
interop, headless screenshot) loading correctly via a plain `file://` path,
no server.

### Reproducing a profile

```sh
dev/callgrind-profile.sh 200          # regenerate everything
xdg-open ~/Downloads/curlscope/index.html
taskset -c 3 ./build-relwithdebinfo/tests/perf/perf urlparser 10000   # manual timing
```

### Line-level view

The speedscope bundle and `top20.md` are *function*-level, and under `-O2`
most of `urlapi.c` is inlined into `parseurl_and_replace` (only
`curl_url_set`, `parseurl_and_replace`, `parse_authority`, `hostname_check`,
`ipv6_parse`, `free_urlhandle` survive as symbols — check with `nm -C
build-relwithdebinfo/lib/libcurl.so.4`). Callgrind charges inlined code to
the enclosing symbol, so to see what is hot *inside* that 37.8% you need the
per-source-line annotation:

```sh
# full per-line annotation of one file (saved copy: dev/trace/urlapi.c.annotated.txt)
callgrind_annotate --show-percs=yes dev/trace/callgrind.out.urlparser.200.<ts> lib/urlapi.c \
  > dev/trace/urlapi.c.annotated.txt
# hottest N source lines of that file, sorted (parses the -- line N markers)
python3 dev/scripts/hotlines.py dev/trace/urlapi.c.annotated.txt lib/urlapi.c 15
```

`=> file:func (Nx)` rows in the annotation are inclusive cost of calls made
from the line above, not source lines; `hotlines.py` skips them.

### Source heatmap (browser)

`dev/scripts/callgrind_to_heatmap.py` renders the whole per-line profile as
one self-contained explorer page (no server, no CDN, works from `file://`):
directory tree on the left, colored and sorted by share of total Ir with
files that have no samples folded away; per-line colored source on the
right; click a line number to see what that line calls (inclusive cost,
links to the callee) and, on a function's first line, who calls it.
`dev/callgrind-profile.sh` writes it as step 5 to
`~/Downloads/curlheat/index.html` (override with `CURLHEAT_DEST`; on this
machine `~/Downloads` is the Windows Downloads folder, so it is also
`C:\Users\ajohn\Downloads\curlheat\index.html`). Standalone:

```sh
python3 dev/scripts/callgrind_to_heatmap.py \
  dev/trace/callgrind.out.urlparser.200.<ts> -o ~/Downloads/curlheat/index.html
```

Only files that carry cost get their source embedded (~0.8 MB page);
`--all-sources` embeds every tracked `.c/.h` under the `--tree` dirs
(default `lib include src tests/perf`) too. It follows
`callgrind_annotate`'s attribution rules exactly (`fi=`/`fe=` switch the
file for inlined lines, the cost line after `calls=` is inclusive and is
charged to the call site separately, `calls=` targets decode relative to
the last cost line) and prints the same self-check ratio as the speedscope
converter, which must be 1.0000; its per-line numbers were verified to match
`hotlines.py` line for line. There was no off-the-shelf tool for this:
KCachegrind has per-line heat but is a desktop app with no directory view,
pprof/Firefox Profiler have source views but no explorer and do not read
callgrind, and coverage-style HTML (lcov, gcovr) has the explorer shape but
only binary hit/miss coloring.

The 20 hottest lines are also marked in-source in `lib/urlapi.c` with
`/* perf #N: X.XX% */` comments on the line above each (rank, share of
total Ir). Those comments are dev annotations, not upstream material: drop
them before submitting anything. Line numbers in profiles taken before the
comments were added (`callgrind.out.urlparser.200.1789436338` and earlier)
are offset from the current source; re-run `dev/callgrind-profile.sh` to
get a profile whose line numbers match.

## Workflow

1. Baseline: run `./build/tests/perf/perf urlparser` a few times, note
   URLs/sec and ns/URL (some run-to-run noise is normal — prefer median of
   3-5 runs). For real timing numbers use the pinned RelWithDebInfo build
   above, not the plain `-O0` `./build` tree.
2. Profile if needed (`perf record`/`perf report`, `dev/callgrind-profile.sh`,
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
