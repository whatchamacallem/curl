# Agent Interaction Guide

Do not modify CLAUDE.md or the README.md without approval. CLAUDE.md may be a
symbolic link to this document and in that case make editing this document
part of the same request. This is an exclusive control surface for the project
maintainer. Mention discrepancies when observed. The maintainer is the final
authority and decides correctness and requirements, however discrepancies are
worth fixing.

Do not use the AskUserQuestion tool and use numbered sub-lists to
as all questions in one go.

Maintain a task list for each session in `dev/tmp` following this format:
`dev/tmp/tasks_sat_0959am.md`. Use ISO 2145 for tasks and do not restart
numbering tasks within a single document or discussion. Add a separate
postmortem section after the tasks section and only modify the postmortem
instead of the initial tasks when providing results. Do not write the
postmortem or provide the user with a postmortem until all subagents and tasks
are done. Anything like a postmortem at the end of a run must include all
unfinished tasks and lost subagents. Provide the user with the postmortem
directly as well as providing a link to the task doc.

## 0 Design Principles

### 0.1 Top of mind

- Overconstrained goals introduce failure modes that are best resolved by
  conversations with the user that identify the contradictory requirements.
- Overconstrained solutions introduce failure modes that are best resolved by
  conversations with the user that identify missing long term requirements.
- No fallbacks: broke is broke. Never swallow an error, provide a default, or
  have a "just in case" branch for a case that can't happen - throw so it
  fails loud with a call stack or exit with the right Unix error code.
- Any error is a hard error, reported immediately, first failure only - no
  script collects failures, tallies of failures.
- Breaking this architecture into the classic Model-View-Controller state
  diagram for web apps would have the frame hold the "model" (specifically the
  parameters encoded in the hash), the menu would be the "controller" and the
  window below it, the "view." Communication goes "view <- model <->
  controller". Where those are "iframe, frame, and menu" respectively.
- There must be no data loss in the logs from a hard exit because there is no
  buffering beyond a single external command.
- `--regenerate` refuses (hard error, exit 2) rather than silently measuring
  when recordings are stale. Any silent downgrade to the more expensive path
  is the same class of bug.
- An unexpected change in a file is probably the user's own edit - never
  revert it, never clobber it; finish it the way it points if it is in the
  way, or stop and ask if needed when it makes no sense.
- `STORAGE_VERSION` is the user's, never a session's - never bump it or reshape
  stored format as a side effect; a format change runs once without
  `--regenerate` and says so.
- `dev/README.md` is the user-facing contract - code follows it, never the
  reverse; never edit README to match code unless the user asked this session.
- One cmake-flag tree per build, never shared between baseline/modified -
  sharing one tree corrupts comparisons.
- No fake data - every value is a measurement or plain arithmetic on one. If a
  tool can't supply a view's data, the view isn't built.
- A value written twice and "kept in step" is banned - one setting in
  `settings.sh`/`settings.py`, read everywhere.
- Any urge to add decorative comments, "helpful" extra logging, or stylistic
  polish not asked for anywhere above - the file is explicit that
  embellishment (borders, tooltips, alpha/fade on the heat map, redesigning on
  your own initiative) is actively unwanted, not merely optional.
- When asked to review a commit or unstaged change do not read this document.
  Report inconsistencies with this document only when encountered through
  knowledge gained when it was injected in your context. That is the self
  healing mechanism.
- Do not commit, uncommit, stage, unstage changes in git. If changes become
  staged during a rename then unstage them. git is the permission system for
  permanent changes and therefore must be reviewed by a user.
- Do not reference `CLAUDE.md` or `declawed.md` outside this doc. No not
  explicitly mention the tests being tested themselves in other source.
- The source formatters may need to run twice to be stable. Alert the user
  if they are not.

### 0.2 One-door glossary

The single function/check owning each concern - never bypass or duplicate:

- `manifest_verify`/`manifest_fault_of` - whether a dir is a report.
- `regenerate_check` - whether `--regenerate` may proceed.
- `counter_value()` - all counter lookups (callgrind.py).
- `column_extents()`/`column_limits()` - table column widths (theme.py/js).
- `checksum_compute`/`_REPORT_CHECKSUM_COMMAND` - report checksums, kept
  separate, re-verified on every open.
- `share_in_scope()` - heat-map denominator scope; diff uses
  `share_of_baseline`.
- `design_scale_travel_set()` - scale slider changes, resets column widths.

### 0.3 Working agreement

- This is a test driven development shop. Routine iteration on HTML generation
  can be tested while working (unless otherwise asked) with:
  `perf2html_batch.sh --regenerate --verbose 2> dev/tmp/perf2html_batch.md`
  Use `--keep-artifacts` to flush artifact cache and then keep the new ones.
- The full run is `test_all.sh` and only run that when asked to "test".
- When iterating send `--verbose` output to `dev/tmp/perf2html_*.md` for
  debugging and review.
- Docs written on request go in `dev/tmp/` only, `.md`, never touched by the
  whitelist.
- More than one goal in a response ends with a done/not-done checklist.
- Numbering of multi-item communication in summaries follows ISO 2145.
- Don't update usage text, tell the user to do that.

### 0.4 Invariants

- `manifest_verify`/`manifest_fault_of` is the one door deciding whether a dir
  is a report - never bypass or duplicate this check elsewhere.
- Never buffer a child's output in a shipping script (`$( )` capture) - breaks
  `--verbose` streaming and hides live failures.
