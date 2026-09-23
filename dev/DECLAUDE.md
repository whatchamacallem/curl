# curl perf work (compressed)

Compressed `DECLAUDE.md`. The full file is authoritative - read it before
changing a topic that is one line here.

## 1 Rules

1. Keep `DECLAUDE.md` current in the same change as any
   tooling/layout/theme/findings change. `CLAUDE.md` symlinks to it. Facts,
   commands, numbers, gotchas. No line numbers - name an identifier.
   **A-list only**: it goes in if a session that had not read it would get it
   wrong, waste an hour, or break a contract. Over **40,000 bytes**, say so
   and leave it alone. **Never compact it on your own initiative.**
1. **`dev/README.md` is the user-facing contract and control surface.** Code
   follows README, never the reverse. A session finding them disagreeing
   fixes the code or asks, and never silently edits README to match. Only
   README edits the user asked for in that session.
1. `dev/` is throwaway profiling tooling: one shared parser, one shared theme,
   no dead code, no duplicate systems. Everything a script writes opens from
   `file://` with nothing fetched at view time.
1. **No fake data.** Every page value is a recorded measurement or plain
   arithmetic on one (sum, difference, share, `CEst`). No apportioning,
   interpolation or "plausible" stacks. If a tool can't supply what a view
   needs (callgrind: per-call stacks/time), the view isn't built.
1. **Nothing test-specific, ever.** No test names, file lists or per-test
   cases anywhere in `dev/`; every view is built for every test in `TESTS_C`.
   Examples read `<test>`/`<file>`.
1. Never "meta" - that is a "header" or a "manifest". No "events", "metrics"
   or "stats", only **counters**.
1. More than one goal in a run → conclude with a checklist of what was and was
   not accomplished, plus any relevant bug reports.
1. New identifiers: at least 2 unabbreviated english words, ideally one noun
   and one verb.
1. **A value written down twice and "kept in step" is banned.** A number,
   colour, key, bound or named two files both need is **one setting** the two
   read from `settings.py` or `settings.py`.
1. All communication involving multiple items follows ISO 2145, Numbering of
   divisions and subdivisions in written documents.

## 2 Commands

```sh
dev/perf2html.sh [--verbose] [--keep-artifacts] [--regenerate]
    [--report=DIR] [--artifacts=TMP] [cmake_flags...]
dev/perf2html_diff.sh [--verbose] [--keep-artifacts] [--regenerate]
    [--artifacts=TMP] [baseline-dir] [modified-dir] [report-dir]
dev/perf2html_batch.sh [--verbose] [--keep-artifacts] [--regenerate]
    [--artifacts=TMP] [--target-dir=DIR] [cmake_flags...]
dev/scripts/reformat.sh [--check] [--verbose] [report-dir]
```

```sh
cmake -S . -B build -G Ninja -DCURL_USE_LIBPSL=OFF
cmake --build build --target perf      # EXCLUDE_FROM_ALL, must be named
taskset -c 3 ./build-relwithdebinfo/tests/perf/perf <test> [loops]
```

- **Verification is two runs, in this order:** `perf2html_batch.sh` measures
  and generates, then `reformat.sh` lints, formats and validates. **The batch
  runs no checks at all**; verifying a build invokes **both**.
- `--regenerate` rebuilds all three reports' pages from the last run's
  recordings, if the artifacts dir survives - it **defaults to
  `perf2html_temporary_artifacts/` in the parent directory of the report**,
  `--artifacts=TMP` overriding it in all three `.sh`.
- `--target-dir=DIR` (default CWD) holds the three **default-named** reports -
  **the batch cannot name them**. **Every batch argument that is not its own
  option is a cmake flag.**
- `CURL_USE_LIBPSL=OFF` is the only intentional deviation. **Never profile
  `./build`** (`-O0`: inlining differs, attribution wrong) - use
  `build-relwithdebinfo`. **Always pin**: WSL2 noise ~106% unpinned, \<1-3%
  pinned.

## 3 The four scripts

`perf2html.sh` builds + profiles + generates one report; `perf2html_diff.sh`
measures nothing and subtracts two reports' `raw/` archives;
`perf2html_batch.sh` runs baseline, modified (`-D CMAKE_C_FLAGS=-Os`), diff;
`reformat.sh` lints, formats, validates. In both, **every step runs even
after an earlier one failed**.

- **`--verbose` is additive, in all four**; `log_verbose()` is the one
  function deciding whether a **line** is printed, and the only other
  readers of `$VERBOSE` are `shared.sh`'s two **stream** routers,
  `child_capture()` (tee or redirect, chosen before the child runs) and
  `log_verbose_file()` (a file a step already wrote, appended to `$RUN_LOG`
  and shown too when verbose). **No script outside `shared.sh` may test
  `$VERBOSE`**, **no function in `dev/*.sh` may wrap `printf` without
  adding logic**, and quiet prints **whole lines only**.
- `perf2html.sh` default DIR is `perf2html_baseline_report`, or
  `perf2html_modified_report` when cmake_flags are given - **after a
  _source_-only change pass `--report=perf2html_modified_report` yourself.**
- **`usage_show`'s heredoc is a script's only usage text.** Never restate it
  in the file header, which says what the script is and nothing more. It and
  `README.md`'s option lists are the one pair kept in step by hand.
