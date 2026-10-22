# perf2html scripts

The [HTML Report Generators](#html-report-generators) are all you need to
profile and generate reports.

- [HTML Report Generators](#html-report-generators)

The rest of these sections are provided as a guide for interested developers.

These are the data formats.

- [URL Components](#url-components)
- [Browser Preferences](#browser-preferences)
- [Report Contents](#report-contents)
- [Raw Data Archive Contents](#raw-data-archive-contents)
- [Temporary Artifacts Contents](#temporary-artifacts-contents)

The remaining sections describe the source code implementing the `perf2html`
report generators. Start by running the tests and checking the results.

- [Call Graph Page](#call-graph-page)
- [Callgrind Parsing](#callgrind-parsing)
- [Database Page](#database-page)
- [Developer Scripts](#developer-scripts)
- [Error Overlay](#error-overlay)
- [Flame Graph](#flame-graph)
- [Heat Map](#heat-map)
- [Menu Strip](#menu-strip)
- [Overview Page](#overview-page)
- [Perf Measurement](#perf-measurement)
- [README Page](#readme-page)
- [Settings Files](#settings-files)
- [Test Harness](#test-harness)
- [Theme Library](#theme-library)
- [Tool Configuration](#tool-configuration)

## HTML Report Generators

| File                    | Purpose                                           |
| ----------------------- | ------------------------------------------------- |
| `../perf2html.sh`       | Builds RelWithDebInfo, profiles every test under  |
|                         | callgrind, perf stat and a function trace, then   |
|                         | writes one report.                                |
| `../perf2html_diff.sh`  | Subtracts a baseline report from a modified       |
|                         | report and writes a diff report, measuring        |
|                         | nothing.                                          |
| `../perf2html_batch.sh` | Writes a baseline report, a modified report built |
|                         | with the cmake flags given, then the diff of the  |
|                         | two.                                              |

## URL Components

- `dark-mode`: Query key of a view frame's address, `1` or `0`, that the top
  page writes so the view opens in the dark mode it shows.
- `debug`: Query key, value `1`, that unfreezes the settings so the settings
  view can apply a setting.
- `file`: Hash key, heat map view only, that names the source file to open.
- `function`: Hash key, heat map view only, that names the function to open and
  excludes `file` and `line`.
- `line`: Hash key, heat map view only, that names the line within `file` to
  scroll to.
- `localProfilePath`: Hash key, flame graph view only, that is speedscope's own
  key naming the profile to load.
- `screenshot=1`: Shows the page address in a corner label, without the  
  two screenshot keys.
- `screenshot-menu`: Query key, focuses that number menu button.
- `setting`: Hash key, settings view only, that focuses a setting.
- `setting-values`: Hash key that carries the base64 JSON object of the setting
  values to apply, writing `debug` into the top page's address in place.
- `test`: Hash key that names the test shown, absent when no test is selected.
- `toggle-dark`: Query key, `0` or `1`, that resets the browser preferences as
  the top page loads, `1` then toggling the dark mode as the dark button does.
- `view`: Hash key, one of `call-graph`, `database`, `heat-map`, `flame-graph`
  or `settings`.

## Browser Preferences

Reports keep user preferences in in the browser's `localStorage`, shared by
every report opened from the same origin. Each value is JSON, `null` meaning
the user never chose one and the default in `settings.py` applies.

If the `perf2html.version` does not match `STORAGE_VERSION` then all
preferences are reset at startup.

- `database.counter_list`: The database counters list, each line, calls,
  callers, callees or any counter, in the order of the pulldown and the
  columns, with whether the line is shown, every line toggled, the ranking
  counter too.
- `database.function_rows`: The database functions table row count, one of
  `TABLE_ROW_COUNT_CHOICES`.
- `heatmap.counter_list`: The heat map counters list, each line, calls or any
  counter, in the order of the pulldown and the columns, with whether the line
  is shown, the ranking counter always shown.
- `heatmap.scale`: The heat map scale curve, `log` or `linear`.
- `heatmap.sort`: The heat map sort order, `heat` or `name`.
- `log.display_length`: The load log line count the settings view shows.
- `perf2html.version`: The `STORAGE_VERSION` the other keys were written under.
- `speedscope-color-scheme`: Speedscope's scheme, `null` so that speedscope
  follows the color scheme its frame takes from the dark mode shown.
- `view.dark_mode`: The dark mode chosen, `1` or `0`.
- `view.scale`: The design scale multiple chosen, shown at the nearest stop.

## Report Contents

Reading a report requires opening `index.html`. The rest of the report is of no
interest to users, except perhaps automated processing of `MANIFEST.txt`.

Otherwise, if you are an interested developer, these are the rest of the files
in the directory. A diff report lacks the `call-graph/`, `flame-graph/`,
`flame-graph-app/` and raw data archive files.

- `scripts/*.js`: Files copied whole or modified, from the scripts/ dir.
- `call-graph/<test>.html`: A test's call graph page.
- `database/<test>.html`: A test's database page holding its JSON database
  model.
- `flame-graph-app/SourceCodePro-Regular.ttf-*.woff2`: The speedscope font.
- `flame-graph-app/speedscope-*.css`: The speedscope app's stylesheet.
- `flame-graph-app/speedscope-*.js`: The speedscope app.
- `flame-graph/index.html`: The flame graph page loading the speedscope app.
- `flame-graph/profiles/<test>.js`: A test's speedscope profile.
- `heat-map/data/<test>.js`: A test's heat map model.
- `heat-map/index.html`: The one heat map page for every test.
- `index.html`: The overview, the top page with the menu, home panel and frame.
- `MANIFEST.txt`: The version line, then the `LABEL=VALUE` rows, written last.
- `README.html`: The user contract as HTML, copied when `build/README.html` is
  newer than `README.md`, which the help link then opens.
- `README.md`: A copy of the user contract.
- `scripts/source_database.js`: The report's files and functions, no counter.
- `settings/index.html`: The settings view page.
- `sources/<path>.js`: A source file's text, the path's non-alphanumerics `_`.
- `timer-artifacts-<time_t>.txz`: The raw data archive, recorded at `<time_t>`.

## Raw Data Archive Contents

Every file sits in the archive's one root directory,
`timer-artifacts-<time_t>/`.

- `0_file_data.json`: Source directory file listing with mode flags.
- `<test>.callgrind.out`: A test's callgrind file, the repo root cut.
- `test_list.txt`: The test names, one per line, sorted.

In `0_file_data.json` each filename is associated with the following:

- `repo` : A project file with source.
- `git` : A non-contributing project file with no source.
- `sys` : A system file with source.
- `err` : A file that `callgrind` could not find or was deleted.

## Temporary Artifacts Contents

An HTML generation run keeps its temporary files in a directory under
`--artifacts`.

A regular report's run keeps these.

- `0_file_data.json`: The paths document, each path's code.
- `<test>.callgrind.out`: The callgrind recording.
- `<test>.cyg_callback.bin`: The function trace of the sampled run.
- `<test>.cyg_callback.bin.maps`: The traced process's mappings.
- `<test>.cyg_callback.log`: The trace page, both runs and the conversion.
- `<test>.perf-stat.csv`: The perf stat counters.
- `<test>.perf-stat.txt`: The timing page, command and counters.
- `<test>.perf-stat.summary`: The timing summary rows, one `label=value` each.
- `<test>.trace_to_speedscope.json`: The speedscope profile of the sampled run.
- `<test>.valgrind.log`: The valgrind log with the objects loaded.
- `perf2html.log`: The measuring run's log.
- `perf2html.regenerate.log`: The last `--regenerate` run's log, that run's
  alone.
- `perf2html.txt`: The manifest rows of the measuring run.
- `test_list.txt`: The test names, one per line, sorted.
- `timer-artifacts-<time_t>/`: The archive staging dir, the tar step's alone.

A diff report's run keeps these.

- `<test>.callgrind_diff.json`: The callers diff with the baseline costs.
- `<test>.callgrind_diff.out`: The callgrind delta, modified minus baseline.
- `baseline.txt`: The baseline report's header block.
- `baseline/`: The baseline report's raw data archive, extracted.
- `modified.txt`: The modified report's header block.
- `modified/`: The modified report's raw data archive, extracted.
- `perf2html_diff.log`: The diff run's log.
- `perf2html_diff.regenerate.log`: The last diff `--regenerate` run's log, that
  run's alone.
- `test_list.txt`: The test names, one per line, sorted.

## Call Graph Page

| File              | Purpose                                                |
| ----------------- | ------------------------------------------------------ |
| `call_graph.html` | Templates the call graph page of one test, holding the |
|                   | JSON call graph model on the empty layout table that   |
|                   | `call_graph.js` fills.                                 |
| `call_graph.js`   | Fills the layout table with a row per shown node, each |
|                   | callee's share of its caller's cumulative cost heat    |
|                   | colored, opens and closes nodes in place, the hottest  |
|                   | path open by default, and sends the focused path to    |
|                   | the status bar.                                        |

## Callgrind Parsing

| File                   | Purpose                                            |
| ---------------------- | -------------------------------------------------- |
| `artifacts.py`         | Holds the artifacts contract: every temporary      |
|                        | file's path, the test list, and the missing file   |
|                        | error.                                             |
| `callgrind.py`         | Parses callgrind files into the one profile model, |
|                        | with costs, derived counters and display paths.    |
| `callgrind_diff.py`    | Subtracts the baseline profile from the modified   |
|                        | profile and writes the delta and the callers JSON. |
| `callgrind_symbols.py` | Names the functions that callgrind left as         |
|                        | addresses in one recording.                        |

## Database Page

| File            | Purpose                                              |
| --------------- | ---------------------------------------------------- |
| `database.html` | Templates the database page of one test, holding the |
|                 | JSON database model of every called function, its    |
|                 | file, line, calls, callers, callees and recorded     |
|                 | counters, and the terms of the derived counters,     |
|                 | that `database.js` draws.                            |
| `database.js`   | Draws the functions table under its heading with its |
|                 | row count, one row per called function linking to    |
|                 | it: the function, file and line, then the shown      |
|                 | lines of its counters list, then activates the page  |
|                 | as a view that scrolls to the top when the address   |
|                 | is followed again.                                   |

## Developer Scripts

| File            | Purpose                                               |
| --------------- | ----------------------------------------------------- |
| `../archive.sh` | Packs the repository's `.git` into a dated `.git.txz` |
|                 | backup, or restores the checkout from one beside it.  |
| `../clean.sh`   | Deletes every generated file under `tests/perf2html/` |
|                 | and the ccache entries the builds made.               |

## Error Overlay

| File               | Purpose                                               |
| ------------------ | ----------------------------------------------------- |
| `debug.js`         | Templates the report's debug script, the manifest     |
|                    | table the error report shows, then the debug tip.     |
| `error_overlay.js` | Catches the first error a page throws, relays it up   |
|                    | the frames and replaces the top page with a plain     |
|                    | error report.                                         |
| `utility.js`       | Reports a failed load of a link, script or image, and |
|                    | keeps the log.                                        |

## Flame Graph

| File                     | Purpose                                         |
| ------------------------ | ----------------------------------------------- |
| `build_flame_graph.py`   | Writes the flame graph page and one base64      |
|                          | profile script per test for the speedscope app. |
| `flame_graph.html`       | Templates the flame graph page that loads the   |
|                          | speedscope app and the report scripts.          |
| `flame_graph.js`         | Waits for speedscope to start, then opens the   |
|                          | profile of the addressed test.                  |
| `trace_to_speedscope.py` | Converts a function trace log into a speedscope |
|                          | profile of the busiest run.                     |

## Heat Map

| File                      | Purpose                                      |
| ------------------------- | -------------------------------------------- |
| `callgrind_to_heatmap.py` | Writes the heat map data and sources of each |
|                           | test, the paths document a diff derives and  |
|                           | the one heat map page.                       |
| `heat_map.css`            | Styles the heat map tree, source table,      |
|                           | information box, ticker tape and minimap.    |
| `heat_map.html`           | Templates the heat map page with its tree    |
|                           | pane, main box, minimap and text bars.       |
| `heat_map.js`             | Draws the heat map tree, source view and     |
|                           | info boxes for every test.                   |

## Menu Strip

| File             | Purpose                                                 |
| ---------------- | ------------------------------------------------------- |
| `menu.js`        | Holds the menu controller, which draws the strip, takes |
|                  | keys and starts every navigation.                       |
| `preferences.js` | Holds the preferences the menu edits and a view draws   |
|                  | with, their choices, each counters list's lines and     |
|                  | labels, and the reader of each counter, a derived       |
|                  | one summed from its terms.                              |

## Overview Page

| File              | Purpose                                              |
| ----------------- | ---------------------------------------------------- |
| `build_report.py` | Writes the overview page with its menu, the database |
|                   | page of each test, and a regular report's call graph |
|                   | page of each test.                                   |
| `frame.js`        | Holds the model of the top page, which checks the    |
|                   | address and loads each view into the frame.          |
| `overview.html`   | Templates the top page with the menu, the home panel |
|                   | and the view frame.                                  |
| `overview.js`     | Fills the home panel's headings and raw data link,   |
|                   | then draws its tables from the rows the page holds.  |

## Perf Measurement

| File              | Purpose                                              |
| ----------------- | ---------------------------------------------------- |
| `perf_measure.py` | Runs the perf test executable under callgrind, perf  |
|                   | stat and the function trace, the one caller of perf, |
|                   | and parses the timing page for the overview and the  |
|                   | summary rows the measuring run prints.               |

## README Page

| File                   | Purpose                                         |
| ---------------------- | ----------------------------------------------- |
| `build_readme_page.py` | Uses `cmark-gfm`, unless the page is newer than |
|                        | every file it is built from.                    |
| `readme_page.html`     | Templates the README page.                      |

## Settings Files

| File                 | Purpose                                              |
| -------------------- | ---------------------------------------------------- |
| `settings.js`        | Written from Python.                                 |
| `settings.py`        | Holds every PY and JS setting with the reader and    |
|                      | writer that load and ship them.                      |
| `settings.sh`        | Holds every shell setting, read by the shell scripts |
|                      | and by `settings.py`.                                |
| `settings_page.html` | Templates the settings view                          |
| `settings_page.js`   | Draws every setting in an editable JSON box.         |
| `ui_strings.js`      | Holds every user interface string, looked up by      |
|                      | name.                                                |

## Test Harness

| File                        | Purpose                                      |
| --------------------------- | -------------------------------------------- |
| `test_all.sh`               | Runs `test_expected_behavior.sh` with kept   |
|                             | artifacts, then `test_error_handling.sh`.    |
| `test_error_handling.sh`    | Proves the cached and regenerated runs, then |
|                             | checks the exit code of each failure mode.   |
| `test_expected_behavior.sh` | Formats, lints and scans the sources, runs   |
|                             | the batch, checks the reports, takes         |
|                             | screenshots, then builds `README.html`.      |
| `test_report.py`            | Checks the pages, manifest, checksum, heat   |
|                             | map, flame graph and timer artifacts of one  |
|                             | report.                                      |
| `test_screenshot.py`        | Shoots the golden bookmarks of one report in |
|                             | Chrome and writes `test_index.html`.         |
| `test_source_scan.py`       | Faults long comment blocks, comment          |
|                             | punctuation, glyphs and escapes in the given |
|                             | sources.                                     |
| `test_template.html`        | Templates the index of report links over a   |
|                             | grid of framed report pages that             |
|                             | `test_screenshot.py` fills in.               |
| `test_utility.sh`           | Holds the functions shared by the test       |
|                             | scripts.                                     |
| `test_whitelist.txt`        | Lists the file globs that the format, lint   |
|                             | and scan stages touch.                       |

## Theme Library

| File             | Purpose                                                |
| ---------------- | ------------------------------------------------------ |
| `dark_mode.css`  | Overrides every light mode color rule with a dark mode |
|                  | role unless dark mode is disabled.                     |
| `light_mode.css` | Holds every light mode color rule, linked before the   |
|                  | dark mode sheet.                                       |
| `theme.css`      | Lays out every page as a grid of its regions, then     |
|                  | styles the strips, tables and text scrollbars.         |
| `theme.js`       | Holds the shared page library for addresses, strips,   |
|                  | tables, numbers, scrollbars and layout.                |
| `theme.py`       | Writes table rows and numbers, fills the page          |
|                  | templates, and writes the shared scripts.              |

## Tool Configuration

| File                 | Purpose                                           |
| -------------------- | ------------------------------------------------- |
| `.prettierrc.json`   | Sets the prettier line width, prose wrap and line |
|                      | endings for the formatting checks.                |
| `pyrightconfig.json` | Configures the pyright type check of the Python   |
|                      | scripts.                                          |
| `ruff.toml`          | Configures the ruff formatter and linter for the  |
|                      | Python scripts.                                   |
| `utility.sh`         | Holds every function shared by the shipping shell |
|                      | scripts.                                          |
