# Agent Interaction Guide

## 0 Design Principles

- No fallbacks: broke is broke. Never swallow an error, `||`/`or` default,
  or "just in case" branch for a case that can't happen - throw so it fails
  loud with a call stack.
- Any error is a hard error, reported immediately, first failure only -
  no script collects failures, tallies, or records-a-fault-and-returns-0.
- `--regenerate` refuses (hard error, exit 2) rather than silently
  measuring when recordings are stale. Any silent downgrade to the more
  expensive path is the same class of bug.
- An unexpected change in a file is the user's own edit - never revert it,
  never clobber it; finish it the way it points, or stop and ask if it
  makes no sense.
- `STORAGE_VERSION` is the user's, never a session's - never bump it or
  reshape stored format as a side effect; a format change runs once
  without `--regenerate` and says so.
- `dev/README.md` is the user-facing contract - code follows it, never the
  reverse; never edit README to match code unless the user asked this
  session.
- No fake data - every value is a measurement or plain arithmetic on one.
  If a tool can't supply a view's data, the view isn't built.
- A value written twice and "kept in step" is banned - one setting in
  `settings.sh`/`settings.py`, read everywhere.
- Any urge to add decorative comments, "helpful" extra logging, or
  stylistic polish not asked for anywhere above - the file is explicit
  that embellishment (borders, tooltips, alpha/fade on the heat map,
  redesigning on your own initiative) is actively unwanted, not merely
  optional.
- One cmake-flag tree per build, never shared between baseline/modified -
  sharing one tree corrupts comparisons.
- `manifest_verify`/`manifest_fault_of` is the one door deciding whether a
  dir is a report - never bypass or duplicate this check elsewhere.
- Never buffer a child's output in a shipping script (`$( )` capture) -
  breaks `--verbose` streaming and hides live failures.
- Nothing test-specific, ever - no test names/file lists baked into
  `dev/`; every view must work for every test in `TESTS_C`.
- Every `dev/*.sh` makes paths absolute at startup; `$PWD` is never read
  again below `args_parse`. Getting this wrong breaks every relative
  invocation silently.
- `mktemp` is banned because log files are banned. only `test_all.sh` creates
  a  log file by redirecting `enforcer.sh ... 2> enforcer.md`.
- No news is good news: nothing prints a success line unless `--verbose`,
  and when it does print, a success line goes to stdout and failures go
  to stderr - not the other way round.
