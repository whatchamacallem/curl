# curl perf work

## Rules

1. Keep this file current in the same change as any
   tooling/layout/theme/findings change. `CLAUDE.md` symlinks to
   `dev/DECLAUDE.md`. Facts, commands, numbers, gotchas. No line numbers (they
   rot) - name a function/identifier. **A-list only**: it goes in if a session
   that had not read it would get it wrong, waste an hour, or break a contract.
   Over **40,000 bytes** as you add to it, **say so and leave it alone**
   (`wc -c`). **Never compact it on your own initiative** - what to drop is the
   user's call.
1. `dev/` is throwaway profiling tooling: one shared parser, one shared theme,
   no dead code, no duplicate systems. Everything a script writes opens from
   `file://` with nothing fetched at view time.
1. **No fake data.** Every value on a page is a recorded measurement or plain
   arithmetic on one (sum, difference, share, `CEst`). No apportioning,
   interpolation or "plausible" stacks. If a tool can't supply what a view
   needs (callgrind: per-call stacks/time), the view isn't built.
1. **Nothing test-specific, ever.** No test names, file lists or per-test cases
   anywhere in `dev/`; every view is built for every test in `TESTS_C`.
   Examples read `<test>`/`<file>`.
1. Never "meta" - that is a "header" or a "manifest". No "events", "metrics"
   or "stats", only **counters**; counting things is what this tool does.
1. More than one goal in a run → conclude with a checklist of what was and was
   not accomplished, plus any relevant bug reports.
1. New identifiers: at least 2 unabbreviated english words, ideally one noun
   and one verb.

## Commands

```sh
dev/perf2html.sh [--verbose] [--keep-artifacts] [--regenerate]
    [--report=DIR] [--artifacts=TMP] [cmake_flags...]
dev/perf2html_diff.sh [--verbose] [--keep-artifacts] [--regenerate]
    [--artifacts=TMP] [baseline-dir] [modified-dir] [report-dir]
dev/perf2html_batch.sh [--verbose] [--keep-artifacts] [--regenerate]
    [--artifacts=TMP] [--target-dir=DIR] [cmake_flags...]
dev/scripts/reformat.sh [--check] [--verbose] [report-dir]
```

**Verification is two runs, in this order:** `perf2html_batch.sh` measures and
generates, then `reformat.sh` lints, formats and validates. **The batch runs no
checks at all**; anything verifying a build invokes **both**. `--regenerate`
rebuilds all three reports' pages from the last run's recordings in seconds if
the artifacts dir still exists (recording run used `--keep-artifacts`).

**The artifacts dir defaults to `perf2html_temporary_artifacts/` in the parent
directory of the report** (so the tool works with its own tree on a read-only
FS); `--artifacts=TMP` overrides it in all three `.sh`, and the batch forwards
it to both children so all three stages share one dir. The batch's
`--target-dir=DIR` (default CWD) holds the three **default-named** reports -
**the batch cannot name them**; call `perf2html.sh` / `perf2html_diff.sh`
directly for custom names. **Every batch argument that is not one of its own
options is a cmake flag**, so a run can be nothing but the flags being tested
and `DEFAULT_FLAGS`' separated `-D CMAKE_C_FLAGS=-Os` needs no value
continuation - the old positional `target-dir` and its one-shot `-D`/`-U`
lookahead are gone.

```sh
cmake -S . -B build -G Ninja -DCURL_USE_LIBPSL=OFF
cmake --build build --target perf      # EXCLUDE_FROM_ALL, must be named
taskset -c 3 ./build-relwithdebinfo/tests/perf/perf <test> [loops]
```

`CURL_USE_LIBPSL=OFF` is the only intentional deviation (libpsl-dev absent).
**Never profile `./build`** (`-O0`: inlining differs, attribution wrong) - use
`build-relwithdebinfo`. **Always pin**: WSL2 noise ~106% unpinned, \<1-3%
pinned.

## How the four scripts fit together

`perf2html.sh` builds + profiles + generates one report; `perf2html_diff.sh`
measures nothing and subtracts two reports' `raw/` archives;
`perf2html_batch.sh` runs baseline, modified (`-D CMAKE_C_FLAGS=-Os`), diff;
`reformat.sh` lints, formats, validates. In the batch and reformat **every step
runs even after an earlier one failed**.

**`--verbose` is additive, in all four**: whatever quiet prints, verbose prints
too, same form and order. `log_verbose()` in `scripts/shared.sh` is the one
function testing `$VERBOSE`; a guard shaped
`[ "$VERBOSE" = 1 ] || printf ...` is the bug this prevents. **No
function in `dev/*.sh` may wrap `printf` without adding logic.** Quiet prints
**whole lines only** (a duration rides in its own `done:` line; an unflushed
partial line can sit unforwarded for minutes).

- `perf2html.sh` default DIR is `perf2html_baseline_report`, or
  `perf2html_modified_report` when any cmake_flags are given - **after a
  _source_-only change pass `--report=perf2html_modified_report` yourself.**
- `toolchain_check` is the **only** toolchain check the user-facing scripts
  have (`cksum` is required too). It collects **every** missing tool before
  exiting 1, one
  `tool -> official install command` each, **official instructions only** - no
  PPAs, no hand-rolled recipes. Missing `perf` prints a WSL2 note: use
  `linux-perf`, not `linux-tools-generic`. **`reformat.sh`'s tools are out of
  scope** - `dev/*.sh` is for tool users, `reformat.sh` for tool development.
- `reformat.sh` **takes no path argument**; its one optional argument is a
  report dir. A directory is a report by its `MANIFEST.txt` line 1, which also
  decides `--diff`; anything else is an **error naming the version string it
  expected**.
- **`reformat.sh` is the only `validate_report.py`, `pyright`, `ruff` and
  `prettier` call anywhere** - no lint or validate step in a generator or the
  batch. **The batch plus `reformat.sh` is the generators' test suite.**
- **`DECLAUDE.md` is the author's notes, not `dev/` source**: no formatter,
  lint or column check reaches it. `SKIPPED_MARKDOWN_NAMES` holds it out,
  honoured in `files_of()` - the **one door** every stage collects files
  through, whose prune also covers the artifacts dir and
  `-not -path '*_report/*'`. `README.md` **is** source and is checked.
- **`reformat.sh` has no `settings` stage** - `lost_settings()` and its
  `settings | note | N below load_into()` row are **gone**, along with the
  `LostSetting` record and the two module constants that scanned for them.
  A file's own constants below the call are simply where they belong; there
  was nothing for a reader to act on in the count.
