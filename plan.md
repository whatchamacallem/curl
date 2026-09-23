# Plan: a failure-mode catalogue, and a stage in reformat.sh that triggers it

Two deliverables, in this order:

1. `dev/failure-modes.md`, one catalogue of every failure the perf2html
   tools are expected to handle, each entry naming how it is provoked.
2. A new stage in `dev/scripts/reformat.sh` that provokes them and checks
   each one failed the way the catalogue says. Code only: the stage
   documents nothing, it tests.

Nothing else changes in this session. No generator, no settings, no
README.md, no DECLAUDE.md.

## 1 What was surveyed

Every `sys.exit`, `raise`, `parser.error`, `self.fail` and shell `exit` in
`dev/`. The counts, by file:

| file                       | error sites | reachable from a fixture |
| -------------------------- | ----------- | ------------------------ |
| `shared.sh`                | 7           | 6                        |
| `perf2html.sh`             | 6           | 3                        |
| `perf2html_diff.sh`        | 4           | 4                        |
| `perf2html_batch.sh`       | 4           | 0                        |
| `reformat.sh`              | 2 + 6 rows  | 8                        |
| `callgrind.py`             | 4           | 4                        |
| `callgrind_diff.py`        | 2           | 2                        |
| `callgrind_to_heatmap.py`  | 5           | 4                        |
| `build_report.py`          | 5           | 5                        |
| `trace_to_speedscope.py`   | 11          | 6                        |
| `settings.py`              | 4 + 13      | 4                        |
| `theme.py`                 | 2           | 1                        |
| `validate_report.py`       | ~40 `fail`  | 6 representative         |
| `comment_block_scan.py`    | 1           | 1                        |
| JS `throw`                 | 4           | 0 (needs a browser)      |

## 2 The catalogue, `dev/failure-modes.md`

One table per family, every row `id | what breaks | how it is provoked |
what must be seen`. The id is what the reformat.sh stage names each case,
so the two files are joined by the id and nothing else.

### 2.1 Report integrity -- `shared.sh`

| id                  | provoked by                                              | expected                                                |
| ------------------- | -------------------------------------------------------- | ------------------------------------------------------- |
| `checksum_mismatch` | copy a second file into a report fixture                  | `does not match its recorded checksum`, found + expected |
| `manifest_absent`   | a populated directory with no `MANIFEST.txt`              | `has no MANIFEST.txt, so it is not a finished report`    |
| `manifest_version`  | rewrite line 1 to `curl/perf2html.sh v2`                  | `unrecognized MANIFEST.txt`, found + expected            |
| `manifest_no_dir`   | name a path that does not exist                           | `no such directory`                                      |
| `checksum_row_gone` | delete the `checksum=` row, keep line 1                   | `has no checksum= row`                                   |
| `report_not_dir`    | `--report=` naming a regular file                         | `the report path is not a directory`                     |
| `artifacts_inside`  | `--artifacts=` a path under `--report=`                   | `the artifacts directory is inside the report`           |
| `report_populated`  | `--report=` a non-empty dir with no manifest              | `holds files but no MANIFEST.txt`                        |

`checksum_mismatch` is the user's own example and is the cheapest of the
lot: `cp` one existing file to a new name inside a fixture copy, then ask
any tool to open it.

### 2.2 The diff -- `perf2html_diff.sh`, `callgrind_diff.py`

| id                   | provoked by                                            | expected                                     |
| -------------------- | ------------------------------------------------------ | -------------------------------------------- |
| `diff_of_a_diff`     | pass `perf2html_diff_report` as the baseline           | `can't diff a diff`, then the version fault  |
| `diff_no_common`     | two fixtures whose `<test>/` names do not overlap      | `the two reports have no test in common`     |
| `diff_no_archive`    | a fixture whose `*/raw/*.txz` are removed              | `no */raw/*.txz archive holding callgrind`   |
| `diff_too_many_args` | four positional directories                            | usage on stderr, exit 2                      |
| `diff_counters`      | two profiles whose `events:` lines differ              | `record different counters`, both lists      |
| `diff_no_ranking`    | a profile whose `events:` lacks the ranking counter    | `cannot supply <counter>`                    |

`diff_of_a_diff` is the user's second example. `diff_counters` and
`diff_no_ranking` are driven by a two-line hand-written callgrind file, not
by a report -- see 3.2.

### 2.3 The parser -- `callgrind.py`

