# perf2html scripts

The [HTML Report Generators](#html-report-generators) are all you need to
profile and generate reports.

- [HTML Report Generators](#html-report-generators)

The remainder of these sections describe the source code implementing the
`perf2html` report generators as a guide for interested developers.

- [Callers Page](#callers-page)
- [Callgrind Parsing](#callgrind-parsing)
- [Error Overlay](#error-overlay)
- [Flame Graph](#flame-graph)
- [Heat Map](#heat-map)
- [Maintenance](#maintenance)
- [Menu Strip](#menu-strip)
- [Overview Page](#overview-page)
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
| `../perf2html_batch.sh` | Writes a baseline report, a modified report built |
|                         | with the cmake flags given, then the diff of the  |
|                         | two.                                              |
| `../perf2html_diff.sh`  | Subtracts a baseline report from a modified       |
|                         | report and writes a diff report, measuring        |
|                         | nothing.                                          |

## Callers Page

| File           | Purpose                                                  |
| -------------- | -------------------------------------------------------- |
| `callers.html` | Templates the callers page of one test with its heading  |
|                | and function table.                                      |
| `callers.js`   | Activates the callers page as a view that scrolls to the |
|                | top when the address is followed again.                  |

## Callgrind Parsing

| File                   | Purpose                                            |
| ---------------------- | -------------------------------------------------- |
| `callgrind.py`         | Parses callgrind files into the one profile model  |
|                        | with costs, derived counters and display paths.    |
| `callgrind_diff.py`    | Subtracts the baseline profile from the modified   |
|                        | profile and writes the delta and the callers JSON. |
| `callgrind_symbols.py` | Names the functions that callgrind left as         |
|                        | addresses in one recording.                        |

## Error Overlay

| File               | Purpose                                                |
| ------------------ | ------------------------------------------------------ |
| `debug.js`         | Templates the report's debug script, the manifest      |
|                    | table the error report shows, then the debug tip.      |
| `error_overlay.js` | Catches the first error a page throws and replaces the |
|                    | top page with a plain error report.                    |
| `utility.js`       | Relays an error report up the frames and reports a     |
|                    | failed load of a link, script or image.                |

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
|                           | test, then the one heat map page.            |
| `heat_map.css`            | Lays out the heat map tree, source table,    |
|                           | minimap and info boxes.                      |
| `heat_map.html`           | Templates the heat map page with its strip,  |
|                           | tree pane, main box, minimap and text bars.  |
| `heat_map.js`             | Draws the heat map tree, home tables, source |
|                           | view and info boxes for every test.          |
| `heat_map_main.html`      | Templates the heat map home with its lines   |
|                           | table and functions table.                   |

## Maintenance

| File            | Purpose                                                  |
| --------------- | -------------------------------------------------------- |
| `../archive.sh` | Packs the git repository into a dated `.git.txz` backup, |
|                 | or restores one when it is the only file present.        |
| `../clean.sh`   | Removes every ignored file but `tmp/`, then evicts the   |
|                 | profiling builds from ccache.                            |

## Menu Strip

| File       | Purpose                                                       |
| ---------- | ------------------------------------------------------------- |
| `menu.css` | Styles every strip and pulldown, the menu, the heat map strip |
|            | and the table headings.                                       |
| `menu.js`  | Holds the menu controller, which draws the strip, takes keys  |
|            | and starts every navigation.                                  |

## Overview Page

| File              | Purpose                                                |
| ----------------- | ------------------------------------------------------ |
| `build_report.py` | Writes the overview page with its menu and the callers |
|                   | page of each test.                                     |
| `frame.js`        | Holds the model of the top page, which checks the      |
|                   | address and loads each view into the frame.            |
| `overview.html`   | Templates the top page with the menu, the home panel   |
|                   | holding each test's logs, and the view frame.          |

## Settings Files

| File               | Purpose                                               |
| ------------------ | ----------------------------------------------------- |
| `settings.html`    | Templates the settings view, one pre that             |
|                    | `settings_page.js` fills, beside its text bar.        |
| `settings.js`      | Templates the settings every page reads, the top page |
|                    | installing them, a framed page taking them relayed,   |
|                    | then writes every root value a stylesheet reads.      |
| `settings.py`      | Holds every Python and JavaScript setting with the    |
|                    | reader and writer that load and ship them.            |
| `settings.sh`      | Holds every shell setting, read by the shell scripts  |
|                    | and by `settings.py`.                                 |
| `settings_page.js` | Lists every setting over an editable JSON box with    |
|                    | link, copy, paste and apply buttons, then applies the |
|                    | value an address carries.                             |
| `ui_strings.js`    | Holds every user interface string, looked up by name. |

## Test Harness

| File                        | Purpose                                      |
| --------------------------- | -------------------------------------------- |
| `test_all.sh`               | Runs `test_expected_behavior.sh` with kept   |
|                             | artifacts, then `test_error_handling.sh`.    |
| `test_error_handling.sh`    | Proves the cached and regenerated runs, then |
|                             | checks the exit code of each failure mode.   |
| `test_expected_behavior.sh` | Formats, lints and scans the sources, runs   |
|                             | the batch, then checks the reports and takes |
|                             | screenshots.                                 |
| `test_index.html`           | Holds the grid of framed report pages that   |
|                             | `test_screenshot.py` fills in.               |
| `test_report.py`            | Checks the pages, manifest, checksum, heat   |
|                             | map, flame graph and timer artifacts of one  |
|                             | report.                                      |
| `test_screenshot.py`        | Shoots the golden bookmarks of one report in |
|                             | Chrome and writes `test_index.html`.         |
| `test_source_scan.py`       | Faults long comment blocks, comment          |
|                             | punctuation, glyphs and escapes in the given |
|                             | sources.                                     |
| `test_utility.sh`           | Holds the functions shared by the test       |
|                             | scripts.                                     |
| `test_whitelist.txt`        | Lists the file globs that the format, lint   |
|                             | and scan stages touch.                       |

## Theme Library

| File             | Purpose                                                 |
| ---------------- | ------------------------------------------------------- |
| `dark_mode.css`  | Overrides every light mode color rule with a dark mode  |
|                  | role unless dark mode is disabled.                      |
| `light_mode.css` | Holds every light mode color rule, linked before the    |
|                  | dark mode sheet.                                        |
| `theme.css`      | Holds the layout rules shared by every report page.     |
| `theme.js`       | Holds the shared page library for addresses, strips,    |
|                  | tables, numbers, scrollbars and layout.                 |
| `theme.py`       | Renders tables, numbers and page heads, then writes the |
|                  | shared assets and checks the root value names the       |
|                  | stylesheets read.                                       |

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