- `--keep-artifacts` keeps the artifacts dir. **The batch owns every deletion
  of it** - it passes `--keep-artifacts` down so a child can't unlink the batch
  log mid-run. A failed flagless batch _keeps_ it. The batch's own
  `KEEP_ARTIFACTS` is set in `args_parse` straight off the flags, never
  re-derived from a `case` over `PASS_ARGS`, and `--regenerate` has its own
  `REGENERATE` guarding `reports_clean` - **`--keep` is gone**: its only effect
  was skipping `reports_clean`, which nothing but `--regenerate` ever wanted,
  and keeping stale files in a re-measured report breaks its checksum.
- **The word "raw" now means only the report's own `<test>/raw/` and its
  `raw-data` page links** - a layout name. The temporary recordings are
  "artifacts" everywhere else, including `validate_report.py`'s
  `raw_archive_check`/`raw_dir_check`, which read that layout dir.
- Profiling:
  `taskset -c 3 valgrind --tool=callgrind --cache-sim=yes --branch-sim=yes`.
  Timing is a _separate_ native pinned
  `perf stat -x, -e cycles:u,instructions:u` run - **its `Time*` lines are the
  only valid speed number**; callgrind's wall clock never is.
- Valgrind's LL cache auto-detects as direct-mapped and overstates conflict
  misses - `--LL=16777216,16,64` on the `valgrind` line in `run_one`.
- Trace tree `build-instr` = same flags + `-finstrument-functions` +
  `dev/cyg_callback.c`. Whole build instrumented, no file list.
- No env vars. **`dev/scripts/shared.sh` (sourced, not executable) holds every
  shared shell setting and every shared shell function**, each half
  alphabetical: the settings registry (`ARCHIVE_SUFFIX`, `ARTIFACTS_NAME`,
  `BASE_NAME`, `BUILD_DIR`, `CALLGRIND_LOOPS`,
  `CONTAINING_PACKAGES`, `CPU=3`, `DEFAULT_FLAGS`, `DIFF_NAME`,
  `FLAME_APP_DIR`, `FLAME_APP_FILES`, `HEADER_ROWS_NAME`, `MOD_NAME`,
  `TIMING_LOOPS`, `TRACE_BUILD_DIR`, `TRACE_SKIP_ALL`), then
  `archive_write` / `checksum_compute` / `clock_microseconds` / `command_run` /
  `duration_format` / `elapsed_format` / `install_command_of` / `json_quote` /
  `log_verbose` / `manifest_script_write` / `manifest_value` /
  `manifest_verify` / `manifest_write` / `absolute_path` /
  `settings_load` / `toolchain_check`. **A name `settings.py` already holds
  is not repeated here** - the assets dir arrives as `ASSETS_NAME` through
  `settings_load`, which is why there is no `ASSETS_DIR`. **Only a value
  derived from `$0` stays per-script** (`REPO`, `TIMESTAMP`), and says so in
  its comment. `usage_show` and
  `args_parse` stay per-script too. The `*_DIR` are derived in each
  `args_parse`. `TESTS` comes from `tests/perf/Makefile.inc`.
- **Sourcing `shared.sh` is inert**: it defines names and runs nothing, so it
  cannot exit its caller. **A function there writes a caller global only where
  all callers agreed it is the canonical setter, and its `#` comment names
  every global it sets** - `settings_load` (`ASSETS_NAME`, `CHECKSUM_LABEL`,
  `DIFF_MANIFEST`, `MANIFEST_SCRIPT`, `REPORT_MANIFEST`), `toolchain_check`
  (`SPEEDSCOPE_RELEASE`), the batch's own `step_run` (`STATUS`, `FAILED`).
- **The shell reads settings by eval**, in `settings_load`, which every caller
  invokes explicitly: `python3 dev/scripts/settings.py --shell` prints
  `ASSETS_NAME`, `CHECKSUM_LABEL`, `DIFF_MANIFEST`, `MANIFEST_SCRIPT` and
  `REPORT_MANIFEST` (mapped by `_SHELL_SETTING_VARIABLES`) - one definition
  across Python and shell, off `REPORT_ASSETS_DIR_NAME`,
  `REPORT_MANIFEST_CHECKSUM_LABEL`, `ASSET_REPORT_MANIFEST_SCRIPT_NAME` and
  `REPORT_MANIFEST_VERSION_FULL`/`_DIFF`. **A generated
  shell fragment was rejected**: it would be a build artifact inside the linted
  tree - formatted and column-checked, dirty in git every run, unwritable on a
  read-only checkout, and needed before any Python has run on a fresh clone, so
  there is no non-circular bootstrap.
- **The `MANIFEST.txt` contract is `shared.sh`'s** - the two version strings
  (`curl/perf2html.sh v1`, `curl/perf2html_diff.sh v1`), the checksum label and
  `checksum_compute` / `manifest_write` / `manifest_value` / `manifest_verify`.
  All three `.sh` plus `reformat.sh` source it; the strings themselves are
  **production settings in `settings.py`**, which is where the generators, the
  shell and `validate_report.py` all read them from.
- **Both** modes log every child's output to the artifacts dir's `*.log` and
  print the same failure summary from it. The verbose tee sits behind
  `if ! { ...; }` so `pipefail` can't take the failure before `PIPESTATUS[0]`
  is read. `now_us()` strips non-digits (locale decimal separator).

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
                      ui_strings.js, settings.js, error_overlay.js,
                      report_manifest.js)
flame-graph-app/      one speedscope copy
sources/              one .js per profiled file -> window.report_sources
README.md             copied from dev/README.md every run ("help" link)
MANIFEST.txt          line 1 = version string; then LABEL=VALUE rows
```

- **"all"** synthetic test: no perf log, no trace log, no flame graph, and in a
  full report **no `raw/`** - it reads every real test's archive. A _diff_'s
  `all` has one, the merged delta (`all_has_archive`).
- **Diff report**: no flame graph, no native timing; per-test pages have no
  preamble **except** the raw-data link to their own archive.
- `MANIFEST.txt` line 1 is the _only_ thing making a directory a diff input (a
  diff names `perf2html_diff.sh`, so diffs can't be diffed). **Written last**,
  after every page, asset and raw archive → an aborted or failed run leaves
  none.
- **`--regenerate` reads every row it wants in `build_manifest`**, which runs
  before `main` drops the previous manifest. `build_compile` used to read
  `build=` after that `rm -f`, which broke `--regenerate` outright - `sed:
  can't read ... MANIFEST.txt`, and the half-written report it left had no
  manifest, so the _next_ regenerate could not start either. A new row a
  regenerated run needs is read there, never later.
