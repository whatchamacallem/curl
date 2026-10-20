# CLAUDE.md is a symlink to declawed.md

## Project Rules

The Project Rules section is set by the project maintainer and must not be
modified without request. The Lookup Accelerator is maintained by the agents
using declawed.md and not the project maintainer. The maintainer is the final
authority and decides correctness and requirements, however discrepancies are
worth fixing. Do not use the AskUserQuestion tool and use numbered number
sub-lists per ISO 2145.

Maintain an engineering log for each session in `tests/perf2html/tmp`
following this format:
`tests/perf2html/tmp/tasks_$day_of_month_$24_hours_and_minutes.md`. This is
formal paperwork with no chit chat required. Text is only added and not
modified. Use ISO 2145 for tasks and do not restart numbering tasks within a
single conversation. Preserve the users literal text in the task list first,
and concatenate additional feature requests to that section. In a second
section, list your intended order of operations to execute the users requests
before starting. Then add a separate postmortem section only when all
subagents are complete and all tasks are ready for review. Anything like a
postmortem at the end of a run must include all unfinished tasks and lost
subagents. Provide the user with the postmortem text directly in the
conversation as well as providing a link to the task doc. Provide a single
sentence bug, task or other description alongside every in-conversation
postmortem reference to a numbered item that is not itself in the postmortem.

### Top of mind

- Overconstrained goals introduce failure modes that are best resolved by
  conversations with the user that identify the contradictory requirements.
- Overconstrained solutions introduce failure modes that are best resolved by
  conversations with the user that identify missing long term requirements.
- No fallbacks: broke is broke. Never swallow an error, provide a default, or
  have a "just in case" branch for a case that can't happen - throw so it
  fails loud with a call stack or exit with the right Unix error code.
- Any error is a hard error, reported immediately, first failure only - no
  script collects failures, tallies of failures.
- When asked to update this document then further confirmation should not be
  required to fix all discrepancies observed, and remove all obsolete
  information even if unrelated to your work.
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
- No combined test data: every number is one test's, or one diff's of one test.
  Nothing sums, merges or averages tests, and no page shows test data in a
  combined form where each test's own contribution is not explicit. The merged
  `all` suite went for this reason.
- A value written twice and "kept in step" is banned - one setting in
  `settings.sh`/`settings.py`, read everywhere.
- Nothing searches, harvests, derives, resolves or finds a file, and nothing
  lists an artifacts dir: a tool takes the perf2html*.sh scripts' own canonical
  paths under the scripts' own flag names, reads `test_list.txt`, and composes
  every name from a settings format.
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
- Do not reference `CLAUDE.md` or `declawed.md` outside this doc. Do not
  explicitly mention the tests being tested themselves in other source.
- The source formatters may need to run twice to be stable. Alert the user
  if they are not.
- If a source reformatting tool can be used to fix an error then stage the
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
- All constants must go in settings.py or settings.sh. The only exception is
  for the numeric constant zero and the color clear.
- `CLAUDE.md`/`declawed.md` is not user documentation and is exempt from
  formatting and validation. Ignore formatting errors it will never be added
  to thw whitelist.
- Provide links to screenshots showing changes in all postmortems.
- The perf2html_diff.sh script has to be able to run on a remote machine with
only two `.txz` compressed reports as inputs. It has to work without access
to any source code or repository involved in the report.

### Accidental-Requirements, Requirements-Data-Loss, and Requirements-Refusal

Accidental-Requirements, Requirements-Data-Loss, and Requirements-Refusal are
a set of processes observed in multiple case studies that can chain together
to make it impossible to specify requirements to an agent at all.

Accidental-Requirements starts when an agent writes code because that code is
handy, illustrative or already lying around, not because the design called for
it. Nothing in the plan motivates the code, so nothing in the plan constrains
it. Then the next session reads the tree before the plan, sees working code,
and treats that code as a decision somebody made: the shape is preserved, the
interfaces built on, the code quoted as prior art. An example nobody chose
becomes architecture by seniority.

The case studies showed three forms of it:

- One planning session surveyed the existing code before writing the plan, and
  the plan carried an older tool's command loop and commands into the new
  design. A decision made for a different problem rode in on the strength of
  its mere existence, and a later round of questions had to remove it.
- Another test plan proposed reusing an existing test driver, the stated
  reason being that the driver existed. That is reuse chosen by availability,
  not by the test plan.
- The injected project context and the memory notes described the old code in
  detail, so every session started with that code in mind before opening the
  plan. The precedent was renewed even in sessions that never read the files.