- Nothing test-specific, ever - no test names/file lists baked into `dev/`;
  every view must work for every test in `TESTS_C`.
- Every `dev/*.sh` makes paths absolute at startup; `$PWD` is never read again
  below `args_parse`. Getting this wrong breaks every relative invocation
  silently.
- buffering command stdout and stderr with `mktemp` is banned. The single door
  policy on `mktemp` is that it is to be used when `--artifacts=TMP`,
  `--keep-artifacts` and `--regenerate` have not been used. In this case TMP
  is to be a directory created with mktmp. The design goal is that perf2html
  users get /tmp used as normal and cleaned up after too. And development work
  on perf2html uses a local artifact dir that can be debugged.
- No news is good news: nothing prints a success line unless `--verbose`, and
  when it does print, a success line goes to stdout and failures go to stderr -
  not the other way round.
- Every ok/success line a script of ours controls (including our Python tools'
  ok lines) is gated behind `--verbose`; an outside tool's own quiet switch is
  passed unless `--verbose` (e.g. `ruff --quiet`); a tool with no quiet switch
  (pyright) prints its one success line in a quiet run, accepted as-is; under
  `--verbose` `pyright_filtered_run` drops it, the maintainer's one exception.
- `--regenerate` clears the report dir too - a report is output only, never
  read back as an input to itself.
- `enforcer.sh` captures, redirects or reformats no output of its own or a
  child's - every child runs through `child_run` and its lines reach the
  terminal verbatim; a non-zero exit is `error_exit`. The one exception is
  `pyright_filtered_run` under `--verbose`.
- `tools_resolve` (or equivalent) must find every formatter/linter before
  anything is deleted, naming every missing tool with its install command -
  never discover a missing tool mid-run after damage is done.
- `test_all.sh` captures nothing and makes no temp file - refusals stream live
  to the terminal; failure checks the exit code only.
- Plumbing (`perf2html.sh`, `perf2html_diff.sh`) holds no working-directory
  opinion; only the batch (porcelain) has one. Don't blur this line.
- `dev/scripts/enforcer_whitelist.txt` is the one list of what source stages
  touch - no directory walk, no skip list, nothing unlisted touched.
- Verification never reads from the code under test for a calculation it's
  checking - local expected constants or a different-route recomputation only.
- `--verbose` is additive/counted, tested only via `[ "$VERBOSE" -ge N ]` in
  `utility.sh` and in the enforcer's `lint_run` for `pyright_filtered_run` - no
  bare `printf` wrappers elsewhere.
- `dev/` is bespoke tooling - one parser, one theme, no dead code or duplicate
  systems.
- Pages are deterministic - same input, byte-identical output.
- New identifiers need 2+ unabbreviated English words.
- Naming split: `_SCREAMING_SNAKE` for a script's own global, `_lowercase` for
  locals, bare names crossing into `utility.sh`.
- 79-column hard max for all `dev/` source.
- Comment blocks max 2 lines (3 is an error via `source_scan.py`); longer
  reasoning goes in `declawed.md` instead.
- ASCII plus the specific whitelisted glyphs (`≈ ∞ ▲ ▶ ▼ …`), written
  literally, never as HTML entities.
- Never say "meta" - say "header" or "manifest".
- Timer artifacts contain `counter` data. Never "events"/"metrics"/"stats".
- Follow style. Alphabetization matters.
- Settings declared as annotation + empty sentinel + `load_into` - don't add
  accessors or conversions, don't turn off `F821`/`reportUnboundVariable`.
- Terminal-editor geometry: no vertical padding/margin/gap on text boxes;
  horizontal spacing only in specific increments (0, 1ch, 2ch).
- No decorative borders, no tooltips outside the two named exceptions.
- Design-pixel discipline: think in design px/ch, then scale; never retune a
  length by eyeballing one screen size.
- `scripts/` page assets may carry comments under the 2-line limit, one `#`
  line per class/function/field, no trailing comments.
- One dark theme, Monaco/monospace, no restyling the heat map's palette or
  curves without proposing first.
- `enforcer.sh` is expected to have its own constants distinct from the
  shipping scripts to compare against - not a bug to flag on sight.
- One line helper functions in `.sh` are discouraged and require approval.
- `error_exit` calls and other error messages must be only one line while
  printing relevant variables too.
- `test_all.sh` should print significant run times, it is not "no news is good
  news".
- When `test_all.sh` has run links to screenshots, reports and `enforcer.md`.
- Don't change code when unable to implement a request as specified. Do not
  adjust requirements to be more reasonable and then determine they are
  satisfied. Disagreements about design indicate further refinement is
  required.
- `perf2html_diff.sh` must have deterministic outputs. That means its runs
  (aside logging) must contain no timestamp for the diff itself. When a diff
  is regenerated the checksum for both reports (excluding MANIFEST.txt) should
  be byte identical. Regeneration from artifacts should be deterministic in
  general.
- Things that are the same should have the same name. The thesaurus was not
  meant to be a naming guide.
- The pronouns for software are `the` and `that`. Not `it` or `they`. Do not
  address the user and their preferences in documentation as if the maintainer
  was feeling chatty. Maximize signal to noise by documenting the purpose
  of a function in a single simple clear english sentence using only commas
  and periods for punctuation. Add a second line for warnings if needed.

## 1 Project Structure

Under `dev/`:

- Shell: `perf2html.sh` builds, profiles, writes one report;
  `perf2html_diff.sh` measures nothing, subtracts two reports;
  `perf2html_batch.sh` runs baseline, modified (`-D CMAKE_C_FLAGS=-Os`), diff;
  `scripts/enforcer.sh` formats, lints, scans, runs the batch, validates;
  `scripts/test_all.sh` runs enforcer mode 2, the cache checks, the
  failure-mode tests, `prettier --check`; `clean.sh` = `git clean -Xdf -e
  '!tmp/'` + ccache eviction; `scripts/settings.sh` every shell setting;
  `scripts/utility.sh` every shared function, sourcing inert.
- Python (`scripts/`): `settings.py` every Python/JS setting; `callgrind.py`
  the one parser; `callgrind_diff.py` delta + callers JSON;
  `callgrind_to_heatmap.py`, `build_report.py` (overview, summary),
  `build_flame_graph.py`, `trace_to_speedscope.py`; `theme.py` with
  `theme.css`/`theme.js` the one theme (`theme.js` = utility library);
  enforcer-only: `validate_report.py`, `source_scan.py`, `screenshots.py`.
- Page assets (`scripts/`): `frame.js` thin top-level controller;
  `heatmap.{js,css,html}`; `flame_bootstrap.js` polls `window.speedscope`;
  `ui_strings.js` (`str_*`); `error_overlay.js` first script on every page;
  `settings_handler.js` (`settings("NAME")` throws on unknown).
- `src/cyg_callback.c` trace hooks; `scripts/enforcer_whitelist.txt`;
  `README.md` user contract, copied into every report; `tmp/` notes, `.md`
  only, gitignored, spared by `clean.sh`.

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
dev/scripts/test_all.sh [--help]   # no arguments to prove reproducibility.
dev/clean.sh [--help]              # no arguments to prove sobriety.
cmake -S . -B build -G Ninja -DCURL_USE_LIBPSL=OFF
cmake --build build --target perf      # EXCLUDE_FROM_ALL, must be named
taskset -c 3 ./build-relwithdebinfo/22_DCMAKECFLAGSO2g/tests/perf/perf \
    <test> [loops]
