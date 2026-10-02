# tasklist

Ten items from the session prompt of 2026-09-20. Each is assigned to one
agent. Agents that change files take a file lock; agents that only report
answer back through the normal channel and touch nothing.

No builds, no test runs, no `dev/*.sh` invocations in this pass. Verification
(`dev/perf2html_batch.sh` then `dev/scripts/reformat.sh`) happens only when
the user says so.

## File locking

An agent that writes takes `/tmp/claude-1000/-home-t-curl/locks/<file>.lock`
before its first edit of that file and releases it after its last, via
`mkdir` (atomic) with a short retry. The assignments below are partitioned so
that the only genuinely shared files are `dev/DECLAUDE.md` (every writing
agent appends its own section) and `dev/scripts/heatmap.html` (tasks 8 and
10).

## Tasks

### 1. reformat.sh header table: explain and extend ascii to \*.c \*.h

Agent: `claude`. Writes `dev/scripts/reformat.sh`,
`dev/scripts/validate_report.py`, `dev/DECLAUDE.md`.

- Answer why the table says what it says (`format`/`lint`/`cols`/`ascii` per
  source kind) and what `yes(1)` on `*.md *.json` means -- footnote (1)
  already reads "README.md only; DECLAUDE.md is not scanned".
- Turn on ASCII scanning for `*.c` `*.h`: `validate_report.py`'s
  `unicode_check` currently walks `.py/.js/.css/.sh/.html` + `README.md`.
  Add `.c`/`.h` to that walk, flip the table cell from `--` to `yes`, and fix
  any non-ASCII it finds in `dev/cyg_callback.c`.
- Update `DECLAUDE.md`'s `unicode_check` sentence to list the new kinds.

Status: **done**

### 2. toolchain_check: official install instructions for non-default deps

Agent: `claude`. Writes `dev/perf2html.sh`, `dev/DECLAUDE.md`.

- Audit every external tool `dev/*.sh` actually needs (`perf2html.sh`,
  `perf2html_diff.sh`, `perf2html_batch.sh`, `clean.sh`) -- not just the
  current `cmake ninja ccache cc valgrind perf taskset python3 addr2line
readelf speedscope` list.
- On a miss, print an official Ubuntu install line (`apt install ...`, or the
  upstream project's own documented install for what Ubuntu does not ship).
  No local/hand-rolled recipes.
- Omit anything that ships in a desktop Ubuntu base install.
- **Explicitly out of scope:** `reformat.sh`'s own tools (pyright, ruff,
  prettier, shfmt, clang-format). `dev/*.sh` is for tool users;
  `reformat.sh` is for tool development.

Status: **done**

### 3. Status rows: fixed "perf2html" outer, full path inner

Agent: `claude`. Writes `dev/scripts/theme.py`, `dev/scripts/frame.js`,
`dev/DECLAUDE.md`.

- Name the two first-cells the "status rows" in code and docs.
- Outer strip's first cell: always the literal `perf2html`, centered.
- Inner strip's first cell (when the second strip is visible): the menu
  selection as the outer one shows it today, centered, existing text color.
- The `all` view must not be clipped: render `all / summary`, not `all`, so
  the summary reads as its own page.
- Today `title_publish` writes `""` when framed; that inverts.
  `TITLE_COLUMNS` must still fit the widest string any page can show.

Status: **done**

### 4. Rename `trace` dir to `temporary_artifacts`

Agent: `claude`. Writes `dev/*.sh`, `dev/.gitignore`,
`dev/scripts/validate_report.py` (if referenced), `dev/README.md`,
`dev/DECLAUDE.md`.

Every `dev/trace/` path, message, comment and doc line. `TRACE_BUILD_DIR`
(`build-instr`), `PERF_TRACE_OUT`, `TRACE_JSON` and the trace *recording*
concept are a different thing and stay.

Status: **done**

### 5. Rename "caller sidecar" to "synthesized callers diff"

Agent: `claude`. Writes `dev/scripts/callgrind_diff.py`,
`dev/scripts/build_report.py`, `dev/scripts/callgrind_to_heatmap.py`,
`dev/scripts/validate_report.py`, `dev/DECLAUDE.md`.

