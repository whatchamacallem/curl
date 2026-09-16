# curl urlparser perf work

## User settings (Do not modify)

Heatmap Colors = `["#3E4A89", "#31688E", "#26828E", "#1F9E89", "#35B779", "#6DCD59", "#B4DE2C", "#FDE725", "#FFC83B", "#FFA22C", "#FF7F21", "#F06142"]`

Theme Colors = `["#00A8FF", "#0097E6", "#E84118", "#C23616", "#9C88FF", "#8C7AE6", "#F5F6FA", "#DCDDE1", "#FBC531", "#E1B12C", "#7F8FA6", "#718093", "#4CD137", "#44BD32", "#273C75", "#192A56", "#487EB0", "#40739E", "#353B48", "#2F3640"]`

## Working rules

1. More than one question/concern/option → terse numbered list, proceed in that order.
2. Keep this file current: any tooling/report-layout/theme/findings change updates CLAUDE.md in the same change. Keep updates in this file's compact style — facts, commands, numbers, gotchas needed to act; no narrative, history, or rationale for rejected approaches. Prefer editing an existing line over appending a new paragraph.
3. No source line numbers here (they silently rot) — refer to a function/identifier/grep-able snippet.
4. `dev/` is throwaway profiling tooling, not upstream material: one shared parser, one shared theme, no dead code, no duplicate systems. Anything a script writes must open from `file://` with nothing fetched at view time.
5. A request bundling several distinct changes → state a checklist up front, work in order, close with a short per-item report (done / changed from ask / not applicable) — no running narration.

## Goal

Optimize `tests/perf/urlparser.c` (and, as needed, `lib/urlapi.c` / `lib/uint-table.c` / `lib/idn.c`) to improve the "urlparser" perf chart: https://curl.se/perf/index.html#urlparser

```
./build/tests/perf/perf urlparser [loops]   # default loops=10000; use ~1000 for quick iteration
```

Don't change the corpus (`urls[]`, ~577 URLs) or the `CURLU_*` option cross-product in `tests/perf/urlparser.c` — invalidates comparison to the public chart. `Errors:` count must stay constant across changes (nonzero is expected/correct; a drop means URLs are being wrongly rejected, not "faster").

## Build

```sh
cmake -S . -B build -G Ninja -DCURL_USE_LIBPSL=OFF
cmake --build build --parallel
cmake --build build --target perf      # EXCLUDE_FROM_ALL, must be named explicitly
```

`CURL_USE_LIBPSL=OFF` is the only intentional deviation (libpsl-dev not installed, `REQUIRED` when ON). Everything else is CMake defaults. Drop the flag if libpsl-dev gets installed.

Debugging: open `dev/` or repo root in VS Code, "perf urlparser" launch config (rebuilds `perf`, runs under gdb).

## Profiling

Never profile the plain `./build` tree (`-O0`, no `-DNDEBUG`): inlining differs from `-O2` so hot-function attribution is wrong (`parseurl_and_replace` alone is 37.6% under `-O2`; separate small functions under `-O0`). Use a second tree:

```sh
cmake -S . -B build-relwithdebinfo -G Ninja -DCURL_USE_LIBPSL=OFF -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build-relwithdebinfo --parallel
cmake --build build-relwithdebinfo --target perf
```

Always pin to a core — WSL2 scheduling noise is ~106% run-to-run unpinned, <1-3% pinned:

```sh
taskset -c 3 ./build-relwithdebinfo/tests/perf/perf urlparser 10000
```

### `dev/perf2html.sh` — automates build+profile+report

```sh
dev/perf2html.sh                                    # -> dev/report, every perf test
dev/perf2html.sh ~/artifacts urlparser              # one test
dev/perf2html.sh ~/artifacts urlparser -DUSE_AVX512  # rebuild with a #define first
dev/perf2html.sh --verbose ~/artifacts urlparser    # stream every tool's output
```