```

- `perf2html.sh` default `--report`: `perf2html_baseline_report`, or
  `perf2html_modified_report` with cmake_flags; after a source-only change pass
  `--report=perf2html_modified_report` yourself. `--report=DIR` is the report
  dir itself. `--artifacts` defaults to `perf2html_temporary_artifacts/` in the
  report's parent dir (all three).
- Batch: `--target-dir` (default CWD) holds the three default-named reports;
  every other argument is a cmake flag.
- Enforcer takes only flags and runs the batch; `MANIFEST.txt` line 1 decides
  each report's `--diff`. Pass `--regenerate` every time except after `perf`
  was re-linked (wrongly passed, it refuses in <1s).
- `usage_show`'s heredoc is the only usage text. `toolchain_check` lists every
  missing tool with its install command, exit 1.
- After any `dev/` edit: `dev/scripts/enforcer.sh --regenerate`. Before final:
  `tests/runtests.pl`.

## 3 Build trees and measuring

- `build_paths` (perf2html.sh) is the one setter of `_TREE_NAME`,
  `_BUILD_TREE`, `_TRACE_TREE`, `_BIN`, `_TRACE_BIN`. Tree name = joined flag
  string's length, `_`, its alphanumerics (`22_DCMAKECFLAGSO2g`,
  `27_DCMAKECFLAGSO2gOs`) under `build-relwithdebinfo/` (`BUILD_DIR`) and
  `build-instr/` (`TRACE_BUILD_DIR`) at the repo root, never `/tmp`. Not unique
  across punctuation (`-DA_B=C` vs `-DA=B_C`). Each run reconfigures its own
  two (~7s, recompiles nothing).
- `args_parse` leads `CMAKE_C_FLAGS` with `-O2 -g`; a later user `-O` wins.
  `CURL_USE_LIBPSL=OFF` is the only deviation; `CURL_WERROR` off. Never profile
  `./build` (-O0, nothing inlined). Always pin: WSL2 noise ~106% unpinned,
  <1-3% pinned. `PROFILE_PINNED_CPU=3`.
- Trace tree = same flags + `-finstrument-functions` + `cyg_callback.c`, whole
  build. `tree_build` sets `local -x CCACHE_NAMESPACE` from
  `BUILD_CCACHE_NAMESPACE` (`perf2html`).
- `run_one`: `taskset -c 3 valgrind --tool=callgrind --cache-sim=yes
  --branch-sim=yes --LL=16777216,16,64` (auto LL is direct-mapped). Timing is a
  separate pinned `perf stat -x, -e cycles:u,instructions:u`; its `Time*` lines
  are the only valid speed number. Flame graph for shape, perf log for speed;
  native speed moves ~1.9x with host state. Callgrind `calls=` are aggregated;
  never feed `--separate-callers=N` output to the summary/heat map.
- Quick read: `perf <test>`, median of 3-5.

## 4 Artifacts, regenerate, enforcer stages

- Artifacts dir holds, per report subdir, `perf-stat.<test>.<recorded>.txt`,
  `perf-stat.*.csv` (`PROFILE_TIMING_FILE_PREFIX`),
  `trace.<test>.<loops>.<recorded>.log` and the
  rows file `header.overview.<report basename>.txt` (`HEADER_ROWS_NAME`;
  `run_all` writes it, `_HEADER_FILE` set in `args_parse`). No `output.txt`
  ships: the summary embeds perf/trace logs (`perf_page_of`/`_TRACE_LOG`); the
  overview reads one `--perf-log NAME=FILE` per test, `all` included.
- `--regenerate` rebuilds pages from recordings, opening no report. First step
  of `recorded_reuse` (perf2html.sh) and `regenerate_check` (enforcer): prove
  rows file and recordings exist. `recorded_reuse` restores `TIMESTAMP` from
  `recorded=`; `build_manifest` reads the rest; both before `report_delete`.
  The diff's `--regenerate` keeps the artifacts without the flush, refusing a
  missing cache dir before its report is deleted. `executable=` is recomputed
  from today's naming: after a tree-naming change run without `--regenerate`.
- `regenerate_check` (right after `whitelist_expand`): per measured report,
  newest `perf-stat.*.csv` vs the `executable=` row's binary (first token,
  repo-relative via `_DIR_REPO`); strictly newer binary → `regenerate_refuse`,
  exit 2 (the same second is fine). A missing dir, rows file, `recorded=`,
  recording, `executable=` or binary refuses, naming the report. The diff names
  no tree.
- Each run owns `<artifacts>/<report basename>/`; `--keep-artifacts` flushes
  that subdir, then keeps it. The batch appends `--keep-artifacts` flagless,
  deletes the whole artifacts dir at the end (a failed flagless batch keeps
  it), and under `--regenerate` proves all three subdirs exist before
  deleting any report.
- Stage order (cost-ascending): `whitelist_expand` → `regenerate_check` →
  `tools_resolve` (`_SHFMT`, `_RUFF`, `_CLANG_FORMAT`, `_PRETTIER`, `_PYRIGHT`)
  → `clear_overwritten_folders` (three reports, never artifacts) → shfmt, ruff,
  clang-format, prettier → `long_lines_report` → `source_scan_run` → `lint_run`
  (pyright) → `batch_run` → `validate_run` → `screenshots_run`. No stage
  reaches inside a report; the batch itself runs no checks.
- Enforcer internals: `child_run` = `command_item_print` + plain `"$@"`,
  non-zero → `error_exit` `error: exit N from: <command>`; `python_run` =
  `child_run` + `verbose_flags_of`; a stage = `heading_print`; status lines
  (`whitelist`, `regenerate`, `cleared`, `columns`) = `log_verbose`;
  `batch_run` = plain child, failure `error_exit` with its code; no `RUN_LOG`;
  own spellings `header_row_of`, `_REPORT_CHECKSUM_COMMAND`, `_SCREENSHOT_*`.
  `tool_find` (`utility.sh`, the pip and npm user bins too) answers through
  `$( )`, for `tools_resolve` and `test_all.sh`'s prettier. `lint_run` runs
  `pyright_filtered_run` under `--verbose`. Only caller of
  `validate_report.py`, `source_scan.py`, `screenshots.py`, `pyright`, `ruff`,
  and of `prettier` but for `test_all.sh`'s last check.
- Whitelist: `whitelist_expand` → `_WHITELISTED_FILES`; `files_of()` picks by
  extension; blank/`#`/whitespace lines refused; a glob matching nothing is
  allowed (`src/*.h`), a non-regular match or empty list is an error.
  `--config`/`--project` always passed; `pyrightconfig.json` names no file.
- `screenshots.py`: modified + diff reports, `_VIEWS` × `_SCREENSHOT_VIEWPORTS`
  → `dev/screenshots/<size>_<report>_<view>.png`, then 4k 3x3
  `thumbnail_<size>_<report>.png`; imports no settings; error view
  `bad_function`; `report_incomplete` shoots a copy lacking
  `assets/report_complete.js` under `dev/build/screenshots_scratch/`;
  `--incognito`; under `--verbose` it prints
  `<report> -> <dir>` and `N screenshot(s)`.
- Debug modes, run in order: 1 `enforcer.sh` cold; 2 `--keep-artifacts`; 3
  `--regenerate`. `test_all.sh` = mode 2 `--verbose` with stderr `2>` into
  `dev/enforcer.md` (gitignored), then the kept recordings checked
  (`cache_populated_check`) and a batch `--regenerate` proved to measure
  nothing (`regenerate_cache_check`), then failure-mode tests on report copies
  in `dev/build/test_all_scratch/` (`_TEST_ALL_SCRATCH`; kept by a failed
  run). `failure_expect` checks the exit code, prints `ok <test>`; wrong code
  → `FAILED: <test>: exit N, expected M, from: <command>`, exit 1; last,
  `prettier --check` with the enforcer's `.prettierrc.json` over
  `dev/enforcer.md`: the markdown must be what prettier prints. It sources
  `utility.sh` for `tool_find` only.

## 5 Shell library

- Paths: `INVOKED_FROM="$PWD"` above the `cd` to the script dir;
  `absolute_path` = `readlink -m` on `$INVOKED_FROM/<path>` (`~/` expanded);
  `$PWD` is `dev/` after the `cd`; display via `path_display` only. `$_SCRIPT`
  finds the tool's own code only. A leaf script derives nothing from a
  collection (batch/enforcer own "three reports").
