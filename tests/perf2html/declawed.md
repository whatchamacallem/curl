# Agent Interaction Guide

Do not modify CLAUDE.md or the README.md without approval. CLAUDE.md may be a
symbolic link to this document and in that case make editing this document
part of the same request. This is an exclusive control surface for the project
maintainer. Mention discrepancies when observed. The maintainer is the final
authority and decides correctness and requirements, however discrepancies are
worth fixing.

Do not use the AskUserQuestion tool and use numbered number sub-lists per ISO
2145.

Maintain an engineering log for each session in `tests/perf2html/tmp`
following this format: `tests/perf2html/tmp/tasks_sat_0959am.md`. This is
formal paperwork with no chit chat required. Text is only added and not
modified. Use ISO 2145 for tasks and do not restart numbering tasks within a
single conversation. Preserve the users literal text in the task list first,
and concatenate additional feature requests to that section. In a second
section, list your intended order of operations to execute the users requests
before starting. Then add a separate postmortem section only when all
subagents are complete and all tasks are ready for review. Anything like a
postmortem at the end of a run must include all unfinished tasks and lost
subagents. Provide the user with the postmortem text directly in the
conversation as well as providing a link to the task doc.

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
- Breaking this architecture into the classic MVC/Model-View-Controller state
  diagram for web apps would have the frame hold the "model" (specifically the
  parameters encoded in the hash), the menu would be the "controller" and the
  window below it, the "view." Communication goes "view <- model <->
  controller". Where those are "iframe, frame, and menu" respectively.
- All constants outside of the test code go into a settings file. Zeros and
  the color clear are the only exceptions. Test files require a golden version
  to compare against and so they require independent constants for that.
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
- `tests/perf2html/README.md` is the user-facing contract - code follows it,
  never the reverse; never edit README to match code unless the user asked
  this session.
- One cmake-flag tree per build, never shared between baseline/modified -
  sharing one tree corrupts comparisons.
- No fake data - every value is a measurement or plain arithmetic on one. If a
  tool can't supply a view's data, the view isn't built.
- A value written twice and "kept in step" is banned - one setting in
  `settings.sh`/`settings.py`, read everywhere.
- Any urge to add decorative comments, "helpful" extra logging, or stylistic
  polish not asked for anywhere above is banned. Adding borders, tooltips,
  using alpha, adjusting shade, using gradients, adding requested style or
  redesigning on your own initiative is actively unwanted.
- When asked to review a commit or unstaged change do not read this document.
  Report inconsistencies with this document only when encountered through
  knowledge gained when it was injected in your context. That is the only self
  healing documentation mechanism needed.
- Do not commit, uncommit, stage, unstage changes in git. If changes become
  staged during a rename then unstage them. `git` is the permission system for
  permanent changes and therefore must be reviewed by a user. The one exception
  is for staging files before running reformatting tools below.
- Do not reference `CLAUDE.md` or `declawed.md` outside this doc. No not
  explicitly mention the tests being tested themselves in other source.
- The source formatters may need to run twice to be stable. Alert the user
  if they are not.
- If a source reformating tool can be used to fix an error then stage the
  file to be modified in git and run the tool. Then check the diff and if
  you believe there was an error the change can be reverted and applied
  manually.
- Do not iterate on formatting `.md` documents. If there is a setting forcing
  you to reformat this document then it has to be disabled, inform the user.
- Never add un-requested documentation because you saw some was missing. Only
  document new code and prefer 1 line comments.
- `error_overlay.js` needs to function when the other modules didn't load
  making it an exception to a lot of rules. Try not to mention it.
- Consider `speedscope` externally maintained and ignore it when applying the
  `perf2html` maintainers guidelines.

### 0.2 One-door glossary

The single function/check owning each concern - never bypass or duplicate:

- `manifest_verify`/`manifest_fault_of` - whether a dir is a report.
- `regenerate_check` - whether `--regenerate` may proceed.
- `counter_value()` - all counter lookups (callgrind.py).
- `column_extents()`/`column_limits()` - table column widths (theme.py/js).
- `checksum_compute`/`_REPORT_CHECKSUM_COMMAND` - report checksums, kept
  separate, re-verified on every open.
- `share_in_scope()` - heat-map denominator scope; a diff divides by the
  thing's own baseline through `diff_share_of()`.
- `diff_share_of()` - every diff share, a fall past its baseline refused
  (theme.py/js).
- `fixed_text()` - every decimal a page prints; `percent()`/`percent_text()`
  every share, `signed_percent()`/`signed_percent_text()` every diff share
  (theme.py `NumberFormat`, theme.js `report_ui_`).
- `design_scale_travel_set()` - scale slider changes; `menu.js` then posts
  `report_ui:layout_reset`, which resets column widths.

### 0.3 Working agreement

- This is a test driven development shop. Routine iteration on HTML generation
  can be tested while working (unless otherwise asked) with:
  `perf2html_batch.sh --regenerate --verbose 2> tmp/perf2html_batch.md`
  from `tests/perf2html/`. Use `--keep-artifacts` to flush artifact cache and
  then keep the new ones.
- The full run is `test_all.sh` and only run that when asked to "test".
- When iterating send `--verbose` output to
  `tests/perf2html/tmp/perf2html_*.md` for debugging and review.
- Docs written on request go in `tests/perf2html/tmp/` only, `.md`, never
  touched by the whitelist.
- More than one goal in a response ends with a done/not-done checklist.
- Numbering of multi-item communication in summaries follows ISO 2145.
- Don't update usage text, tell the user to do that.
- The default directories for temp and output files for perf2html.sh and
  perf2html_diff.sh are intentionally "pinned" to the invocation directory.
  `perf2html_batch.sh` is just a convenience wrapper and will likely evolve.
  This is a closed discussion.

### 0.4 Invariants

- `manifest_verify`/`manifest_fault_of` is the one door deciding whether a dir
  is a report - never bypass or duplicate this check elsewhere.
- Never buffer a child's output in a shipping script (`$( )` capture) - breaks
  `--verbose` streaming and hides live failures.
