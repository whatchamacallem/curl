# curl perf work

## Rules

1. Keep this file current in the same change as any
   tooling/layout/theme/findings change. `CLAUDE.md` is a symlink to
   `dev/DECLAUDE.md`. Compact style: facts, commands, numbers, gotchas. No line
   numbers (they rot) - name a function/identifier.
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
   trial only - never single it out.)
1. Don't use the word "meta". that is a "header" or a "manifest".
1. On any run where more than one goal was given conclude with a checklist of
   what was and was not accomplished. Also include any relevant bug reports.

## Commands

```sh
dev/perf2html.sh [--verbose] [--keep-raw] [--regenerate] [--report=DIR]
    [cmake_flags...]
dev/perf2html_diff.sh [--verbose] [--keep-raw] [--regenerate]
    [baseline-dir] [modified-dir] [report-dir]
dev/perf2html_batch.sh [--verbose] [--keep] [--keep-raw] [--regenerate]
    [cmake_flags...]
dev/scripts/reformat.sh [--check] [--verbose] [report-dir]
```

**Verification is two runs, in this order:** `dev/perf2html_batch.sh` measures
and generates, then `dev/scripts/reformat.sh` lints, formats and validates what
it produced. The batch runs no checks at all. Anything that verifies a build
has to invoke **both**.

**Iterating on generators: `dev/perf2html_batch.sh --regenerate`** - rebuilds
all three reports' pages from their last run's raw data. Seconds, not ~2.5min.
Needs `dev/temporary_artifacts/` to still exist, i.e. the recording run used
`--keep-raw`. Re-measure only when the measured thing changed (`lib/` edit,
different flags, new test).

Build (plain tree, debugging only):

```sh
cmake -S . -B build -G Ninja -DCURL_USE_LIBPSL=OFF
cmake --build build --target perf      # EXCLUDE_FROM_ALL, must be named
```

`CURL_USE_LIBPSL=OFF` is the only intentional deviation (libpsl-dev absent).
Never profile `./build` (`-O0`: inlining differs, attribution wrong) - use
`build-relwithdebinfo`. Always pin: WSL2 noise is ~106% unpinned, \<1-3%
pinned.

```sh
taskset -c 3 ./build-relwithdebinfo/tests/perf/perf <test> [loops]
```

## How the four scripts fit together

- `perf2html.sh` - builds + profiles + generates one report. Default DIR
  `perf2html_baseline_report`, or `perf2html_modified_report` when any
  cmake_flags are given (after a _source_-only change, pass
  `--report=perf2html_modified_report` yourself). cwd-independent (cd's to
  `dev/`); relative DIR is under `dev/`. Last line printed is the `file://`
  URL. `toolchain_check` is the **only** toolchain check the user-facing
  scripts have (the batch reaches it by calling this script; the diff only
  probes `python3` inline). It collects **every** missing tool before exiting
  1, printing one `tool -> official install command` line each from
  `install_hint`: `sudo apt install` for what Ubuntu ships (`cmake`,
  `ninja-build`, `ccache`, `build-essential` for `cc`, `valgrind`,
  `linux-tools-generic` for `perf`, `binutils` for `addr2line`/`readelf`) and
  the project's own command for what it does not (`npm install -g speedscope`).
  **Official instructions only** - no PPAs, no hand-rolled recipes. A missing
  `perf` also prints a WSL2 note: `linux-tools-generic` is built against an
  Ubuntu kernel WSL does not run, so `linux-perf` is the kernel-independent
  build. Tools a desktop Ubuntu already has are deliberately hint-free beyond
  the default `apt` line - `taskset` (util-linux), `python3`, and
  `git`/`lscpu`/`awk`/`sed`/`find`, which aren't probed at all. `reformat.sh`'s
  tools (pyright, ruff, prettier, shfmt, clang-format, node) are **out of
  scope** here: `dev/*.sh` is for tool users, `reformat.sh` for tool
  development.
- `perf2html_diff.sh` - measures nothing; subtracts two reports' own `raw/`
  data.
- `perf2html_batch.sh` - measures and generates, and runs **no** checks. Three
  steps: 1 baseline, 2 modified (default `-D CMAKE_C_FLAGS=-Os`), 3 diff. Every
  step runs even after a failure; exit 1 names the failed ones. **Quiet mode
  prints whole lines only**, each one an `[N.NNs]`-prefixed entry in a single
  timeline: the flags line, `running step 1 baseline: <cmd>` _before_ a call
  that can take minutes, `done: step 1 baseline in 1m23s` after it, the
  `removing ...` lines, and the closing `file://` URL. A step's duration rides
  in its own `done:` line, so no stat depends on a half-written line - nothing
  is ever left unterminated, because an unflushed partial line can sit
  unforwarded for minutes. `--verbose` is unchanged: `== N name: cmd ==`
  banners with a matching `done in`/`FAILED` banner, no `[Ns]` prefix, the
  child's own output in between.
- `scripts/reformat.sh` - **the one hook that verifies `dev/` and its output.**
  Lint, then format, then validate, every stage running even after an earlier
  one failed. **It takes no path argument**: the directories are fixed by
  convention, `..` (dev/ itself) for `*.sh`/`*.c`/`*.h`/`*.md` and `.`
  (scripts/) for everything else, and the header carries an ASCII table of
  which tool runs over which kind. Lint is pyright (**0 errors**) + ruff +
  `prettier`. Its one optional argument is a report dir; a relative one
  resolves against the caller's cwd, not `scripts/`. Validation is
  `validate_report.py` over that report, else over whichever of the three
  defaults exist. A directory is a report by holding a `MANIFEST.txt` whose
  line 1 is `curl/perf2html.sh v1` or `curl/perf2html_diff.sh v1`; that line
  also decides `--diff`. Anything else is an **error naming the version string
  it expected** - a missing directory, a missing `MANIFEST.txt`, a foreign
  version string, or no argument with the default `perf2html_baseline_report`
  absent.