- `settings.sh`: alphabetical, no `$` words, parsed by
  `SettingsReader.shell_settings_read` (`-?[0-9]+` → int); one name in all
  three languages. `TIMESTAMP` per script (`$(date +%s)`) just above
  `_SCRIPT="$(readlink -f "$0")"`; enforcer declares none. Env vars, two:
  `PERF2HTML_HEADER_DEPTH`, `PERF2HTML_CLOCK_START_US`.
- Naming: script global `_SCREAMING_SNAKE`, local `_lowercase`, names crossing
  into `utility.sh` bare. `utility.sh` reads `ARTIFACTS_DIR`, `PERF2HTML_DIR_`,
  `INVOKED_FROM`, `RUN_LOG` (batch has none), `TIMESTAMP`, `VERBOSE`; sets
  `SPEEDSCOPE_RELEASE`, `RUN_LOG` (`report_begin`),
  `CHILD_EXIT_CODE`/`LOG_LINE_FROM` (`child_capture`), `QUIET_SWITCH`
  (`quiet_switch_set`), `VERBOSE_{COMMAND_NUMBER,ITEM_INDENT,BLOCK_PRINTED}`
  (`verbose_begin`, `block_lead`, `command_item_print`, `heading_write`,
  `verbose_filter`). A function's comment names every global it sets.
- Children: `child_capture PAGE_FILE cmd` (tee-or-redirect chosen before start;
  tee behind `if ! { ...; }` for `PIPESTATUS[0]`, tee failure a hard error);
  `command_run` for a tool; `page_command_run PAGE SHOWN cmd` when the lines
  are page content (caller writes the `$` line and `#` comments); `step_run`'s
  `"$@"` runs one of our scripts uncaptured. Values return through globals
  (`CHILD_EXIT_CODE`). `$( )` around `printf`/`date`/`basename`, or
  `verbose_filter`'s awk answer, is a value, fine.
- Failure: `error_exit CODE LINE...` = one ```txt fence on stderr, exit. Tool
  child: `failure_print_log_tail` = same fence holding `error: exit ...`. cmake
  configure output goes to `/dev/null` below level 2; `tree_build` →
  `child_capture_noisy` (= `child_capture` at 2); failure prints only error:
  cmake failed to build $command...
- Verbose: `verbose_begin` (after `args_parse`) exports its own
  `PERF2HTML_HEADER_DEPTH`, one past the depth it inherits (enforcer 1, batch
  2, perf2html/diff 3, work 4), and `PERF2HTML_CLOCK_START_US`, the outermost
  script's clock, so a child's `[elapsed]` continues its parent's, and sets
  `lastpipe`. Every line printed is a code span, a table cell or sits in a
  fence, so nothing is escaped or wrapped and `prettier --check` passes as
  printed. `code_span` = text with
  `$HOME/` as `~/`, in the shortest backtick run it lacks; `block_lead` = the
  blank line before a block (none before a hand-run script's first, none
  between two items unless the first is loose). `title_print` = script heading;
  `heading_print` = one piece of work; `` `[elapsed] text` ``; items restart
  per heading; `command_item_print` = `` N. `$ cmd` ``; `log_verbose` = a
  paragraph of one code span; `table_print` = one whole table, header words
  plain, values code spans, padded as prettier pads. `verbose_filter INDENT`
  (awk, stderr, flushes every line) streams a child's lines into a ```txt fence
  at the item's indent: `$HOME/`→`~/`, trailing blanks and blank lines dropped,
  no fence when empty, a line with as many backticks as the fence closes it and
  opens a longer one; indented, 2+ `words: number [unit]` lines in a row are
  one single-row table (header words plain, values code spans, padded as
  `table_print` pads), tight after a fence, else led by a blank line that makes
  the item loose: the awk answers `loose` on stdout and
  `VERBOSE_BLOCK_PRINTED=loose` puts the blank line before the next block,
  which `lastpipe` lets the filter, a pipeline's last stage, set; `error_exit`
  and `failure_print_log_tail` use it at indent 0, `item_output_print` for our
  own lines. `$VERBOSE` is tested only in `utility.sh`: `log_verbose`,
  `heading_write`, `command_item_print`, `item_output_print`, `table_print`,
  `quiet_switch_set`, `verbose_begin`, `child_capture` at 1,
  `child_capture_noisy` at 2; and in the enforcer's `lint_run`, the pyright
  exception. `verbose_flags_of` = one `--verbose` per level, one per line
  (`mapfile -t`). Python tools' ok lines: stdout, `--verbose` only. Quiet
  switches `ruff --quiet` and prettier `--log-level warn`, recorded once in
  `quiet_switch_set` (`QUIET_SWITCH`, empty under `--verbose`); pyright has
  none. `enforcer.sh --verbose 2> x.md` is the whole run.
- Manifest contract (`utility.sh`): `manifest_fault_of` (reader: why a dir is
  not a report, or nothing; takes each acceptable version string),
  `manifest_verify` (hard-error policy), `manifest_recorded_of` (first token,
  refuses empty), `manifest_value` (general), `manifest_write`,
  `manifest_wanted_phrase`, `checksum_compute`. Version strings
  `curl/perf2html.sh v1`, `curl/perf2html_diff.sh v1`, checksum label and
  manifest name are settings. `revision_describe REPO` = the one
  `<short>[-dirty]`.