- Nothing test-specific, ever - no test names/file lists baked into
  `tests/perf2html/`; every view must work for every test in `TESTS_C`. The
  one exception is `test_screenshot.py`: screenshots are to be made from
  string literal golden bookmarks, and changing the url format must require
  changing those string literals.
- Every `tests/perf2html/*.sh` makes paths absolute at startup; `$PWD` is
  never read again below `args_parse`. Getting this wrong breaks every
  relative invocation silently.
- buffering command stdout and stderr with `mktemp` is banned. Use of `mktemp`
  is to be by request only. The two door policy as follows. Door one is that
  `--keep-artifacts` and `--regenerate` have not been used.  In this case the
  "TMP" directory is to be a directory created with `mktemp`. Door two is that
  it can be used for `.txz` archive extraction. The design goal is that
  perf2html users get /tmp used as normal and cleaned up after too. And
  development work on perf2html uses a local artifact dir that can be
  debugged.
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
- `test_expected_behavior.sh` captures, redirects or reformats no output of its
  own or a child's - every child runs through `subprocess_run` and its lines
  reach the terminal verbatim; a non-zero exit is `error_exit`. The one
  exception is `pyright_filtered_run` under `--verbose`.
- `tools_resolve` (or equivalent) must find every formatter/linter before
  anything is deleted, naming every missing tool with its install command -
  never discover a missing tool mid-run after damage is done.
- `test_all.sh` captures nothing and makes no temp file - refusals stream live
  to the terminal; failure checks the exit code only.
- Plumbing (`perf2html.sh`, `perf2html_diff.sh`) and the batch (porcelain)
  share one working-directory rule, `report_path_of`: a report name not
  starting with `/` or `~/` sits under `--target-dir` (default `$PWD`).
- `tests/perf2html/scripts/test_whitelist.txt` is the one list of what source
  stages touch - no directory walk, no skip list, nothing unlisted touched.
- Verification never reads from the code under test for a calculation it's
  checking - local expected constants or a different-route recomputation only.
- `--verbose` is additive/counted - no bare `printf` wrappers.
- `tests/perf2html/` is bespoke tooling - one parser, one theme, no dead code
  or duplicate systems.
- Pages are deterministic - same input, byte-identical output.
- New identifiers need 2+ unabbreviated English words.
- Naming split: `_SCREAMING_SNAKE` for a script's own global, `_lowercase` for
  locals, bare names crossing into `utility.sh`.
- 79-column hard max for all `tests/perf2html/` source.
- Comment blocks max 1 line (2 is an error via `test_source_scan.py`); longer
  reasoning goes in `declawed.md` instead. The file header is exempt from the
  line limit, the glyph check and the `ENGLISH_PUNCT` check.
- ASCII plus the specific whitelisted glyphs (`≈ ∞ ▲⯈⯇▼ … █ ░ ▒ ▓`), written
  literally, never as HTML entities.
- Never say "meta" - say "header" or "manifest".
- Timer artifacts contain `counter` data. Never "events"/"metrics"/"stats".
- Follow source code style. Alphabetization of source sections matters.
- Settings declared as annotation + empty sentinel + `load_into` - don't add
  accessors or conversions, don't turn off `F821`/`reportUnboundVariable`.
- Terminal-editor geometry: no vertical padding/margin/gap on text boxes;
  horizontal spacing only in specific increments (0, 1ch, 2ch).
- No decorative borders, no tooltips outside the two named exceptions.
- Design-pixel discipline: think in design px/ch, then scale; never retune a
  length by eyeballing one screen size.
- `scripts/` page assets may carry comments under the 1-line limit, one `#`
  line per class/function/field, no trailing comments.
- One dark theme, Monaco/monospace, no restyling the heat map's palette or
  curves without proposing first.
- `test_expected_behavior.sh` is expected to have its own constants distinct
  from the shipping scripts to compare against - not a bug to flag on sight.
- One line helper functions in `.sh` are discouraged and require approval.
- `error_exit` calls and other error messages must be only one line while
  printing relevant variables too.
- `test_all.sh` should print significant run times, it is not "no news is good
  news".
- When `test_all.sh` has run links to screenshots, reports and
  `test_expected_behavior.md`.
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
- A comment never opens with the name of what it documents. Not
  `foo: the function foo finds bar.`, just `Finds bar.`

## 1 Project Structure

Under `tests/perf2html/`:

- Shell: `perf2html.sh` builds, profiles, writes one report;
  `perf2html_diff.sh` measures nothing, subtracts two reports;
  `perf2html_batch.sh` runs baseline, modified (`-D CMAKE_C_FLAGS=-Os`), diff;
  `scripts/test_expected_behavior.sh` formats, lints, scans, runs the batch,
  validates; `scripts/test_all.sh` runs that with `--keep-artifacts`, then
  `scripts/test_error_handling.sh`, the failure-mode tests ending in
  `prettier --check`; `clean.sh` = `git clean -Xdf -e '!tmp/' -e
  '!tmp/**'` + ccache eviction; `scripts/settings.sh` every shell setting;
  `scripts/utility.sh` every shared function, sourcing inert, the test
  scripts' own in `scripts/test_utility.sh`.
- Python (`scripts/`): `settings.py` every Python/JS setting; `callgrind.py`
  the one parser; `callgrind_diff.py` delta + callers JSON;
  `callgrind_to_heatmap.py`, `build_report.py` (overview, callers),
  `build_flame_graph.py`, `trace_to_speedscope.py`; `theme.py` with
  `theme.css`/`theme.js` the one theme (`theme.js` = utility library);
  test-only: `test_report.py`, `test_source_scan.py`, `test_screenshot.py`.