Key behaviors worth knowing before touching them:

- `--keep-raw` keeps `dev/temporary_artifacts/`; otherwise it's deleted at
  startup. **The batch owns every `dev/temporary_artifacts/` deletion** - it
  passes `--keep-raw` down so a child can't unlink the batch log mid-run, and
  deletes after step 3. A failed flagless batch _keeps_
  `dev/temporary_artifacts/` (the step logs are the evidence).
- `--regenerate` implies `--keep-raw`, and in the batch also `--keep`. It reads
  `stamp=` back from the report's own `MANIFEST.txt` and rebuilds
  byte-identically when no generator changed.
- **`reformat.sh` is the only `validate_report.py`, `pyright`, `ruff` and
  `prettier` call anywhere.** Don't add a lint or validate step to a generator
  or to the batch. Validation reads the report dirs only, never
  `dev/temporary_artifacts/`, so the batch deleting `temporary_artifacts/` on a
  clean flagless run doesn't affect it.
- **The batch plus `reformat.sh` is the generators' test suite** - driving them
  over all three output dirs is the coverage. Don't grow a per-generator check.
- Profiling:
  `taskset -c 3 valgrind --tool=callgrind --cache-sim=yes --branch-sim=yes`.
  Timing is a _separate_ native pinned
  `perf stat -x, -e cycles:u,instructions:u` run - its `Time*` lines are the
  only valid speed number; callgrind's wall clock never is.
- Trace tree `build-instr` = same flags + `-finstrument-functions` +
  `dev/cyg_callback.c` linked in. Whole build instrumented, no file list.
- No env vars; constants live at the top of each shell script (`CPU=3`,
  `LOOPS_DIVISOR=50`, `SKIP_ALL`, `MANIFEST_VERSION`). `TESTS` comes from
  `tests/perf/Makefile.inc`; loops from `loops_of` grepping the test source.
- Valgrind's LL cache auto-detects as direct-mapped and overstates conflict
  misses - `--LL=16777216,16,64` is on the `valgrind` line in `run_one`.
- Quiet mode logs to `dev/temporary_artifacts/*.log`; a failing step prints its
  last 40 lines, under an `[N.NNs] FAILED: step N name, exit C, after 12s` line
  on stderr.
- The batch's `[N.NNs]` clock is elapsed time since `main()` started, from the
  `EPOCHREALTIME` builtin - `SECONDS` is integer-only, and a builtin keeps the
  script free of the toolchain check it doesn't have. `now_us()` strips every
  non-digit, so the locale's decimal separator can't corrupt the arithmetic;
  `took()` still renders a step's own duration as `1m23s`/`12s`.

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
  no preamble at all - strip straight to the table.