The Requirements-Data-Loss process has been observed as a compounding input
step to the Accidental-Requirements process. Accidental-Requirements can
operate independently; the pair is simply noted here because it is a wild
ride.

Requirements-Data-Loss happens when a planner reasons its way to a good API,
decides it is too much for the moment, writes down the smaller one, and leaves
at most a clause saying the larger one is for later.

- The reasoning that produced the discarded good API is gone: not in the plan,
  not in the questions, not in the code. The maintainer is left holding the
  wrong interface with no record of the right one to judge it against, and the
  next session cannot tell a better design was ever on the table.
- In the case studies, requirements were both dropped without a trace from the
  planning process, and then incorrect requirements were copied into the next
  plan and from there into the code as if settled.
- The only recovery is for the maintainer to rediscover the design, by keeping
  engineering logs and doing case studies on all planning.

This mode is worse than the first because it destroys information rather than
adding some. A deferred feature with its full design written beside the
deferral costs the maintainer one question. A deferred feature with its design
discarded costs the design.

Put more simply, first Requirements-Data-Loss knowingly produces the wrong
API. Then the Accidental-Requirements process ossifies it, because once the
reduced API is in the tree, that is the thing later sessions preserve.

Requirements-Refusal is when the agent decides not to follow instructions and
silently carries out unrequested (and thereby easily incorrect) work instead.
This behavior may be the result of the agent trying to make a better choice
for the user. However, the end point is a breakdown in communication as
unsatisfied requests accumulate and the user becomes frustrated and confused.

- The pull for an agent is hard to resist because agents are trained not to
  break what exists, and code is more concrete than a sentence in a plan, so a
  conflict between the two is settled in the code's favor without anyone
  noticing a choice was made.
- Clear instructions to work from first principles are ignored and users may
  simply not be informed, so problems remain unaddressed.

Please consider the effects of Requirements-Data-Loss,
Accidental-Requirements, and Requirements-Refusal at the same time. It is like
requesting a new skyscraper and never getting a call back because they didn't
think you knew how deep a hole they had to dig.

Here are ways to avoid these.

- Nothing concrete exists ahead of the prose that describes it, so there are
  no Accidental-Requirements if nothing is added to the design without being
  motivated by a requirement.
- Injected context and memory notes describe current state, not design. A
  design decision found there is checked against the plan before anything is
  built on it.
- Prevent Requirements-Data-Loss by writing APIs and architecture for as much
  of the system as possible, from the top down, before ever writing any code.
- Write software from the bottom up using unit tests first, and integration
  tests second. Once the APIs are done, the unit tests begin.
- Reuse is chosen by the plan, never by availability. "It exists" is not a
  reason. Code is cheaper than negotiating requirements, and so requirements
  alignment needs to be prioritized over the cost of rewrites.

When asked to write a planning doc, read all the engineering notes related to
the conversation to understand the evolution of the users requirements while
responding to questions. Analyze the users requirements throughout the process
in those planning docs. Separate the requirements into:

- `A`: Request unsatisfied or modified without cause.
- `B`: Request unsatisfied or modified with cause but without confirmation.
- `C`: Request confirmed withdrawn or modified.
- `D`: Request satisfied without modification or withdrawal.

Add both `A` and `B` class requirements in a section to the planning doc at the
end explaining whether you were able to satisfy the requirements in the new
plan, as is preferable, or if multiple choice questions have to be answered to
try to solve for all the requirements simultaneously.

### One-door glossary

The single function/check owning each concern - never bypass or duplicate:

- `manifest_verify`/`manifest_fault` - whether a dir is a report.
- `regenerate_check` - whether `--regenerate` may proceed.
- `sources_match_check` - whether a diff's two reports show the same source
  code: every source file both reports show is byte identical, a file one
  shows alone is that report's (perf2html_diff.sh).
- `DerivedPaths` - every path a diff shows, as its two reports' paths
  documents show it, `in_baseline` naming the report its source is copied
  from (callgrind.py).
- `artifact_path` - every temporary artifact path, a printf format of
  `ARTIFACT_RUN_FILE_FORMATS` or `ARTIFACT_TEST_FILE_FORMATS` applied to a
  directory and a test name (utility.sh, artifacts.py).
- `report_artifacts_dir` - a report's own artifacts dir,
  `REPORT_ARTIFACTS_DIR_FORMAT` of `--artifacts` and the report's name
  (utility.sh, artifacts.py).
- `artifacts_verify` - whether a temporary artifacts dir holds every file the
  contract names, first miss exit 2 (utility.sh).
