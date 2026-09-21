# curl perf work

## Rules

1. Keep this file current in the same change as any
   tooling/layout/theme/findings change. `CLAUDE.md` is a symlink to
   `dev/DECLAUDE.md`. Compact style: facts, commands, numbers, gotchas. No line
   numbers (they rot) - name a function/identifier. **A-list only**: a thing
   goes in if a session that had not read it would get it wrong, waste an hour,
   or break a contract. If it isn't A-list it probably won't fit. You know what
   is A-list because this file is what is in your context - judge a new fact
   against what is already here. Keep adding A-list facts as long as they are
   worth maintaining, into the section they belong to. When this file goes over
   **40,000 bytes** at the moment you are adding to it, compact it back to
   **32,000** in that same change (`wc -c`).
1. `dev/` is throwaway profiling tooling: one shared parser, one shared theme,
   no dead code, no duplicate systems. Everything a script writes must open
   from `file://` with nothing fetched at view time.
1. **No fake data.** Every value on a page is a recorded measurement or plain
   arithmetic on one (sum, difference, share, `CEst`). No apportioning,
   interpolation or "plausible" stacks. If a tool can't supply what a view
   needs (callgrind: per-call stacks/time), the view isn't built.
1. **Nothing test-specific, ever.** No test names, file lists or per-test cases
   anywhere in `dev/`; every view is built for every test in `TESTS_C`.
   Examples read `<test>`/`<file>`.
1. Don't use the word "meta". that is a "header" or a "manifest".
1. On any run where more than one goal was given conclude with a checklist of
   what was and was not accomplished. Also include any relevant bug reports.
1. All new identifiers should have at least 2 unabbreviated english words
   including one noun and one verb, ideally.

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
has to invoke **both**. `--regenerate` rebuilds all three reports' pages from
the last run's raw data in seconds, if `dev/temporary_artifacts/` still exists
(the recording run used `--keep-raw`); re-measure only when the measured thing
changed.

```sh
cmake -S . -B build -G Ninja -DCURL_USE_LIBPSL=OFF
cmake --build build --target perf      # EXCLUDE_FROM_ALL, must be named
taskset -c 3 ./build-relwithdebinfo/tests/perf/perf <test> [loops]
```

`CURL_USE_LIBPSL=OFF` is the only intentional deviation (libpsl-dev absent).
Never profile `./build` (`-O0`: inlining differs, attribution wrong) - use
`build-relwithdebinfo`. Always pin: WSL2 noise is ~106% unpinned, \<1-3%
pinned.

## How the four scripts fit together

`perf2html.sh` builds + profiles + generates one report; `perf2html_diff.sh`
measures nothing and subtracts two reports' `raw/` archives;
`perf2html_batch.sh` runs baseline, modified (`-D CMAKE_C_FLAGS=-Os`), diff,
every step even after a failure; `scripts/reformat.sh` lints, formats and
validates, every stage running even after an earlier one failed.

**`--verbose` is additive, in all four.** Whatever quiet prints, verbose prints
too, same form and order; `verbose()` is the one function that tests
`$VERBOSE`. A guard of the shape `[ "$VERBOSE" = 1 ] || printf ...` is the bug
this rule prevents - the quiet line _is_ the line. **No function in `dev/*.sh`
may wrap `printf` without adding logic.** Quiet prints **whole lines only**: a
step's duration rides in its own `done:` line, because an unflushed partial
line can sit unforwarded for minutes.

- `perf2html.sh` default DIR is `perf2html_baseline_report`, or
  `perf2html_modified_report` when any cmake_flags are given - **after a
  _source_-only change pass `--report=perf2html_modified_report` yourself.**
- `toolchain_check` is the **only** toolchain check the user-facing scripts
  have (the diff probes `python3`/`tar`/`xz` inline). It collects **every**
  missing tool before exiting 1, one `tool -> official install command` each.
  **Official instructions only** - no PPAs, no hand-rolled recipes. A missing
  `perf` prints a WSL2 note: `linux-tools-generic` is built against an Ubuntu
  kernel WSL does not run, so `linux-perf` is the kernel-independent build.
  `reformat.sh`'s tools are **out of scope**: `dev/*.sh` is for tool users,
  `reformat.sh` for tool development.
- `reformat.sh` **takes no path argument** - the dirs are fixed by convention;
  its one optional argument is a report dir. A directory is a report by holding
  a `MANIFEST.txt` whose line 1 names `perf2html.sh` or `perf2html_diff.sh`,
  which also decides `--diff`. Anything else is an **error naming the version
  string it expected**.
- **`reformat.sh` is the only `validate_report.py`, `pyright`, `ruff` and
  `prettier` call anywhere.** Don't add a lint or validate step to a generator
  or to the batch. **The batch plus `reformat.sh` is the generators' test
  suite** - don't grow a per-generator check.
- `--keep-raw` keeps `dev/temporary_artifacts/`. **The batch owns every
  deletion of it** - it passes `--keep-raw` down so a child can't unlink the
  batch log mid-run. A failed flagless batch _keeps_ it (the logs are the
  evidence).