- **No tool may open a report whose `MANIFEST.txt` is missing or whose version
  line is not EXACTLY the expected string**; the error prints **both found and
  expected**. Enforced at `--regenerate`, both diff inputs, `reformat.sh`'s
  report detection and `validate_report.py`. Deliberately strict, to catch
  breaking changes during development. `perf2html_diff.sh --regenerate`
  **hard-errors** on a missing or unverifiable report rather than falling back
  to a fresh stamp.
- **`checksum=` row**: POSIX `cksum` over every file **except the manifest**,
  list `LC_ALL=C` sorted, paths **relative** to the report dir.
  **Re-verified every time any tool opens a report**; a mismatch is a hard
  error printing expected vs found. `validate_report.py` shells out to the
  identical pipeline rather than reimplementing the CRC.
- Paths in pages/manifest: **relative**. `home_dir_check` fails on `$HOME`.
  Reports copy off-box.
- **Generated pages are deterministic** - same input ⇒ byte-identical output,
  so a page diff is always code, never sampling. Only `stamp=` and re-measured
  time vary. Verify by running a generator twice and `cmp`.
- **Raw data compressed, one `tar.xz` per test**, named after the **directory**
  holding it, never the page title (which can carry a space). The `tar` line is
  **`--sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner`** - without
  those an archive carries mtimes and readdir order and two runs differ.
- `perf2html_diff.sh` unpacks both inputs **once** in `profiles_extract` (a
  listing the per-test code reads) and **synthesizes the `all` row**, the union
  of every real test's profiles.
- **A diff overview reads its rows from `--diff-profile NAME=FILE`**, the
  working subtracted profile in the artifacts dir, not the report's `raw/`.

**What every page shares is stored once and linked**, never inlined: `assets/`,
`flame-graph-app/`, `sources/`. **No generator takes an assets href** - it is
`theme.shared_href(depth, name)`, `depth` fixed by layout: overview 0, summary
1, heat map or flame graph 2 (`HEAT_MAP_VIEW_ENTRY`, `FLAME_GRAPH_VIEW_ENTRY`).
The one variable is a **diff's single-test mode**, where the summary page _is_
the root (`--single-test-report`). **A page that must stand alone is a new flag
with a caller**, never an inline-everything default.

**`sources/` holds one script per profiled file**, named `source_name()`
(display path, non-alphanumerics flattened to `_`, plus `.js`) assigning its
text into `window.report_sources[<display path>]`. A `FileModel`'s `source` is
that **file name**, not the text; `heatmap.js` resolves it through
`source_text(file_path)`, the one door its three read sites use - a `file://`
page cannot `fetch()` a second blob.

**The stylesheet is generated, not copied** (colour variables computed in
`Theme.css()`). **Classic `<script src>` and `<link>` only** - an ES module or
`fetch()` would need a web server and is what this must never become;
`localStorage` and the frame `postMessage` nest work because same-origin
`file://` documents count as same-origin to each other.

**Only the speedscope files a page loads are copied** (`speedscope-*.js`,
`speedscope-*.css`, `*.woff2`, which must sit beside the CSS naming it);
`flame_app_install` **fails unless each glob matches exactly one file** and
hands the resolved names to `build_flame_graph.py`. **Validation follows a link
rather than assuming inlining**: `page_scripts()` reads every `src=`/`href=` a
page names and appends the file, so a **missing or misspelled href fails
loudly**; `sources_check` catches a page linking `sources/` when the directory
is missing.

Artifacts dir (gitignored): `callgrind.out.<test>.<loops>.<ts>`,
`valgrind.<test>.<loops>.<ts>.log`, `trace.<test>.<loops>.<ts>.bin`
(+`.maps`), `.speedscope.json`, `perf-stat.<test>.<ts>.csv`,
`profile.<ts>.log`.

## Diff semantics

- Every number is **MODIFIED - BASELINE, per (function, file, line)** - never
  per (file, line) alone, which hands half an inlined function's cost to its
  neighbour.
- The delta is plain callgrind format with **no `calls=` lines** → no call
  graph → no call columns/caller tables in the heat map (`HAS_CALL_GRAPH`). The
  summary's calls/callers columns come from the **synthesized callers diff**, a
  separate JSON beside the delta (`callgrind_diff.py --callers-output`).
- **Every share divides by that same thing's own baseline cost**, never a
  global budget: `(new - old)/old`. 1→0 = -100%, 100→90 = -10%, 90→100 =
  +11.1%, 1→1 = 0% (rendered empty). Something the baseline never had is
  **+100%**. Baselines ride in the synthesized callers diff, keyed by `<fn>`
  and `<fn>\n<display path>\n<line>`.
- **`events` is the recorded counters and nothing else**; every vector is
  written against them. `costs_fit()` pads to recorded width, trims trailing
  zeros, stores **no derived slot** - a slot's index never moves and a short
  vector still means zeros. `callgrind.counter_value(counters, costs, name)` is
  the one Python door; coefficients live only in `settings.py`'s
  `DERIVED_COUNTER_TERMS`. Ranking and heat are `abs()`, so winners and losers
  interleave.
- **Per-line baselines are wildly skewed**: median line ~18 Ir, 72% under
  1,000, a line that cost 1 and moved 200K reads 20,360,300%, only ~1.8% exceed
  ±1000%. Hence no measured maximum - the `HEAT_COLOR_FULL_SCALE_PERCENT` clamp
  holds those lines.
- `profile_magnitudes()` (Σ|per-function line delta|) is what
  `heatMapTotals.totals` carries, **not** what shares divide by.
- `summary:` in the delta = the signed total, so the parser's 1.0000 self-check
  holds on it too.
- **Core vs diff split** (the non-diff path stays byte-checkable against an
  older generator): `BuildReport.test` vs `.diff_test`;
  `CallgrindToHeatmap.model()` vs `.diff_model()`; in heat-map JS every diff
  override in the one `if (IS_DIFF) {...}` block; `validate_report.py`
  data-driven by its own `_LAYOUT_FULL`/`_LAYOUT_DIFF`.

## `dev/scripts/` conventions

- **79 columns is the hard max** for every line of `dev/` source, code and
  comment, every language. `reformat.sh` makes a line still over 79 after the
  formatters an **error**, not a note. Formatters cannot reach `echo` text, a
  fenced block in `.md`, or a long template literal - split by hand. Whole tree
  at 0. **Not** the 80-column source _view_
  (`HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS`), which **must never change to match**.
- **ASCII plus a short allow list**: `≈`, `∞`, `▲`, `▶`, `▼`, `…`
  (`_SOURCE_SCAN_ALLOWED_NON_ASCII_CHARS`, now in `validate_report.py`),
  **written literally** - an entity
  would be double-escaped by `html_escape()` and its length corrupts the
  `text.length` column math. Adding one = a line in that constant with a `#`
  comment. `DECLAUDE.md` is not scanned (`SKIPPED_MARKDOWN_NAMES`), nor
  `.json`.