- `test_list.txt` - the one list of a run's tests, born from `TESTS_C` in
  `perf2html.sh`, read everywhere.
- `counter_value()` - all counter lookups (callgrind.py).
- `root_reach()` - every recording cut at `CALLGRIND_ROOT_FUNCTION_NAME`:
  the root and what the calls reach from it kept, the root's calls into
  `root_call_count`, the summary the kept lines' sum; a delta is not cut
  (callgrind.py); `caller_calls()` every calls per caller aggregation.
- `function_line()` - the one line a function is addressed at: the line before
  its callgrind entry line when that line carries no counter and the
  function's counters span more than one line, else the entry line
  (callgrind_to_heatmap.py).
- `report_source_database_` - the one list of the files and functions a report
  names, every test's union, no counter (scripts/source_database.js).
- `text_clip()` - every cell text cut at its column's `clip`;
  `table_slide_press()` every column width, a drag setting its title
  cell's `min-width` (theme.js).
- `checksum_compute`/`_REPORT_CHECKSUM_COMMAND` - report checksums, kept
  separate, re-verified on every open.
- `share_of_test()` and `share_of_function()` - every regular heat map share,
  a file's or a function's of the test, a line's of the summed self of the
  functions costing it, `lineFunctions` of the model; a diff divides by the
  thing's own baseline through `diff_share()` (heat_map.js).
- `diff_share()` - every diff share, a fall past its baseline refused
  (theme.py/js).
- `fixed_text()` - every decimal a page prints; `percent_text()` every
  share, `signed_percent()`/`signed_percent_text()` every diff share
  (theme.py `NumberFormat`, theme.js `report_ui_`); theme.js's
  `uses_whitespace` false where nothing aligns: a callers cell, a call
  graph share no sibling's shown share lines up with; the call graph
  prints no zero share.
- `edge_share()` - every call graph share, a callee's calls per call of its
  caller, the root's calls from its row, a diff's the change of that through
  `diff_share()` (call_graph.js); `call_graph_roots()` the one root a call
  graph starts from, any other uncalled function refused (build_report.py).
- `design_scale_stop_set()` - every scale change; `menu.js` then posts
  `layout_reset`, which resets column widths, pane widths and heading row
  counts.
- `information_box_render(file_path, line_number)` - every file, function
  and line info box, answering `{markup, copy_text}`, line 0 the file's
  (heat_map.js).
- `hash_for_location()` - every heat map link into a file at a line, a
  function's line written as the function's hash (heat_map.js).
- `report_ui_.strip.render(strip_element, entries, status_entries)` - every
  strip cell: the menu and its status bar, the heat map strip, each table
  heading (theme.js).
- `report_ui_.resize_settle_register(callback)` - every window resize
  settle: the one animation frame per rendering update,
  runs `layout_refresh`, then each callback in registration order; a scale
  change settles with the refresh alone (theme.js).
- `template_fill(template_text, marker_values)` - every template marker
  fill, a marker its template lacks refused (theme.py/js; `settings.py`
  refuses a missing `__DATA__` itself, as theme.py imports it).
- `window.render_element_`/`render_element()` - every tag a page
  script or a page builder writes, each attribute escaped through
  `window.render_html_escape_`/`render_html_escape()`
  (theme.js/theme.py); the one HTML composition system per language,
  `report_ui_.render_table` every table (theme.js),
  `window.render_element_of_` every element made from markup.
- `window.render_menu_button_`/`render_menu_button()` - every menu
  button: a strip cell, a control, a ticker tape entry (theme.js); a link
  in a table or a page is a plain anchor from `render_element()`.
- `window.render_page_emphasis_` - every page emphasis, called by
  the strip for a heading title (theme.js).
- `heat_cell_style(percent, curve, is_diff)` - every heat color, JS
  alone; Python paints nothing.
- `table_sort.records()` - every table sort; `render_table`'s
  `on_sort` the one column title click (theme.js).
- `report_preferences_.now()` - every read of the counters, calls, heat
  scale and heat sort preferences; `preference_choose()` on the top
  page the one writer, relayed down on every message, a view taking it
  through `report_preferences_.relay_handler()` (preferences.js).
- `load_log_append()` - every load log entry, on the clock the top page's
  navigation started, a framed page posting it up (utility.js);
  `report_load_log_.page_render_log()` and `.event_render_log()` every
  render entry, a view drawing after its own loads calling its load render
  log once drawn through `view_activate`'s `load_render_defer`.

### Working agreement