- A writer runs `report_delete`, then flushes its artifacts subdir, so a
  refused delete keeps the last run's recordings; the batch runs it on its
  three reports before step 1. `report_begin` (creates dirs, opens
  `$RUN_LOG`, lays `README.md`/empty `assets/`) and `report_finish` (writes
  `assets/settings.js`, then `report_complete.js`, then the checksum, then
  MANIFEST.txt last, `log_verbose`s the entry page) bracket every writer. A
  target
  is deleted unprompted only if its own `MANIFEST.txt` proves we wrote it; a
  non-directory, or a dir without one, goes only on a typed y (prompt on
  stderr, a no is `error_exit 1`). `path_overlap_check` refuses two paths
  where one is, holds or sits inside the other: a report and its artifacts
  dir (in `report_delete`), a diff's output and artifacts against its inputs,
  the batch's artifacts against its three reports.

## 6 Report layout

```text
OUTDIR/  index.html (overview)  <test>/{index.html,flame-graph/,heat-map/,
raw/}  all/  assets/  flame-graph-app/  sources/  README.md  MANIFEST.txt
```

- `raw/<test>.txz` = callgrind file + speedscope JSON, one deterministic
  `tar.xz` per test (`archive_write`). `all/` = every test merged: no perf log,
  trace, flame graph; no `raw/` in a full report, one in a diff
  (`all_has_archive`).
- `MANIFEST.txt`: line 1 version string, then LABEL=VALUE. Full: `revision`,
  `cpu`, `build`, `executable` (repo-relative), `recorded` (`<unix> <human
  date>`), `checksum`. Diff: `baseline`, `modified`, `baseline_recorded`,
  `modified_recorded`, `checksum`, no `recorded=` (`manifest_check` copies
  rows verbatim). Line 1 alone makes a dir a diff input; diffs can't be diffed.
  Version line must match EXACTLY; errors print found and expected. `checksum=`
  = POSIX `cksum` over every file but the manifest, `LC_ALL=C` sorted, relative
  paths; `home_dir_check` fails on `$HOME`.
- Diff report: no flame graph, no native timing; per-test preamble is the
  raw-data link only. Overview reads `--diff-profile NAME=FILE` per paired
  test; a test in one report only → `tests_pair` error.
