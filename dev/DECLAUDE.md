# curl perf work

## Rules

1. Keep this file current in the same change as any
   tooling/layout/theme/findings change. `CLAUDE.md` is a symlink to
   `dev/DECLAUDE.md`. Compact style: facts, commands, numbers, gotchas. No line
   numbers (they rot) — name a function/identifier.
1. `dev/` is throwaway profiling tooling: one shared parser, one shared theme,
   no dead code, no duplicate systems. Everything a script writes must open
   from `file://` with nothing fetched at view time.
1. **No fake data.** Every value on a page is a recorded measurement or plain
   arithmetic on one (sum, difference, share, `CEst`). No apportioning,
   interpolation or "plausible" stacks. If a tool can't supply what a view
   needs (callgrind: per-call stacks/time), the view isn't built.
1. **Nothing test-specific, ever.** No test names, file lists or per-test cases
   anywhere in `dev/`; every view is built for every test in `TESTS_C`.
   Examples read `<test>`/`<file>`. (`urlparser`/`lib/urlapi.c` was a first
   trial only — never single it out.)

## Commands

```sh
dev/perf2html.sh [--verbose] [--keep-raw] [--regenerate] [--report=DIR]
    [cmake_flags...]
dev/perf2html_diff.sh [--verbose] [--keep-raw] [--regenerate]
    [baseline-dir] [modified-dir] [report-dir]
dev/perf2html_batch.sh [--verbose] [--keep] [--keep-raw] [--regenerate]
    [cmake_flags...]
```

**Iterating on generators: `dev/perf2html_batch.sh --regenerate`** — rebuilds
all three reports' pages from their last run's raw data. Seconds, not ~2.5min.
Needs `dev/trace/` to still exist, i.e. the recording run used `--keep-raw`.
Re-measure only when the measured thing changed (`lib/` edit, different flags,
new test).

Build (plain tree, debugging only):

```sh
cmake -S . -B build -G Ninja -DCURL_USE_LIBPSL=OFF
cmake --build build --target perf      # EXCLUDE_FROM_ALL, must be named
```

`CURL_USE_LIBPSL=OFF` is the only intentional deviation (libpsl-dev absent).
Never profile `./build` (`-O0`: inlining differs, attribution wrong) — use
`build-relwithdebinfo`. Always pin: WSL2 noise is ~106% unpinned, \<1-3%
pinned.

```sh
taskset -c 3 ./build-relwithdebinfo/tests/perf/perf <test> [loops]
```

## How the three scripts fit together

- `perf2html.sh` — builds + profiles + generates one report. Default DIR
  `perf2html_baseline_report`, or `perf2html_modified_report` when any
  cmake_flags are given (after a *source*-only change, pass
  `--report=perf2html_modified_report` yourself). cwd-independent (cd's to
  `dev/`); relative DIR is under `dev/`. Last line printed is the `file://`
  URL.
- `perf2html_diff.sh` — measures nothing; subtracts two reports' own `raw/`
  data.
- `perf2html_batch.sh` — the only thing that runs checks. Five steps: 1 lint
  (pyright, must be **0 errors**, + `check_js.py`), 2 baseline, 3 modified
  (default `-D CMAKE_C_FLAGS=-Os`), 4 diff, 5 `validate_report.py` ×3. Every
  step runs even after a failure; exit 1 names the failed ones.

Key behaviors worth knowing before touching them:

- `--keep-raw` keeps `dev/trace/`; otherwise it's deleted at startup. **The
  batch owns every `dev/trace/` deletion** — it passes `--keep-raw` down so a
  child can't unlink the batch log mid-run, and deletes after step 5. A failed
  flagless batch *keeps* `dev/trace/` (the step logs are the evidence).
- `--regenerate` implies `--keep-raw`, and in the batch also `--keep`. It reads
  `stamp=` back from the report's own `MANIFEST.txt` and rebuilds
  byte-identically when no generator changed.
- **Step 5 is the only `validate_report.py` call anywhere.** Don't add a
  validate step to a generator.