- Profiling:
  `taskset -c 3 valgrind --tool=callgrind --cache-sim=yes --branch-sim=yes`.
  Timing is a _separate_ native pinned
  `perf stat -x, -e cycles:u,instructions:u` run - its `Time*` lines are the
  only valid speed number; callgrind's wall clock never is.
- Valgrind's LL cache auto-detects as direct-mapped and overstates conflict
  misses - `--LL=16777216,16,64` is on the `valgrind` line in `run_one`.
- Trace tree `build-instr` = same flags + `-finstrument-functions` +
  `dev/cyg_callback.c` linked in. Whole build instrumented, no file list.
- No env vars; constants sit at the top of each shell script (`CPU=3`,
  `LOOPS_DIVISOR=50`, `SKIP_ALL`, `MANIFEST_VERSION`). `TESTS` comes from
  `tests/perf/Makefile.inc`; loops from `loops_of` grepping the test source.
- **Both** modes log every child's output to `dev/temporary_artifacts/*.log`
  and print the same failure summary from it. The verbose tee sits behind
  `if ! { ...; }` so `pipefail` can't take the failure before `PIPESTATUS[0]`
  is read. `now_us()` strips every non-digit so the locale's decimal separator
  can't corrupt the arithmetic.

## Report layout

```text
OUTDIR/
index.html            overview: strip + header table + test suites
<test>/index.html     summary: logs, raw-data links, top 50 by self
<test>/flame-graph/   index.html + profile.js (rdtsc trace)
<test>/heat-map/      per-line source heat map
<test>/perf-tool/     output.txt (the summary's "perf log")
<test>/raw/           <test>txz: callgrind file + speedscope JSON
all/                  every test's callgrind data merged
assets/               one theme copy (theme/heatmap css+js, frame.js,
                      ui_strings.js, settings.js)
flame-graph-app/      one speedscope copy
sources/              one .js per profiled file -> window.report_sources
README.md             copied from dev/README.md every run ("help" link)
MANIFEST.txt          line 1 = version string; then LABEL=VALUE rows
```

- The **"all"** synthetic test: no perf log, no trace log, no flame graph, and
  in a full report **no `raw/` at all** - it reads every real test's archive. A
  _diff_'s `all` does have one, the merged delta (`all_has_archive`).
- A **diff report**: no flame graph, no native timing, and per-test pages have
  no preamble **except** the raw-data link to their own archive.
- `MANIFEST.txt` line 1 is the _only_ thing that makes a directory a diff input
  (a diff's version string names `perf2html_diff.sh`, so diffs can't be
  diffed). Written by `run_all` after every test, so an aborted run leaves
  none.
- **Every path written to a page or manifest is relative**; `home_dir_check`
  fails on the author's `$HOME`. A report must be copyable off-box.
- **Generated pages are deterministic** - same input ⇒ byte-identical output,
  so a page diff is always code, never sampling. Only `stamp=` and genuinely
  re-measured time vary. Verify by running a generator twice and `cmp`.

**Raw data is stored compressed, one `tar.xz` per test**, named after the
**directory** holding it, never the page title, which can carry a space
(`<test> diff`). The `tar` line is
**`--sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner`**: without those
an archive carries mtimes and readdir order and two runs on one input differ,
breaking determinism. `perf2html_diff.sh` unpacks both inputs **once** in
`profiles_extract`, writing a listing the per-test code reads - re-globbing per
test would re-extract every archive. `profiles_extract` also **synthesizes the
`all` row** for a diff, as the union of every real test's profiles.

**A diff overview reads its rows from `--diff-profile NAME=FILE`**, the working
subtracted profile in `temporary_artifacts/`, not the report's `raw/`. Reading
`raw/` would have silently rendered every row blank once raw data was
compressed.

**What every page shares is stored once and linked**, never inlined: `assets/`,
`flame-graph-app/`, `sources/`. **No generator takes an assets href** - it is
`theme.shared_href(depth, name)`, `depth` fixed by the layout: overview 0,
summary 1, heat map or flame graph 2. The one genuine variable is a **diff's
single-test mode**, where the report holds one test so its summary page _is_
the root (`--single-test-report`). There is no inline-everything branch: a page
that must stand alone is a new flag with a caller, not a default nobody
exercises.

**`sources/` holds one script per profiled file**, named `source_name()` - the
display path with every non-alphanumeric character flattened to `_`, plus
`.js` - assigning its text into `window.report_sources[<display path>]`. A
`FileModel`'s `source` is that **file name**, not the text; `heatmap.js`
resolves it through `source_text(file_path)`, the one door its three read sites
use. A `file://` page cannot `fetch()` a second blob, which is why this is a
`<script src>` assigning a global.

**The stylesheet is generated, not copied** - its colour variables are computed
in `Theme.css()`, so a copied `scripts/theme.css` would silently drop them.
This is a `file://` layout: **classic `<script src>` and `<link>` only**. An ES
module or a `fetch()` would need a web server and is what this must never
become; `localStorage` and the frame `postMessage` nest keep working because
same-origin `file://` documents still count as same-origin to each other.