- Page assets (`scripts/`): `frame.js` the top page's model; `menu.{js,css}`
  the menu (`menu.css` also styles the heat map's strip); `overview.html` the
  overview template; `callers.js` the callers view; `heat_map.{js,css,html}`;
  `flame_graph.{js,html}`, `flame_graph.js` polls `window.speedscope`;
  `ui_strings.js` (`str_*`); `error_overlay.js` first script on every page;
  `utility.js` second, relaying an error report up the frames and reporting a
  failed `<link>`/`<script>`/`<img>` load; `light_mode.css` the light mode,
  under `:root[data-dark-mode-="disabled"]`; `settings.js`
  (`settings_("NAME")` throws on unknown).
- `src/cyg_callback.c` trace hooks; `scripts/test_whitelist.txt`;
  `README.md` user contract, copied into every report; `tmp/` notes, `.md`
  only, gitignored, spared by `clean.sh`.

`_TESTS` comes from `tests/perf/Makefile.inc`. Words: "header"/"manifest"
(never meta); "counters" except callgrind's `events:`; "raw" = only the
overview's "raw data" link to `timer-artifacts-<unix>.txz`, temporary
recordings are "artifacts"; "settings", never "constants"; rows are
`ManifestRow`/`ManifestBlock`.

## 2 Commands

```sh
tests/perf2html/perf2html.sh [--verbose] [--keep-artifacts] [--regenerate]
    [--txz] [--report=DIR] [--target-dir=DIR] [--artifacts=TMP]
    [cmake_flags...]
tests/perf2html/perf2html_diff.sh [--verbose] [--keep-artifacts]
    [--regenerate] [--txz] [--target-dir=DIR] [--artifacts=TMP]
    [baseline-dir] [modified-dir] [report-dir]
tests/perf2html/perf2html_batch.sh [--verbose] [--keep-artifacts]
    [--regenerate] [--txz] [--artifacts=TMP] [--target-dir=DIR]
    [cmake_flags...]
tests/perf2html/scripts/test_expected_behavior.sh [--check-formatting]
    [--keep-artifacts] [--regenerate] [--verbose]
tests/perf2html/scripts/test_error_handling.sh [--help]
# no arguments to prove reproducibility.
tests/perf2html/scripts/test_all.sh [--help]
# no arguments to prove sobriety.
tests/perf2html/clean.sh [--help]
cmake -S . -B build -G Ninja -DCURL_USE_LIBPSL=OFF
cmake --build build --target perf      # EXCLUDE_FROM_ALL, must be named
taskset -c 3 ./build-relwithdebinfo/22_DCMAKECFLAGSO2g/tests/perf/perf \
    <test> [loops]
```

- `perf2html.sh` default `--report`: `perf2html_baseline_report`, or
  `perf2html_modified_report` with cmake_flags; after a source-only change pass
  `--report=perf2html_modified_report` yourself. `--report=DIR` is the report
  dir itself; `report_path_of` puts a name not starting with `/` or `~/`
  under `--target-dir` (default `$PWD`), the diff's three names too.
  `--artifacts` defaults to a `mktemp -d`, or under `--keep-artifacts` or
  `--regenerate` to `perf2html_temporary_artifacts/` in the report's parent
  dir (all three).
- Batch: `--target-dir` (default $PWD) holds the three default-named reports;
  a `--report=` is refused, exit 2; every other argument is a cmake flag.
- `test_expected_behavior.sh` takes only flags and runs the batch;
  `MANIFEST.txt` line 1 decides each report's `--diff`. Pass `--regenerate`
  every time except after `perf` was re-linked (wrongly passed, it refuses in
  <1s).
- `usage_show`'s heredoc is the only usage text. `toolchain_check` lists every
  missing tool with its install command, exit 1.
- After any `tests/perf2html/` edit:
  `tests/perf2html/scripts/test_expected_behavior.sh --regenerate`. Before
  final: `tests/runtests.pl`.

## 3 Build trees and measuring

- `build_paths` (perf2html.sh) is the one setter of `_TREE_NAME`,
  `_BUILD_TREE`, `_TRACE_TREE`, `_BIN`, `_TRACE_BIN`. Tree name = joined flag
  string's length, `_`, its alphanumerics (`22_DCMAKECFLAGSO2g`,
  `27_DCMAKECFLAGSO2gOs`) under `build-relwithdebinfo/` (`BUILD_DIR`) and
  `build-instr/` (`TRACE_BUILD_DIR`) at the repo root, never `/tmp`. Not unique
  across punctuation (`-DA_B=C` vs `-DA=B_C`). Each measuring run reconfigures
  its own two (~7s, recompiles nothing); `--regenerate` configures neither.
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
  never feed `--separate-callers=N` output to the callers page/heat map.
- Quick read: `perf <test>`, median of 3-5.

## 4 Artifacts, regenerate, test stages

- Artifacts dir holds, per report subdir, `perf-stat.<test>.<recorded>.txt`,
  `perf-stat.*.csv` (`PROFILE_TIMING_FILE_PREFIX`),
  `trace.<test>.<loops>.<recorded>.log` and the
  rows file `header.overview.<report basename>.txt` (`HEADER_ROWS_NAME`;
  `run_all` writes it, `_HEADER_FILE` set in `args_parse`). No `output.txt`
  ships: the callers page embeds perf/trace logs (`artifact_path_of
  timing-page`/`_TRACE_LOG`);
  the
  overview reads one `--perf-log NAME=FILE` per test, `all` included.
- `timer_artifacts_write` fills a transient `timer-artifacts-<recorded>/` in
  the subdir, each test's callgrind file stripped and a link to its
  speedscope JSON, packs it with `tar --dereference` into the report's
  `timer-artifacts-<recorded>.txz`, then removes it; the diff unpacks each
  input's (`profiles_extract`) into `<role>.<TIMESTAMP>/` in its subdir.
- `--regenerate` rebuilds pages from recordings, opening no report. First step
  of `recorded_reuse` (perf2html.sh) and `regenerate_check`
  (`test_expected_behavior.sh`): prove rows file and recordings exist.
  `recorded_reuse` restores `TIMESTAMP` from
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
  → `clear_overwritten_folders` (three reports and their `.txz`, never
  artifacts) → shfmt, ruff, clang-format, prettier → `long_lines_report` →
  `test_source_scan_run` → `lint_run` (pyright) → `batch_run` →
  `test_expected_report_check_run` → `test_expected_archive_check_run` →
  `screenshots_run`. No stage reaches inside a report; the batch itself runs
  no checks.