- Reformatting `heatmap.html`, `heatmap.js`, `heatmap.css`, `frame.js`,
  `flame_bootstrap.js`, `theme.css` or `theme.js` **changes a report**, so a
  page diff is expected; `--regenerate` then diff against a snapshot. Text a
  script `echo`s into `perf-tool/output.txt` is _page content_ - split into
  extra `#` lines rather than overflow.
- **Comments: short, tech-writer style, never docstrings.** One
  `# <Name> - what it is` above every class and function; a one-line `#` above
  every field, never trailing. **No comments at all in the `scripts/` page
  assets** (`.js`, `.css`, `.html`). `ArgumentParser()` gets no description.
- **A name must answer "which one?" and "what kind?" on its own**, strictest
  for **flags, fields and constants**; the fix is never a longer help string.
- **Names left alone:** `profile`, `stamp`, `loops` - a decision. `stamp` is a
  **boundary name** (a `MANIFEST.txt` row `--regenerate` reads back).
  **`event` was renamed to `counter` throughout**; only callgrind's own
  `events:` line keeps the spelling, and the `e=` URL key keeps its letter.
  **Do not open a renaming campaign** - rename only while already editing that
  code, when the name is not a boundary name and it reads in one sitting
  (`--profile` → `--diff-profile` is the shape to copy).
- **File shape:** constants → classes → public free functions → `main()`. One
  enclosing class per script holding **every** non-exported function - no free
  helpers, no nested `def`s. Classes and methods alphabetical. Public free
  functions are one-line delegations so callers never name a class.
  **Constants alphabetical ignoring `_`**; only those that can't be evaluated
  above may sit below the classes.
- **Imports: `import X` only**, never `from X import Y` - sole exception
  `from __future__ import annotations`. Every use site qualified
  (`typing.NamedTuple`, `collections.abc.Sequence`, `dataclasses.field`,
  `callgrind.Costs`, `theme.html_escape`). **Packed onto one alphabetical line
  per block**, one before `sys.path.insert` and one after for our own modules;
  past 79 columns it splits into further `import a, b` lines keeping order.
  Hence **`E401` and `I001` are off in `ruff.toml`** - both unpack those lines
  and `reformat.sh` runs `ruff check --fix`. `[lint.isort]` went with `I001`.
- **Typing** (pyright `standard`, py3.11, **0 errors**): everything annotated,
  no `Any`-shaped records. Record → `NamedTuple`; summed in place →
  `@dataclass`; JSON object → `TypedDict` (a NamedTuple serializes as an
  array). Cost vectors are `callgrind.Costs` (`list[int]`), summed only via
  `costs_add` and friends. Each CLI converts argparse into a NamedTuple before
  calling anything. A field shadowing a base-class method takes a trailing
  underscore (`index_`).
- pyright at `~/.local/bin/pyright`
  (`pip3 install --user --break-system-packages pyright`; PEP-668 box).
  Pylance is not usable - LSP only, ignores argv. `prettier` **reparses what it
  writes**, so a syntax error or unbalanced `</div>` fails the run instead of
  shipping into every page; config `dev/.prettierrc.json` (`printWidth` 79,
  `proseWrap: always`). `npm install -g prettier` lands in `~/.npm-global/bin`,
  which `tool_find` searches alongside `~/.local/bin`.

### The scripts

**`settings.py` - the entire control surface for the tools' configuration**,
beside `ui_strings.js` for the UI's vocabulary. **Single-file use is not a
reason to keep a setting elsewhere.** `RANKING_COUNTER_NAME` is the counter
every table ranks, colours and divides by.

- **Stays out**: format facts nobody may retune (`cyg_callback.c` wire format,
  valgrind-output regexes), class instances, derived values, **and anything
  only the verification component reads**. Deleting `reformat.sh` plus
  `validate_report.py` must leave no dead setting behind, so the `VALIDATE_*`
  byte floors, the two `ReportLayout`s and the `SOURCE_SCAN_*` family are
  `validate_report.py`'s own constants, below its `load_into()` call.
  **Verification may read production settings to confirm a report obeyed
  them** - it just may never keep its own copy of a production value, which is
  why `_LAYOUT_FULL`/`_DIFF` take `manifest_version` from
  `REPORT_MANIFEST_VERSION_FULL`/`_DIFF` rather than restating it. The old
  `_SHELL_SETTING_LAYOUT_FIELD` reach-into-validation is gone.
- **"settings", never "constants"**, in every language, identifiers and prose.
  `settings.py`, `assets/settings.js`, page global `settings`.
- **One setting, one spelling, all three languages**: `SCREAMING_SNAKE` in the
  JSON key, JS use site and Python. One grep finds every use.
- Name = **full plain-word path, broad to narrow**, min two words:
  `HEAT_MAP_TREE_INDENT_PER_LEVEL_PX`, not `tree_indent`. Unit suffix stays
  (`_PX`, `_MS`, `_PERCENT`, `_SHARE`, `_CHARS`, `_BYTES`); a count takes none.
- **A file declares what it reads; `load_into()` assigns** - annotation
  naming the type **plus an empty sentinel of that type** (`""`, `0`, `0.0`,
  `()`, `[]`, `{}`), then the call, before anything else:

```python
_HEAT_MAP_TREE_ALWAYS_LISTED_DIRS: tuple[str, ...] = ()
_RANKING_COUNTER_NAME: str = ""
settings.load_into(__name__)
```

  **The sentinel is never read** - `load_into()` overwrites every one of them
  at import, and a file that runs before it would be broken anyway. It is
  there so the name is bound, which is what lets both uninitialized-variable
  checks stay **on**.

- **No accessor, no conversion**: no inline `settings.X`, no
  `page_constant_int()`, nothing that coerces. `load_into()` is the one door.
- **Stops the run at import, three checks in this order**, each naming its
  fix. `load_into()` walks **every `SCREAMING_SNAKE` name the module has
  bound**, annotated or not - each one is a setting being asked for:
  1. `match_check` - **`error: constant doesn't match any setting`**.
     settings.py has no setting by that name. This is **first**, so a file's
     own constant written above the call is told it matches nothing rather
     than being judged on its shape; a misspelled setting lands here too.
  1. `sentinel_check` - **`error: settings must have sentinels 0, 0.0, (),
     [], or ""`**. The name matches, so it is a declaration, and a
     declaration carries an empty sentinel and nothing else. An unannotated
     name that happens to match a setting lands here, not in `match_check`.
  1. `type_check` - **`error: settings must not be coerced to another
     type`**. Scalars exact (`float` on `int` is an error); containers
     checked to the container, not walked.

  There is no `namespace_check` any more: the first check subsumes it, and
  does so with the better message.