- `MANIFEST.txt` line 1 is the _only_ thing that makes a directory a diff input
  (`head -1`; a diff's own version string names `perf2html_diff.sh`, so diffs
  can't be diffed). Written by `run_all` after every test, so an aborted run
  leaves none.
- **Every path written to a page or manifest is relative** - `path_display()` /
  `$REPO` stripping. `validate_report.py`'s `home_dir_check` walks every file
  and fails on the author's `$HOME`: a report must be copyable off-box.

**Generated pages are deterministic** - same input ⇒ byte-identical output, so
a page diff is always code, never sampling. Only `MANIFEST.txt`'s `stamp=` and
genuinely re-measured time (`perf-tool/output.txt`, `flame-graph/output.txt`,
the trace) vary. Verify by running a generator twice on one input and `cmp`.

Raw data in `dev/temporary_artifacts/` (gitignored):
`callgrind.out.<test>.<loops>.<ts>`, `valgrind.<test>.<loops>.<ts>.log`,
`trace.<test>.<loops>.<ts>.bin` (+`.maps`), `.speedscope.json`,
`perf-stat.<test>.<ts>.csv`, `profile.<ts>.log`.

## Diff semantics

- Every number is **MODIFIED - BASELINE, per (function, file, line)** - never
  per (file, line) alone, which hands half an inlined function's cost to its
  neighbour.
- The delta is a plain callgrind-format file with **no `calls=` lines** → no
  call graph → no call columns/caller tables in the heat map
  (`HAS_CALL_GRAPH`). The summary's calls/callers columns come from the
  **synthesized callers diff**, a separate JSON file written beside the delta
  (`callgrind_diff.py --callers-output`, consumed via
  `build_report.py test --diff --callers-data`).
- **Every share divides by that same thing's own baseline cost**, never by a
  global budget: a function by its baseline self, a line by its baseline cost,
  a file/dir by its summed baseline, the overview by that test's baseline
  total. `(new - old)/old`, so 1→0 is -100%, 100→90 is -10%, 90→100 is +11.1%,
  1→1 is 0% (rendered empty). Something the baseline never had is **+100%**.
  Baselines ride in the synthesized callers diff (`baseline`, keyed by `<fn>`
  and `<fn>\n<display path>\n<line>`, `baselineTotal`, `baselineCalls`,
  `events`); the heat map reads it via `--baseline-data`. **`events` names the
  derived events too** - recorded slots keep the indices they always had and
  `costs_emit()` appends one slot per derived event to every vector it writes,
  so `events.index("CEst")` resolves like any other and the diff is no longer
  pinned to a recorded event. The heat map ignores the appended slots: its JS
  resolves a derived event from the recorded ones itself. Ranking and heat are
  `abs()`, so winners and losers interleave.
- **Per-line baselines are wildly skewed** - median line is ~18 Ir and 72% are
  under 1,000, so a line that cost 1 and moved 200K reads 20,360,300%. Only
  ~1.8% of lines exceed ±1000%, but a max-based colour scale is set by exactly
  those. In a diff the `FULL_HEAT_PERCENT` clamp handles it (a diff has no
  per-function scope); in a non-diff report that is what `log, per function` is
  for.
- `profile_magnitudes()` (Σ|per-function line delta|) still exists and is what
  `heatMapTotals.totals` carries, but it is no longer what shares divide by.
- `summary:` in the delta = the signed total, so the parser's 1.0000 self-check
  holds on it too.

**Core vs diff code.** The non-diff path stays byte-checkable against an older
generator. Keep the split: `BuildReport.test`/`.functions_table` core vs
`.diff_test`/`.diff_functions_table`; `CallgrindToHeatmap.model()` core vs
`.diff_model()`; in heat-map JS every diff override sits in the one
`if (IS_DIFF) {...}` block; `validate_report.py` is data-driven by
`ValidateReport.ReportLayout` (`_LAYOUT_FULL`/`_LAYOUT_DIFF`).

## `dev/scripts/` conventions

**79 columns is the hard max** for every line of `dev/` source - code and
comment alike, in every language. `scripts/reformat.sh` enforces it, and a line
still over 79 after the formatters run is an **error**, not a note:
`long_lines_report` prints `file:line`, the width and the whole line, and the
script exits 1. It scans `.sh`, `.c`, `.h`, `.md` under `dev/` and `.py`,
`.js`, `.css`, `.html` under `scripts/`. The formatters cannot reach some of
those lines - `echo` text in a shell script, a fenced block in `.md`, and a
template literal too long to fit, which `prettier` will not break - so those
few are split by hand. Whole tree is at 0.

**`dev/` source is ASCII plus a short allow list.** `validate_report.py`'s
`unicode_check` walks every `.py`/`.js`/`.css`/`.sh`/`.html`/`.c`/`.h` and
`README.md` under `dev/` and fails on any character outside `_NON_ASCII_RE`,
which is ASCII plus `_ALLOWED_UNICODE`: `≈`, `▲`, `▶`, `▼`, `…`. Those are the
diff vocabulary plus the heat map tree's carets, and they are **written
literally** - not `▼`, not a `▼` escape, and not an HTML entity. An entity
would be double-escaped into visible text by the JS `html_escape()` and by
`theme.py`'s `html_escape()` (both escape `&`), and its length would corrupt
the `text.length` column-width math. Adding a character to the page's
vocabulary means adding it to `_ALLOWED_UNICODE` with a `#` comment naming it.
`DECLAUDE.md` is not scanned, and neither is any `.json` - `reformat.sh`'s
table pairs `*.md` with `*.json` only because `prettier` handles both.

Reformatting any of `scripts/heatmap.html`, `heatmap.js`, `heatmap.css`,
`frame.js`, `flame_bootstrap.js`, `theme.css` or `theme.js` changes every
generated page (they are all inlined into each one), so a page diff after such
an edit is expected; `perf2html_batch.sh --regenerate` then a diff against a
snapshot is how you check that only the inlined `<style>`/`<script>` moved.
Text a script `echo`s into `perf-tool/output.txt` is _page content_, so
rewrapping it does change the report - split it into extra `#` lines rather
than letting it overflow.

Not to be confused with the **80-column source _view_** in the heat map
(`SOURCE_WIDTH`, `MINIMUM_COLUMNS`), which is the standard width the profiled
`lib/` source is rendered at - that stays 80 and has nothing to do with how
`dev/` is written.

**Comments: short, tech-writer style, never docstrings.** Every class and
function gets one `# <Name> - what it is` line above it, wrapped to a second
`#` line if it must be. Every field gets a one-line `#` comment **above it**,
never trailing - no arg-by-arg docs, no `:param:`, no reStructuredText. Names
carry the meaning; the comment only says what a name can't. Still no comments
in any of the `scripts/` page assets - the `.js`, `.css` and `.html` files.
Shebangs stay. `ArgumentParser()` gets no description by design.

**Class names read like a how-to, not an abbreviation** - `CompressedNames`,
`PositionDecoder`, `FileTally`, `ExecutableMapping`, `TraceRecording`,
`ReportLayout`. A name needing a comment to be legible is the wrong name.

**Naming:** `object_method` lowercase C-identifier form (`args_parse`,
`profile_parse`, `report_test`) for shell functions and public free functions;
a method drops the prefix its class supplies (`Callgrind.parse`,
`BuildReport.report_page`). Entry point is always `main()`, directly above
`if __name__ == "__main__":`.

**File shape:** constants → classes → public free functions → `main()`. One
enclosing class per script, named after it in PascalCase, holding **every**
non-exported function - no free helpers, no nested `def`s. A second class only
when it carries its own state. Classes alphabetical within two bands (record
types, then logic classes); methods alphabetical. Public free functions are
one-line delegations (`profile_load(paths)` → `Callgrind().load(paths)`) so
callers never name a class.

**Constants are alphabetical ignoring the leading `_`** - so `BODY` sorts
before `_CSS`, `_EVENT_LONG` before `REPO_ROOT`. The _only_ constants allowed
below the classes are the ones that can't be evaluated above them: a constant
whose value names a class in the same file (`_DERIVED_DEFAULTS`,
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
pipx/uv). Pylance is not usable - LSP only, ignores argv.

### The scripts

- `callgrind.py` - the one parser. `profile_load(path)` exits unless the
  self-check ratio (stderr) is exactly **1.0000** - re-verify after touching
  it. It is cost conservation only, and says nothing about whether emitted
  structure was observed (rule 3). `REPO_ROOT` +
  `path_norm() -> PathInfo(display, local, group)` are the one path resolver
  every generator uses - no `--repo-root` flag exists. Functions keyed by
  **name**, so a symbol in two objects is one function. Derived events when
  inputs exist: `D1m`, `DLm`, `L1m`, `LLm`, `Bm`, `CEst` (= Ir + 10·L1m +
  100·LLm). `Profile.function_lines[fn][SourceLine]` is the only per-context
  table. `function_entry` for an uncalled function = the **first** cost line
  callgrind wrote in its home file (matched 505/505; lowest line number does
  not - inlined helpers sit above the entry).
- `build_report.py test|overview` - summary and overview pages. `_TOP = 50`.
  **One event constant, `_EVENT = "CEst"`, for every table on both sides of the
  core/diff split** - the non-diff summary's "top 50 functions by self", every
  diff path and the diff overview alike. It may name a recorded or a derived
  event, and can be pointed at any event `callgrind.py` knows with no other
  edit. `event_of()` resolves it per profile - `_EVENT` when
  `Profile.event_names()` carries it, else that profile's first recorded
  event - because `Profile.value()` **raises `KeyError`** on an event a profile
  can't supply; the resolved name is a local that both the column label and the
  ranking key read. There is **no second named fallback**. The numerator was
  never the obstacle (CEst is linear, so
  `CEst(mod-base) == CEst(mod)-CEst(base)`, verified); the **denominator** was,
  and the synthesized callers diff now gives a derived event its own slot, so
  `callers_data_load()`/`baseline_total_load()` find one by `events.index(...)`
  exactly like a recorded event. `--perf-log`/`--trace-log`/`--raw-data` each
  render a section only when given; the flame-graph strip link exists only with
  `--trace-log`. `--diff` picks `diff_test` in `main()`. The LABEL=VALUE rows
  above a page's content are `ManifestRow`/`ManifestBlock` (methods
  `manifest_*`) - not the heat map's `HeatMapTotals`, and not a table's
  column-title row (`theme.table_render(column_titles=...)`). **Never call any
  of them just "header".** Its `FRAME_JS` is `theme.theme_asset("frame.js")`.
