# perf2html task list

Four independent tasks, one subagent each. Nobody builds, tests or runs any
script in this round: edit source only, and leave verification
(`dev/perf2html_batch.sh` then `dev/scripts/reformat.sh`) to the user.

## File ownership protocol

Several tasks touch the same tree, so a file is claimed by **renaming it** to
carry the claiming task's number. The rename is the lock: it is atomic, and any
other agent can see it.

1. Before editing `<path>`, rename it to `<path>.<task-number>` (`git mv` is
   not needed; plain `mv` is fine).
   - `scripts/heatmap.html` claimed by task 1 becomes `scripts/heatmap.html.1`.
1. If `<path>` is missing but `<path>.<other>` exists, another task owns it.
   **Sleep and retry** - `sleep 20` in a loop, re-checking each time. Do not
   edit the `.N` file of another task, and do not rename it back.
1. Edit through the claimed `<path>.<task-number>` name.
1. When done with that file, rename it back to `<path>` immediately - hold a
   claim no longer than the edits to that one file take.
1. Claim files one at a time where possible, and release before claiming the
   next, so two tasks needing the same two files cannot deadlock.
1. A task is finished only when every file it claimed is back under its
   original name. Never leave a `.N` file behind.

## Project rules that still apply

`dev/CLAUDE.md` (symlink to `dev/DECLAUDE.md`) governs everything: 79-column
hard max on every line of `dev/` source, ASCII plus the short allow list
(`≈ ▲ ▶ ▼ …` written literally), `# <Name> - what it is` comments and no
docstrings, constants alphabetical ignoring a leading `_`, no test-specific
anything, no fake data, no tooltips. Update `dev/DECLAUDE.md` in the same
change whenever a task alters tooling, layout, theme or findings - each task
below says which sections it owns.

## 1. Split the JS out of `scripts/heatmap.html`

`scripts/heatmap.html` is ~66KB and almost all of it is one `<script>` block;
only the first ~35 lines are markup. Move that block's contents into a new
`scripts/heatmap.js` and leave a `__HEATMAP_JS__` substitution marker in its
place, exactly parallel to the existing `__THEME_JS__`.

- `heatmap.html` keeps its markup, its
  `<script id="heatdata" type="application/json">__DATA__</script>` block and
  its `__THEME_JS__` block, and gains `<script>\n  __HEATMAP_JS__;\n</script>`
  (or without the trailing semicolon, whichever reads right) where the big
  block was.
- `scripts/callgrind_to_heatmap.py` currently does
  `BODY.replace("__THEME_JS__", theme.theme_js()).replace("__DATA__", data)`.
  Add a third holder constant read through `theme.theme_asset("heatmap.js")`
  and a third `.replace("__HEATMAP_JS__", ...)`. Holder names are free (nothing
  looks a constant up by name), but keep the file-shape rules: constants
  alphabetical ignoring `_`, and the new constant sits with `BODY` and `_CSS`
  at the top.
- Substitution order matters: `__DATA__` also appears inside `heatmap.html`,
  and the moved JS may contain text that later replaces would disturb.
  Substitute so no replacement can rewrite text introduced by an earlier one.
- The generated page must be byte-identical in behaviour: same script order
  (data JSON, then theme JS, then heat map JS), same inlining. Whitespace
  around the inlined block may differ; nothing else may.
- No comments in the page assets (`.js`/`.css`/`.html`) - that rule extends to
  the new `heatmap.js`.
- `scripts/reformat.sh` picks up a new `.js` under `scripts/` with no list to
  edit, so nothing there needs changing. Check that assumption rather than
  assuming it.
- `validate_report.py` greps generated pages for `report_ui.layout_activate`;
  it must still be present in the generated page after the move.
- DECLAUDE.md: update the "No generator holds a multi-line HTML/CSS/JS literal
  any more" bullet's file->holder list, the JS-naming section's note about
  `heatmap.html`'s `__DATA__`/`__THEME_JS__` markers, and the "Popup 'copy' ...
  It lives in `scripts/heatmap.html`" gotcha if the popup code moves.

