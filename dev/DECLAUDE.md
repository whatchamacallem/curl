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

### `dev/perf2html.sh` — build + profile + report (every perf test)

```sh
dev/perf2html.sh                                     # generates `perf2html_baseline_report`.
dev/perf2html.sh -DCMAKE_C_FLAGS="-O3 -march=native" # generates `perf2html_modified_report`.
dev/perf2html.sh --report="~/try2"                   # generates `~/try2`
```

`dev/perf2html.sh [--verbose] [--report=DIR] [cmake_flags...]`; `--help` prints the script's header comment. Key facts:
- cwd-independent (cd's to `dev/`): a relative `--report=DIR` is `dev/DIR`, `~/` is expanded. Default DIR is `perf2html_baseline_report`, or `perf2html_modified_report` when any cmake_flags are given — after a *source* change alone, pass `--report=perf2html_modified_report` yourself. Last line printed is the report's `file://` URL.
- Build: `cmake -S .. -B build-relwithdebinfo -G Ninja -DCURL_USE_LIBPSL=OFF -DCMAKE_C_COMPILER_LAUNCHER=ccache <cmake_flags>`, then only the `perf` target. `-O2 -g` is prepended to a `-DCMAKE_C_FLAGS=` among the flags or added as one (`-DCMAKE_C_FLAGS=-O3` → `-O2 -g -O3`, the later flag wins). No `CMAKE_BUILD_TYPE`, hence no `-DNDEBUG` (curl's lib has no `assert`; only a `#error` guard mentions it). `CMakeCache.txt` is deleted before every configure, so nothing from a previous run's flags lingers. ccache is required: switching flag sets rebuilds 195 objects from cache in ~12s, same flags = configure only (~7s), no recompile.
- No env vars — constants at the top of the script: `CPU=3`, `BUILD_DIR`, `MANIFEST_VERSION` (`perf2html_diff.sh` has `MANIFEST_OURS`/`MANIFEST_THEIRS`); `TESTS` is read from `tests/perf/Makefile.inc` (`TESTS_C`) and loops are per test in `run_one` (urlparser 200, everything else 200000). Extra valgrind flags (LL cache auto-detects as direct-mapped and overstates conflict misses; `--LL=16777216,16,64` fixes it) go on the `valgrind` line in `profile_run`.
- Profile: `taskset -c 3 valgrind --tool=callgrind --cache-sim=yes --branch-sim=yes` (~17s at loops=200). Events: `Ir Dr Dw I1mr D1mr D1mw ILmr DLmr DLmw Bc Bcm Bi Bim`. Timing: separate native pinned run — the only valid speed number; callgrind's own wall-clock is never used as one.
- Validates nothing itself: `dev/perf2html_batch.sh` is the only caller of `validate_report.py`. Same for `perf2html_diff.sh`.
- Everything the tools print goes to `dev/trace/profile.<ts>.log` (quiet mode) or the terminal (`--verbose`); a failing step shows its last 40 lines.

Naming scheme across `dev/`: `object_method`-style lowercase C-identifier form (e.g. `args_parse`, `theme_css`, `profile_parse`, `report_test`). Each script's entry point is `main()`, defined at the bottom of the file directly above `if __name__ == "__main__":`. Follow this for any new top-level Python/shell function. Embedded JS in generators' HTML templates is untouched by this rule.

### Report layout

```text
OUTDIR/, all file://-openable, nothing fetched at view time
index.html          overview: cross-test strip + header table + "test suites" table (one
                    row per test, its native timing numbers, name links to its report)
<test>/index.html   one test's summary: strip (title badge + "|"-separated links) +
                    collapsed valgrind log, collapsed raw-data link, "top 50 functions
                    by self" table (#, % self, symbol, calls, callers — callers/symbol
                    link to heat map)
<test>/flame-graph/ speedscope bundle + profile.js (Ir, D1mr+D1mw, DLmr+DLmw, I1mr, Bcm, Bim)
<test>/heat-map/    per-line source heat map (event selector, miss columns)
<test>/perf-tool/   native timing run output (output.txt + index.html, binary/build header)
<test>/raw/         the callgrind file, repo-root path prefix stripped
all/                every test's callgrind data merged into one profile, same shape
README.md           event-column glossary + flame graph / heat map notes + a "The
                    Scripts" section (usage for all three perf2*.sh, reader-facing
                    prose only — keep it in step with their header comments); copied
                    from dev/README.md every run; opened by the "help" link
MANIFEST.txt        line 1 = the generator's version string, `curl/perf2html.sh v1` —
                    the only thing that makes a directory a recognized diff input (a
                    diff report's own reads perf2html_diff.sh v1). Below it, the
                    overview's header rows as LABEL=VALUE lines (build / timed),
                    passed to the page via `--header-file`, which keeps
                    LABEL=VALUE lines only and so ignores line 1. A reader checks the
                    version or ignores it. perf2html_diff.sh re-reads each side's rows
                    so the diff overview can show both source reports' own stats.
                    Written by `run_all` after every test, so an aborted run leaves no
                    manifest and cannot be diffed. validate_report.py requires the
                    version line and each `Layout.manifest_labels` row.
```

Raw data in `dev/trace/` (gitignored): `callgrind.out.<test>.<loops>.<ts>`, `valgrind.<test>.<loops>.<ts>.log`, `<test>.<loops>.<ts>.speedscope.json`, `profile.<ts>.log` (quiet mode only). Every path embedded in a generated page is relative — OUTDIR is portable.

**Generated pages are deterministic**: same callgrind input ⇒ byte-identical output, so a page diff is always code, never sampling. Nothing timestamped reaches a page — `dev/trace/` keeps the `<ts>` for run history, but the copy under `<test>/raw/` drops it (`callgrind.out.<test>.<loops>`, `callgrind.diff.<test>`) because the summary prints that basename as link text, `MANIFEST.txt` has no `generated=` row, and the speedscope document name (`--name`, also what `build_flame_graph.py` shows, read from the JSON's own `name`) is stamp-free. The one allowed timestamp-shaped output is `perf-tool/output.txt`'s measured durations — it is a timer artifact. Check with: run any generator twice on one input and `cmp`.

### `dev/perf2html_diff.sh` — compares two reports

```sh
dev/perf2html_diff.sh                             # `perf2html_baseline_report` vs `perf2html_modified_report` -> `perf2html_diff_report`
dev/perf2html_diff.sh ~/before ~/after            # -> `perf2html_diff_report`
dev/perf2html_diff.sh ~/before ~/after ~/delta    # -> `~/delta`
```

`dev/perf2html_diff.sh [--verbose] [baseline-dir modified-dir] [report-dir]` — 0 dirs = the defaults, 1 = report-dir, 2 = baseline modified, 3 = all; `--verbose` only first; relative dirs under `dev/`, `~/` expanded; `--help` prints the header comment. Key facts:
- Inputs are two `perf2html.sh` OUTDIRs, recognized by the **first line** of `MANIFEST.txt` alone (`manifest_check` reads it with `head -1`, never the whole file, since the header rows follow: a diff report's own version string names `perf2html_diff.sh`, so a diff can't be diffed; a report predating the manifest must be regenerated). Tests are paired by directory name (`tests_pair`); a test only one side has is noted on stderr and skipped.
- Output: mirrors the input layout — `index.html` (overview) + `<test>/index.html` + `<test>/heat-map/` + `<test>/raw/callgrind.diff.<test>` + `README.md` + `MANIFEST.txt` (its own version line + `baseline`/`modified` rows). **No flame graph, no native timing** — a delta has no call graph for speedscope, and two wall clocks don't subtract.
- The overview's header is a `baseline` and a `modified` block (`--header-block LABEL=FILE`, one `<h2>` + header table each) holding that side's `report=` directory followed by its own `MANIFEST.txt` header rows, so the diff page shows the same build/timed stats as the two reports it came from. `header_file_of` in the diff script writes each block's file to `dev/trace/header.<role>.<ts>.txt` (`grep '='` on the source manifest, so its version line never becomes a row); a source report whose manifest is the version line alone contributes its directory alone.
- Every number is MODIFIED − BASELINE, **per source line**: `callgrind_diff.py` parses both sides with the shared parser, subtracts per (function, file, line) via `Profile.function_lines` — never per (file, line) alone, which hands roughly half of an inlined function's cost to its neighbour (`line_function` is first-seen) — and writes a plain callgrind-format file: `fl=`/`fn=`/`fi=` per function, that function's entry line first (a zero-cost line if it did not change), `summary:` = the signed total so the 1.0000 self-check holds on the delta too. No `calls=` lines: the delta has no call graph, hence no calls/callers columns in the summary and no call columns/caller tables in the heat map (`HAS_CALLS`).
- Shares use the **sum of all magnitudes** as denominator (`callgrind_diff.profile_magnitudes()` = Σ|per-function line delta|, the finest granularity, so no line or function share exceeds 100%), not the near-zero signed total. Summary table and both heat-map home tables rank by `abs()`, so biggest winners and losers interleave at the top; heat intensity is `abs()` too. Heading is "top N functions by change in self"; `HOT` becomes "Most changed".
- Ranking event is `Ir` (`build_report.EVENT`); the heat map's event picker still offers every event. Delta header: `desc: Baseline: <file>`, `desc: Modified: <file>`; the repo root is stripped from every written path.
- `dev/trace/callgrind.diff.<test>.<ts>` + `diff.<ts>.log` (quiet mode).

**Core vs diff code.** The non-diff path is byte-for-byte checkable against an older generator (build both from one `raw/` file with `git show <rev>:dev/scripts/*` copies and `cmp`). `build_report.py`: `report_test`/`functions_table` are core, `diff_report_test`/`diff_functions_table` are the diff, both through `report_page()`; `--diff` only picks the function in `main()`. `callgrind_to_heatmap.py`: `model_build()` is core, `diff_model()` patches `meta.totals`/`meta.diff`; in its JS every diff override sits in the one `if (DIFF) {...}` block (`fmtP`/`fmtH` wrapped with a sign, `HOT`/`HOT_LINES`/`SELF.title`), and ranking/heat go through `mag()` (= `Math.abs`, a no-op on a profile's non-negative costs). `validate_report.py` is data-driven by `Layout` (`LAYOUT_FULL`/`LAYOUT_DIFF`, picked by `--diff`).

### Scripts (`dev/scripts/`)

Every CLI below is invoked only by the three shell scripts (`perf2html.sh`, `perf2html_diff.sh`, `perf2html_batch.sh`); the signatures here are the checklist of what each still takes (`--help` on any of them lists its arguments).

- `callgrind.py` — the one parser: per-line/function cost vectors, call graph. `profile_load(path)` parses one file and exits unless the self-check ratio (printed to stderr) is 1.0000. `REPO_ROOT` (from the script's own location — no `--repo-root` flag anywhere) and `path_norm(path) -> PathInfo(display, local, group)` are the one path resolver every generator uses (`local` is None unless the file is readable; `group` is repo/system/external). Functions keyed by **name** (not object), so a symbol in two objects is one function. Derived events added when inputs exist: `D1m`, `DLm`, `L1m`, `LLm`, `Bm`, `CEst` (= Ir + 10·L1m + 100·LLm). Tables are keyed by NamedTuples (`SourceLine`, `CallSite`, `Caller`), call-graph edges are `Tally(count, costs)`. `Profile.function_lines[fn][SourceLine]` is the only per-context table (`line_self` merges every `fn=` context a line was charged under). A function nobody recorded a call to gets `function_entry` from the **first** cost line callgrind wrote for it in its home file — that matched the `calls=` target line in 505/505 checked functions; the lowest line number does not (inlined helpers sit above the entry).
- `theme.py`/`theme.css`/`theme.js` — shared look/behavior, inlined by every generator (see "Look and feel").
- `build_report.py test FILE -o OUT --test TITLE --raw-data FILE [--log FILE] [--diff] [--header LABEL=VALUE]...` — the summary page; `--diff` dispatches to `diff_report_test` (abs ranking, signed numbers, `DIFF_VIEWS` strip, no calls/callers columns); `--header` rows form the page's top table. `build_report.py timing -o OUT --test NAME --output-file FILE [--header ...]` — the native timing page. `build_report.py overview -o OUT --test NAME... [--header LABEL=VALUE] [--header-file FILE] [--header-block LABEL=FILE] [--diff]` — the cross-test page; `--header-file` appends a file's `LABEL=VALUE` lines to the `--header` rows and silently drops every other line (that is how `MANIFEST.txt` reaches the page, version line and all), `--header-block` adds a further table under its own `<h2>` from such a file (repeatable; the diff's baseline/modified blocks), `--diff` swaps each test's native timing for its `Ir` change. **"header" = the label/value rows above a page's real content** (`Header`/`HeaderBlock`, `header_table`, `header_read_file`, `header_parse_blocks`) — not the heat map's `MetaModel`, which is a profile's event metadata. `EVENT = "Ir"` and `TOP = 50` are constants.
- `callgrind_diff.py BASELINE MODIFIED -o DELTA` — subtracts per (function, file, line), writes a callgrind-format delta (see perf2html_diff.sh above). Also home of `profile_magnitudes()`, which the generators import.
- `callgrind_to_heatmap.py FILE -o OUT --title T [--diff]` — heat-map/index.html; `DEFAULT_EVENT = "CEst"`, `TREE` = the directories whose tracked `.c/.h` files are listed even without samples. `--diff` = `diff_model()`: shares against `profile_magnitudes()`, signed numbers, "Most changed" headings (the JS `if (DIFF)` block). Call columns and the popup's caller table/note exist only when the profile has a call graph (`HAS_CALLS`).
- `callgrind_to_speedscope.py FILE -o JSON` (`EVENTS` constant, one speedscope profile per expression, `A+B` sums; document name = the file's basename) + `build_flame_graph.py --speedscope-dir DIR --profile-json JSON` (writes `profile.js`, patches a fresh `index.html`) — flame-graph/.
- `validate_report.py OUTDIR [--diff]` — structural smoke test, called only by `perf2html_batch.sh` step 5 (pages exist/non-truncated, titles, strip links, `raw/` has a callgrind file without the absolute repo root, timing line + `Errors:` present); an `overview`-titled index also walks every test directory it links to. Every report's `MANIFEST.txt` is checked at the root: first line = `Layout.manifest_version`, plus a `LABEL=` row per `Layout.manifest_labels` (full: build/timed; diff: baseline/modified). `--diff` = heat map only, "by change in self" heading, overview must carry the `baseline`/`modified` header blocks (`Layout.header_blocks`).
- `check_js.py` — `node --check` on `theme.js` and on every JS chunk embedded in a generator's Python string (`SOURCES` lists the module/attribute pairs; `<script>` blocks that are only a `__PLACEHOLDER__` are skipped). Add a pair here when a generator grows new embedded JS.

Both `callgrind.py`'s parser and `callgrind_to_speedscope.py`'s walk print self-check ratios to stderr on every run — must be exactly/~1.0000 or nothing is written. If you touch either script, re-verify those ratios.

`dev/scripts/*.{py,js,css}` carry **no comments or docstrings** — none in the Python, none in the JS/CSS embedded in its string literals, none in the standalone `theme.js`/`theme.css`. Symbol names are the only documentation; behavioral notes belong here or in `dev/README.md`. Keep new edits comment-free. Shebangs stay. `argparse.ArgumentParser()` gets no description, so `--help` lists only the arguments by design.

### `dev/perf2html_batch.sh` — every check the tooling has, one run

```sh
dev/perf2html_batch.sh                          # lint, both reports, the diff, validate all three
dev/perf2html_batch.sh --keep                   # don't delete the three report dirs first
dev/perf2html_batch.sh -D CMAKE_C_FLAGS=-O3     # the modified build's flags
```

`dev/perf2html_batch.sh [--verbose] [--keep] [cmake_flags...]`; `--help` prints the header comment. Five steps, in order: **1 lint** (pyright over `dev/scripts` per `dev/pyrightconfig.json` — `standard` mode, `pythonVersion` 3.11, must stay at **0 errors** — plus `check_js.py`, which catches a `\n` that needed `\\n` in JS-inside-a-Python-string before it reaches a generated page), **2 baseline** (`perf2html.sh` → `perf2html_baseline_report`), **3 modified** (`perf2html.sh <flags>` → `perf2html_modified_report`, default flags `-D CMAKE_C_FLAGS=-Os`), **4 diff** (`perf2html_diff.sh` → `perf2html_diff_report`), **5 validate** (`validate_report.py` on all three, `--diff` on the last). Key facts:
- The three report dirs are **deleted before step 2** (`--keep` skips it) so a stale page can't be validated in place of a fresh one; ~2.5min for a full run (two builds + two callgrind passes).
- Every step runs even if an earlier one failed — one run reports every broken thing, not just the first. Exit 1 if any failed, and the closing line names them (`perf2html_batch: N step(s) failed: ...`). Last line on success is the diff report's `file://` URL.
- **Step 5 is the only `validate_report.py` call anywhere**; `perf2html.sh`/`perf2html_diff.sh` validate nothing. Keep it that way — don't re-add a validate step to a generator.
- Quiet mode logs each step to `dev/trace/perf2html_batch.<ts>.log` and prints the last 40 lines of a failing one; `--verbose` streams everything and is passed down to both generators.
- `cmake_flags` go to `perf2html.sh` untouched. Both cmake spellings work and keep their form: glued `-DCMAKE_C_FLAGS=-Os` and separated `-D CMAKE_C_FLAGS=-Os` (two argv words) both get `-O2 -g` prepended in place by `args_parse`; `CMAKE_CXX_FLAGS` does nothing here (curl is C).
- **This is where the generators are tested.** Driving them over all three output directories is their coverage — neither runs a check of its own, and neither should grow one.
- Replaced `dev/lint.sh` (deleted — its pyright/check_js body is step 1); named `dev_test.sh` for one commit before the `perf2html_*` rename.

The checker is **pyright**, installed from PyPI: `pip3 install --user --break-system-packages pyright` → `~/.local/bin/pyright` (this box is PEP-668 externally-managed and has no pipx/uv; the flag matches how the other `~/.local/bin` tools got there). **Pylance is not usable here** — it is a VS Code extension, and its bundled `dist/pyright.bundle.js` speaks LSP only, ignores argv and prints nothing (no `outputjson` string in it).

Typing rules in `dev/scripts/` (everything annotated, no `Any`-shaped records): a record is a `NamedTuple` (`callgrind.SourceLine`/`Term`/`DerivedEvent`, `theme.Column`/`Cell`/`ColorPair`, `build_report.View`/`StripLink`, heat map `LineCost`/`CallRow`); anything summed in place is a `@dataclass` (`Profile`, `Tally`, speedscope `Graph`, heat map `_FileAccumulator`/`_LineAccumulator`). JSON-bound shapes: an object is a `TypedDict` (`HeatModel`/`FileModel`/`FunctionModel`, `SpeedscopeDoc`, `ThemeRuntime` — a NamedTuple would serialize as an array), a positional array is a NamedTuple (`json.dumps` writes it as the `[a, b, c]` the page indexes). Cost vectors are `callgrind.Costs` (`list[int]`), summed only via `costs_add`/`costs_accumulate`/`tally_accumulate`. Each CLI turns argparse into a NamedTuple (`TestArgs`, `HeatArgs`, `SpeedscopeArgs`, ...) before calling anything. Naming: a field that would shadow a method of its base class gets a trailing underscore, never a synonym — a NamedTuple's `index`/`count` (pyright: overrides `tuple`'s methods) is `index_`/`count_` (`ResolvedTerm.event_index`, `LineCost.count_`, `CallRow.count_`); a dataclass field with the same meaning stays plain (`Tally.count`). Generator output is reproducible run to run (the heat map's `model_build` walks raw file names sorted, so the `raw` field of an external header that several build paths map to is always the same one); byte-compare generated pages directly.

### Line-level view (why the heat map exists)

Under `-O2` most of `urlapi.c` inlines into `parseurl_and_replace`; only `curl_url_set`, `parseurl_and_replace`, `parse_authority`, `hostname_check`, `ipv6_parse`, `free_urlhandle` survive as symbols (`nm -C build-relwithdebinfo/lib/libcurl.so.4`). Flame graph / top-N table are function-level only. Use the heat map, or cross-check with:

```sh
callgrind_annotate --show-percs=yes dev/trace/callgrind.out.urlparser.200.<ts> lib/urlapi.c
```

The 20 hottest lines are marked in `lib/urlapi.c` with `/* perf #N: X.XX% */` comments — **dev annotations, drop before submitting upstream**. Line numbers only match profiles taken after those comments were added; re-run `dev/perf2html.sh` if unsure.

### Look and feel (theme rules — apply to any dev/ page changes)

- One dark theme. `theme.py`'s `COLOR_PAIR` values are raw "User settings" THEME entries, odd index = dark member, even = light; `--<name>-l` is the light member. Don't touch the `HEAT` ramp with this rule. Exception: `--bg` (`ROLE["bg"]`) is the slate dark member darkened 8% via `_shade()` (`#2F3640` → `#2B323B`); every page background, the scrollbar track, the minimap band and the heat blend (`heat_style()`/`heatStyle()` via `theme_runtime()`) all follow it, so change it only there.
- Monaco/monospace everywhere; column widths are exact `ch` counts: the header label is every column's floor (a header never ellipsizes), then the longest cell text; `width` = exact, `clip` = cap; + `theme.PADDING_CHARS` (1ch padding each side + 1ch slack). One rule in two places — `colWidths()` in the heat map's script and `table_render()` in theme.py — keep them in step.
- Heat colors: 12-stop `HEAT` ramp blended over `--bg`, alpha on log scale of magnitude; text color picked by resulting luminance (`theme.heat_style()` / `heatStyle()`). Non-diff pages index it single-ended, `0..1` low-to-high (unchanged). Diff pages index it signed, `-1..1` across the *whole* ramp — negative (savings) toward `HEAT[0]` (cold/blue end), positive (regressions) toward `HEAT[-1]` (hot/red end), 0 at the ramp's midpoint — via `heat_style(heat, signed=True)` / the JS `if (DIFF)` branch inside `heatStyle`/`heatP` (`(heat+1)*0.5` remap before indexing; sign no longer stripped before the call). Only caller needing `signed=True` today: `diff_functions_table`'s "% self" column; the heat map's `heatT`/`heatP` auto-detect via the module-level `DIFF` const. Speedscope keeps its own colors (untouched by theme).
- No decorative borders anywhere. The only drawn lines are drag targets: column-resize `.bar` and pane `.split`, both invisible at rest and painted only on hover/active (`.bar::before`/`.split` background is `none` until `:hover`/`.active`). Everything else is told apart by background shading only (`--panel`/`--bg`/`--bg-alt`/`--nav`). `select`/`input` get `border:0; border-radius:0` + explicit `--bg`.
- A `<select>` whose option text length varies with page state (heat map's `#event`, long name changes per event) gets a fixed `style.width` in `ch` sized to its longest option + slack at populate time, so picking a different option never reflows sibling controls.
- Scrollbars: square unrounded `--blue` thumb, 14px, no arrows, track = pane's own `--bg` (exception: `pre.logbox` matches `--panel`). No hover/active state on the thumb itself.
- Every table is `theme.table_render()` / heat map's `table()`: draggable resize bar at every column boundary including the trailing edge. Column widths are **never persisted** — reload always resets to default; "reset columns" link (top-level strip only) undoes drags for the current view only. `fill` tables (summary functions table, heat map's per-file source listing) span `data-fill` × the visible width of the pane that scrolls them (`scrollerOf()` in theme.js: nearest `overflow: auto|scroll` ancestor, else the document — never `window.innerWidth`, the heat map's listing pane is only part of the window; default 0.9, the source listing sets `data-fill="1"` = edge to edge between tree and minimap), floored to whole px so rounding can't raise a sideways scrollbar; the `grow` column (`<col class="grow">` — heat map `col.grow`, theme.py `Column.grow`; else the last) takes the rest, and its own default width is its minimum (source listing: `SRC_COLS` = 80 visible chars; summary `callers`: its label), so a pane too narrow for the static columns plus that minimum scrolls sideways instead of squeezing it — at 1366×768 with the default 280px tree the urlparser listing is 1095px in a 932px pane, the two right-most miss columns need a scroll or a narrower tree. `fillTable()` re-fits on every `Theme.relayout()` (window resize, tree splitter drag — one rAF per move) until a column bar is dragged (`table._dragged`); "reset columns" clears that and re-fits. `fillTable()` returns at once for a table with no layout (`offsetWidth` 0): under `display:none` every rect and `clientWidth` reads 0, so it would fit the grow column to `0px` — the frame's `home` is hidden behind the iframe, and a window resize / "reset columns" / a load with `#<view>` in the URL used to leave the summary's `callers` column at 0px. Frame `show()` calls `Theme.relayout(home)` on every return to the summary, so whatever changed while hidden is fitted then (probe: `col.style.width`/last `th` width must be >0 after `#heat-map` → `resize` → summary). The trailing `.bar` lies wholly inside the table (`.bar:last-child`, line flush with the right edge) so a 100% table never pokes past its pane. Heat map's two home tables ("Hottest lines by"/"Hottest functions by") are plain (non-`fill`) tables sized to content, same as the tree pane, so a long column header can't stretch a heat-colored value cell into a wide bar or push a trailing column off-screen. No per-column tooltip is a "legend" link anymore — glossary lives once in README.md. Full row is a click target on `fill`/rowlink tables; only the one real `<a>` cell shows hover state.
- Numbers: `theme.num_human()`/`fmtH()` → `2.1K`/`21K`/`2.1M`/`2.0G` (exact value in tooltip); shares via `theme.num_pct()`/`fmtP()` → `63.2%`, `<0.01%`. Diff pages wrap both in a sign: `theme.num_signed()`/`num_signed_pct()` and the JS `fmtH`/`fmtP` overrides in the `if (DIFF)` block → `+4.3K`, `−37.8%` (U+2212 in the page, exact zero renders as empty, not `+0`; `fmtH(0)` is `0`).
- Index page is a frame: strip (title badge + `|`-separated plain-word links, no brackets, `flex-wrap: nowrap` so it clips rather than wraps) + its own page; sub-pages load into an iframe on click. Picked link/title highlighted at `--hot`/`--hot-fg`. Title = current view path (`urlparser / heat map`). `theme.TITLE_COLUMNS` sets `--title-w` and must stay ≥ the **widest title any page can show** — `len("simpleformat diff / native timing")`, i.e. the longest `TESTS_C` name + the longest view label + the diff suffix; too small and the badge silently clips mid-word (`flex-wrap: nowrap`) on exactly the one test/view pair nobody opens. "reset columns" / "help" / "curl.se/perf" sit right-aligned via `.strip .sp`.
- Frame pages nest two deep: the overview frames a test summary, which frames that test's heat map / flame graph / native timing (the heat map's `#hdr` is a controls strip, not a frame strip). Both `FRAME_JS` levels are the same script, which decides by `framed = window.parent !== window` and by `data-frame` on the active strip link (set for the overview's per-test links, `StripLink.frame`):
  - **Title badge**: printed only by the outermost strip (`setTitle` writes `""` when `framed`). The badge element stays, so it reads as one continuous `--title-bg` block down the stacked strips and every strip's links line up at `--title-w`. `document.title` is still set at every level.
  - **Util block** (`#util`: "reset columns | help | curl.se/perf"): lives on the lowest strip that has one. A framed page always shows it; a top-level page hides it (`util.hidden`) only while it frames another frame page, which brings its own. A single-test report opened on its own therefore keeps it on its top strip.
  - **"reset columns"** walks the whole nest: each level resets its own `home` and posts `theme:reset-cols` down (`resetAll()`), and a framed page runs `resetAll()` when it receives that message from `window.parent`, so the click reaches all three documents. Probe both with the Chrome `probe.html` trick (a framed `contentDocument` is same-origin only with `--allow-file-access-from-files`).
- URL = the whole state, one grammar at every level. Frame page (`FRAME_JS` `parse()`/`build()`): `#<view>[/<inner hash without #>]`, e.g. `#heat-map/f=lib/urlapi.c&l=1343&e=Ir`. Heat map (`hashOf()`/`stateOf()`): `f=<file>` file, `f=<file>&l=<n>` line (popup open), `fn=<name>` function (popup at its entry line), none = home; `&e=<event>` always spelled out when the profile has >1 event; `enc()` percent-encodes values but keeps `/` readable. Every click is `location.hash =` (one history entry per step, back/forward walk them); `route()` renders it, then rewrites the canonical spelling via `replaceState` (unknown file/function → home, unknown line → its file, unknown event → default) and posts `{theme:"hash", hash}` up; `FRAME_JS` `sync()` mirrors it into `#<view>/...` via `replaceState`. Closing a popup ([X], "close", re-clicking its row) navigates to `hashFor(curFile)` = the file. `fn=` links: summary symbol/caller cells (`entry_link()`, `urllib.parse.quote` with encodeURIComponent's safe set + `/`), home "Hottest functions" rows, popup callee "defined at" (`linkFn()`/`fnLinkable()`); `f=&l=` links: hottest lines, chips, popup caller "called at". Bare `#heat-map` = home at the default event — nothing is remembered outside the URL (`heat.event` localStorage is gone); scale/sort/search stay `localStorage`-only (`heat.scale`/`heat.sort`).
- Render is a function of the hash: `route()` rebuilds the listing only when the `shown` key (file, event, scale) changes — a rebuild of the same file keeps `scrollTop`, a new file without `l` centers its hottest line — then `detailSet(line)` reconciles the popup (`detailOpen()`; the popup under the row is the only marker of the picked line — no outline/recolor on the row; the row is centered only if `rowOnScreen()` is false, so a clicked row stays put while a chip/link/bookmark scrolls to it). Scale change: `shown = ""` then `route()`; event pick: `location.hash = hashOf({...state, ev})`.
- `FRAME_JS` puts a page into the frame with `view.contentWindow.location.replace(href + (sub || "#"))` — never `iframe.src`, which adds a joint history entry per load so back would desync strip and frame (headless Chrome check: `history.length` +1 per hash step, +0 per frame load, back/forward restore both levels). `"#"` not `""` for the empty state: a fragment-less URL is a document reload, `#` a fragment navigation. Same page and same `state` → nothing. Four messages, all checked by source (`event.source === view.contentWindow` inward, `=== window.parent` outward). **inner→outer**: `{theme:"hash"}` (heat map only — `FRAME_JS`'s own `sync()` must **not** post it, or a middle level's hash races the heat map's real state and a deep link like `#urlparser/heat-map/f=lib/urlapi.c&l=1343&e=Ir` collapses to `#urlparser/heat-map/e=Ir`) and `{theme:"title"}`, which is how a title set two levels down reaches the outermost badge. **outer→inner**: `"theme:reset-cols"` and `"theme:title?"`, the latter sent by `show()` when the frame already holds the wanted page (`href === page`, so no `location.replace` fires) to re-ask for a title that would otherwise go stale. A framed page's `setTitle` writes `""` into its own badge but still posts up and still sets `document.title`. Probe: `#urlparser/heat-map` must leave `document.title` and the badge reading `urlparser / heat map`, not `urlparser`.
- Routing tests: jsdom (page loaded from an `http://localhost/` URL, `location.hash =` then a tick — `hashchange` is async) covers the heat map alone; the frame page needs Chrome (`location.replace` across documents isn't implemented in jsdom): copy `index.html` to `probe.html` beside it with an appended `<script>` that sets `location.hash`, awaits the mirrored canonical hash and writes a log `<pre>`, run with `--dump-dom --virtual-time-budget=30000`. Cross-origin `file://` frames are opaque — observe the outer hash/title/`history.length` only.
- Outer frame page (`body.frame`) never scrolls itself — only `main`/`iframe` children do (`overflow: hidden` on both `html:has(body.frame)` and `body.frame`, to avoid a real (non-overlay) scrollbar sub-pixel rounding gap that doesn't repro in headless Chrome).
- Heat map source table: columns `<event>`, `line`, `source`, `calls`, D1m, DLm, Bcm. No row-wide heat (`tr` carries only id/class/`data-ln`/title): the event, line and source cells each get the line's self heat inline, `calls` (cost of the calls made from the line, share of the event total) its own heat on the same scale, D1m/DLm/Bcm theirs (`extraCells`) — so no cell's text is ever contrast-colored against another cell's background. `EVS`/`EXTRA` (`callgrind_to_heatmap.py`) list every event the profile can produce (raw `events:` membership, derived only gated by `resolved_derived_events()` having all its terms) — **not** filtered by whether its total/magnitude happens to be zero, so the event dropdown and the D1m/DLm/Bcm columns stay layout-stable across profiles/diffs instead of columns appearing/disappearing based on what happened to change; a genuinely all-zero column just renders blank cells (`extraCells`'s `self ? fmtP(...) : ""`), no heat, no `NaN`. `TOTAL`/`MAXPX[key].total` guard `|| 1` for a zero-total event so percentages come out `0`, not `NaN`. Clickable-row hover cue = underline on `td.ln` (an inline heat `color` beats any stylesheet color, so a `--link` recolor can't show on heated lines). Minimap clone rows take their heat from the cloned `td.code` itself.
- Call counts are a metric of their own, heat-colored by share of every call the profile recorded (each call site's count, summed), log-scaled to the most-called function, same ramp/alpha as cost, event-independent: heat map `numCalls()` (`CALLS_TOTAL`/`CALLS_MAXP`; home functions `calls`, popup `call count` columns), summary `functions_table()` (`calls_total`/`calls_max_pct`). Speedscope untouched. Reader-facing rule: README.md "Colors".
- Heat map code view layout (`renderFile()`): `.fhead` band, `.chips` and the listing's `.tbl-cols` sit inside one `.srcwrap` (`width: max-content; min-width: 100%`) so the wrapper is exactly the sideways scroll range and the sticky band's background reaches its far right edge after the listing is dragged wider than the pane. Bands/chips get `contain: inline-size` (without it their *unwrapped* single-line width is what max-content takes, pushing the wrapper past the pane on every file). `td.code` clips (no `overflow: visible`) so nothing spills past the table. The listing has no side margins: it fills the pane edge to edge (`data-fill="1"`, source = the `grow` column) and dragging a column grows it rightward past the pane; it is a `bare` `table()` (no `.tbl` box) because `alignSticky` only stacks header cells outside a `.tbl` box under the sticky bands. Order gotcha: `minimapBuild()` runs **before** `Theme.init()` — the band narrows the pane by 110px and the fill measures the pane as it is at that moment. `centerRow()` (vertical only, centered in the part of the pane below `coverH()`) replaces `scrollIntoView`, which also pulled the pane sideways for a row wider than it.
- Heat map minimap (`#minimap`/`#mmBox`/`#mmViewport`): never scrolls itself and `#minimap` is never resized; `minimapLayout()`'s scale = `min(1, bandW/(MM_MIN_COLS·mmChPx), bandH/mmCloneH)` — pinned to `MM_MIN_COLS` (80) only, never widened to the file's longest line; the clone `table.src` has `width: 100%` + `table-layout: fixed` (fixed layout needs a non-auto table width, else the lone column sizes to the longest line and heat rows stop there) + `td { overflow: visible }`, so heat spans the band and longer lines are clipped by `#minimap`. `mmCloneH` = clone `offsetHeight`, read only after the band's `empty` class is removed (display:none measures 0). `mmViewport`'s fill is `rgba(245,246,250,0.36)`, border alpha `0.55`. Scroll sync caches nothing: `mmGeom()` reads live rects every time — `rows` = tbody height minus an open `tr.detail`, `above(y)` = row px above client-y `y` (popup excluded), `cover` = `coverH()` = `.band` heights + first `th` height, `head` = first `th` bottom. Only the `th` cells are sticky, the `<thead>` scrolls away — never measure the thead. Box top/height = `mmCloneH·mmScale` × fractions `above(head)/rows`, `(above(bottom)−above(head))/rows`; `mmScrollTo(r0)` is the inverse (click centers the clicked row on screen, drag moves the box). `minimapSync()` is also called after a popup opens/closes (`detailSet()`; changes visible rows without a scroll event). Verify with a DOM probe: rows with rect between first-th bottom and pane bottom must match `top/height` of `#mmViewport` mapped back to row numbers.
- Heat map detail popup (`.dbox`, `detailOpen()`): "copy" writes a plain-text twin built in parallel with the HTML (`tableText()` mirrors `table()` off the same `cols`/`rows`), not scraped `textContent` — a space-padded GFM pipe table so the columns line up pasted raw or rendered. Stashed as `tr.detail._copyText`; JS source embedded in a Python triple-quoted string needs literal `\n` written as `\\n` or it breaks the generated page's `<script>` (`node --check` the extracted script after touching this function). Line headline has two exact forms picked by whether the line is a function's entry line (`evLong()` gives the long event name): entry line → `path:ln self P% by <long event name>, H <EVENT_KEY>.` (no `in fnName`/`line`/`:` — the "entered here" heading right below already names it); otherwise → `path:ln in fnName: line self P% <long event name>, H <EVENT_KEY>` (no trailing period). Both forms append inline EXTRA (D1m/DLm/Bcm) stats whenever nonzero, so all per-line stats are handed over in one place rather than only as bare source-table columns. Function-entry heading reads `fnName by call count: self P%, total P%.` (dropped the old "is entered here — ... Called from (by call count):" phrasing since the table's own `call count` column already says that); without a call graph (`HAS_CALLS` false: a diff) it reads `fnName: self P%.` and no caller table or "(no recorded caller ...)" note follows.

### Checking pages in a browser (no browser inside WSL2)

```sh
"/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --disable-gpu \
  --window-size=1366,768 --screenshot="\\\\wsl.localhost\\$WSL_DISTRO_NAME\\tmp\\x.png" \
  "file://wsl.localhost/$WSL_DISTRO_NAME/home/t/curl/dev/perf2html_baseline_report/index.html#heat-map"
```

`--dump-dom` instead of `--screenshot` for post-script DOM (append a probe `<script>` that runs on `load`, after `theme.js` init). Node+jsdom works for interaction tests (click/drag/open) but layout is all-zeros and `localStorage` throws on `file://` — use `http://localhost/` for jsdom, Chrome for anything geometric. jsdom is **not installed** on this box (no global or repo `node_modules`); the Chrome probe above needs nothing extra and is what verified the diff/plain heat maps (headings, columns, popup heading, `−` signs). Target viewport: 1366×768 (medium laptop) — pages must not assume more.

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
5. Compare: `dev/perf2html.sh --report=perf2html_modified_report` then `dev/perf2html_diff.sh`; keep only changes that measurably help AND keep `Errors:` constant.
6. Record before/after numbers here (in "Current state") as you go.
7. Before calling anything final: full test suite (`tests/runtests.pl` or `ctest` from `build/` with `-DBUILD_TESTING=ON`) — this perf test alone doesn't validate correctness.