Full reference: `dev/perf2html.md` / `dev/perf2html.sh --help`. Key facts:
- `OUTDIR` default `dev/report` (gitignored). `PERFTEST` = a `tests/perf/Makefile.inc` name or `all` (default) — writes `OUTDIR/<test>/`, merged `OUTDIR/all/`, and `OUTDIR/index.html`.
- Anything after OUTDIR/PERFTEST becomes `CMAKE_C_FLAGS` for a fresh build (passed every run — never lingers from a prior run).
- Build: `build-relwithdebinfo`, `-O2 -g`, ccache when on PATH.
- Profile: `valgrind --tool=callgrind --cache-sim=yes --branch-sim=yes`, pinned `taskset -c $CALLGRIND_CPU` (default 3), `CALLGRIND_LOOPS` (default 200 urlparser / 200000 others), `CALLGRIND_OPTS` for extra valgrind flags. Events: `Ir Dr Dw I1mr D1mr D1mw ILmr DLmr DLmw Bc Bcm Bi Bim`. LL cache auto-detects as direct-mapped (overstates conflict misses) — override with `CALLGRIND_OPTS="--LL=16777216,16,64"` when LL numbers matter.
- Timing: separate native pinned run (`perf <test>`) — the only valid speed number; callgrind's own wall-clock is never used as one.
- `validate_report.py OUTDIR` runs automatically as the last step (structural smoke test, not a numeric re-check); a report that finishes without error already has every expected page.
- Everything the tools print goes to `dev/trace/profile.<ts>.log` (quiet mode) or the terminal (`--verbose`).
- `--top N` (default 50) sets top-N-functions table size.

Naming scheme across `dev/`: `object_method`-style lowercase C-identifier form (e.g. `args_parse`, `theme_css`, `profile_parse`, `report_test`, `heatmap_main`). Follow it for any new top-level Python/shell function. Embedded JS in generators' HTML templates is untouched by this rule.

### Report layout

```text
OUTDIR/ (or OUTDIR/<test>/ under `all`), all file://-openable, nothing fetched at view time
index.html          strip (title badge + "|"-separated links) + summary: collapsed
                    valgrind log, collapsed raw-data links, "top N functions by self"
                    table (#, % self, symbol, calls, callers — callers/symbol link to
                    heat map). Log omitted on the `all` page (--no-log).
flame-graph/        speedscope bundle (Ir, D1mr+D1mw, DLmr+DLmw, I1mr, Bcm, Bim)
heat-map/           per-line source heat map (event selector, miss columns)
perf-tool/          native timing run output
README.md           event-column glossary + flame graph / heat map notes; copied from
                    dev/README.md every run; opened by top-level "help" link
raw/                callgrind file(s), repo-root path prefix stripped
```

Raw data in `dev/trace/` (gitignored): `callgrind.out.<test>.<loops>.<ts>`, `valgrind.<test>.<loops>.<ts>.log`, `profile.<ts>.log` (quiet mode only), speedscope JSON. Every path embedded in a generated page is relative — OUTDIR is portable.

### Scripts (`dev/scripts/`)

- `callgrind.py` — the one parser: per-line/function cost vectors, call graph, `desc:` lines. `load(paths)` parses+`merge()`s multiple files. Functions keyed by **name** (not object), so a symbol in two objects is one function. Derived events added when inputs exist: `D1m`, `DLm`, `L1m`, `LLm`, `Bm`, `CEst` (= Ir + 10·L1m + 100·LLm).
- `theme.py`/`theme.css`/`theme.js` — shared look/behavior, inlined by every generator (see "Look and feel").
- `build_report.py` — `test`/`timing`/`overview` pages.
- `callgrind_to_heatmap.py` — heat-map/index.html.
- `callgrind_to_speedscope.py` (`--event` repeatable, `A+B` sums, `--repo-root` relativizes) + `build_flame_graph.py` — flame-graph/.
- `callgrind_to_cgdiff.py BEFORE... -- AFTER... -o OUT.html` — regression diff via `dev/profile_diff.sh`.
- `validate_report.py OUTDIR` — structural smoke test (pages exist/non-truncated, strip links present, `raw/` has real files, timing line present, no leaked absolute paths). `--test NAME` narrows an overview check.

Both `callgrind.py`'s parser and `callgrind_to_speedscope.py`'s walk print self-check ratios to stderr on every run — must be exactly/~1.0000 or nothing is written. If you touch either script, re-verify those ratios.