- `callgrind_diff.py` - the subtraction; also home of `profile_magnitudes()`,
  which generators import. Its own `_EVENT` is `CEst`, the same one knob, and
  `event_of()` drops to the first recorded event when a side can't supply it.
  `--callers-output` is required, and writes the **synthesized callers diff**
  (`CallersDoc`), carrying the baselines every diff share divides by; every
  vector it writes goes through `costs_emit()`, which pads to the recorded
  width, appends one slot per derived event in `events_all()` order and only
  then trims trailing zeros - so a slot's index never moves and a short vector
  still means zeros. `perf2html_diff.sh` copies it into the report's `raw/` as
  `<delta>.callers.json` so the overview can reach it; `validate_report.py`
  skips it in `raw_dir_check` (`_CALLERS_SUFFIX`). The file name, the flags and
  the JSON keys are contract - only the prose and the Python names say
  "synthesized callers diff": `CallgrindToHeatmap`'s `SynthesizedCallers` +
  `synthesized_callers_load()` read it, `BuildReport.CallersData` +
  `callers_data_load()` read it back whole.
- `callgrind_to_heatmap.py` - `_DEFAULT_EVENT = "CEst"`, `_TREE` = dirs whose
  tracked `.c/.h` are listed even without samples. Its `BODY`, `_CSS` and
  `_HEAT_MAP_JS` are `theme.theme_asset()` of `heatmap.html`, `heatmap.css` and
  `heatmap.js`. `render()` substitutes `__THEME_JS__` and `__HEATMAP_JS__`
  **before** `__DATA__`: the two scripts are our own files and carry no marker,
  while `__DATA__` is profiled source text, so it is the one replacement whose
  result must never be scanned again.
- **No generator holds a multi-line HTML/CSS/JS literal any more.** Each one is
  a real file in `scripts/`, read at import through `theme.theme_asset()` -
  `Theme.asset_read()` exposed as a free function, the same door
  `theme.css`/`theme.js` come through. The files and their holders:
  `heatmap.html` → `callgrind_to_heatmap.BODY`, `heatmap.css` →
  `callgrind_to_heatmap._CSS`, `heatmap.js` →
  `callgrind_to_heatmap._HEAT_MAP_JS`, `frame.js` → `build_report.FRAME_JS`,
  `flame_bootstrap.js` → `build_flame_graph._BOOTSTRAP`. Being off the Python
  side, **their JS is written plainly** - `\n` is `\n`, not `\\n`; that gotcha
  is gone from `dev/` entirely. They keep their coverage: `prettier` formats
  and parses each file on disk, which is the same string the holder reads, and
  the 79-column and ASCII scans run over all of them. Holder names are now
  free - nothing looks a constant up by name any more.