- Every ok/success line a script of ours controls (including our Python
  tools' ok lines) is gated behind `--verbose`; an outside tool's own
  quiet switch is passed unless `--verbose` (e.g. `ruff --quiet`); a tool
  with no quiet switch (pyright) is left alone, its one unsuppressable
  success line accepted as-is, never worked around.
- `--regenerate` clears the report dir too - a report is output only,
  never read back as an input to itself.
- `enforcer.sh` captures, redirects or reformats no output of its own or
  a child's - every child runs through `child_run` and its lines reach
  the terminal verbatim; a non-zero exit is `error_exit`.
- `tools_resolve` (or equivalent) must find every formatter/linter before
  anything is deleted, naming every missing tool with its install
  command - never discover a missing tool mid-run after damage is done.
- `test_all.sh` captures nothing and makes no temp file - refusals stream
  live to the terminal; failure checks the exit code only.
- Plumbing (`perf2html.sh`, `perf2html_diff.sh`) holds no working-directory
  opinion; only the batch (porcelain) has one. Don't blur this line.
- `checksum=` re-verified whenever a tool opens a report - don't merge
  `checksum_compute` and `_REPORT_CHECKSUM_COMMAND`, don't skip
  re-verification.
- `dev/scripts/enforcer_whitelist.txt` is the one list of what source
  stages touch - no directory walk, no skip list, nothing unlisted
  touched.
- Verification never reads from the code under test for a calculation
  it's checking - local expected constants or a different-route
  recomputation only.
- `--verbose` is additive/counted, tested only via `[ "$VERBOSE" -ge N ]`
  in `shared.sh` - no bare `printf` wrappers elsewhere.
- Docs written on request go in `dev/tmp/` only, `.md`, never touched by
  the whitelist.
- `dev/` is bespoke tooling - one parser, one theme, no dead code or
  duplicate systems.
- Pages are deterministic - same input, byte-identical output.
- New identifiers need 2+ unabbreviated English words.
- Naming split: `_SCREAMING_SNAKE` for a script's own global, `_lowercase`
  for locals, bare names crossing into `shared.sh`.
- 79-column hard max for all `dev/` source.
- Comment blocks max 2 lines (3 is an error via `source_scan.py`); longer
  reasoning goes in `DECLAUDE.md` instead.
- ASCII plus the specific whitelisted glyphs (`≈ ∞ ▲ ▶ ▼ …`), written
  literally, never as HTML entities.
- Never say "meta" - say "header" or "manifest".
- Timer artifacts contain `counter` data. Never "events"/"metrics"/"stats".
- Follow style. Alphabatization matters.
- Settings declared as annotation + empty sentinel + `load_into` - don't
  add accessors or conversions, don't turn off `F821`/`reportUnboundVariable`.
- More than one goal in a response ends with a done/not-done checklist.
- Numbering of multi-item communication in summaries follows ISO 2145.
- Terminal-editor geometry: no vertical padding/margin/gap on text boxes;
  horizontal spacing only in specific increments (0, 1ch, 2ch).
- No decorative borders, no tooltips outside the two named exceptions.
- Design-pixel discipline: think in design px/ch, then scale; never
  retune a length by eyeballing one screen size.
- `scripts/` page assets may carry comments under the 2-line limit, one
  `#` line per class/function/field, no trailing comments.
- One dark theme, Monaco/monospace, no restyling the heat map's palette
  or curves without proposing first.
- Don't update usage text, tell the user to do that.
- `enforcer.sh` is expected to have its own constants distinct from the
  shipping scripts to compare against - not a bug to flag on sight.


## 1 Map

Under `dev/`:

- Shell: `perf2html.sh` builds, profiles, writes one report;
  `perf2html_diff.sh` measures nothing, subtracts two reports;
  `perf2html_batch.sh` runs baseline, modified (`-D CMAKE_C_FLAGS=-Os`),
  diff; `scripts/enforcer.sh` formats, lints, scans, runs the batch,
  validates; `scripts/test_all.sh` runs enforcer mode 2, the failure-mode
  tests, markdownlint; `clean.sh` = `git clean -Xdf -e '!tmp/'` + ccache
  eviction; `scripts/settings.sh` every shell setting; `scripts/shared.sh`
  every shared function, sourcing inert.
- Python (`scripts/`): `settings.py` every Python/JS setting;
  `callgrind.py` the one parser; `callgrind_diff.py` delta + callers JSON;
  `callgrind_to_heatmap.py`, `build_report.py` (overview, summary),
  `build_flame_graph.py`, `trace_to_speedscope.py`; `theme.py` with
  `theme.css`/`theme.js` the one theme (`theme.js` = utility library);
  enforcer-only: `validate_report.py`, `source_scan.py`, `screenshots.py`.
- Page assets (`scripts/`): `frame.js` thin top-level controller;
  `heatmap.{js,css,html}`; `flame_bootstrap.js` polls `window.speedscope`;
  `ui_strings.js` (`str_*`); `error_overlay.js` first script on every
  page; `settings_handler.js` (`settings("NAME")` throws on unknown).
- `src/cyg_callback.c` trace hooks; `scripts/enforcer_whitelist.txt`;
  `README.md` user contract, copied into every report; `tmp/` notes,
  `.md` only, gitignored, spared by `clean.sh`.

`_TESTS` comes from `tests/perf/Makefile.inc`. Words: "header"/"manifest"
(never meta); "counters" except callgrind's `events:` and the `e=` URL key;
"raw" = only `<test>/raw/` and `raw-data` links, temporary recordings are
"artifacts"; "settings", never "constants"; rows are `ManifestRow`/
`ManifestBlock`.

## 2 Commands

```sh
dev/perf2html.sh [--verbose] [--keep-artifacts] [--regenerate]
    [--report=DIR] [--artifacts=TMP] [cmake_flags...]
dev/perf2html_diff.sh [--verbose] [--keep-artifacts] [--regenerate]
    [--artifacts=TMP] [baseline-dir] [modified-dir] [report-dir]
dev/perf2html_batch.sh [--verbose] [--keep-artifacts] [--regenerate]
    [--artifacts=TMP] [--target-dir=DIR] [cmake_flags...]
dev/scripts/enforcer.sh [--check-formatting] [--keep-artifacts] [--regenerate]
    [--verbose]
dev/scripts/test_all.sh    # no arguments to prove reproducability.
dev/clean.sh [-h|--help]   # no arguments to prove sobriety.
cmake -S . -B build -G Ninja -DCURL_USE_LIBPSL=OFF
cmake --build build --target perf      # EXCLUDE_FROM_ALL, must be named
taskset -c 3 ./build-relwithdebinfo/22_DCMAKECFLAGSO2g/tests/perf/perf \
    <test> [loops]
```

- `perf2html.sh` default `--report`: `perf2html_baseline_report`, or
  `perf2html_modified_report` with cmake_flags; after a source-only change
  pass `--report=perf2html_modified_report` yourself. `--report=DIR` is
  the report dir itself. `--artifacts` defaults to
  `perf2html_temporary_artifacts/` in the report's parent dir (all three).
- Batch: `--target-dir` (default CWD) holds the three default-named
  reports; every other argument is a cmake flag.
- Enforcer takes only flags and runs the batch; `MANIFEST.txt` line 1
  decides each report's `--diff`. Pass `--regenerate` every time except
  after `perf` was re-linked (wrongly passed, it refuses in <1s).
- `usage_show`'s heredoc is the only usage text. `toolchain_check` lists
  every missing tool with its install command, exit 1.
- After any `dev/` edit: `dev/scripts/enforcer.sh --regenerate`. Before
  final: `tests/runtests.pl`.

## 3 Build trees and measuring

- `build_paths` (perf2html.sh) is the one setter of `_TREE_NAME`,
  `_BUILD_TREE`, `_TRACE_TREE`, `_BIN`, `_TRACE_BIN`. Tree name = joined
  flag string's length, `_`, its alphanumerics (`22_DCMAKECFLAGSO2g`,
  `27_DCMAKECFLAGSO2gOs`) under `build-relwithdebinfo/` (`BUILD_DIR`) and
  `build-instr/` (`TRACE_BUILD_DIR`) at the repo root, never `/tmp`. Not
  unique across punctuation (`-DA_B=C` vs `-DA=B_C`). Each run
  reconfigures its own two (~7s, recompiles nothing).