- **The batch is the generators' test suite** — driving them over all three
  output dirs is the coverage. Don't grow a per-generator check.
- Profiling:
  `taskset -c 3 valgrind --tool=callgrind --cache-sim=yes --branch-sim=yes`.
  Timing is a *separate* native pinned
  `perf stat -x, -e cycles:u,instructions:u` run — its `Time*` lines are the
  only valid speed number; callgrind's wall clock never is.
- Trace tree `build-instr` = same flags + `-finstrument-functions` +
  `dev/cyg_callback.c` linked in. Whole build instrumented, no file list.
- No env vars; constants live at the top of each shell script (`CPU=3`,
  `LOOPS_DIVISOR=50`, `SKIP_ALL`, `MANIFEST_VERSION`). `TESTS` comes from
  `tests/perf/Makefile.inc`; loops from `loops_of` grepping the test source.
- Valgrind's LL cache auto-detects as direct-mapped and overstates conflict
  misses — `--LL=16777216,16,64` is on the `valgrind` line in `run_one`.
- Quiet mode logs to `dev/trace/*.log`; a failing step prints its last 40
  lines.

## Report layout

```text
OUTDIR/
index.html          overview: strip + header table + "test suites" table
                    (one row per test, its native timing numbers, name
                    links to its report)
<test>/index.html   summary: strip + collapsed perf log / trace log /
                    valgrind log / raw-data links + "top 50 functions
                    by self"
<test>/flame-graph/ speedscope bundle + profile.js (recorded rdtsc trace)
<test>/heat-map/    per-line source heat map
<test>/perf-tool/   output.txt only (rendered as the summary's "perf log")
<test>/raw/         callgrind file (repo root stripped) + the trace's
                    speedscope JSON
all/                every test's callgrind data merged, same shape
README.md           glossary + notes; copied from dev/README.md every
                    run ("help" link)
MANIFEST.txt        line 1 = version string; then LABEL=VALUE header rows
```

Exceptions to remember:

- The **"all"** synthetic test: no perf log, no trace log, no raw-data section,
  no flame graph (the files still exist on disk, just unlinked).
- A **diff report**: no flame graph, no native timing, and per-test pages have
  no preamble at all — strip straight to the table.