- `flame_bootstrap.js` keeps its `__NAME__`/`__DATA__` markers, which
  `build_flame_graph.py` substitutes at generate time; they are bare
  identifiers, so `node --check` accepts the file as written.
- `dev/cyg_callback.c` - the recorder. Hot path is
  `if(next < end) { next->fn = fn; next->tsc = rdtsc | flag; ++next; }` - 11/12
  instructions (check with
  `cc -O2 -fcf-protection=none -S -masm=intel dev/cyg_callback.c`). `next` must
  stay a pointer, `end` a variable. `next == end` = not sampling; everything
  else lives on that cold path. Setup is a constructor (incl. `memset` of the
  buffer, so no page fault lands in a timed call; the buffer holds
  `CYG_CALLBACKS_MAX_REC`=327680 records, 5MB static, and no test fills it),
  teardown a destructor writing `CYG_OUT` + `.maps`. Its header comment is the
  format reference. Single-threaded.
- `trace_to_speedscope.py` - pairs enters/exits (mismatch = non-zero exit),
  takes the busiest run's first `_MAX_CALLS`=200 complete calls and writes
  them, with no byte budget - one `json.dumps`, and `frames` symbolizes only
  what is written. 200 is hard-coded for the current `TESTS_C`, whose recorded
  call counts run 79–202 for seven of the eight; the eighth records 3,180 cheap
  calls. So the cut lands right on the top of that range - a test at 202 loses
  its last two calls, and anything at or under 200 emits its whole trace. The
  numbers below the constant were measured at 512 and have not been re-measured
  since: spans ran 0.10–0.69ms and documents up to ~2MB, both of which 200 can
  only shrink. **Re-measure before trusting either.** Retune the constant if a
  test's shape changes. `at` is raw (hook cost included). Must run while
  `build-instr` still holds the traced binary (symbolization reads it). GCC
  instruments inlined bodies, so inlined helpers are frames.