- `args_parse` leads `CMAKE_C_FLAGS` with `-O2 -g`; a later user `-O` wins.
  `CURL_USE_LIBPSL=OFF` is the only deviation; `CURL_WERROR` off. Never
  profile `./build` (-O0, nothing inlined). Always pin: WSL2 noise ~106%
  unpinned, <1-3% pinned. `PROFILE_PINNED_CPU=3`.
- Trace tree = same flags + `-finstrument-functions` + `cyg_callback.c`,
  whole build. `tree_build` sets `local -x CCACHE_NAMESPACE` from
  `BUILD_CCACHE_NAMESPACE` (`perf2html`).
- `run_one`: `taskset -c 3 valgrind --tool=callgrind --cache-sim=yes
  --branch-sim=yes --LL=16777216,16,64` (auto LL is direct-mapped). Timing
  is a separate pinned `perf stat -x, -e cycles:u,instructions:u`; its
  `Time*` lines are the only valid speed number. Flame graph for shape,
  perf log for speed; native speed moves ~1.9x with host state. Callgrind
  `calls=` are aggregated; never feed `--separate-callers=N` output to
  the summary/heat map.
- Quick read: `perf <test>`, median of 3-5.

## 4 Artifacts, regenerate, enforcer stages

- Artifacts dir holds `perf-stat.<test>.<stamp>.txt`, `perf-stat.*.csv`
  (`PROFILE_TIMING_FILE_PREFIX`), `trace.<test>.<loops>.<stamp>.log` and
  the rows file `header.overview.<report basename>.txt`
  (`HEADER_ROWS_NAME`; `run_all` writes it, `_HEADER_FILE` set in
  `args_parse`). No `output.txt` ships: the summary embeds perf/trace logs
  (`perf_page_of`/`_TRACE_LOG`); the overview reads one
  `--perf-log NAME=FILE` per test, `all` included.
- `--regenerate` rebuilds pages from recordings, opening no report. First
  step of `stamp_reuse` (perf2html.sh), `regenerate_inputs_verify`
  (batch), `regenerate_check` (enforcer): prove rows file and recordings
  exist. `stamp_reuse` restores `TIMESTAMP` from `stamp=`; `build_manifest`
  reads the rest; both before `report_begin`. The diff's `--regenerate` =
  `--keep-artifacts` alone. `executable=` is recomputed from today's
  naming: after a tree-naming change run without `--regenerate`.
- `regenerate_check` (right after `whitelist_expand`): per measured
  report, newest `perf-stat.*.csv` vs the `executable=` row's binary
  (first token, repo-relative via `_DIR_REPO`); strictly newer binary →
  `regenerate_refuse`, exit 2 (the same second is fine). A missing dir,
  rows file, `stamp=`, recording, `executable=` or binary refuses, naming
  the report. The diff names no tree.