- `toolchain_check` is the **only** toolchain check the user-facing scripts
  have, collecting **every** missing tool before exiting 1, one
  `tool -> official install command` each, **official instructions only**
  (missing `perf` → use `linux-perf`, not `linux-tools-generic`).
  **`reformat.sh`'s tools are out of scope.**
- `reformat.sh` **takes no path argument**; its one optional argument is a
  report dir, recognised by `MANIFEST.txt` line 1, which also decides
  `--diff`. **It is the only `validate_report.py`, `pyright`, `ruff` and
  `prettier` call anywhere**, and with the batch is the generators' test
  suite. It sources **both** `settings.sh` and `shared.sh`, like the other
  three - it reads the two `REPORT_MANIFEST_VERSION_*` strings, and without
  the first no report can match its own version line.
- **`reformat.sh` reaches source and nothing else**, collected through
  `files_of()`, the **one door** every stage uses: `*.sh` under `dev/`,
  `*.c *.h` under `src/`, `*.py *.js *.css *.html` under `scripts/`, and
  **`README.md` is the one `.md`** (`_MARKDOWN_NAME` - an allow-list, so
  `DECLAUDE.md` is out by not being named). **A config file is untouched
  by every stage** - no `.json`, `.yml` or `.toml` is formatted, linted or
  column-checked; `.prettierrc.json`, `ruff.toml` and `pyrightconfig.json`
  live in `scripts/`, `.clang-format` in `src/`.
  **`reformat.sh` always passes `--config`**, so a config need not sit where
  a tool's own upward search would find it.
- **The batch owns every deletion of the artifacts dir** - it passes
  `--keep-artifacts` down so a child can't unlink the batch log mid-run; a
  failed flagless batch _keeps_ it. **`--keep` is gone.**
- **"raw" means only the report's own `<test>/raw/` and its `raw-data` page
  links**; temporary recordings are "artifacts" everywhere else.
- Profiling:
  `taskset -c 3 valgrind --tool=callgrind --cache-sim=yes --branch-sim=yes`
  plus `--LL=16777216,16,64` in `run_one` (Valgrind's LL cache auto-detects as
  direct-mapped and overstates conflict misses). Timing is a _separate_ native
  pinned `perf stat -x, -e cycles:u,instructions:u` run - **its `Time*` lines
  are the only valid speed number**, never callgrind's wall clock.
- Trace tree `build-instr` = same flags + `-finstrument-functions` +
  `dev/src/cyg_callback.c`; whole build instrumented, no file list.
- The verbose tee sits behind `if ! { ...; }` so `pipefail` can't take the
  failure before `PIPESTATUS[0]` is read. `clock_microseconds()` strips
  non-digits. That tee is in `shared.sh`'s **`child_capture`**, the one
  runner: it records the child's code in `CHILD_EXIT_CODE` rather than
  taking it, and **reports through globals, never stdout** - verbose's tee
  already owns stdout, so a `$(child_capture ...)` would capture the
  child's own output along with the code. Two policies sit on it:
  `command_run` exits with the child's code, and the batch's `step_run`
  records the failure in `_STATUS` / `_FAILED` and returns 0 so every later
  step still runs. Both print the same tail through **`failure_tail_print`**
  (`LOG_FAILURE_TAIL_LINES` lines).

### 3.1 `settings.sh` and `shared.sh`

No env vars. **`settings.sh` holds every setting the shell reads, `shared.sh`
(sourced, not executable) every shared shell function**, each alphabetical.
`settings.sh` is **one assignment per line** because `shared.sh` sources it
**and `settings.py` parses it at import**
(`SettingsReader.shell_settings_read`,
whose result `settings.py` binds under its own names; a `-?[0-9]+` scalar
arrives as `int`). **A word may hold `$` or a command**,
but **`settings.py` neither runs nor reproduces one**: `shell_word_withhold`
binds the name to `_SHELL_EXPANDED_WORD` and records it in
`SettingsReader.expanded_names`. **Only bash may read such a word** - the
shell expands it as it sources the file, so any Python answer would be the
import's and would name a different run. So there is **no table of
expansions**, and **no `$` word is ever spelled twice**: `value_of` raises on
a withheld name, so a module declaring `TIMESTAMP` stops at import, and
`script_write()` drops it from the browser's object. A generator's stamp
arrives as the shell's `stamp=` row. A `'single-quoted'` word is literal to
both and never expanded. **Verification is bash
itself** - every script sources the file, so no character allow-list.
Hand-written, never generated. **A shell setting is a Python setting, one name
in all three languages.** **`TIMESTAMP` is a setting** (`$(date +%s)`, fixed
at profiler run time the way `__DATE__` is at compile time), which is why the
scripts declare none of their own; `--regenerate` still assigns it back from
the report's `stamp=` row. **Only a value derived from `$0` stays
per-script** (`_REPO`), as do `usage_show`, `args_parse` and the `*_DIR` they
derive. `_TESTS` comes from `tests/perf/Makefile.inc`. Grep the files for
names; notable: `PROFILE_PINNED_CPU=3`, `REPORT_RAW_ARCHIVE_SUFFIX` (`.txz`,
dot included).