| id                 | provoked by                                       | expected                            |
| ------------------ | ------------------------------------------------- | ----------------------------------- |
| `parse_no_events`  | a file with cost lines and no `events:` line      | `no 'events:' line`                 |
| `parse_ratio`      | edit one `summary:` so the self-check misses 1.0  | `does not add up to ... summary`    |
| `parse_name_ref`   | an `fn=(7)` with no prior `fn=(7) name`           | `refers to a name this file never spelled out` |
| `parse_merge`      | merge two files with different `events:`          | `cannot merge profiles with different counters` |

### 2.4 The generators -- `build_report.py`, `callgrind_to_heatmap.py`

| id                     | provoked by                             | expected                                |
| ---------------------- | --------------------------------------- | --------------------------------------- |
| `report_header_form`   | `--header LABEL` with no `=`            | `--header expects LABEL=VALUE`          |
| `report_block_form`    | `--header-block LABEL` with no `=`      | `--header-block expects LABEL=FILE`     |
| `report_block_absent`  | `--header-block L=/nonexistent`         | the path, then `the page cannot be built` |
| `report_callers_none`  | `--diff` with no `--callers-data`       | `--diff needs --callers-data`           |
| `report_callers_gone`  | `--callers-data /nonexistent`           | the path and the OSError                |
| `heat_baseline_none`   | `--diff` with no `--baseline-data`      | `--diff needs --baseline-data FILE`     |
| `heat_baseline_gone`   | `--baseline-data /nonexistent`          | `no such --baseline-data file`          |
| `heat_no_ranking`      | a profile without the ranking counter   | `cannot supply <counter>`               |

### 2.5 The trace -- `trace_to_speedscope.py`

| id                  | provoked by                                    | expected                              |
| ------------------- | ---------------------------------------------- | ------------------------------------- |
| `trace_absent`      | a path that does not exist                     | the path, the strerror, `cyg_callback.c writes` |
| `trace_not_a_trace` | 64 zero bytes                                  | `not a cyg_callback.c trace`          |
| `trace_partial_word`| a file whose length is not a multiple of 8     | `not a whole number of 8-byte words`  |
| `trace_truncated`   | a valid header claiming more records than follow | `truncated, or no time passed`      |
| `trace_no_output`   | no `-o` and no `--seen`                        | `-o is required without --seen`       |

The three that need a real build -- `buildid_verify`'s two and the "in no
executable mapping" one -- are catalogued and marked **not provoked**: they
need a `build-instr` tree and a recorded trace, which is a full profiling
run. The catalogue says so rather than pretending.

### 2.6 Settings -- `settings.py`

Driven by writing a throwaway module into a scratch dir on `sys.path` and
importing it, and by a corrupt copy of `settings.sh`:

| id                  | provoked by                                    | expected                          |
| ------------------- | ---------------------------------------------- | --------------------------------- |
| `setting_unknown`   | a module declaring `NO_SUCH_SETTING_NAME: str = ""` | `doesn't match any setting`  |
| `setting_no_annot`  | a bare `RANKING_COUNTER_NAME = ""`             | `settings must have sentinels`    |
| `setting_not_empty` | a sentinel written with a value                | `is written with`                 |
| `setting_wrong_type`| a setting annotated `int` that is a `str`      | `must not be coerced`             |
| `shell_grammar`     | a corrupt `settings.sh` line, e.g. `A=$(rm -rf /)` | `settings.sh line N`, the fix |

`shell_grammar` is the one that matters most and is nearly free: the
expansion table is what keeps `settings.py` from running anything, so a
line holding an unlisted `$(...)` must stop the import naming the line.

### 2.7 The validator -- `validate_report.py`

Six representative faults, each one file removed or truncated in a fixture
copy:

`validate_page_gone`, `validate_page_small`, `validate_href_broken`,
`validate_manifest_row`, `validate_archive_gone`, `validate_home_dir`
(a `$HOME` path written into a page).

### 2.8 Tooling absence -- `toolchain_check`

The user asked whether this can be tested. It can, and cheaply.
`toolchain_check` runs in `perf2html.sh` before any build, and decides
entirely on `command -v`. So:

| id              | provoked by                                          | expected                                     |
| --------------- | ---------------------------------------------------- | -------------------------------------------- |
| `tools_missing` | run `perf2html.sh --help`-less with `PATH` set to a scratch dir holding symlinks to every tool **but one** | `N tool(s) not found`, the tool, its official install command, exit 1 |
| `tools_perf`    | the same with `perf` held out                        | additionally the `linux-perf` note            |
| `tools_several` | three tools held out                                 | `3 tool(s) not found`, all three named        |
| `speedscope_bundle` | a `speedscope` stub on the stub PATH with no `dist/release` beside it | `no speedscope bundle at` |

The stub PATH is built by symlinking, into a scratch dir, every name
`toolchain_check` looks for except the one under test, plus `bash`, `sed`,
`grep`, `readlink`, `dirname` and the handful of coreutils the script needs
before the check. Held-out-one-at-a-time is a loop over the tool list read
out of `shared.sh`, so a tool added to `toolchain_check` later is covered
without editing the test.

Two caveats the catalogue will state:

- The run has to stop **at** the check. `perf2html.sh` reaches
  `toolchain_check` after `args_parse`, which reads
  `tests/perf/Makefile.inc` -- so the stub PATH needs `sed`, `grep` and
  `sort`, and the test asserts the exit came from the toolchain message
  rather than from the earlier `TESTS_C` error.
- `speedscope_bundle` needs a stub `speedscope` that `readlink -f` resolves
  somewhere with no `dist/release` above it. A plain executable file in the
  scratch dir does exactly that.

### 2.9 Not provoked, and why

A short closing section, so a later session does not re-derive it:

- the four JS `throw`s (`settings_handler.js`, `ui_strings.js`,
  `frame.js`, `flame_bootstrap.js`) need a browser; there is no headless
  runner in `dev/` and adding one is out of scope.
- `theme.py`'s `THEME_COLOR_PAIR_ENTRIES` length check fires at import of a
  corrupt `settings.py`, which is the same mechanism as 2.6 and is listed
  there instead.
- `trace_to_speedscope.py`'s build-id and mapping checks, per 2.5.
- `perf2html_batch.sh`'s four `rm -rf` failures need an unwritable
  directory, which is a root-owned path; catalogued, not provoked.
- `perf2html.sh`'s `--regenerate` faults (`stamp=` row absent, recordings
  missing) are provokable but need a kept artifacts dir, so they are
  catalogued as **fixture-dependent**: provoked when one is present,
  skipped with a printed reason when it is not.

## 3 The reformat.sh stage

### 3.1 Shape

One new stage function, `failure_modes_run`, called from `main()` after
`validate_run` and before the `_MISSING` block. It follows the existing
stage contract exactly:

- prints `Testing sjdhbskhjb...` before the test.
- prints `sjdhbskhjb OK.` after the test.
- respects `log_verbose` for the per-case detail and nothing else tests
  `$VERBOSE`.
- exit 1 on first error.

No failure tracking.

### 3.2 Fixtures

Each fixture is a plain function call with names made of words going
from less specific to more specific about nouns and verbs involved.

## 4 Order of work

1. `dev/failure-modes.md`, the catalogue, complete, with the
   not-provoked section.
2. `dev/scripts/failure_modes.sh`, `failure_case` plus the families in
   the order of section 2, verifying each case against the live tools as
   it is written -- a case that does not actually trigger is a bug in the
   plan, and the catalogue row gets corrected.
3. The `failure_modes_run` stage and its one call in `reformat.sh`.
4. `dev/perf2html_batch.sh` then `dev/scripts/reformat.sh`, per the
   workflow, so the new file passes the column, ASCII and comment checks
   it is now a peer of.
5. `DECLAUDE.md`: one short subsection under section 3 naming the stage,
   the two new files and the `failure_case` contract. Rule 1 requires it
   in the same change; the file is at 39,156 bytes of 40,000, so the
   addition has to be a handful of lines and may need an equally small
   trim elsewhere -- which is a compaction, so it gets asked about rather
   than done.

## 5 Open questions

1. **`failure-modes.md` under `dev/`** puts a second `.md` beside
   `README.md` and `DECLAUDE.md`. `reformat.sh`'s `_MARKDOWN_NAME` is an
   allow-list of one, so the new file is untouched by every stage --
   consistent with `DECLAUDE.md`, but it means nothing formats or
   column-checks it. Confirm that is wanted, or say it should be added to
   the allow-list.
2. **Rule 1 and the 40,000-byte ceiling.** See 4.5. The DECLAUDE.md note
   is required by rule 1 but the file is within 850 bytes of the limit.
   Preference: add the note and leave the file over-size with a printed
   warning, or trim first?