- The batch owns every deletion of the artifacts dir, passing
  `--keep-artifacts` down; a failed flagless batch keeps it.
- Stage order (cost-ascending): `whitelist_expand` → `regenerate_check` →
  `tools_resolve` (`_SHFMT`, `_RUFF`, `_CLANG_FORMAT`, `_PRETTIER`,
  `_PYRIGHT`) → `clear_overwritten_folders` (three reports, never
  artifacts) → shfmt, ruff, clang-format, prettier → `long_lines_report`
  → `source_scan_run` → `lint_run` (pyright) → `batch_run` →
  `validate_run` → `screenshots_run`. No stage reaches inside a report;
  the batch itself runs no checks.
- Enforcer internals: `child_run` = `command_item_print` + plain `"$@"`,
  non-zero → `error_exit` `error: exit N from: <command>`; `python_run` =
  `child_run` + `verbose_flags_of`; a stage = `heading_print`; status
  lines (`whitelist`, `regenerate`, `cleared`, `columns`) = `log_verbose`;
  `batch_run` = plain child, failure `error_exit` with its code; no
  `RUN_LOG`; own spellings `header_row_of`, `_REPORT_CHECKSUM_COMMAND`,
  `_SCREENSHOT_*`, `tool_find`'s `$( )`. Only caller of
  `validate_report.py`, `source_scan.py`, `screenshots.py`, `pyright`,
  `ruff`, `prettier`.
- Whitelist: `whitelist_expand` → `_WHITELISTED_FILES`; `files_of()` picks
  by extension; blank/`#`/whitespace lines refused; a glob matching nothing
  is allowed (`src/*.h`), a non-regular match or empty list is an error.
  `--config`/`--project` always passed; `pyrightconfig.json` names no file.
- `screenshots.py`: modified + diff reports, `_VIEWS` ×
  `_SCREENSHOT_VIEWPORTS` → `dev/screenshots/<size>_<report>_<view>.png`,
  then 4k 3x3 `thumbnail_<size>_<report>.png`; imports no settings; error
  view `bad_function`; `--incognito`; under `--verbose` it prints
  `<report> -> <dir>` and `N screenshot(s)`.
- Debug modes, run in order: 1 `enforcer.sh` cold; 2
  `--keep-artifacts`; 3 `--regenerate`. `test_all.sh` = mode 2 `--verbose`
  with stderr `2>` into `dev/enforcer.md` (gitignored), then failure-mode
  tests (`tmp/failure-modes.md`) on report copies in
  `dev/build/test_all_scratch/` (`_TEST_ALL_SCRATCH`; kept by a failed
  run). `failure_expect` checks the exit code, prints `ok <test>`; wrong
  code → `FAILED: <test>: exit N, expected M`, exit 1.

## 5 Shell library

- Paths: `INVOKED_FROM="$PWD"` above the `cd` to the script dir;
  `absolute_path` = `readlink -m` on `$INVOKED_FROM/<path>` (`~/`
  expanded); `$PWD` is `dev/` after the `cd`; display via `path_display`
  only. `$_SCRIPT` finds the tool's own code only. A leaf script derives
  nothing from a collection (batch/enforcer own "three reports").
- `settings.sh`: alphabetical, no `$` words, parsed by
  `SettingsReader.shell_settings_read` (`-?[0-9]+` → int); one name in all
  three languages. `TIMESTAMP` per script (`$(date +%s)`) just above
  `_SCRIPT="$(readlink -f "$0")"`; enforcer declares none. Only env var:
  `PERF2HTML_HEADING_DEPTH`.
- Naming: script global `_SCREAMING_SNAKE`, local `_lowercase`, names
  crossing into `shared.sh` bare. `shared.sh` reads `ARTIFACTS_DIR`,
  `PERF2HTML_DIR_`, `INVOKED_FROM`, `RUN_LOG` (batch has none),
  `TIMESTAMP`, `VERBOSE`; sets `SPEEDSCOPE_RELEASE`, `RUN_LOG`
  (`report_begin`), `CHILD_EXIT_CODE`/`LOG_LINE_FROM` (`child_capture`),
  `VERBOSE_{START_US,HEADING_DEPTH,COMMAND_NUMBER,ITEM_INDENT,
  OUTPUT_ENDS_BLANK}` (`verbose_begin`). A function's comment names every
  global it sets.