- Pages: shared assets linked, never inlined; hrefs from
  `theme.shared_href(depth, name)` (overview 0, summary 1, heat map/flame 2;
  strip via `strip_render`'s `depth`); stylesheet from `Theme.css()`; classic
  `<script src>`/`<link>` only, no `fetch()`, no ES modules; opens from
  `file://`. `sources/<source_name()>` (display path, non-alphanumerics → `_`,
  plus `.js`); `FileModel.source` read via `source_text(file_path)`;
  `flame_app_install` needs each glob to match one file.
  `report_complete_write` ships `assets/report_complete.js`
  (`window.report_manifest_table`, the preformatted manifest table
  string, its only content, no `checksum=`).

## 7 Python

- Style: one enclosing class per script for non-exported functions; `import X`
  only, alphabetical; `from` only for `__future__` `annotations`,
  `collections.abc`, `typing`. pyright 0 errors. Costs are `callgrind.Costs`,
  summed by `costs_add`. No multi-line HTML/CSS/JS literal: real files via
  `theme.asset_text_read()`.
- `settings.py`: settings first, then `SettingsReader` (constants carry `_`);
  cut at `_SETTING_NAMES`; `_is_setting_name()` strips a leading `_`. A
  consumer declares annotation + empty sentinel, then
  `settings.load_into(__name__)` first (`match_check`, `sentinel_check`,
  `type_check`); own constants below; `bool` sentinel `False`; `E401`/
  `I001`/`E501` off. Names `SCREAMING_SNAKE`, broad→narrow, 2+ words, unit
  suffix (`_PX`, `_MS`, `_PERCENT`, `_SHARE`, `_CHARS`, `_BYTES`).
  `settings_script_write()` ships the module as frozen JSON (all
  JSON-serializable; the manifest table is not among it, see `manifest_table`
  and `report_complete_write` in section 6); `settings_handler.js` is read
  with a local `open()` (not `theme.asset_text_read()`: cycle).
  `RANKING_COUNTER_NAME` ranks, colours and
  divides every table.
- `callgrind.py`: `profile_load(paths)` exits unless the self-check ratio is
  1.0000; `path_norm() -> PathInfo(display, local, group)`; functions keyed by
  name; derived counters from `settings.DERIVED_COUNTER_TERMS` (`D1m`, `DLm`,
  `L1m`, `LLm`, `Bm`, `CEst` = Ir + 10·L1m + 100·LLm), no coefficient in code;
  `counter_value()` is the door; descriptions in `ui_strings.js`
  (`HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX` + key lowercased); uncalled
  `function_entry` = first cost line in home file. New counter =
  `settings.py` + `ui_strings.js` + README (descriptions byte-identical per
  key, 19 keys).
- `build_report.py`: `_RANKING_COUNTER_NAME`; `Profile.value()` raises
  `KeyError`; `BuildReport.test`/`.diff_test`.
- `callgrind_diff.py`: `counters_check()` names both lists; `--callers-output`
  required (name, flags, JSON keys are contract).
- `callgrind_to_heatmap.py`: `render()` substitutes `__SCRIPTS__` before
  `__DATA__`; order `theme.page_preamble_scripts()`, `sources/`, `settings.js`,
  `theme.js`, `heatmap.js`; head from `theme.page_document` (`extra_css`,
  `body_holds_scripts`); `model()`/ `diff_model()`; `model()` refuses an
  unemitted `RANKING_COUNTER_NAME`.
- `trace_to_speedscope.py`: busiest run's first
  `FLAME_GRAPH_MAX_RECORDED_CALLS` (200) calls; `buildid_verify` refuses a
  moved build-id (run before rebuilding the trace tree); inlined helpers are
  frames; `_HEADER_MAGIC` = `cyg_callback.c`'s `CYG_CALLBACKS_MAGIC`.
- `cyg_callback.c`: `next` a pointer, `end` a variable (11/12-instruction hot
  path); `buildid` path is `realpath`; single-threaded.
- `validate_report.py`: greps `loadFileFromBase64`, `var document_base64 =
  "..."`, `report_ui.layout_activate`; report dir required;
  `manifest_recorded_labels` get the unix-time check; `perf_tool_check` reads
  the summary's `perf log` section.
- `source_scan.py`: file paths (`nargs="+"`), read once; a block = consecutive
  whole-line comments plus a `/* */` or `<!-- -->` opened first on a line, file
  header exempt (`_COMMENT_BLOCK_MAX_LINES`); glyphs
  `_SOURCE_SCAN_ALLOWED_NON_ASCII_CHARS` (`≈ ∞ ▲ ▶ ▼ …`, literal);
  `_COMMENT_SYNTAX_BY_EXTENSION` (`.html` adds `//`, `/* */`); faults
  `path:line: message` sorted. The 79-column limit is unrelated to
  `HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS` (80).
- Reformatting `heatmap.*`, `frame.js`, `flame_bootstrap.js`,
  `error_overlay.js`, `ui_strings.js`, `theme.css`, `theme.js` changes reports;
  text echoed into a perf/trace recording is page content.

## 8 Pages and JS

- `ui_strings.js`: `str_*`; `text_of(id)` throws on unknown; no boundary names
  or number notation; `(no recorded caller)` stays in Python matching
  `str_no_caller`; empty pulldown = `str_no_match`.
- `error_overlay.js`: replaces the document on `error`/`unhandledrejection`
  through `document.open()` one task later; `<pre>` holds message, address,
  stack and, when `window.report_manifest_table` exists, that string raw,
  else "Report has no manifest."; font size is `DESIGN_FONT_SIZE_PX` (13)
  scaled once at `page_write` by `window.innerWidth /
  DESIGN_COORDINATES_WIDTH_PX`, no resize listener; two links, `copy`
  (`navigator.clipboard.writeText` of the same text) and `back`
  (`history.back()`); posts `report_ui: "report_error"` up from a frame;
  touches the URL only via `back`, reads no other script.
- JS settings: each `.js` resolves each `settings("NAME")` once into a
  same-named `const` at the top of its IIFE, never in a render path; every
  number/colour/key/bound is a setting (`STRIP_PULLDOWN_KEY_NAMES`).
- Names: `snake_case` ours; camelCase owned by browser/Python (DOM, CSS class,
  `data-*`, storage/URL key, TypedDict key). `window.report_sources` keyed by
  display path, read by `source_text()`. Markers `__NAME__`, `__DATA__`,
  `__SCRIPTS__`, `__APP_CSS__`, `__APP_JS__`, `__PROFILE_JS__`.
- Frames: overview → summary → heat map/flame graph; both outer levels run
  `frame.js`, deciding by `report_ui.is_framed`; cross-frame helpers
  (`is_framed`, `parent_post`, `parent_listen`, `hash_publish`) in `theme.js`.
  Load via `location.replace(link_href + (inner_hash || "#"))`, never
  `iframe.src`.
- URL = whole state: `#<view>[/<inner hash>]`; heat map `f=<file>`,
  `f=<file>&l=<n>`, `fn=<name>`, none = home, `&e=<counter>` when >1 counter;
  else `state_of_hash` throws, `view_show` overlays. Regression path
  `#<test>/heat-map/f=<file>&l=<n>&e=<ev>` reloads all three levels.
- Storage: only `heat.scale`, `heat.sort`, `view.scale` (0..1), `split.<pane>`.
  `STORAGE_VERSION` = `perf2html v2` under `STORAGE_VERSION_KEY` =
  `perf2html.version`; mismatch sweeps owned keys; new keys go in
  `STORAGE_OWNED_KEYS`/`STORAGE_OWNED_PREFIXES` (`split.`). `localStorage`
  refused is a designed condition, not a fallback.
- Messages up `{report_ui: <name>}`: `title_changed`, `scale_changed`,
  `hash_changed` (heat map and framed `frame.js`, via
  `report_ui.hash_publish()`), `tests_pulldown_key_pressed`, `report_error`.
  Down (strings): `report_ui:title_request`, `report_ui:layout_reset`,
  `report_ui:tests_pulldown_closed`. `#layout-reset` runs `reset_broadcast()`.
- Strip: logo → `location.assign(data-root-href)`. Pulldowns `tests`, `files`,
  `functions` only on the overview, `report_ui.pulldown.attach()` (`theme.js`)
  each: tests entries are `strip_link_render()` links (`tabindex=-1`), box
  reads the framed test or `STRIP_PULLDOWN_MERGED_TEST_NAME`; files/functions
  entries are that test's `window.report_pulldown_names` names
  (`pulldown_names_write`), heat map links on the counter shown; open, it is a
  `new RegExp(text, "i")` search steered by `STRIP_PULLDOWN_KEY_NAMES`; blur
  closes; list `z-index: 3` over `.band`. A framed summary forwards keys
  (typed characters always; command keys only while the tests pulldown is
  open, until `tests_pulldown_closed`); the pulldown's `key_take` is the one
  key handler and `search_box_focus()` takes focus, else
  `str_error_pulldown_focus_refused`.

## 9 Look and feel numbers

- Design: `DESIGN_COORDINATES_WIDTH_PX` 1920, fitted by `design_scale_apply()`
  (one `zoom` on `:root`, every resize); Monaco `DESIGN_FONT_SIZE_PX` 12,
  `DESIGN_FONT_CHARACTER_WIDTH_PX` 7.2 → 266 ch; `font_fit_apply()` measures
  `0` via canvas `measureText`, sets `--font-fit` (`DESIGN_FONT_FIT_PROPERTY`)
  on `:root`; the one font size is `body`'s `calc(var(--font-px) *
  var(--font-fit))`, inherited everywhere. Unzoomed: `window.inner*`,
  `documentElement.client*` (convert with `design_px()`), `vh` (use
  `--design-vh`). Width media queries can't fire.
- Scale slider: `DESIGN_SCALE_*`, 0.5..2, default mid-travel
  (`DESIGN_SCALE_DEFAULT_TRAVEL_SHARE`), each half geometric
  (`design_scale_multiple_of()`/`design_scale_travel_of()`);
  `design_scale_travel_set()` is the door and resets column widths.
- Geometry: cells `0 1ch`, `.fhead` 2ch, `ul.rawdata` marker 2ch, `--title-w` =
  `STRIP_STATUS_ROW_WIDTH_CHARS` ch, tree indent `HEAT_MAP_TREE_INDENT_*_PX`.
  The only `title=` attributes: `<iframe title="report page">` and `<th>`. Only
  `th` and `.band` are sticky.
- Colour: `--bg` = slate dark via `Theme.shade()`
  (`THEME_COLOR_ROLE_BACKGROUND_SHADE_FACTOR`, 0.90);
  `THEME_COLOR_PAIR_ENTRIES` two per `THEME_COLOR_PAIR_NAMES` entry.
  `HEAT_COLOR_LOGO_STOPS` palette; `ramp_channels_at()` the one interpolation
  (`cell_style()`, `logo_color_at()`); cells paint the stop opaque.
  `heat_of_share()`: clamp to `HEAT_COLOR_FULL_SCALE_PERCENT`, divide, curve;
  nothing measured off the data; a diff maps [-100..100%], 0% at the 5.5
  midpoint. Dropdown = curve × scope; `scale` is an entry. Scope = denominator
  only (`global`, `per file`, `per function`; `share_in_scope()`); a diff uses
  `share_of_baseline`, one scope `per line`.
- Columns: `column_extents()` → `column_limits()` (lo, hi +
  `TABLE_COLUMN_EXTRA_WIDTH_CHARS`) → `column_width_text()`, twins in
  `theme.py`/`theme.js`; lo = `data-min`. L/H = Σlo/Σhi of non-grow, S = H - L,
  G = grow lo: `{lo}ch` if hi = lo, else `clamp(lo, lo + (100cqw - (L+G)) *
  (hi-lo) / S, hi)`; grow `max(G, 100cqw - clamp(L, 100cqw - G, H))`; G = grow
  `width` or `TABLE_GROW_COLUMN_NARROWEST_CHARS` + extra. `.page`, `#main`,
  `.home`, `.dbox` are inline-size containers; a scrolling one needs
  `scrollbar-gutter: stable`. Drags use `design_px()` rects and `clientX`,
  floored at `data-min`.