Files: `scripts/heatmap.html`, new `scripts/heatmap.js`,
`scripts/callgrind_to_heatmap.py`, `DECLAUDE.md`.

## 2. One event knob: `_EVENT = "CEst"` everywhere

`scripts/build_report.py` has three event constants where the user wants one.
Collapse them to a single `_EVENT = "CEst"` that is the universal default, and
make every consumer support a **derived** event so `_EVENT` can later be set to
any event, recorded or derived, with no other edit.

- Delete `_EVENT_FALLBACK`. `event_of()` exists because `Profile.value()`
  raises `KeyError` on an event a profile cannot supply; decide deliberately
  what replaces it. Preferred: keep a resolver, but have it fall back to the
  profile's first available event rather than to a second named constant, so
  there is no second name to explain.
- Delete `_DIFF_EVENT`. Every diff path (`diff_test`, `diff_functions_table`,
  the diff overview, `callers_data_load()`, `baseline_total_load()`) moves to
  `_EVENT`.
- The blocker is real and must be fixed, not worked around:
  `callgrind_diff.py`'s synthesized callers diff (`CallersDoc`) stores
  baselines as bare cost vectors plus an `events` list, and the readers locate
  a baseline by `events.index(<event>)`. A derived event such as `CEst` has no
  slot, which is the only reason the diff was pinned to a recorded event.
  `callgrind.Profile` already resolves derived events
  (`resolved_derived_events()`, `event_names()`, `value()`), and `CEst` is
  linear, so `CEst(mod - base) == CEst(mod) - CEst(base)` holds. Fix the format
  so a derived event has a slot: when writing `CallersDoc`, append every event
  the baseline profile can derive to `events` and append each one's computed
  value to every cost vector it writes (`baseline`, `baselineTotal`, and any
  per-caller vector). Then `events.index("CEst")` resolves like any other and
  every reader works unchanged.
  - Writers: `callgrind_diff.py`'s `callers_write` / `costs_trim` /
    `baseline_costs` and whatever else builds those vectors.
  - Readers: `build_report.py`'s `CallersData` / `callers_data_load()` /
    `baseline_total_load()`, and `callgrind_to_heatmap.py`'s
    `SynthesizedCallers` / `synthesized_callers_load()` (`--baseline-data`).
  - Keep every vector's existing recorded-event slots at their existing indices
    so the change is purely additive.
  - The `--event` CLI flag of `callgrind_diff.py` and `_EVENT` in that file
    (`callgrind_diff.py:_EVENT = "Ir"`) are part of this: make the default
    `CEst` too, so the whole toolchain has one default. The file name, the
    flags and the JSON keys are contract - do not rename any of them.
- `callgrind_to_heatmap.py`'s `_DEFAULT_EVENT = "CEst"` already agrees; leave
  its name alone but make sure nothing in the diff path now contradicts it.
- Verify by reading, not running: every place that previously read
  `_DIFF_EVENT` must now tolerate `_EVENT` being derived, and every place that
  previously read `_EVENT` must tolerate it being recorded. No `KeyError` path
  may become reachable for a profile that records the normal event set.
- DECLAUDE.md: rewrite the `build_report.py` bullet's "Two event constants, one
  per side of the core/diff split" paragraph - it currently documents exactly
  the design being removed, including the claim that moving the diff to CEst
  "means changing `callgrind_diff.py`'s synthesized callers diff format" (which
  this task does). Also update the "Diff semantics" bullet about baselines
  riding in the synthesized callers diff, and the `callgrind_diff.py` bullet.

Files: `scripts/build_report.py`, `scripts/callgrind_diff.py`,
`scripts/callgrind_to_heatmap.py`, `DECLAUDE.md`.

## 3. Progress output in `perf2html_batch.sh` without `--verbose`

Quiet mode currently prints a partial line (`printf '%-2s%-11s'`) before a step
runs and completes it (`| ok | 12s`) afterwards, so a step's identity sits in a
half-written line for minutes and the OS may not forward it. Replace that with
whole lines only.