- Children: `child_capture PAGE_FILE cmd` (tee-or-redirect chosen before
  start; tee behind `if ! { ...; }` for `PIPESTATUS[0]`, tee failure a
  hard error); `command_run` for a tool; `page_command_run PAGE SHOWN cmd`
  when the lines are page content (caller writes the `$` line and `#`
  comments); `step_run`'s `"$@"` runs one of our scripts uncaptured.
  Values return through globals (`CHILD_EXIT_CODE`). `$( )` around
  `printf`/`date`/`basename` is a value, fine.
- Failure: `error_exit CODE LINE...` = one ```txt fence on stderr, exit.
  Tool child: `failure_print_log_tail` = same fence holding
  `error: exit N from: <shown>`, the last `LOG_FAILURE_TAIL_LINES` lines
  and `(see: log)`. Parent of our script: one line (`step_run`) or a fence
  (`batch_run`, `child_run`), child's code. cmake configure output goes
  to `/dev/null` below level 2; `tree_build` → `child_capture_noisy`
  (= `child_capture` at 2); failure prints only
  `error: cmake failed to build <command>` (`%q`), no tail.
- Verbose: `verbose_begin` (after `args_parse`) reads
  `PERF2HTML_HEADING_DEPTH` (enforcer 1, batch 2, perf2html/diff 3, work
  4) and exports one deeper. `title_print` = script heading;
  `heading_print` = one piece of work; `` `[elapsed] text` `` on
  `VERBOSE_START_US`; items restart per heading; `command_item_print` =
  `` N. `$ cmd` ``. `verbose_filter` (awk, writes stderr, flushes every
  line except a held stat run) modes: `list` (child output: `$HOME/`→`~/`,
  blanks dropped, 2+ `words: number [unit]` lines → one single-row table,
  else `M. line` wrapped at `VERBOSE_LINE_WIDTH_CHARS`), `wrap PREFIX`,
  `paths`. `log_verbose` = paragraph; `table_head_print`/`table_row_print`
  = a table; `item_output_print` nests our own lines. `$VERBOSE` is tested
  only in `shared.sh`: those plus `heading_write`, `child_capture` at 1,
  `child_capture_noisy` at 2. `verbose_flags_of` = one `--verbose` per
  level, one per line (`mapfile -t`). Python tools' ok lines: stdout,
  `--verbose` only. Quiet switches `ruff --quiet` and prettier
  `--log-level warn`; pyright has none. `enforcer.sh --verbose 2> x.md` is
  the whole run.
- Manifest contract (`shared.sh`): `manifest_fault_of` (reader: why a dir
  is not a report, or nothing; takes each acceptable version string),
  `manifest_verify` (hard-error policy), `manifest_stamp_of` (first token,
  refuses empty), `manifest_value` (general), `manifest_write`,
  `manifest_wanted_phrase`, `checksum_compute`. Version strings
  `curl/perf2html.sh v1`, `curl/perf2html_diff.sh v1`, checksum label and
  manifest name are settings. `revision_describe REPO` = the one
  `<short>[-dirty]`.
- `report_begin` (clears, creates dirs, drops stale manifest, opens
  `$RUN_LOG`, lays `README.md`/`assets/`) and `report_finish` (writes the
  manifest last, `log_verbose`s the entry page) bracket every writer. A
  dir is cleared only if its own `MANIFEST.txt` proves we wrote it;
  `--artifacts` inside the report is refused.

## 6 Report layout

```text
OUTDIR/  index.html (overview)  <test>/{index.html,flame-graph/,heat-map/,
raw/}  all/  assets/  flame-graph-app/  sources/  README.md  MANIFEST.txt
```

- `raw/<test>.txz` = callgrind file + speedscope JSON, one deterministic
  `tar.xz` per test (`archive_write`).
  `all/` = every test merged: no perf log, trace, flame graph; no `raw/`
  in a full report, one in a diff (`all_has_archive`).
- `MANIFEST.txt`: line 1 version string, then LABEL=VALUE. Full:
  `sampled`, `revision`, `cpu`, `build`, `executable` (repo-relative),
  `stamp` (`<unix> <human date>`), `checksum`. Diff: `baseline`,
  `modified`, `baseline_stamp`, `modified_stamp`, `checksum`, no `stamp=`
  (`manifest_check` copies rows verbatim). Line 1 alone makes a dir a diff
  input; diffs can't be diffed. Version line must match EXACTLY; errors
  print found and expected. `checksum=` = POSIX `cksum` over every file
  but the manifest, `LC_ALL=C` sorted, relative paths; `home_dir_check`
  fails on `$HOME`.
- Diff report: no flame graph, no native timing; per-test preamble is the
  raw-data link only. Overview reads `--diff-profile NAME=FILE` per paired
  test; a test in one report only → `tests_pair` error.
- Pages: shared assets linked, never inlined; hrefs from
  `theme.shared_href(depth, name)` (overview 0, summary 1, heat map/flame
  2; strip via `strip_render`'s `depth`); stylesheet from `Theme.css()`;
  classic `<script src>`/`<link>` only, no `fetch()`, no ES modules; opens
  from `file://`. `sources/<source_name()>.js` (display path,
  non-alphanumerics → `_`); `FileModel.source` read via
  `source_text(file_path)`; `flame_app_install` needs each glob to match
  one file. `manifest_script_write` ships
  `assets/report_manifest.js` (`window.report_manifest`, no `checksum=`).