Prose, comments and identifiers (`sidecar_load`, `BaselineSidecar`,
`sidecars`, `_CALLERS_SUFFIX` comments). The on-disk filename
`<delta>.callers.json` and the CLI flags `--callers-output` /
`--callers-data` / `--baseline-data` stay -- they are a contract.

Status: **done**

### 6. Top-50 functions table: rank and show CEst, not Ir

Agent: `claude`. Writes `dev/scripts/build_report.py`, `dev/DECLAUDE.md`.

`_EVENT = "Ir"` -> `"CEst"` for the non-diff summary's
"top 50 functions by self": replace the Ir column and rank by CEst. Scope is
that table; the diff table paths share `_EVENT`, so either split the constant
or state clearly that both moved.

Status: **done**

### 7. Explain the speedscope sampling architecture

Agent: `Explore` (read-only, reports back, writes nothing).

Is it one approach or several? Cover `-finstrument-functions` +
`dev/cyg_callback.c`, the `.bin`/`.maps` record format,
`trace_to_speedscope.py` pairing and its `_MAX_CALLS` cut,
`build_flame_graph.py`, and why callgrind is a separate pipeline.

Status: **done**

### 8. Remove all tooltips

Agent: `claude`. Writes `dev/scripts/build_report.py`,
`dev/scripts/theme.py`, `dev/scripts/callgrind.py`,
`dev/scripts/callgrind_to_heatmap.py`, `dev/scripts/heatmap.html`,
`dev/DECLAUDE.md`.