- `MANIFEST.txt` line 1 is the *only* thing that makes a directory a diff input
  (`head -1`; a diff's own version string names `perf2html_diff.sh`, so diffs
  can't be diffed). Written by `run_all` after every test, so an aborted run
  leaves none.
- **Every path written to a page or manifest is relative** — `path_display()` /
  `$REPO` stripping. `validate_report.py`'s `home_dir_check` walks every file
  and fails on the author's `$HOME`: a report must be copyable off-box.

**Generated pages are deterministic** — same input ⇒ byte-identical output, so
a page diff is always code, never sampling. Only `MANIFEST.txt`'s `stamp=` and
genuinely re-measured time (`perf-tool/output.txt`, `flame-graph/output.txt`,
the trace) vary. Verify by running a generator twice on one input and `cmp`.

Raw data in `dev/trace/` (gitignored): `callgrind.out.<test>.<loops>.<ts>`,
`valgrind.<test>.<loops>.<ts>.log`, `trace.<test>.<loops>.<ts>.bin` (+`.maps`),
`.speedscope.json`, `perf-stat.<test>.<ts>.csv`, `profile.<ts>.log`.

## Diff semantics

- Every number is **MODIFIED − BASELINE, per (function, file, line)** — never
  per (file, line) alone, which hands half an inlined function's cost to its
  neighbour.
- The delta is a plain callgrind-format file with **no `calls=` lines** → no
  call graph → no call columns/caller tables in the heat map (`HAS_CALLS`). The
  summary's calls/callers columns come from a separate JSON sidecar
  (`callgrind_diff.py --callers-output`, consumed via
  `build_report.py test --diff --callers-data`).
- Shares use `profile_magnitudes()` = Σ|per-function line delta| as
  denominator, **not** the near-zero signed total. Ranking and heat are
  `abs()`, so winners and losers interleave.
- `summary:` in the delta = the signed total, so the parser's 1.0000 self-check
  holds on it too.

**Core vs diff code.** The non-diff path stays byte-checkable against an older
generator. Keep the split: `BuildReport.test`/`.functions_table` core vs
`.diff_test`/`.diff_functions_table`; `CallgrindToHeatmap.model()` core vs
`.diff_model()`; in heat-map JS every diff override sits in the one
`if (DIFF) {...}` block; `validate_report.py` is data-driven by
`ValidateReport.ReportLayout` (`_LAYOUT_FULL`/`_LAYOUT_DIFF`).

## `dev/scripts/` conventions

**79 columns is the hard max** for every line of `dev/` source — code and
comment alike, in every language. `scripts/reformat.sh` enforces it, and a line
still over 79 after the formatters run is an **error**, not a note:
`long_lines_report` prints `file:line`, the width and the whole line, and the
script exits 1. The formatters cannot reach those lines — embedded JS/CSS in a
Python string literal, `echo` text in a shell script, a fenced block in `.md` —
so they are rewrapped by hand. Whole tree is at 0.

Rewrapping an embedded block changes every generated page (the CSS and JS are
inlined into each one), so a page diff after such an edit is expected;
`perf2html_batch.sh --regenerate` then a diff against a snapshot is how you
check that only the inlined `<style>`/`<script>` moved. Text a script `echo`s
into `perf-tool/output.txt` is *page content*, so rewrapping it does change the
report — split it into extra `#` lines rather than letting it overflow.

Not to be confused with the **80-column source *view*** in the heat map
(`SRC_COLS`, `MM_MIN_COLS`), which is the standard width the profiled `lib/`
source is rendered at — that stays 80 and has nothing to do with how `dev/` is
written.

**Comments: short, tech-writer style, never docstrings.** Every class and
function gets one `# <Name> - what it is` line above it, wrapped to a second
`#` line if it must be. Every field gets a one-line `#` comment **above it**,
never trailing — no arg-by-arg docs, no `:param:`, no reStructuredText. Names
carry the meaning; the comment only says what a name can't. Still no comments
in JS/CSS embedded in string literals or in `theme.js`/`theme.css`. Shebangs
stay. `ArgumentParser()` gets no description by design.

**Class names read like a how-to, not an abbreviation** — `CompressedNames`,
`PositionDecoder`, `FileTally`, `ExecutableMapping`, `TraceRecording`,
`ReportLayout`. A name needing a comment to be legible is the wrong name.

**Naming:** `object_method` lowercase C-identifier form (`args_parse`,
`profile_parse`, `report_test`) for shell functions and public free functions;
a method drops the prefix its class supplies (`Callgrind.parse`,
`BuildReport.report_page`). Entry point is always `main()`, directly above
`if __name__ == "__main__":`.

**File shape:** constants → classes → public free functions → `main()`. One
enclosing class per script, named after it in PascalCase, holding **every**
non-exported function — no free helpers, no nested `def`s. A second class only
when it carries its own state. Classes alphabetical within two bands (record
types, then logic classes); methods alphabetical. Public free functions are
one-line delegations (`profile_load(paths)` → `Callgrind().load(paths)`) so
callers never name a class.

**Constants are alphabetical ignoring the leading `_`** — so `BODY` sorts
before `_CSS`, `_EVENT_LONG` before `REPO_ROOT`. The *only* constants allowed
below the classes are the ones that can't be evaluated above them: a constant
whose value names a class in the same file (`_DERIVED_DEFAULTS`, `_HOLDERS`,
`_LAYOUT_FULL`/`_LAYOUT_DIFF`, `_FLAME_VIEW`/`_HEAT_VIEW`, `_TIME_UNITS`) or a
singleton/derived value built from one (`theme.py`'s
`_RENDERER`/`_NUMBERS`/`_COLOR_PAIR`/`_ROLE`). Those sit after the class that
defines them, alphabetical among themselves where order allows.

**Typing** (pyright `standard`, py3.11, 0 errors): everything annotated, no
`Any`-shaped records. Record → `NamedTuple`; anything summed in place →
`@dataclass`. JSON object → `TypedDict` (a NamedTuple would serialize as an
array); JSON positional array → `NamedTuple`. Cost vectors are
`callgrind.Costs` (`list[int]`), summed only via
`costs_add`/`costs_accumulate`/`tally_accumulate`. Each CLI converts argparse
into a NamedTuple before calling anything. A field shadowing a base-class
method gets a trailing underscore, never a synonym (`index_`, `count_`); a
dataclass field with the same meaning stays plain.

pyright is at `~/.local/bin/pyright`
(`pip3 install --user --break-system-packages pyright`; PEP-668 box, no
pipx/uv). Pylance is not usable — LSP only, ignores argv.

### The scripts

- `callgrind.py` — the one parser. `profile_load(path)` exits unless the
  self-check ratio (stderr) is exactly **1.0000** — re-verify after touching
  it. It is cost conservation only, and says nothing about whether emitted
  structure was observed (rule 3). `REPO_ROOT` +
  `path_norm() -> PathInfo(display, local, group)` are the one path resolver
  every generator uses — no `--repo-root` flag exists. Functions keyed by
  **name**, so a symbol in two objects is one function. Derived events when
  inputs exist: `D1m`, `DLm`, `L1m`, `LLm`, `Bm`, `CEst` (= Ir + 10·L1m +
  100·LLm). `Profile.function_lines[fn][SourceLine]` is the only per-context
  table. `function_entry` for an uncalled function = the **first** cost line
  callgrind wrote in its home file (matched 505/505; lowest line number does
  not — inlined helpers sit above the entry).
- `build_report.py test|overview` — summary and overview pages.
  `_EVENT = "Ir"`, `_TOP = 50`. `--perf-log`/`--trace-log`/`--raw-data` each
  render a section only when given; the flame-graph strip link exists only with
  `--trace-log`. `--diff` picks `diff_test` in `main()`. "header" here means
  the LABEL=VALUE rows above a page's content (`Header`/`HeaderBlock`) — not
  the heat map's `MetaModel`.
- `callgrind_diff.py` — the subtraction; also home of `profile_magnitudes()`,
  which generators import. `--callers-output` is required.
- `callgrind_to_heatmap.py` — `_DEFAULT_EVENT = "CEst"`, `_TREE` = dirs whose
  tracked `.c/.h` are listed even without samples.
- `dev/cyg_callback.c` — the recorder. Hot path is
  `if(next < end) { next->fn = fn; next->tsc = rdtsc | flag; ++next; }` — 11/12
  instructions (check with
  `cc -O2 -fcf-protection=none -S -masm=intel dev/cyg_callback.c`). `next`
  must stay a pointer, `end` a variable. `next == end` = not sampling;
  everything else lives on that cold path. Setup is a constructor (incl.
  `memset` of the buffer, so no page fault lands in a timed call; the
  buffer holds `CYG_CALLBACKS_MAX_REC`=327680 records, 5MB static, and no
  test fills it), teardown a destructor
  writing `CYG_OUT` + `.maps`. Its header comment is the format reference.
  Single-threaded.
- `trace_to_speedscope.py` — pairs enters/exits (mismatch = non-zero exit),
  takes the busiest run's first `_MAX_CALLS`=200 complete calls under
  `_MAX_BYTES`=204800. No test is bound by `_MAX_CALLS` — the byte budget
  alone sets capture length, so bytes/call decides how many calls land
  (31–196 across `TESTS_C`). `at` is raw (hook cost included). Must run while
  `build-instr` still holds the traced binary (symbolization reads it). GCC
  instruments inlined bodies, so inlined helpers are frames.
- `validate_report.py OUTDIR [--diff]` — structural smoke test only;
  `flame_graph_check` requires exactly one `evented` profile whose `exporter`
  is `_FLAME_EXPORTER`, so a synthesized or stale flame graph fails.
- `check_js.py` — `node --check` on `theme.js` and every JS chunk embedded in a
  Python string (`_HOLDERS`). **Add a pair here when a generator grows new
  embedded JS.** This is what catches a `\n` that needed `\\n`.

## Why the heat map exists

Under `-O2` small static functions inline into their callers, so the
function-level top-N table charges their cost to the caller. The heat map shows
it per source line; the flame graph shows inlined bodies as own frames.
Cross-check:

```sh
callgrind_annotate --show-percs=yes \
  dev/trace/callgrind.out.<test>.<loops>.<ts> <file>
```

`/* perf #N: X.XX% */` comments in `lib/` are stale dev annotations — drop
before submitting upstream.

## Look and feel

One dark theme, Monaco/monospace everywhere. Target viewport **1366×768** —
pages must not assume more.

- `theme.py`'s `_COLOR_PAIR` values are raw "User settings" THEME entries, odd
  index = dark member; `--<name>-l` is light. Exception: `--bg` is the slate
  dark member darkened 8% via `Theme.shade()` — page background, scrollbar
  track, minimap band and heat blend all follow it, so change it only there.
  The `_HEAT` ramp is exempt from the pair rule.
- Heat = 12-stop `_HEAT` blended over `--bg`, alpha on log scale of magnitude,
  text color by resulting luminance. Non-diff indexes `0..1`; **diff indexes
  signed `-1..1` across the whole ramp** (savings → cold/blue, regressions →
  hot/red, 0 at midpoint) via `heat_style(signed=True)` / the JS `if (DIFF)`
  branch.
- Call counts are their own metric, heat-colored by share of all recorded
  calls, log-scaled, event-independent.
- Numbers: `num_human()`/`fmtH()` → `2.1K`/`2.0G` (exact in tooltip);
  `num_pct()`/`fmtP()` → `63.2%`, `<0.01%`. Diff wraps both in a sign (U+2212
  in the page; exact zero renders empty, not `+0`).
- **No decorative borders.** The only drawn lines are drag targets (`.bar`,
  `.split`), invisible until hover/active. Everything else is separated by
  background shading (`--panel`/`--bg`/`--bg-alt`/`--nav`).
- Column widths: exact `ch` counts; the header label is every column's floor —
  **no column is ever narrower than its own title**, not at rest, after a drag,
  or after a fill. One rule in two places, `colWidths()` (heat map JS) and
  `table_render()` (theme.py) — keep them in step. Widths are **never
  persisted**; reload resets.
- `fill` tables end with the right edge at the same inset from the scrolling
  pane as the left edge — `fillTable()` measures it live against `scrollerOf()`
  (never `window.innerWidth`). The `grow` column's runtime minimum is its
  **title** alone, so it squeezes before a pane scrolls sideways. `fillTable()`
  bails on a table with no layout (`offsetWidth` 0) — under `display:none`
  everything reads 0 and the grow column would be fitted to `0px`; `show()`
  calls `Theme.relayout(home)` on return to fix what changed while hidden.
- Heat map's two home tables are plain (non-`fill`), sized to content, so a
  long header can't stretch a heat-colored cell into a wide bar.
- A `<select>` whose option text varies with page state gets a fixed `ch` width
  at populate time so picking an option doesn't reflow siblings.
- Scrollbars: square, unrounded `--blue` thumb, 14px, no arrows, no hover
  state; track = the pane's own `--bg` (`pre.logbox` uses `--panel`).
- `theme.TITLE_COLUMNS` must stay ≥ the widest title any page can show (longest
  `TESTS_C` name + longest view label + diff suffix) — `flex-wrap: nowrap`
  means too small clips mid-word on exactly the pair nobody opens.

### Frames and URL state

Pages nest two deep: overview frames a test summary, which frames its heat map
/ flame graph. Both levels run the same `FRAME_JS`, deciding by
`framed = window.parent !== window`.

- Title badge printed only by the outermost strip (framed levels write `""` but
  keep the element, so the `--title-bg` block reads continuous and links line
  up). `document.title` is set at every level.
- Util block (`reset columns | help | curl.se/perf`) lives on the lowest strip
  that has one.
- "reset columns" walks the whole nest via `theme:reset-cols`, and also resets
  `Theme.splitter` panes back to authored width.
- **URL is the whole state.** Frame: `#<view>[/<inner hash>]`. Heat map:
  `f=<file>`, `f=<file>&l=<n>` (popup), `fn=<name>`, none = home, `&e=<event>`
  always spelled out when >1 event. Every click is `location.hash =` (one
  history entry each); `route()` renders, then canonicalizes via `replaceState`
  and posts up. Nothing is remembered outside the URL except
  `heat.scale`/`heat.sort` in localStorage.
- `FRAME_JS` loads a page with
  `view.contentWindow.location.replace(href + (sub || "#"))` — **never
  `iframe.src`**, which adds a history entry per load and desyncs back. `"#"`
  not `""`: a fragment-less URL is a document reload.
- Four postMessages, all source-checked. Inward: `theme:reset-cols`,
  `theme:title?`. Outward: `{theme:"hash"}` (posted by the heat map *and* by a
  framed `FRAME_JS`'s own `sync()`, so a middle level relays its full hash up —
  without it the outer hash freezes at `#<test>`), `{theme:"title"}`.
- Regression test for URL-as-state: click test → view → file → line → event,
  the outer hash must end `#<test>/heat-map/f=<file>&l=<n>&e=<ev>`, and loading
  that URL back must reproduce all three levels' hashes.
- Outer frame page never scrolls itself — `overflow: hidden` on
  `html:has(body.frame)` and `body.frame` (a real non-overlay scrollbar's
  sub-pixel gap doesn't repro headless).

### Heat map internals (gotchas)

- Source table columns: `<event>`, `line`, `source`, `calls`, D1m, DLm, Bcm.
  **No row-wide heat** — each cell carries its own, so no cell's text is
  contrast-colored against another cell's background.
- `EVS`/`EXTRA` list every event the profile *can* produce, **not** filtered by
  whether the total is zero — the dropdown and columns stay layout-stable
  across profiles/diffs. An all-zero column renders blank, no heat, no `NaN`.
  Totals guard `|| 1`.
- `.fhead`, `.chips` and `.tbl-cols` sit in one `.srcwrap`
  (`width: max-content; min-width: 100%`) so the wrapper equals the sideways
  scroll range. Bands/chips need `contain: inline-size` or their unwrapped
  single-line width sets max-content. **Order gotcha:** `minimapBuild()` runs
  *before* `Theme.init()` — it narrows the pane by 110px and the fill measures
  it as-is at that moment.
- `centerRow()` (vertical only) replaces `scrollIntoView`, which also pulled
  the pane sideways.
- The source view is **80 columns** — `SRC_COLS`=80 is the `source` column's
  `ch` width, the standard width for rendering C. It is not the `dev/` source
  limit (79) and must never be changed to match it.
- Minimap: `#minimap` is never resized and never scrolls; scale pinned to
  `MM_MIN_COLS`=80 (the same 80-column view), never widened to the longest
  line. Clone needs `width: 100%`
  - `table-layout: fixed`. `mmCloneH` readable only after `empty` is removed
    (display:none measures 0). `mmGeom()` caches nothing. Only the `th` cells
    are sticky, the `<thead>` scrolls away — **never measure the thead**.
    `minimapSync()` also runs after a popup opens/closes.
- Popup "copy" builds a plain-text twin in parallel with the HTML
  (`tableText()` off the same `cols`/`rows`), never scraped `textContent`. **JS
  in a Python triple-quoted string needs `\n` written `\\n`** or the generated
  `<script>` breaks — `node --check` after touching it.
- The popup opens with a `metric | share | amount` stats table
  (`heat.detail.stats`), not a sentence: one row for self (`line self` when the
  line isn't a function entry), `calls` + `call count` rows only when the line
  has call cost, then one row per `EXTRA` event with a non-zero value. Zero
  rows are dropped, so the table's height varies. `num()`/`numCalls()` cells
  keep the exact value in the tooltip; `tableText()` turns the same
  `cols`/`rows` into the copied markdown.
- The tree's cold-file expander is labelled just `no samples` — no count, no
  event name.
- Clickable-row hover cue is an underline on `td.ln`: an inline heat `color`
  beats any stylesheet color, so a `--link` recolor can't show on heated lines.

## Checking pages in a browser (no browser in WSL2)

```sh
CHROME="/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
SHOT="\\\\wsl.localhost\\$WSL_DISTRO_NAME\\tmp\\x.png"
PAGE="file://wsl.localhost/$WSL_DISTRO_NAME/home/t/curl/dev"
"$CHROME" --headless=new --disable-gpu --window-size=1366,768 \
  --screenshot="$SHOT" \
  "$PAGE/perf2html_baseline_report/index.html#heat-map"
```

`--dump-dom` instead for post-script DOM (append a probe `<script>` running on
`load`, after `theme.js` init). For the frame page, copy `index.html` to
`probe.html` beside it with an appended script that sets `location.hash`,
awaits the canonical hash and writes a `<pre>`; run with
`--dump-dom --virtual-time-budget=30000`. Cross-origin `file://` frames are
opaque **unless** `--allow-file-access-from-files` is passed — which is what
lets one probe click through all three levels. **jsdom is not installed on this
box** (no global or repo `node_modules`), and it can't do `location.replace`
across documents or layout anyway — Chrome for anything geometric.

## Measurement facts (2026-09-19)

- Callgrind cannot give per-call stacks or time: `calls=` lines are aggregated
  (caller, callee) totals. `--read-inline-info=yes` changes nothing observable.
  `--separate-callers=N` is exact but still aggregated and orderless — **never
  feed such a file to the summary/heat map**, functions come out named by full
  chain.
- Whole-build `-finstrument-functions` + `cyg_callback.c`: one top-level
  library call is 2–184 events depending on the test; 0 enter/exit
  mismatches in all 8 tests.
  Perturbation native → traced, one run: 152 → 154 ns/call at 2 events/call,
  304 → 746 at 184. The box's native speed itself moves ~1.9× with host state,
  so only compare numbers from one run. Hook cost is inside every traced
  duration → **flame graph is for shape and outliers, perf log for speed.**
- `rdtsc` steps by 20 ticks = 10.02 ns here, so every flame-graph duration is a
  multiple of ~10 ns. The 28→11 instruction hook saving is verified in
  disassembly only — it's below the clock's step.
- speedscope evented JSON ≈ 38 B/event: 200 KB ≈ 5,000 events.
- TSC: `constant_tsc nonstop_tsc rdtscp tsc_reliable`; measured 1.9962 tsc/ns.
- `perf stat -e cycles:u,instructions:u` works in this WSL2 (kernel 6.18
  exposes the CPU PMU). `perf record` works but samples.
- uftrace is not installed (needs sudo); a `dpkg -x` copy hung in
  `uftrace record`. It would cost more per call than the rdtsc hook.

## Current state

No `lib/` change has come out of the profiling yet. Per-test numbers live in
the reports (overview: native time, cycles, instructions), not here.

## Workflow

1. Quick read: `./build/tests/perf/perf <test>`, median of 3–5 — but **real
   numbers only from the pinned RelWithDebInfo build**.
1. Profile via `dev/perf2html.sh` on the RelWithDebInfo tree only.
1. One focused change, rebuild, re-run.
1. `dev/perf2html.sh --report=perf2html_modified_report` then
   `dev/perf2html_diff.sh`. Keep only changes that measurably help **and**
   leave everything else the test prints (counts, error totals) unchanged.
1. Record before/after numbers in "Current state" as you go.
1. Before calling anything final: full suite (`tests/runtests.pl`, or `ctest`
   from `build/` with `-DBUILD_TESTING=ON`) — the perf test doesn't validate
   correctness.