**Only the speedscope files a page loads are copied** (`speedscope-*.js`,
`speedscope-*.css`, `*.woff2` - the font is named by the CSS by a path relative
to **itself**, so it must sit beside it); the rest was 973KB of dead weight per
test. `flame_app_install` **fails unless each glob matches exactly one file**
and hands the resolved names to `build_flame_graph.py` - the script that copied
them is what knows them.

**Validation follows a link rather than assuming inlining.** `page_scripts()`
reads every `src=`/`href=` a page names and appends the file, so a **missing or
misspelled href fails loudly** - the one failure mode sharing introduces.
`sources_check` adds what that walk cannot see: a page linking `sources/` when
the directory is missing.

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
  **synthesized callers diff**, a separate JSON beside the delta
  (`callgrind_diff.py --callers-output`).
- **Every share divides by that same thing's own baseline cost**, never by a
  global budget. `(new - old)/old`, so 1→0 is -100%, 100→90 is -10%, 90→100 is
  +11.1%, 1→1 is 0% (rendered empty). Something the baseline never had is
  **+100%**. Baselines ride in the synthesized callers diff, keyed by `<fn>`
  and `<fn>\n<display path>\n<line>`.
- **`events` is the recorded events and nothing else**, and every vector is
  written against them - `costs_fit()` pads to the recorded width and trims
  trailing zeros, and stores **no derived slot**, because a derived event is a
  pure function of the recorded ones and a stored copy could only go stale. So
  a slot's index never moves and a short vector still means zeros. On the
  Python side `callgrind.event_value(events, costs, name)` is the one door,
  which is why the coefficients live only in `_DERIVED_DEFAULTS`. Ranking and
  heat are `abs()`, so winners and losers interleave.
- **Per-line baselines are wildly skewed** - median line is ~18 Ir and 72% are
  under 1,000, so a line that cost 1 and moved 200K reads 20,360,300%. Only
  ~1.8% of lines exceed ±1000%, but a max-based colour scale is set by exactly
  those. In a diff the `FULL_HEAT_PERCENT` clamp handles it; in a non-diff
  report that is what `log, per function` is for.
- `profile_magnitudes()` (Σ|per-function line delta|) is what
  `heatMapTotals.totals` carries, but it is no longer what shares divide by.
- `summary:` in the delta = the signed total, so the parser's 1.0000 self-check
  holds on it too.

**Core vs diff code.** The non-diff path stays byte-checkable against an older
generator. Keep the split: `BuildReport.test` core vs `.diff_test`;
`CallgrindToHeatmap.model()` core vs `.diff_model()`; in heat-map JS every diff
override sits in the one `if (IS_DIFF) {...}` block; `validate_report.py` is
data-driven by `_LAYOUT_FULL`/`_LAYOUT_DIFF`.

## `dev/scripts/` conventions

**79 columns is the hard max** for every line of `dev/` source - code and
comment alike, every language. `reformat.sh` makes a line still over 79 after
the formatters run an **error**, not a note. The formatters cannot reach `echo`
text, a fenced block in `.md`, or a long template literal - those few are split
by hand. Whole tree is at 0. Not to be confused with the **80-column source
_view_** in the heat map (`HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS`), the width
profiled `lib/` source renders at - that stays 80 and must never be changed to
match the 79.

**`dev/` source is ASCII plus a short allow list**: `≈`, `∞`, `▲`, `▶`, `▼`,
`…` (`SOURCE_SCAN_ALLOWED_NON_ASCII_CHARS`), **written literally**. An entity
would be double-escaped into visible text by `html_escape()`, and its length
would corrupt the `text.length` column-width math. Adding a character means
adding it to that constant with a `#` comment naming it. `DECLAUDE.md` is not
scanned, nor any `.json`.

Reformatting `heatmap.html`, `heatmap.js`, `heatmap.css`, `frame.js`,
`flame_bootstrap.js`, `theme.css` or `theme.js` changes a report, so a page
diff after such an edit is expected; `--regenerate` then a diff against a
snapshot is how you check it. Text a script `echo`s into `perf-tool/output.txt`
is _page content_ - split it into extra `#` lines rather than letting it
overflow.

**Comments: short, tech-writer style, never docstrings.** One
`# <Name> - what it is` line above every class and function; a one-line `#`
above every field, never trailing. No comments at all in the `scripts/` page
assets (`.js`, `.css`, `.html`). `ArgumentParser()` gets no description.

**A name must answer "which one?" and "what kind?" on its own** - whether a
reader who has **not** read this code can recover the referent from the name
alone. Strictest for **flags, fields and constants**, read alone with no
surrounding code. The fix is never a longer help string.

**Names left alone.** `profile`, `stamp`, `loops`, `event` stay - a decision.
`event` and `stamp` are **boundary names**: `events:` is callgrind's own line,
`stamp=` a `MANIFEST.txt` row `--regenerate` reads back. Renaming the Python
without the format is a lie; renaming both breaks every report on disk to make
a variable read better. **Do not open a renaming campaign** - rename only while
already editing that code, when the name is not a boundary name and the change
reads in one sitting. `--profile` → `--diff-profile` is the shape to copy.