- `test_expected_behavior.sh` internals: `subprocess_run` =
  `command_item_print` plus plain `"$@"`, non-zero → `error_exit`
  `error: exit N from: <command>`; a Python tool = `subprocess_run python3`
  with `verbose_flags_of`; a stage = `heading_print`; status lines
  (`whitelist`, `regenerate`, `cleared`, `columns`) = `log_verbose`;
  `batch_run` = plain child, failure `error_exit` with its code; no `RUN_LOG`;
  own spellings `header_row_of`, `_REPORT_CHECKSUM_COMMAND`, `_SCREENSHOT_*`.
  `tool_find` (`test_utility.sh`, the pip and npm user bins too) answers
  through `$( )`, for `tools_resolve` and `test_error_handling.sh`'s prettier.
  `lint_run` runs `pyright_filtered_run` under `--verbose`. Only caller of
  `test_report.py`, `test_source_scan.py`, `test_screenshot.py`, `pyright`,
  `ruff`, and of `prettier` but for `test_error_handling.sh`'s last check.
- Whitelist: `whitelist_expand` → `_WHITELISTED_FILES`; `files_of()` picks by
  extension; blank/`#`/whitespace lines refused; a glob matching nothing is
  allowed (`src/*.h`), a non-regular match or empty list is an error.
  `--config`/`--project` always passed; `pyrightconfig.json` names no file.
- `test_screenshot.py`: modified + diff reports, `_VIEWS` ×
  `_SCREENSHOT_VIEWPORTS` × `_SCREENSHOT_DARK_VALUES` (`1`, then `0` light)
  → `tests/perf2html/screenshots/NN_<size>_<report>_<view>_dark-<0|1>.png`,
  `NN` the view's number in `_VIEWS`, then per size and dark value a 4k sheet
  3 shots wide, `thumbnail_<size>_<report>_dark-<0|1>.png`; imports no
  settings;
  each `_VIEWS` hash
  is a golden bookmark written out whole as one string literal, never
  formulated from a constant; error view
  `bad_function`; `report_incomplete` and `stylesheet_missing` shoot a copy
  lacking `assets/report_complete.js` or `assets/theme.css` under
  `tests/perf2html/build/screenshots_scratch/`;
  `--incognito`; under `--verbose` it prints
  `<report> -> <dir>` and `N screenshot(s)`.
- Debug modes, run in order: 1 `test_expected_behavior.sh` cold; 2
  `--keep-artifacts`; 3 `--regenerate`. `test_all.sh` runs mode 2, then
  `test_error_handling.sh`, and prints `perf2html test_all.sh all_tests_pass`
  last.
  `test_error_handling.sh` re-runs mode 2 `--verbose` with stderr `2>` into
  `tests/perf2html/test_expected_behavior.md` (gitignored), then checks the
  kept recordings (`test_error_cache_populated_check`) and proves a batch
  `--regenerate` measures nothing (`test_error_regenerate_cache_check`), then
  an uncached diff expected to pass (`test_error_diff_uncached_test`) and
  failure-mode tests on report copies in
  `tests/perf2html/build/test_error_handling_scratch/`
  (`_TEST_ERROR_SCRATCH`; kept by a failed run). `test_failure_expect NAME CODE
  --` checks the exit code and prints `ok <test>`; wrong code →
  `<test>: exit N, expected M, from: <command>` through `test_fail`, exit 1;
  last, `prettier --check` with `.prettierrc.json` over
  `tests/perf2html/test_expected_behavior.md`: the markdown must be what
  prettier prints.
  `test_expected_behavior.sh` and `test_error_handling.sh` source
  `test_utility.sh`, which holds `path_shown`, `test_fail`,
  `test_failure_expect`, `test_report_copy` and `tool_find`.

## 5 Shell library

- Paths: `INVOKED_FROM="$PWD"` above the `cd` to the script dir;
  `absolute_path` = `realpath -m -s` on `$INVOKED_FROM/<path>` (`~/`
  expanded); `$PWD` is `tests/perf2html/` after the `cd`; display via
  `path_display` only. `$_SCRIPT` finds the tool's own code only. A leaf
  script derives nothing from a collection (batch/test_expected_behavior own
  "three reports").
- `settings.sh`: alphabetical, no `$` words, parsed by
  `SettingsReader.shell_settings_read` (`-?[0-9]+` → int); one name in all
  three languages. `TIMESTAMP` per script (`$(date +%s)`) just above
  `INVOKED_FROM="$PWD"`; the test scripts declare none. Env vars,
  two:
  `PERF2HTML_HEADER_DEPTH`, `PERF2HTML_CLOCK_START_US`.
- Naming: script global `_SCREAMING_SNAKE`, local `_lowercase`, names crossing
  into `utility.sh` bare. `utility.sh` reads `ARTIFACTS_DIR`, `PERF2HTML_DIR_`,
  `INVOKED_FROM`, `KEEP_ARTIFACTS`, `REGENERATE`, `RUN_LOG` (batch has none),
  `TARGET_DIR`, `TIMESTAMP`, `VERBOSE`, `WRITE_REPORT_ARCHIVE`; sets
  `ARTIFACTS_DIR`, `KEEP_ARTIFACTS`, `REGENERATE`, `REMAINING_ARGUMENTS`,
  `TARGET_DIR`, `VERBOSE`, `WRITE_REPORT_ARCHIVE` (`shared_options_parse`,
  `ARTIFACTS_DIR` again in `artifacts_dir_resolve`), `SPEEDSCOPE_RELEASE`,
  `RUN_LOG` (`report_begin`),
  `SOURCE_CACHE_{PACKAGE,VERSION,DIR}` (`source_cache_sync`),
  `CHILD_EXIT_CODE`/`LOG_LINE_FROM` (`child_capture`), `QUIET_SWITCH`
  (`quiet_switch_set`), `VERBOSE_{COMMAND_NUMBER,ITEM_INDENT,BLOCK_PRINTED}`
  (`verbose_begin`, `block_lead`, `command_item_print`, `heading_write`,
  `verbose_filter`). A function's comment names every global it sets.
- Children: `child_capture PAGE_FILE cmd` (a `tee` into `$RUN_LOG` and the
  page, onward to stderr, `verbose_filter` or `/dev/null` by level, chosen
  before start; tee behind `if ! { ...; }` for `PIPESTATUS[0]`, a tee or
  filter failure a hard error);
  `command_run` for a tool; `page_command_run PAGE SHOWN cmd` when the lines
  are page content (caller writes the `$` line and `#` comments); `step_run`'s
  `"$@"` runs one of our scripts uncaptured. Values return through globals
  (`CHILD_EXIT_CODE`). `$( )` around `printf`/`date`/`basename`, or
  `verbose_filter`'s awk answer, is a value, fine.