Every `title=` attribute and the plumbing that feeds it (`Column`
descriptions, `theme.Cell.title`, `cell_number()`/`call_count_cell()` exact
values, the popup's exact-value tooltips). Drop the parameters too, not just
the call sites. Several DECLAUDE lines promise tooltips ("exact in tooltip",
"Tooltips keep an explicit +/-") -- those go.

Coordinates with task 10 on `heatmap.html` via the lock.

Status: **done**

### 9. Version the localStorage store

Agent: `claude`. Writes `dev/scripts/theme.js`, `dev/DECLAUDE.md`.

`view_storage` gains a stored version string (`perf2html v1`); on read, a
mismatched or absent version clears every key the report owns, so a format
change is self-healing. Keys today: `heat.scale`, `heat.sort`, pane widths.

Status: **done**

### 10. (folded into 8) heatmap.html tooltip removal

Handled inside task 8 so one agent owns `heatmap.html`.

Status: **done**

## Postmortem

Eight agents, ten items, no lost work. Every lock was acquired and released;
the locks directory is empty and `git status` shows 16 modified files, all
expected. Two agents reported contending for `DECLAUDE.md` (one acquired on
try 23) and re-read the file before editing rather than writing over a
stale read - the protocol did its job.

**Nothing below is verified.** No agent built, ran a generator, or ran
`reformat.sh`, per instruction.

### 1. ascii scanning for \*.c \*.h -- went great

`.c`/`.h` added to `validate_report.py`'s `_UNICODE_SCAN_EXTS`, table cell
flipped to `yes`. `dev/cyg_callback.c` is the only such file and was already
pure ASCII (checked at byte level, zero bytes above 0x7F), so the new
coverage is green from the start with no cleanup pass.

The `yes(1)` question turned up a documentation bug: the footnote was
**not accurate as written**. It narrowed markdown to `README.md` but said
nothing about `*.json`, and JSON gets **no ASCII scan at all** - it is not in
`_UNICODE_SCAN_EXTS` nor `_UNICODE_SCAN_NAMES`. JSON sits on that row only
because it shares prettier with markdown in `format_prettier`'s one loop, and
the ascii column inherited a grouping that was never true for it. Footnote now
states both exclusions.

### 2. toolchain_check install instructions -- went great

The existing eleven-tool list was audited and found already complete; nothing
the diff or batch scripts call was missing. It now reports **all** misses at
once, still exiting 1, with official commands only: apt for cmake /
ninja-build / ccache / build-essential / valgrind / linux-tools-generic /
binutils, upstream `npm install -g speedscope`. `reformat.sh`'s tools stayed
out as specified.

`perf` kept `linux-tools-generic` as the official answer plus a WSL2 note,
because that binary is built against an Ubuntu kernel WSL does not run;
`linux-perf` is the kernel-independent build.

### 3. status rows -- went great

`frame.js`'s `title_publish` inverted: outer strip is the centered literal
`perf2html`, inner strip carries the centered selection. The `all` case is
solved **generally** - `selection_path()` appends `" / summary"` to any
single-segment path, so `all / summary` falls out of the same rule that
applies to any test name. Nothing test-specific was introduced.

`TITLE_COLUMNS` re-derived and **kept at 33**: widest inner string is
`simpleformat` (12) + `" / "` + `flame graph` (11) = 26, and no diff suffix
appears in rendered strings today. 7 columns of slack; growing it would only
eat strip width at the 1366px target.

`theme.css` gained one line (`justify-content: center` on `.strip .title`) -
`align-items: center` alone only centers vertically. That file was in no
task's ownership list; the change is minimal and correct.

### 4. trace -> temporary_artifacts -- went great

35 replacements across 6 files. Every recording-concept name correctly
preserved: `TRACE_BUILD_DIR`, `PERF_TRACE_OUT`/`SKIP`, `TRACE_JSON`,
`trace_record`/`trace_render`, `trace_to_speedscope.py`, `--trace-log`, the
`trace.<test>...bin` filenames, README's "traced run".

Best catch of the run: `reformat.sh`'s `files_of` had a
`-not -path '*/trace/*'` exclusion outside the agent's ownership list. Left
unchanged it would have silently stopped excluding raw data, letting the
linters walk callgrind output - invisible until a lint run started scanning
it. The agent took the lock and changed only that line.

Two renamed lines broke 79 columns and were restructured rather than
overflowed: `callers_file` now derives as `"$diff_file.callers.json"`, and
`TRACE_JSON` is built in two assignments. Both behaviour-identical.

### 5. caller sidecar -> synthesized callers diff -- went great

`BaselineSidecar` -> `SynthesizedCallers`, `sidecar_load` ->
`synthesized_callers_load`, `sidecars` -> `synthesized_callers`. Zero
"sidecar" left in `dev/` source. All contract preserved: `.callers.json`,
both `_CALLERS_SUFFIX` values, the three CLI flags, the camelCase JSON keys.

The rename forced two **moves** to keep file-shape conventions - the class
from the head to the tail of the record band, the method below `source_read`
to keep methods alphabetical (`so` < `sy`). A mechanical replace would have
broken both silently. Incidental fix: a stray comment was stranded above
`sidecar_load` instead of its owner `source_read`; the reorder put it back.

Applied cleanly on top of task 6's concurrent `build_report.py` edits,
re-wording the new `_DIFF_EVENT` comment rather than clobbering it.

### 6. top-50 by CEst -- went great, with a real finding

Chose to **split the constant** rather than move `_EVENT` outright:
`_EVENT = "CEst"` (core), `_DIFF_EVENT = "Ir"` (diff paths),
`_EVENT_FALLBACK = "Ir"`, plus a new `event_of()` resolving CEst -> Ir ->
first recorded event.

The reason is worth keeping: **CEst is derivable in a diff for the numerator
but not the denominator.** CEst is linear, so
`CEst(mod-base) == CEst(mod) - CEst(base)` - verified on two real callgrind
files, both exactly 16198. But `callers_data_load()` and
`baseline_total_load()` locate a baseline via `events.index(...) ->
costs[slot]`, a single slot in the recorded cost vector. CEst is a weighted
sum of seven recorded events and has no slot. A CEst diff would therefore
divide a CEst numerator by an Ir denominator, which is wrong, unless the
callers-JSON format changes. Out of scope; the code now says so.

`event_of()` is necessary because `profile.value()` **raises `KeyError`** for
an unsupplied event rather than returning 0.

**Expect a real page diff:** the ranking genuinely reorders. On one test CEst
promotes `_dl_relocate_object_no_relro` above the library function, because
CEst weights LL misses 100x. Intended effect, not a regression.

### 7. speedscope sampling architecture -- reported, nothing touched

Answer delivered in chat. Summary: it is **one approach, and it is not
sampling** - exhaustive `-finstrument-functions` instrumentation. One
recorder, one converter, one embedder; no second path, no fallback, no
merging of sources. The word "sampling" in the code's prose is a gate
(`next == end` = off), not a rate. Frame widths are exact rdtsc deltas for
individual calls, so the profile has no statistical validity as an aggregate.
Callgrind is a wholly separate pipeline on a different build tree and
structurally cannot produce a flame graph - `calls=` lines are aggregated
(caller, callee) totals with no order and no per-call durations.

### 8. remove all tooltips -- went great, with losses to review

50+ `title=` sites cleared across `theme.py`, `build_report.py` and
`heatmap.html`. `Cell.title` and `Column.title` fields deleted outright, not
left unused. Dead code removed: `exact_text()` and five now-unused locals.

Two judgement calls that prevented bugs:
- `Column("#", "rank", numeric=True)` would have silently passed `"rank"` as
  `numeric` once the description field was removed. Caught and fixed.
- `event_long`/`DerivedEvent.long`/`eventLong` are **not** tooltip plumbing -
  they supply the event dropdown's option text. Removing them would have
  broken the dropdown. Data kept, four misleading "for tooltips" comments
  reworded.

Four `title=` occurrences remain and are correct: two `<iframe title=>`
accessibility labels (iframes show no hover tooltip), one `data-title`
attribute that `frame.js` reads for the status row, and one `title=` kwarg
for the page title.

A **No tooltips** rule was added under Look and feel so this does not regress.

### 10. n/a

Folded into 8, so `heatmap.html` had a single owner and was never contended.

## Bug reports

- **`_MAX_CALLS` doc/code mismatch.** `trace_to_speedscope.py` has
  `_MAX_CALLS = 200`; `DECLAUDE.md` documents 512 and sizes its whole tuning
  discussion against 512 ("seven of the eight record fewer calls than that and
  emit their whole trace (79-202 calls)"). At 200 the cut is materially
  sharper - tests recording 79-202 calls now sit at the boundary, so several
  that used to emit a whole trace are being truncated. One side is stale and
  rule 1 says they move together. **Not fixed** - needs a decision on which
  number is correct.
- **`perf2html_diff.sh` has a second, inconsistent toolchain check.** A bare
  `command -v python3` in `main()` with no install hint - a duplicate system
  for the job `toolchain_check` now does properly. Rubs against the "no
  duplicate systems" rule. **Not fixed** (ownership).
- **Pre-script title flash.** `build_report.py`'s `strip_render` still renders
  the page title server-side into `#title`, visible for an instant before
  `frame.js` overwrites it. On the overview that flash now reads `overview`
  rather than `perf2html`. **Not fixed** (ownership); one-line change.
- **Columns now have no on-page explanation.** Tooltip removal took the only
  on-page documentation for: `% self`, `symbol`, `calls`, `callers`,
  `% of change`, `functions changed`, `self`, `incl`, `defined at`,
  `called at`. README.md is an events/views glossary and does not cover
  columns. The heat map's diff `self` description is the significant one - it
  was the only on-page statement of how to read a diff ("up is more, down is
  less, -100% is gone entirely, +100% is all new"). A caption or README
  section would be the fix; no agent invented one.
- **Precision lost from pages.** Exact integers behind every `2.1K`/`2.0G`,
  the explicit +/- exact diff values, and per-line detail
  (`N Ir self, N in calls over N calls`). The last is still reachable by
  clicking the line to open the popup, which keeps its stats table. Clipped
  text (symbols past 20 chars, paths, caller lists) is recoverable only by
  dragging the column.
- **On-disk `dev/trace/` still needs moving.** Deliberately not renamed. Needs
  `mv dev/trace dev/temporary_artifacts` to keep existing raw data usable for
  `--regenerate`, or a fresh recording run. It currently shows untracked
  because `.gitignore` no longer covers that name.
- **`TITLE_COLUMNS` remains fragile.** Still a written-down constant (33)
  rather than a computed one. It has 7 columns of slack today but will clip
  silently the next time a longer test name or a view label lands.
- **Verification is entirely outstanding.** Expect formatting fallout from
  tasks 3, 5 and 8, which moved many string lengths. Task 5 predicts
  byte-identical pages (comment/identifier changes only) - worth confirming
  via `--regenerate`. Task 6 predicts a genuine page diff in the top-50
  ranking. Task 9's prettier formatting of the new block is unconfirmed.