**File shape:** constants → classes → public free functions → `main()`. One
enclosing class per script holding **every** non-exported function - no free
helpers, no nested `def`s. Classes and methods alphabetical. Public free
functions are one-line delegations so callers never name a class. **Constants
alphabetical ignoring the leading `_`**; the only ones allowed below the
classes are those that can't be evaluated above.

**Typing** (pyright `standard`, py3.11, **0 errors**): everything annotated, no
`Any`-shaped records. Record → `NamedTuple`; summed in place → `@dataclass`;
JSON object → `TypedDict` (a NamedTuple serializes as an array). Cost vectors
are `callgrind.Costs` (`list[int]`), summed only via `costs_add` and friends.
Each CLI converts argparse into a NamedTuple before calling anything. A field
shadowing a base-class method takes a trailing underscore (`index_`).

pyright is at `~/.local/bin/pyright`
(`pip3 install --user --break-system-packages pyright`; PEP-668 box). Pylance
is not usable - LSP only, ignores argv. `prettier` **reparses what it writes**,
so a syntax error or unbalanced `</div>` fails the run instead of shipping into
every page; config `dev/.prettierrc.json` (`printWidth` 79,
`proseWrap: always` - without that prose is left on one line).
`npm install -g prettier` lands in `~/.npm-global/bin`, which `tool_find`
searches alongside `~/.local/bin`.

### The scripts

- `settings.py` - **the entire control surface for the tools' configuration**,
  beside `ui_strings.js` for the UI's vocabulary. **Single-file use is not a
  reason to keep a setting elsewhere.** `RANKING_COUNTER_NAME` is the counter
  every table ranks, colours and divides by. **What stays out** is what is not
  a decision: a derived value, a constant naming a class in its own file, and a
  **format fact** nobody may retune - `cyg_callback.c`'s wire format and the
  regexes parsing valgrind's output.

  **It is "settings", never "constants".** That word is banned for this data,
  in every language, in identifiers and in prose. The file is `settings.py`,
  the generated asset is `assets/settings.js`, the page global is `settings`.

  **One setting, one spelling, in all three languages.** A setting is
  `SCREAMING_SNAKE` in the JSON key, at the JS use site and in Python alike, so
  one grep finds every use everywhere and nothing translates case at a
  boundary. The name is a **full plain-word path, broad to narrow**, minimum
  two words: `HEAT_MAP_TREE_INDENT_PER_LEVEL_PX`, not `tree_indent`. A reader
  reviews the design by reading the names, so no jargon a newcomer would have
  to look up - "the timestamp on a file we send as out-of-band extra data",
  never "the stamp on a sidecar". A unit suffix stays (`_PX`, `_MS`,
  `_PERCENT`, `_SHARE`, `_CHARS`, `_BYTES`); a bare count takes none.

  **A file declares the settings it reads and `settings.load_into()` assigns
  them.** The declaration is a bare pyright annotation naming the type the file
  expects, and the call comes straight after, before anything else the module
  defines:

  ```python
  _HEAT_MAP_TREE_ALWAYS_LISTED_DIRS: tuple[str, ...]
  _RANKING_COUNTER_NAME: str
  settings.load_into(__name__)
  ```

  There is **no accessor and no conversion** - no `settings.X` read inline at a
  use site, no `page_constant_int()`, nothing that coerces. The annotation is
  the whole request and `load_into()` is the one door. It stops the run at
  import on any of four things, each message naming its own fix: a declared
  name settings.py does not define, a scalar whose type disagrees with the
  annotation (exactly - `float` on an `int` is an error, not a promotion;
  containers are checked to the container only), a setting that cannot be
  found, and **any `SCREAMING_SNAKE` name already bound when it runs**.

  That last one is why **settings come first**. The whole `SCREAMING_SNAKE`
  namespace belongs to the reader until `load_into()` returns, so that what it
  walks is a clean list of names it was asked for; the file's own constants -
  `_PID_PREFIX`, `_MAGIC`, a derived regex - are assigned **below** the call. A
  constant written above it fails the import naming itself and saying to move
  it down.

  Declared settings sort alphabetically ignoring the leading `_`, under **one**
  comment for the whole block - never one per line, because each value's
  comment lives on its definition in `settings.py` and a second copy is where
  the two drift apart.

  **ruff's `F821` is off tree-wide** because a bare annotation reads to it as a
  use of an undefined name. pyright understands the form, still reports a
  genuinely undefined name, and is gated at **0 errors**, so that check moved
  tools rather than being dropped.

  **Every setting the page's JS reads** is listed in `_BROWSER_SETTING_NAMES`
  and reaches the browser as **one generated file** written by
  `settings_script_write()`, a single `const settings = ...` - no per-setting
  serialization, so adding one is a name in that list and a `settings.NAME` at
  the use site. **The object is frozen to its leaves** by `_DEEP_FREEZE`,
  carried in that file since nothing else has loaded yet (a shallow
  `Object.freeze` leaves nested objects writable), and `settings` is a
  **lexical `const`, not a `window` property**. Python and the page read the
  same name, so a heat alpha or a column width is **one value under one id, not
  a hand-matched twin**. **The page links it before every script that reads
  it.**

