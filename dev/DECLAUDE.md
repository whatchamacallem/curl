# curl perf work (30k)

Half-size `DECLAUDE.md` for quick work. **`DECLAUDE.md` is authoritative** -
read its section before changing anything a line here only names. Section
numbers match it.

## 1 Rules

1. Keep `DECLAUDE.md` current in the same change as any tooling/layout/
   theme/findings change (`CLAUDE.md` symlinks to it). Facts, commands,
   numbers, gotchas; name identifiers, never line numbers. A-list only. Over
   40,000 bytes: say so, leave it. **Never compact it unasked.**
1. **`dev/README.md` is the user-facing contract.** Code follows README,
   never the reverse. On disagreement fix the code or ask; edit README only
   when the user asked in that session.
1. `dev/` is throwaway tooling: one parser, one theme, no dead code or
   duplicate systems. Output opens from `file://`, fetching nothing.
1. **No fake data.** Every value is a measurement or plain arithmetic on one
   (sum, difference, share, `CEst`). If a tool can't supply a view's data,
   the view isn't built.
1. **Nothing test-specific, ever.** No test names or file lists in `dev/`;
   every view for every test in `TESTS_C`. Examples read `<test>`/`<file>`.
1. Never "meta" (say "header"/"manifest"). No "events", "metrics", "stats" -
   only **counters**.
1. More than one goal → end with a done / not-done checklist and bug
   reports.
1. New identifiers: at least 2 unabbreviated English words, ideally noun +
   verb.
1. **A value written twice and "kept in step" is banned.** Anything two
   files need is **one setting** read from `settings.sh`/`settings.py`.
1. Multi-item communication follows ISO 2145 numbering.
1. **Every `dev/*.sh` makes paths absolute at startup; `$PWD` is never read
   again.** `INVOKED_FROM="$PWD"` sits **above** the `cd` to the script's
   own dir; `args_parse` runs each path through `absolute_path`. After the
   `cd`, `$PWD` is `dev/`, so any `$PWD` below `args_parse` is a bug. The
   way back is **`shared.sh`'s `path_display`** only, never a hand-rolled
   `#"$_REPO"/` strip. **A leaf script derives nothing from a
   collection** - the batch and `enforcer.sh` own "three reports".
1. **Plumbing vs porcelain - settled, not for debate.** `perf2html.sh` and
   `perf2html_diff.sh` are plumbing: every path they take is
   invocation-relative, made absolute by `absolute_path` in `args_parse`;
   they hold no opinion about working directories, and `$_SCRIPT` only
   finds the tool's own code - nothing is placed by
   `$(dirname "$_SCRIPT")`. `--report=DIR` is the final report dir itself,
   not a dir to put reports in; `--artifacts` defaulting beside it is
   README's interface, not a derivation to remove. Only
   `perf2html_batch.sh` (porcelain) has a working dir (`--target-dir`,
   default CWD) and default names in it. **README and `usage_show` are the
   interface; code drifting from them is the bug.** **The tool is never
   reshaped for its verifier**: `enforcer.sh` adapts to the tool's layout
   (per-flags `dev/builds/` trees, added so `regenerate_check` could date
   each report, were that mistake). **Uncommitted changes are not the
   design** - the user, HEAD, README and this file are.
1. **`STORAGE_VERSION` is the user's, never a session's.** A change to a
   stored format leaves it alone, runs **without `--regenerate`** once, and
   says so.
1. **Docs written on request (`plan.md`, notes, write-ups) go in
   `dev/docs/`**, which `dev/.gitignore` ignores. `.md` only, never named
   `README.md`: `files_of()` and the ASCII scan still walk `dev/docs/`, and
   they match that name at any depth.

## 2 Commands

```sh
dev/perf2html.sh [--verbose] [--keep-artifacts] [--regenerate]
    [--report=DIR] [--artifacts=TMP] [cmake_flags...]
dev/perf2html_diff.sh [--verbose] [--keep-artifacts] [--regenerate]
    [--artifacts=TMP] [baseline-dir] [modified-dir] [report-dir]
dev/perf2html_batch.sh [--verbose] [--keep-artifacts] [--regenerate]
    [--artifacts=TMP] [--target-dir=DIR] [cmake_flags...]
dev/scripts/enforcer.sh [--check] [--keep-artifacts] [--regenerate]
    [--verbose]
dev/scripts/test_all.sh                 # the three modes, in order
```