- This is a test driven development shop. Routine iteration on HTML generation
  can be tested while working (unless otherwise asked) with:
  `perf2html.sh --regenerate --verbose 2> tmp/perf2html\.md`
  from `tests/perf2html/`. Use `--keep-artifacts` to flush artifact cache and
  then keep the new ones.
- Mandated workflow: use `--keep-artifacts` and `--regenerate` whenever
  possible, every run of `perf2html_batch.sh` or
  `test_expected_behavior.sh` after the first measuring run, unless the
  recordings' file formats changed or a stage was killed part way, leaving
  recordings incomplete. Only then measure again, once, with
  `--keep-artifacts`.
- Debug mode is a run given `--keep-artifacts` or `--regenerate`; every other
  run is non-debug mode, `perf2html_batch.sh` with no arguments or cmake
  flags alone among them. Non-debug mode keeps nothing: each `perf2html.sh`
  and `perf2html_diff.sh` invocation deletes its artifacts subdir, its log
  with it, at every exit, a failed one too, and the batch keeps no artifacts
  dir and no log of its own; a failure's log tail still reaches stderr.
  Debug mode keeps the artifacts in `perf2html_temporary_artifacts/` for a
  later `--regenerate` and for debugging.
- Copy `tests/perf2html/screenshots/` to `tests/perf2html/screenshots-gold/` once
  its shots are right, then iterate with
  `scripts/test_expected_behavior.sh --regenerate`. That rebuilds every page
  from the same recordings, so the recorded time, the raw data archive name,
  the timings and the counters the shots show match the gold, and it
  compares each shot with its gold twin, writing a `compare_` image of each
  difference into `tests/perf2html/screenshots-diff/`; a difference is then
  the edit's own. Only `--regenerate` compares: a measuring run changes what
  the shots show, so after one copy its shots to `screenshots-gold/` again.
- The full run is `test_all.sh` and only run that when asked to "test".
- More than one goal in a response ends with a done/not-done checklist.
- Numbering of multi-item communication in summaries follows ISO 2145.
- Don't update usage text, tell the user to do that.
- Advice to change a setting gives the change as a settings view URL, from
  `index.html` on, to open in a report:
  `index.html#view=settings&setting=<NAME>&setting-values=<value>`,
  the value a JSON object of each setting's whole new value, base64.
  - The default directories for temp and output files for perf2html.sh and
  perf2html_diff.sh are intentionally "pinned" to the invocation directory.
  `perf2html_batch.sh` is just a convenience wrapper and will likely evolve.
  This is a closed discussion.

### Invariants

- `manifest_verify`/`manifest_fault` is the one door deciding whether a dir
  is a report - never bypass or duplicate this check elsewhere.
- Never buffer a child's output in a shipping script (`$( )` capture) - breaks
  `--verbose` streaming and hides live failures.
- Nothing test-specific, ever - no test names/file lists baked into
  `tests/perf2html/`; every view must work for every test in `TESTS_C`. The
  one exception is `test_screenshot.py`: screenshots are to be made from
  string literal golden bookmarks, and changing the url format must require
  changing those string literals.
- Screenshot code runs only in the shots `test_screenshot.py` takes and in
  the frames of `test_index.html`, so that no screenshot code can hide a bug
  in a page a user opens. The query keys `screenshot` and
  `screenshot-menu` gate all of it, a click through from `test_index.html`
  drops both, and the label shows the address without them. `toggle-dark`
  is not screenshot code: it takes the dark button's path and stays.
- Every `tests/perf2html/*.sh` makes paths absolute at startup; `$PWD` is
  never read again below `args_parse`. Getting this wrong breaks every
  relative invocation silently.
- buffering command stdout and stderr with `mktemp` is banned. Use of `mktemp`
  is to be by request only. The two door policy as follows. Door one is
  non-debug mode (section 0.3) with no `--artifacts`: each `perf2html.sh` and
  `perf2html_diff.sh` makes its own "TMP" directory with `mktemp -d`, which
  its `trap ... EXIT` deletes at every exit; the batch makes none. Door two
  is the diff's `.txz` archive extraction, deleted by the same trap in either
  mode. The design goal is that
  perf2html users get /tmp used as normal and cleaned up after too. And
  development work on perf2html uses a local artifact dir that can be
  debugged.
- No news is good news: nothing prints a success line unless `--verbose`, and
  when it does print, a success line goes to stdout and failures go to stderr -
  not the other way round.