- **Never leave a line unterminated.** Every progress message is a complete
  line ending in a newline, printed before the call that may take over three
  seconds begins.
- Before each such call: `[2.14s] running perf2html.sh <args>...`
- After it returns: `[2.34s] done: perf2html.sh <args>` - and something clearly
  distinct on failure, naming the step and the exit code.
- The bracketed number is **seconds since the script started**, with two
  decimal places. Bash's `SECONDS` is integer-only, so source the fractional
  value another way (`EPOCHREALTIME` is available in the bash on this box;
  compute against a start value captured at the top of `main`). Keep it a shell
  builtin where possible - no new tool dependency, since `toolchain_check` in
  `perf2html.sh` is the only toolchain check and this script does not have one.
- The same `[Ns]` prefix goes on every message the script prints in quiet mode,
  including the opening
  `dev/perf2html_batch.sh <stamp>: modified build flags: ...` line and the
  closing `file://...` URL line, so the whole log reads as one timeline.
- **Stats must be obviously attached to their step.** The current `| ok | 12s`
  status line is the "strange status line" being replaced: put the
  elapsed-time-for-this-step figure in the `done:` line next to the step name,
  rather than in a column that depends on the earlier half-line. Keep
  `took()`'s `1m23s` formatting for that per-step figure if it still reads
  well.
- Apply the same treatment to any other call in the script that can exceed
  three seconds.
- `--verbose` behaviour may keep its `== N name: cmd ==` banners; do not
  regress it. The failure path that tails 40 lines of `$RUN_LOG` stays.
- Text this script echoes is terminal output, not page content, so rewrapping
  is free - but the 79-column limit still applies to the source, and
  `long_lines_report` cannot reformat an `echo`/`printf` string for you.
- DECLAUDE.md: update the `perf2html_batch.sh` bullet under "How the four
  scripts fit together" and the "Quiet mode logs to
  `dev/temporary_artifacts/*.log`" bullet if its behaviour changes.

Files: `perf2html_batch.sh`, `DECLAUDE.md`.

## 4. Name the event in the heat map popup's stats table

In the per-line detail popup (`heat.detail.stats`, built in the heat map JS),
the stats table's column titles are `metric | share | amount`. They must name
what is actually being shown: the current event, its share of the global total,
and its count.

Before:

```text
<file>:<line> in <fn>
| metric                     |  share | amount |
| -------------------------- | -----: | -----: |
| self cycle estimate / CEst | <0.01% |    96K |
```

After:

```text
<file>:<line> in <fn>
| event                      | global % | count |
| -------------------------- | -------: | ----: |
| self cycle estimate / CEst |   <0.01% |   96K |
```

- Exactly three changes: column 1 title `metric` -> `event`, column 2 `share`
  -> `global %`, column 3 `amount` -> `count`. Mirror them precisely; change
  nothing else about the table, its rows, its heat or its ordering.
- Column 1 may already read `event` in the source - if so, that part is already
  done; do not invent further edits.
- The table below it (the caller/`by call count` table) is **unchanged**.
- The same `stat_columns` array feeds `table_html()` and `table_markdown()`, so
  the popup and its "copy" markdown stay in step automatically - confirm that
  rather than editing two places.
- A column's title is its width floor in both `column_widths()` (heat map JS)
  and `table_render()` (theme.py): `global %` is wider than `share`, so the
  column gets wider. That is expected and correct; do not add a width override
  to fight it.
- This text lives in whichever file holds the heat map JS. **Task 1 is moving
  that JS out of `scripts/heatmap.html` into `scripts/heatmap.js`.** Follow the
  ownership protocol: whichever file currently exists un-suffixed is the one to
  claim, and if both are mid-move, sleep and retry until task 1 has released
  its claim.
- DECLAUDE.md: the "The popup opens with a `event | share | amount` stats
  table" bullet under "Heat map internals (gotchas)" names the old titles -
  update it.

Files: `scripts/heatmap.html` or `scripts/heatmap.js` (whichever task 1 has
left in place), `DECLAUDE.md`.