```sh
cmake -S . -B build -G Ninja -DCURL_USE_LIBPSL=OFF
cmake --build build --target perf      # EXCLUDE_FROM_ALL, must be named
taskset -c 3 ./build-relwithdebinfo/tests/perf/perf <test> [loops]
```

- **Build trees: `build-relwithdebinfo` (`BUILD_DIR`) and `build-instr`
  (`TRACE_BUILD_DIR`) at the repo root**, shared by baseline and modified;
  each run reconfigures them. A report's `executable=` row names its tree,
  **repo-relative**. `build_paths` is the one setter of `_BUILD_TREE`/
  `_TRACE_TREE`/`_BIN`/`_TRACE_BIN`. No tree per report or per flags;
  **not `/tmp`** (tmpfs too small).
- **Verification is one run: `enforcer.sh`.** It clears reports, formats and
  lints `dev/`, runs the batch, then validates, shoots and scans. **The batch
  runs no checks** - a hand-run batch is measuring, not verifying.
- `--regenerate` rebuilds all three reports' pages from the last run's
  recordings. Artifacts dir **defaults to `perf2html_temporary_artifacts/`
  in the report's parent dir**; `--artifacts=TMP` overrides in all three.
- **Pass `enforcer.sh --regenerate` every time**, except after `perf` was
  re-linked. It is checked: `regenerate_check` runs first and stale
  recordings are a **hard error** (`regenerate_refuse`, exit 2) - it
  **never** falls back to measuring. `perf2html.sh`, the batch and
  `enforcer.sh` each prove their inputs before starting work. The three
  default-named reports and `enforcer.sh`'s artifacts dir are debug output,
  deletable any time.
- **`manifest_verify` is the one door saying why a dir is not a report**;
  every `--regenerate` path calls it on all three reports.
- **A recording in the link's own second is still that link's**: refuse only
  when the binary is **strictly newer**. `find -newer` alone was the bug.
- `--target-dir=DIR` (default CWD) holds the three **default-named** reports.
  **Every batch argument not its own option is a cmake flag.**
- `CURL_USE_LIBPSL=OFF` is the only intentional deviation. **Never profile
  `./build`** (`-O0`, wrong attribution); use `build-relwithdebinfo`
  (`-O2 -g`). **Always pin**: WSL2 noise ~106% unpinned, <1-3% pinned.

## 3 The four scripts

`perf2html.sh` builds + profiles + generates one report; `perf2html_diff.sh`
measures nothing and subtracts two reports' `raw/` archives;
`perf2html_batch.sh` runs baseline, modified (`-D CMAKE_C_FLAGS=-Os`), diff;
`enforcer.sh` lints, formats, validates.

- **Any error is a hard error, reported immediately.** Stop at the first
  failure, print it, nothing after. **No script collects failures** - no
  `_STATUS`/`_FAILED`/`_MISSING`, no tallies, no stage recording a fault and
  returning 0. A stage that _cannot_ run (missing formatter, missing report)
  **is a failure, not a skip**.
- **A silent downgrade is the same fault.** Never quietly do the more
  expensive thing; **prefer the refusal whenever the fallback is the
  expensive branch** - hence `--regenerate` refuses rather than measures.
- **No news is good news.** Only `test_all.sh` prints on success; the rest
  print on failure or under `--verbose`.
- **Never buffer a child's output.** No shipping `dev/*.sh` captures a child
  through `$( )` (`enforcer.sh` exempt). Children run through `shared.sh`'s
  **`child_capture`** (tee-or-redirect chosen before start, so `--verbose`
  streams); a step needing the text reads `$RUN_LOG` afterwards via
  `log_verbose_file`. Values come back **through globals**
  (`CHILD_EXIT_CODE`), never stdout. `$( )` around `printf`/`date`/
  `basename` is fine - a value, not a stream.
- **cmake's configure output goes to `/dev/null`**, banned from `--verbose`
  and `$RUN_LOG` (half the log). `tree_build` runs it outside
  `child_capture`; a failure prints only `cmake failed to build <command>`,
  the command `%q`-quoted so it pastes and reruns; the build step still uses
  `command_run`.
- **`--verbose` is additive.** **Only `shared.sh` tests `$VERBOSE`**
  (`log_verbose`, `child_capture`, `log_verbose_file`); no bare `printf`
  wrappers.