## 7 Python

- Style: one enclosing class per script for non-exported functions;
  `import X` only, alphabetical; `from` only for `__future__`
  `annotations`, `collections.abc`, `typing`. pyright 0 errors. Costs are
  `callgrind.Costs`, summed by `costs_add`. No multi-line HTML/CSS/JS
  literal: real files via `theme.asset_text_read()`.
- `settings.py`: settings first, then `SettingsReader` (constants carry
  `_`); cut at `_SETTING_NAMES`; `_is_setting_name()` strips a leading
  `_`. A consumer declares annotation + empty sentinel, then
  `settings.load_into(__name__)` first (`match_check`, `sentinel_check`,
  `type_check`); own constants below; `bool` sentinel `False`; `E401`/
  `I001`/`E501` off. Names `SCREAMING_SNAKE`, broad→narrow, 2+ words, unit
  suffix (`_PX`, `_MS`, `_PERCENT`, `_SHARE`, `_CHARS`, `_BYTES`).
  `settings_script_write()` ships the module as frozen JSON (all
  JSON-serializable); `settings_handler.js` is read with a local `open()`
  (not `theme.asset_text_read()`: cycle). `RANKING_COUNTER_NAME` ranks,
  colours and divides every table.
- `callgrind.py`: `profile_load(path)` exits unless the self-check ratio
  is 1.0000; `path_norm() -> PathInfo(display, local, group)`; functions
  keyed by name; derived counters from `settings.DERIVED_COUNTER_TERMS`
  (`D1m`, `DLm`, `L1m`, `LLm`, `Bm`, `CEst` = Ir + 10·L1m + 100·LLm), no
  coefficient in code; `counter_value()` is the door; descriptions in
  `ui_strings.js` (`HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX` + key
  lowercased); uncalled `function_entry` = first cost line in home file.
  New counter = `settings.py` + `ui_strings.js` + README (descriptions
  byte-identical per key, 19 keys).
- `build_report.py`: `_RANKING_COUNTER_NAME`; `Profile.value()` raises
  `KeyError`; `BuildReport.test`/`.diff_test`.
- `callgrind_diff.py`: `counters_check()` names both lists;
  `--callers-output` required (name, flags, JSON keys are contract).
- `callgrind_to_heatmap.py`: `render()` substitutes `__SCRIPTS__` before
  `__DATA__`; order `theme.page_preamble_scripts()`, `sources/`,
  `ui_strings.js`, `theme.js`, `heatmap.js`; head from
  `theme.page_document` (`extra_css`, `body_holds_scripts`); `model()`/
  `diff_model()`; `model()` refuses an unemitted `RANKING_COUNTER_NAME`.
- `trace_to_speedscope.py`: busiest run's first
  `FLAME_GRAPH_MAX_RECORDED_CALLS` (200) calls; `buildid_verify` refuses a
  moved build-id (run before rebuilding the trace tree); inlined helpers
  are frames; `_MAGIC` = `cyg_callback.c`'s `CYG_CALLBACKS_MAGIC`.
- `cyg_callback.c`: `next` a pointer, `end` a variable (11/12-instruction
  hot path); `buildid` path is `realpath`; single-threaded.
- `validate_report.py`: greps `loadFileFromBase64`,
  `var document_base64 = "..."`, `report_ui.layout_activate`; report dir
  required; `manifest_stamp_labels` get the unix-time check;
  `perf_tool_check` reads the summary's `perf log` section.