### Line-level view (why the heat map exists)

Under `-O2` most of `urlapi.c` inlines into `parseurl_and_replace`; only `curl_url_set`, `parseurl_and_replace`, `parse_authority`, `hostname_check`, `ipv6_parse`, `free_urlhandle` survive as symbols (`nm -C build-relwithdebinfo/lib/libcurl.so.4`). Flame graph / top-N table are function-level only. Use the heat map, or cross-check with:

```sh
callgrind_annotate --show-percs=yes dev/trace/callgrind.out.urlparser.200.<ts> lib/urlapi.c
```

The 20 hottest lines are marked in `lib/urlapi.c` with `/* perf #N: X.XX% */` comments — **dev annotations, drop before submitting upstream**. Line numbers only match profiles taken after those comments were added; re-run `dev/perf2html.sh` if unsure.

### Comparing two runs

```sh
dev/profile_diff.sh BEFORE_DIR AFTER_DIR [TEST] [OUTPUT.html]
```

Uses valgrind's real `cg_diff` (function-level only — it always emits line `0`, no line-level regression diff is possible this way). `TEST` needed only for an `all`/overview OUTDIR.

### Look and feel (theme rules — apply to any dev/ page changes)

- One dark theme. `theme.py`'s `PAIR` values (`_DARKEN = 0.08` subtracted from raw "User settings" HSL) are the dark member; `--<name>-l` is the raw light member. Don't touch the `HEAT` ramp with this rule.
- Monaco/monospace everywhere; column widths are exact `ch` counts (`theme.PAD` = 1ch padding + 1ch slack).
- Heat colors: 12-stop ramp blended over `--bg`, alpha on log scale of share; text color picked by resulting luminance (`theme.heat_style()` / `heatStyle()`). Speedscope keeps its own colors (untouched by theme).
- No decorative borders anywhere. The only drawn lines are drag targets: column-resize `.bar` and pane `.split`, both invisible at rest and painted only on hover/active (`.bar::before`/`.split` background is `none` until `:hover`/`.active`). Everything else is told apart by background shading only (`--panel`/`--bg`/`--bg-alt`/`--nav`). `select`/`input` get `border:0; border-radius:0` + explicit `--bg`.
- A `<select>` whose option text length varies with page state (heat map's `#event`, long name changes per event) gets a fixed `style.width` in `ch` sized to its longest option + slack at populate time, so picking a different option never reflows sibling controls.
- Scrollbars: square unrounded `--blue` thumb, 14px, no arrows, track = pane's own `--bg` (exception: `pre.logbox` matches `--panel`). No hover/active state on the thumb itself.
- Every table is `theme.table()` / heat map's `table()`: draggable resize bar at every column boundary including the trailing edge. Column widths are **never persisted** — reload always resets to default; "reset columns" link (top-level strip only) undoes drags for the current view only. `fill` tables (summary functions table, heat map's two home tables, cgdiff table) open at 90% viewport width, computed once at first render; dragging never re-triggers that calc. No per-column tooltip is a "legend" link anymore — glossary lives once in README.md. Full row is a click target on `fill`/rowlink tables; only the one real `<a>` cell shows hover state.
- Numbers: `theme.human()`/`fmtH()` → `2.1K`/`21K`/`2.1M`/`2.0G` (exact value in tooltip); shares via `theme.pct()`/`fmtP()` → `63.2%`, `<0.01%`.
- Index page is a frame: strip (title badge + `|`-separated plain-word links, no brackets, `flex-wrap: nowrap` so it clips rather than wraps) + summary; sub-pages load into an iframe on click. Picked link/title highlighted at `--hot`/`--hot-fg`. Title = current view path (`urlparser / heat map`); nested frames hide their own title and post it up via `{theme:"title"}`. "reset columns" / "help" / "curl.se/perf" exist only on the top-level strip, right-aligned via `.strip .sp`.
- Outer frame page (`body.frame`) never scrolls itself — only `main`/`iframe` children do (`overflow: hidden` on both `html:has(body.frame)` and `body.frame`, to avoid a real (non-overlay) scrollbar sub-pixel rounding gap that doesn't repro in headless Chrome).
- Heat map source table: only the row's own self-cost heat (`tr[style]`) may recolor text via `color: inherit`, scoped to `td.ln`/`td.self`/`td.code` only — `td.incl` ("calls") and `td.x` (D1m/DLm/Bcm) carry independent cost/their own inline heat background and must never inherit the row's contrast color, or the two heats visually stack and neither reads correctly.
- Heat map minimap (`#minimap`/`#mmBox`/`#mmViewport`): never scrolls itself, so `minimapLayout()`'s scale must satisfy both width (`bandW / (mmMaxCols*mmChPx)`) and height (`bandH / mmNaturalH`) — width-only scale left tall files' thumbnail frozen on the first screenful while `#mmViewport` kept sliding down past content never actually drawn.
- Heat map detail popup (`.dbox`, `toggleDetail()`): "copy" writes a plain-text twin built in parallel with the HTML (`tableText()` mirrors `table()` off the same `cols`/`rows`), not scraped `textContent` — a space-padded GFM pipe table so the columns line up pasted raw or rendered. Stashed as `tr.detail._copyText`; JS source embedded in a Python triple-quoted string needs literal `\n` written as `\\n` or it breaks the generated page's `<script>` (`node --check` the extracted script after touching this function).

### Checking pages in a browser (no browser inside WSL2)

```sh
"/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --disable-gpu \
  --window-size=1366,768 --screenshot="\\\\wsl.localhost\\$WSL_DISTRO_NAME\\tmp\\x.png" \
  "file://wsl.localhost/$WSL_DISTRO_NAME/home/t/curl/dev/report/index.html#heat-map"
```

`--dump-dom` instead of `--screenshot` for post-script DOM (append a probe `<script>` that runs on `load`, after `theme.js` init). Node+jsdom works for interaction tests (click/drag/open) but layout is all-zeros and `localStorage` throws on `file://` — use `http://localhost/` for jsdom, Chrome for anything geometric. Target viewport: 1366×768 (medium laptop) — pages must not assume more.

## Current state (update this section as findings change)

Validated baseline (RelWithDebInfo, pinned, `loops=10000`, median of 7 runs): **137.66 ns/URL**, **~7.26M URLs/sec**, `Errors: 1240000` (constant across every run/build so far).

Hot-spot breakdown (`loops=200` → 807,800 `curl_url_set()` calls, 1,977,194,203 Ir total, `-O2 -g`):

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

Hottest single line: inlined `badoctets()` control-char test in `lib/urlapi.c` (`if(*p <= control || *p == 127)`) — **236,011,200 Ir, 11.94%** alone (+95.4M loop condition, +47.2M pointer increment ≈ 19% of the program total). Scalar byte-by-byte scan, called on path/query/fragment/user/password/options per URL (grep `badoctets(`). **Not yet attempted: chunked/SIMD scan here** — the obvious next optimization target.

`free`/`malloc` ≈10% combined: every `curl_url_set(CURLUPART_URL,...)` tears down and rebuilds the whole handle (`free_urlhandle()`) — allocator overhead independent of parse logic; a reuse/arena strategy is a second candidate.

No `lib/urlapi.c` changes have been made yet in the profiling work that produced these numbers — the above is still the baseline to beat.

## Workflow

1. Baseline: `./build/tests/perf/perf urlparser` a few runs (median of 3-5) for a quick read, but **real numbers only from the pinned RelWithDebInfo build**.
2. Profile via `dev/perf2html.sh` (or manual callgrind/gdb) on the RelWithDebInfo tree only.
3. Make one focused change.
4. Rebuild (`cmake --build build --target perf`, plus the lib if `lib/` changed) and re-run.
5. Compare to baseline; keep only changes that measurably help AND keep `Errors:` constant.
6. Record before/after numbers here (in "Current state") as you go.
7. Before calling anything final: full test suite (`tests/runtests.pl` or `ctest` from `build/` with `-DBUILD_TESTING=ON`) — this perf test alone doesn't validate correctness.