- `validate_report.py OUTDIR [--diff]` - structural smoke test only;
  `flame_graph_check` requires exactly one `evented` profile whose `exporter`
  is `_FLAME_EXPORTER`, so a synthesized or stale flame graph fails. **It greps
  generated pages for three JS names**, so those three are contract, not
  private: `loadFileFromBase64` (speedscope's own API),
  `var document_base64 = "..."` (the regex `flame_graph_check` pulls the base64
  profile out of `flame_bootstrap.js` with) and `report_ui.layout_activate`
  (`heat_map_check`'s proof the heat map carries its runtime). Rename one of
  those in the JS and every page fails validation while looking perfectly
  correct in a browser - change both sides together.
- `prettier` - formats **and** lints JS, CSS, HTML, Markdown, JSON and YAML,
  replacing the former `check_js.py`/`check_html.py` and `mdformat`. It
  reparses what it writes, so a syntax error or an unbalanced `</div>` fails
  the run instead of shipping into every generated page; both cases are
  reported as `[error] <file>: SyntaxError` with a line/column. Config is
  `dev/.prettierrc.json` (`printWidth` 79, `proseWrap: always` - that last one
  is what keeps markdown wrapped the way `mdformat --wrap` did; without it
  prose is left on one line). A new `.js`/`.css`/`.html`/`.md` under the two
  scanned dirs is picked up with no list to edit. Install:
  `npm install -g prettier` (lands in `~/.npm-global/bin`, which `tool_find`
  now searches alongside `~/.local/bin`).

## Why the heat map exists

Under `-O2` small static functions inline into their callers, so the
function-level top-N table charges their cost to the caller. The heat map shows
it per source line; the flame graph shows inlined bodies as own frames.
Cross-check:

```sh
callgrind_annotate --show-percs=yes \
  dev/temporary_artifacts/callgrind.out.<test>.<loops>.<ts> <file>
```

`/* perf #N: X.XX% */` comments in `lib/` are stale dev annotations - drop
before submitting upstream.

## Look and feel

One dark theme, Monaco/monospace everywhere. Target viewport **1366×768** -
pages must not assume more.

- `theme.py`'s `_COLOR_PAIR` values are raw "User settings" THEME entries, odd
  index = dark member; `--<name>-l` is light. Exception: `--bg` is the slate
  dark member darkened 8% via `Theme.shade()` - page background, scrollbar
  track, minimap band and heat blend all follow it, so change it only there.
  The `_HEAT` ramp is exempt from the pair rule.
- Heat = 12-stop `_HEAT` blended over `--bg`, alpha on log scale of magnitude,
  text color by resulting luminance. **The scale dropdown is a curve × scope
  product, built at runtime** - `SCALE_CHOICES` from `{log, linear}` ×
  `SCOPE_CHOICES`, and `scale` is the chosen entry (`.curve`, `.scope`,
  `.value`), never a bare string. `heat_of_share()` reads `.curve`;
  `max_share`/`max_share_for_line()` read `.scope`. Non-diff `SCOPE_CHOICES` is
  all three, so the dropdown carries **all six** permutations: `global`
  (`maximum_share`, every line of every file), `per file`, `per function` (each
  line against the hottest line of the function that owns it -
  `max_share_for_line()`; what keeps one blown-up line from flattening a whole
  file). **A diff has exactly one scope, `per line`**, so its dropdown is just
  `log`/`linear` with no scope suffix: a diff share already divides by that
  line's own baseline, so there is no global, file or function delta to scale
  against and `max_share` is simply `FULL_HEAT_PERCENT`. Because `file` and
  `function` scope can no longer be reached in a diff, both `max_share` arms
  use plain `share_of_total()` - no `IS_DIFF ? share_of_baseline(...)` branch,
  and no per-file percentage max. An unknown stored `heat.scale` falls back to
  `SCALE_CHOICES[0]`, which is how old values survive. Non-diff indexes `0..1`;
  **diff indexes signed `-1..1` across the ramp** (savings → cold/blue,
  regressions → hot/red, 0 at midpoint) via `heat_style(signed=True)` / the JS
  `if (IS_DIFF)` branch. **A diff clamps both the share and `max_share` to
  100%** (`_FULL_HEAT_PCT` / `FULL_HEAT_PERCENT`, applied in
  `BuildReport.diff_heat` and in `heat_of_share`), so a change the size of the
  thing's own baseline is already fully lit and the 1.8% of lines reading
  millions of percent can't set a scale nothing else registers on:
  `c(100%) == c(10000000%)`, `c(90%) != c(10000000%)`. Non-diff is untouched -
  `heat_of_cost()`/`heat_of_share()` clamp nothing without `IS_DIFF`.
- Call counts are their own event, heat-colored by share of all recorded calls,
  log-scaled, event-independent.
- Numbers: `num_human()`/`human_text()` → `2.1K`/`2.0G`;
  `num_pct()`/`share_text()` → `63.2%`, `<0.01%`. Exact zero renders empty. **A
  diff never prints `+`.** A share leads with an arrow and keeps a negative's
  sign, Bloomberg style - `▲11.1%` up, `▼-100.0%` down (`num_signed_pct()` /
  the JS `share_text()`); an amount carries only a minus when negative, nothing
  when positive (`num_signed()` / `human_text()`, U+2212 in the page). Under
  0.01% it is `▲≈0.00%`/`▼≈0.00%` - direction kept, size marginal. **A diff
  share past 100% switches to a multiple** - `▲1.30x` - and at or past `99.99x`
  it is just `>1000x`, deliberately approximate (`Numbers.multiple()` / the JS
  `multiple_text()`; both sides kept in step and tested on the same cases).
  `≈0.00%` and `>1000x` state a bound, not a value, so neither takes a sign.
  **A drop can't pass -100%** - `(new-old)/old` bottoms out when the cost
  reaches zero - so the multiple branch is reachable only for a rise; don't
  "fix" negative multiples, they can't occur. **There are no tooltips** - the
  rounded, arrow-signed text is all a page shows, so the exact value is not on
  the page at all. The popup's "copy" markdown carries the same rounded text,
  not the raw number.
- **No decorative borders.** The only drawn lines are drag targets (`.bar`,
  `.split`), invisible until hover/active. Everything else is separated by
  background shading (`--panel`/`--bg`/`--bg-alt`/`--nav`).
- **No tooltips.** Nothing a page renders carries a `title=` attribute -
  neither `Cell` nor `Column` has a field for one, and `table_render()` / the
  heat map's `table_html()` emit none. What a cell can't fit is simply not
  shown; widen the column or drag the bar. The only `title=` left in a
  generator is the `<iframe title="report page">` accessibility label, and
  `<title>`/`document.title`/`data-title` are the page title and the status
  row, not hover text. If a header needs explaining, that is a caption or a
  `README.md` section, never a `title=`. **A page that can only be read by
  hovering is a broken page** - that is the whole reason the attribute is gone,
  so "put it back in a `title=`" is never the fix.
- **"Reading a Diff Report" in `README.md` is where diff notation is
  explained** - the arrows, the minus-only amounts, the empty zero cell, the
  per-baseline denominator, the multiple form and `>1000x`, the signed heat
  ramp and the `abs()` ranking. It replaced the diff `self` description, which
  had been the only on-page statement of how to read a diff. The README is
  copied into every report every run and the strip's "help" link opens it, so a
  diff page reaches it in one click. Keep it in step with "Diff semantics"
  above: that section is the implementation, this one is the same rules in the
  user's words, and a change to the notation is a change to both.
- Column widths: exact `ch` counts; the header label is every column's floor -
  **no column is ever narrower than its own title**, not at rest, after a drag,
  or after a fill. One rule in two places, `column_widths()` (heat map JS) and
  `table_render()` (theme.py) - keep them in step. Widths are **never
  persisted**; reload resets.
- `fill` tables end with the right edge at the same inset from the scrolling
  pane as the left edge - `grow_column_fill()` measures it live against
  `nearest_scroller()` (never `window.innerWidth`). The `grow` column's runtime
  minimum is its **title** alone, so it squeezes before a pane scrolls
  sideways. `grow_column_fill()` bails on a table with no layout
  (`offsetWidth` 0) - under `display:none` everything reads 0 and the grow
  column would be fitted to `0px`; `view_show()` calls
  `report_ui.layout_refresh(home_panel)` on return to fix what changed while
  hidden.
- Heat map's two home tables are plain (non-`fill`), sized to content, so a
  long header can't stretch a heat-colored cell into a wide bar.
- A `<select>` whose option text varies with page state gets a fixed `ch` width
  at populate time so picking an option doesn't reflow siblings.
- Scrollbars: square, unrounded `--blue` thumb, 14px, no arrows, no hover
  state; track = the pane's own `--bg` (`pre.logbox` uses `--panel`).
- `theme.TITLE_COLUMNS` must stay ≥ the widest string a **status row** can
  show. The inner status row carries the selection path, so the budget is
  longest `TESTS_C` name + `" / "` + longest view label + diff suffix. Today
  that is `simpleformat / flame graph` = 26 and the `<test> / summary` form is
  shorter, so 33 still holds with room to spare. `flex-wrap: nowrap` means too
  small clips mid-word on exactly the pair nobody opens. Both status rows
  center their text (`justify-content: center` on `.strip .title`).

### JS naming: snake_case is ours, camelCase is theirs

Every identifier in `dev/scripts`' JavaScript that we own is `snake_case` and
unabbreviated; anything still camelCase is a name the browser or Python owns -
a DOM API member, a CSS class, a `data-*` attribute, a localStorage or URL key,
or a JSON key from `callgrind_to_heatmap.py`'s TypedDicts (`heatMapTotals`,
`lineFunction`, `defaultEvent`, `fgDark`, ...). The split is the documentation:
a camelCase name is the signal that it crosses a boundary and cannot be renamed
freely. The shared runtime global is `window.report_ui` (`layout_activate`,
`layout_refresh`, `layout_reset`, `pane_splitter.attach`,
`view_storage.value_read`/`.value_write`); `theme.py`'s `Theme` class is Python
and unrelated. The stored keys themselves are boundary names, so they keep
their dotted spelling - `heat.scale`, `heat.sort`, `split.<pane>` and
`perf2html.version`, the last holding the store version that `theme.js` sweeps
on. `flame_bootstrap.js`'s `__NAME__`/`__DATA__` and `heatmap.html`'s
`__DATA__`/`__THEME_JS__`/`__HEATMAP_JS__` are substitution markers Python
matches literally - never rename them.

### Frames and URL state

Pages nest two deep: overview frames a test summary, which frames its heat map
/ flame graph. Both levels run the same `FRAME_JS`, deciding by
`is_framed = window.parent !== window`.

- **Status rows** are the two strips' first cells, the `#title` element in the
  `--title-bg` block, `--title-w` wide and centered. The outermost one always
  reads the literal `perf2html`, whatever is selected. A framed level's status
  row reads the **selection path** instead - what the outer one used to show -
  so the second strip says which page is open. Both levels keep the element, so
  the block reads continuous and the links line up. `document.title` is still
  set at every level, from the unrendered title, which is why the outer level
  keeps taking `title_changed` even though its own status row ignores it.
- A selection path with no `" / "` in it is a summary page, so `frame.js`'s
  `selection_path()` appends `" / summary"` - `all` renders `all / summary`.
  That is a general rule about one-segment paths, not a case for one test name.
- Util block (`reset columns | help | curl.se/perf`) lives on the lowest strip
  that has one.
- "reset columns" walks the whole nest via `report_ui:reset_columns`, and also
  resets `report_ui.pane_splitter.attach` panes back to authored width.
- **URL is the whole state.** Frame: `#<view>[/<inner hash>]`. Heat map:
  `f=<file>`, `f=<file>&l=<n>` (popup), `fn=<name>`, none = home, `&e=<event>`
  always spelled out when >1 event. Every click is `location.hash =` (one
  history entry each); `route_render()` renders, then canonicalizes via
  `replaceState` and posts up. Nothing is remembered outside the URL except
  `heat.scale`/`heat.sort` and the `split.<pane>` pane widths in localStorage,
  all of them guarded by the store version below.
- **The local store is versioned.** `theme.js` holds `STORAGE_VERSION` =
  `perf2html v1` under the key `perf2html.version`, written as a bare string,
  not JSON, so it stays readable whatever the stored formats do. The first
  `view_storage.value_read`/`.value_write` in a document calls
  `storage_version_check()` once (`storage_is_checked` latches it): the stored
  version not being **exactly** the current string - absent, stale or garbage -
  sweeps every key this report owns and writes the current one, then reads
  carry on normally. **Bumping the string is how a stored-format change is
  rolled out** - change a value's shape and change `STORAGE_VERSION` in the
  same edit, and every browser drops the old data on its next page load.
- **What the sweep owns** is `STORAGE_OWNED_KEYS` (`heat.scale`, `heat.sort`)
  plus `STORAGE_OWNED_PREFIXES` (`split.`, which `pane_splitter.attach`
  generates one key per pane under). It walks `localStorage.key(i)`, so a
  generated pane key needs no list. Existing key spellings were deliberately
  **not** moved under one shared prefix: renaming them would orphan exactly the
  data the version check exists to clean, and v1 cannot sweep what it has no
  name for, since the pre-version data carries no version to match on. A new
  key must be added to one of those two constants or its data outlives every
  bump. The whole check sits inside the same `try`/`catch` the accessors use,
  so a private-mode `localStorage` that throws leaves the page working.
- `FRAME_JS` loads a page with `view_frame.contentWindow.location.replace()`,
  passing `link_href + (inner_hash || "#")` - **never `iframe.src`**, which
  adds a history entry per load and desyncs back. `"#"` not `""`: a
  fragment-less URL is a document reload.
- Four postMessages, all source-checked. Inward: `report_ui:reset_columns`,
  `report_ui:title_request`. Outward: `{report_ui:"hash_changed"}` (posted by
  the heat map _and_ by a framed `FRAME_JS`'s own `hash_canonicalize()`, so a
  middle level relays its full hash up - without it the outer hash freezes at
  `#<test>`), `{report_ui:"title_changed"}`.
- Regression test for URL-as-state: click test → view → file → line → event,
  the outer hash must end `#<test>/heat-map/f=<file>&l=<n>&e=<ev>`, and loading
  that URL back must reproduce all three levels' hashes.
- Outer frame page never scrolls itself - `overflow: hidden` on
  `html:has(body.frame)` and `body.frame` (a real non-overlay scrollbar's
  sub-pixel gap doesn't repro headless).

### Heat map internals (gotchas)

- Source table columns: `<event>`, `line`, `source`, `calls`, D1m, DLm, Bcm.
  **No row-wide heat** - each cell carries its own, so no cell's text is
  contrast-colored against another cell's background.
- `event_list`/`secondary_events` list every event the profile _can_ produce,
  **not** filtered by whether the total is zero - the dropdown and columns stay
  layout-stable across profiles/diffs. An all-zero column renders blank, no
  heat, no `NaN`. Totals guard `|| 1`.
- `.fhead`, `.chips` and `.tbl-cols` sit in one `.srcwrap`
  (`width: max-content; min-width: 100%`) so the wrapper equals the sideways
  scroll range. Bands/chips need `contain: inline-size` or their unwrapped
  single-line width sets max-content. **Order gotcha:** `minimap_build()` runs
  _before_ `report_ui.layout_activate()` - it narrows the pane by 110px and the
  fill measures it as-is at that moment.
- `row_center()` (vertical only) replaces `scrollIntoView`, which also pulled
  the pane sideways.
- The source view is **80 columns** - `SOURCE_WIDTH`=80 is the `source`
  column's `ch` width, the standard width for rendering C. It is not the `dev/`
  source limit (79) and must never be changed to match it.
- Minimap: `#minimap` is never resized and never scrolls; scale pinned to
  `MINIMUM_COLUMNS`=80 (the same 80-column view), never widened to the longest
  line. Clone needs `width: 100%`
  - `table-layout: fixed`. `clone_height_px` readable only after `empty` is
    removed (display:none measures 0). `geometry_measure()` caches nothing.
    Only the `th` cells are sticky, the `<thead>` scrolls away - **never
    measure the thead**. `minimap_sync()` also runs after a popup opens/closes.
- Popup "copy" builds a plain-text twin in parallel with the HTML
  (`table_markdown()` off the same `cols`/`rows`), never scraped `textContent`.
  It lives in `scripts/heatmap.js`, so its `\n` is written plainly; the
  double-backslash gotcha died with the last Python JS literal.
- The popup opens with a `event | global % | count` stats table
  (`heat.detail.stats`), not a sentence: one row for self (`line self` when the
  line isn't a function entry), `calls` + `call count` rows only when the line
  has call cost, then one row per `secondary_events` event with a non-zero
  value. Zero rows are dropped, so the table's height varies.
  `cell_number()`/`call_count_cell()` print the rounded value only;
  `table_markdown()` turns the same `cols`/`rows` into the copied markdown.
- The tree's cold-file expander is labelled just `no samples` - no count, no
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
opaque **unless** `--allow-file-access-from-files` is passed - which is what
lets one probe click through all three levels. **jsdom is not installed on this
box** (no global or repo `node_modules`), and it can't do `location.replace`
across documents or layout anyway - Chrome for anything geometric.

## Measurement facts (2026-09-19)

- Callgrind cannot give per-call stacks or time: `calls=` lines are aggregated
  (caller, callee) totals. `--read-inline-info=yes` changes nothing observable.
  `--separate-callers=N` is exact but still aggregated and orderless - **never
  feed such a file to the summary/heat map**, functions come out named by full
  chain.
- Whole-build `-finstrument-functions` + `cyg_callback.c`: one top-level
  library call is 2–184 events depending on the test; 0 enter/exit mismatches
  in all 8 tests. Perturbation native → traced, one run: 152 → 154 ns/call at 2
  events/call, 304 → 746 at 184. The box's native speed itself moves ~1.9× with
  host state, so only compare numbers from one run. Hook cost is inside every
  traced duration → **flame graph is for shape and outliers, perf log for
  speed.**
- `rdtsc` steps by 20 ticks = 10.02 ns here, so every flame-graph duration is a
  multiple of ~10 ns. The 28→11 instruction hook saving is verified in
  disassembly only - it's below the clock's step.
- speedscope evented JSON ≈ 38 B/event: 1 MB ≈ 26,000 events.
- TSC: `constant_tsc nonstop_tsc rdtscp tsc_reliable`; measured 1.9962 tsc/ns.
- `perf stat -e cycles:u,instructions:u` works in this WSL2 (kernel 6.18
  exposes the CPU PMU). `perf record` works but samples.
- uftrace is not installed (needs sudo); a `dpkg -x` copy hung in
  `uftrace record`. It would cost more per call than the rdtsc hook.

## Current state

No `lib/` change has come out of the profiling yet. Per-test numbers live in
the reports (overview: native time, cycles, instructions), not here.

## Workflow

1. Quick read: `./build/tests/perf/perf <test>`, median of 3–5 - but **real
   numbers only from the pinned RelWithDebInfo build**.
1. Profile via `dev/perf2html.sh` on the RelWithDebInfo tree only.
1. One focused change, rebuild, re-run.
1. `dev/perf2html.sh --report=perf2html_modified_report` then
   `dev/perf2html_diff.sh`. Keep only changes that measurably help **and**
   leave everything else the test prints (counts, error totals) unchanged.
1. Record before/after numbers in "Current state" as you go.
1. After any `dev/` edit: `dev/perf2html_batch.sh` **then**
   `dev/scripts/reformat.sh`. The batch alone checks nothing.
1. Before calling anything final: full suite (`tests/runtests.pl`, or `ctest`
   from `build/` with `-DBUILD_TESTING=ON`) - the perf test doesn't validate
   correctness.