- Failure: `error_exit CODE LINE...` = one ```txt fence on stderr, exit. Tool
  child: `failure_print_log_tail` = same fence holding `error: exit ...`.
  `cmake` configure output goes to `/dev/null` below level 2; `tree_build` →
  `child_capture_noisy` (= `child_capture` at 2); failure prints only error:
  cmake failed to build $command...
- Verbose: `verbose_begin` (after `args_parse`) exports its own
  `PERF2HTML_HEADER_DEPTH`, one past the depth it inherits
  (`test_expected_behavior.sh` 1, batch
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
  own lines. `verbose_flags_of` = one `--verbose` per level, one per line
  (`mapfile -t`). Python tools' ok lines: stdout, `--verbose` only. Quiet
  switches `ruff --quiet` and prettier `--log-level warn`, recorded once in
  `quiet_switch_set` (`QUIET_SWITCH`, empty under `--verbose`); pyright has
  none. `test_expected_behavior.sh --verbose 2> x.md` is the whole run.
- Manifest contract (`utility.sh`): `manifest_fault_of` (reader: why a dir is
  not a report, or nothing; takes each acceptable version string),
  `manifest_verify` (hard-error policy), `manifest_recorded_of` (first token,
  refuses empty), `manifest_recorded_row`, `manifest_value` (general),
  `manifest_table_of`, `manifest_write`, `manifest_wanted_phrase`,
  `checksum_compute`. Version strings `curl/perf2html.sh v1`,
  `curl/perf2html_diff.sh v1` and the checksum label are settings.
  `revision_describe REPO` = the one `<short>[-dirty]`.
- A writer runs `report_delete`, then flushes its artifacts subdir, so a
  refused delete keeps the last run's recordings; the batch runs it on its
  three reports before step 1. `report_begin` (creates dirs, opens
  `$RUN_LOG`, lays `README.md`/empty `assets/`) and `report_finish` (writes
  the shared `assets/`, `settings.js` among them, then `report_complete.js`,
  then the checksum, then MANIFEST.txt last, `log_verbose`s the entry page
  and, under `--txz`, writes `<report>.txz` beside the report) bracket every
  writer. A target
  is deleted unprompted only if it holds a `MANIFEST.txt`, its existence
  alone; a non-directory, or a dir without one, goes only on a typed y
  (prompt on stderr, a no is `error_exit 1`). `path_overlap_check` refuses
  two paths where one is, holds or sits inside the other: a report and its
  artifacts dir (in `report_delete`), a diff's output and artifacts against
  its inputs, the batch's artifacts against its three reports. Each path is
  also refused overlapping `tests/perf2html/scripts/` or holding
  `$INVOKED_FROM`.

## 6 Report layout

```text
OUTDIR/  index.html (overview)  <test>/index.html (callers, all included)
heat-map/{index.html,data/<test>.js}  flame-graph/{index.html,profiles/
<test>.js}  flame-graph-app/  assets/  sources/  README.md  MANIFEST.txt
timer-artifacts-<unix>.txz (full report only)
```

- `timer-artifacts-<unix>.txz` = every test's callgrind file, repo root
  stripped, + speedscope JSON, one deterministic `tar.xz` holding one root
  entry of the same name (`timer_artifacts_write`), the overview's raw data
  (`--raw-data`); a diff reads its inputs' (`timer_artifacts_find`) and
  ships none. `all/` = every test merged: no perf log, trace, flame graph.
- `MANIFEST.txt`: line 1 version string, then LABEL=VALUE. Full: `revision`,
  `cpu`, `build`, `executable` (repo-relative), `recorded` (`<unix> <human
  date>`), `checksum`. Diff: `baseline`, `modified`, `baseline_recorded`,
  `modified_recorded`, `checksum`, no `recorded=` (`manifest_check` copies
  rows verbatim). Line 1 decides a diff input, which also holds one
  `timer-artifacts-*.txz` at its top (`timer_artifacts_find`); diffs can't be
  diffed. Version line must match EXACTLY; errors print found and expected.
  `checksum=` = POSIX `cksum` over every file but the manifest, `LC_ALL=C`
  sorted, relative paths; `home_dir_check` fails on `$HOME`.
- Diff report: no flame graph, no native timing, no raw data; a callers page
  has no preamble. Overview reads `--diff-profile NAME=FILE` per paired
  test; a test in one report only → `tests_pair` error.
- Pages: shared assets linked, never inlined; hrefs from
  `theme.shared_href(depth, name)` (overview 0; callers, heat map and flame
  graph 1); stylesheet from `Theme.css()`; classic
  `<script src>`/`<link>` only, no `fetch()`, no ES modules; opens from
  `file://`. `sources/<source_name()>` (display path, non-alphanumerics → `_`,
  plus `.js`); `FileModel.source` read via `source_text(file_path)`;
  `flame_app_install` needs each glob to match one file.
  `report_complete_write` ships `assets/report_complete.js`
  (`window.report_manifest_table_`, the preformatted manifest table
  string, no `checksum=`, then `screenshot_label_script_print`, showing a
  `screenshot` URL param as a label).

## 7 Python

- Style: one enclosing class per script for non-exported functions; `import X`
  only, alphabetical; `from` only for `__future__` `annotations`,
  `collections.abc`, `typing`. `pyright` 0 errors. Costs are
  `callgrind.Costs`, summed by `costs_add`. No multi-line HTML/CSS/JS
  literal: real files via `theme.asset_text_read()`.