- `callgrind.py` - the one parser. `profile_load(path)` exits unless the
  self-check ratio is exactly **1.0000** - re-verify after touching it. It is
  cost conservation only, and says nothing about whether emitted structure was
  observed (rule 3). `path_norm() -> PathInfo(display, local, group)` is the
  one path resolver every generator uses - no `--repo-root` flag exists.
  Functions keyed by **name**, so a symbol in two objects is one function.
  Derived events when inputs exist: `D1m`, `DLm`, `L1m`, `LLm`, `Bm`, `CEst` (=
  Ir + 10·L1m + 100·LLm). **Nothing outside this file spells a coefficient**,
  and **no Python spells out what an event is called** - the pages render
  descriptions out of `ui_strings.js`. `event_value()` / `event_names()` are
  the door a reader with a **stored** vector uses. `function_entry` for an
  uncalled function = the **first** cost line callgrind wrote in its home file
  (505/505; lowest line number does not - inlined helpers sit above the entry).
- `build_report.py test|overview` lists 50 functions. **Every table on both
  sides of the core/diff split names `_RANKING_COUNTER_NAME` directly**, with
  **no fallback**: `Profile.value()` raises `KeyError` on an event a profile
  can't supply, which is wanted - a silently substituted event is a wrong
  column and a wrong denominator. `events_check()` is the one guard, naming the
  event it wanted and the recorded list it got. CEst is linear
  (`CEst(mod-base) == CEst(mod)-CEst(base)`), so the numerator was never the
  obstacle; the **denominator** is added up from recorded slots. The
  LABEL=VALUE rows above a page's content are `ManifestRow`/`ManifestBlock` -
  not `HeatMapTotals`, not a column-title row. **Never call any of them just
  "header".**
- `callgrind_diff.py` - `events_check()` is a **hard error** - two sides
  recording different events, or either unable to supply the ranking counter,
  names both lists and exits non-zero. `subtract()` owns that call, so every
  path is guarded once. `--callers-output` is required; the overview reaches it
  off the working copy, not by reading the archive back. Its file name, flags
  and JSON keys are contract.
- `callgrind_to_heatmap.py` - `render()` substitutes `__SCRIPTS__` **before**
  `__DATA__`: the scripts carry no marker while `__DATA__` is the model, so it
  is the one replacement whose result must never be scanned again. Script order
  is `sources/`, `ui_strings.js`, `theme.js`, `heatmap.js` - `heatmap.js`
  renders the opened file the moment it runs, so anything it reads must already
  be there.
- **No generator holds a multi-line HTML/CSS/JS literal** - each is a real file
  in `scripts/`, read through `theme.asset_text_read()`, so **their JS is
  written plainly**: `\n` is `\n`, not `\\n`. `flame_bootstrap.js` keeps its
  `__NAME__`/`__DATA__` markers, bare identifiers so `node --check` accepts the
  file; it **polls**, because speedscope defines `window.speedscope` only once
  it has started up, well after its script tag ran.
- `ui_strings.js` - **the whole UI vocabulary, in one object**, keyed by a
  `str_` id named for what the string _is_, not where it sits. `text_of(id)`
  **returns `(update ui_strings.js)` for an unknown id**, so a typo renders an
  instruction instead of an empty cell. A string with a number or name in it is
  **one entry with a placeholder**, never split at the seam; replacements are
  not rescanned, so a function name containing braces cannot inject a second
  substitution. It must load **before** the script that reads it. What stays
  out is the boundary names: CSS classes, `data-*`, localStorage and URL keys,
  element ids, JSON keys, substitution markers, and the three names
  `validate_report.py` greps for. Diff arrows and `>1000x`/`≈0.00%` stay out
  too - number _notation_, produced in lockstep with `theme.py`'s `Numbers`.
  **`heatmap.html` holds none either**: its control labels and placeholder are
  empty in the markup and filled at startup. Python is the one boundary it
  cannot cross - `build_report.py` renders text server-side, so
  `(no recorded caller)` stays in Python, kept in step with `str_no_caller` by
  hand.
- `dev/cyg_callback.c` - the recorder. Hot path is
  `if(next < end) { next->fn = fn; next->tsc = rdtsc | flag; ++next; }` - 11/12
  instructions (check with
  `cc -O2 -fcf-protection=none -S -masm=intel dev/cyg_callback.c`). `next` must
  stay a pointer, `end` a variable. `next == end` = not sampling; everything
  else lives on that cold path. Setup is a constructor (incl. `memset` of the
  buffer, so no page fault lands in a timed call; 327680 records, 5MB static,
  no test fills it). Its header comment is the format reference.
  Single-threaded.
- `trace_to_speedscope.py` - pairs enters/exits (mismatch = non-zero exit),
  takes the busiest run's first `FLAME_GRAPH_MAX_RECORDED_CALLS` = 200 complete
  calls. 200 is hard-coded for the current `TESTS_C`, whose call counts run
  79–202 for seven of eight; the eighth records 3,180 cheap calls. Retune if a
  test's shape changes. `at` is raw (hook cost included). Must run while
  `build-instr` still holds the traced binary (symbolization reads it). GCC
  instruments inlined bodies, so inlined helpers are frames.