- **Settings come first**; a file's own constants (`_PID_PREFIX`, `_MAGIC`, a
  derived regex) go **below** the call. Declared settings sort alphabetically
  ignoring `_`, under **one** comment for the block.
- **ruff `F821` and pyright `reportUnboundVariable` are both ON** - the
  sentinel initializers are what buys that, so neither tool can read a
  declaration as a use of an undefined name. They were both off while
  declarations were bare; **do not turn either off again** - a real
  uninitialized read is exactly what they are there to catch. `E401`/`I001`
  stay off for the import shape, `E501` for the column check reformat.sh
  does itself. pyright gated at **0 errors**.
- **Everything the page's JS reads** is in `_BROWSER_SETTING_NAMES` (incl.
  `HEAT_COLOR_LOGO_STOPS`, `NUMBER_SMALLEST_PRINTED_PERCENT`), shipped as
  **one generated file** from `settings_script_write()`, **frozen to its
  leaves**. One value, one id, **no hand-matched twin**. **Linked before every
  reader**; the page's script list is unchanged, nothing new is linked.
- The freeze + reader is `settings_handler.js`, written plainly with bare
  `__NAME__`/`__DATA__`
  markers so `node --check` accepts it unsubstituted; named by
  `ASSET_TEMPLATE_SETTINGS_HANDLER_NAME`, making the template block **four**.
  **`settings.py` reads it with a local `open()` against its own `_DIRECTORY`,
  never `theme.asset_text_read()`** - `theme.py` does `import settings`, so
  importing theme here would cycle. The generated `assets/settings.js` carries
  `"use strict"` inside its IIFE, so a write to a frozen leaf throws instead of
  failing silently.
- **`settings` is a reader function, not an object**: `settings("NAME")` throws
  on an unlisted name. **Lexical `const`, not a `window` property.**
- **A `.js` file resolves each setting once into a local `const` of the same
  name**, one block atop its IIFE under `"use strict"`, alphabetical, one
  comment. **Never call `settings()` in a loop or render path**, never inline.

**`callgrind.py` - the one parser.**

- `profile_load(path)` exits unless the self-check ratio is exactly **1.0000** -
  re-verify after touching. Cost conservation only; says nothing about whether
  emitted structure was observed (rule 3).
- `path_norm() -> PathInfo(display, local, group)` is the one path resolver.
  No `--repo-root` flag exists.
- Functions keyed by **name**: a symbol in two objects is one function.
- Derived counters when inputs exist, off `settings.DERIVED_COUNTER_TERMS`:
  `D1m`, `DLm`, `L1m`, `LLm`, `Bm`, `CEst` (= Ir + 10·L1m + 100·LLm). **No
  coefficient and no counter key is spelled in code** - only `settings.py`,
  and this file is their one reader. Adding/dropping a counter = an edit there
  plus its description in `ui_strings.js` and `README.md`.
- **No Python spells out what a counter is called**; pages render descriptions
  from `ui_strings.js` via
  `HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX` + name lowercased.
  `counter_value()` / `counter_names()` are the door for a **stored** vector.
- `function_entry` for an uncalled function = the **first** cost line callgrind
  wrote in its home file (505/505); lowest line number does not - inlined
  helpers sit above the entry.

**`build_report.py test|overview`** - 50 functions.

- **Every table on both sides of the core/diff split names
  `_RANKING_COUNTER_NAME` directly, no fallback**: `Profile.value()` raises
  `KeyError` on a counter a profile can't supply. A substituted counter is a
  wrong column and a wrong denominator.
- `counters_check()` is the one guard, naming wanted vs recorded. CEst is
  linear (`CEst(mod-base) == CEst(mod)-CEst(base)`); the denominator adds up
  recorded slots.
- LABEL=VALUE rows are `ManifestRow`/`ManifestBlock` - not `HeatMapTotals`, not
  a column-title row. **Never call any just "header".**

**`callgrind_diff.py`** - `counters_check()` is a **hard error**: two sides
recording different counters, or either unable to supply the ranking counter,
names both lists and exits non-zero. `subtract()` owns that call, guarding
every path once. `--callers-output` required, reached off the working copy; its
file name, flags and JSON keys are contract.

**`callgrind_to_heatmap.py`** - `render()` substitutes `__SCRIPTS__` **before**
`__DATA__`; the scripts carry no marker, so it is the one replacement whose
result must never be scanned again. Script order
`theme.page_preamble_scripts()`, `sources/`, `ui_strings.js`, `theme.js`,
`heatmap.js` - the last renders the opened file as it runs.

**No generator holds a multi-line HTML/CSS/JS literal** - each is a real file
in `scripts/` (`ASSET_TEMPLATE_HEAT_MAP_PAGE_NAME`,
`ASSET_TEMPLATE_FLAME_GRAPH_PAGE_NAME`,
`ASSET_TEMPLATE_FLAME_GRAPH_BOOTSTRAP_NAME`) read via
`theme.asset_text_read()`, so **their JS is written plainly**: `\n` is `\n`,
not `\\n`. `flame_bootstrap.js` keeps bare `__NAME__`/`__DATA__` markers so
`node --check` accepts it, and **polls**: speedscope defines
`window.speedscope` only once started, well after its script tag ran.

**`ui_strings.js` - the whole UI vocabulary, in one object**, keyed by a `str_`
id named for what the string _is_, not where it sits.

- `text_of(id)` **throws on an unknown id**, and `settings(name)` throws on
  an unlisted setting. Both surface as the error page, which is the point:
  a missing string or setting is a bug in this tool, not something a page
  papers over. The old `(update ui_strings.js)` marker return is gone, and
  with it `heatmap.js`'s `MISSING_STRING_TEXT` sentinel - `counter_label`
  now just reads the description, so a counter with none fails loudly
  instead of silently rendering its bare key.
- A string with a number or name is **one entry with a placeholder**, never
  split at the seam; replacements are not rescanned.
- **Must load before the script that reads it.**
- **Out**: boundary names (CSS classes, `data-*`, localStorage and URL keys,
  element ids, JSON keys, substitution markers, the three greped names); diff
  arrows and `>1000x`/`≈0.00%` too - number _notation_, in lockstep with
  `theme.py`'s `Numbers`.
- **`heatmap.html` holds none**: control labels and placeholder empty in the
  markup, filled at startup.
- Python is the one boundary it cannot cross: `build_report.py` renders
  server-side, so `(no recorded caller)` stays in Python, kept in step with
  `str_no_caller` by hand.