- `settings.py`: settings first, then `SettingsReader` and `SettingsWriter`
  (constants carry `_`); cut at `_SETTING_NAMES`; `_is_setting_name()` strips
  a leading `_`. A consumer declares annotation + empty sentinel, then
  `settings.load_into(__name__)` first (`match_check`, `sentinel_check`,
  `type_check`); own constants below; `bool` sentinel `False`; `E401`/
  `I001`/`E501` off. Names `SCREAMING_SNAKE`, broad→narrow, 2+ words, unit
  suffix (`_PX`, `_MS`, `_PERCENT`, `_SHARE`, `_CHARS`, `_BYTES`). Every
  constant that changes a pixel is a setting; `STYLE_*` = every setting
  that changes a pixel or picks a colour, written into a style as is or
  computed with first. A stylesheet keeps only zero, none, hidden and
  values with no visible effect.
  `settings_script_write()` ships the module as frozen JSON (all
  JSON-serializable; the manifest table is not among it, see `manifest_table`
  and `report_complete_write` in section 6); `settings.js` is read
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
  key, 19 keys). Every object names its code without debug info `???`;
  `file_key_of()` keys each apart as `<object basename>/???`, shown
  `(unknown)` by `path_norm()`.
- `build_report.py`: `_RANKING_COUNTER_NAME`; `Profile.value()` raises
  `KeyError`; `BuildReport.test`/`.diff_test`.
- `callgrind_diff.py`: `counters_check()` names both lists; `--callers-output`
  required (name, flags, JSON keys are contract).
- `callgrind_to_heatmap.py`: `data` writes one test's
  `heat-map/data/<test>.js`, the `sources/` it shows and, for the merged test,
  `assets/pulldown_text.js`; `page`, after the last `data`, writes the one
  `heat-map/index.html`, its `__SCRIPTS__` in the order
  `report_complete.js`, every `sources/` file, `pulldown_text.js`,
  `settings.js`, `theme.js`, `heat_map.js`; head from `theme.page_document`
  (`theme.page_preamble_scripts()`, `extra_css`, `body_holds_scripts`);
  `model()`/ `diff_model()`; `model()`
  refuses an unemitted `RANKING_COUNTER_NAME`.
- `trace_to_speedscope.py`: busiest run's first
  `FLAME_GRAPH_MAX_RECORDED_CALLS` (200) calls; `buildid_verify` refuses a
  moved build-id (run before rebuilding the trace tree); inlined helpers are
  frames; `_HEADER_MAGIC` = `cyg_callback.c`'s `CYG_CALLBACKS_MAGIC`.
- `cyg_callback.c`: `next` a pointer, `end` a variable (11/12-instruction hot
  path); `buildid` path is `realpath`; single-threaded.