- `validate_report.py OUTDIR [--diff]` - structural smoke test only.
  `flame_graph_check` requires exactly one `evented` profile whose `exporter`
  is ours, so a synthesized or stale flame graph fails, and fails any file in a
  test's `flame-graph/` outside `_FLAME_GRAPH_FILES`. **It greps generated
  pages for three JS names**, so those are contract, not private:
  `loadFileFromBase64` (speedscope's own API), `var document_base64 = "..."`
  and `report_ui.layout_activate`. Rename one in the JS and every page fails
  validation while looking perfectly correct in a browser - change both sides
  together. `raw_archive_check` opens each `raw/*txz` with `tarfile` and runs
  the per-file checks **inside** it, fails an uncompressed file left beside the
  archives, and fails a `raw/` on a test that stores nothing.

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

- `--bg` is the slate dark member darkened 8% via `Theme.shade()` - page
  background, scrollbar track, minimap band and heat blend all follow it, so
  change it only there. `THEME_COLOR_PAIR_ENTRIES` holds raw THEME entries, odd
  index = dark member, `--<name>-l` light; `HEAT_COLOR_RAMP_STOPS` is exempt
  from the pair rule.
- Heat = the 12-stop `HEAT_COLOR_RAMP_STOPS` blended over `--bg`, alpha on log
  scale of magnitude, text colour by resulting luminance. **The scale dropdown
  is a curve × scope product built at runtime**, and `scale` is the chosen
  entry (`.curve`, `.scope`, `.value`), never a bare string.
- **Scope is a denominator, not just a colour ceiling** - it picks what a
  percentage divides by, and the heat is that same percentage, so the printed
  number and the colour behind it are one quantity. `global` divides by the
  profile total, `per file` by that file's lines, `per function` by the lines
  the owning function holds. `scope_totals_build()` sums a file once per
  render, for the selected event **and every secondary event**, so `Bcm` under
  `per function` reads what share of that function's mispredictions a line
  carries. `share_in_scope()` is the door; `heat_of_line()` picks between it
  and the diff's `share_of_baseline` on `IS_DIFF`, which is how the core/diff
  split survives a shared call site. Scope reaches the **file view only** - the
  home tables and tree span every file, where `per file` and `per function`
  name nothing, and `home_render()` clears `scope_totals` so a stale file's
  sums can't leak in. The popup's share column is titled for the scope in
  force, so the copied markdown can't be misread as global.
- **A scope's heat ceiling is either fixed or measured**: `global` colours
  against 10% and `line` against 100%, while `per file`/`per function` measure
  the scope's own largest percentage per event. `global` is fixed because no
  single line is a large share of a whole program - measuring would light the
  hottest line fully and say nothing, while `[0..10%] -> full palette` reads as
  an absolute standing across every file. A line past it clamps.
- **A diff has exactly one scope, `per line`**, so its dropdown is just
  `log`/`linear`. Non-diff indexes `0..1`; **diff indexes signed `-1..1` across
  the ramp** (savings → cold/blue, regressions → hot/red, 0 at midpoint). **A
  diff clamps both the share and `max_share` to 100%**, so the 1.8% of lines
  reading millions of percent can't set a scale nothing else registers on:
  `c(100%) == c(10000000%)`, `c(90%) != c(10000000%)`. Non-diff clamps nothing.
- Call counts are their own event, heat-coloured by share of all recorded
  calls, log-scaled, event-independent.
- Numbers: `2.1K`/`2.0G`, `63.2%`, `<0.01%`; exact zero renders empty. **A diff
  never prints `+`.** A share leads with an arrow and keeps a negative's sign -
  `▲11.1%`, `▼-100.0%`; an amount carries only a minus when negative (U+2212).
  Under 0.01% it is `▲≈0.00%` - direction kept, size marginal. **A diff share
  past 100% switches to a multiple** (`▲1.30x`), and at or past `99.99x` it is
  just `>1000x`, deliberately approximate; both sides (`Numbers.multiple()` and
  the JS `multiple_text()`) are kept in step and tested on the same cases.
  `≈0.00%` and `>1000x` state a bound, not a value, so neither takes a sign.
  **A drop can't pass -100%**, so the multiple branch is reachable only for a
  rise; don't "fix" negative multiples, they can't occur.
- **No decorative borders** - the only drawn lines are drag targets, invisible
  until hover/active.
- **No tooltips.** Nothing a page renders carries a `title=`; neither `Cell`
  nor `Column` has a field for one. What a cell can't fit is simply not shown.
  The only `title=` left is the `<iframe title="report page">` label. **A page
  that can only be read by hovering is a broken page** - "put it back in a
  `title=`" is never the fix. There is also no exact value anywhere: the
  rounded, arrow-signed text is all a page shows, and the "copy" markdown
  carries the same rounded text.
- **"Reading a Diff Report" in `README.md` is where diff notation is
  explained.** The README is copied into every report every run and the strip's
  "help" link opens it. Keep it in step with "Diff semantics": that section is
  the implementation, this one the same rules in the user's words.
- Column widths: exact `ch` counts; the header label is every column's floor -
  **no column is ever narrower than its own title**, at rest, after a drag or
  after a fill. One rule in two places, `column_widths()` (JS) and
  `table_render()` (theme.py) - keep them in step. Widths are **never
  persisted**; reload resets.
- `fill` tables end with the right edge at the same inset as the left -
  `grow_column_fill()` measures it live against `nearest_scroller()`, never
  `window.innerWidth`, and bails on a table with no layout (`offsetWidth` 0),
  since under `display:none` everything reads 0 and the grow column would be
  fitted to `0px`.
- Scrollbars: square, unrounded `--blue` thumb, 14px, no arrows, no hover
  state.
- `STRIP_STATUS_ROW_WIDTH_CHARS` must stay ≥ the widest string a **status row**
  can show. Today `simpleformat / flame graph` = 26, so 33 holds;
  `flex-wrap: nowrap` means too small clips mid-word on exactly the pair nobody
  opens.

### JS naming: snake_case is ours, camelCase is theirs

Every identifier we own is `snake_case` and unabbreviated; anything still
camelCase is a name the browser or Python owns - a DOM member, a CSS class, a
`data-*`, a localStorage or URL key, or a JSON key from the TypedDicts
(`heatMapTotals`, `lineFunction`, ...). **A camelCase name crosses a boundary
and cannot be renamed freely.** The shared runtime global is
`window.report_ui`; `window.report_sources` is the second, keyed by **display
path** and read only by `source_text()` - change one side and every heat map
renders "Source not available." without failing anything. Stored keys keep
their dotted spelling (`heat.scale`, `split.<pane>`, `perf2html.version`).
`__NAME__`/`__DATA__`/`__SCRIPTS__`/`__APP_CSS__`/`__APP_JS__`/`__PROFILE_JS__`
are substitution markers Python matches literally - never rename them. **A
string literal left inline in a `.js` file is a boundary name by definition** -
if it is not one, it belongs in `ui_strings.js`.

### Frames and URL state

Pages nest two deep: overview frames a test summary, which frames its heat map
/ flame graph. Both levels run the same `FRAME_JS`, deciding by
`is_framed = window.parent !== window`.

- The outermost **status row** always reads the literal `perf2html`; a framed
  level's reads the **selection path**. Both levels keep the element, so the
  block reads continuous and the links line up. `document.title` is set at
  every level, which is why the outer level keeps taking `title_changed`.
- A selection path with no `" / "` is a summary page, so `selection_path()`
  appends `" / summary"` - a general rule about one-segment paths, not a case
  for one test name.
- **URL is the whole state.** Frame: `#<view>[/<inner hash>]`. Heat map:
  `f=<file>`, `f=<file>&l=<n>`, `fn=<name>`, none = home, `&e=<event>` spelled
  out when >1 event. Every click is `location.hash =`; `route_render()` renders
  then canonicalizes via `replaceState` and posts up. Nothing is remembered
  outside the URL except `heat.scale`/`heat.sort` and `split.<pane>`.
- **The local store is versioned** - `STORAGE_VERSION` = `perf2html v1` under
  `perf2html.version`, a bare string, not JSON, so it stays readable whatever
  the stored formats do. The stored version not being **exactly** the current
  string sweeps every key this report owns. **Bumping the string is how a
  stored-format change is rolled out.** The sweep owns `STORAGE_OWNED_KEYS`
  plus `STORAGE_OWNED_PREFIXES` (`split.`), walking `localStorage.key(i)` so a
  generated pane key needs no list. Existing spellings were deliberately
  **not** moved under one prefix: renaming would orphan exactly the data the
  check exists to clean. **A new key must be added to one of those two
  constants or its data outlives every bump.** The check sits inside the
  accessors' `try`/`catch`, so a private-mode `localStorage` that throws leaves
  the page working.
- `FRAME_JS` loads a page with `location.replace()`, passing
  `link_href + (inner_hash || "#")` - **never `iframe.src`**, which adds a
  history entry per load and desyncs back. `"#"` not `""`: a fragment-less URL
  is a document reload.
- Four postMessages, all source-checked. `hash_changed` is posted by the heat
  map _and_ by a framed `FRAME_JS`'s own `hash_canonicalize()`, so a middle
  level relays its full hash up - without it the outer hash freezes at
  `#<test>`.
- Regression test for URL-as-state: click test → view → file → line → event,
  the outer hash must end `#<test>/heat-map/f=<file>&l=<n>&e=<ev>`, and loading
  that URL back must reproduce all three levels' hashes.
- Outer frame page never scrolls itself - `overflow: hidden` on
  `html:has(body.frame)` and `body.frame` (a real non-overlay scrollbar's
  sub-pixel gap doesn't repro headless).

### Heat map internals (gotchas)

- **No row-wide heat** - each cell carries its own, so no cell's text is
  contrast-coloured against another cell's background.
- `event_list`/`secondary_events` list every event the profile _can_ produce,
  **not** filtered by whether the total is zero - the dropdown and columns stay
  layout-stable across profiles/diffs. An all-zero column renders blank, no
  heat, no `NaN`. Totals guard `|| 1`.
- **The event descriptions are one vocabulary in two places that must say the
  same words**: `ui_strings.js`'s `str_event_<key>` entries and `README.md`'s
  "Callgrind Events" table. Same key means a **byte-identical string**, all 19
  events. Change a wording in one and change both, same edit; Python is **not**
  a third place. Register is "plain and unabbreviated but not a sentence":
  `L1 data cache misses`, not `L1 cache` (too terse to tell `D1m` from `L1m`)
  and not one carrying the formula (that belongs in the README's "Derived from"
  column). **Watch the width:** the `<select>` takes its fixed `ch` width from
  the longest `"<desc> / <key>"`, now 42 ch, against the 1366x768 target.
- `.fhead`, `.chips` and `.tbl-cols` sit in one `.srcwrap`
  (`width: max-content; min-width: 100%`) so the wrapper equals the sideways
  scroll range. Bands/chips need `contain: inline-size` or their unwrapped
  single-line width sets max-content. **Order gotcha:** `minimap_build()` runs
  _before_ `layout_activate()` - it narrows the pane by 110px and the fill
  measures it as-is at that moment.
- `row_center()` (vertical only) replaces `scrollIntoView`, which also pulled
  the pane sideways.
- Minimap: `#minimap` is never resized and never scrolls; scale pinned to 80
  columns, never widened to the longest line. Clone needs `width: 100%` +
  `table-layout: fixed`. `clone_height_px` readable only after `empty` is
  removed (display:none measures 0). Only the `th` cells are sticky, the
  `<thead>` scrolls away - **never measure the thead**.
- Popup "copy" builds a plain-text twin in parallel with the HTML, never
  scraped `textContent`. The popup's stats table drops zero rows, so its height
  varies, and every row divides by the selected scale's scope.
- Clickable-row hover cue is an underline on `td.ln`: an inline heat `color`
  beats any stylesheet colour, so a `--link` recolor can't show on heated
  lines.

## Checking pages in a browser (no browser in WSL2)

```sh
CHROME="/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
SHOT="\\\\wsl.localhost\\$WSL_DISTRO_NAME\\tmp\\x.png"
PAGE="file://wsl.localhost/$WSL_DISTRO_NAME/home/t/curl/dev"
"$CHROME" --headless=new --disable-gpu --window-size=1366,768 \
  --screenshot="$SHOT" \
  "$PAGE/perf2html_baseline_report/index.html#heat-map"
```

`--dump-dom` instead for post-script DOM. For the frame page, copy `index.html`
to `probe.html` beside it with an appended script that sets `location.hash`,
awaits the canonical hash and writes a `<pre>`; run with
`--dump-dom --virtual-time-budget=30000`. Cross-origin `file://` frames are
opaque **unless** `--allow-file-access-from-files` is passed - which is what
lets one probe click through all three levels. **jsdom is not installed on this
box**, and it can't do `location.replace` across documents or layout anyway -
Chrome for anything geometric.

## Measurement facts (2026-09-19)

- Callgrind cannot give per-call stacks or time: `calls=` lines are aggregated
  (caller, callee) totals. `--read-inline-info=yes` changes nothing observable.
  `--separate-callers=N` is exact but still aggregated and orderless - **never
  feed such a file to the summary/heat map**, functions come out named by full
  chain.
- Whole-build `-finstrument-functions`: one top-level library call is 2–184
  events depending on the test; 0 enter/exit mismatches in all 8 tests.
  Perturbation native → traced: 152 → 154 ns/call at 2 events/call, 304 → 746
  at 184. The box's native speed itself moves ~1.9× with host state, so only
  compare numbers from one run. Hook cost is inside every traced duration →
  **flame graph is for shape and outliers, perf log for speed.**
- `rdtsc` steps by 20 ticks = 10.02 ns here, so every flame-graph duration is a
  multiple of ~10 ns. The 28→11 instruction hook saving is verified in
  disassembly only - it's below the clock's step.
- speedscope evented JSON ≈ 38 B/event: 1 MB ≈ 26,000 events.
- TSC: `constant_tsc nonstop_tsc rdtscp tsc_reliable`; measured 1.9962 tsc/ns.
- `perf stat -e cycles:u,instructions:u` works in this WSL2 (kernel 6.18
  exposes the CPU PMU). `perf record` works but samples.
- uftrace is not installed (needs sudo); a `dpkg -x` copy hung in
  `uftrace record`. It would cost more per call than the rdtsc hook.

## What a report's bytes are (2026-09-20)

A default report over the eight `TESTS_C` is **8.39MB**: heat-map pages 44%,
the flame `profile.js` base64 trace 36%, everything shared 13%, raw archives
5%. Almost all of it is recorded measurement, and **none of it is deleted to
make a number smaller**. **base64 costs a flat 33%** of every trace - 744KB of
the 2.98MB `profile.js` is padding - and it is **not ours to remove**:
`loadFileFromBase64` is the only entry point speedscope's bundle exports, and
it is reached only when the hash carries `localProfilePath`, on which
speedscope appends **its own** `<script src="file:///profile">` that silently
404s. Our `profile.js` tag is what actually loads, which is why the bootstrap
polls. Removing the padding means a different loader, not a smaller encoding.
**This is the one finding here that is still open**, and it is open because the
fix is somebody else's loader.

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