**`error_overlay.js` - the error page.** An uncaught `error` or
`unhandledrejection` replaces the document with the message, the source
(exception or rejection), the page address, the callstack and the report's
MANIFEST.txt. **It must be the first script every page links** - it installs
the window handlers, so anything linked before it can throw where nothing is
listening. `theme.page_preamble_scripts()` is the one place that order is
written, and both `theme.document()` and `callgrind_to_heatmap.render()`
spread it first.

- It is the **only** `.js` that may not resolve its strings at IIFE top: it
  loads before `ui_strings.js` by design, so `text_or_fallback(id, text)`
  reads them at render time and falls back only when `window.ui_strings` is
  not there yet. It catches `text_of`'s throw for the same reason - an error
  page that throws shows nothing. **Its ten `str_error_*` entries still live
  in `ui_strings.js`**; the fallbacks exist for the one moment before it
  loads, not as a second copy to edit.
- `history.pushState` to `#report-error`, so **Back restores the page** at
  the address it was showing (kept in `sessionStorage` under
  `error.restore-hash`, and taken from `location.href` first).
- A `file://` page cannot `fetch()` its own MANIFEST.txt, so
  `manifest_script_write` in `shared.sh` ships it as
  `assets/report_manifest.js` assigning the text to `window.report_manifest`.
  **It carries every row but `checksum=`**: it is written _before_
  `checksum_compute` runs and is counted by it, so a checksum inside it could
  only ever be the previous run's. Reading the checksum back is
  `manifest_verify`'s job and always was.

**`dev/cyg_callback.c` - the recorder.** Hot path
`if(next < end) { next->fn = fn; next->tsc = rdtsc | flag; ++next; }` = 11/12
instructions (`cc -O2 -fcf-protection=none -S -masm=intel dev/cyg_callback.c`).
`next` must stay a pointer, `end` a variable. `next == end` = not sampling; all
else is cold path. Setup is a constructor (incl. `memset`, so no page fault
lands in a timed call; 327680 records, 5MB static, no test fills it). Header
comment is the format reference. Single-threaded.

**`trace_to_speedscope.py`** - pairs enters/exits (mismatch = non-zero exit),
takes the busiest run's first `FLAME_GRAPH_MAX_RECORDED_CALLS` = 200 complete
calls, hard-coded for the current `TESTS_C` (79–202 calls for seven of eight;
the eighth records 3,180 cheap ones) - retune if a test's shape changes. `at`
is raw, hook cost included. Must run while `build-instr` still holds the traced
binary. GCC instruments inlined bodies → inlined helpers are frames.

**`validate_report.py OUTDIR [--diff]`** - structural smoke test only,
data-driven by its own `_LAYOUT_FULL`/`_LAYOUT_DIFF` `ReportLayout`s, built
directly below the class (no `layout_build()` mapping step any more). Every
value it checks against is either its own (`VALIDATE_*`, `SOURCE_SCAN_*`) or a
production setting read through `load_into()` - never a copy of one.

- `flame_graph_check` requires exactly one `evented` profile whose `exporter`
  is ours; fails any file in a test's `flame-graph/` outside
  `_FLAME_GRAPH_FILES`.