- Notation: `2.1K`/`2.0G`, `63.2%`, `<0.01%`, exact zero empty; floor
  `NUMBER_SMALLEST_PRINTED_PERCENT` (0.01). Diff: no `+`; `▲11.1%`, `▼-100.0%`;
  ASCII hyphen for amounts; `▲≈0.00%` under 0.01%; `▲∞%` on zero baseline; past
  100% a multiple `▲1.30x`; at/past `NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES`
  (999.99) `>1000x` unsigned. `theme.js` `report_ui` and `theme.py`
  `NumberFormat` match by hand; README "Reading a Diff Report" is the spec.

## 10 Diff semantics

- Every number is MODIFIED - BASELINE per (function, file, line). Delta is
  callgrind format without `calls=` → no call columns (`HAS_CALL_GRAPH`);
  callers from `callgrind_diff.py --callers-output` JSON keyed `<fn>` and
  `<fn>\n<display path>\n<line>`.
- Share = `(new - old)/old` of the thing's own baseline: 1→0 = -100%, 90→100 =
  +11.1%, 1→1 empty; new in modified = `inf`/`Infinity`, `▲∞%`, heat-clamped.
  `events` = recorded counters; `costs_fit()` pads, trims trailing zeros;
  ranking and heat use `abs()`; `profile_magnitudes()` (Σ|delta|) feeds
  `heatMapTotals.totals`; `summary:` is the signed total.
- Diff overrides live in the one `if (IS_DIFF) {...}` block of the heat map JS.

## 11 Why the heat map

`-O2` inlines small statics, so function tables misattribute; the heat map
shows cost per line. Cross-check `callgrind_annotate --show-percs=yes`.