- `perf2html.sh` default DIR is `perf2html_baseline_report`, or
  `perf2html_modified_report` with cmake_flags - **after a source-only change
  pass `--report=perf2html_modified_report` yourself.**
- **`usage_show`'s heredoc is the only usage text**, matched to README's
  option lists by hand.
- `toolchain_check` is the only toolchain check: lists **every** missing
  tool with its official install command, then exits 1.
- `enforcer.sh` **takes only flags** and runs the batch itself;
  `MANIFEST.txt` line 1 decides each report's `--diff`. **It is the only
  caller of `validate_report.py`, `screenshots.py`, `pyright`, `ruff`,
  `prettier`.** It sources both `settings.sh` and `shared.sh`.
- **`enforcer.sh` is "do as I say, not as I do".** It keeps its own
  constants and spellings (`regenerate_stamp_of`,
  `_REPORT_CHECKSUM_COMMAND`, `_SCREENSHOT_*`, `screenshots_run`'s `$( )`)
  on purpose - a check built from the code it tests is no oracle. **Citing a
  shipping-script rule against it is not a bug by itself.**
- **Verification may read a shared value** (name, key, suffix) from the
  settings, and **never adds a setting**. A _calculation_ it checks gets
  local expected constants or a different-route recomputation - **never the
  code under test** (e.g. no shared manifest validation).
- **Stage order is cost-ascending**: `regenerate_check` → `surface_clear`
  (skipped under `--regenerate`; deletes the three reports, never the
  artifacts dir) → format/columns/comments/`source_scan_run`/`lint_run` →
  `batch_run` → `validate_run` → `screenshots_run` **last**. Every source
  stage precedes the batch; no stage reaches inside a report.
- **`screenshots.py` is verification**: modified + diff reports, each
  `_VIEWS` hash × `_SCREENSHOT_VIEWPORTS` (720p/1080p/4k), into
  `dev/screenshots/<size>_<report>_<view>.png`, then 4k 3x3 contact sheets
  `thumbnail_<size>_<report>.png`. **Imports no settings; no `_VIEWS` entry
  names a test**; one error view (`bad_function`).
- **`enforcer.sh` reaches source only**, via `files_of()`; `README.md` is
  the one `.md`. **Config files are untouched**; `--config` always passed.
- **`regenerate_check`** dates the **modified** report's newest timing
  recording (`perf-stat.*.csv`, `PROFILE_TIMING_FILE_PREFIX`) against the
  executable its `executable=` row names (first token, repo-relative,
  resolved via `_DIR_REPO`): the modified run links the shared tree last,
  so the baseline's binary is gone and its recordings need only exist. A
  strictly newer binary refuses. The diff names no tree. Missing
  executable/row/artifacts dir/`stamp=` row or unfinished report each
  refuse, naming the report.
- **`stamp=` is `<unix> <human date>`**; readers take the first token via
  **`manifest_stamp_of`**. **`manifest_value` stays general** (`cpu=`,
  `build=` hold spaces).
- **The batch owns every deletion of the artifacts dir**, passing
  `--keep-artifacts` down; a failed flagless batch keeps it. `--keep` is
  gone.
- **"raw"** means only `<test>/raw/` and its `raw-data` links; temporary
  recordings are "artifacts".
- Profiling: `taskset -c 3 valgrind --tool=callgrind --cache-sim=yes
  --branch-sim=yes --LL=16777216,16,64` in `run_one` (auto-detected LL is
  direct-mapped, overstates misses). Timing is a _separate_ pinned
  `perf stat -x, -e cycles:u,instructions:u` run - **its `Time*` lines are
  the only valid speed number**.
- Trace tree = same flags + `-finstrument-functions` +
  `dev/src/cyg_callback.c`; whole build, no file list.
- `child_capture`'s tee sits behind `if ! { ...; }` (for `PIPESTATUS[0]`).
  `command_run`/`step_run` exit with the child's code via
  `failure_print_log_tail`.

### 3.1 `settings.sh` and `shared.sh`

No env vars. `settings.sh` = every shell setting; `shared.sh` (sourced) =
every shared shell function; each alphabetical. `settings.sh` is **one
assignment per line**, parsed also by `settings.py`
(`SettingsReader.shell_settings_read`; `-?[0-9]+` → `int`). **No setting's
word is expanded** - no `$` words. Hand-written. **One name in all three
languages.** **`TIMESTAMP` is per-script** (`$(date +%s)`), assigned just
above `_SCRIPT="$(readlink -f "$0")"` in each shipping script; `--regenerate`
restores it from `stamp=`. `enforcer.sh` declares none. `$0`-derived values
(`_REPO`), `usage_show`, `args_parse` stay per-script. `_TESTS` comes from
`tests/perf/Makefile.inc`. Notable: `PROFILE_PINNED_CPU=3`,
`REPORT_RAW_ARCHIVE_SUFFIX` (`.txz`, dot included),
`PROFILE_TIMING_FILE_PREFIX` (`perf-stat`).

**Naming**: a script's own global is `_SCREAMING_SNAKE` (`_OUT_DIR`); a
`local` is `_lowercase` (`local _output _exit_code`). Names crossing into
`shared.sh` are bare: it reads `ARTIFACTS_DIR`, `RUN_LOG`, `START_US`,
`TIMESTAMP`, `VERBOSE`; sets `SPEEDSCOPE_RELEASE`, `RUN_LOG`
(`report_begin`), `CHILD_EXIT_CODE`/`LOG_LINE_FROM` (`child_capture`).
Settings and environment names (`CMAKE_C_FLAGS`, `PERF_TRACE_OUT`) are bare.
Underscore is on variables only, not `awk -v`, `find -name` or messages.

**Sourcing `shared.sh` is inert.** A function there sets a caller global only
as its agreed canonical setter, and its comment names every global it sets.

**`MANIFEST.txt` contract is `shared.sh`'s**: `checksum_compute`,
`manifest_fault_of`, `manifest_stamp_of`, `manifest_write`, `manifest_value`,
`manifest_verify`, `manifest_wanted_phrase`. `manifest_stamp_of` verifies,
reads, drops the date tail, **refuses an empty stamp** (the checksum excludes
the manifest, so a torn row would otherwise pass). `manifest_fault_of` is
the one reader: echoes why a dir is not a finished report, or nothing; takes
each acceptable version string. `manifest_verify` is the hard-error policy on
top. Version strings (`curl/perf2html.sh v1`, `curl/perf2html_diff.sh v1`),
checksum label and manifest script name are settings.

## 4 Report layout

```text
OUTDIR/  index.html (overview)  <test>/{index.html,flame-graph/,heat-map/,
perf-tool/,raw/}  all/  assets/  flame-graph-app/  sources/  README.md
MANIFEST.txt
```

`raw/<test>.txz` = callgrind file + speedscope JSON; `all/` = every test
merged; `README.md` copied from `dev/README.md` each run; `MANIFEST.txt`
line 1 = version string, then LABEL=VALUE.

- **"all"**: no perf log, trace or flame graph; in a full report **no
  `raw/`**; a diff's `all` has one (`all_has_archive`). A **diff report** has
  no flame graph or native timing; per-test pages have no preamble except the
  raw-data link.
- Manifest line 1 alone makes a dir a diff input (diffs can't be diffed); it
  is **written last**. **No tool opens a report whose manifest is missing or
  whose version line isn't EXACTLY expected**; errors print found and
  expected.
- **`report_begin`/`report_finish`** bracket every report-writing run.
  `report_begin` clears, creates dirs, drops the stale manifest, opens
  `$RUN_LOG`, lays down `README.md`/`assets/`; `report_finish` writes the
  manifest and echoes the `file://` URL. **A dir is cleared only if its own
  `MANIFEST.txt` proves we wrote it**; a populated dir without one is
  refused, as is `--artifacts` inside the report. `--regenerate` clears
  nothing.
- **`--regenerate` reads every row it needs in `build_manifest`**, before
  `main` drops the old manifest.
- **`checksum=`**: POSIX `cksum` over every file but the manifest,
  `LC_ALL=C` sorted, relative paths; **re-verified whenever a tool opens a
  report**. `home_dir_check` fails on `$HOME`. `checksum_compute` and
  `_REPORT_CHECKSUM_COMMAND` are separate **on purpose - don't merge**.
- **Pages are deterministic** - same input, byte-identical output.
- **One `tar.xz` per test**, named after its directory, `tar` with
  `--sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner`.
- A diff overview reads `--diff-profile NAME=FILE`, not `raw/`.

**Shared once and linked**, never inlined. Asset hrefs come only from
`theme.shared_href(depth, name)` (overview 0, summary 1, heat map/flame 2).
Stylesheet is generated (`Theme.css()`). Pages use **classic
`<script src>`/`<link>` only** - no `fetch()`, no ES modules.

**`sources/`**: each file is `source_name()` (display path,
non-alphanumerics → `_`, + `.js`); `FileModel.source` is that file name,
resolved via `source_text(file_path)`. `flame_app_install` fails unless each
glob matches exactly one file. `page_scripts()` makes a bad href fail loudly.

## 5 Diff semantics

- Every number is **MODIFIED - BASELINE per (function, file, line)**, never
  per (file, line).
- The delta is callgrind format with **no `calls=`** → no call columns
  (`HAS_CALL_GRAPH`). Callers come from the synthesized callers JSON
  (`callgrind_diff.py --callers-output`), keyed by `<fn>` and
  `<fn>\n<display path>\n<line>`, baselines included.
- **Every share divides by that thing's own baseline**: `(new - old)/old`.
  1→0 = -100%, 90→100 = +11.1%, 1→1 = 0% (empty). New in modified =
  **infinite share** (`inf`/`Infinity`, `▲∞%`, heat-clamped) - never a
  finite substitute.
- **`events` = recorded counters only.** `costs_fit()` pads, trims trailing
  zeros, stores no derived slot. `callgrind.counter_value()` is the door.
  Ranking and heat use `abs()`.
- `profile_magnitudes()` (Σ|delta|) feeds `heatMapTotals.totals`, not share
  denominators. `summary:` = signed total (self-check holds).
- **Core vs diff split**: `BuildReport.test`/`.diff_test`,
  `CallgrindToHeatmap.model()`/`.diff_model()`, heat-map JS diff overrides
  in the one `if (IS_DIFF) {...}` block.

## 6 `dev/scripts/` conventions

- **79 columns is a hard max** for all `dev/` source; split `echo` text,
  fenced `.md` blocks and long template literals by hand. Unrelated to the
  80-column source view (`HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS`) - never change
  it to match.
- **A comment block is max 2 lines**; 3 is an error (`comment_block_scan.py`,
  `_COMMENT_BLOCK_MAX_LINES`). Blocks = consecutive whole-line comments. A
  file's opening header is exempt. Longer reasoning goes into `DECLAUDE.md`.
- **ASCII plus `≈ ∞ ▲ ▶ ▼ …`** (`_SOURCE_SCAN_ALLOWED_NON_ASCII_CHARS`),
  **written literally**, never as entities (double-escaping, broken
  `text.length` math). The scan covers `dev/` source only
  (`_SOURCE_SCAN_FILE_EXTENSIONS`, `README.md`), runs before `batch_run`, and
  prunes `__pycache__`, artifacts dir (`_SOURCE_SCAN_SKIPPED_DIRS`) and
  `*_report`
  (`_SOURCE_SCAN_SKIPPED_DIR_SUFFIXES`).
- Reformatting `heatmap.*`, `frame.js`, `flame_bootstrap.js`, `theme.css`,
  `theme.js` changes reports. Text echoed into `perf-tool/output.txt` is page
  content.
- **No comments in `scripts/` page assets**; elsewhere one
  `# <Name> - what it is` above every class/function and one `#` line above
  every field; no trailing comments, no docstrings.
- `event` → `counter` everywhere except callgrind's `events:` and the `e=`
  URL key. **No renaming campaigns.**
- One enclosing class per Python script holds every non-exported function.
  **`import X` only**, one alphabetical line per block; the only `from`
  forms: `from __future__ import annotations`, `collections.abc` and
  `typing`, each alphabetical. pyright at **0 errors**; costs are
  `callgrind.Costs`, summed via `costs_add`.

### 6.1 `settings.py`

**The whole configuration surface** (beside `ui_strings.js` for UI words);
single-file use is no reason to keep a setting elsewhere.
`RANKING_COUNTER_NAME` is what every table ranks, colours and divides by.
"settings", never "constants". `SCREAMING_SNAKE`, full broad-to-narrow
plain-word path, two words min, unit suffix (`_PX`, `_MS`, `_PERCENT`,
`_SHARE`, `_CHARS`, `_BYTES`).

- Settings first, then `SettingsReader` (its constants carry `_`); the cut
  is `_SETTING_NAMES`. `_is_setting_name()` **strips** a leading underscore
  on purpose.
- **Stays out**: format facts, class instances, derived values, anything
  only verification reads (settings ship in every report).
- **Declaring**: annotation + empty sentinel of that type, then
  `settings.load_into(__name__)` before anything else. Sentinel is never
  read; it keeps ruff `F821` and pyright `reportUnboundVariable` **on - do
  not turn them off**. `load_into()` runs `match_check`, `sentinel_check`,
  `type_check`. No accessor, no conversion. A file's own constants go below
  the call. `E401`/`I001`/`E501` stay off.
- **The browser gets every setting**: `settings_script_write()` serializes
  the module as frozen JSON, linked before every reader; no allow-list, so
  every setting must be JSON-serializable. `settings_handler.js` is read
  with a local `open()`, **never `theme.asset_text_read()`** (cycle).
- **JS**: `settings("NAME")` throws on unknown names; lexical `const`, not
  `window`. Each `.js` resolves each setting once into a same-named `const`
  at the top of its IIFE, above its own constants - **never in a loop or
  render path**. Any number/colour/key/bound a `.js` would spell is a
  setting.

### 6.2 `callgrind.py` - the one parser

- `profile_load(path)` exits unless the self-check ratio is **1.0000**.
- `path_norm() -> PathInfo(display, local, group)` is the one resolver; no
  `--repo-root`. Functions keyed by **name**.
- Derived counters from `settings.DERIVED_COUNTER_TERMS`: `D1m`, `DLm`,
  `L1m`, `LLm`, `Bm`, `CEst` (= Ir + 10·L1m + 100·LLm). No coefficient or
  counter key in code. Adding a counter = `settings.py` + description in
  `ui_strings.js` and `README.md`.
- No Python names what a counter is called; descriptions come from
  `ui_strings.js` (`HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX` + key
  lowercased).
- Uncalled `function_entry` = **first** cost line in its home file, not the
  lowest line.

### 6.3 Other scripts

- **`build_report.py`**: tables name `_RANKING_COUNTER_NAME`, no fallback
  (`Profile.value()` raises `KeyError`). Rows are
  `ManifestRow`/`ManifestBlock`, never "header".
- **`callgrind_diff.py`**: `counters_check()` is a hard error naming both
  lists. `--callers-output` required; name, flags, JSON keys are contract.
- **`callgrind_to_heatmap.py`**: `render()` substitutes `__SCRIPTS__`
  **before** `__DATA__`, never rescanned. Order:
  `theme.page_preamble_scripts()`, `sources/`, `ui_strings.js`, `theme.js`,
  `heatmap.js`. Head from `theme.page_document` (`extra_css`,
  `body_holds_scripts`).
- **No multi-line HTML/CSS/JS literal in a generator** - real files in
  `scripts/` via `theme.asset_text_read()`. `flame_bootstrap.js` keeps bare
  `__NAME__`/`__DATA__` and **polls** for `window.speedscope`.
- **`cyg_callback.c`**: `next` stays a pointer, `end` a variable (hot path
  11/12 instructions). The `buildid` lines' path is a **`realpath`**, not
  `dlpi_name`. **`CYG_CALLBACKS_MAGIC` = `trace_to_speedscope.py`'s
  `_MAGIC`** - change both. Single-threaded.
- **`trace_to_speedscope.py`**: busiest run's first
  `FLAME_GRAPH_MAX_RECORDED_CALLS` (200) calls; retune if a test's shape
  changes. Refuses an object whose build-id moved (`buildid_verify`) - run
  it before rebuilding the trace tree. Inlined helpers are frames.
- **`validate_report.py`** greps pages for three contract JS names:
  `loadFileFromBase64`, `var document_base64 = "..."`,
  `report_ui.layout_activate` - rename one and every page fails.

### 6.4 `ui_strings.js`, `error_overlay.js`, JS names

**`ui_strings.js` is the whole UI vocabulary**, keyed `str_*`, loaded before
its readers. `text_of(id)` and `settings(name)` throw on unknowns (→ error
page, deliberately). Strings with numbers are one entry with a placeholder.
Out: boundary names, number notation. `heatmap.html` holds none.
`(no recorded caller)` stays in Python, matching `str_no_caller` by hand.

**`error_overlay.js`** replaces the document on uncaught `error`/
`unhandledrejection`; **first script on every page**
(`theme.page_preamble_scripts()`), before `ui_strings.js` and settings, so
it resolves strings at render time and keeps inline colours. A thrown
message is tokens: `str_` key + `{N}` args (`format_or_raw`); **any failure
prints the raw message verbatim**. **`file://` paths are truncated to the
report root** (privacy). **An error owns the whole tab** (posted up as
`report_ui: "report_error"`) and **touches neither `history` nor the URL** -
no `#report-error` marker. `manifest_script_write` ships
`assets/report_manifest.js` (`window.report_manifest`, every row but
`checksum=`).

**Names**: `snake_case` is ours; **camelCase is owned by the browser or
Python** (DOM, CSS class, `data-*`, storage/URL key, TypedDict key) - can't
be renamed freely. `window.report_sources` is keyed by display path, read
only by `source_text()`. Markers `__NAME__`, `__DATA__`, `__SCRIPTS__`,
`__APP_CSS__`, `__APP_JS__`, `__PROFILE_JS__` - **never rename**. An inline
string literal in `.js` is a boundary name by definition.

## 7 Why the heat map exists

`-O2` inlines small statics into callers, so function tables misattribute;
the heat map shows cost per line. Cross-check with
`callgrind_annotate --show-percs=yes`. `/* perf #N: X.XX% */` comments in
`lib/` are stale - drop before upstreaming.

## 8 Look and feel

One dark theme, Monaco/monospace. **Every `dev/` page length is a design
pixel**: design width `DESIGN_COORDINATES_WIDTH_PX` = 1920, fitted to the
window by `theme.js`'s `design_scale_apply()` (one `zoom` on `:root`, every
resize). **Never retune a length by looking at one screen.**

- The `scale:` slider multiplies the fit (`DESIGN_SCALE_*` settings,
  multipliers never shown); `design_scale_travel_set()` is the door, and a
  change resets column widths.
- Unzoomed exceptions: `window.inner*`/`documentElement.client*` (convert
  via `design_px()`), and `vh` - **use `--design-vh`**. A framed document
  scales by 1. **Width media queries can't fire** - don't add one.
- **No decorative borders, no tooltips** (no `title=` anywhere except
  `<iframe title="report page">`).
- `--bg` = slate dark darkened 8% via `Theme.shade()`
  (`THEME_COLOR_ROLE_BACKGROUND_SHADE_FACTOR`) - change it only there.
  Heated cells paint their stop opaque. `THEME_COLOR_PAIR_ENTRIES`/
  `THEME_COLOR_PAIR_NAMES` must match in length.
- **Stylizing the heat map is forbidden.** `HEAT_COLOR_LOGO_STOPS` is the
  user's palette; a cell paints the stop itself. `ramp_channels_at()` is the
  one interpolation (callers `cell_style()`, `logo_color_at()`), ramp read
  via `settings("HEAT_COLOR_LOGO_STOPS")`. **No alpha, fade or blend**; the
  alpha settings must not return. Fix mappings that contradict docs; **never
  retune stops/curves/contrast for looks, never redesign on your own
  initiative** - propose instead.
- **`heat_of_share()` is the whole colour mapping**: clamp to
  `HEAT_COLOR_FULL_SCALE_PERCENT`, divide, curve. **Nothing measured off the
  data** - no `max_share`, no floor. A diff maps `[-100..100%]`, 0% at the
  5.5 midpoint, curve on magnitude before remap. The scale dropdown is
  curve × scope; `scale` is an entry, not a string.
- **Scope is only a denominator** (`global`, `per file`, `per function`;
  `share_in_scope()`); `heat_of_line()` uses `share_of_baseline` on
  `IS_DIFF`. File view only. A diff has one scope, `per line`.
- **README's "Reading a Diff Report" specifies diff notation**;
  `NumberFormat` and `theme.js` follow it.
- Column widths are exact `ch`, never persisted, **never narrower than the
  title** (`column_widths()`, `table_render()`); `grow_column_fill()`
  measures `nearest_scroller()`, not `window.innerWidth`.
- **Counter descriptions**: `ui_strings.js` `str_counter_<key>` and
  README's "Callgrind Counters" table are **byte-identical per key**, all 19;
  Python is not a third place. `<select>` width = longest
  `"<desc> / <key>"` (42 ch).
- Counter lists are not zero-filtered; zero columns render blank. No
  row-wide heat. Only `th` is sticky - never measure the thead.

### 8.1 Number notation

`2.1K`/`2.0G`, `63.2%`, `<0.01%`; exact zero is empty. Floor:
`NUMBER_SMALLEST_PRINTED_PERCENT` (0.01), the only floor. Notation strings
(`<0.01%`, `≈0.00%`, `>1000x`, `∞%`) stay inline.

**A diff never prints `+`.** Shares lead with an arrow and keep a negative's
sign (`▲11.1%`, `▼-100.0%`); amounts use the **ASCII hyphen** for minus.
Under 0.01% → `▲≈0.00%`; zero baseline → `▲∞%`. Past 100% → multiple
(`▲1.30x`); at/past `NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES` (999.99) →
`>1000x`, unsigned. Multiples are rise-only. `theme.js`'s `report_ui` and
`theme.py`'s `NumberFormat` match by hand (verified on README's rows); both
read the bound as a setting.