- **Greps generated pages for three JS names - contract, not private**:
  `loadFileFromBase64` (speedscope's own API), `var document_base64 = "..."`,
  `report_ui.layout_activate`. Rename one in the JS and every page fails
  validation while looking correct in a browser.
- `raw_archive_check` opens each `raw/*txz` with `tarfile`, runs the per-file
  checks **inside** it, and fails an uncompressed file beside the archives or a
  `raw/` on a test storing nothing.
## Why the heat map exists

Under `-O2` small static functions inline into their callers, so the
function-level top-N table charges their cost to the caller. The heat map shows
it per line; the flame graph shows inlined bodies as own frames. Cross-check:

```sh
callgrind_annotate --show-percs=yes \
  <artifacts>/callgrind.out.<test>.<loops>.<ts> <file>
```

`/* perf #N: X.XX% */` comments in `lib/` are stale dev annotations - drop
before submitting upstream.

## Look and feel

One dark theme, Monaco/monospace everywhere. Target viewport **1366×768** -
pages must not assume more.

- `--bg` = slate dark member darkened 8% via `Theme.shade()`
  (`THEME_COLOR_ROLE_BACKGROUND_SHADE_FACTOR`). Page background, scrollbar
  track, minimap band and heat blend all follow it - **change it only there**.
- `THEME_COLOR_PAIR_ENTRIES` holds raw THEME entries, odd index = dark member,
  `--<name>-l` light; `THEME_COLOR_PAIR_NAMES` names them and `Theme.pairs()`
  **fails if the two disagree in length**. `HEAT_COLOR_LOGO_STOPS` is exempt
  from the pair rule. Time units are `THEME_TIME_UNIT_ENTRIES`; colour roles
  `THEME_COLOR_ROLE_SOURCES`.
- Heat = the 12-stop `HEAT_COLOR_LOGO_STOPS` blended over `--bg`, text colour
  by resulting luminance. **The scale dropdown is a curve × scope product built
  at runtime**; `scale` is the chosen entry (`.curve`, `.scope`, `.value`),
  never a bare string.
- **The colour mapping is the simplest correct one and `heat_of_share()` is all
  of it**: clamp the percentage to `HEAT_COLOR_FULL_SCALE_PERCENT`, divide by
  it, apply the curve; `cell_style()` multiplies by `COLOR_STOPS.length - 1`.
  **Nothing is measured off the data** - no `max_share`, no per-scope scan, no
  smallest-visible floor - so a line's colour depends only on the number
  printed beside it. **Resist re-introducing a measured ceiling.**
  - Non-diff `[0..100%]` → index `[0..11]`.
  - Diff `[-100..100%]` → `[0..11]`, **0% at the 5.5 midpoint**, savings →
    cold/blue, regressions → hot/red; curve applied to the **magnitude before**
    the remap, so the halves stay symmetric.
  - `log` = `log10(1 + 9f)`, mapping `[0..1]` onto `[0..1]` exactly.
- **Scope is only a denominator**, never a colour ceiling: `global` by profile
  total, `per file` by that file's lines, `per function` by the owning
  function's lines. `scope_totals_build()` sums a file once per render, for the
  selected counter **and every secondary counter**. `share_in_scope()` is the
  door; `heat_of_line()` picks it or the diff's `share_of_baseline` on
  `IS_DIFF`. **File view only** - `home_render()` clears `scope_totals`. The
  popup's share column is titled for the scope in force.
- **A diff has one scope, `per line`** → dropdown is just `log`/`linear`. The
  100% clamp keeps the 1.8% of lines reading millions of percent from setting a
  scale nothing else registers on.
- Call counts are their own counter: share of all recorded calls, log-scaled,
  counter-independent.
- **The `perf2html` wordmark is painted per-character from the ramp**, first
  letter mid-ramp, last hottest. **Gotcha:** `.strip .title` is `--title-bg`
  (`stops[2]`, teal), where the hot end is nearly invisible (1.39:1), so the
  wordmark plate is forced to `--bg` via `:has(.wordmark-letter)`. A framed
  level's selection path keeps the teal and stays plain uncoloured text;
  `document.title` stays plain text.
- Numbers: `2.1K`/`2.0G`, `63.2%`, `<0.01%`; exact zero renders empty. The
  notation floor is **`NUMBER_SMALLEST_PRINTED_PERCENT`** (0.01), one
  definition behind `theme.py`'s `percent()`/`signed_percent()` and
  `heatmap.js`'s `share_text()`/`magnitude_text()`. **Not
  `HEAT_COLOR_SMALLEST_VISIBLE_SHARE`**, which is the log colour scale's
  bottom - confusing the two has been done once already. The notation
  _strings_ (`<0.01%`, `≈0.00%`, `>1000x`) stay inline, out of
  `ui_strings.js`. **A diff
  never prints `+`.** A share leads with an arrow, keeping a negative's sign
  (`▲11.1%`, `▼-100.0%`); an amount carries only a minus when negative
  (U+2212). Under 0.01% → `▲≈0.00%`. **Past 100% a diff share switches to a
  multiple** (`▲1.30x`), and at or past `99.99x` to `>1000x`;
  `Numbers.multiple()` and the JS `multiple_text()` are kept in step and tested
  on the same cases. `≈0.00%` and `>1000x` state a bound, not a value - no
  sign. **A drop can't pass -100%**, so the multiple branch is rise-only; don't
  "fix" negative multiples.
- **No decorative borders** - the only drawn lines are drag targets, invisible
  until hover/active.
- **No tooltips.** Nothing rendered carries a `title=`; neither `Cell` nor
  `Column` has a field for one, and what a cell can't fit is not shown. Only
  `<iframe title="report page">` remains. **A page that can only be read by
  hovering is a broken page.** No exact value anywhere - the rounded,
  arrow-signed text is all a page shows, and "copy" carries the same text.
- **`README.md`'s "Reading a Diff Report" is where diff notation is
  explained** - copied into every report every run, opened by the strip's
  "help" link. Keep it in step with "Diff semantics".
- Column widths: exact `ch` counts; the header label is every column's floor -
  **no column is ever narrower than its own title**, at rest, after a drag or a
  fill. One rule in two places, `column_widths()` (JS) and `table_render()`
  (theme.py). Widths are **never persisted**.
- `fill` tables end with the right edge at the left's inset -
  `grow_column_fill()` measures live against `nearest_scroller()`, never
  `window.innerWidth`, and bails on a table with no layout (`offsetWidth` 0).
- Scrollbars: square, unrounded `--blue` thumb, 14px, no arrows, no hover.
- `STRIP_STATUS_ROW_WIDTH_CHARS` ≥ the widest **status row** string. Today
  `simpleformat / flame graph` = 26, so 33 holds; `flex-wrap: nowrap` means too
  small clips mid-word.
### JS naming: snake_case is ours, camelCase is theirs

Every identifier we own is `snake_case` and unabbreviated. **camelCase means a
name the browser or Python owns** - a DOM member, CSS class, `data-*`,
localStorage or URL key, or a JSON key from the TypedDicts (`heatMapTotals`,
`lineFunction`, ...) - **it crosses a boundary and cannot be renamed freely**.
Runtime globals: `window.report_ui`, and `window.report_sources` keyed by
**display path**, read only by `source_text()` - change one side and every heat
map renders "Source not available." without failing anything. Stored keys keep
their dotted spelling (`heat.scale`, `split.<pane>`, `perf2html.version`).
`__NAME__`/`__DATA__`/`__SCRIPTS__`/`__APP_CSS__`/`__APP_JS__`/`__PROFILE_JS__`
are substitution markers Python matches literally - **never rename them**. **A
string literal left inline in a `.js` file is a boundary name by definition**;
if it is not one, it belongs in `ui_strings.js`.

### Frames and URL state

Two levels deep: overview frames a test summary, which frames its heat map /
flame graph. Both run the same `FRAME_JS`, deciding by
`report_ui.is_framed`.

**`theme.js` is the utility library for being an HTML app; `frame.js` is
only the thin top-level frame controller.** Colour lives in `theme.js`:
`logo_color_at(fraction)` interpolates `HEAT_COLOR_LOGO_STOPS` and
`logo_letters_build(text, class_name, start_fraction)` paints text from the
ramp - the wordmark is one caller, not a special case. Cross-frame talk is
`theme.js` too: `is_framed`, `parent_post(payload)` (a no-op unframed) and
`parent_listen(on_parent_message)` (source-checked against
`window.parent`), and `hash_publish(hash)`, which `replaceState`s then posts
`hash_changed` up. `frame.js` keeps only what is about the nesting itself -
`hash_parse`/`hash_build` for `#<view>[/<inner>]`, `hash_for_href`,
`view_show`, `title_publish`/`selection_path`, `reset_broadcast`, the
delegated click handler and the listener for its **child** iframe.
**Moving a helper into `frame.js` is the wrong direction** - ask whether any
page that is not a frame would want it, and if so it belongs in `theme.js`
behind `window.report_ui`.

- Outermost **status row** reads the literal `perf2html`; a framed level's
  reads the **selection path**. Both keep the element so the block reads
  continuous and links line up. `document.title` is set at every level - why
  the outer keeps taking `title_changed`.
- A selection path with no `" / "` is a summary page → `selection_path()`
  appends `" / summary"`: a rule about one-segment paths, not one test name.
- **URL is the whole state.** Frame `#<view>[/<inner hash>]`; heat map
  `f=<file>`, `f=<file>&l=<n>`, `fn=<name>`, none = home, `&e=<counter>`
  spelled out when >1 counter. Every click is `location.hash =`;
  `route_render()` renders, canonicalizes via `replaceState`, posts up.
  **Nothing is remembered outside the URL** except `heat.scale`/`heat.sort` and
  `split.<pane>`.
- **The local store is versioned**: `STORAGE_VERSION` = `perf2html v1` under
  `perf2html.version`, a bare string, not JSON. Not **exactly** the current
  string → sweep every key this report owns. **Bumping it is how a
  stored-format change is rolled out.** The sweep owns `STORAGE_OWNED_KEYS`
  plus `STORAGE_OWNED_PREFIXES` (`split.`), walking `localStorage.key(i)`;
  spellings were deliberately **not** moved under one prefix. **A new key must
  go in one of those two constants or its data outlives every bump.** The check
  sits inside the accessors' `try`/`catch`, so a throwing private-mode
  `localStorage` leaves the page working. All four `STORAGE_*` names sit in
  `theme.js`'s one alphabetical UPPERCASE constant block, not beside
  `view_storage`.
- `FRAME_JS` loads with `location.replace()`, passing
  `link_href + (inner_hash || "#")` - **never `iframe.src`** (a history entry
  per load, back desyncs). `"#"` not `""`: a fragment-less URL is a reload.
- Four postMessages, all source-checked. `hash_changed` is posted by the heat
  map _and_ by a framed `FRAME_JS`, so a middle level relays its full hash
  up - without it the outer hash freezes at `#<test>`. **Both go through the
  one `report_ui.hash_publish()`**; the heat map's `hash_canonicalize()` is
  now a one-line delegation, and `frame.js` calls `hash_publish` directly.
- Regression test for URL-as-state: click test → view → file → line → counter;
  the outer hash must end `#<test>/heat-map/f=<file>&l=<n>&e=<ev>`, and loading
  it back must reproduce all three levels' hashes.
- Outer frame page never scrolls itself - `overflow: hidden` on
  `html:has(body.frame)` and `body.frame`.

### Heat map internals (gotchas)

- **No row-wide heat** - each cell carries its own, so no cell's text is
  contrast-coloured against another cell's background.
- `counter_list`/`secondary_counters` list every counter the profile _can_
  produce, **not** filtered on a zero total, so dropdown and columns stay
  layout-stable across profiles/diffs. All-zero columns render blank - no heat,
  no `NaN`. Totals guard `|| 1`.
- **Counter descriptions are one vocabulary in two places that must say the
  same words**: `ui_strings.js`'s `str_counter_<key>` and `README.md`'s
  "Callgrind Counters" table - **byte-identical per key**, all 19, changed in
  one edit. Python is **not** a third place. Register is plain and
  unabbreviated but not a sentence (`L1 data cache misses`, not `L1 cache`, and
  never the formula - that is README's "Derived from" column). **Watch the
  width:** the `<select>`'s fixed `ch` width comes from the longest
  `"<desc> / <key>"`, now 42 ch, against 1366x768.
- `.fhead`, `.chips`, `.tbl-cols` sit in one `.srcwrap`
  (`width: max-content; min-width: 100%`) so the wrapper equals the sideways
  scroll range. Bands/chips need `contain: inline-size` or their unwrapped
  single-line width sets max-content. **Order gotcha:** `minimap_build()` runs
  _before_ `layout_activate()`, narrowing the pane by 110px - the fill measures
  it as-is at that moment.
- `row_center()` (vertical only) replaces `scrollIntoView`, which also pulled
  the pane sideways.
- Minimap: `#minimap` is never resized and never scrolls; scale pinned to 80
  columns. Clone needs `width: 100%` + `table-layout: fixed`.
  `clone_height_px` readable only after `empty` is removed (display:none
  measures 0). Only `th` cells are sticky - **never measure the thead**.
- Popup "copy" builds a plain-text twin in parallel with the HTML, never
  scraped `textContent`. Its stats table drops zero rows, so height varies;
  every row divides by the selected scale's scope.
- Clickable-row hover cue is an underline on `td.ln` - an inline heat `color`
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

`--dump-dom` for post-script DOM. For the frame page, copy `index.html` to
`probe.html` beside it with an appended script that sets `location.hash`,
awaits the canonical hash and writes a `<pre>`; run
`--dump-dom --virtual-time-budget=30000`. Cross-origin `file://` frames are
opaque **unless `--allow-file-access-from-files` is passed** - that is what
lets one probe click through all three levels. **jsdom is not installed** and
cannot do `location.replace` across documents or layout - Chrome for anything
geometric.

## Measurement facts (2026-09-19)

- Callgrind gives no per-call stacks or time: `calls=` lines are aggregated
  (caller, callee) totals. `--read-inline-info=yes` changes nothing observable.
  `--separate-callers=N` is exact but still aggregated and orderless - **never
  feed such a file to the summary/heat map**, functions come out named by full
  chain.
- Whole-build `-finstrument-functions`: one top-level library call = 2–184
  events by test; 0 enter/exit mismatches in all 8. Native → traced: 152 → 154
  ns/call at 2 events/call, 304 → 746 at 184. Native speed moves ~1.9× with
  host state - only compare within one run. Hook cost is inside every traced
  duration → **flame graph for shape and outliers, perf log for speed.**
- `rdtsc` steps by 20 ticks = 10.02 ns, so every flame-graph duration is a
  multiple of ~10 ns. TSC: `constant_tsc nonstop_tsc rdtscp tsc_reliable`,
  measured 1.9962 tsc/ns. speedscope evented JSON ≈ 38 B/event.
- `perf stat -e cycles:u,instructions:u` works in this WSL2 (kernel 6.18
  exposes the CPU PMU). `perf record` works but samples. uftrace is not
  installed (needs sudo) and would cost more per call than the rdtsc hook.

## What a report's bytes are (2026-09-20)

Eight `TESTS_C` = **8.39MB**: heat-map pages 44%, flame `profile.js` base64
trace 36%, shared 13%, raw archives 5%. Almost all recorded measurement, and
**none of it is deleted to make a number smaller**. **base64 costs a flat 33%**
of every trace and is **not ours to remove**: `loadFileFromBase64` is the only
entry point speedscope's bundle exports, reached only via a hash carrying
`localProfilePath`, on which speedscope appends its own
`<script src="file:///profile">` that 404s - our `profile.js` tag is what
loads, hence the polling bootstrap. **Still open**; the fix is somebody else's
loader.

## Current state

No `lib/` change has come out of the profiling yet. Per-test numbers live in
the reports (overview: native time, cycles, instructions), not here.

## Workflow

1. Quick read: `./build/tests/perf/perf <test>`, median of 3–5 - **real
   numbers only from the pinned RelWithDebInfo build**.
1. Profile via `dev/perf2html.sh`, RelWithDebInfo tree only.
1. One focused change, rebuild, re-run.
1. `dev/perf2html.sh --report=perf2html_modified_report` then
   `dev/perf2html_diff.sh`. Keep only changes that measurably help **and**
   leave everything else the test prints (counts, error totals) unchanged.
1. Record before/after numbers in "Current state" as you go.
1. After any `dev/` edit: `dev/perf2html_batch.sh` **then**
   `dev/scripts/reformat.sh`; the batch alone checks nothing.
1. Before final: full suite (`tests/runtests.pl`, or `ctest` from `build/` with
   `-DBUILD_TESTING=ON`) - the perf test doesn't validate correctness.