**A global a script declares for itself is `_SCREAMING_SNAKE`**, leading
underscore, the way the Python keeps a private name - `_OUT_DIR`,
`_CMAKE_FLAGS`, `_STATUS`. **The underscore means "mine": the names that
cross into `shared.sh` do not carry one** - it reads `ARTIFACTS_DIR`,
`RUN_LOG`, `START_US`, `TIMESTAMP` and `VERBOSE`, and sets
`SPEEDSCOPE_RELEASE`, `RUN_LOG` (in `report_begin`) and
`CHILD_EXIT_CODE` / `LOG_LINE_FROM` (in `child_capture`).
**No `settings.sh` name ever takes one** (`settings.py`
parses that file, and a setting is one spelling in three languages), and
neither does a name the environment owns (`CMAKE_C_FLAGS`, `PERF_TRACE_OUT`).
So: underscore = this file's, bare = shared or foreign. **A `local` takes the
underscore too and stays lowercase** - `local _output _exit_code`. The
underscore is on the _variable_ only: an `awk -v max=`, a `find -name`, and
every word of a message a script prints keep their plain spelling.

**Sourcing `shared.sh` is inert** - defines names, runs nothing. **A function
there writes a caller global only where all callers agreed it is the canonical
setter, and its `#` comment names every global it sets** - `toolchain_check`
(`SPEEDSCOPE_RELEASE`), the batch's `step_run` (`_STATUS`, `_FAILED`).

**The `MANIFEST.txt` contract is `shared.sh`'s** - `checksum_compute`,
`manifest_fault_of`, `manifest_write`, `manifest_value`, `manifest_verify`,
`manifest_wanted_phrase`. **`manifest_fault_of` is the one reader**: it
echoes why a directory is not a finished report, or nothing when it holds
up, and takes **each version string line 1 may read** - naming one is how a
diff is never read back as a diff input, naming both is how `reformat.sh`
accepts either. `manifest_verify` is the hard-error policy on top;
`reformat.sh` collects the same text instead, so a broken report cannot
hide a valid one. The two version strings
(`curl/perf2html.sh v1`, `curl/perf2html_diff.sh v1`), the checksum label and
the manifest script name are **settings in `settings.sh`**.

## 4 Report layout

```text
OUTDIR/  index.html (overview)  <test>/{index.html,flame-graph/,heat-map/,
perf-tool/,raw/}  all/  assets/  flame-graph-app/  sources/  README.md
MANIFEST.txt
```

`raw/<test>txz` = callgrind file + speedscope JSON; `all/` is every test's
data merged; `README.md` is copied from `dev/README.md` every run (the "help"
link); `MANIFEST.txt` line 1 = version string, then LABEL=VALUE.

- **"all"** synthetic test: no perf log, trace log or flame graph, and in a
  full report **no `raw/`** - it reads every real test's archive; a _diff_'s
  `all` has one, the merged delta (`all_has_archive`). A **diff report** has
  no flame graph and no native timing, and its per-test pages have no preamble
  **except** the raw-data link to their own archive.