### 8.2 Frames and URL state

Overview frames a test summary, which frames its heat map/flame graph; both
run `FRAME_JS`, deciding by `report_ui.is_framed`. **`theme.js` is the
utility library; `frame.js` is only the thin top-level controller** -
cross-frame helpers (`is_framed`, `parent_post`, `parent_listen`,
`hash_publish`) stay in `theme.js`.

- **URL is the whole state.** Frame `#<view>[/<inner hash>]`; heat map
  `f=<file>`, `f=<file>&l=<n>`, `fn=<name>`, none = home, `&e=<counter>` when
  >1 counter. Only `heat.scale`, `heat.sort`, `view.scale` (top-level
  slider, 0..1) and `split.<pane>` are stored.
- **Storage is versioned**: `STORAGE_VERSION` = `perf2html v2` under
  `STORAGE_VERSION_KEY` = `perf2html.version` (bare string). Mismatch →
  sweep owned keys. **A new key must go in `STORAGE_OWNED_KEYS` or
  `STORAGE_OWNED_PREFIXES` (`split.`).** All four are settings.
- `FRAME_JS` loads via `location.replace(link_href + (inner_hash || "#"))` -
  **never `iframe.src`**; `"#"` not `""`.
- `hash_changed` is posted by the heat map and by a framed `FRAME_JS` (the
  middle level relays up), both via `report_ui.hash_publish()`.