- `source_scan.py`: file paths (`nargs="+"`), read once; a block =
  consecutive whole-line comments plus a `/* */` or `<!-- -->` opened first
  on a line, file header exempt (`_COMMENT_BLOCK_MAX_LINES`); glyphs
  `_SOURCE_SCAN_ALLOWED_NON_ASCII_CHARS` (`≈ ∞ ▲ ▶ ▼ …`, literal);
  `_COMMENT_SYNTAX_BY_EXTENSION` (`.html` adds `//`, `/* */`); faults
  `path:line: message` sorted. The 79-column limit is unrelated to
  `HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS` (80).
- Reformatting `heatmap.*`, `frame.js`, `flame_bootstrap.js`, `theme.css`,
  `theme.js` changes reports; text echoed into a perf/trace recording is
  page content.

## 8 Pages and JS

- `ui_strings.js`: `str_*`; `text_of(id)` throws on unknown; no boundary
  names or number notation; `(no recorded caller)` stays in Python matching
  `str_no_caller`; empty test menu = `str_no_match`.
- `error_overlay.js`: replaces the document on `error`/
  `unhandledrejection`; message = `str_` key + `{N}` args
  (`format_or_raw`, raw on any failure); `file://` paths truncated to the
  report root; posts `report_ui: "report_error"`; touches neither
  `history` nor the URL.
- JS settings: each `.js` resolves each `settings("NAME")` once into a
  same-named `const` at the top of its IIFE, never in a render path; every
  number/colour/key/bound is a setting (`STRIP_TEST_MENU_KEY_NAMES`).
- Names: `snake_case` ours; camelCase owned by browser/Python (DOM, CSS
  class, `data-*`, storage/URL key, TypedDict key). `window.report_sources`
  keyed by display path, read by `source_text()`. Markers `__NAME__`,
  `__DATA__`, `__SCRIPTS__`, `__APP_CSS__`, `__APP_JS__`, `__PROFILE_JS__`.
- Frames: overview → summary → heat map/flame graph; both outer levels run
  `FRAME_JS`, deciding by `report_ui.is_framed`; cross-frame helpers
  (`is_framed`, `parent_post`, `parent_listen`, `hash_publish`) in
  `theme.js`. Load via `location.replace(link_href + (inner_hash || "#"))`,
  never `iframe.src`.
- URL = whole state: `#<view>[/<inner hash>]`; heat map `f=<file>`,
  `f=<file>&l=<n>`, `fn=<name>`, none = home, `&e=<counter>` when >1
  counter; else `state_of_hash` throws, `view_show` overlays. Regression
  path `#<test>/heat-map/f=<file>&l=<n>&e=<ev>` reloads all three levels.
- Storage: only `heat.scale`, `heat.sort`, `view.scale` (0..1),
  `split.<pane>`. `STORAGE_VERSION` = `perf2html v2` under
  `STORAGE_VERSION_KEY` = `perf2html.version`; mismatch sweeps owned keys;
  new keys go in `STORAGE_OWNED_KEYS`/`STORAGE_OWNED_PREFIXES` (`split.`).
  `localStorage` refused is a designed condition, not a fallback.
- Messages up `{report_ui: <name>}`: `title_changed`, `scale_changed`,
  `hash_changed` (heat map and framed `FRAME_JS`, via
  `report_ui.hash_publish()`), `test_menu_key_pressed`, `report_error`.
  Down (strings): `report_ui:title_request`, `report_ui:layout_reset`,
  `report_ui:test_menu_closed`. `#layout-reset` runs `reset_broadcast()`.
- Strip: logo → `location.assign(data-root-href)`. Test menu only on the
  overview: `strip_link_render()` entries (`tabindex=-1`), box reads the
  framed test or `STRIP_TEST_MENU_MERGED_TEST_NAME`; open, it is a
  `new RegExp(text, "i")` search steered by `STRIP_TEST_MENU_KEY_NAMES`;
  blur closes; list `z-index: 3` over `.band`. A framed summary forwards
  keys (typed characters always; command keys only while the menu is
  open, until `test_menu_closed`); the top's `menu_key_take` is the one
  keydown handler and `search_box_focus()` takes focus, else
  `str_error_test_menu_focus_refused`.

## 9 Look and feel numbers

- Design: `DESIGN_COORDINATES_WIDTH_PX` 1920, fitted by
  `design_scale_apply()` (one `zoom` on `:root`, every resize); Monaco
  `DESIGN_FONT_SIZE_PX` 12, `DESIGN_FONT_CHARACTER_WIDTH_PX` 7.2 → 266 ch;
  `font_fit_apply()` measures `0` via canvas `measureText`, sets
  `--font-fit` (`DESIGN_FONT_FIT_PROPERTY`) on `:root`; the one font size
  is `body`'s `calc(var(--font-px) * var(--font-fit))`, inherited
  everywhere. Unzoomed: `window.inner*`,
  `documentElement.client*` (convert with `design_px()`), `vh` (use
  `--design-vh`). Width media queries can't fire.