- Every ok/success line a script of ours controls (including our Python tools'
  ok lines) is gated behind `--verbose`; an outside tool's own quiet switch is
  passed unless `--verbose` (e.g. `ruff --quiet`), curl's `--silent` unless
  level 2, as its progress meter would break the level 1 Markdown; a tool with
  no quiet switch (pyright) prints its one success line in a quiet run,
  accepted as-is; at level 1 `pyright_filtered_run` drops it, the maintainer's
  one exception.
- Level 2 (`VERBOSE_RAW_LEVEL`, `--verbose --verbose`) is plain text: no
  Markdown, no line of ours or a child's reformatted or filtered, every tool
  run without its quiet switch.
- `--regenerate` clears the report dir too - a report is output only, never
  read back as an input to itself.
- `test_expected_behavior.sh` captures, redirects or reformats no output of its
  own or a child's - every child runs through `subprocess_run` and its lines
  reach the terminal verbatim; a non-zero exit is `error_exit`. The one
  exception is `pyright_filtered_run` at level 1.
- `tools_resolve` (or equivalent) must find every formatter/linter before
  anything is deleted, naming every missing tool with its install command -
  never discover a missing tool mid-run after damage is done.
- `test_all.sh` captures nothing and makes no temp file - refusals stream live
  to the terminal; failure checks the exit code only.
- Plumbing (`perf2html.sh`, `perf2html_diff.sh`) and the batch (porcelain)
  share one working-directory rule, `report_path`: a report name not
  starting with `/` or `~/` sits under `--target-dir` (default `$PWD`).
- `tests/perf2html/scripts/test_whitelist.txt` is the one list of what source
  stages touch - no directory walk, no skip list, nothing unlisted touched.
- `tests/perf2html/scripts/README.md` holds one entry per file in
  `scripts/` and per `tests/perf2html/*.sh`, sectioned by name prefix,
  every line within 79 columns - a file added, removed or renamed there
  updates its entry in the same change.
- Verification never reads from the code under test for a calculation it's
  checking - local expected constants or a different-route recomputation only.
- `--verbose` is additive/counted - no bare `printf` wrappers.
- `tests/perf2html/` is bespoke tooling - one parser, one theme, no dead code
  or duplicate systems; the theme is color, notation, markup and layout
  alone, no home for whatever two pages share (section 0.5).
- Pages are deterministic - same input, byte-identical output.
- New identifiers need 2+ unabbreviated English words.
- Naming split: `_SCREAMING_SNAKE` for a script's own global, `_lowercase` for
  locals, bare names crossing into `utility.sh`.
- 79-column hard max for all `tests/perf2html/` source. Ruff will reformat.
- Comment blocks max 1 line (2 is an error via `test_source_scan.py`); longer
  reasoning goes in `declawed.md` instead. The file header is exempt from the
  line limit and the `ENGLISH_PUNCT` check, not from the glyph and escape
  checks.
- Comment punctuation: a comment holds only letters, digits, spaces and the
  `ENGLISH_PUNCT` marks `. , " ' ? : ! ( ) /`, so that each comment stays
  one plain English sentence. `test_source_scan.py` cuts the comment marks
  and any backtick code span, then faults the first other character on each
  comment line as `comment holds 'X' outside ENGLISH_PUNCT`.
- ASCII plus the specific whitelisted glyphs (`© ≈ ∞ ▲◄►▼ … █ ░ ▒ ▓ ◼`,
  the call graph's `─ │ └ ├ ┬` and a no-break space), written literally,
  never as HTML entities.
- No unicode escapes or runtime character constructors in source, comments
  and header included: `\u`, `\U`, `\x`, `\N{`, octal `\NNN`, CSS hex
  escapes, numeric entities (`&#65;`), `String.fromCharCode`,
  `String.fromCodePoint`, `unescape`, `atob`, `chr`, `bytes.fromhex`,
  `unicode_escape`. Named entities for ASCII (`&amp;`) are fine.
- Never say "meta" - say "header" or "manifest".
- Timer artifacts contain `counter` data. Never "events"/"metrics"/"stats".
- Follow source code style. Alphabetization of source sections matters.
- Settings declared as annotation + empty sentinel + `load_into` - don't add
  accessors or conversions, don't turn off `F821`/`reportUnboundVariable`.
- No decorative borders, no tooltips outside the two named exceptions.
- Design-pixel discipline: think in design px/ch, then scale; never retune a
  length by eyeballing one screen size.
- `scripts/` page scripts may carry comments under the 1-line limit, one `#`
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
  of a function in a single simple clear english sentence using only the
  `ENGLISH_PUNCT` marks for punctuation. Add a second line for warnings if
  needed.
- A comment never opens with the name of what it documents. Not
  `foo: the function foo finds bar.`, just `Finds bar.`