- Regression test: test → view → file → line → counter; outer hash ends
  `#<test>/heat-map/f=<file>&l=<n>&e=<ev>` and reloads all three levels.

## 9 Measurement and byte facts

- Callgrind `calls=` are aggregated. **Never feed `--separate-callers=N`
  output to the summary/heat map.**
- **Flame graph for shape, perf log for speed** (hook cost is in traced
  durations). Native speed moves ~1.9× with host state - compare within one
  run. uftrace is not installed.
- Nothing is deleted to shrink reports; speedscope's base64 is not ours.

## 10 Current state

No `lib/` change has come out of the profiling yet. Per-test numbers live in
the reports, not here.

## 11 Workflow

1. Quick read: `perf <test>`, median of 3-5; **real numbers only from a
   pinned `build-relwithdebinfo`**.
1. One focused change, rebuild, re-run, then
   `dev/perf2html.sh --report=perf2html_modified_report` and
   `dev/perf2html_diff.sh`. Keep only changes that measurably help **and**
   leave test output unchanged. Record before/after in "Current state".
1. After any `dev/` edit: **`dev/scripts/enforcer.sh --regenerate`**, one
   run. Leave `--regenerate` off only after `perf` was re-linked; wrongly
   passed, it refuses in under a second.
1. **Changing the scripts is verified by all three modes, in order**
   (11.1); the daily loop is mode 3 only.
1. Before final: `tests/runtests.pl` (perf doesn't check correctness).

### 11.1 The three debug modes

Each proves a different property; running one verifies a third.

1. **`enforcer.sh`**: cold, deletes everything, measures. Proves measuring
   and deletion.
1. **`--keep-artifacts`**: same, keeps the artifacts dir. Proves recordings
   survive.
1. **`--regenerate`**: rebuilds pages from mode 2's recordings. Proves
   reuse.

**Run in that order** (each mode's precondition is the previous one's
postcondition), ≈ 6 min on warm ccache; `dev/scripts/test_all.sh` does.