- `test_report.py`: greps `loadFileFromBase64` in the flame graph page and
  its scripts and `report_ui_.layout_activate` in the heat map page's; reads
  the entry each `data/<test>.js` and `profiles/<test>.js` files under its
  global; report dir required;
  `manifest_recorded_labels` get the unix-time check; `perf_tool_check` reads
  the callers page's `perf log` section; `diff_baseline_check`
  (`has_baselines`, a diff's) fails a file, line or function change past its
  baseline.
- `test_source_scan.py`: file paths (`nargs="+"`), read once; a block =
  consecutive whole-line comments plus a `/* */` or `<!-- -->` opened first on
  a line, file
  header exempt from the block limit (`_COMMENT_BLOCK_MAX_LINES`, 1), the
  glyphs and `ENGLISH_PUNCT`; glyphs
  `_SOURCE_SCAN_ALLOWED_NON_ASCII_CHARS` (`≈ ∞ ▲ ⯇ ⯈ ▼ … █ ░ ▒ ▓`, literal);
  `_COMMENT_SYNTAX_BY_EXTENSION` (`.html` adds `//`, `/* */`); faults
  `path:line: message` sorted. The 79-column limit is unrelated to
  `HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS` (80).
- Reformatting `heat_map.*`, `menu.*`, `frame.js`, `flame_graph.*`,
  `callers.js`, `overview.html`, `settings.js`, `error_overlay.js`,
  `utility.js`, `light_mode.css`, `ui_strings.js`, `theme.css`, `theme.js`,
  `README.md` changes reports;
  text echoed into a perf/trace recording is page content.

## 8 Pages and JS

- `ui_strings.js`: `str_*`; `text_of(id)` throws on unknown; no boundary names
  or number notation; `(no recorded caller)` stays in Python matching
  `str_no_caller`; empty pulldown = `str_no_match`.
- `error_overlay.js`, exempt from every rule: `window.catch_show_throw_(fn)`
  wraps an entry point (load body, listener, timer); a throw, or a returned
  promise's rejection, reaches `err_overlay_show_` as the `Error` itself, then
  is rethrown, since a `file://` page gets another file's error as "Script
  error."; `err_overlay_show_(error)` and the `error`/`unhandledrejection`
  listeners make `error_text_of_(error)` (stack, else name and message, then
  each `cause`) in the realm that caught it; the first error of a load wins;
  a frame posts `{report_ui: "report_error", report: {page, text}}` up
  through `utility.js`,
  `page` its report-relative path and hash; the top replaces the document
  through `document.open()` one task later with one well-formed page, every
  text HTML-escaped, one `<pre>` in `white-space: pre`, no Markdown, no
  wrapping: `perf2html error`, `address` (its report-relative path and hash
  at render), `page` when a frame threw, the text, then `manifest` and
  `window.report_manifest_table_` raw, else "Report has no
  assets/report_complete.js"; the report root, the directory above
  `assets/` from `document.currentScript`, is cut from every text; font
  size is `DESIGN_FONT_SIZE_PX` (24) scaled once at `page_write_` by
  `window.innerWidth / DESIGN_COORDINATES_WIDTH_PX`, no resize listener;
  two links, `copy` (`navigator.clipboard.writeText` of the text shown,
  unescaped) and `back` (`history.back()`); a `hashchange` or `popstate` on
  the written page reloads it; touches the URL only via `back`, reads no
  other script.
- JS settings: each `.js` resolves each `settings_("NAME")` once into a
  same-named `const` at the top of its IIFE, never in a render path; every
  number/colour/key/bound is a setting (`MENU_PULLDOWN_KEY_NAMES`).
- Names: `snake_case` ours; camelCase owned by browser/Python (DOM,
  storage/URL key, TypedDict key). A CSS class, id, colour role or value
  entry is its object path, `-` between words, singular words: the views
  it shows on (`callers`, `heat-map`, `menu`, `overview`, alphabetized, or
  `page` when the views are all of them), component, part; no word its
  parent already gives. State classes
  (`current_`, `selected_`, `open_`, `empty_`, `drag_`) and layout helpers
  (`.band_`, `.table-box-`, `.page_`) stay plain. Every class, id, CSS
  custom property and `data-*` attribute perf2html writes ends in a
  marker, `-` when the name holds a `-`, else `_` (`#heat-map-tree-`,
  `.current_`, `--menu-title-width-`, `data-test-name-`), setting it apart
  from DOM and native widget names. JS reads a `data-*` attribute through
  `getAttribute()` by its written name, never `dataset`.
  `window.report_sources_` keyed by
  display path, read by `source_text()`. Markers `__NAME__` and `__DATA__`
  (the `settings.js` template), `__SCRIPTS__`, `__APP_CSS__`, `__APP_JS__`,
  `__RAW_DATA__`, `__MANIFEST__`, `__TESTS__`.
- Frames: the overview frames one view at a time, a test's callers page,
  the heat map app or the flame graph app, the page
  `report_ui_.address.page_href_of()` names. `frame.js`, the model, runs on
  the top page alone as `window.report_frame_` (`activate()`,
  `address_now()`, `address_request(hash)`, `view_post(message)`).
  `view_show()` parses and checks the top's hash, records it, calls
  `report_menu_.address_show()`, then loads the view by
  `location.replace(page_href + location.hash)`, never `iframe.src`, or
  shows the home panel. `menu.js`, the controller, is `window.report_menu_`
  (`address_show()`, `dark_mode_show_()`, `menu_key_take(key)`) and starts
  every navigation
  through `report_frame_.address_request`. The frame's one message listener
  hands the controller each key a view sent up. A view uses `theme.js` doors
  alone, `report_ui_.address` and
  `report_ui_.view_activate({preferences_apply, recenter})`, which requests a
  clicked address link, forwards keys and meets the downward strings. The
  flame graph app forwards no keys.
- URL = whole state, one grammar on every page: `#test=<t>&view=<v>`, `view`
  one of `callers`, `heat-map`, `flame-graph`; the heat map adds
  `&file=<f>[&line=<n>]` or `&function=<name>`; the flame graph adds
  `&localProfilePath=profile`, speedscope's own key, which speedscope reads
  from the same hash; none = the overview's home. `report_ui_.address`
  (`of_hash`, `hash_of`, `home_hash_of`, `link_hash_of`, `page_href_of`,
  `request`) is the one JS door and `build_report.py` `address_of` the one
  Python door, the key names string literals in those alone. Keys parse in
  any order and are written in that order; each fault throws its own
  `str_error_hash_*`. The top page forwards its hash to the view unmodified,
  and no page rewrites a hash it received. Regression path
  `#test=<t>&view=heat-map&file=<f>&line=<n>` reloads both levels.
- Storage: only `heat.counter`, `heat.scale`, `heat.sort`, `view.dark_mode`,
  `view.scale` (a
  scale bar stop, 0..20), `split.<pane>`. `STORAGE_VERSION` =
  `perf2html v5` under `STORAGE_VERSION_KEY` = `perf2html.version`;
  mismatch sweeps owned keys; `view_storage.preferences_clear()`, the reset
  button's door, sweeps every owned key; new keys go in
  `STORAGE_OWNED_KEYS`/`STORAGE_OWNED_PREFIXES` (`split.`). `localStorage`
  refused is a designed condition, not a fallback.
- Messages up `{report_ui: <name>, ...}`: `address_request` (`hash`, from
  `report_ui_.address.request()`), `menu_key_pressed` (`key`, a view's
  forwarded key), `report_error` (`report: {page, text}`, utility.js's
  own, relayed up by each frame). Down, strings through
  `report_frame_.view_post()`: `report_ui:layout_reset`,
  `report_ui:recenter`, `report_ui:tests_pulldown_closed`,
  `report_ui:dark_mode_apply`.
  `#menu-reset-button-` and a scale change post `report_ui:layout_reset`,
  which resets the home panel's columns too.
- Menu, the overview's alone: logo → `index.html`, a plain link.
  The buttons follow `MENU_BUTTON_ORDER`, the flame graph's and dark mode's
  before reset, each but dark mode's numbered and keyed `(index + 1) % 10`
  by `menu.js`, which writes
  every label. A button a report lacks, a diff's flame graph, keeps every
  other number. The flame graph button hides while the buttons name
  `MENU_PULLDOWN_MERGED_TEST_NAME`, and the view buttons' hrefs follow the
  address. Pulldowns `tests`, `files`, `functions`, `pulldown_attach()`
  (`menu.js`) each: tests entries are `menu_link_render()` links
  (`tabindex=-1`, `data-test-name-`), box reads the test on show or
  `MENU_PULLDOWN_MERGED_TEST_NAME`; files/functions entries are
  `window.report_pulldown_text_` names (`pulldown_text_write`), heat map
  addresses in that test; open, it is a `new RegExp(text, "i")` search
  steered by `MENU_PULLDOWN_KEY_NAMES`; blur closes; list `z-index: 3` over
  `.band_`. A view forwards keys typed outside a field (typed characters
  always, but `MENU_PULLDOWN_SKIPPED_KEY_NAMES`; command keys only while the
  tests pulldown is open, until `tests_pulldown_closed`; never Tab or
  Shift+Tab); the pulldown's `key_take` is the one key handler and
  `search_box_focus()` takes focus, else `str_error_pulldown_focus_refused`.
- Keyboard: `WIDGET_KEY_NAMES` names every key a focused widget takes,
  read through `report_ui_.widget_key` (`of`, `activates`, `link_click_take`,
  Space on a focused link). Each widget is one tab stop, moved by
  `tab_stop_move()`: the heat map tree (`role="tree"`), a table whose rows
  open something (`table_rows.attach`, `role="treegrid"`), the ticker tape
  (`role="toolbar"`), the pane splitter (`pane_splitter.attach`,
  `role="separator"`). A key a widget takes is default-prevented and never
  sent up. `view_show()` hands the focus from a panel it hides to the view,
  or to the home's last tab stop.

## 9 Look and feel numbers

- Design: `STYLE_DESIGN_COORDINATES_WIDTH_PX` 1920, fitted by
  `design_scale_apply()` (one `zoom` on `:root`, every resize); Monaco
  `STYLE_DESIGN_FONT_SIZE_PX` 12, `STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX` 7.2
  → 266 ch; `font_fit_apply()` measures `0` via canvas `measureText`, sets
  `--design-font-fit-` (`STYLE_DESIGN_FONT_FIT_PROPERTY`) on `:root`; the
  one font size is `body`'s
  `calc(var(--design-font-size-px-) * var(--design-font-fit-))`, inherited
  everywhere. Unzoomed: `window.inner*`,
  `documentElement.client*` (convert with `design_px()`), `vh` (use
  `--design-viewport-height-`, `STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY`).
  Width media queries can't fire.
- Scale slider: `STYLE_DESIGN_SCALE_*`, 0.5..2, default mid-travel
  (`STYLE_DESIGN_SCALE_DEFAULT_TRAVEL_SHARE`), each half geometric
  (`design_scale_multiple_of()`); `design_scale_travel_set()` is the door;
  `menu.js` then posts `report_ui:layout_reset`, which resets column widths.
- Geometry: cells `0 1ch`, `.heat-map-source-file-header-` 2ch,
  `--menu-title-width-` in `STYLE_VALUE_ENTRIES`, tree indent depth ×
  `STYLE_HEAT_MAP_TREE_INDENT_PER_LEVEL_CHARS` in ch.
  The only `title=` attributes: `<iframe title="report page">` and `<th>`. Only
  `th`, `.band_` and `#heat-map-minimap-` are sticky.
- Colour: `STYLE_COLOR_PAIR_ENTRIES` maps each palette colour, lighter then
  dimmer per pair, to its roles. A role is its object path, then any state,
  then `fg`, `bg`, `outline` or `border`, `-dim` on a dimmer colour, then
  the marker `-`. Each thing a page colours has its own role, so the
  palette is the one control surface. `Theme.css()` writes a role only
  when a stylesheet names it. Every other value a stylesheet draws with is
  a `STYLE_VALUE_ENTRIES` variable.
  `STYLE_HEAT_COLOR_STOPS` palette; `ramp_channels_at()` the one interpolation
  (`cell_style()`, `logo_color_at()`); cells paint the stop opaque, their
  text on-bright above `STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE`.
  `heat_of_share()`: clamp to `STYLE_HEAT_COLOR_FULL_SCALE_PERCENT`, divide,
  curve;
  nothing measured off the data; a diff maps [-100..100%], 0% at the 5.5
  midpoint. Dropdown = curve × scope; `scale` is an entry. Scope = denominator
  only (`global`, `per file`, `per function`; `share_in_scope()`); a diff
  divides by the thing's own baseline (`diff_share_of()`), one scope
  `per line`.
- Columns: `column_extents()` → `column_limits()` (lo, hi +
  `STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS`) → `column_width_text()`, twins in
  `theme.py`/`theme.js`; lo = `data-min-`. L/H = Σlo/Σhi of non-grow,
  S = H - L,
  G = grow lo: `{lo}ch` if hi = lo, else `clamp(lo, lo + (100cqw - (L+G)) *
  (hi-lo) / S, hi)`; grow `max(G, 100cqw - clamp(L, 100cqw - G, H))`; G = grow
  `width` or `STYLE_TABLE_GROW_COLUMN_NARROWEST_CHARS` + extra. `.page_`,
  `.heat-map-home-`, `.heat-map-source-`,
  `.heat-map-source-line-detail-` are inline-size containers;
  `#heat-map-main-`, the box scrolling the heat map's, keeps
  `scrollbar-gutter: stable`. Drags use `design_px()`
  rects and `clientX`, floored at `data-min-`.
- Notation: `2.1K`/`2.0G`, `63.20%`, `≈0.00%` above 0 and under the floor,
  exact zero empty, a heading's
  zero share `0.00%` (`zero_percent_text()`); every share, multiple and time
  keeps `NUMBER_FRACTION_DIGITS` (2) decimals; floor
  `NUMBER_SMALLEST_PRINTED_PERCENT` (0.01). Diff: no `+`; the arrow, then the
  amount right-aligned in the floor's amount width (8 characters, 9 in all;
  `signed_percent_amount_chars`/`SIGNED_PERCENT_AMOUNT_CHARS`, derived from
  `NUMBER_FRACTION_DIGITS`, not a setting), so the arrow touches the amount
  only at the floor, share cells keeping the spaces (`white-space: pre`):
  `▲  11.11%`, `▼-100.00%`; ASCII hyphen for amounts; `▲  ≈0.00%` under
  0.01%; `▲      ∞%` on a
  rise from a zero baseline, a fall past its baseline refused
  (`diff_share_of()`), so `▼-100.00%` is the floor; past 100% a multiple
  `▲   1.30x`; at/past `NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES` (999.99)
  `▲     ≈∞%`.
  `theme.js` `report_ui_` and `theme.py` `NumberFormat` match by hand; README
  "Reading A Diff Report" is the spec.

## 10 Diff semantics

- Every number is MODIFIED - BASELINE per (function, file, line). Delta is
  callgrind format without `calls=` → no call columns (`HAS_CALL_GRAPH`);
  callers from `callgrind_diff.py --callers-output` JSON keyed `<fn>` and
  `<display path>\n<line>`, a line's baseline summed over every function on
  it, as the line row sums its delta.
- Share = `(new - old)/old` of the thing's own baseline: 1→0 = `▼-100.00%`,
  90→100 = `▲  11.11%`, 1→1 empty; new in modified = `inf`/`Infinity`,
  `▲      ∞%`, heat-clamped.
  `events` = recorded counters; `costs_fit()` pads, trims trailing zeros;
  ranking and heat use `abs()`; `profile_magnitudes()` (Σ|delta|) feeds
  `heatMapTotals.totals`; `summary:` is the signed total.
- Diff overrides live in the one `if (IS_DIFF) {...}` block of the heat map JS.

## 11 Why the heat map

`-O2` inlines small statics, so function tables misattribute; the heat map
shows cost per line. Cross-check `callgrind_annotate --show-percs=yes`.