- Scale slider: `DESIGN_SCALE_*`, 0.5..2, default mid-travel
  (`DESIGN_SCALE_DEFAULT_TRAVEL_SHARE`), each half geometric
  (`design_scale_multiple_of()`/`design_scale_travel_of()`);
  `design_scale_travel_set()` is the door and resets column widths.
- Geometry: cells `0 1ch`, `.fhead` 2ch, `ul.rawdata` marker 2ch,
  `--title-w` = `STRIP_STATUS_ROW_WIDTH_CHARS` ch, tree indent
  `HEAT_MAP_TREE_INDENT_*_PX`. The only `title=` attributes:
  `<iframe title="report page">` and `<th>`. Only `th` is sticky.
- Colour: `--bg` = slate dark via `Theme.shade()`
  (`THEME_COLOR_ROLE_BACKGROUND_SHADE_FACTOR`, 8%);
  `THEME_COLOR_PAIR_ENTRIES`/`THEME_COLOR_PAIR_NAMES` equal length.
  `HEAT_COLOR_LOGO_STOPS` palette; `ramp_channels_at()` the one
  interpolation (`cell_style()`, `logo_color_at()`); cells paint the stop
  opaque. `heat_of_share()`: clamp to `HEAT_COLOR_FULL_SCALE_PERCENT`,
  divide, curve; nothing measured off the data; a diff maps [-100..100%],
  0% at the 5.5 midpoint. Dropdown = curve × scope; `scale` is an entry.
  Scope = denominator only (`global`, `per file`, `per function`;
  `share_in_scope()`); a diff uses `share_of_baseline`, one scope
  `per line`.
- Columns: `column_extents()` → `column_limits()` (lo, hi +
  `TABLE_COLUMN_EXTRA_WIDTH_CHARS`) → `column_width_text()`, twins in
  `theme.py`/`theme.js`; lo = `data-min`. L/H = Σlo/Σhi of non-grow, S =
  H - L, G = grow lo: `{lo}ch` if hi = lo, else `clamp(lo, lo + (100cqw -
  (L+G)) * (hi-lo) / S, hi)`; grow `max(G, 100cqw - clamp(L, 100cqw - G,
  H))`; G = grow `width` or `TABLE_GROW_COLUMN_NARROWEST_CHARS` + extra.
  `.page`, `#main`, `.home`, `.dbox` are inline-size containers; a
  scrolling one needs `scrollbar-gutter: stable`. Drags use `design_px()`
  rects and `clientX`, floored at `data-min`.
- Notation: `2.1K`/`2.0G`, `63.2%`, `<0.01%`, exact zero empty; floor
  `NUMBER_SMALLEST_PRINTED_PERCENT` (0.01). Diff: no `+`; `▲11.1%`,
  `▼-100.0%`; ASCII hyphen for amounts; `▲≈0.00%` under 0.01%; `▲∞%` on
  zero baseline; past 100% a multiple `▲1.30x`; at/past
  `NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES` (999.99) `>1000x` unsigned.
  `theme.js` `report_ui` and `theme.py` `NumberFormat` match by hand;
  README "Reading a Diff Report" is the spec.

## 10 Diff semantics

- Every number is MODIFIED - BASELINE per (function, file, line). Delta
  is callgrind format without `calls=` → no call columns
  (`HAS_CALL_GRAPH`); callers from `callgrind_diff.py --callers-output`
  JSON keyed `<fn>` and `<fn>\n<display path>\n<line>`.
- Share = `(new - old)/old` of the thing's own baseline: 1→0 = -100%,
  90→100 = +11.1%, 1→1 empty; new in modified = `inf`/`Infinity`, `▲∞%`,
  heat-clamped. `events` = recorded counters; `costs_fit()` pads, trims
  trailing zeros; ranking and heat use `abs()`; `profile_magnitudes()`
  (Σ|delta|) feeds `heatMapTotals.totals`; `summary:` is the signed total.
- Diff overrides live in the one `if (IS_DIFF) {...}` block of the heat
  map JS.

## 11 Why the heat map

`-O2` inlines small statics, so function tables misattribute; the heat map
shows cost per line. Cross-check `callgrind_annotate --show-percs=yes`.