- `MANIFEST.txt` line 1 is the _only_ thing making a directory a diff input
  (a diff names `perf2html_diff.sh`, so diffs can't be diffed), and is
  **written last** → an aborted run leaves none. **No tool may open a report
  whose manifest is missing or whose version line is not EXACTLY the expected
  string**; the error prints **both found and expected**.
- **`report_begin` and `report_finish`** are the head and tail of every run
  that writes a report. `report_begin` clears what a previous run left,
  creates the directories, drops the stale manifest, opens `$RUN_LOG` and
  lays down `README.md` and `assets/`; `report_finish` writes the manifest
  last and echoes the `file://` URL. **A report is cleared only on the
  proof that we wrote it** - its own `MANIFEST.txt`. A populated directory
  without one is refused, never emptied, so a `--report=DIR` naming a
  user's path is safe; an `--artifacts=TMP` **inside** the report is
  refused for the same reason. **`--regenerate` clears nothing**.
- **`--regenerate` reads every row it wants in `build_manifest`**, which runs
  before `main` drops the previous manifest. A new row a regenerated run needs
  is read there, never later.
- **`checksum=` row**: POSIX `cksum` over every file **except the manifest**,
  list `LC_ALL=C` sorted, paths **relative** to the report dir.
  **Re-verified every time any tool opens a report**; mismatch is a hard
  error. Paths in pages/manifest are **relative**; `home_dir_check` fails on
  `$HOME`. `shared.sh`'s `checksum_compute` and `validate_report.py`'s
  `_REPORT_CHECKSUM_COMMAND` spell that pipeline **separately on purpose -
  not the banned twin**: a check importing what wrote the checksum would
  agree by construction and could never catch it being wrong, which is the
  only thing it is for. **Do not "de-duplicate" them.**
- **Generated pages are deterministic** - same input ⇒ byte-identical output,
  so a page diff is always code; only `stamp=` and re-measured time vary.
- **Raw data compressed, one `tar.xz` per test**, named after the
  **directory** holding it, never the page title. The `tar` line needs
  **`--sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner`** or two runs
  differ.
- `perf2html_diff.sh` unpacks both inputs **once** in `profiles_extract` and
  **synthesizes the `all` row**. **A diff overview reads its rows from
  `--diff-profile NAME=FILE`**, the working subtracted profile, not `raw/`.

**Shared once and linked**, never inlined. **No generator takes an assets
href** - it is `theme.shared_href(depth, name)`, `depth` fixed by layout
(overview 0, summary 1, heat map/flame graph 2) and nothing else. **A page
that must stand alone is a new flag with a caller** - the last one, a diff's
`--single-test-report`, was deleted as unreachable. **The
stylesheet is generated, not copied** (`Theme.css()`), and
pages are **classic `<script src>`/`<link>` only** - `fetch()` or an ES module
would need a web server and is what this must never become.

**`sources/`** names each script `source_name()` (display path,
non-alphanumerics → `_`, plus `.js`); a `FileModel`'s `source` is that **file
name**, not the text, resolved via `source_text(file_path)`.
`flame_app_install` **fails unless each glob matches exactly one file**
(`*.woff2` must sit beside the CSS naming it). `page_scripts()` reads every
`src=`/`href=` a page names, so a **missing or misspelled href fails loudly**.

## 5 Diff semantics

- Every number is **MODIFIED - BASELINE, per (function, file, line)** - never
  per (file, line) alone, which hands half an inlined function's cost to its
  neighbour.
- The delta is plain callgrind format with **no `calls=` lines** → no call
  graph → no call columns/caller tables in the heat map (`HAS_CALL_GRAPH`).
  Calls/callers come from the **synthesized callers diff**, a separate JSON
  beside the delta (`callgrind_diff.py --callers-output`), keyed by `<fn>` and
  `<fn>\n<display path>\n<line>`; baselines ride there too.
- **Every share divides by that same thing's own baseline cost**, never a
  global budget: `(new - old)/old`. 1→0 = -100%, 100→90 = -10%, 90→100 =
  +11.1%, 1→1 = 0% (rendered empty). A thing the baseline never had is an
  **infinite share** (`float("inf")`/`Infinity`), printed `▲∞%` and
  heat-clamped at full scale - **never a substitute finite number**.
- **`events` is the recorded counters and nothing else.** `costs_fit()` pads
  to recorded width, trims trailing zeros, stores **no derived slot** - a
  slot's index never moves. `callgrind.counter_value()` is the one Python
  door. Ranking and heat are `abs()`, so winners and losers interleave.
- **Per-line baselines are wildly skewed**: median line ~18 Ir, 72% under
  1,000, only ~1.8% exceed ±1000%. Hence no measured maximum - the
  `HEAT_COLOR_FULL_SCALE_PERCENT` clamp holds those lines.
- `profile_magnitudes()` (Σ|per-function line delta|) is what
  `heatMapTotals.totals` carries, **not** what shares divide by.
- `summary:` in the delta = the signed total, so the parser's 1.0000
  self-check holds on it too.
- **Core vs diff split** (the non-diff path stays byte-checkable against an
  older generator): `BuildReport.test` vs `.diff_test`,
  `CallgrindToHeatmap.model()` vs `.diff_model()`, and in heat-map JS every
  diff override in the one `if (IS_DIFF) {...}` block.

## 6 `dev/scripts/` conventions

- **79 columns is the hard max** for every line of `dev/` source, every
  language, and a longer line is an **error**. Formatters cannot reach `echo`
  text, a fenced `.md` block or a long template literal - split by hand.
  **Not** the 80-column source _view_ (`HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS`),
  which **must never change to match**.
- **A comment block is 2 lines, and 3 is a formatting error**
  (`comment_block_scan.py`, `_COMMENT_BLOCK_MAX_LINES`, run by `reformat.sh`
  as the `comments` stage). A block is consecutive **whole-line** comments,
  so a blank line splits one and a trailing comment is invisible. **A file's
  opening header is exempt** - line 1 to the first line of code - which is
  what keeps `cyg_callback.c`'s format reference, `settings.sh`'s grammar and
  `reformat.sh`'s coverage table. Longer reasoning moves **here**, not into a
  third line; the other fix is to name the thing above and push the "why"
  onto the code below it.
- **ASCII plus a short allow list**: `≈`, `∞`, `▲`, `▶`, `▼`, `…`
  (`_SOURCE_SCAN_ALLOWED_NON_ASCII_CHARS` in `validate_report.py`), **written
  literally** - an entity would be double-escaped by `html_escape()` and its
  length corrupts the `text.length` column math. Scanned is an allow-list
  too (`_SOURCE_SCAN_FILE_EXTENSIONS` plus `_SOURCE_SCAN_FILE_NAMES` =
  `README.md`), so `DECLAUDE.md` and every config file are out.
- Reformatting `heatmap.*`, `frame.js`, `flame_bootstrap.js`, `theme.css` or
  `theme.js` **changes a report**, so a page diff is expected. Text a script
  `echo`s into `perf-tool/output.txt` is _page content_ - split into extra `#`
  lines rather than overflow.
- **No comments at all in the `scripts/` page assets**; elsewhere one
  `# <Name> - what it is` above every class and function and one `#` line
  above every field, never trailing, never docstrings.
- **Names left alone:** `profile`, `stamp`, `loops`; `stamp` is a **boundary
  name**. **`event` was renamed to `counter` throughout** - only callgrind's
  `events:` line and the `e=` URL key keep the old spelling. **Do not open a
  renaming campaign.**
- One enclosing class per script holds **every** non-exported function.
  **`import X` only**, packed one alphabetical line per block - hence
  **`E401` and `I001` are off in `ruff.toml`**, whose comment is the rule's
  long form. **Three `from X import Y` forms are allowed and no others**:
  `from __future__ import annotations`, and the names taken from
  `collections.abc` and from `typing`, each on its own line below the first
  plain line, names spelled alphabetically. pyright gated at **0 errors**;
  cost vectors are `callgrind.Costs`, summed only via `costs_add`.

### 6.1 `settings.py`

**The entire control surface for the tools' configuration**, beside
`ui_strings.js` for the UI's vocabulary. **Single-file use is not a reason to
keep a setting elsewhere.** `RANKING_COUNTER_NAME` is the counter every table
ranks, colours and divides by. **"settings", never "constants"**, every
language. **One setting, one spelling, all three languages**
(`SCREAMING_SNAKE`); name = **full plain-word path, broad to narrow**, min two
words (`HEAT_MAP_TREE_INDENT_PER_LEVEL_PX`, not `tree_indent`), unit suffix
kept (`_PX`, `_MS`, `_PERCENT`, `_SHARE`, `_CHARS`, `_BYTES`).

- **`settings.py` (imported, never run) holds every setting, then the
  `SettingsReader` that checks and assigns them** - settings first, the
  reader's own constants below them, the order every file reading a setting
  is written in. **The line between the two is `_SETTING_NAMES`**, taken
  right after `shell_settings_read()` binds the shell's: every setting is
  bound by then and not one of the reader's constants is, and `all_named()`
  and `match_check` read that frozenset, never the live namespace. **A
  setting is spelled bare and the reader's own carry the leading
  underscore** (`_SHELL_*`, `_SENTINEL_*`, `_SETTINGS_DIRECTORY`) - the same
  "underscore means mine" as the shell, and what keeps them out of both the
  browser's object and every module's load. `_is_setting_name()` still
  **strips** the underscore, because a _declaring_ module spells its
  declaration `_RANKING_COUNTER_NAME`; do not make it stop.
- **Stays out**: format facts nobody may retune, class instances, derived
  values, **and anything only verification reads** - so `VALIDATE_*`, the two
  `ReportLayout`s and `SOURCE_SCAN_*` are `validate_report.py`'s own
  constants. **Verification may read production settings**, never copy one.
- **A file declares what it reads; `load_into()` assigns**: an annotation
  naming the type **plus an empty sentinel of that type**, then
  `settings.load_into(__name__)`, before anything else. **The sentinel is
  never read**; it binds the name, which is what lets ruff `F821` and pyright
  `reportUnboundVariable` stay **on** - **do not turn either off again**.
  `load_into()` walks every `SCREAMING_SNAKE` name bound and stops the run at
  import via `match_check`, `sentinel_check`, `type_check`, in that order.
  **No accessor, no conversion** - it is the one door.
- **Settings come first**; a file's own constants go **below** the call.
  `E401`/`I001` stay off for the import shape, `E501` for reformat.sh's own
  column check.
- **The browser gets every setting, wholesale**: `settings_script_write()`
  serializes the module as one JSON literal, **frozen to its leaves**,
  **linked before every reader**. **There is no list of what the pages may
  see and none may come back** - a `.js` file reads a setting by naming it,
  and nothing in Python changes when it starts or stops. **A setting is
  therefore JSON-serializable**; anything that is not belongs below the cut,
  where it is not a setting. **The one exclusion is a `settings.sh` word bash
  expands** (`TIMESTAMP`), held back by `SettingsReader.expanded_names` for the
  reason `shell_word_withhold` gives - only bash may read one.
  One value, one id, **no hand-matched twin** - why `FLAME_GRAPH_APP_DIR_NAME`,
  `FLAME_GRAPH_APP_FILE_GLOBS` and `REPORT_RAW_ARCHIVE_SUFFIX` live once, in
  `settings.sh`. The freeze + reader is `settings_handler.js`, which
  **`script_write()` reads with a local `open()` against
  `_SETTINGS_DIRECTORY`, never `theme.asset_text_read()`** - `theme.py` does
  `import settings`, so importing theme there would cycle.
- **`settings` is a reader function, not an object**: `settings("NAME")`
  throws on a name the module does not hold; **lexical `const`, not a `window`
  property**. **A `.js` file resolves each setting once into a local `const`
  of the same name, at the top of its IIFE, above its own constants** -
  **never call `settings()` in a loop or render path**. **A number, colour,
  key or bound a `.js` file would otherwise spell for itself is a setting** -
  `theme.js` and `frame.js` keep none.

### 6.2 `callgrind.py` - the one parser

- `profile_load(path)` exits unless the self-check ratio is exactly
  **1.0000** - re-verify after touching; cost conservation only.
- `path_norm() -> PathInfo(display, local, group)` is the one path resolver;
  no `--repo-root` flag exists. Functions are keyed by **name**, so one symbol
  in two objects is one function.
- Derived counters off `settings.DERIVED_COUNTER_TERMS`: `D1m`, `DLm`, `L1m`,
  `LLm`, `Bm`, `CEst` (= Ir + 10·L1m + 100·LLm). **No coefficient and no
  counter key is spelled in code** - only `settings.py`, and this file is
  their one reader. Adding/dropping a counter = an edit there plus its
  description in `ui_strings.js` and `README.md`.
- **No Python spells out what a counter is called**; pages render descriptions
  from `ui_strings.js` via `HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX` +
  name lowercased. `counter_value()`/`counter_names()` are the door for a
  **stored** vector.
- `function_entry` for an uncalled function = the **first** cost line
  callgrind wrote in its home file; lowest line number does not - inlined
  helpers sit above the entry.

### 6.3 Other scripts

- **`build_report.py`**: **every table names `_RANKING_COUNTER_NAME`
  directly, no fallback** - `Profile.value()` raises `KeyError` on a counter a
  profile can't supply. LABEL=VALUE rows are `ManifestRow`/`ManifestBlock` -
  **never call any just "header"**.
- **`callgrind_diff.py`**: `counters_check()` is a **hard error** naming both
  lists. `--callers-output` required; its name, flags and JSON keys are
  contract.
- **`callgrind_to_heatmap.py`**: `render()` substitutes `__SCRIPTS__`
  **before** `__DATA__`, and that result must never be scanned again. Order:
  `theme.page_preamble_scripts()`, `sources/`, `ui_strings.js`, `theme.js`,
  `heatmap.js`. The head is `theme.page_document`'s, asked for the heat map
  stylesheet with `extra_css` and told `body_holds_scripts` because
  `__SCRIPTS__` sits where its own script block would go.
- **No generator holds a multi-line HTML/CSS/JS literal** - each is a real
  file in `scripts/` read via `theme.asset_text_read()`, so **their JS is
  written plainly**. `flame_bootstrap.js` keeps bare `__NAME__`/`__DATA__`
  markers and **polls**: speedscope defines `window.speedscope` only once
  started, after its script tag ran.
- **`cyg_callback.c`**: `next` must stay a pointer and `end` a variable, so
  the hot path stays 11/12 instructions; `next == end` = not sampling. Setup
  is a constructor (incl. `memset`, so no page fault lands in a timed call).
  The dump appends one `buildid <hex> <path>` line per loaded object to the
  `.maps` copy, which is what lets a reader refuse a stale trace. **That path
  is a `realpath`**: the loader hands `dlpi_name` the soname it asked for
  (`libcurl.so.4`) while the maps lines name the file it resolved to
  (`libcurl.so.4.8.0`), and `buildid_verify` matches the two by string, so
  writing `dlpi_name` raw makes every run die "records no build-id".
  **`CYG_CALLBACKS_MAGIC` is `trace_to_speedscope.py`'s `_MAGIC`** - a header
  fact in two languages, so change neither alone. Single-threaded.
- **`trace_to_speedscope.py`** takes the busiest run's first
  `FLAME_GRAPH_MAX_RECORDED_CALLS` = 200 complete calls, hard-coded for the
  current `TESTS_C` - retune if a test's shape changes. Must run while
  `build-instr` still holds the traced binary; GCC instruments inlined bodies,
  so inlined helpers are frames. **It refuses an object whose build-id moved**
  since the trace was recorded (`buildid_verify`), so "must run while" is now
  enforced, not just documented: rebuild before converting and the run stops
  naming both ids.
- **`validate_report.py OUTDIR [--diff]`** is a structural smoke test.
  **It greps generated pages for three JS names - contract, not private**:
  `loadFileFromBase64`, `var document_base64 = "..."`,
  `report_ui.layout_activate`; rename one and every page fails validation
  while looking correct in a browser. `flame_graph_check` requires exactly one
  `evented` profile whose `exporter` is ours; `raw_archive_check` runs its
  checks **inside** each `raw/*txz`.

### 6.4 `ui_strings.js`, `error_overlay.js`, JS names

**`ui_strings.js` is the whole UI vocabulary, in one object**, keyed by a
`str_` id. **Must load before the script that reads it.** `text_of(id)`
**throws on an unknown id** and `settings(name)` on an unlisted setting - both
surface as the error page, deliberately. A string with a number is **one entry
with a placeholder**, never split at the seam. **Out**: boundary names and
number notation. **`heatmap.html` holds none.** `build_report.py` renders
server-side, so `(no recorded caller)` stays in Python, in step with
`str_no_caller` by hand.

**`error_overlay.js`** replaces the document on an uncaught `error` or
`unhandledrejection`. **It must be the first script every page links**;
`theme.page_preamble_scripts()` is the one place that order is written. It is
the **only** `.js` that may not resolve strings at IIFE top (it loads before
`ui_strings.js`), so `text_or_fallback(id)` reads at render time; **its ten
`str_error_*` entries live only in `ui_strings.js`**. `history.pushState` to
`#report-error` so **Back restores the page**. A `file://` page cannot
`fetch()` MANIFEST.txt, so `manifest_script_write` ships
`assets/report_manifest.js` into `window.report_manifest`, **carrying every
row but `checksum=`**.

**Names:** `snake_case` is ours, **camelCase means a name the browser or
Python owns** (DOM member, CSS class, `data-*`, localStorage or URL key,
TypedDict JSON key) - **it crosses a boundary and cannot be renamed freely**.
`window.report_sources` is keyed by display path and read only by
`source_text()`; break one side and every heat map silently renders "Source
not available." The `__NAME__`/`__DATA__`/`__SCRIPTS__`/`__APP_CSS__`/
`__APP_JS__`/`__PROFILE_JS__` substitution markers are matched literally by
Python - **never rename them**. **A string literal left inline in a `.js` file
is a boundary name by definition.**

## 7 Why the heat map exists

Under `-O2` small static functions inline into their callers, so the
function-level top-N table charges their cost to the caller; the heat map
shows it per line. Cross-check with `callgrind_annotate --show-percs=yes`.
`/* perf #N: X.XX% */` comments in `lib/` are stale dev annotations - drop
before submitting upstream.

## 8 Look and feel

One dark theme, Monaco/monospace everywhere. Target viewport **1366×768**.
**No decorative borders**; **no tooltips** - nothing rendered carries a
`title=`, neither `Cell` nor `Column` has a field for one, and no exact value
appears anywhere (only `<iframe title="report page">` remains).

- `--bg` = slate dark member darkened 8% via `Theme.shade()`
  (`THEME_COLOR_ROLE_BACKGROUND_SHADE_FACTOR`) - background, scrollbar track,
  minimap band all follow it, so **change it only there**. **A heated cell
  does not** - it carries its ramp stop opaque, blended over nothing.
  `THEME_COLOR_PAIR_ENTRIES`/`THEME_COLOR_PAIR_NAMES` must agree in length or
  `Theme.pairs()` fails (`HEAT_COLOR_LOGO_STOPS` exempt).
- **Stylizing the heat map is forbidden - it renders precisely as
  advertised.** `HEAT_COLOR_LOGO_STOPS` is the user's own palette, picked to
  be seen, so **a cell paints the stop itself** - `ramp_channels_at()` in
  `theme.js` is the one interpolation, between the two stops the position
  falls between, and it stops there; `cell_style()` and `logo_color_at()`
  are its only callers and the ramp reaches it as
  `settings("HEAT_COLOR_LOGO_STOPS")`, never through `__DATA__`. **No
  alpha, no fade, no blend over the background**, and no softer variant for
  the tree: the alpha settings were removed and must not come back. A
  session may fix a mapping that
  contradicts this file or `README.md`; it may **not** retune a stop, a
  curve or a contrast rule because the result would look better, and may not
  add a new visual treatment on top. **No redesign, ever, on a session's own
  initiative** - propose it and leave the code alone.
- **`heat_of_share()` is the whole colour mapping**: clamp to
  `HEAT_COLOR_FULL_SCALE_PERCENT`, divide, apply the curve. **Nothing is
  measured off the data** - no `max_share`, no per-scope scan, no
  smallest-visible floor, so a line's colour depends only on the number
  printed beside it. **Resist re-introducing a measured ceiling.** A diff maps
  `[-100..100%]` with **0% at the 5.5 midpoint**, the curve applied to the
  **magnitude before** the remap. The scale dropdown is a curve × scope
  product built at runtime; `scale` is an entry, never a bare string.
- **Scope is only a denominator**, never a colour ceiling (`global`,
  `per file`, `per function`); `share_in_scope()` is the door, `heat_of_line()`
  picks it or the diff's `share_of_baseline` on `IS_DIFF`. **File view only.**
  **A diff has one scope, `per line`.**
- **Gotcha:** `.strip .title` is `--title-bg` (teal), where the hot end is
  nearly invisible (1.39:1), so the wordmark plate is forced to `--bg` via
  `:has(.wordmark-letter)`.
- **`README.md`'s "Reading a Diff Report" is the specification of the diff
  notation** - `NumberFormat` and the `theme.js` functions follow it, never
  the reverse.
- Column widths are exact `ch`, **never persisted**, and **no column is ever
  narrower than its own title** - one rule in `column_widths()` and
  `table_render()`; `grow_column_fill()` measures against
  `nearest_scroller()`, never `window.innerWidth`.
- **Counter descriptions are one vocabulary in two places that must say the
  same words**: `ui_strings.js`'s `str_counter_<key>` and `README.md`'s
  "Callgrind Counters" table - **byte-identical per key**, all 19, one edit;
  Python is **not** a third place. The `<select>`'s `ch` width comes from the
  longest `"<desc> / <key>"` (42 ch).
- `counter_list`/`secondary_counters` list every counter the profile _can_
  produce, **not** filtered on a zero total, so layout stays stable; all-zero
  columns render blank, totals guard `|| 1`. **No row-wide heat.**
- `minimap_build()` runs _before_ `layout_activate()`, narrowing the pane by
  110px - the fill measures it as-is. Only `th` cells are sticky - **never
  measure the thead**.

### 8.1 Number notation

`2.1K`/`2.0G`, `63.2%`, `<0.01%`; exact zero renders empty. The notation floor
is **`NUMBER_SMALLEST_PRINTED_PERCENT`** (0.01), and it is now the only such
floor: `HEAT_COLOR_SMALLEST_VISIBLE_SHARE` went with `theme.heat_t()`, since
`heat_of_share()` measures nothing off the data. The notation _strings_
(`<0.01%`, `≈0.00%`, `>1000x`, `∞%`) stay inline, out of `ui_strings.js`.

**A diff never prints `+`.** A share leads with an arrow, keeping a negative's
sign (`▲11.1%`, `▼-100.0%`); an amount carries only a minus when negative, the
**ASCII hyphen** - U+2212 is not in the allow list and neither renderer emits
it. Under 0.01% → `▲≈0.00%`; a zero baseline → `▲∞%`. **Past 100% a diff
share switches to a multiple** (`▲1.30x`), and at or past
**`NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES`** (999.99) to `>1000x`; those two
state a bound, so no sign. **A drop can't pass -100%**, so
the multiple branch is rise-only - don't "fix" negative multiples. `theme.js`'s
`report_ui` functions and `theme.py`'s `NumberFormat` are kept in step by
hand, verified on README's rows; **both read the bound as a setting** - it was
once a number spelled in each file and "kept in step", which is exactly what a
setting exists to end.

### 8.2 Frames and URL state

Two levels deep: overview frames a test summary, which frames its heat map /
flame graph; both run `FRAME_JS`, deciding by `report_ui.is_framed`.
**`theme.js` is the utility library for being an HTML app; `frame.js` is only
the thin top-level frame controller** - cross-frame talk (`is_framed`,
`parent_post`, `parent_listen`, `hash_publish`) lives in `theme.js`, and
**moving a helper into `frame.js` is the wrong direction**.

- **URL is the whole state.** Frame `#<view>[/<inner hash>]`; heat map
  `f=<file>`, `f=<file>&l=<n>`, `fn=<name>`, none = home, `&e=<counter>` when
  >1 counter. **Nothing is remembered outside the URL** except
  `heat.scale`/`heat.sort` and `split.<pane>`.
- **The local store is versioned**: `STORAGE_VERSION` = `perf2html v1` under
  `STORAGE_VERSION_KEY` = `perf2html.version`, a bare string, not JSON. Not
  **exactly** the current string → sweep every key this report owns;
  **bumping it is how a stored-format change is rolled out**. **A new key must
  go in `STORAGE_OWNED_KEYS` or `STORAGE_OWNED_PREFIXES` (`split.`) or its
  data outlives every bump.** All four are **settings**, not `theme.js`
  constants; the keys themselves stay boundary names.
- `FRAME_JS` loads with `location.replace()`, passing
  `link_href + (inner_hash || "#")` - **never `iframe.src`** (a history entry
  per load, back desyncs). `"#"` not `""`: a fragment-less URL is a reload.
- `hash_changed` is posted by the heat map _and_ by a framed `FRAME_JS`, so a
  middle level relays its full hash up - without it the outer hash freezes at
  `#<test>`. **Both go through `report_ui.hash_publish()`.**
- Regression test: click test → view → file → line → counter; the outer hash
  must end `#<test>/heat-map/f=<file>&l=<n>&e=<ev>` and load back to all three
  levels' hashes.

## 9 Measurement and byte facts

- Callgrind gives no per-call stacks or time: `calls=` lines are aggregated
  (caller, callee) totals. `--separate-callers=N` is exact but still
  aggregated and orderless - **never feed such a file to the summary/heat
  map**, functions come out named by full chain.
- Hook cost is inside every traced duration → **flame graph for shape and
  outliers, perf log for speed**. Native speed moves ~1.9× with host state -
  only compare within one run. `rdtsc` steps by 20 ticks = 10.02 ns, so every
  flame-graph duration is a multiple of ~10 ns.
- `perf stat -e cycles:u,instructions:u` works in this WSL2; `perf record`
  samples; uftrace is not installed.
- Eight `TESTS_C` = **8.39MB**: heat-map pages 44%, flame `profile.js` base64
  trace 36%, shared 13%, raw archives 5%. **None of it is deleted to make a
  number smaller.** **base64 costs a flat 33%** of every trace and is **not
  ours to remove**: `loadFileFromBase64` is the only entry point speedscope
  exports, and its own `<script src="file:///profile">` 404s - hence the
  polling bootstrap. **Still open.**

## 10 Current state

No `lib/` change has come out of the profiling yet. Per-test numbers live in
the reports (overview: native time, cycles, instructions), not here.

## 11 Workflow

1. Quick read: `./build/tests/perf/perf <test>`, median of 3–5 - **real
   numbers only from the pinned RelWithDebInfo build**.
1. One focused change, rebuild, re-run, then
   `dev/perf2html.sh --report=perf2html_modified_report` and
   `dev/perf2html_diff.sh`. Keep only changes that measurably help **and**
   leave everything else the test prints unchanged. Record before/after
   numbers in "Current state".
1. After any `dev/` edit: `dev/perf2html_batch.sh` **then**
   `dev/scripts/reformat.sh`; the batch alone checks nothing.
1. Before final: full suite (`tests/runtests.pl`, or `ctest` from `build/`
   with `-DBUILD_TESTING=ON`) - the perf test doesn't validate correctness.
